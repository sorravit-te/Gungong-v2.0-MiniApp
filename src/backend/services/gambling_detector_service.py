"""
Gambling Website Detection Service

Detects gambling/casino/betting websites using:
1. Domain pattern matching (fast)
2. URL keyword analysis (fast)
3. Web content scraping (slower, optional)
"""

import re
import httpx
import asyncio
from typing import Optional, Dict, List, Set
from urllib.parse import urlparse
from bs4 import BeautifulSoup


class GamblingDetectorService:
    """Service for detecting gambling/casino websites."""

    # Domain TLDs commonly used by gambling sites
    GAMBLING_TLDS = {
        '.bet', '.casino', '.poker', '.game', '.games',
        '.betting', '.sport', '.esport', '.lotto'
    }

    # Domain keywords that indicate gambling
    DOMAIN_KEYWORDS = {
        # English
        'casino', 'slot', 'slots', 'poker', 'betting', 'bet', 'gamble',
        'lottery', 'lotto', 'jackpot', 'roulette', 'blackjack', 'baccarat',
        'sportbet', 'sportsbook', 'odds', 'wager',

        # Thai (romanized)
        'baccara', 'bacara', 'slotxo', 'pgslot', 'joker123',
        'ufabet', 'sbobet', 'maxbet', 'sagame', 'sexy', 'sexygame',
        'ambbet', 'amb', 'live22', 'spade', 'king', 'luckyking',
        'winner', 'richman', 'fortune', 'gold', 'diamond', 'royal'
    }

    # Path keywords
    PATH_KEYWORDS = {
        'casino', 'slot', 'poker', 'betting', 'bet', 'register',
        'signup', 'deposit', 'withdraw', 'promotion', 'bonus'
    }

    # Whitelisted domains to skip content scraping (performance optimization)
    SAFE_DOMAINS = {
        'line.me', 'line.naver.jp', 'liff.line.me',
        'google.com', 'www.google.com', 'youtu.be', 'youtube.com', 'www.youtube.com',
        'facebook.com', 'www.facebook.com', 'm.facebook.com',
        'instagram.com', 'www.instagram.com',
        'twitter.com', 'x.com',
        'tiktok.com', 'www.tiktok.com',
        'pantip.com', 'www.pantip.com',
        'wikipedia.org', 'en.wikipedia.org', 'th.wikipedia.org'
    }

    # Thai gambling keywords for content analysis
    THAI_GAMBLING_KEYWORDS = {
        # Direct gambling terms
        'คาสิโน', 'สล็อต', 'บาคาร่า', 'เสือมังกร', 'รูเล็ต',
        'ไฮโล', 'ป๊อกเด้ง', 'แทงบอล', 'พนันบอล', 'เดิมพัน',
        'หวย', 'ลอตเตอรี่', 'แทงหวย', 'หวยออนไลน์',

        # Platform terms
        'เว็บพนัน', 'เว็บตรง', 'ไม่ผ่านเอเย่นต์', 'ฝากถอน',
        'ฝากถอนออโต้', 'ถอนไม่อั้น', 'แตกง่าย', 'แตกหนัก',
        'โบนัส', 'เครดิตฟรี', 'ฟรีเครดิต', 'ทดลองเล่น',

        # Payment terms
        'ฝากขั้นต่ำ', 'ถอนขั้นต่ำ', 'ฝาก-ถอน', 'ทรูวอลเล็ท',

        # Games
        'สล็อตออนไลน์', 'คาสิโนออนไลน์', 'บาคาร่าออนไลน์',
        'ยิงปลา', 'เกมยิงปลา'
    }

    # English gambling keywords
    ENGLISH_GAMBLING_KEYWORDS = {
        'casino', 'slot machine', 'slots', 'baccarat', 'roulette',
        'blackjack', 'poker', 'betting', 'gambling', 'wager',
        'deposit', 'withdraw', 'bonus', 'free credit', 'jackpot',
        'sports betting', 'live casino', 'online casino'
    }

    def __init__(self, timeout: int = 10, use_headless: bool = True):
        """
        Initialize gambling detector.

        Args:
            timeout: HTTP request timeout in seconds
            use_headless: Enable headless browser fallback for JavaScript-heavy sites
        """
        self.timeout = timeout
        self.use_headless = use_headless
        self.client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )

        # Initialize headless scraper (lazy loading)
        self.headless_scraper = None
        if use_headless:
            try:
                from .headless_scraper_service import get_headless_scraper
                self.headless_scraper = get_headless_scraper()
            except ImportError:
                print("⚠️  Headless scraper not available (Playwright not installed)")
                self.use_headless = False

    def check_url(self, url: str, scrape_content: bool = False, use_headless_if_needed: bool = True) -> Dict:
        """
        Check if URL is a gambling website.

        Args:
            url: URL to check
            scrape_content: Whether to scrape and analyze content (slower)
            use_headless_if_needed: Use headless browser if httpx insufficient (requires scrape_content=True)

        Returns:
            Dict with detection results:
            {
                "is_gambling": bool,
                "confidence": float (0-1),
                "detected_by": list of detection methods,
                "keywords_found": list of keywords found,
                "details": str
            }
        """
        result = {
            "is_gambling": False,
            "confidence": 0.0,
            "detected_by": [],
            "keywords_found": [],
            "details": ""
        }

        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            path = parsed.path.lower()

            # Method 1: Check TLD
            tld_match = self._check_tld(domain)
            if tld_match:
                result["detected_by"].append("tld")
                result["keywords_found"].append(f"TLD: {tld_match}")
                result["confidence"] += 0.4

            # Method 2: Check domain keywords
            domain_keywords = self._check_domain_keywords(domain)
            if domain_keywords:
                result["detected_by"].append("domain_keyword")
                result["keywords_found"].extend(domain_keywords)
                result["confidence"] += 0.3 * len(domain_keywords)

            # Method 3: Check path keywords
            path_keywords = self._check_path_keywords(path)
            if path_keywords:
                result["detected_by"].append("path_keyword")
                result["keywords_found"].extend(path_keywords)
                result["confidence"] += 0.2 * len(path_keywords)

            # Check whitelist - Skip content scraping for safe domains
            is_safe_domain = domain in self.SAFE_DOMAINS or any(domain.endswith('.' + safe) for safe in self.SAFE_DOMAINS)
            
            if is_safe_domain:
                # print(f"🛡️ Skipping content scraping for safe domain: {domain}")
                scrape_content = False

            # Method 4: Scrape content (optional, slower)
            if scrape_content and result["confidence"] < 0.7:
                content_result = self._scrape_and_analyze(url, use_headless=use_headless_if_needed)
                if content_result["keywords_found"]:
                    result["detected_by"].append("content_analysis")
                    result["keywords_found"].extend(content_result["keywords_found"])
                    result["confidence"] += content_result["confidence"]

            # Cap confidence at 1.0
            result["confidence"] = min(result["confidence"], 1.0)

            # Determine if it's gambling (confidence > 0.5)
            result["is_gambling"] = result["confidence"] >= 0.5

            # Build details message
            if result["is_gambling"]:
                methods = ", ".join(result["detected_by"])
                result["details"] = f"Detected as gambling site ({methods})"
            else:
                result["details"] = "Not detected as gambling site"

            return result

        except Exception as e:
            print(f"⚠️  Gambling detection error for {url}: {e}")
            return result

    def _check_tld(self, domain: str) -> Optional[str]:
        """Check if domain uses gambling TLD."""
        for tld in self.GAMBLING_TLDS:
            if domain.endswith(tld):
                return tld
        return None

    def _check_domain_keywords(self, domain: str) -> List[str]:
        """Check if domain contains gambling keywords."""
        found = []
        for keyword in self.DOMAIN_KEYWORDS:
            if keyword in domain:
                found.append(f"domain:{keyword}")
        return found

    def _check_path_keywords(self, path: str) -> List[str]:
        """Check if URL path contains gambling keywords."""
        found = []
        for keyword in self.PATH_KEYWORDS:
            if keyword in path:
                found.append(f"path:{keyword}")
        return found

    async def check_url_async(self, url: str, scrape_content: bool = False, use_headless_if_needed: bool = True) -> Dict:
        """Async version of check_url."""
        # Use run_in_executor for the CPU-bound parts (parsing, keywords)
        # But use await for the I/O parts (httpx, headless)
        
        result = {
            "is_gambling": False,
            "confidence": 0.0,
            "detected_by": [],
            "keywords_found": [],
            "details": ""
        }

        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            path = parsed.path.lower()

            # Method 1: Check TLD
            tld_match = self._check_tld(domain)
            if tld_match:
                result["detected_by"].append("tld")
                result["keywords_found"].append(f"TLD: {tld_match}")
                result["confidence"] += 0.4

            # Method 2: Check domain keywords
            domain_keywords = self._check_domain_keywords(domain)
            if domain_keywords:
                result["detected_by"].append("domain_keyword")
                result["keywords_found"].extend(domain_keywords)
                result["confidence"] += 0.3 * len(domain_keywords)

            # Method 3: Check path keywords
            path_keywords = self._check_path_keywords(path)
            if path_keywords:
                result["detected_by"].append("path_keyword")
                result["keywords_found"].extend(path_keywords)
                result["confidence"] += 0.2 * len(path_keywords)

            # Check whitelist - Skip content scraping for safe domains
            is_safe_domain = domain in self.SAFE_DOMAINS or any(domain.endswith('.' + safe) for safe in self.SAFE_DOMAINS)
            
            if is_safe_domain:
                # print(f"🛡️ Skipping content scraping for safe domain: {domain}")
                scrape_content = False

            # Method 4: Scrape content (optional, slower)
            if scrape_content and result["confidence"] < 0.7:
                content_result = await self._scrape_and_analyze_async(url, use_headless=use_headless_if_needed)
                if content_result["keywords_found"]:
                    result["detected_by"].append("content_analysis")
                    result["keywords_found"].extend(content_result["keywords_found"])
                    result["confidence"] += content_result["confidence"]

            # Cap confidence at 1.0
            result["confidence"] = min(result["confidence"], 1.0)

            # Determine if it's gambling (confidence > 0.5)
            result["is_gambling"] = result["confidence"] >= 0.5

            # Build details message
            if result["is_gambling"]:
                methods = ", ".join(result["detected_by"])
                result["details"] = f"Detected as gambling site ({methods})"
            else:
                result["details"] = "Not detected as gambling site"

            return result

        except Exception as e:
            print(f"⚠️  Gambling detection error for {url}: {e}")
            return result

    async def _scrape_and_analyze_async(self, url: str, use_headless: bool = False) -> Dict:
        """Async version of _scrape_and_analyze."""
        result = {
            "keywords_found": [],
            "confidence": 0.0
        }

        # Step 1: Try httpx first (fast) - Use async client if possible, or wrap sync
        # For now, wrap sync httpx in executor
        loop = asyncio.get_event_loop()
        httpx_result = await loop.run_in_executor(None, self._scrape_with_httpx, url)

        # Step 2: If httpx got good confidence (>0.6), use it
        if httpx_result["confidence"] >= 0.6 or not use_headless or not self.headless_scraper:
            return httpx_result

        # Step 3: If confidence low and headless available, try headless browser
        print(f"🔄 httpx confidence low ({httpx_result['confidence']:.0%}), trying headless browser...")

        try:
            # Call the ASYNC method directly
            headless_result = await self.headless_scraper._scrape_and_analyze_async(url)

            if headless_result["success"] and headless_result["confidence"] > httpx_result["confidence"]:
                print(f"✅ Headless browser improved confidence: {httpx_result['confidence']:.0%} → {headless_result['confidence']:.0%} ({headless_result['time']:.1f}s)")
                return {
                    "keywords_found": headless_result["keywords_found"],
                    "confidence": headless_result["confidence"]
                }
            else:
                print(f"⚠️  Headless browser didn't improve results, using httpx")

        except Exception as e:
            print(f"⚠️  Headless scraping failed: {e}, fallback to httpx")

        return httpx_result

    def _scrape_and_analyze(self, url: str, use_headless: bool = False) -> Dict:
        """
        Scrape website and analyze content for gambling keywords.
        """
        # ... (keep original sync method for backward compatibility if needed)
        # But actually, we can just implement it as before or leave it.
        # Since we are replacing it, let's keep the sync implementation here for reference or fallback.
        # Wait, I am REPLACING the sync method with the async one in the file content?
        # No, I should ADD the async method and KEEP the sync one if possible, or replace if unused.
        # The user instruction says "Implement async versions...".
        # I will ADD them.
        return self._scrape_and_analyze_sync(url, use_headless)

    def _scrape_and_analyze_sync(self, url: str, use_headless: bool = False) -> Dict:
        """Sync version of _scrape_and_analyze."""
        result = {
            "keywords_found": [],
            "confidence": 0.0
        }

        # Step 1: Try httpx first (fast)
        httpx_result = self._scrape_with_httpx(url)

        # Step 2: If httpx got good confidence (>0.6), use it
        if httpx_result["confidence"] >= 0.6 or not use_headless or not self.headless_scraper:
            return httpx_result

        # Step 3: If confidence low and headless available, try headless browser
        print(f"🔄 httpx confidence low ({httpx_result['confidence']:.0%}), trying headless browser...")

        try:
            # Call the sync wrapper
            headless_result = self.headless_scraper.scrape_and_analyze(url)

            if headless_result["success"] and headless_result["confidence"] > httpx_result["confidence"]:
                print(f"✅ Headless browser improved confidence: {httpx_result['confidence']:.0%} → {headless_result['confidence']:.0%} ({headless_result['time']:.1f}s)")
                return {
                    "keywords_found": headless_result["keywords_found"],
                    "confidence": headless_result["confidence"]
                }
            else:
                print(f"⚠️  Headless browser didn't improve results, using httpx")

        except Exception as e:
            print(f"⚠️  Headless scraping failed: {e}, fallback to httpx")

        return httpx_result

    def _scrape_with_httpx(self, url: str) -> Dict:
        """
        Scrape website using httpx (fast but may miss JavaScript content).

        Returns:
            Dict with keywords_found and confidence
        """
        result = {
            "keywords_found": [],
            "confidence": 0.0
        }

        try:
            # Fetch page
            response = self.client.get(url)
            response.raise_for_status()

            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')

            # Get text content
            text = soup.get_text().lower()

            # Also check meta tags
            meta_keywords = []
            for meta in soup.find_all('meta'):
                if meta.get('name') in ['keywords', 'description']:
                    content = meta.get('content', '').lower()
                    meta_keywords.append(content)

            meta_text = ' '.join(meta_keywords)
            full_text = f"{text} {meta_text}"

            # Check Thai keywords
            thai_found = []
            for keyword in self.THAI_GAMBLING_KEYWORDS:
                if keyword in full_text:
                    thai_found.append(f"thai:{keyword}")

            # Check English keywords
            english_found = []
            for keyword in self.ENGLISH_GAMBLING_KEYWORDS:
                if keyword in full_text:
                    english_found.append(f"en:{keyword}")

            # Calculate confidence based on keyword count
            total_keywords = len(thai_found) + len(english_found)
            if total_keywords > 0:
                result["keywords_found"] = thai_found + english_found
                # More keywords = higher confidence (cap at 0.5 for content alone)
                result["confidence"] = min(0.1 * total_keywords, 0.5)

            return result

        except Exception as e:
            print(f"⚠️  Content scraping failed for {url}: {e}")
            return result

    def __del__(self):
        """Clean up HTTP client."""
        try:
            self.client.close()
        except:
            pass


# Singleton instance
_gambling_detector_instance = None


def get_gambling_detector() -> GamblingDetectorService:
    """Get or create singleton gambling detector instance."""
    global _gambling_detector_instance
    
    if _gambling_detector_instance is None:
        from ..core.performance_config import get_performance_config
        config = get_performance_config()
        
        _gambling_detector_instance = GamblingDetectorService(
            timeout=int(config.GAMBLING_DETECTION_TIMEOUT),
            use_headless=config.ENABLE_GAMBLING_SCRAPING
        )
    return _gambling_detector_instance
