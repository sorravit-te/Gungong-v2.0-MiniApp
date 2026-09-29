"""Conversation Analyzer Service for detecting manipulation tactics in conversations.

This service analyzes full conversations (not just single messages) to detect:
- Manipulation tactics (urgency, fear, greed, false authority)
- Timeline of manipulation events
- Behavioral predictions (what scammer will do next)
- Overall manipulation score
"""

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from typing import Dict, Any, List, Optional
import json
import re
import asyncio
from datetime import datetime
from ..core.config import settings


# Enhanced prompt for conversation analysis
CONVERSATION_ANALYSIS_PROMPT = """
**System/Instruction:**
You are "Gun Gong" (กันโกง), an expert fraud detection analyst specializing in conversation analysis.

Your task is to analyze an ENTIRE CONVERSATION between two or more people to detect scam patterns and manipulation tactics.

**IMPORTANT CONTEXT:**
- This is a full conversation, not a single message
- Look for patterns across multiple messages
- Pay attention to the TIMELINE of events
- Identify how manipulation escalates over time

---

**MANIPULATION TACTICS TO DETECT:**

1. **URGENCY CREATION** (เร่งให้เร็ว)
   - Creates artificial time pressure
   - "ต้องตัดสินใจวันนี้", "เหลือเวลา 24 ชม.", "โอกาสสุดท้าย", "ด่วนมาก"
   - Forces quick decisions without time to think

2. **FEAR TACTICS** (ข่มขู่)
   - Threatens negative consequences
   - "บัญชีจะถูกปิด", "จะโดนฟ้อง", "จะเสียเงิน", "จะพลาดโอกาส"
   - Creates anxiety and panic

3. **GREED EXPLOITATION** (ใช้ความโลภ)
   - Promises unrealistic gains
   - "รับประกันกำไร", "รวยภายใน 30 วัน", "รับเงินฟรี", "โบนัส 100%"
   - Too good to be true offers

4. **FALSE AUTHORITY** (ปลอมตัว)
   - Claims to be someone important
   - "เจ้าหน้าที่ธนาคาร", "ตำรวจ", "ผู้เชี่ยวชาญ", "ที่ปรึกษาการเงิน"
   - Uses authority to gain trust

5. **EMOTIONAL MANIPULATION** (เล่นอารมณ์)
   - Appeals to emotions
   - "ช่วยเหลือครอบครัว", "เพื่อนกู", "คนดี", "น่าสงสาร"
   - Builds emotional connection

6. **INFORMATION FISHING** (ล่อข้อมูล)
   - Asks for personal/financial information
   - "ขอเลขบัญชี", "รหัสผ่าน", "OTP", "บัตรประชาชน"
   - Collecting sensitive data

7. **AVOIDANCE PATTERNS** (หลีกเลี่ยง)
   - Avoids video calls, meetings, verification
   - "กล้องเสีย", "ยุ่งมาก", "ไม่สะดวก", "ไว้ภายหลัง"
   - Refuses to prove identity

8. **STORY INCONSISTENCIES** (เรื่องเล่าไม่ตรง)
   - Details change over time
   - Location, job, emergency story changes
   - Contradictions in timeline

---

**COMMON SCAM PATTERNS:**

- **Investment Scam**: Guaranteed profit + Urgency + "Expert" advice + Money request
- **Romance Scam**: Love bombing + Emergency + Money needed + Avoids meeting
- **Impersonation**: Authority claim + Threat + Urgent action + Payment/Info request
- **Loan Shark**: Fast approval + No credit check + High interest hidden
- **Prize/Lottery**: You won + Fee to claim + Urgent action + No prior entry

---

**ANALYSIS INSTRUCTIONS:**

1. **Read the ENTIRE conversation carefully**
2. **Extract Timeline**: Identify key moments when manipulation tactics appear
3. **Count Tactics**: How many times each tactic is used
4. **Assess Manipulation Score**:
   - 0-30: Low manipulation (normal conversation)
   - 31-60: Medium manipulation (some red flags)
   - 61-85: High manipulation (clear scam patterns)
   - 86-100: Very high manipulation (dangerous scam)
4. **Predict Next Move**: Based on patterns, what will scammer likely do next?
5. **Determine Risk Level**: LOW / MEDIUM / HIGH / CRITICAL

---

**SCORING FORMULA:**

Manipulation Score = (Tactics Count × 10) + (Urgency Weight × 15) + (Authority/Fear Weight × 20) + (Money Request × 25)

- Each tactic detected: +10 points
- Urgency tactics: +15 points each
- Authority/Fear tactics: +20 points each
- Direct money request: +25 points
- Story inconsistencies: +15 points
- Cap at 100

---

**OUTPUT FORMAT (JSON ONLY):**

{{
  "manipulation_score": 0-100,
  "risk_level": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
  "scam_type": "investment" | "romance" | "impersonation" | "loan" | "prize" | "other" | "none",
  "tactics_detected": [
    {{
      "tactic": "urgency" | "fear" | "greed" | "authority" | "emotional" | "fishing" | "avoidance" | "inconsistency",
      "count": <number>,
      "severity": "low" | "medium" | "high",
      "examples": ["quote from conversation", "another example"]
    }}
  ],
  "timeline": [
    {{
      "time": "message timestamp or order",
      "sender": "sender name",
      "message": "brief message content",
      "tactic": "tactic detected in this message",
      "significance": "why this moment is important"
    }}
  ],
  "predictions": [
    "Scammer will likely ask for bank account details next",
    "Another predicted action based on pattern"
  ],
  "reason_th": "สรุปสั้นๆ ภาษาไทยว่าทำไมน่าสงสัย หรือปลอดภัย",
  "confidence": 0-100
}}

---

**CONVERSATION TO ANALYZE:**

{conversation}

---

**JSON RESPONSE:**
"""


class ConversationAnalyzer:
    """
    Analyzes full conversations to detect manipulation tactics and scam patterns.

    Unlike single message detection, this service looks at:
    - Pattern evolution over time
    - Escalation of manipulation
    - Timeline of red flags
    - Behavioral predictions
    """

    def __init__(self, api_key: str | None = None, model: str | None = None):
        """
        Initialize Conversation Analyzer.

        Args:
            api_key: Google API key. If None, uses settings.google_api_key
            model: Gemini model name. If None, uses settings.gemini_model
        """
        self.api_key = api_key or settings.google_api_key
        self.model = model or settings.gemini_model

        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not found")

        # Initialize LLM
        self.llm = ChatGoogleGenerativeAI(
            model=self.model,
            temperature=0,  # Deterministic for consistency
            api_key=self.api_key,
        )

        # Create prompt template
        self.prompt = PromptTemplate(
            input_variables=["conversation"],
            template=CONVERSATION_ANALYSIS_PROMPT,
        )

    def analyze_conversation(self, conversation_text: str) -> Dict[str, Any]:
        """
        Analyze a full conversation for manipulation tactics.

        Args:
            conversation_text: Full conversation text (can be formatted in various ways)

        Returns:
            Dict with analysis results:
            {
                "manipulation_score": 0-100,
                "risk_level": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
                "scam_type": "investment" | "romance" | ...,
                "tactics_detected": [...],
                "timeline": [...],
                "predictions": [...],
                "reason_th": "...",
                "confidence": 0-100
            }

        Raises:
            Exception: If Gemini API fails or returns invalid response.
        """
        try:
            # Format prompt with conversation
            formatted_input = self.prompt.format(conversation=conversation_text)

            # Invoke Gemini
            response = self.llm.invoke(formatted_input)

            # Extract response content
            content = response.content.strip()

            # Parse JSON response
            try:
                # Extract JSON from response (handle markdown code blocks)
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    json_str = json_match.group(0)
                    result = json.loads(json_str)
                else:
                    # Fallback: try parsing entire content
                    result = json.loads(content)

                # Validate required fields
                required_fields = [
                    "manipulation_score",
                    "risk_level",
                    "scam_type",
                    "tactics_detected",
                    "timeline",
                    "predictions",
                    "reason_th",
                    "confidence"
                ]

                if not all(field in result for field in required_fields):
                    print(f"⚠️  Missing fields in response. Has: {result.keys()}")
                    # Try to fill in missing fields with defaults
                    result.setdefault("manipulation_score", 0)
                    result.setdefault("risk_level", "LOW")
                    result.setdefault("scam_type", "none")
                    result.setdefault("tactics_detected", [])
                    result.setdefault("timeline", [])
                    result.setdefault("predictions", [])
                    result.setdefault("reason_th", "ไม่สามารถวิเคราะห์ได้")
                    result.setdefault("confidence", 50)

                # Validate risk_level
                valid_risk_levels = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
                if result["risk_level"] not in valid_risk_levels:
                    print(f"⚠️  Invalid risk_level: {result['risk_level']}, defaulting to LOW")
                    result["risk_level"] = "LOW"

                return result

            except (json.JSONDecodeError, ValueError) as e:
                # JSON parsing failed - log and return default safe response
                print(f"⚠️  Failed to parse JSON response: {e}")
                print(f"Raw response (first 500 chars): {content[:500]}")

                return {
                    "manipulation_score": 0,
                    "risk_level": "LOW",
                    "scam_type": "none",
                    "tactics_detected": [],
                    "timeline": [],
                    "predictions": [],
                    "reason_th": "ไม่สามารถวิเคราะห์บทสนทนาได้ กรุณาลองใหม่",
                    "confidence": 0,
                    "error": "JSON parse error"
                }

        except Exception as e:
            raise Exception(f"Conversation analysis failed: {str(e)}")

    async def analyze_conversation_async(self, conversation_text: str) -> Dict[str, Any]:
        """
        Async version: Analyze a conversation for manipulation tactics.

        Args:
            conversation_text: Full conversation text

        Returns:
            Dict with analysis results (same as analyze_conversation)
        """
        # Run sync method in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.analyze_conversation, conversation_text)

    def extract_timeline(self, messages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Extract timeline from structured messages.

        Args:
            messages: List of message dicts with keys: time, sender, message

        Returns:
            List of timeline events with tactics detected

        Note: This is a helper method. For full analysis, use analyze_conversation()
        which includes AI-powered timeline extraction.
        """
        timeline = []

        for idx, msg in enumerate(messages):
            timeline.append({
                "time": msg.get("time", f"Message {idx + 1}"),
                "sender": msg.get("sender", "Unknown"),
                "message": msg.get("message", ""),
                "tactic": "unknown",  # Would be filled by AI analysis
                "significance": "Needs AI analysis"
            })

        return timeline

    def predict_next_move(self, tactics: List[Dict[str, Any]], scam_type: str) -> List[str]:
        """
        Predict scammer's next move based on detected tactics and scam type.

        Args:
            tactics: List of detected tactics from analyze_conversation
            scam_type: Type of scam (investment, romance, etc.)

        Returns:
            List of predicted actions

        Note: This provides rule-based predictions. The AI analysis includes
        more sophisticated predictions based on the full conversation context.
        """
        predictions = []

        # Common patterns by scam type
        scam_patterns = {
            "investment": [
                "Will ask for initial investment/deposit",
                "Will provide fake trading platform link",
                "Will show fake profit screenshots",
                "Will ask for more money to 'unlock' profits"
            ],
            "romance": [
                "Will create emergency situation needing money",
                "Will ask for gift cards or wire transfer",
                "Will avoid video calls or meetings",
                "Will ask for passport/ID photos"
            ],
            "impersonation": [
                "Will demand immediate payment to avoid penalty",
                "Will ask for OTP or password",
                "Will threaten legal action",
                "Will provide fake official links"
            ],
            "loan": [
                "Will ask for upfront processing fee",
                "Will request bank account access",
                "Will charge hidden interest rates",
                "Will trap in debt cycle"
            ],
            "prize": [
                "Will ask for 'tax' or 'processing fee'",
                "Will request bank account details",
                "Will claim prize expires soon",
                "Will ask for ID/personal information"
            ]
        }

        # Get predictions for detected scam type
        if scam_type in scam_patterns:
            predictions.extend(scam_patterns[scam_type][:2])  # Top 2 predictions

        # Add tactic-specific predictions
        tactic_names = [t.get("tactic", "") for t in tactics]

        if "urgency" in tactic_names:
            predictions.append("Will increase time pressure and urgency")

        if "authority" in tactic_names:
            predictions.append("Will use official-sounding language to intimidate")

        if "fishing" in tactic_names:
            predictions.append("Will continue asking for sensitive information")

        return predictions if predictions else ["Unable to predict - need more context"]


# Singleton instance (optional, for convenience)
_analyzer_instance = None


def get_conversation_analyzer() -> ConversationAnalyzer:
    """Get or create singleton conversation analyzer instance."""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = ConversationAnalyzer()
    return _analyzer_instance
