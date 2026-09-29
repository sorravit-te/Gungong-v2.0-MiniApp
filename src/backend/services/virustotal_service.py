"""VirusTotal API integration for URL/IP checking."""

import requests
import re
import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from ..core.config import settings
from .url_expander_service import get_url_expander_service

# Import gambling detector (optional)
try:
    from .gambling_detector_service import get_gambling_detector
    GAMBLING_DETECTOR_AVAILABLE = True
except ImportError:
    GAMBLING_DETECTOR_AVAILABLE = False


@dataclass
class VirusTotalResult:
    """Result from VirusTotal API check."""

    is_malicious: bool
    malicious_count: int
    total_scanners: int
    url: str
    positives_details: List[str]


class VirusTotalService:
    """Service for checking URLs and IPs with VirusTotal."""

    BASE_URL = "https://www.virustotal.com/api/v3"

    def __init__(self, api_key: Optional[str] = None, expand_urls: bool = True, check_gambling: bool = True):
        """Initialize VirusTotal service.

        Args:
            api_key: VirusTotal API key. If None, uses settings.
            expand_urls: Whether to expand shortened URLs before checking (default: True)
            check_gambling: Whether to also check for gambling websites (default: True)
        """
        self.api_key = api_key or settings.virustotal_api_key
        self.expand_urls = expand_urls
        self.check_gambling = check_gambling and GAMBLING_DETECTOR_AVAILABLE

        # Initialize URL expander
        self.url_expander = get_url_expander_service() if expand_urls else None

        # Initialize gambling detector
        self.gambling_detector = get_gambling_detector() if self.check_gambling else None

        if not self.api_key or self.api_key == "your_virustotal_api_key_here":
            raise ValueError(
                "VirusTotal API key not configured. "
                "Please set VIRUSTOTAL_API_KEY in .env file. "
                "Get your API key from: https://www.virustotal.com/gui/my-apikey"
            )

    def extract_urls(self, text: str) -> List[str]:
        """Extract URLs from text.

        Args:
            text: Text to extract URLs from

        Returns:
            List of URLs found in text
        """
        # URL pattern (simplified)
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'

        # Short URL patterns (bit.ly, etc.)
        short_url_pattern = r'(?:bit\.ly|goo\.gl|tinyurl\.com|t\.co|ow\.ly)/[a-zA-Z0-9]+'

        urls = re.findall(url_pattern, text)
        urls.extend(re.findall(short_url_pattern, text))

        return list(set(urls))  # Remove duplicates

    def check_url(self, url: str) -> VirusTotalResult:
        """Check a URL with VirusTotal API.

        Args:
            url: URL to check

        Returns:
            VirusTotalResult with scan results
        """
        # Expand shortened URLs first (if enabled)
        original_url = url
        if self.expand_urls and self.url_expander:
            expand_result = self.url_expander.expand_url(url)

            if expand_result.is_shortened and not expand_result.error:
                url = expand_result.final_url
                print(f"🔗 Expanded {original_url} → {url}")

        headers = {
            "accept": "application/json",
            "x-apikey": self.api_key
        }

        # URL encode the URL
        import base64
        url_id = base64.urlsafe_b64encode(url.encode()).decode().strip("=")

        # Check URL
        endpoint = f"{self.BASE_URL}/urls/{url_id}"

        try:
            response = requests.get(endpoint, headers=headers, timeout=10)

            if response.status_code == 404:
                # URL not in database, submit it for scanning
                return self._submit_url_for_scan(url)

            response.raise_for_status()
            data = response.json()

            # Parse results
            stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})

            malicious_count = stats.get("malicious", 0)
            suspicious_count = stats.get("suspicious", 0)
            total = sum(stats.values())

            # Get scanner details
            results = data.get("data", {}).get("attributes", {}).get("last_analysis_results", {})
            positives = [
                scanner for scanner, info in results.items()
                if info.get("category") in ["malicious", "suspicious"]
            ]

            return VirusTotalResult(
                is_malicious=(malicious_count + suspicious_count) > 0,
                malicious_count=malicious_count + suspicious_count,
                total_scanners=total,
                url=url,
                positives_details=positives[:5]  # Top 5 detections
            )

        except requests.RequestException as e:
            print(f"Error checking URL with VirusTotal: {e}")
            # Return safe result on error
            return VirusTotalResult(
                is_malicious=False,
                malicious_count=0,
                total_scanners=0,
                url=url,
                positives_details=[]
            )

    def _submit_url_for_scan(self, url: str) -> VirusTotalResult:
        """Submit URL for scanning if not in database.

        Args:
            url: URL to submit

        Returns:
            VirusTotalResult (will be pending)
        """
        headers = {
            "accept": "application/json",
            "x-apikey": self.api_key,
            "content-type": "application/x-www-form-urlencoded"
        }

        endpoint = f"{self.BASE_URL}/urls"
        data = {"url": url}

        try:
            response = requests.post(endpoint, headers=headers, data=data, timeout=10)
            response.raise_for_status()

            # URL submitted, return pending result
            return VirusTotalResult(
                is_malicious=False,
                malicious_count=0,
                total_scanners=0,
                url=url,
                positives_details=["Scan pending"]
            )

        except requests.RequestException:
            # Return safe result on error
            return VirusTotalResult(
                is_malicious=False,
                malicious_count=0,
                total_scanners=0,
                url=url,
                positives_details=[]
            )

    def check_text_for_malicious_urls(self, text: str) -> Dict:
        """Check text for malicious URLs.

        Args:
            text: Text to check

        Returns:
            Dict with check results
        """
        urls = self.extract_urls(text)

        if not urls:
            return {
                "has_urls": False,
                "urls_found": [],
                "malicious_urls": [],
                "is_dangerous": False
            }

        results = []
        malicious_urls = []
        gambling_urls = []

        # Use ThreadPoolExecutor for parallel URL checking (max 3 concurrent)
        with ThreadPoolExecutor(max_workers=3) as executor:
            # Submit all URL check tasks
            future_to_url = {executor.submit(self.check_url, url): url for url in urls}

            # Process results as they complete
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    result = future.result()

                    # Also check for gambling (if enabled)
                    gambling_result = None
                    if self.gambling_detector:
                        try:
                            # Content scraping with headless fallback (Optimized)
                            gambling_result = self.gambling_detector.check_url(url, scrape_content=True, use_headless_if_needed=True)
                            if gambling_result["is_gambling"]:
                                gambling_urls.append(url)
                                print(f"🎰 Gambling site detected: {url} (confidence: {gambling_result['confidence']:.0%})")
                        except Exception as e:
                            print(f"⚠️  Gambling check failed for {url}: {e}")

                    results.append({
                        "url": url,
                        "is_malicious": result.is_malicious,
                        "is_gambling": gambling_result["is_gambling"] if gambling_result else False,
                        "gambling_confidence": gambling_result["confidence"] if gambling_result else 0,
                        "gambling_keywords": gambling_result["keywords_found"] if gambling_result else [],
                        "detections": f"{result.malicious_count}/{result.total_scanners}",
                        "scanners": result.positives_details
                    })

                    if result.is_malicious:
                        malicious_urls.append(url)
                except Exception as e:
                    print(f"⚠️  Error checking URL {url}: {e}")
                    # Add failed check with safe default
                    results.append({
                        "url": url,
                        "is_malicious": False,
                        "is_gambling": False,
                        "gambling_confidence": 0,
                        "gambling_keywords": [],
                        "detections": "error",
                        "scanners": []
                    })

        return {
            "has_urls": True,
            "urls_found": urls,
            "malicious_urls": malicious_urls,
            "gambling_urls": gambling_urls,
            "is_dangerous": len(malicious_urls) > 0 or len(gambling_urls) > 0,
            "details": results
        }

    async def check_url_async(self, url: str) -> VirusTotalResult:
        """Async version of check_url."""
        # Run sync VT check in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.check_url, url)

    async def check_text_for_malicious_urls_async(self, text: str) -> Dict:
        """
        Async version: Check text for malicious URLs.
        Uses asyncio.gather for parallel execution.
        """
        urls = self.extract_urls(text)

        if not urls:
            return {
                "has_urls": False,
                "urls_found": [],
                "malicious_urls": [],
                "is_dangerous": False
            }

        results = []
        malicious_urls = []
        gambling_urls = []

        # Create tasks for all URLs
        tasks = []
        for url in urls:
            tasks.append(self._check_single_url_async(url))

        # Run all checks in parallel
        url_results = await asyncio.gather(*tasks)

        # Process results
        for res in url_results:
            results.append(res)
            if res["is_malicious"]:
                malicious_urls.append(res["url"])
            if res.get("is_gambling"):
                gambling_urls.append(res["url"])

        return {
            "has_urls": True,
            "urls_found": urls,
            "malicious_urls": malicious_urls,
            "gambling_urls": gambling_urls,
            "is_dangerous": len(malicious_urls) > 0 or len(gambling_urls) > 0,
            "details": results
        }

    async def _check_single_url_async(self, url: str) -> Dict:
        """Helper to check a single URL asynchronously (VT + Gambling)."""
        try:
            # 1. Check VirusTotal (in thread)
            vt_result = await self.check_url_async(url)

            # 2. Check Gambling (Async)
            gambling_result = None
            if self.gambling_detector:
                try:
                    # Use the async method directly
                    if hasattr(self.gambling_detector, 'check_url_async'):
                        gambling_result = await self.gambling_detector.check_url_async(url, scrape_content=True, use_headless_if_needed=True)
                    else:
                        # Fallback to sync in thread (should not happen if service is updated)
                        loop = asyncio.get_event_loop()
                        gambling_result = await loop.run_in_executor(
                            None, 
                            lambda: self.gambling_detector.check_url(url, scrape_content=True, use_headless_if_needed=True)
                        )

                    if gambling_result["is_gambling"]:
                        print(f"🎰 Gambling site detected: {url} (confidence: {gambling_result['confidence']:.0%})")
                except Exception as e:
                    print(f"⚠️  Gambling check failed for {url}: {e}")

            return {
                "url": url,
                "is_malicious": vt_result.is_malicious,
                "is_gambling": gambling_result["is_gambling"] if gambling_result else False,
                "gambling_confidence": gambling_result["confidence"] if gambling_result else 0,
                "gambling_keywords": gambling_result["keywords_found"] if gambling_result else [],
                "detections": f"{vt_result.malicious_count}/{vt_result.total_scanners}",
                "scanners": vt_result.positives_details
            }

        except Exception as e:
            print(f"⚠️  Error checking URL {url}: {e}")
            return {
                "url": url,
                "is_malicious": False,
                "is_gambling": False,
                "gambling_confidence": 0,
                "gambling_keywords": [],
                "detections": "error",
                "scanners": []
            }


# Singleton instance
_virustotal_service = None


def get_virustotal_service() -> Optional[VirusTotalService]:
    """Get VirusTotal service instance (singleton).

    Returns:
        VirusTotalService instance or None if API key not configured
    """
    global _virustotal_service

    if _virustotal_service is None:
        try:
            _virustotal_service = VirusTotalService()
        except ValueError:
            # API key not configured
            return None

    return _virustotal_service
