"""Enhanced Fraud Detection Router for v2.0 - with emotional manipulation analysis.

New endpoints that extend v1.0 fraud detection with:
- Emotional manipulation detection
- Language detection
- Enhanced risk scoring
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from slowapi import Limiter
from slowapi.util import get_remote_address
from datetime import datetime

from ..services.gemini_service import get_fraud_detector
from ..services.emotional_detector import get_emotional_detector
from ..services.database_service import get_database_service
from ..core.logger import get_logger

# Initialize router with v2 prefix
router = APIRouter(prefix="/api/v2", tags=["Fraud Detection v2"])
limiter = Limiter(key_func=get_remote_address)
logger = get_logger(__name__)


# ==================== Request/Response Models ====================

class EnhancedFraudCheckRequest(BaseModel):
    """Request model for enhanced fraud checking."""

    message: str = Field(..., min_length=1, description="Message text to analyze")
    user_id: Optional[str] = Field(None, description="User ID for history tracking")
    detect_emotions: bool = Field(default=True, description="Enable emotional manipulation detection")


class EmotionalManipulation(BaseModel):
    """Model for emotional manipulation analysis."""

    detected: bool = Field(..., description="Whether manipulation was detected")
    tactics: List[str] = Field(default_factory=list, description="List of tactics detected (urgency, fear, greed, authority)")
    details: Dict[str, Any] = Field(default_factory=dict, description="Detailed analysis for each tactic")
    severity: str = Field(..., description="Overall severity: low, medium, high")


class EnhancedFraudCheckResponse(BaseModel):
    """Response model for enhanced fraud checking."""

    # Original fraud detection fields
    category: str = Field(..., description="Fraud category")
    risk_level: str = Field(..., description="Risk level: Low, Medium, High")
    confidence_score: int = Field(..., ge=0, le=100, description="Confidence score (0-100)")
    reason_th: str = Field(..., description="Thai explanation")
    keywords_found: List[str] = Field(default_factory=list, description="Detected keywords")
    is_fraud: bool = Field(..., description="Whether message is fraudulent")

    # v2.0 enhancements
    emotional_manipulation: Optional[EmotionalManipulation] = Field(None, description="Emotional manipulation analysis")
    language: Optional[str] = Field(None, description="Detected language (th, en, etc.)")

    # Metadata
    cached: bool = Field(default=False, description="Whether result was from cache")
    timestamp: datetime = Field(default_factory=datetime.now, description="When check was performed")


# ==================== Endpoints ====================

@router.post("/check-message-enhanced", response_model=EnhancedFraudCheckResponse)
@limiter.limit("10/minute")
async def check_message_enhanced(http_request: Request, request: EnhancedFraudCheckRequest):
    """
    Enhanced fraud detection with emotional manipulation analysis.

    **Features:**
    - Traditional fraud detection (categories, keywords, AI analysis)
    - **NEW:** Emotional manipulation tactics detection
    - **NEW:** Language detection
    - **NEW:** Severity scoring based on tactics

    **Emotional Manipulation Tactics Detected:**
    1. **Urgency**: "ด่วน", "limited time", "today only"
    2. **Fear**: "บัญชีถูกระงับ", "suspended", "will lose"
    3. **Greed**: "รับเงินฟรี", "guaranteed profit", "free money"
    4. **Authority**: "เจ้าหน้าที่", "officer", "from bank"

    **Input:**
    - message: Text to analyze
    - user_id: Optional user identifier
    - detect_emotions: Enable/disable emotional analysis (default: true)

    **Output:**
    - All standard fraud detection fields
    - emotional_manipulation: Detailed tactics analysis
    - language: Detected language code

    **Example:**
    ```json
    POST /api/v2/check-message-enhanced
    {
        "message": "ด่วน! บัญชีของคุณถูกระงับ โอนเงินทันทีเพื่อยืนยันตัวตน",
        "detect_emotions": true
    }

    Response:
    {
        "category": "SCAM_MALICIOUS",
        "risk_level": "High",
        "confidence_score": 95,
        "emotional_manipulation": {
            "detected": true,
            "tactics": ["urgency", "fear", "authority"],
            "severity": "high"
        },
        "language": "th"
    }
    ```
    """
    try:
        # Check cache first
        db_service = get_database_service()
        cached_result = None

        if db_service:
            cached_result = db_service.get_cached_result(request.message)

            if cached_result and "emotional_manipulation" in cached_result:
                logger.info(f"✅ Cache HIT for enhanced fraud check")

                # Return cached result
                return EnhancedFraudCheckResponse(
                    category=cached_result.get("category", "SAFE_NORMAL"),
                    risk_level=cached_result.get("risk_level", "Low"),
                    confidence_score=cached_result.get("confidence_score", 50),
                    reason_th=cached_result.get("reason_th", ""),
                    keywords_found=cached_result.get("keywords_found", []),
                    is_fraud=cached_result.get("is_fraud", False),
                    emotional_manipulation=cached_result.get("emotional_manipulation"),
                    language=cached_result.get("language"),
                    cached=True,
                    timestamp=datetime.now()
                )

        logger.info(f"❌ Cache MISS - analyzing with AI + emotional detection")

        # 1. Basic fraud detection with AI
        detector = get_fraud_detector()
        fraud_result = await detector.classify_with_details_async(request.message)

        # 2. Emotional manipulation detection
        emotional_result = None
        if request.detect_emotions:
            emotional_detector = get_emotional_detector()
            emotional_analysis = emotional_detector.analyze_all(request.message)

            emotional_result = EmotionalManipulation(
                detected=emotional_analysis["detected"],
                tactics=emotional_analysis["tactics"],
                details=emotional_analysis["details"],
                severity=emotional_analysis["severity"]
            )

        # 3. Language detection
        detected_language = None
        try:
            from langdetect import detect
            detected_language = detect(request.message)
        except Exception as lang_error:
            logger.warning(f"Language detection failed: {lang_error}")
            detected_language = "unknown"

        # 4. Build response
        response = EnhancedFraudCheckResponse(
            category=fraud_result.get("category", "SAFE_NORMAL"),
            risk_level=fraud_result.get("risk_level", "Low"),
            confidence_score=fraud_result.get("confidence_score", 50),
            reason_th=fraud_result.get("reason_th", ""),
            keywords_found=fraud_result.get("keywords_found", []),
            is_fraud=fraud_result.get("is_fraud", False),
            emotional_manipulation=emotional_result,
            language=detected_language,
            cached=False,
            timestamp=datetime.now()
        )

        # 5. Save to cache
        if db_service:
            cache_data = {
                "category": response.category,
                "risk_level": response.risk_level,
                "confidence_score": response.confidence_score,
                "reason_th": response.reason_th,
                "keywords_found": response.keywords_found,
                "is_fraud": response.is_fraud,
                "emotional_manipulation": emotional_result.dict() if emotional_result else None,
                "language": detected_language
            }

            message_hash = db_service.hash_message(request.message)
            db_service.save_fraud_result(
                message_hash=message_hash,
                classification_result=cache_data,
                message_text=request.message[:500],
                url_check_result=None,
                expires_days=1  # Cache for 1 day
            )

            # Save to history if user_id provided
            if request.user_id:
                db_service.save_to_history(
                    user_id=request.user_id,
                    message_text=request.message,
                    classification=response.category,
                    is_fraud=response.is_fraud,
                    url_check_result=None
                )

        return response

    except Exception as e:
        logger.error(f"❌ Enhanced fraud check failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Enhanced fraud check failed: {str(e)}"
        )


# Export router
__all__ = ["router"]
