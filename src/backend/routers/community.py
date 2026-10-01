"""Shared community feed, separate from each user's private scan history."""
import asyncio
import hashlib
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from google.api_core.exceptions import AlreadyExists
from google.cloud import firestore
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..services.database_service import get_database_service
from ..services.user_identity_service import UserIdentity, require_user
from ..services.community_image_service import MAX_IMAGE_BASE64, normalize_post_image


class BoundedPostRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def bounded(request: Request):
            if request.method == "POST":
                body = bytearray()
                async for chunk in request.stream():
                    if len(body) + len(chunk) > 256 * 1024:
                        raise HTTPException(413, "Post too large")
                    body.extend(chunk)
                request._body = bytes(body)
            return await handler(request)
        return bounded

def fresh_response(response: Response):
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(prefix="/community", route_class=BoundedPostRoute,
                   dependencies=[Depends(fresh_response)])
limiter = Limiter(key_func=get_remote_address)
COLLECTION = "community_posts"
RPC_TIMEOUT = 4


class PostRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(default="", max_length=2000)
    request_id: UUID
    image: str | None = Field(default=None, max_length=MAX_IMAGE_BASE64)

    @field_validator("content")
    @classmethod
    def trim_content(cls, value):
        value = value.strip()
        return value

    @model_validator(mode="after")
    def require_content(self):
        if not self.content and not self.image:
            raise ValueError("Empty post")
        return self


def collection():
    service = get_database_service()
    if not service:
        raise HTTPException(503, "Database unavailable")
    return service.db.collection(COLLECTION)


def public_post(doc):
    data = doc.to_dict()
    created = data.get("created_at")
    return {"id": doc.id, "author": data.get("author", "สมาชิก"),
            "content": data.get("content", ""),
            "created_at": created.isoformat() if hasattr(created, "isoformat") else None,
            "has_image": bool(data.get("has_image"))}


async def database_call(function):
    try:
        return await asyncio.wait_for(asyncio.to_thread(function), timeout=5)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, "Database unavailable; refresh before retrying") from None


@router.get("/posts")
async def list_posts(limit: int = Query(default=20, ge=1, le=50),
                     after: str | None = Query(default=None, max_length=64, pattern=r"^[a-f0-9]{64}$")):
    def read():
        posts = collection()
        query = posts.order_by("created_at", direction=firestore.Query.DESCENDING).select(
            ["author", "content", "created_at", "has_image"])
        if after:
            cursor = posts.document(after).get(timeout=RPC_TIMEOUT, retry=None)
            if not cursor.exists:
                raise HTTPException(400, "Invalid cursor")
            query = query.start_after(cursor)
        docs = list(query.limit(limit + 1).stream(timeout=RPC_TIMEOUT, retry=None))
        return {"posts": [public_post(doc) for doc in docs[:limit]],
                "next_cursor": docs[limit - 1].id if len(docs) > limit else None}
    return await database_call(read)


@router.post("/posts")
@limiter.limit("5/minute")
async def create_post(request: Request, post: PostRequest, user: UserIdentity = Depends(require_user)):
    def write():
        try:
            image = normalize_post_image(post.image)
        except ValueError:
            raise HTTPException(422, "Invalid image; use a small JPEG, PNG or WebP") from None
        key = hashlib.sha256(f"{user.user_id}:{post.request_id}".encode()).hexdigest()
        ref = collection().document(key)
        data = {"author_id": user.user_id, "author": user.display_name,
                "content": post.content, "created_at": datetime.now(timezone.utc),
                "has_image": image is not None,
                "image_hash": hashlib.sha256(image).hexdigest() if image else None}
        if image:
            data["image"] = image
        try:
            ref.create(data, timeout=RPC_TIMEOUT, retry=None)
        except AlreadyExists:
            pass
        doc = ref.get(timeout=RPC_TIMEOUT, retry=None)
        if (not doc.exists or doc.to_dict().get("content") != post.content
                or doc.to_dict().get("image_hash") != data["image_hash"]):
            raise HTTPException(409, "Request already used; refresh before posting")
        return public_post(doc)
    return await database_call(write)


@router.get("/posts/{post_id}/image")
async def get_post_image(post_id: str = Path(pattern=r"^[a-f0-9]{64}$")):
    def read():
        doc = collection().document(post_id).get(field_paths=["image"], timeout=RPC_TIMEOUT, retry=None)
        image = doc.to_dict().get("image") if doc.exists else None
        if not isinstance(image, bytes):
            raise HTTPException(404, "Image not found")
        return Response(image, media_type="image/jpeg", headers={
            "Cache-Control": "public, max-age=86400, immutable",
            "X-Content-Type-Options": "nosniff",
        })
    return await database_call(read)
