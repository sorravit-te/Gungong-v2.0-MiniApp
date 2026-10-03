"""Public bearer-link reads; authenticated owner-only create/revoke."""
import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..services.database_service import get_database_service
from ..services.user_identity_service import UserIdentity, require_user
from ..services import history_shares as service


HEADERS = {"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer",
           "X-Robots-Tag": "noindex, nofollow", "X-Content-Type-Options": "nosniff"}


class ShareRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def bounded(request: Request):
            try:
                if request.method == "POST":
                    body = bytearray()
                    async for chunk in request.stream():
                        if len(body) + len(chunk) > 32 * 1024:
                            raise HTTPException(413, "Share request too large")
                        body.extend(chunk)
                    request._body = bytes(body)
                response = await handler(request)
                response.headers.update(HEADERS)
                return response
            except RequestValidationError:
                # Validation responses must not echo bearer links/input bodies.
                raise HTTPException(422, "Invalid share request", headers=HEADERS) from None
            except HTTPException as error:
                error.headers = {**(error.headers or {}), **HEADERS}
                raise
        return bounded


router = APIRouter(prefix="/api/history-shares", route_class=ShareRoute)
limiter = Limiter(key_func=get_remote_address)


class ShareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entry_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")]
    token: Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{43}$")]
    include_content: StrictBool = True
    consent: StrictBool  # Enforced on server, not just UI.


async def run(operation, *args):
    database = get_database_service()
    if not database:
        raise HTTPException(503, "Sharing unavailable")
    try:
        return await asyncio.wait_for(asyncio.to_thread(operation, database.db, *args), timeout=8)
    except HTTPException:
        raise
    except Exception:
        # Never return exception text, private data or a bearer token.
        raise HTTPException(503, "Sharing unavailable") from None


@router.post("")
@limiter.limit("10/minute")
async def create(request: Request, body: ShareRequest, user: UserIdentity = Depends(require_user)):
    if body.consent is not True:
        raise HTTPException(422, "Consent required")
    return await run(service.create_share, body.entry_id, body.token, body.include_content, user.user_id)


@router.get("/{token}")
@limiter.limit("60/minute")
async def detail(request: Request, token: str):
    if not service.TOKEN.fullmatch(token):
        raise HTTPException(404, "Share unavailable")
    return await run(service.read_share, token)


@router.post("/{token}/revoke")
@limiter.limit("10/minute")
async def revoke(request: Request, token: str, user: UserIdentity = Depends(require_user)):
    return await run(service.revoke_share, token, user.user_id)
