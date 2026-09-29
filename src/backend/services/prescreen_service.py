"""Pre-screening service for fraud detection.

This service performs fast, rule-based checks to filter suspicious messages
before sending them to AI for detailed analysis. Similar to Gmail spam detection.
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from .headless_scraper_service import get_headless_scraper
from .homoglyph_detector import get_homoglyph_detector
from .url_expander_service import get_url_expander_service, URLExpandResult


@dataclass
class PrescreenResult:
    """Result from pre-screening check."""

    is_suspicious: bool
    confidence: float  # 0.0 to 1.0
    matched_patterns: List[str]
    should_check_with_ai: bool
    analysis_message: str
    is_educational_context: bool = False
    urls_found: List[str] = field(default_factory=list)


class FraudPrescreenService:
    """Fast rule-based pre-screening for fraud detection."""

    def __init__(
        self,
        config_path: Optional[str] = None,
    ):
        """Initialize pre-screen service.

        Args:
            config_path: Path to fraud patterns JSON config. If None, uses default path.
        """
        # Load patterns from JSON config
        if config_path is None:
            # Default path: src/backend/core/fraud_patterns.json
            config_path = Path(__file__).parent.parent / "core" / "fraud_patterns.json"
        else:
            config_path = Path(config_path)

        # Load config
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)

        # Get thresholds from config
        self.min_confidence_for_ai = self.config["thresholds"]["min_confidence_for_ai"]

        # Compile whitelist patterns (safe domains that should be ignored)
        self._whitelist_patterns = []
        if "whitelist" in self.config and "safe_domains" in self.config["whitelist"]:
            self._whitelist_patterns = [
                re.compile(pattern, re.IGNORECASE)
                for pattern in self.config["whitelist"]["safe_domains"]
            ]

        # Load legitimate context signals
        self._legitimate_contexts = []
        if "context_signals" in self.config and "legitimate_contexts" in self.config["context_signals"]:
            self._legitimate_contexts = [
                ctx.lower() for ctx in self.config["context_signals"]["legitimate_contexts"]
            ]

        # Compile regex patterns for efficiency
        self._pattern_groups = {}
        for group_name, group_config in self.config["patterns"].items():
            patterns = [re.compile(p, re.IGNORECASE) for p in group_config["patterns"]]
            weight = group_config["weight"]
            self._pattern_groups[group_name] = {
                "patterns": patterns,
                "weight": weight
            }

        # Load special checks config
        self.special_checks = self.config["special_checks"]

    def _is_whitelisted(self, message: str) -> bool:
        """Check if message contains whitelisted safe domains.

        Args:
            message: Message text to check

        Returns:
            True if message contains safe domain, False otherwise
        """
        for pattern in self._whitelist_patterns:
            if pattern.search(message):
                return True
        return False

    def _has_legitimate_context(self, message: str) -> bool:
        """Check if message appears to be legitimate content (news, review, warning).

        Args:
            message: Message text to check

        Returns:
            True if message has legitimate context signals, False otherwise
        """
        message_lower = message.lower()
        for ctx in self._legitimate_contexts:
            if ctx in message_lower:
                return True
        return False

    def _normalize_and_find_urls(self, text: str) -> List[str]:
        """
        Normalizes text to reveal obfuscated URLs and finds all possible URLs.
        Handles:
        - Obfuscation like [.] and " dot "
        - URLs without http/https schemes (e.g., www.example.com)
        """
        # De-obfuscate common patterns without removing all spaces
        deobfuscated_text = text.replace("[.]", ".").replace("(.)", ".")
        deobfuscated_text = re.sub(r'\s*dot\s*', '.', deobfuscated_text, flags=re.IGNORECASE)

        # Regex for finding standard URLs with schemes
        standard_urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', deobfuscated_text)

        # Regex for finding things that look like domains but might not have a scheme
        # e.g., www.example.com or sub.domain.co.th
        domain_regex = r'\b(?:www\.|[a-zA-Z0-9-]+\.)[a-zA-Z0-9-]+\.[a-zA-Z]{2,6}\b'
        potential_domains = re.findall(domain_regex, deobfuscated_text, re.IGNORECASE)

        # Prepend https:// to found domains that are not already part of a full URL
        schemeless_urls = []
        for domain in potential_domains:
            # Check if this domain is already part of a full URL we've found
            if not any(domain in std_url for std_url in standard_urls):
                schemeless_urls.append('https://' + domain)
                
        # Combine and return unique URLs
        return list(set(standard_urls + schemeless_urls))

    def check_message(self, message: str) -> PrescreenResult:
        """Pre-screen a message for fraud indicators.

        Args:
            message: Message text to check

        Returns:
            PrescreenResult with suspicion level and matched patterns
        """
        # Expand URLs, replace them in the message, and then scrape content
        url_expander = get_url_expander_service()
        scraper = get_headless_scraper()
        
        # Use a copy of the message for analysis
        analysis_message = message
        
        urls = self._normalize_and_find_urls(analysis_message)
        
        scraped_content = []
        expand_results = {}

        if urls:
            expand_results = url_expander.expand_multiple(urls)
            final_urls_to_scrape = []
            
            successful_expansions = 0
            for original_url, result in expand_results.items():
                if result and not result.error:
                    # Expansion was successful
                    final_urls_to_scrape.append(result.final_url)
                    if result.final_url != original_url:
                        # Replace short URL with final URL for analysis
                        analysis_message = analysis_message.replace(original_url, result.final_url)
                        successful_expansions += 1
                else:
                    # Expansion failed (timeout or other error)
                    # Remove the problematic URL from the message to avoid false positives on the shortener itself
                    analysis_message = analysis_message.replace(original_url, "")
                    print(f"⚠️ Failed to expand {original_url}, removing it from analysis. Reason: {result.error if result else 'Unknown'}")

            if successful_expansions > 0:
                print(f"🔗 Replaced {successful_expansions} short URLs in message for analysis.")

            # Scrape content from the successfully expanded URLs
            if final_urls_to_scrape:
                scraped_urls = set() # Use a set to track scraped URLs to avoid duplicates
                for url in final_urls_to_scrape:
                    if url and url not in scraped_urls:
                        scrape_result = scraper.scrape_url(url)
                        if scrape_result.get("success"):
                            # Penalize suspicious JS-based redirects
                            if scrape_result.get("was_redirected"):
                                reason = f"delayed_js_redirect: {scrape_result.get('initial_url', '')} -> {scrape_result.get('final_url', '')}"
                                if reason not in matched_patterns:
                                    matched_patterns.append(reason)
                                    score += 0.7  # High penalty for suspicious redirects
                            
                            # Add scraped text for analysis
                            if scrape_result.get("text"):
                                scraped_content.append(str(scrape_result["text"]))
                        
                        scraped_urls.add(url) # Mark this URL as scraped

        
        # Append scraped content for analysis
        if scraped_content:
            # Join the scraped text content into a single string
            analysis_message += " " + " ".join(scraped_content)

        # Correctly extract final URLs for the result
        final_urls_found = [res.final_url for res in expand_results.values() if res and not res.error]

        # Check for legitimate context BEFORE all other checks
        has_legit_context = self._has_legitimate_context(analysis_message)

        # FIRST: Check if message contains whitelisted safe domains
        if self._is_whitelisted(analysis_message):
            return PrescreenResult(
                is_suspicious=False,
                confidence=0.0,
                matched_patterns=["whitelisted_safe_domain"],
                should_check_with_ai=False,
                analysis_message=analysis_message,
                is_educational_context=has_legit_context,
                urls_found=final_urls_found,
            )

        matched_patterns = []
        score = 0.0

        # Add context to matched_patterns if detected
        if has_legit_context:
            matched_patterns.append("legitimate_context_detected")

        # Initialize homoglyph detector once for both checks
        homoglyph_detector = get_homoglyph_detector()

        # Check all pattern groups from config FIRST (faster than homoglyph)
        for group_name, group_data in self._pattern_groups.items():
            patterns = group_data["patterns"]
            weight = group_data["weight"]

            for pattern in patterns:
                if pattern.search(analysis_message):
                    matched_patterns.append(f"{group_name}: {pattern.pattern}")
                    # Reduce weight if legitimate context detected (80% reduction)
                    applied_weight = weight * 0.2 if has_legit_context else weight
                    score += applied_weight
                    break  # Only count once per group to avoid double-counting

        # Only check homoglyph if message has SOME suspicion (score >= 0.1)
        # AND does NOT have legitimate context (news/review/warning)
        # This avoids expensive homoglyph detection on clearly safe messages
        if score >= 0.1 and not has_legit_context:
            homoglyph_detector = get_homoglyph_detector()
            homoglyph_result = homoglyph_detector.detect(analysis_message)

            if homoglyph_result.is_suspicious:
                matched_patterns.append(f"homoglyph_attack: {homoglyph_result.reason}")
                score += homoglyph_result.confidence

        # Check for Homoglyph attacks in URLs (HIGH PRIORITY)
        # This is a strong signal and should not be discounted by legitimate context.
        url_homoglyph_results = homoglyph_detector.analyze_url_domains(analysis_message)
        if url_homoglyph_results:
            for result in url_homoglyph_results:
                reason = f"homoglyph_url_attack: {result['reason']}"
                if reason not in matched_patterns:
                    matched_patterns.append(reason)
                    score += 0.9  # Very high confidence for URL spoofing

        # Check message length
        msg_len = len(analysis_message)
        if msg_len < self.special_checks["very_short_message_threshold"]:
            # Too short, likely safe greeting
            score += self.special_checks["very_short_message_penalty"]
        elif msg_len > self.special_checks["very_long_message_threshold"]:
            # Very long, might be spam
            matched_patterns.append("very_long_message")
            score += self.special_checks["very_long_message_weight"]

        # Check for multiple URLs
        url_count = len(urls) # Use the already found urls
        if url_count >= self.special_checks["multiple_urls_threshold"]:
            matched_patterns.append(f"multiple_urls: {url_count}")
            score += self.special_checks["multiple_urls_weight"]

        # Normalize confidence to 0.0-1.0
        confidence = min(1.0, max(0.0, score))

        # Determine if suspicious
        is_suspicious = confidence >= self.min_confidence_for_ai

        # Determine if should check with AI
        should_check_with_ai = is_suspicious

        return PrescreenResult(
            is_suspicious=is_suspicious,
            confidence=confidence,
            matched_patterns=matched_patterns,
            should_check_with_ai=should_check_with_ai,
            analysis_message=analysis_message,
            is_educational_context=has_legit_context,
            urls_found=final_urls_found,
        )

    def get_quick_response(self, prescreen_result: PrescreenResult) -> Optional[str]:
        """Get a quick response for clearly safe messages.

        Args:
            prescreen_result: Result from pre-screening

        Returns:
            Quick response text if message is clearly safe, None otherwise
        """
        # If confidence is very low, message is likely safe
        if prescreen_result.confidence < 0.1:
            return None  # No need to respond to normal conversation

        # If suspicious, let AI handle it
        if prescreen_result.should_check_with_ai:
            return None

        return None


# Global instance
_prescreen_service: Optional[FraudPrescreenService] = None


def get_prescreen_service() -> FraudPrescreenService:
    """Get or create pre-screen service instance.

    Returns:
        FraudPrescreenService instance
    """
    global _prescreen_service

    if _prescreen_service is None:
        _prescreen_service = FraudPrescreenService()

    return _prescreen_service