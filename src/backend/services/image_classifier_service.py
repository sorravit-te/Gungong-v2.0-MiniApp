"""Image Classification Service using Google Gemini Vision.

Classifies images to determine their type before processing.
"""

import google.generativeai as genai
from PIL import Image
import base64
import io
import json
import re
from typing import Dict, Any, Literal

from ..core.config import settings


ImageType = Literal["id_card", "qr_code", "general"]


class ImageClassifierService:
    """Service for classifying image types using Gemini Vision."""

    def __init__(self):
        """Initialize Gemini Vision model."""
        genai.configure(api_key=settings.google_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)

    def classify_image(self, image_base64: str) -> Dict[str, Any]:
        """
        Classify image type using Gemini Vision.

        Args:
            image_base64: Base64 encoded image (with or without data URI prefix)

        Returns:
            Dictionary containing:
            - image_type: "id_card" | "qr_code" | "general"
            - confidence: float (0-1)
            - description: str - Brief description of the image
            - qr_url: str | None - Extracted URL if QR code detected
            - success: bool

        Examples:
            >>> classifier = ImageClassifierService()
            >>> result = classifier.classify_image(base64_image)
            >>> print(result['image_type'])
            "id_card"
        """
        try:
            # Remove data URI prefix if present
            if ',' in image_base64 and image_base64.startswith('data:'):
                image_base64 = image_base64.split(',')[1]

            # Decode base64 image
            image_data = base64.b64decode(image_base64)
            image = Image.open(io.BytesIO(image_data))

            # Gemini Vision prompt for classification
            prompt = """วิเคราะห์ภาพนี้และจำแนกประเภทของภาพ

คุณต้องระบุประเภทของภาพเป็น 1 ใน 3 ประเภทต่อไปนี้:

1. **id_card** - บัตรประจำตัวประชาชนไทย
   - ต้องเป็นบัตรประชาชนไทยเท่านั้น (มีตราครุฑ, เลข 13 หลัก)
   - ไม่ใช่บัตรอื่นๆ เช่น ใบขับขี่, บัตรนักศึกษา, บัตรเครดิต

2. **qr_code** - ภาพที่มี QR Code
   - มี QR Code อยู่ในภาพ (ไม่ว่าจะมีเนื้อหาอื่นด้วยหรือไม่)
   - ถ้าเป็น QR Code ให้พยายามอ่านและส่ง URL/ข้อความที่ซ่อนอยู่ใน QR Code ด้วย
   - ตัวอย่าง: QR Code ชำระเงิน, QR Code โปรโมชั่น, QR Code ลิงก์

3. **general** - ภาพทั่วไป
   - รูปถ่ายทั่วไป เช่น คน, สัตว์, ทิวทัศน์, อาหาร, สิ่งของ
   - ภาพที่ไม่ใช่บัตรประชาชนและไม่มี QR Code

ตอบกลับเป็น JSON ในรูปแบบนี้:
{
    "image_type": "id_card" | "qr_code" | "general",
    "confidence": 0.95,
    "description": "คำอธิบายสั้นๆ ว่าภาพนี้คืออะไร (ภาษาไทย)",
    "qr_url": "URL หรือข้อความที่อ่านได้จาก QR Code (ถ้ามี) หรือ null"
}

กฎสำคัญ:
- ถ้าไม่แน่ใจว่าเป็นบัตรประชาชนให้เลือก "general"
- confidence ควรเป็น 0.9+ สำหรับ id_card และ qr_code, น้อยกว่านั้นให้เลือก general
- ถ้ามี QR Code ให้พยายามอ่านและแปลงเป็น URL/text ใน qr_url field

ตอบกลับเฉพาะ JSON object เท่านั้น:
"""

            # Generate content with image
            response = self.model.generate_content([prompt, image])

            # Parse JSON response
            text = response.text.strip()

            # Remove markdown code blocks if present
            text = re.sub(r'^```json\s*', '', text)
            text = re.sub(r'\s*```$', '', text)

            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', text)

            if json_match:
                data = json.loads(json_match.group(0))

                # Validate image_type
                image_type = data.get("image_type", "general")
                if image_type not in ["id_card", "qr_code", "general"]:
                    image_type = "general"

                print(f"[CLASSIFY] Image classified as: {image_type} "
                      f"(confidence: {data.get('confidence', 0):.2f})")

                return {
                    "success": True,
                    "image_type": image_type,
                    "confidence": data.get("confidence", 0.5),
                    "description": data.get("description", ""),
                    "qr_url": data.get("qr_url")
                }
            else:
                print("[ERROR] Could not parse classification response")
                return {
                    "success": False,
                    "image_type": "general",
                    "confidence": 0,
                    "description": "Could not classify image",
                    "qr_url": None,
                    "error": "Failed to parse response"
                }

        except Exception as e:
            print(f"[ERROR] Image classification failed: {e}")
            return {
                "success": False,
                "image_type": "general",
                "confidence": 0,
                "description": "Classification error",
                "qr_url": None,
                "error": str(e)
            }


# Singleton instance
_classifier_service = None


def get_image_classifier_service() -> ImageClassifierService:
    """Get singleton instance of ImageClassifierService."""
    global _classifier_service
    if _classifier_service is None:
        _classifier_service = ImageClassifierService()
    return _classifier_service
