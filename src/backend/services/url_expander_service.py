"""URL Expander Service - Resolves shortened URLs to their final destinations."""

import requests
from typing import Optional, Dict, List
from dataclasses import dataclass
from urllib.parse import urlparse
import time


@dataclass
class URLExpandResult:
    """Result from URL expansion."""

    original_url: str
    final_url: str
    redirect_chain: List[str]
    is_shortened: bool
    error: Optional[str] = None


class URLExpanderService:
    """
    Service for expanding shortened URLs (bit.ly, tinyurl, etc.) to their final destinations.

    This helps avoid false positives when checking URLs - legitimate organizations often
    use URL shorteners, so we need to check the actual destination URL.
    """

    # Common URL shortener domains
    SHORTENER_DOMAINS = {
        'bit.ly', 'goo.gl', 'tinyurl.com', 't.co', 'ow.ly',
        'is.gd', 'buff.ly', 'adf.ly', 'bl.ink', 'lnkd.in',
        'shorte.st', 'cutt.ly', 'rb.gy', 'shorturl.at',
        'clk.sh', 'short.io', 'tiny.cc', 'cli.re'
    }

    # Safety limits
    MAX_REDIRECTS = 10  # Prevent infinite redirect loops
    TIMEOUT = 5  # Timeout in seconds

    def __init__(self):
        """Initialize URL expander service."""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                         '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

        # Simple in-memory cache (URL -> result)
        self._cache: Dict[str, URLExpandResult] = {}
        self._cache_max_size = 1000
        self._cache_timestamps: Dict[str, float] = {}
        self._cache_ttl = 3600  # 1 hour TTL

    def is_shortened_url(self, url: str) -> bool:
        """
        Check if URL is from a known URL shortener.

        Args:
            url: URL to check

        Returns:
            True if URL is from a known shortener
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # Remove www. prefix
            if domain.startswith('www.'):
                domain = domain[4:]

            return domain in self.SHORTENER_DOMAINS
        except Exception:
            return False

    def _clean_cache(self):
        """Remove expired entries from cache."""
        current_time = time.time()
        expired_keys = [
            key for key, timestamp in self._cache_timestamps.items()
            if current_time - timestamp > self._cache_ttl
        ]

        for key in expired_keys:
            self._cache.pop(key, None)
            self._cache_timestamps.pop(key, None)

        # If still too large, remove oldest entries
        if len(self._cache) > self._cache_max_size:
            sorted_keys = sorted(
                self._cache_timestamps.items(),
                key=lambda x: x[1]
            )
            keys_to_remove = [k for k, _ in sorted_keys[:len(self._cache) - self._cache_max_size]]

            for key in keys_to_remove:
                self._cache.pop(key, None)
                self._cache_timestamps.pop(key, None)

    def expand_url(self, url: str, use_cache: bool = True) -> URLExpandResult:
        """
        Expand a shortened URL to its final destination.

        Args:
            url: URL to expand (can be shortened or regular)
            use_cache: Whether to use cached results

        Returns:
            URLExpandResult with expansion details
        """
        # Check cache first
        if use_cache and url in self._cache:
            cached_time = self._cache_timestamps.get(url, 0)
            if time.time() - cached_time < self._cache_ttl:
                return self._cache[url]

        # Clean cache periodically
        if len(self._cache) > self._cache_max_size:
            self._clean_cache()

        # Check if URL is from a shortener
        is_shortened = self.is_shortened_url(url)

        # If not a shortened URL, return as-is
        if not is_shortened:
            result = URLExpandResult(
                original_url=url,
                final_url=url,
                redirect_chain=[url],
                is_shortened=False
            )
            self._cache[url] = result
            self._cache_timestamps[url] = time.time()
            return result

        # Expand the shortened URL
        try:
            redirect_chain = [url]
            current_url = url

            # Follow redirects manually to track the chain
            for i in range(self.MAX_REDIRECTS):
                try:
                    # Use HEAD request first (faster, doesn't download content)
                    response = self.session.head(
                        current_url,
                        allow_redirects=False,
                        timeout=self.TIMEOUT
                    )

                    # If HEAD fails (some servers block it), try GET with stream
                    if response.status_code >= 400:
                        response = self.session.get(
                            current_url,
                            allow_redirects=False,
                            timeout=self.TIMEOUT,
                            stream=True
                        )
                        # Close stream immediately (we only need headers)
                        response.close()

                    # Check if there's a redirect
                    if response.status_code in (301, 302, 303, 307, 308):
                        next_url = response.headers.get('Location')

                        if not next_url:
                            break

                        # Handle relative URLs
                        if not next_url.startswith('http'):
                            from urllib.parse import urljoin
                            next_url = urljoin(current_url, next_url)

                        redirect_chain.append(next_url)
                        current_url = next_url
                    else:
                        # No more redirects
                        break

                except requests.RequestException:
                    # If request fails, try final fallback with allow_redirects=True
                    try:
                        response = self.session.get(
                            url,
                            allow_redirects=True,
                            timeout=self.TIMEOUT,
                            stream=True
                        )
                        current_url = response.url
                        response.close()
                        redirect_chain.append(current_url)
                    except Exception:
                        pass
                    break

            final_url = redirect_chain[-1]

            result = URLExpandResult(
                original_url=url,
                final_url=final_url,
                redirect_chain=redirect_chain,
                is_shortened=True
            )

            # Cache the result
            self._cache[url] = result
            self._cache_timestamps[url] = time.time()

            return result

        except Exception as e:
            result = URLExpandResult(
                original_url=url,
                final_url=url,
                redirect_chain=[url],
                is_shortened=is_shortened,
                error=str(e)
            )

            # Cache errors too (to avoid repeated failures)
            self._cache[url] = result
            self._cache_timestamps[url] = time.time()

            return result

    def expand_multiple(self, urls: List[str]) -> Dict[str, URLExpandResult]:
        """
        Expand multiple URLs.

        Args:
            urls: List of URLs to expand

        Returns:
            Dict mapping original URL to expansion result
        """
        results = {}

        for url in urls:
            results[url] = self.expand_url(url)

        return results


# Singleton instance
_expander_service = None


def get_url_expander_service() -> URLExpanderService:
    """
    Get URL expander service instance (singleton).

    Returns:
        URLExpanderService instance
    """
    global _expander_service

    if _expander_service is None:
        _expander_service = URLExpanderService()

    return _expander_service
