"""Homoglyph detection service for detecting character substitution attacks.

This service detects when scammers use look-alike characters from different scripts
to bypass spam filters (e.g., using Latin 'n' instead of Thai 'ท').
"""

import unicodedata
import re
from typing import Dict, List
from dataclasses import dataclass


@dataclass
class HomoglyphDetectionResult:
    """Result from homoglyph detection."""

    is_suspicious: bool
    confidence: float  # 0.0 to 1.0
    risk_level: str  # SAFE, MEDIUM, HIGH
    detected_confusables: List[str]
    visual_spoof_check: str
    reason: str


class HomoglyphDetector:
    """Detect homoglyph attacks in text using Thai-Latin confusables."""

    # Confusables mapping: Latin/Symbol -> Thai lookalike
    CONFUSABLES_MAP = {
        'w': 'พ', 'W': 'พ',
        'u': 'บ', 'U': 'บ',
        'n': 'ท',
        'o': 'อ', 'O': 'อ', '0': 'อ',  # เลข 0 ก็เหมือน อ
        's': 'ร', 'S': 'ร', '5': 'ร',
        'l': 'เ', 'I': 'เ', '|': 'เ', '1': 'เ',
        'L': 'เ',
        'i': 'เ',
        'x': 'ร',  # บางฟอนต์ x เหมือน ร
        'm': 'ท',  # m อาจมองเป็น ท
        'a': 'ล',  # บางฟอนต์ a เหมือน ล
        'y': 'ย',
        'j': 'ง',
        'p': 'ป',
        'c': 'ค',
        'T': 'ไ',
        't': 'ت',
    }
    
    # Skeleton mapping for normalization: Confusable -> Canonical ASCII
    SKELETON_MAP = {
        # Cyrillic to Latin
        'а': 'a', 'в': 'b', 'с': 'c', 'ԁ': 'd', 'е': 'e', 'ѕ': 's', 'і': 'i',
        'ј': 'j', 'к': 'k', 'ӏ': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'р': 'p',
        'ԛ': 'q', 'г': 'r', 'т': 't', 'у': 'u', 'ѵ': 'v', 'х': 'x', 'у': 'y',
        'z': 'z', 'һ': 'h',
        # Greek to Latin
        'α': 'a', 'β': 'b', 'γ': 'g', 'δ': 'd', 'ε': 'e', 'ζ': 'z', 'η': 'n',
        'θ': 'o', 'ι': 'i', 'κ': 'k', 'λ': 'l', 'μ': 'm', 'ν': 'v', 'ξ': 'x',
        'ο': 'o', 'π': 'p', 'ρ': 'p', 'σ': 's', 'τ': 't', 'υ': 'u', 'φ': 'f',
        'χ': 'x', 'ψ': 'y', 'ω': 'w',
        # Other symbols
        '١': '1', 'ం': 'o', '੦': 'o', '૦': 'o', '०': 'o', '০': 'o', 'ං': 'o',
        '೦': 'o', '∙': '.', '‚': ',', '–': '-', '—': '-', '⁄': '/',
    }


    # Regex patterns
    RE_THAI = re.compile(r'[\u0E00-\u0E7F]')
    RE_LATIN = re.compile(r'[a-zA-Z]')
    RE_INVISIBLE = re.compile(r'[\u200b\u200c\u200d\uFEFF]')  # Zero-width chars

    def __init__(self):
        """Initialize homoglyph detector."""
        pass

    def step1_normalize(self, text: str) -> str:
        """Step 1: Remove invisible characters and fix floating vowels.

        Args:
            text: Input text

        Returns:
            Normalized text
        """
        if not text:
            return ""

        # Remove invisible characters (zero-width spaces, etc.)
        text = self.RE_INVISIBLE.sub('', text)

        # Use NFKC to combine characters (e.g., ำ, แ from เ+เ)
        text = unicodedata.normalize('NFKC', text)

        return text.strip()

    def step2_detect_mixed_script(self, text: str) -> bool:
        """Step 2: Detect if text contains mixed Thai and Latin scripts.

        Args:
            text: Input text

        Returns:
            True if text contains both Thai and Latin characters
        """
        has_thai = bool(self.RE_THAI.search(text))
        has_latin = bool(self.RE_LATIN.search(text))

        # If both Thai and Latin are present, it's suspicious
        return has_thai and has_latin

    def step3_analyze_spoofing(self, text: str) -> Dict:
        """Step 3: Analyze if mixed scripts use homoglyphs (confusables).

        Args:
            text: Input text to analyze

        Returns:
            Dict with analysis results
        """
        # Step 1: Normalize
        normalized_text = self.step1_normalize(text)

        # Step 2: Check for mixed scripts
        is_mixed = self.step2_detect_mixed_script(normalized_text)

        result = {
            "original": text,
            "normalized": normalized_text,
            "is_risk": False,
            "risk_level": "SAFE",
            "details": [],
            "visual_spoof_check": ""
        }

        if not is_mixed:
            # Pure single script (Thai only or Latin only) - safe
            return result

        # Step 3: If mixed, check for confusables
        found_confusables = []
        skeleton_preview = ""  # Show what user might actually see

        for char in normalized_text:
            if self.RE_THAI.match(char):
                skeleton_preview += char
            elif char in self.CONFUSABLES_MAP:
                # Found a Latin char in the confusables map
                fake_thai = self.CONFUSABLES_MAP[char]
                found_confusables.append(f"'{char}' → '{fake_thai}'")
                skeleton_preview += fake_thai  # Replace with Thai lookalike
            else:
                skeleton_preview += char

        if found_confusables:
            result["is_risk"] = True
            result["risk_level"] = "HIGH"
            result["details"] = found_confusables
            result["visual_spoof_check"] = skeleton_preview
        else:
            # Mixed script but no direct confusables (e.g., 'Thai2024')
            result["is_risk"] = True
            result["risk_level"] = "MEDIUM"
            result["details"] = ["Mixed Thai and Latin characters"]
            result["visual_spoof_check"] = normalized_text

        return result

    def detect(self, text: str) -> HomoglyphDetectionResult:
        """Detect homoglyph attacks in text.

        Args:
            text: Input text to analyze

        Returns:
            HomoglyphDetectionResult with detection info
        """
        # Run 3-step analysis
        analysis = self.step3_analyze_spoofing(text)

        # Convert to result format
        is_suspicious = analysis["is_risk"]
        risk_level = analysis["risk_level"]

        # Calculate confidence
        if risk_level == "HIGH":
            confidence = min(1.0, len(analysis["details"]) * 0.3)
        elif risk_level == "MEDIUM":
            confidence = 0.2
        else:
            confidence = 0.0

        # Build reason message
        reason = ""
        if risk_level == "HIGH":
            char_list = analysis["details"][:3]
            reason = f"พบตัวอักษรหลอกลวง: {', '.join(char_list)}"
            if len(analysis["details"]) > 3:
                reason += f" และอีก {len(analysis['details']) - 3} ตัว"
            reason += f" | อาจอ่านเป็น: '{analysis['visual_spoof_check']}'"
        elif risk_level == "MEDIUM":
            reason = "พบการผสมภาษาไทยและอังกฤษในข้อความเดียวกัน"

        return HomoglyphDetectionResult(
            is_suspicious=is_suspicious,
            confidence=confidence,
            risk_level=risk_level,
            detected_confusables=analysis["details"],
            visual_spoof_check=analysis["visual_spoof_check"],
            reason=reason
        )

    def analyze_url_domains(self, text: str) -> List[Dict]:
        """
        Analyzes all URLs in a text to detect homoglyph attacks in domain names.

        Args:
            text: The full text of the message to analyze.

        Returns:
            A list of dictionaries, where each dict represents a suspicious URL found.
            Example:
            [
                {
                    "original_url": "https://gооgle.com",
                    "suspicious_domain": "gооgle.com",
                    "normalized_domain": "google.com",
                    "reason": "Domain 'gооgle.com' uses non-ASCII characters to impersonate 'google.com'."
                }
            ]
            Returns an empty list if no suspicious URLs are found.
        """
        from urllib.parse import urlparse
        
        suspicious_urls = []
        
        # Regex to find URLs in text
        url_regex = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        urls = re.findall(url_regex, text)

        if not urls:
            return suspicious_urls

        for url in urls:
            try:
                # Extract the domain (netloc)
                parsed_url = urlparse(url)
                original_domain = parsed_url.netloc
                
                if not original_domain:
                    continue

                # Create the "skeleton" by replacing confusable characters
                # We work with the IDNA-decoded version of the domain
                try:
                    # Handles Punycode (e.g., xn--... domains)
                    decoded_domain = original_domain.encode('idna').decode('utf-8')
                except Exception:
                    # If IDNA encoding fails, just use the original domain
                    decoded_domain = original_domain

                normalized_domain = ""
                was_modified = False
                for char in decoded_domain.lower():
                    if char in self.SKELETON_MAP:
                        normalized_domain += self.SKELETON_MAP[char]
                        was_modified = True
                    else:
                        normalized_domain += char
                
                # Further cleaning: remove all characters that are not alphanumeric, hyphen, or dot
                normalized_domain = re.sub(r'[^a-z0-9.-]', '', normalized_domain)

                # Compare the original domain (lowercase) with the normalized one
                if was_modified and normalized_domain != decoded_domain.lower():
                    suspicious_urls.append({
                        "original_url": url,
                        "suspicious_domain": original_domain,
                        "normalized_domain": normalized_domain,
                        "reason": f"Domain '{original_domain}' uses non-ASCII characters to impersonate '{normalized_domain}'."
                    })
            except Exception as e:
                # Ignore errors in parsing single URLs
                print(f"⚠️  Error analyzing URL for homoglyphs: {url} - {e}")
                continue
                
        return suspicious_urls


# Global instance
_homoglyph_detector: HomoglyphDetector = None


def get_homoglyph_detector() -> HomoglyphDetector:
    """Get or create homoglyph detector instance.

    Returns:
        HomoglyphDetector instance
    """
    global _homoglyph_detector

    if _homoglyph_detector is None:
        _homoglyph_detector = HomoglyphDetector()

    return _homoglyph_detector
