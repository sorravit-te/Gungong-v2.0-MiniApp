"""Pydantic models for request/response validation and database models."""

from pydantic import BaseModel, Field
from typing import Literal, Optional, List, Dict, Any
from datetime import datetime

# Fraud classification types
FraudClassification = Literal["FRAUD_GAMBLING_AD", "SCAM_MALICIOUS_INVITE", "SAFE_NORMAL"]


class FraudCheckRequest(BaseModel):
    """Request model for fraud detection API."""

    message: str = Field(..., min_length=1, description="Message text to check for fraud")
    user_id: Optional[str] = Field(None, description="User ID (e.g., LINE User ID) for history tracking")


class FraudCheckResponse(BaseModel):
    """Response model for fraud detection API."""

    classification: FraudClassification = Field(..., description="Fraud classification result")
    is_fraud: bool = Field(..., description="Whether the message is fraudulent")
    is_safe: bool = Field(..., description="Whether the message is safe")
    message_length: int = Field(..., description="Length of the analyzed message")
    model: str = Field(..., description="AI model used for classification")
    timestamp: datetime = Field(default_factory=datetime.now, description="When the check was performed")


class LINEMessageEvent(BaseModel):
    """Simplified LINE message event model."""

    reply_token: str = Field(..., description="Token for replying to the message")
    user_id: str = Field(..., description="LINE user ID")
    message_text: str = Field(..., description="Message text from user")
    timestamp: int = Field(..., description="Event timestamp")


class LINEWebhookRequest(BaseModel):
    """LINE Webhook request model."""

    events: List[Dict[str, Any]] = Field(default_factory=list, description="List of LINE events")
    destination: Optional[str] = Field(None, description="Bot's user ID")


class HealthCheckResponse(BaseModel):
    """Health check response model."""

    status: str = Field(default="healthy", description="Service status")
    app_name: str = Field(..., description="Application name")
    timestamp: datetime = Field(default_factory=datetime.now, description="Current server time")


# ==================== Firestore Collection Names ====================
# These are just constants to ensure consistency
COLLECTION_FRAUD_CHECK_CACHE = "fraud_check_cache"
COLLECTION_GAMBLING_DOMAINS = "gambling_domains"
COLLECTION_URL_REPUTATION = "url_reputation_cache"
COLLECTION_FRAUD_MESSAGES = "fraud_messages"
COLLECTION_FEEDBACK_LOGS = "feedback_logs"
COLLECTION_WHITELISTED_DOMAINS = "whitelisted_domains"
COLLECTION_BLACKLIST_BANK_ACCOUNTS = "blacklist_bank_accounts"
COLLECTION_BLACKLIST_PHONE_NUMBERS = "blacklist_phone_numbers"
COLLECTION_BLACKLIST_ID_CARDS = "blacklist_id_cards"
COLLECTION_HISTORY = "fraud_check_history"


# ==================== ID Card Verification Models ====================


class IDCardVerificationRequest(BaseModel):
    """Request model for Thai ID card verification."""

    image_base64: str = Field(..., description="Base64 encoded ID card image (JPEG/PNG)")
    user_id: Optional[str] = Field(None, description="User ID for tracking")


class IDCardData(BaseModel):
    """Extracted ID card data from OCR."""

    id_number: str = Field(..., description="13-digit Thai ID number")
    name_th: Optional[str] = Field(None, description="Thai first name")
    surname_th: Optional[str] = Field(None, description="Thai surname")
    date_of_birth: Optional[str] = Field(None, description="Date of birth")
    address: Optional[str] = Field(None, description="Address on card")
    issue_date: Optional[str] = Field(None, description="Card issue date")
    expiry_date: Optional[str] = Field(None, description="Card expiry date")


class IDCardVerificationResponse(BaseModel):
    """Response model for ID card verification."""

    id_number: str = Field(..., description="Thai ID number")
    is_valid_format: bool = Field(..., description="Whether ID format/checksum is valid")
    is_blacklisted: bool = Field(..., description="Whether ID is blacklisted")
    is_safe: bool = Field(..., description="Whether ID is safe")
    reports_count: int = Field(..., description="Number of fraud reports")
    risk_level: str = Field(..., description="Risk level: LOW, MEDIUM, HIGH, CRITICAL")
    extracted_data: Optional[IDCardData] = Field(None, description="Extracted card data")
    category: Optional[str] = Field(None, description="Fraud category if blacklisted")
    timestamp: datetime = Field(default_factory=datetime.now, description="Verification timestamp")