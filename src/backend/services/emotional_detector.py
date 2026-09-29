"""Emotional Manipulation Detector for enhanced fraud analysis.

Detects emotional manipulation tactics used in scam messages:
- Urgency tactics
- Fear tactics
- Greed tactics
- False authority
"""

from typing import Dict, List, Any
import re


class EmotionalManipulationDetector:
    """Detects emotional manipulation tactics in text messages."""

    # Urgency keywords (Thai + English)
    URGENCY_KEYWORDS = [
        # Thai
        "ด่วน", "เร่งด่วน", "ทันที", "โอนเลย", "รีบ", "เหลือเวลา",
        "วันนี้เท่านั้น", "โอกาสสุดท้าย", "ก่อน", "หมดเวลา",
        "ภายใน", "ชม.", "นาที", "limited", "จำกัด", "สิ้นสุด",

        # English
        "urgent", "hurry", "now", "immediately", "asap", "quick",
        "limited time", "today only", "last chance", "expires",
        "deadline", "don't wait", "act now"
    ]

    # Fear tactics keywords
    FEAR_KEYWORDS = [
        # Thai - Account/System threats
        "บัญชีถูกระงับ", "บัญชีถูกปิด", "บัญชีจะโดน", "ระงับ", "โดนปิด",
        "ถูกแบน", "โดนแบน", "หยุดการใช้งาน", "ระบบตรวจพบ",

        # Thai - Legal/Authority threats
        "จะโดนฟ้อง", "โดนจับ", "ผิดกฎหมาย", "คดี", "ตำรวจ",
        "โดนปรับ", "จะเสียค่าปรับ", "เสียหาย", "พัวพัน",

        # Thai - Loss threats
        "จะเสียเงิน", "สูญเสีย", "พลาดโอกาส", "หมดสิทธิ์",
        "ไม่รับผิดชอบ", "เสี่ยง", "อันตราย",

        # English
        "suspended", "banned", "blocked", "terminated", "freeze",
        "illegal", "lawsuit", "police", "arrested", "penalty",
        "lose", "loss", "risk", "danger", "miss out"
    ]

    # Greed tactics keywords
    GREED_KEYWORDS = [
        # Thai - Money promises
        "รับเงินฟรี", "แจกเงิน", "แจกฟรี", "ได้เงิน", "โบนัส",
        "รับประกันกำไร", "กำไรแน่นอน", "รวยเร็ว", "รวยง่าย",
        "ทำเงิน", "รายได้", "passive income",

        # Thai - Percentage/ROI
        "%", "เท่า", "คูณ", "ROI", "ผลตอบแทน", "ดอกเบี้ย",
        "รับคืน", "ได้กลับ",

        # Thai - Easy money
        "ง่ายมาก", "ไม่ยาก", "ทำเองได้", "ที่บ้าน", "นอนรับเงิน",
        "คลิกรับ", "กดรับ",

        # English
        "free money", "bonus", "guaranteed profit", "get rich",
        "easy money", "passive income", "work from home",
        "100%", "no risk", "risk-free"
    ]

    # False authority keywords
    AUTHORITY_KEYWORDS = [
        # Thai - Official titles
        "เจ้าหน้าที่", "ตำรวจ", "ทหาร", "ข้าราชการ",
        "จากธนาคาร", "จากรัฐบาล", "จากสรรพากร",
        "ไปรษณีย์", "ศาล", "DSI", "ปปง", "กรมสรรพากร",

        # Thai - Professional titles
        "ผู้เชี่ยวชาญ", "ที่ปรึกษา", "นักวิเคราะห์", "โค้ช",
        "ผู้จัดการ", "ผู้อำนวยการ",

        # Thai - Authority claims
        "ขอความร่วมมือ", "ตามกฎหมาย", "ตามระเบียบ",
        "แจ้งเตือน", "แจ้งจากทางการ", "ประกาศ",

        # English
        "officer", "police", "authority", "government",
        "bank official", "tax office", "court",
        "expert", "advisor", "manager", "director",
        "official", "notification", "announcement"
    ]

    def detect_urgency(self, text: str) -> Dict[str, Any]:
        """
        Detect urgency tactics in text.

        Returns:
            {
                "detected": bool,
                "count": int,
                "severity": "low" | "medium" | "high",
                "examples": [str]
            }
        """
        text_lower = text.lower()
        found_keywords = []

        for keyword in self.URGENCY_KEYWORDS:
            if keyword.lower() in text_lower:
                # Find actual occurrence in original text
                pattern = re.compile(re.escape(keyword), re.IGNORECASE)
                matches = pattern.findall(text)
                found_keywords.extend(matches)

        count = len(found_keywords)

        # Determine severity
        severity = "low"
        if count >= 5:
            severity = "high"
        elif count >= 3:
            severity = "medium"

        return {
            "detected": count > 0,
            "count": count,
            "severity": severity,
            "examples": list(set(found_keywords))[:5]  # Max 5 unique examples
        }

    def detect_fear(self, text: str) -> Dict[str, Any]:
        """Detect fear tactics in text."""
        text_lower = text.lower()
        found_keywords = []

        for keyword in self.FEAR_KEYWORDS:
            if keyword.lower() in text_lower:
                pattern = re.compile(re.escape(keyword), re.IGNORECASE)
                matches = pattern.findall(text)
                found_keywords.extend(matches)

        count = len(found_keywords)

        severity = "low"
        if count >= 4:
            severity = "high"
        elif count >= 2:
            severity = "medium"

        return {
            "detected": count > 0,
            "count": count,
            "severity": severity,
            "examples": list(set(found_keywords))[:5]
        }

    def detect_greed(self, text: str) -> Dict[str, Any]:
        """Detect greed exploitation tactics in text."""
        text_lower = text.lower()
        found_keywords = []

        for keyword in self.GREED_KEYWORDS:
            if keyword.lower() in text_lower:
                pattern = re.compile(re.escape(keyword), re.IGNORECASE)
                matches = pattern.findall(text)
                found_keywords.extend(matches)

        count = len(found_keywords)

        severity = "low"
        if count >= 5:
            severity = "high"
        elif count >= 3:
            severity = "medium"

        return {
            "detected": count > 0,
            "count": count,
            "severity": severity,
            "examples": list(set(found_keywords))[:5]
        }

    def detect_authority(self, text: str) -> Dict[str, Any]:
        """Detect false authority claims in text."""
        text_lower = text.lower()
        found_keywords = []

        for keyword in self.AUTHORITY_KEYWORDS:
            if keyword.lower() in text_lower:
                pattern = re.compile(re.escape(keyword), re.IGNORECASE)
                matches = pattern.findall(text)
                found_keywords.extend(matches)

        count = len(found_keywords)

        severity = "low"
        if count >= 3:
            severity = "high"
        elif count >= 2:
            severity = "medium"

        return {
            "detected": count > 0,
            "count": count,
            "severity": severity,
            "examples": list(set(found_keywords))[:5]
        }

    def analyze_all(self, text: str) -> Dict[str, Any]:
        """
        Analyze text for all emotional manipulation tactics.

        Returns:
            {
                "detected": bool,
                "tactics": ["urgency", "fear", ...],
                "details": {
                    "urgency": {...},
                    "fear": {...},
                    "greed": {...},
                    "authority": {...}
                },
                "total_tactics": int,
                "severity": "low" | "medium" | "high"
            }
        """
        urgency = self.detect_urgency(text)
        fear = self.detect_fear(text)
        greed = self.detect_greed(text)
        authority = self.detect_authority(text)

        # Determine which tactics were detected
        tactics_detected = []
        if urgency["detected"]:
            tactics_detected.append("urgency")
        if fear["detected"]:
            tactics_detected.append("fear")
        if greed["detected"]:
            tactics_detected.append("greed")
        if authority["detected"]:
            tactics_detected.append("authority")

        # Overall severity
        high_count = sum([
            urgency["severity"] == "high",
            fear["severity"] == "high",
            greed["severity"] == "high",
            authority["severity"] == "high"
        ])

        medium_count = sum([
            urgency["severity"] == "medium",
            fear["severity"] == "medium",
            greed["severity"] == "medium",
            authority["severity"] == "medium"
        ])

        overall_severity = "low"
        if high_count >= 2 or (high_count >= 1 and medium_count >= 2):
            overall_severity = "high"
        elif high_count >= 1 or medium_count >= 2:
            overall_severity = "medium"

        return {
            "detected": len(tactics_detected) > 0,
            "tactics": tactics_detected,
            "details": {
                "urgency": urgency,
                "fear": fear,
                "greed": greed,
                "authority": authority
            },
            "total_tactics": len(tactics_detected),
            "severity": overall_severity
        }


# Singleton instance
_detector_instance = None


def get_emotional_detector() -> EmotionalManipulationDetector:
    """Get or create singleton emotional manipulation detector."""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = EmotionalManipulationDetector()
    return _detector_instance
