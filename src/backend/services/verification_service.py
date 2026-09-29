"""Verification Service for phone numbers, bank accounts, and social profiles.

Provides verification functionality for Quick Verification Hub feature.
"""

from typing import Dict, Any, Optional
from datetime import datetime
import re

from .blacklist_service import BlacklistService
from .database_service import DatabaseService, get_database_service


class VerificationService:
    """Service for verifying phone numbers, bank accounts, and social profiles."""

    def __init__(self, db_service: DatabaseService = None):
        """
        Initialize verification service.

        Args:
            db_service: Database service instance. If None, uses singleton.
        """
        self.db_service = db_service or get_database_service()
        self.blacklist_service = BlacklistService(self.db_service)

    def verify_phone(self, phone: str) -> Dict[str, Any]:
        """
        Verify a phone number against blacklist.

        Args:
            phone: Phone number to verify (any format)

        Returns:
            {
                "phone": "0812345678",
                "is_blacklisted": bool,
                "is_safe": bool,
                "reports_count": int,
                "risk_level": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
                "last_reported": str | None,
                "categories": dict | None,
                "details": dict | None
            }
        """
        try:
            # Normalize phone number
            clean_phone = self._normalize_phone(phone)

            # Check blacklist
            blacklist_result = self.blacklist_service.check_phone_number(clean_phone)

            if blacklist_result["is_blacklisted"]:
                details = blacklist_result.get("details", {})

                # Extract data from Firestore document
                report_count = details.get("report_count", 1)
                categories = details.get("categories", {})
                last_reported = details.get("last_reported")

                # Format last_reported
                if last_reported:
                    if hasattr(last_reported, 'isoformat'):
                        last_reported = last_reported.isoformat()
                    else:
                        last_reported = str(last_reported)

                # Determine risk level based on report count
                risk_level = self._calculate_risk_level(report_count)

                return {
                    "phone": clean_phone,
                    "is_blacklisted": True,
                    "is_safe": False,
                    "reports_count": report_count,
                    "risk_level": risk_level,
                    "last_reported": last_reported,
                    "categories": categories,
                    "details": details
                }
            else:
                # Not blacklisted - safe
                return {
                    "phone": clean_phone,
                    "is_blacklisted": False,
                    "is_safe": True,
                    "reports_count": 0,
                    "risk_level": "LOW",
                    "last_reported": None,
                    "categories": None,
                    "details": None
                }

        except Exception as e:
            raise Exception(f"Phone verification failed: {str(e)}")

    def verify_bank(self, account_number: str, bank_code: str) -> Dict[str, Any]:
        """
        Verify a bank account against blacklist.

        Args:
            account_number: Bank account number
            bank_code: Bank code (e.g., KBANK, SCB, BBL)

        Returns:
            {
                "account_number": "1234567890",
                "bank_code": "KBANK",
                "is_blacklisted": bool,
                "is_safe": bool,
                "reports_count": int,
                "risk_level": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
                "account_name": str | None,
                "category": str | None,
                "details": dict | None
            }

        Note: For MVP, real data for blacklisted accounts, mock for others
        """
        try:
            # Normalize account number
            clean_account = "".join(filter(str.isdigit, account_number))

            # Check blacklist
            blacklist_result = self.blacklist_service.check_bank_account(bank_code, clean_account)

            if blacklist_result["is_blacklisted"]:
                details = blacklist_result.get("details", {})

                report_count = details.get("report_count", 1)
                risk_level = self._calculate_risk_level(report_count)

                return {
                    "account_number": clean_account,
                    "bank_code": bank_code,
                    "is_blacklisted": True,
                    "is_safe": False,
                    "reports_count": report_count,
                    "risk_level": risk_level,
                    "account_name": details.get("account_name"),
                    "category": details.get("category"),
                    "details": details
                }
            else:
                # Not blacklisted - perform basic validation
                is_valid = self._validate_bank_account_format(clean_account, bank_code)

                return {
                    "account_number": clean_account,
                    "bank_code": bank_code,
                    "is_blacklisted": False,
                    "is_safe": is_valid,
                    "reports_count": 0,
                    "risk_level": "LOW",
                    "account_name": None,
                    "category": None,
                    "format_valid": is_valid,
                    "details": None
                }

        except Exception as e:
            raise Exception(f"Bank verification failed: {str(e)}")

    def verify_social(self, profile_url: str, platform: str = "auto") -> Dict[str, Any]:
        """
        Verify a social media profile.

        Args:
            profile_url: Social media profile URL
            platform: Platform name (facebook, instagram, line, twitter, auto)

        Returns:
            {
                "profile_url": "...",
                "platform": "facebook",
                "is_valid_url": bool,
                "is_safe": bool,
                "risk_score": 0-100,
                "warnings": [str],
                "recommendations": [str]
            }

        Note: For MVP, basic URL validation only. Full implementation in Phase 2.
        """
        try:
            # Auto-detect platform if not specified
            if platform == "auto":
                platform = self._detect_platform(profile_url)

            # Basic URL validation
            is_valid_url = self._validate_url(profile_url)

            if not is_valid_url:
                return {
                    "profile_url": profile_url,
                    "platform": platform,
                    "is_valid_url": False,
                    "is_safe": False,
                    "risk_score": 0,
                    "warnings": ["Invalid URL format"],
                    "recommendations": ["Please provide a valid URL"]
                }

            # MVP: Basic checks only
            warnings = []
            recommendations = []
            risk_score = 0

            # Check for suspicious patterns
            suspicious_keywords = ["bit.ly", "tinyurl", "short", "redirect"]
            for keyword in suspicious_keywords:
                if keyword in profile_url.lower():
                    warnings.append(f"URL contains suspicious keyword: {keyword}")
                    risk_score += 20

            # Check if it's a legitimate platform domain
            legitimate_domains = {
                "facebook": ["facebook.com", "fb.com", "fb.me"],
                "instagram": ["instagram.com", "instagr.am"],
                "twitter": ["twitter.com", "x.com"],
                "line": ["line.me"],
                "tiktok": ["tiktok.com"],
            }

            is_legitimate = False
            if platform in legitimate_domains:
                for domain in legitimate_domains[platform]:
                    if domain in profile_url.lower():
                        is_legitimate = True
                        break

            if not is_legitimate and platform != "unknown":
                warnings.append(f"URL does not match expected {platform} domain")
                risk_score += 30

            # Determine safety
            is_safe = risk_score < 50

            if not is_safe:
                recommendations.append("Verify this profile through official app")
                recommendations.append("Be cautious before sharing personal information")

            return {
                "profile_url": profile_url,
                "platform": platform,
                "is_valid_url": True,
                "is_safe": is_safe,
                "risk_score": min(risk_score, 100),
                "warnings": warnings,
                "recommendations": recommendations if recommendations else ["Profile appears legitimate"]
            }

        except Exception as e:
            raise Exception(f"Social profile verification failed: {str(e)}")

    # ==================== Helper Methods ====================

    def _normalize_phone(self, phone: str) -> str:
        """
        Normalize phone number to standard format.

        Examples:
            +66812345678 -> 0812345678
            66-81-234-5678 -> 0812345678
            081-234-5678 -> 0812345678
        """
        # Remove all non-digit characters
        clean = "".join(filter(str.isdigit, phone))

        # Handle +66 country code
        if clean.startswith("66"):
            clean = "0" + clean[2:]

        return clean

    def _calculate_risk_level(self, report_count: int) -> str:
        """
        Calculate risk level based on report count.

        Args:
            report_count: Number of reports

        Returns:
            "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
        """
        if report_count >= 20:
            return "CRITICAL"
        elif report_count >= 10:
            return "HIGH"
        elif report_count >= 5:
            return "MEDIUM"
        else:
            return "LOW"

    def _validate_bank_account_format(self, account_number: str, bank_code: str) -> bool:
        """
        Validate bank account number format.

        Note: Basic validation only. Full validation requires bank-specific rules.

        Args:
            account_number: Account number (digits only)
            bank_code: Bank code

        Returns:
            True if format is valid
        """
        # Basic checks
        if not account_number.isdigit():
            return False

        # Check length (most Thai banks use 10-12 digits)
        if len(account_number) < 8 or len(account_number) > 15:
            return False

        # Bank-specific validation (basic)
        bank_formats = {
            "KBANK": (10, 10),  # Kasikorn: 10 digits
            "SCB": (10, 12),    # SCB: 10-12 digits
            "BBL": (10, 12),    # Bangkok Bank: 10-12 digits
            "KTB": (10, 10),    # Krung Thai: 10 digits
            "TMB": (10, 10),    # TMB: 10 digits
        }

        if bank_code in bank_formats:
            min_len, max_len = bank_formats[bank_code]
            if len(account_number) < min_len or len(account_number) > max_len:
                return False

        return True

    def _validate_url(self, url: str) -> bool:
        """
        Validate URL format.

        Args:
            url: URL string

        Returns:
            True if URL format is valid
        """
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
            r'localhost|'  # localhost
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)

        return bool(url_pattern.match(url))

    def _detect_platform(self, url: str) -> str:
        """
        Detect social media platform from URL.

        Args:
            url: Profile URL

        Returns:
            Platform name (facebook, instagram, twitter, line, tiktok, unknown)
        """
        url_lower = url.lower()

        if "facebook.com" in url_lower or "fb.com" in url_lower or "fb.me" in url_lower:
            return "facebook"
        elif "instagram.com" in url_lower or "instagr.am" in url_lower:
            return "instagram"
        elif "twitter.com" in url_lower or "x.com" in url_lower:
            return "twitter"
        elif "line.me" in url_lower:
            return "line"
        elif "tiktok.com" in url_lower:
            return "tiktok"
        elif "linkedin.com" in url_lower:
            return "linkedin"
        else:
            return "unknown"


# Singleton instance
_verification_service_instance = None


def get_verification_service() -> VerificationService:
    """Get or create singleton verification service instance."""
    global _verification_service_instance
    if _verification_service_instance is None:
        _verification_service_instance = VerificationService()
    return _verification_service_instance
