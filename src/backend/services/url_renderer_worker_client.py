"""Opt-in local worker transport. No Docker access or provider secrets in API calls."""

import asyncio
import json
from urllib.parse import urlsplit

import httpx

from ..core.config import settings
from ..core.performance_config import get_performance_config
from .url_safety_service import normalize_public_url

MAX_TRANSPORT_BYTES = 6 * 1024 * 1024


def worker_endpoint(base_url: str) -> str:
    """Only explicit local administrative configuration can select a worker."""
    parsed = urlsplit(base_url)
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1"}
            or parsed.username is not None or parsed.password is not None
            or parsed.port is None or not 1024 <= parsed.port <= 65535
            or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
        raise ValueError("Worker must be a numeric loopback HTTP endpoint")
    return base_url.rstrip("/") + "/render"


async def render_in_local_worker(url, *, initial_html=None, content_security_policy="", client_factory=None):
    if not settings.url_render_enabled:
        return {"status": "unavailable", "complete": False, "reason": "renderer_disabled"}
    token = settings.url_render_worker_token
    if not settings.url_render_worker_url or token is None or len(token.get_secret_value()) < 32:
        return {"status": "unavailable", "complete": False, "reason": "worker_not_configured"}
    config = get_performance_config()
    try:
        endpoint = worker_endpoint(settings.url_render_worker_url)
        payload = json.dumps({
            "url": normalize_public_url(url), "initial_html": initial_html,
            "content_security_policy": content_security_policy,
            "timeout": config.URL_RENDER_TIMEOUT,
        }, ensure_ascii=False).encode("utf-8")
        if len(payload) > MAX_TRANSPORT_BYTES:
            raise ValueError("Worker payload too large")

        async def request():
            factory = client_factory or (lambda: httpx.AsyncClient(
                trust_env=False, follow_redirects=False, timeout=config.URL_RENDER_TIMEOUT,
            ))
            async with factory() as client:
                async with client.stream("POST", endpoint, content=payload, headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + token.get_secret_value(),
                }) as response:
                    if response.status_code != 200:
                        return {"status": "unavailable", "complete": False, "reason": "worker_http_error"}
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(body) + len(chunk) > MAX_TRANSPORT_BYTES:
                            raise ValueError("Worker response too large")
                        body.extend(chunk)
            result = json.loads(body)
            if (not isinstance(result, dict) or result.get("status") not in {
                    "clean", "insufficient", "blocked", "error", "timeout", "unavailable"}
                    or not isinstance(result.get("complete"), bool)):
                raise ValueError("Malformed worker response")
            if result["status"] == "clean":
                chain = result.get("redirect_chain")
                if (result["complete"] is not True or not isinstance(result.get("html"), str)
                        or not isinstance(result.get("visible_text"), str)
                        or not isinstance(chain, list) or not chain
                        or len(chain) > config.MAX_REDIRECTS + 1
                        or chain[0] != normalize_public_url(url)
                        or result.get("final_url") != chain[-1]):
                    raise ValueError("Worker clean response lacks page evidence")
                for target in chain:
                    normalize_public_url(target)
            return {**result, "source": "isolated_local_worker"}

        return await asyncio.wait_for(request(), timeout=config.URL_RENDER_TIMEOUT)
    except (asyncio.TimeoutError, httpx.TimeoutException):
        return {"status": "timeout", "complete": False, "reason": "worker_deadline"}
    except Exception:
        # Never log response bodies, URLs, tokens or raw exceptions.
        return {"status": "unavailable", "complete": False, "reason": "worker_unavailable"}
