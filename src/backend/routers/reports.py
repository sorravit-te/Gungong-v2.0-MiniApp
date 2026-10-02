"""Authenticated, append-only link/text tips; never promote tips to a blacklist."""
import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.routing import APIRoute
from google.api_core.exceptions import AlreadyExists
from pydantic import BaseModel, ConfigDict, Field, model_validator
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..services.database_service import get_database_service
from ..services.user_identity_service import UserIdentity, require_user

COLLECTION = "content_reports"


class BoundedReportRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def bounded(request: Request):
            if request.method == "POST":
                body = bytearray()
                async for chunk in request.stream():
                    if len(body) + len(chunk) > 32 * 1024:
                        raise HTTPException(413, "Report too large")
                    body.extend(chunk)
                request._body = bytes(body)
            return await handler(request)
        return bounded


def no_cache(response: Response):
    response.headers["Cache-Control"] = "private, no-store"


router = APIRouter(prefix="/api/reports", route_class=BoundedReportRoute,
                   dependencies=[Depends(no_cache)])
limiter = Limiter(key_func=get_remote_address)


class ReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    kind: Literal["link", "text"]
    content: str = Field(min_length=1, max_length=5000)
    reason: Literal["phishing", "scam", "spam", "other"]
    details: str = Field(default="", max_length=1000)
    request_id: UUID

    @model_validator(mode="after")
    def valid_link(self):
        if self.kind == "link":
            try:
                url = urlsplit(self.content)
                valid = (len(self.content) <= 2048 and url.scheme in {"http", "https"}
                         and bool(url.hostname) and not url.username and not url.password
                         and not any(char.isspace() or ord(char) < 32 for char in self.content))
                # Reject malformed ports too. Reported URLs are stored, never fetched.
                _ = url.port
            except ValueError:
                valid = False
            if not valid:
                raise ValueError("Use an HTTP(S) link without embedded credentials")
        return self


def save_report(report: ReportRequest, user: UserIdentity):
    service = get_database_service()
    if not service:
        raise HTTPException(503, "Reports unavailable")
    key = hashlib.sha256(f"{user.user_id}:{report.request_id}".encode()).hexdigest()
    reference = service.db.collection(COLLECTION).document(key)
    data = {"reporter_id": user.user_id, "kind": report.kind, "content": report.content,
            "reason": report.reason, "details": report.details, "status": "pending",
            "request_id": str(report.request_id), "created_at": datetime.now(timezone.utc)}
    try:
        reference.create(data, timeout=4, retry=None)
    except AlreadyExists:
        previous = reference.get(timeout=4, retry=None).to_dict() or {}
        if any(previous.get(field) != data[field] for field in
               ("reporter_id", "kind", "content", "reason", "details", "request_id")):
            raise HTTPException(409, "Request ID already used for a different report") from None
    return {"id": key, "status": "pending"}


@router.post("")
@limiter.limit("5/minute")
async def submit_report(request: Request, report: ReportRequest,
                        user: UserIdentity = Depends(require_user)):
    try:
        return await asyncio.wait_for(asyncio.to_thread(save_report, report, user), timeout=6)
    except HTTPException:
        raise
    except Exception:
        # A write might have completed before timeout; retrying the same ID is safe.
        raise HTTPException(503, "Receipt unavailable; retry with the same request ID") from None
