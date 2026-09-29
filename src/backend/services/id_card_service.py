"""ID Card Service for verification and blacklist checking."""

from typing import Dict, Any
from datetime import datetime

from .database_service import DatabaseService, get_database_service
from .id_card_ocr_service import get_ocr_service
from ..utils.thai_id_validator import validate_thai_id, normalize_thai_id
from ..core.models import COLLECTION_BLACKLIST_ID_CARDS


class IDCardService:
    """Service for Thai ID card verification and blacklist checking."""

    def __init__(self, db_service: DatabaseService = None):
        """
        Initialize ID Card Service.

        Args:
            db_service: Database service instance (defaults to singleton)
        """
        self.db_service = db_service or get_database_service()
        self.ocr_service = get_ocr_service()

    def check_id_blacklist(self, id_number: str) -> Dict[str, Any]:
        """
        Check if Thai ID is blacklisted in Firestore.

        Args:
            id_number: Thai ID number (13 digits)

        Returns:
            Dictionary with:
            - is_blacklisted: bool
            - details: dict (if blacklisted)
            - error: str (if error occurred)

        Examples:
            >>> service = IDCardService()
            >>> result = service.check_id_blacklist("1234567890123")
            >>> print(result['is_blacklisted'])
            False
        """
        try:
            # Normalize ID number
            clean_id = normalize_thai_id(id_number)

            if not clean_id or len(clean_id) != 13:
                return {
                    "is_blacklisted": False,
                    "error": "Invalid ID number format"
                }

            # Query Firestore
            doc_ref = self.db_service.db.collection(COLLECTION_BLACKLIST_ID_CARDS).document(clean_id)
            doc = doc_ref.get()

            if doc.exists:
                data = doc.to_dict()
                return {
                    "is_blacklisted": True,
                    "details": data
                }

            return {"is_blacklisted": False}

        except Exception as e:
            print(f"[ERROR] Error checking ID blacklist: {e}")
            return {
                "is_blacklisted": False,
                "error": str(e)
            }

    def verify_id_card(self, image_base64: str) -> Dict[str, Any]:
        """
        Complete ID card verification flow:
        1. OCR extraction using Gemini Vision
        2. Format validation (13-digit checksum)
        3. Blacklist checking

        Args:
            image_base64: Base64 encoded ID card image

        Returns:
            Dictionary with verification results:
            - success: bool
            - id_number: str
            - is_valid_format: bool
            - is_blacklisted: bool
            - is_safe: bool
            - reports_count: int
            - risk_level: str (LOW, MEDIUM, HIGH, CRITICAL)
            - category: str (if blacklisted)
            - extracted_data: dict (OCR results)
            - error: str (if failed)

        Examples:
            >>> service = IDCardService()
            >>> result = service.verify_id_card(base64_image)
            >>> print(f"Safe: {result['is_safe']}, Risk: {result['risk_level']}")
        """
        # Step 1: Extract data from image using OCR
        print("[OCR] Starting OCR extraction...")
        ocr_result = self.ocr_service.extract_id_card_data(image_base64)

        if not ocr_result.get("success"):
            print(f"[ERROR] OCR failed: {ocr_result.get('error')}")
            return {
                "success": False,
                "error": "OCR failed: " + ocr_result.get("error", "Unknown error"),
                "is_valid_format": False,
                "is_blacklisted": False,
                "is_safe": False,
                "reports_count": 0,
                "risk_level": "UNKNOWN"
            }

        id_number = ocr_result.get("id_number")

        if not id_number:
            print("[ERROR] Could not extract ID number")
            return {
                "success": False,
                "error": "Could not extract ID number from card",
                "is_valid_format": False,
                "is_blacklisted": False,
                "is_safe": False,
                "reports_count": 0,
                "risk_level": "UNKNOWN"
            }

        print(f"[OK] OCR successful, extracted ID: {id_number[:4]}****{id_number[-2:]}")

        # Step 2: Validate format using checksum
        is_valid_format = validate_thai_id(id_number)
        print(f"[VALIDATION] Format validation: {'Valid' if is_valid_format else 'Invalid'}")

        # Step 3: Check blacklist
        print("[CHECK] Checking blacklist...")
        blacklist_result = self.check_id_blacklist(id_number)
        is_blacklisted = blacklist_result.get("is_blacklisted", False)

        # Calculate risk level and build response
        if is_blacklisted:
            details = blacklist_result.get("details", {})
            report_count = details.get("report_count", 1)

            # Calculate risk level based on report count
            if report_count >= 20:
                risk_level = "CRITICAL"
            elif report_count >= 10:
                risk_level = "HIGH"
            elif report_count >= 5:
                risk_level = "MEDIUM"
            else:
                risk_level = "LOW"

            print(f"[WARNING] BLACKLISTED: {report_count} reports, risk: {risk_level}")

            return {
                "success": True,
                "id_number": id_number,
                "is_valid_format": is_valid_format,
                "is_blacklisted": True,
                "is_safe": False,
                "reports_count": report_count,
                "risk_level": risk_level,
                "category": details.get("category"),
                "last_reported": details.get("last_reported"),
                "extracted_data": ocr_result,
                "error": None
            }
        else:
            # Not blacklisted
            risk_level = "LOW" if is_valid_format else "MEDIUM"
            print(f"[OK] Safe: Not in blacklist, risk: {risk_level}")

            return {
                "success": True,
                "id_number": id_number,
                "is_valid_format": is_valid_format,
                "is_blacklisted": False,
                "is_safe": is_valid_format,
                "reports_count": 0,
                "risk_level": risk_level,
                "category": None,
                "last_reported": None,
                "extracted_data": ocr_result,
                "error": None
            }

    def verify_id_number_only(self, id_number: str) -> dict:
        """
        Verify Thai National ID number without image scanning.

        Args:
            id_number: 13-digit Thai National ID number

        Returns:
            dict: Verification result
        """
        print(f"[ID-CHECK] Verifying ID number: {id_number[:4]}****{id_number[-2:]}")

        # Validate format
        is_valid_format = self.thai_id_validator.validate(id_number)
        print(f"[VALIDATION] Format validation: {'Valid' if is_valid_format else 'Invalid'}")

        # Check blacklist
        print("[CHECK] Checking blacklist...")
        blacklist_result = self.database_service.check_blacklist_id_card(id_number)

        is_blacklisted = blacklist_result.get("is_blacklisted", False)
        reports_count = blacklist_result.get("reports_count", 0)
        category = blacklist_result.get("category")
        last_reported = blacklist_result.get("last_reported")

        # Determine risk level
        if is_blacklisted:
            if reports_count >= 10:
                risk_level = "CRITICAL"
            elif reports_count >= 5:
                risk_level = "HIGH"
            else:
                risk_level = "MEDIUM"
            print(f"[WARNING] BLACKLISTED: {reports_count} reports, risk: {risk_level}")
        else:
            risk_level = "LOW" if is_valid_format else "MEDIUM"
            print(f"[OK] Safe: Not in blacklist, risk: {risk_level}")

        # Overall safety
        is_safe = is_valid_format and not is_blacklisted

        return {
            "success": True,
            "id_number": id_number,
            "is_valid_format": is_valid_format,
            "is_blacklisted": is_blacklisted,
            "is_safe": is_safe,
            "reports_count": reports_count,
            "risk_level": risk_level,
            "category": category,
            "last_reported": last_reported,
            "extracted_data": None,
            "error": None
        }


# Singleton instance
_id_card_service_instance = None


def get_id_card_service() -> IDCardService:
    """Get singleton instance of IDCardService."""
    global _id_card_service_instance
    if _id_card_service_instance is None:
        _id_card_service_instance = IDCardService()
    return _id_card_service_instance
