"""Thai ID checksum, OCR, and fraud-blacklist verification service."""

from typing import Any, Dict, Optional

from .database_service import DatabaseService, get_database_service
from .id_card_ocr_service import IDCardOCRService, get_ocr_service
from ..core.logger import get_logger
from ..core.models import COLLECTION_BLACKLIST_ID_CARDS
from ..utils.thai_id_validator import normalize_thai_id, validate_thai_id


logger = get_logger(__name__)

BLACKLIST_UNAVAILABLE = "blacklist_unavailable"
OCR_UNAVAILABLE = "ocr_unavailable"


def _mask_id(id_number: str) -> str:
    """Return a log-safe representation without exposing the full ID."""
    clean_id = normalize_thai_id(id_number)
    if len(clean_id) < 6:
        return "****"
    return f"{clean_id[:4]}****{clean_id[-2:]}"


def _risk_level_for_reports(report_count: int) -> str:
    """Apply the shared blacklist report-count risk thresholds."""
    if report_count >= 20:
        return "CRITICAL"
    if report_count >= 10:
        return "HIGH"
    if report_count >= 5:
        return "MEDIUM"
    return "LOW"


class IDCardService:
    """Check Thai ID checksums and the fraud blacklist, with optional OCR."""

    def __init__(
        self,
        db_service: Optional[DatabaseService] = None,
        ocr_service: Optional[IDCardOCRService] = None,
    ):
        """
        Initialize ID Card Service.

        Args:
            db_service: Database service instance (defaults to singleton)
        """
        self.db_service = db_service if db_service is not None else get_database_service()
        self._ocr_service = ocr_service

    def _get_ocr_service(self) -> IDCardOCRService:
        """Initialize Gemini OCR only when the image flow needs it."""
        if self._ocr_service is None:
            self._ocr_service = get_ocr_service()
        return self._ocr_service

    @staticmethod
    def _failure(error: str, error_code: str) -> Dict[str, Any]:
        """Build a fail-closed result that can never be interpreted as safe."""
        return {
            "success": False,
            "error": error,
            "error_code": error_code,
            "is_valid_format": False,
            "is_blacklisted": False,
            "is_safe": False,
            "reports_count": 0,
            "risk_level": "UNKNOWN",
        }

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

            if self.db_service is None:
                return {
                    "is_blacklisted": False,
                    "error": "Blacklist service unavailable",
                    "error_code": BLACKLIST_UNAVAILABLE,
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

        except Exception as exc:
            logger.error("ID blacklist lookup failed (%s)", type(exc).__name__)
            return {
                "is_blacklisted": False,
                "error": "Blacklist service unavailable",
                "error_code": BLACKLIST_UNAVAILABLE,
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
        # Step 1: Extract data from image using OCR. Model creation stays lazy so
        # the number-only flow never requires Gemini configuration.
        logger.info("Starting ID card OCR extraction")
        try:
            ocr_service = self._get_ocr_service()
            ocr_result = ocr_service.extract_id_card_data(image_base64)
        except Exception as exc:
            logger.error("ID card OCR initialization failed (%s)", type(exc).__name__)
            return self._failure("OCR service unavailable", OCR_UNAVAILABLE)

        if not ocr_result.get("success"):
            error_code = ocr_result.get("error_code", "ocr_failed")
            error = ocr_result.get("error", "Could not read ID card image")
            logger.warning("ID card OCR did not produce a usable result (%s)", error_code)
            return self._failure(error, error_code)

        id_number = normalize_thai_id(ocr_result.get("id_number", ""))

        if len(id_number) != 13:
            return self._failure("Could not extract a 13-digit ID number", "ocr_failed")

        ocr_result = {**ocr_result, "id_number": id_number}
        logger.info("ID card OCR succeeded for %s", _mask_id(id_number))

        # Step 2: Validate format using checksum
        is_valid_format = validate_thai_id(id_number)
        logger.info("ID checksum validation: %s", "valid" if is_valid_format else "invalid")

        # Step 3: Check blacklist
        logger.info("Checking ID fraud blacklist")
        blacklist_result = self.check_id_blacklist(id_number)
        if blacklist_result.get("error"):
            return self._failure(
                "Blacklist service unavailable",
                BLACKLIST_UNAVAILABLE,
            )

        is_blacklisted = blacklist_result.get("is_blacklisted", False)

        # Calculate risk level and build response
        if is_blacklisted:
            details = blacklist_result.get("details", {})
            report_count = details.get("report_count", 1)

            risk_level = _risk_level_for_reports(report_count)

            logger.warning("ID is blacklisted: %s reports, risk %s", report_count, risk_level)

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
            logger.info("ID not found in blacklist; risk %s", risk_level)

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
        clean_id = normalize_thai_id(id_number)
        logger.info("Verifying ID number %s", _mask_id(clean_id))

        if len(clean_id) != 13:
            return self._failure("ID number must contain 13 digits", "invalid_id")

        # Validate format
        is_valid_format = validate_thai_id(clean_id)
        logger.info("ID checksum validation: %s", "valid" if is_valid_format else "invalid")

        # Check blacklist
        logger.info("Checking ID fraud blacklist")
        blacklist_result = self.check_id_blacklist(clean_id)

        if blacklist_result.get("error"):
            return self._failure(
                "Blacklist service unavailable",
                BLACKLIST_UNAVAILABLE,
            )

        is_blacklisted = blacklist_result.get("is_blacklisted", False)
        blacklist_details = blacklist_result.get("details", {})
        reports_count = blacklist_details.get("report_count", 1 if is_blacklisted else 0)
        category = blacklist_details.get("category")
        last_reported = blacklist_details.get("last_reported")

        # Determine risk level
        if is_blacklisted:
            risk_level = _risk_level_for_reports(reports_count)
            logger.warning("ID is blacklisted: %s reports, risk %s", reports_count, risk_level)
        else:
            risk_level = "LOW" if is_valid_format else "MEDIUM"
            logger.info("ID not found in blacklist; risk %s", risk_level)

        # Overall safety
        is_safe = is_valid_format and not is_blacklisted

        return {
            "success": True,
            "id_number": clean_id,
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
