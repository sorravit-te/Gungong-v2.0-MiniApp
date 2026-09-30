"""Normalize public URLs and resolve redirects within an SSRF-safe boundary."""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Awaitable, Callable, Iterable, Mapping, Optional
from urllib.parse import SplitResult, urljoin, urlsplit, urlunsplit

import httpx

from ..core.performance_config import get_performance_config


REDIRECT_STATUSES = {301, 302, 303, 307, 308}
META_REFRESH_PATTERN = re.compile(
    r"^\s*(?P<delay>\d+(?:\.\d+)?)\s*;\s*url\s*=\s*(?P<url>.+?)\s*$",
    re.IGNORECASE,
)
MAX_META_REFRESH_DELAY_SECONDS = 5.0


class URLSafetyError(ValueError):
    """Raised when a URL is malformed, unsupported, or targets a non-public host."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class RedirectResolutionError(RuntimeError):
    """Raised when bounded redirect resolution cannot complete safely."""

    def __init__(self, code: str, message: str, chain: Optional[list[str]] = None):
        super().__init__(message)
        self.code = code
        self.chain = chain or []


@dataclass(frozen=True)
class RedirectHTTPResponse:
    status_code: int
    headers: Mapping[str, str]
    body_preview: bytes = b""
    body_truncated: bool = False


@dataclass(frozen=True)
class RedirectResolutionResult:
    original_url: str
    final_url: str
    redirect_chain: list[str]
    redirect_count: int
    content_type: str = ""
    content_preview: str = ""
    status_code: int = 0
    content_readable: bool = False
    content_truncated: bool = False
    redirect_kinds: tuple[str, ...] = ()
    client_redirect_checked: bool = False
    client_redirect_status: str = "not_checked"


Resolver = Callable[[str, int], Awaitable[Iterable[str]]]
Requester = Callable[[str, float], Awaitable[RedirectHTTPResponse]]


class _MetaRefreshParser(HTMLParser):
    """Collect meta refresh declarations without executing page content."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.refresh_values: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if tag.lower() != "meta":
            return
        values = {name.lower(): value for name, value in attrs if name}
        if (values.get("http-equiv") or "").strip().lower() == "refresh":
            self.refresh_values.append(values.get("content") or "")


def _extract_meta_refresh_target(html_preview: str) -> tuple[Optional[str], str]:
    """Return one conservative target plus an honest bounded-parser status."""
    parser = _MetaRefreshParser()
    try:
        parser.feed(html_preview)
        parser.close()
    except Exception:
        return None, "not_safely_parseable"
    if not parser.refresh_values:
        return None, "none_found"

    targets: list[str] = []
    for content in parser.refresh_values:
        match = META_REFRESH_PATTERN.fullmatch(content)
        if not match:
            return None, "not_safely_parseable"
        try:
            delay = float(match.group("delay"))
        except ValueError:
            return None, "not_safely_parseable"
        if delay > MAX_META_REFRESH_DELAY_SECONDS:
            return None, "delayed_refresh_not_followed"
        target = match.group("url").strip()
        if len(target) >= 2 and target[0] == target[-1] and target[0] in {"'", '"'}:
            target = target[1:-1].strip()
        if not target:
            return None, "not_safely_parseable"
        targets.append(target)

    if len(set(targets)) != 1:
        return None, "ambiguous"
    return targets[0], "found"


def normalize_public_url(raw_url: str) -> str:
    """Return a stable HTTP(S) URL without performing network I/O."""
    if not isinstance(raw_url, str) or not raw_url.strip():
        raise URLSafetyError("malformed", "URL is empty")

    candidate = raw_url.strip()
    try:
        parsed = urlsplit(candidate)
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise URLSafetyError("malformed", "URL could not be parsed") from exc

    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise URLSafetyError("unsupported_scheme", "Only HTTP and HTTPS URLs are supported")
    if not parsed.hostname:
        raise URLSafetyError("missing_hostname", "URL must contain a hostname")
    if parsed.username is not None or parsed.password is not None:
        raise URLSafetyError("userinfo_not_allowed", "Credentials in URLs are not supported")

    hostname = parsed.hostname.rstrip(".")
    if not hostname:
        raise URLSafetyError("missing_hostname", "URL must contain a hostname")

    try:
        ip_value = ipaddress.ip_address(hostname.split("%", 1)[0])
        normalized_host = f"[{ip_value.compressed}]" if ip_value.version == 6 else ip_value.compressed
    except ValueError:
        try:
            ascii_host = hostname.encode("idna").decode("ascii").lower()
        except UnicodeError as exc:
            raise URLSafetyError("malformed_hostname", "Hostname is not valid IDN text") from exc
        labels = ascii_host.split(".")
        if len(ascii_host) > 253 or any(
            not label
            or len(label) > 63
            or label.startswith("-")
            or label.endswith("-")
            or any(not (character.isascii() and (character.isalnum() or character == "-")) for character in label)
            for label in labels
        ):
            raise URLSafetyError("malformed_hostname", "Hostname is malformed")
        normalized_host = ascii_host

    if port is not None and not (1 <= port <= 65535):
        raise URLSafetyError("invalid_port", "URL port is invalid")

    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    netloc = normalized_host if port is None or default_port else f"{normalized_host}:{port}"
    path = parsed.path or "/"
    return urlunsplit(SplitResult(scheme, netloc, path, parsed.query, parsed.fragment))


def is_public_address(value: str) -> bool:
    """Use ipaddress semantics to allow only globally routable destinations."""
    try:
        address = ipaddress.ip_address(value.split("%", 1)[0])
    except ValueError:
        return False

    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    return bool(
        address.is_global
        and not address.is_multicast
        and not address.is_reserved
        and not address.is_unspecified
        and not address.is_loopback
        and not address.is_link_local
        and not address.is_private
    )


async def resolve_hostname(hostname: str, port: int) -> list[str]:
    """Resolve all A/AAAA addresses without blocking the event loop."""
    try:
        literal = ipaddress.ip_address(hostname.split("%", 1)[0])
        return [literal.compressed]
    except ValueError:
        pass

    loop = asyncio.get_running_loop()
    try:
        records = await loop.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise URLSafetyError("dns_failed", "Hostname could not be resolved") from exc
    return sorted({record[4][0].split("%", 1)[0] for record in records})


async def validate_public_url(url: str, resolver: Resolver = resolve_hostname) -> str:
    """Normalize a URL, resolve its hostname, and reject every non-public address."""
    normalized = normalize_public_url(url)
    parsed = urlsplit(normalized)
    hostname = parsed.hostname or ""
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    addresses = list(await resolver(hostname, port))
    if not addresses:
        raise URLSafetyError("dns_failed", "Hostname did not resolve")
    if any(not is_public_address(address) for address in addresses):
        raise URLSafetyError("non_public_target", "URL resolves to a non-public address")
    return normalized


class SafeRedirectResolver:
    """Resolve redirects manually, validating DNS before every outbound request."""

    def __init__(
        self,
        *,
        resolver: Resolver = resolve_hostname,
        requester: Optional[Requester] = None,
        max_redirects: Optional[int] = None,
        total_timeout: Optional[float] = None,
    ):
        config = get_performance_config()
        self.resolver = resolver
        self.requester = requester or self._request
        self.max_redirects = max_redirects if max_redirects is not None else config.MAX_REDIRECTS
        self.total_timeout = total_timeout if total_timeout is not None else config.URL_EXPANSION_TIMEOUT
        self.max_content_bytes = config.MAX_CONTENT_PREVIEW_BYTES

    async def _request(self, url: str, timeout: float) -> RedirectHTTPResponse:
        limits = httpx.Limits(max_connections=10, max_keepalive_connections=5)
        async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=httpx.Timeout(timeout),
            limits=limits,
            trust_env=False,
            headers={"User-Agent": "GunGong-URLVerifier/1.0"},
        ) as client:
            async with client.stream("GET", url) as response:
                preview = bytearray()
                truncated = False
                if response.status_code not in REDIRECT_STATUSES:
                    async for chunk in response.aiter_bytes():
                        remaining = self.max_content_bytes - len(preview)
                        if remaining <= 0:
                            truncated = True
                            break
                        preview.extend(chunk[:remaining])
                        if len(chunk) > remaining:
                            truncated = True
                            break
                return RedirectHTTPResponse(
                    response.status_code,
                    dict(response.headers),
                    bytes(preview),
                    truncated,
                )

    async def resolve(self, raw_url: str) -> RedirectResolutionResult:
        try:
            return await asyncio.wait_for(self._resolve(raw_url), timeout=self.total_timeout)
        except asyncio.TimeoutError as exc:
            raise RedirectResolutionError("timeout", "Redirect resolution timed out") from exc

    async def _resolve(self, raw_url: str) -> RedirectResolutionResult:
        original_url = await validate_public_url(raw_url, self.resolver)
        current_url = original_url
        chain = [original_url]
        seen = {original_url}
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.total_timeout
        redirect_kinds: list[str] = []

        for _ in range(self.max_redirects + 1):
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise RedirectResolutionError("timeout", "Redirect resolution timed out", chain)
            response = await self.requester(current_url, remaining)
            if response.status_code not in REDIRECT_STATUSES:
                content_type = response.headers.get("content-type", "")
                preview = ""
                content_readable = (
                    response.status_code < 400
                    and ("text" in content_type.lower() or "html" in content_type.lower() or not content_type)
                )
                if content_readable:
                    preview = response.body_preview.decode("utf-8", errors="replace")
                client_redirect_checked = bool(content_readable and (
                    "html" in content_type.lower()
                    or (not content_type and "<" in preview)
                ))
                client_redirect_status = "not_html"
                if client_redirect_checked:
                    meta_target, client_redirect_status = _extract_meta_refresh_target(preview)
                    if meta_target is not None:
                        if len(chain) - 1 >= self.max_redirects:
                            raise RedirectResolutionError("too_many_redirects", "Redirect limit exceeded", chain)
                        next_url = await validate_public_url(urljoin(current_url, meta_target), self.resolver)
                        if next_url in seen:
                            raise RedirectResolutionError("redirect_loop", "Redirect loop detected", chain + [next_url])
                        seen.add(next_url)
                        chain.append(next_url)
                        redirect_kinds.append("meta_refresh")
                        current_url = next_url
                        continue
                    if redirect_kinds and client_redirect_status == "none_found":
                        client_redirect_status = "followed"
                return RedirectResolutionResult(
                    original_url,
                    current_url,
                    chain,
                    len(chain) - 1,
                    content_type,
                    preview,
                    response.status_code,
                    content_readable,
                    response.body_truncated,
                    tuple(redirect_kinds),
                    client_redirect_checked,
                    client_redirect_status,
                )

            location = response.headers.get("location") or response.headers.get("Location")
            if not location:
                raise RedirectResolutionError("missing_location", "Redirect response had no Location", chain)
            if len(chain) - 1 >= self.max_redirects:
                raise RedirectResolutionError("too_many_redirects", "Redirect limit exceeded", chain)

            next_url = await validate_public_url(urljoin(current_url, location), self.resolver)
            if next_url in seen:
                raise RedirectResolutionError("redirect_loop", "Redirect loop detected", chain + [next_url])
            seen.add(next_url)
            chain.append(next_url)
            redirect_kinds.append("http")
            current_url = next_url

        raise RedirectResolutionError("too_many_redirects", "Redirect limit exceeded", chain)
