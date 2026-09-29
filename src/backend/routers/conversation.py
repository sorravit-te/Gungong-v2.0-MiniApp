"""Conversation Analysis Router - v2.0 API endpoints.

Provides endpoints for analyzing full conversations to detect manipulation tactics.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import re
from datetime import datetime
import io

from ..services.conversation_analyzer_service import get_conversation_analyzer
from ..services.database_service import DatabaseService

# Initialize router
router = APIRouter(prefix="/api/v2", tags=["Conversation Analysis"])

# Initialize services
conversation_analyzer = get_conversation_analyzer()
db_service = DatabaseService()


# ==================== Request/Response Models ====================

class ConversationAnalysisRequest(BaseModel):
    """Request model for conversation analysis."""

    conversation_text: str = Field(..., min_length=10, description="Full conversation text to analyze")
    user_id: Optional[str] = Field(None, description="User ID for history tracking")


class TacticDetected(BaseModel):
    """Model for a detected manipulation tactic."""

    tactic: str = Field(..., description="Type of tactic (urgency, fear, greed, etc.)")
    count: int = Field(..., description="Number of times this tactic was used")
    severity: str = Field(..., description="Severity level (low, medium, high)")
    examples: List[str] = Field(default_factory=list, description="Example quotes from conversation")


class TimelineEvent(BaseModel):
    """Model for a timeline event in the conversation."""

    time: str = Field(..., description="Timestamp or message order")
    sender: str = Field(..., description="Who sent the message")
    message: str = Field(..., description="Brief message content")
    tactic: str = Field(..., description="Tactic detected in this message")
    significance: str = Field(..., description="Why this moment is important")


class ConversationAnalysisResponse(BaseModel):
    """Response model for conversation analysis."""

    manipulation_score: int = Field(..., ge=0, le=100, description="Overall manipulation score (0-100)")
    risk_level: str = Field(..., description="Risk level: LOW, MEDIUM, HIGH, CRITICAL")
    scam_type: str = Field(..., description="Detected scam type (investment, romance, impersonation, etc.)")
    tactics_detected: List[TacticDetected] = Field(default_factory=list, description="List of detected manipulation tactics")
    timeline: List[TimelineEvent] = Field(default_factory=list, description="Timeline of manipulation events")
    predictions: List[str] = Field(default_factory=list, description="Predicted next scammer moves")
    reason_th: str = Field(..., description="Thai explanation of the analysis")
    confidence: int = Field(..., ge=0, le=100, description="Confidence in the analysis (0-100)")
    cached: bool = Field(default=False, description="Whether result was from cache")
    timestamp: datetime = Field(default_factory=datetime.now, description="When analysis was performed")


# ==================== Helper Functions ====================

def parse_conversation_file(content: str, file_format: str = "auto") -> str:
    """
    Parse conversation file content into standardized format.

    Supports:
    - LINE export: [2024-01-06 10:00] Username: message
    - WhatsApp export: [10:00, 06/01/2024] Username: message
    - CSV: timestamp,sender,message
    - JSON: [{"time": "...", "sender": "...", "text": "..."}]
    - Plain text: Any format

    Args:
        content: Raw file content
        file_format: Format hint (auto, line, whatsapp, csv, json, txt)

    Returns:
        Standardized conversation text
    """
    # Auto-detect format if not specified
    if file_format == "auto":
        if content.strip().startswith("[{"):
            file_format = "json"
        elif "," in content and "\n" in content:
            # Check if it looks like CSV
            first_line = content.split("\n")[0]
            if first_line.count(",") >= 2:
                file_format = "csv"
        elif re.search(r'\[\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\]', content):
            file_format = "line"
        elif re.search(r'\[\d{2}:\d{2},\s+\d{2}/\d{2}/\d{4}\]', content):
            file_format = "whatsapp"
        else:
            file_format = "txt"

    # Parse based on format
    if file_format == "line":
        # LINE format: [2024-01-06 10:00] Username: message
        # Already in good format, just return
        return content

    elif file_format == "whatsapp":
        # WhatsApp format: [10:00, 06/01/2024] Username: message
        # Convert to LINE format
        lines = content.split("\n")
        converted = []
        for line in lines:
            match = re.match(r'\[(\d{2}:\d{2}),\s+(\d{2}/\d{2}/\d{4})\]\s+([^:]+):\s+(.*)', line)
            if match:
                time, date, username, message = match.groups()
                # Convert date format
                day, month, year = date.split("/")
                converted_line = f"[{year}-{month}-{day} {time}] {username}: {message}"
                converted.append(converted_line)
            else:
                converted.append(line)
        return "\n".join(converted)

    elif file_format == "csv":
        # CSV format: timestamp,sender,message
        import csv
        lines = content.split("\n")
        reader = csv.reader(lines)
        converted = []
        for row in reader:
            if len(row) >= 3:
                timestamp, sender, message = row[0], row[1], row[2]
                converted.append(f"[{timestamp}] {sender}: {message}")
        return "\n".join(converted)

    elif file_format == "json":
        # JSON format: [{"time": "...", "sender": "...", "text": "..."}]
        import json
        try:
            messages = json.loads(content)
            converted = []
            for msg in messages:
                time = msg.get("time", msg.get("timestamp", "Unknown time"))
                sender = msg.get("sender", msg.get("from", msg.get("user", "Unknown")))
                text = msg.get("text", msg.get("message", msg.get("content", "")))
                converted.append(f"[{time}] {sender}: {text}")
            return "\n".join(converted)
        except json.JSONDecodeError:
            # If JSON parsing fails, treat as plain text
            return content

    else:  # txt or unknown
        # Plain text - return as-is
        return content


# ==================== Endpoints ====================

@router.post("/analyze-conversation", response_model=ConversationAnalysisResponse)
async def analyze_conversation(request: ConversationAnalysisRequest):
    """
    Analyze a full conversation for manipulation tactics and scam patterns.

    **Features:**
    - Detects manipulation tactics (urgency, fear, greed, authority, etc.)
    - Extracts timeline of manipulation events
    - Predicts scammer's next moves
    - Calculates overall manipulation score (0-100)
    - Determines risk level (LOW, MEDIUM, HIGH, CRITICAL)

    **Input:**
    - conversation_text: Full conversation (any format)
    - user_id: Optional user identifier for history tracking

    **Output:**
    - Complete analysis with tactics, timeline, predictions
    - Risk level and manipulation score
    - Thai explanation

    **Caching:**
    - Results are cached for 7 days (same conversation = same result)
    - Cache based on SHA-256 hash of conversation text
    """
    try:
        # Check cache first
        cached_result = db_service.get_cached_result(
            request.conversation_text,
            check_expiration=True
        )

        if cached_result and "manipulation_score" in cached_result:
            print(f"✅ Cache HIT for conversation analysis")

            # Return cached result
            return ConversationAnalysisResponse(
                manipulation_score=cached_result["manipulation_score"],
                risk_level=cached_result["risk_level"],
                scam_type=cached_result.get("scam_type", "unknown"),
                tactics_detected=cached_result.get("tactics_detected", []),
                timeline=cached_result.get("timeline", []),
                predictions=cached_result.get("predictions", []),
                reason_th=cached_result.get("reason_th", ""),
                confidence=cached_result.get("confidence", 80),
                cached=True,
                timestamp=datetime.now()
            )

        # Cache miss - analyze with AI
        print(f"❌ Cache MISS - analyzing conversation with AI")

        # Perform AI analysis
        result = await conversation_analyzer.analyze_conversation_async(
            request.conversation_text
        )

        # Save to cache (7 days TTL)
        message_hash = db_service.hash_message(request.conversation_text)
        db_service.save_fraud_result(
            message_hash=message_hash,
            classification_result=result,
            message_text=request.conversation_text[:500],  # Save first 500 chars
            url_check_result=None,
            expires_days=7  # Longer cache for conversations
        )

        # Save to history if user_id provided
        if request.user_id:
            db_service.save_to_history(
                user_id=request.user_id,
                message_text=request.conversation_text[:500],
                classification=result.get("scam_type", "unknown"),
                is_fraud=result.get("risk_level") in ["HIGH", "CRITICAL"],
                url_check_result=None
            )

        return ConversationAnalysisResponse(
            manipulation_score=result["manipulation_score"],
            risk_level=result["risk_level"],
            scam_type=result["scam_type"],
            tactics_detected=result["tactics_detected"],
            timeline=result["timeline"],
            predictions=result["predictions"],
            reason_th=result["reason_th"],
            confidence=result["confidence"],
            cached=False,
            timestamp=datetime.now()
        )

    except Exception as e:
        print(f"❌ Error analyzing conversation: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze conversation: {str(e)}"
        )


@router.post("/analyze-conversation-file", response_model=ConversationAnalysisResponse)
async def analyze_conversation_file(
    file: UploadFile = File(..., description="Conversation file (txt, json, csv)"),
    user_id: Optional[str] = Form(None, description="User ID for history tracking")
):
    """
    Analyze a conversation from an uploaded file.

    **Supported Formats:**
    - **LINE export**: `[2024-01-06 10:00] Username: message`
    - **WhatsApp export**: `[10:00, 06/01/2024] Username: message`
    - **CSV**: `timestamp,sender,message`
    - **JSON**: `[{"time": "...", "sender": "...", "text": "..."}]`
    - **Plain text**: Any conversation format

    **File Size Limit:** 5 MB

    **Auto-detection:**
    - Format is automatically detected from file content
    - Falls back to plain text if format is unknown

    **Output:**
    - Same as /analyze-conversation endpoint
    """
    try:
        # Read file content
        content = await file.read()

        # Check file size (max 5 MB)
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail="File too large. Maximum size is 5 MB."
            )

        # Decode content
        try:
            text_content = content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text_content = content.decode("utf-8-sig")  # Try with BOM
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="Unable to decode file. Please use UTF-8 encoding."
                )

        # Parse file based on format
        conversation_text = parse_conversation_file(text_content, file_format="auto")

        # Validate parsed content
        if len(conversation_text.strip()) < 10:
            raise HTTPException(
                status_code=400,
                detail="Conversation too short. Please provide at least 10 characters."
            )

        # Use the same analysis logic as analyze_conversation
        request = ConversationAnalysisRequest(
            conversation_text=conversation_text,
            user_id=user_id
        )

        return await analyze_conversation(request)

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error processing file: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process file: {str(e)}"
        )


# Export router
__all__ = ["router"]
