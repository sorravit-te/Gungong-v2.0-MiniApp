"""Local-only credential-free renderer service, not the GunGong API application."""

import asyncio
import hmac
import json
import os
from pathlib import Path
from time import monotonic

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..core.performance_config import get_performance_config
from .url_renderer_service import BoundedPageRenderer
from .url_safety_service import URLSafetyError, normalize_public_url, validate_public_url

MAX_TRANSPORT_BYTES = 6 * 1024 * 1024
FORBIDDEN_ENV = (
    "GOOGLE_API_KEY", "VIRUSTOTAL_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS",
    "GOOGLE_SERVICE_ACCOUNT_JSON", "LINE_CHANNEL_ACCESS_TOKEN", "LINE_CHANNEL_SECRET",
    "URL_REPUTATION_API_KEY", "FIRESTORE_PROJECT_ID", "FIRESTORE_DATABASE_ID",
)


def assert_worker_environment():
    """Fail closed if backend credentials/configuration are accidentally forwarded."""
    if any(os.environ.get(key) for key in FORBIDDEN_ENV):
        raise RuntimeError("Renderer refuses backend credentials")
    if any(Path(name).exists() for name in (".env", "secrets", "service-account.json")):
        raise RuntimeError("Renderer refuses backend secret files")
    if len(os.environ.get("URL_RENDER_WORKER_TOKEN", "")) < 32:
        raise RuntimeError("Renderer requires a dedicated local access token")


class RenderJob(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(min_length=1, max_length=8192)
    initial_html: str | None = Field(default=None, max_length=1048576)
    content_security_policy: str = Field(default="", max_length=16384)
    timeout: float = Field(default=4.0, gt=0, le=4.0)


async def _cancel_job(job):
    if not job.done():
        job.cancel()
    # Owned browser teardown has independent bounded operations. Do not cancel
    # it a second time merely because the HTTP caller has disconnected.
    try:
        await asyncio.wait_for(job, get_performance_config().URL_RENDER_CLEANUP_ALLOWANCE + 0.3)
    except (asyncio.CancelledError, Exception):
        pass


async def _run_job(renderer, payload, request):
    async def work():
        deadline = monotonic() + payload.timeout
        try:
            safe_url = await asyncio.wait_for(validate_public_url(payload.url), timeout=payload.timeout)
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise asyncio.TimeoutError
            return await renderer.render(
                safe_url, timeout=remaining, initial_html=payload.initial_html,
                content_security_policy=payload.content_security_policy,
            )
        except URLSafetyError as exc:
            return {"status": "unavailable" if exc.code == "dns_failed" else "blocked",
                    "complete": exc.code != "dns_failed", "reason": exc.code}
        except asyncio.TimeoutError:
            return {"status": "timeout", "complete": False, "reason": "worker_deadline"}

    job = asyncio.create_task(work())

    stop_monitor = asyncio.Event()

    async def disconnected():
        while not stop_monitor.is_set():
            if await request.is_disconnected():
                return
            try:
                await asyncio.wait_for(stop_monitor.wait(), timeout=0.05)
            except asyncio.TimeoutError:
                pass

    monitor = asyncio.create_task(disconnected())
    try:
        await asyncio.wait({job, monitor}, return_when=asyncio.FIRST_COMPLETED,
                           timeout=payload.timeout + get_performance_config().URL_RENDER_CLEANUP_ALLOWANCE + 0.3)
        if job.done():
            return await job
        await _cancel_job(job)
        return {"status": "timeout", "complete": False, "reason": "worker_cancelled_or_deadline"}
    finally:
        # is_disconnected uses an AnyIO cancellation scope. A raw cancel during
        # that call can be swallowed by the scope and leave an infinite monitor.
        # Stop cooperatively first and bound the shutdown independently.
        stop_monitor.set()
        try:
            await asyncio.wait_for(monitor, timeout=0.2)
        except (asyncio.CancelledError, Exception):
            pass
        if not job.done():
            await _cancel_job(job)


def create_app(renderer=None):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    engine = renderer or BoundedPageRenderer(max_concurrency=1)

    @app.get("/health")
    async def health():
        return {"status": "ok", "component": "renderer_worker"}

    @app.post("/render")
    async def render(request: Request):
        expected = os.environ.get("URL_RENDER_WORKER_TOKEN", "")
        if (len(expected) < 32 or request.headers.get("origin")
                or not hmac.compare_digest(request.headers.get("authorization", ""), "Bearer " + expected)):
            raise HTTPException(403, "Worker access denied")
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
            raise HTTPException(415, "JSON required")

        async def read_body():
            data = bytearray()
            async for chunk in request.stream():
                if len(data) + len(chunk) > MAX_TRANSPORT_BYTES:
                    raise HTTPException(413, "Worker request too large")
                data.extend(chunk)
            return data

        try:
            body = await asyncio.wait_for(read_body(), timeout=1.0)
            payload = RenderJob.model_validate_json(body)
            normalize_public_url(payload.url)
        except asyncio.TimeoutError:
            raise HTTPException(408, "Worker body deadline") from None
        except (ValidationError, ValueError, URLSafetyError):
            # Do not echo untrusted HTML or URLs in framework validation errors.
            raise HTTPException(422, "Invalid worker request") from None
        result = await _run_job(engine, payload, request)
        if len(json.dumps(result, ensure_ascii=False).encode("utf-8")) > MAX_TRANSPORT_BYTES:
            return {"status": "insufficient", "complete": False, "reason": "worker_response_limit"}
        return result

    return app


if __name__ == "__main__":
    assert_worker_environment()
    import uvicorn
    uvicorn.run(create_app(), host="0.0.0.0", port=8071, access_log=False,
                log_level="warning", limit_concurrency=4, backlog=8, timeout_keep_alive=2)
