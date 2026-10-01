"""Bounded, anonymous SPA evidence. Chromium never fetches a URL directly.

All passive HTTP resources are fulfilled by a DNS-pinned public-address broker.
A deny-all local proxy covers browser traffic outside Playwright routing. This
is not CAPTCHA evasion, authentication, an interactive login, or a full crawl.
"""

from __future__ import annotations

import asyncio
import ipaddress
import os
import ssl
import zlib
from dataclasses import dataclass
from time import monotonic
from urllib.parse import urlsplit

import httpcore

from ..core.config import settings
from ..core.performance_config import get_performance_config
from .url_safety_service import URLSafetyError, is_public_address, normalize_public_url, resolve_hostname, validate_public_url


def browser_environment():
    """Minimal OS runtime environment; no worker/provider tokens in Chromium."""
    names = ("PATH", "HOME", "TMPDIR", "TMP", "TEMP", "SystemRoot", "WINDIR",
             "LANG", "LC_ALL", "LD_LIBRARY_PATH", "PLAYWRIGHT_BROWSERS_PATH")
    return {name: os.environ[name] for name in names if name in os.environ}


class PublicNetworkBackend(httpcore.AsyncNetworkBackend):
    """Resolve once, reject ALL non-public answers, connect to a validated IP.

    httpcore still uses the original URL hostname for TLS SNI/certificate checks.
    No second hostname resolution occurs at connection time.
    """

    def __init__(self, resolver=resolve_hostname, backend=None):
        self.resolver = resolver
        self.backend = backend or httpcore.AnyIOBackend()

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        async def connect():
            addresses = list(await self.resolver(host, port))
            if not addresses:
                raise URLSafetyError("dns_failed", "No resolved addresses")
            if any(not is_public_address(ip) for ip in addresses):
                raise URLSafetyError("non_public_address", "Non-public network target")
            return await self.backend.connect_tcp(
                addresses[0], port, timeout=timeout, local_address=local_address,
                socket_options=socket_options,
            )
        return await asyncio.wait_for(connect(), timeout=timeout)

    async def connect_unix_socket(self, *args, **kwargs):
        raise URLSafetyError("unsupported_transport", "Unix sockets are prohibited")

    async def sleep(self, seconds):
        await asyncio.sleep(seconds)


@dataclass(frozen=True)
class ResourceResponse:
    status: int
    headers: dict[str, str]
    body: bytes


class PublicResourceBroker:
    def __init__(self):
        self.pool = httpcore.AsyncConnectionPool(
            ssl_context=ssl.create_default_context(), network_backend=PublicNetworkBackend(),
            max_connections=6, max_keepalive_connections=6, retries=0,
        )

    async def fetch(self, raw_url, timeout, max_bytes):
        url = normalize_public_url(raw_url)
        if max_bytes <= 0:
            raise ValueError("Resource byte limit exceeded")
        # Never forward a user's/browser's cookies, credentials or headers.
        async with self.pool.stream("GET", url, headers={
            "User-Agent": settings.url_fetch_user_agent,
            "Accept-Encoding": "identity", "Accept": "*/*",
        }, extensions={"timeout": {key: timeout for key in ("connect", "read", "write", "pool")}}) as response:
            headers = {k.decode("latin1").lower(): v.decode("latin1") for k, v in response.headers}
            encoding = headers.get("content-encoding", "identity").strip().lower()
            # Some servers compress despite Accept-Encoding: identity. Bound
            # BOTH wire and decoded bytes; never use unbounded gzip.decompress.
            if encoding not in {"identity", "", "gzip", "deflate"}:
                raise ValueError("Unsupported resource content encoding")
            decoder = zlib.decompressobj(16 + zlib.MAX_WBITS if encoding == "gzip" else zlib.MAX_WBITS) if encoding in {"gzip", "deflate"} else None
            body = bytearray()
            wire_bytes = 0
            async for chunk in response.aiter_stream():
                wire_bytes += len(chunk)
                if wire_bytes > max_bytes:
                    raise ValueError("Resource byte limit exceeded")
                decoded = decoder.decompress(chunk, max_bytes - len(body) + 1) if decoder else chunk
                if len(body) + len(decoded) > max_bytes:
                    raise ValueError("Decoded resource byte limit exceeded")
                body.extend(decoded)
            if decoder and (not decoder.eof or decoder.unused_data or decoder.unconsumed_tail):
                # Reject truncated/concatenated/trailing encoded streams rather
                # than treating a partial script/document as completed evidence.
                raise ValueError("Incomplete or unsupported encoded resource")
            return ResourceResponse(response.status, headers, bytes(body))

    async def close(self):
        await self.pool.aclose()


class BoundedPageRenderer:
    """Fresh browser per job; bounded concurrency, no queue or persistent session."""

    def __init__(self, *, fetcher=None, browser_factory=None, max_concurrency=2):
        self.fetcher = fetcher
        self.browser_factory = browser_factory
        self._slots = asyncio.Semaphore(max_concurrency)

    async def render(self, url, *, timeout=None, initial_html=None, content_security_policy="", deadline_managed=False):
        config = get_performance_config()
        if not settings.url_render_enabled:
            return {"status": "unavailable", "complete": False, "reason": "renderer_disabled"}
        if self._slots.locked():
            return {"status": "unavailable", "complete": False, "reason": "renderer_busy"}
        async with self._slots:
            try:
                work = self._render(url, initial_html=initial_html, content_security_policy=content_security_policy)
                # The verifier already owns the stage deadline and reserves
                # cleanup. Two coincident timers can cancel teardown twice.
                return await work if deadline_managed else await asyncio.wait_for(work, timeout=timeout or config.URL_RENDER_TIMEOUT)
            except asyncio.TimeoutError:
                return {"status": "timeout", "complete": False, "reason": "render_deadline"}
            except URLSafetyError as exc:
                return {"status": "blocked", "complete": True, "reason": exc.code}
            except Exception as exc:
                # No URL, browser error body or sensitive query in diagnostics.
                reason = "renderer_sandbox_unavailable" if "No usable sandbox" in str(exc) else (
                    "renderer_cleanup_timeout" if str(exc) == "renderer_cleanup_timeout" else "renderer_failed"
                )
                return {"status": "unavailable", "complete": False, "reason": reason}

    async def _render(self, url, *, initial_html=None, content_security_policy=""):
        from playwright.async_api import async_playwright

        config = get_performance_config()
        started = monotonic()
        deadline = started + config.URL_RENDER_TIMEOUT
        broker = PublicResourceBroker() if self.fetcher is None else None
        fetch = self.fetcher or broker.fetch
        browser = None
        playwright = None
        proxy = None
        connections = set()
        tasks = set()
        critical_tasks = set()
        blocked = []
        failures = []
        failure_kinds = []
        optional_failures = 0
        chain = []
        request_count = 0
        downloaded = 0
        main_status = 0

        async def deny_proxy(reader, writer):
            # Deliberately do not read, resolve, connect or relay anything.
            connections.add(writer)
            writer.close()
            await writer.wait_closed()
            connections.discard(writer)

        async def route_request(route, request):
            nonlocal request_count, downloaded, main_status, optional_failures
            task = asyncio.current_task()
            tasks.add(task)
            # Passive public-page assessment is not verification of every
            # third-party analytics/auth backend. Main documents, executable
            # scripts, styles and same-origin data remain required. Missing
            # optional data can NEVER substitute for positive readable text.
            same_origin = urlsplit(request.url).netloc == urlsplit(url).netloc
            essential = (request.resource_type in {"document", "script", "stylesheet"}
                         or (same_origin and request.resource_type in {"xhr", "fetch"}))
            if essential:
                critical_tasks.add(task)
            try:
                parsed = urlsplit(normalize_public_url(request.url))
                # Literal private targets are rejected even with a mocked fetcher.
                try:
                    literal = ipaddress.ip_address(parsed.hostname)
                    if not is_public_address(str(literal)):
                        raise URLSafetyError("non_public_address", "Non-public resource")
                except ValueError as exc:
                    if isinstance(exc, URLSafetyError):
                        raise
                is_main = request.is_navigation_request() and request.frame == request.frame.page.main_frame
                if is_main:
                    normalized = normalize_public_url(request.url)
                    if normalized in chain or len(chain) > config.MAX_REDIRECTS:
                        raise URLSafetyError("render_redirect_violation", "Render redirect limit/loop")
                    chain.append(normalized)
                if request.method != "GET":
                    if essential:
                        failures.append("non_passive_request")
                        failure_kinds.append(f"{request.resource_type}:non_passive")
                    else:
                        optional_failures += 1
                    await route.abort()
                    return
                if request.resource_type in {"image", "media", "font"}:
                    await route.abort()
                    return
                request_count += 1
                if request_count > config.URL_RENDER_MAX_REQUESTS:
                    raise ValueError("Resource count exceeded")
                if is_main and request.url == url and initial_html is not None:
                    # Reuse the completed lightweight response, not a second
                    # fetch with possibly different content. DNS still checked.
                    await asyncio.wait_for(validate_public_url(url), timeout=max(0.001, deadline - monotonic()))
                    seed_headers = {"content-type": "text/html; charset=utf-8"}
                    if content_security_policy:
                        seed_headers["content-security-policy"] = content_security_policy
                    response = ResourceResponse(200, seed_headers, initial_html.encode("utf-8"))
                else:
                    response = await asyncio.wait_for(fetch(
                        request.url, max(0.001, deadline - monotonic()),
                        min(config.URL_RENDER_RESOURCE_BYTES, config.URL_RENDER_TOTAL_BYTES - downloaded),
                    ), timeout=max(0.001, deadline - monotonic()))
                downloaded += len(response.body)
                if downloaded > config.URL_RENDER_TOTAL_BYTES:
                    raise ValueError("Combined byte limit exceeded")
                if is_main:
                    main_status = response.status
                if essential and response.status >= 400:
                    failures.append("resource_http_error")
                    failure_kinds.append(f"{request.resource_type}:http_{response.status}")
                elif response.status >= 400:
                    optional_failures += 1
                # No cookies, authentication, compressed/chunked length mismatch,
                # downloads or response credentials survive into the context.
                headers = {k: v for k, v in response.headers.items() if k in {
                    "content-type", "location", "access-control-allow-origin", "content-security-policy",
                }}
                await route.fulfill(status=response.status, headers=headers, body=response.body)
            except URLSafetyError as exc:
                if exc.code == "dns_failed":
                    if essential:
                        failures.append("resource_dns_failed")
                        failure_kinds.append(f"{request.resource_type}:dns_failed")
                else:
                    blocked.append(exc.code)
                await route.abort()
            except Exception:
                if essential:
                    failures.append("resource_unavailable")
                    failure_kinds.append(f"{request.resource_type}:unavailable")
                await route.abort()
            finally:
                tasks.discard(task)
                critical_tasks.discard(task)

        try:
            normalize_public_url(url)
            proxy = await asyncio.start_server(deny_proxy, "127.0.0.1", 0)
            proxy_port = proxy.sockets[0].getsockname()[1]
            playwright = await async_playwright().start()
            launch = self.browser_factory or playwright.chromium.launch
            browser = await launch(
                headless=True, channel=settings.url_render_browser_channel,
                env=browser_environment(),
                chromium_sandbox=True,
                proxy={"server": f"http://127.0.0.1:{proxy_port}"},
                args=["--proxy-bypass-list=<-loopback>",
                      "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
                      "--force-webrtc-ip-handling-policy=disable_non_proxied_udp"],
            )
            context = await browser.new_context(
                service_workers="block", accept_downloads=False,
                user_agent=settings.url_fetch_user_agent,
            )
            await context.route("**/*", route_request)
            async def deny_websocket(socket):
                failures.append("non_passive_websocket")
                await socket.close()
            await context.route_web_socket("**/*", deny_websocket)
            page = await context.new_page()
            def close_popup(popup):
                if popup != page:
                    job = asyncio.create_task(popup.close())
                    tasks.add(job)
                    job.add_done_callback(tasks.discard)
            context.on("page", close_popup)
            try:
                await page.goto(url, wait_until="commit", timeout=config.URL_RENDER_TIMEOUT * 1000)
            except Exception:
                if not blocked and len(chain) <= 1:
                    raise
                if not blocked:
                    await page.wait_for_load_state("domcontentloaded", timeout=max(1, (deadline - monotonic()) * 1000))
            if blocked:
                return {"status": "blocked", "complete": True, "reason": blocked[0]}
            # Wait for positive rendered text and quiet resource/DOM activity,
            # not networkidle (analytics streams can run forever).
            previous = None
            stable_since = monotonic()
            while monotonic() < deadline:
                if blocked:
                    return {"status": "blocked", "complete": True, "reason": blocked[0]}
                try:
                    snapshot = await page.evaluate("""() => ({
                        text: (document.body?.innerText || '').slice(0, 4096),
                        html: document.documentElement.outerHTML.slice(0, 1048577),
                        url: location.href
                    })""")
                except Exception:
                    # A verified JS navigation can destroy the old execution
                    # context. Re-read the new DOM within the same budget.
                    await asyncio.sleep(0.05)
                    continue
                signature = (snapshot["text"], snapshot["url"])
                if signature != previous or critical_tasks:
                    stable_since = monotonic()
                    previous = signature
                if len(snapshot["text"]) >= config.MIN_PAGE_VISIBLE_TEXT_CHARS and monotonic() - stable_since >= 0.35:
                    break
                await asyncio.sleep(0.05)
            if blocked:
                return {"status": "blocked", "complete": True, "reason": blocked[0]}
            final_url = normalize_public_url(snapshot["url"])
            if chain and final_url != chain[-1] and urlsplit(final_url).netloc == urlsplit(chain[-1]).netloc and urlsplit(final_url).scheme == urlsplit(chain[-1]).scheme:
                # hash routing / history.pushState cannot change origin and
                # performs no network connection. Retain the rendered location.
                chain.append(final_url)
            if not chain or final_url != chain[-1]:
                # An unmediated/scheme-changing navigation is not usable evidence.
                return {"status": "error", "complete": False, "reason": "unverified_render_navigation"}
            complete = not failures and not critical_tasks and 200 <= main_status < 300 and len(snapshot["html"]) <= 1048576
            return {
                "status": "clean" if complete else "insufficient", "complete": complete,
                "reason": "rendered_page" if complete else "render_resources_incomplete",
                "final_url": final_url, "redirect_chain": chain,
                "html": snapshot["html"], "visible_text": snapshot["text"],
                "http_status": main_status, "resource_count": request_count,
                "downloaded_bytes": downloaded, "resource_failures": len(failures),
                "resource_failure_kinds": list(set(failure_kinds)),
                "optional_resource_failures": optional_failures,
            }
        finally:
            # Cancellation propagates, but all intercepted resource work is
            # explicitly cancelled and awaited before closing the owned browser.
            pending = list(tasks)
            for task in pending:
                task.cancel()
            async def close_bounded(factory, budget):
                try:
                    await asyncio.wait_for(factory(), timeout=budget)
                    return True
                except Exception:
                    return False
            if pending:
                await close_bounded(lambda: asyncio.gather(*pending, return_exceptions=True), 0.1)
            if browser:
                await close_bounded(browser.close, 0.4)
            driver_closed = True
            if playwright:
                driver_closed = await close_bounded(playwright.stop, 1.0)
            if broker:
                await close_bounded(broker.close, 0.1)
            if proxy:
                proxy.close()
                await proxy.wait_closed()
            for writer in list(connections):
                writer.close()
            if pending:
                await close_bounded(lambda: asyncio.gather(*pending, return_exceptions=True), 0.1)
            if not driver_closed:
                raise RuntimeError("renderer_cleanup_timeout")


_renderer = None


def get_page_renderer():
    global _renderer
    if _renderer is None:
        _renderer = BoundedPageRenderer()
    return _renderer
