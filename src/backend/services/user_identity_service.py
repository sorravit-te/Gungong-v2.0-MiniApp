"""Verified request identity; never trust browser-provided user IDs or names."""
import asyncio
import logging
from dataclasses import dataclass

import httpx
from fastapi import Header, HTTPException
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token

from ..core.config import settings

# LINE's token verification endpoint requires a query parameter. Do not let
# HTTPX's request logger disclose it; application stage logs remain available.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


@dataclass(frozen=True)
class UserIdentity:
    user_id: str
    display_name: str


async def verify_line_identity(token: str) -> UserIdentity:
    async with httpx.AsyncClient(timeout=3, follow_redirects=False, trust_env=False) as client:
        verified = await client.get("https://api.line.me/oauth2/v2.1/verify", params={"access_token": token})
        if verified.status_code >= 500 or verified.status_code == 429:
            raise HTTPException(503, "Identity provider unavailable")
        if verified.status_code != 200:
            raise HTTPException(401, "Invalid session")
        data = verified.json()
        if (data.get("client_id") != settings.line_login_channel_id
                or data.get("expires_in", 0) <= 0):
            raise HTTPException(401, "Invalid session audience or expiry")
        profile = await client.get("https://api.line.me/v2/profile", headers={"Authorization": f"Bearer {token}"})
        if profile.status_code >= 500 or profile.status_code == 429:
            raise HTTPException(503, "Identity provider unavailable")
        if profile.status_code != 200:
            raise HTTPException(401, "Invalid session")
        data = profile.json()
        if not isinstance(data.get("userId"), str) or not data["userId"]:
            raise HTTPException(401, "Invalid session")
        return UserIdentity(data["userId"], str(data.get("displayName") or "สมาชิก")[:80])


def verify_firebase_identity(token: str) -> UserIdentity:
    if not settings.firestore_project_id:
        raise HTTPException(503, "Identity provider not configured")

    def bounded_request(url, method="GET", body=None, headers=None, **_kwargs):
        return GoogleRequest()(url, method=method, body=body, headers=headers, timeout=3)

    data = id_token.verify_firebase_token(token, bounded_request, audience=settings.firestore_project_id)
    uid = data.get("sub")
    if not isinstance(uid, str) or not uid or len(uid) > 128:
        raise HTTPException(401, "Invalid session")
    return UserIdentity(uid, str(data.get("name") or "สมาชิก")[:80])


async def require_user(authorization: str = Header(default=""),
                       x_auth_provider: str = Header(default="")) -> UserIdentity:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token or len(token) > 8192:
        raise HTTPException(401, "Login required")
    try:
        if x_auth_provider == "line":
            return await asyncio.wait_for(verify_line_identity(token), timeout=6)
        if x_auth_provider == "firebase":
            return await asyncio.wait_for(asyncio.to_thread(verify_firebase_identity, token), timeout=6)
        raise HTTPException(401, "Unsupported session")
    except HTTPException:
        raise
    except (httpx.HTTPError, asyncio.TimeoutError):
        raise HTTPException(503, "Identity provider unavailable") from None
    except Exception:
        raise HTTPException(401, "Invalid session") from None
