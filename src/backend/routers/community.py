"""Shared community feed, separate from each user's private scan history."""
import asyncio
import hashlib
import time
from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StringConstraints, field_validator, model_validator
from google.api_core.exceptions import AlreadyExists, FailedPrecondition, Conflict
from google.cloud import firestore
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..services.database_service import get_database_service
from ..services.user_identity_service import UserIdentity, require_user, safe_line_picture
from ..services.community_image_service import MAX_IMAGE_BASE64, normalize_post_image


class BoundedPostRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def bounded(request: Request):
            if request.method in {"POST", "PUT", "PATCH"}:
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
POST_ID_PATTERN = r"^[a-f0-9]{64}$"
PostId = Annotated[str, StringConstraints(pattern=POST_ID_PATTERN)]
PUBLIC_FIELDS = ["author", "author_picture_url", "content", "created_at", "updated_at", "has_image", "image_hash",
                 "like_count", "comment_count", "revision", "deleted_at"]


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
    return post_data(doc.id, doc.to_dict())


def post_data(post_id, data):
    created = data.get("created_at")
    updated = data.get("updated_at")
    return {"id": post_id, "author": data.get("author", "สมาชิก"),
            "author_picture_url": safe_line_picture(data.get("author_picture_url")),
            "content": data.get("content", ""),
            "created_at": created.isoformat() if hasattr(created, "isoformat") else None,
            "updated_at": updated.isoformat() if hasattr(updated, "isoformat") else None,
            "has_image": bool(data.get("has_image")), "image_version": data.get("image_hash"),
            "like_count": max(0, data.get("like_count", 0)),
            "comment_count": max(0, data.get("comment_count", 0)),
            "revision": data.get("revision", 0)}


def require_post(doc):
    data = doc.to_dict()
    if not doc.exists or data.get("deleted_at"):
        raise HTTPException(404, "Post not found")
    return data


def member_key(user, request_id=""):
    return hashlib.sha256(f"{user.user_id}:{request_id}".encode()).hexdigest()


def mutate_post(post_id, change, owner=None):
    """Atomic CAS batch: parent precondition serializes counters and ownership.

    All writes to the parent/child documents commit together. A concurrent edit,
    reaction or deletion changes the parent's update_time, so stale writes cannot
    commit. Re-read on contention within a real, bounded RPC budget.
    """
    service = get_database_service()
    if not service:
        raise HTTPException(503, "Database unavailable")
    ref = service.db.collection(COLLECTION).document(post_id)
    deadline = time.monotonic() + 4.5

    def remaining():
        budget = deadline - time.monotonic()
        if budget <= 0:
            raise HTTPException(503, "Database unavailable; refresh before retrying")
        return min(RPC_TIMEOUT, budget)

    for _ in range(3):
        doc = ref.get(timeout=remaining(), retry=None)
        data = require_post(doc)
        if owner and data.get("author_id") != owner.user_id:
            raise HTTPException(403, "Only the author can change this post")
        batch = service.db.batch()
        updates, result = change(batch, ref, data, remaining)
        if not updates:
            return result
        batch.update(ref, updates, option=service.db.write_option(last_update_time=doc.update_time))
        try:
            batch.commit(timeout=remaining(), retry=None)
            return result
        except (FailedPrecondition, Conflict, AlreadyExists):
            continue
    raise HTTPException(409, "Post changed; refresh before retrying")


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
        query = posts.order_by("created_at", direction=firestore.Query.DESCENDING).select(PUBLIC_FIELDS)
        if after:
            cursor = posts.document(after).get(timeout=RPC_TIMEOUT, retry=None)
            if not cursor.exists or cursor.to_dict().get("deleted_at"):
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
                "author_picture_url": safe_line_picture(user.picture_url),
                "content": post.content, "created_at": datetime.now(timezone.utc),
                "has_image": image is not None,
                "image_hash": hashlib.sha256(image).hexdigest() if image else None,
                "like_count": 0, "comment_count": 0, "revision": 0}
        if image:
            data["image"] = image
        try:
            ref.create(data, timeout=RPC_TIMEOUT, retry=None)
        except AlreadyExists:
            pass
        doc = ref.get(timeout=RPC_TIMEOUT, retry=None)
        if (not doc.exists or doc.to_dict().get("deleted_at") or doc.to_dict().get("content") != post.content
                or doc.to_dict().get("image_hash") != data["image_hash"]):
            raise HTTPException(409, "Request already used; refresh before posting")
        return public_post(doc)
    return await database_call(write)


@router.get("/posts/{post_id}/image")
async def get_post_image(post_id: str = Path(pattern=r"^[a-f0-9]{64}$")):
    def read():
        doc = collection().document(post_id).get(field_paths=["image", "deleted_at"], timeout=RPC_TIMEOUT, retry=None)
        data = require_post(doc)
        image = data.get("image")
        if not isinstance(image, bytes):
            raise HTTPException(404, "Image not found")
        return Response(image, media_type="image/jpeg", headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        })
    return await database_call(read)


class ViewerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    post_ids: list[PostId] = Field(min_length=1, max_length=50)


@router.post("/posts/viewer-state")
@limiter.limit("30/minute")
async def viewer_state(request: Request, body: ViewerRequest, user: UserIdentity = Depends(require_user)):
    def read():
        service = get_database_service()
        if not service:
            raise HTTPException(503, "Database unavailable")
        posts = service.db.collection(COLLECTION)
        refs = []
        for key in dict.fromkeys(body.post_ids):
            ref = posts.document(key)
            refs.extend([ref, ref.collection("likes").document(member_key(user))])
        docs = {doc.reference.path: doc for doc in service.db.get_all(refs,
            field_paths=["author_id", "deleted_at"], timeout=RPC_TIMEOUT, retry=None)}
        result = {}
        for key in dict.fromkeys(body.post_ids):
            ref = posts.document(key)
            doc = docs.get(ref.path)
            if not doc or not doc.exists or doc.to_dict().get("deleted_at"):
                continue
            like = docs.get(ref.collection("likes").document(member_key(user)).path)
            result[key] = {"can_edit": doc.to_dict().get("author_id") == user.user_id,
                           "liked": bool(like and like.exists)}
        return {"states": result}
    return await database_call(read)


@router.get("/posts/{post_id}")
async def get_post(post_id: str = Path(pattern=POST_ID_PATTERN)):
    def read():
        doc = collection().document(post_id).get(field_paths=PUBLIC_FIELDS, timeout=RPC_TIMEOUT, retry=None)
        require_post(doc)
        return public_post(doc)
    return await database_call(read)


class LikeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    liked: StrictBool


@router.put("/posts/{post_id}/like")
@limiter.limit("30/minute")
async def like_post(request: Request, body: LikeRequest, post_id: str = Path(pattern=POST_ID_PATTERN),
                    user: UserIdentity = Depends(require_user)):
    def change(batch, ref, data, remaining):
        like = ref.collection("likes").document(member_key(user))
        exists = like.get(timeout=remaining(), retry=None).exists
        count = max(0, data.get("like_count", 0))
        if exists == body.liked:
            return {}, {"liked": body.liked, "like_count": count}
        count = max(0, count + (1 if body.liked else -1))
        if body.liked:
            batch.set(like, {"created_at": datetime.now(timezone.utc)})
        else:
            batch.delete(like)
        return {"like_count": count}, {"liked": body.liked, "like_count": count}
    return await database_call(lambda: mutate_post(post_id, change))


class CommentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(min_length=1, max_length=1000)
    request_id: UUID

    @field_validator("content")
    @classmethod
    def trim(cls, value):
        if not value.strip():
            raise ValueError("Empty comment")
        return value.strip()


def public_comment(doc):
    data = doc.to_dict()
    created = data.get("created_at")
    return {"id": doc.id, "author": data.get("author", "สมาชิก"), "content": data.get("content", ""),
            "author_picture_url": safe_line_picture(data.get("author_picture_url")),
            "created_at": created.isoformat() if hasattr(created, "isoformat") else None}


@router.get("/posts/{post_id}/comments")
async def list_comments(post_id: str = Path(pattern=POST_ID_PATTERN),
                        limit: int = Query(default=20, ge=1, le=50),
                        after: str | None = Query(default=None, max_length=64, pattern=POST_ID_PATTERN)):
    def read():
        ref = collection().document(post_id)
        require_post(ref.get(field_paths=["deleted_at"], timeout=RPC_TIMEOUT, retry=None))
        comments = ref.collection("comments")
        query = comments.order_by("created_at").select(["author", "author_picture_url", "content", "created_at"])
        if after:
            doc = comments.document(after).get(timeout=RPC_TIMEOUT, retry=None)
            if not doc.exists:
                raise HTTPException(400, "Invalid cursor")
            query = query.start_after(doc)
        docs = list(query.limit(limit + 1).stream(timeout=RPC_TIMEOUT, retry=None))
        return {"comments": [public_comment(doc) for doc in docs[:limit]],
                "next_cursor": docs[limit - 1].id if len(docs) > limit else None}
    return await database_call(read)


@router.post("/posts/{post_id}/comments")
@limiter.limit("10/minute")
async def comment_post(request: Request, body: CommentRequest, post_id: str = Path(pattern=POST_ID_PATTERN),
                       user: UserIdentity = Depends(require_user)):
    def change(batch, ref, data, remaining):
        comment = ref.collection("comments").document(member_key(user, str(body.request_id)))
        existing = comment.get(timeout=remaining(), retry=None)
        if existing.exists:
            if existing.to_dict().get("content") != body.content:
                raise HTTPException(409, "Request already used")
            return {}, {"comment": public_comment(existing), "comment_count": data.get("comment_count", 0)}
        created = datetime.now(timezone.utc)
        batch.create(comment, {"author_id": user.user_id, "author": user.display_name,
                               "author_picture_url": safe_line_picture(user.picture_url),
                               "content": body.content, "created_at": created})
        count = data.get("comment_count", 0) + 1
        return {"comment_count": count}, {"comment": {"id": comment.id, "author": user.display_name,
            "author_picture_url": safe_line_picture(user.picture_url),
            "content": body.content, "created_at": created.isoformat()}, "comment_count": count}
    return await database_call(lambda: mutate_post(post_id, change))


class EditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(max_length=2000)
    expected_revision: int = Field(ge=0)
    image: str | None = Field(default=None, max_length=MAX_IMAGE_BASE64)
    remove_image: StrictBool = False

    @model_validator(mode="after")
    def normalize(self):
        self.content = self.content.strip()
        if self.image and self.remove_image:
            raise ValueError("Cannot replace and remove the image together")
        return self


@router.patch("/posts/{post_id}")
@limiter.limit("5/minute")
async def edit_post(request: Request, body: EditRequest, post_id: str = Path(pattern=POST_ID_PATTERN),
                    user: UserIdentity = Depends(require_user)):
    def write():
        try:
            image = normalize_post_image(body.image)
        except ValueError:
            raise HTTPException(422, "Invalid image") from None

        def change(batch, ref, data, remaining):
            if data.get("revision", 0) != body.expected_revision:
                raise HTTPException(409, "Post changed; reopen before editing")
            has_image = image is not None or (data.get("has_image", False) and not body.remove_image)
            if not body.content and not has_image:
                raise HTTPException(422, "Empty post")
            updates = {"content": body.content, "has_image": has_image,
                       "author_picture_url": safe_line_picture(user.picture_url),
                       "revision": body.expected_revision + 1, "updated_at": datetime.now(timezone.utc)}
            if image:
                updates.update(image=image, image_hash=hashlib.sha256(image).hexdigest())
            elif body.remove_image:
                updates.update(image=firestore.DELETE_FIELD, image_hash=None)
            return updates, post_data(ref.id, {**data, **updates})
        return mutate_post(post_id, change, owner=user)
    return await database_call(write)


@router.delete("/posts/{post_id}")
@limiter.limit("5/minute")
async def delete_post(request: Request, post_id: str = Path(pattern=POST_ID_PATTERN),
                      user: UserIdentity = Depends(require_user)):
    def change(batch, ref, data, remaining):
        # Tombstone keeps request IDs from resurrecting deleted posts. Removing
        # created_at excludes it from the ordered public feed without a new index.
        return {"deleted_at": datetime.now(timezone.utc), "created_at": firestore.DELETE_FIELD,
                "content": "", "image": firestore.DELETE_FIELD, "image_hash": None, "has_image": False}, {"deleted": True}
    return await database_call(lambda: mutate_post(post_id, change, owner=user))


class ReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Literal["scam", "phishing", "risky", "other"]
    details: str = Field(default="", max_length=500)


@router.put("/posts/{post_id}/report")
@limiter.limit("5/minute")
async def report_post(request: Request, body: ReportRequest, post_id: str = Path(pattern=POST_ID_PATTERN),
                      user: UserIdentity = Depends(require_user)):
    def change(batch, ref, data, remaining):
        now = datetime.now(timezone.utc)
        report = ref.collection("reports").document(member_key(user))
        batch.set(report, {"reporter_id": user.user_id, "reason": body.reason,
                           "details": body.details.strip(), "status": "pending", "updated_at": now})
        return {"last_report_at": now}, {"reported": True, "status": "pending"}
    return await database_call(lambda: mutate_post(post_id, change))
