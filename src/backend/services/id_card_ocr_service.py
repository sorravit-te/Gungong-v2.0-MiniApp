"""ID Card OCR Service using Google Gemini Vision."""

import google.generativeai as genai
from PIL import Image, UnidentifiedImageError
import base64
import binascii
import io
import json
import re
from typing import Dict, Any

from ..core.config import settings


MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 25_000_000
SUPPORTED_IMAGE_FORMATS = {"JPEG", "PNG"}


class IDCardOCRService:
    """Service for extracting data from Thai ID cards using Gemini Vision."""

    def __init__(self):
        """Initialize Gemini Vision model."""
        genai.configure(api_key=settings.google_api_key)
        # Use configured Gemini model for multimodal support
        self.model = genai.GenerativeModel(settings.gemini_model)

    def extract_id_card_data(self, image_base64: str) -> Dict[str, Any]:
        """
        Extract data from Thai ID card image using Gemini Vision.

        Args:
            image_base64: Base64 encoded ID card image (with or without data URI prefix)

        Returns:
            Dictionary containing:
            - success: bool - Whether extraction succeeded
            - id_number: str - 13-digit Thai ID number
            - name_th: str - Thai first name
            - surname_th: str - Thai surname
            - date_of_birth: str - Date of birth (YYYY-MM-DD format)
            - address: str - Address on card
            - issue_date: str - Card issue date (YYYY-MM-DD)
            - expiry_date: str - Card expiry date (YYYY-MM-DD)
            - error: str - Error message if failed

        Examples:
            >>> ocr_service = IDCardOCRService()
            >>> result = ocr_service.extract_id_card_data(base64_image)
            >>> print(result['id_number'])
            "1234567890123"
        """
        if not isinstance(image_base64, str) or not image_base64.strip():
            return {
                "success": False,
                "error": "Image payload is required",
                "error_code": "invalid_image",
            }

        # Remove a data URI prefix and whitespace before strict decoding.
        payload = image_base64.strip()
        if payload.startswith("data:") and "," in payload:
            payload = payload.split(",", 1)[1]
        payload = re.sub(r"\s+", "", payload)

        max_base64_chars = ((MAX_IMAGE_BYTES + 2) // 3) * 4
        if len(payload) > max_base64_chars:
            return {
                "success": False,
                "error": "Image payload is too large",
                "error_code": "invalid_image",
            }

        try:
            image_data = base64.b64decode(payload, validate=True)
        except (binascii.Error, ValueError):
            return {
                "success": False,
                "error": "Image payload is not valid base64",
                "error_code": "invalid_image",
            }

        if not image_data or len(image_data) > MAX_IMAGE_BYTES:
            return {
                "success": False,
                "error": "Image payload is empty or too large",
                "error_code": "invalid_image",
            }

        try:
            with Image.open(io.BytesIO(image_data)) as candidate:
                if candidate.format not in SUPPORTED_IMAGE_FORMATS:
                    return {
                        "success": False,
                        "error": "Image must be JPEG or PNG",
                        "error_code": "invalid_image",
                    }
                if candidate.width * candidate.height > MAX_IMAGE_PIXELS:
                    return {
                        "success": False,
                        "error": "Image dimensions are too large",
                        "error_code": "invalid_image",
                    }
                candidate.verify()

            with Image.open(io.BytesIO(image_data)) as candidate:
                candidate.load()
                image = candidate.copy()
        except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError):
            return {
                "success": False,
                "error": "Image payload is not a valid image",
                "error_code": "invalid_image",
            }

        try:
            # Gemini Vision prompt in Thai
            prompt = """
วิเคราะห์ภาพบัตรประจำตัวประชาชนไทยนี้และแยกข้อมูลออกมาในรูปแบบ JSON

ข้อมูลที่ต้องการ:
- id_number: เลขบัตรประชาชน 13 หลัก (เฉพาะตัวเลข ไม่มีขีดกลาง)
- name_th: ชื่อ (ภาษาไทยเท่านั้น)
- surname_th: นามสกุล (ภาษาไทยเท่านั้น)
- date_of_birth: วันเกิด (รูปแบบ YYYY-MM-DD หรือ DD/MM/YYYY)
- address: ที่อยู่ตามบัตร (ภาษาไทย)
- issue_date: วันออกบัตร (รูปแบบ YYYY-MM-DD หรือ DD/MM/YYYY)
- expiry_date: วันหมดอายุ (รูปแบบ YYYY-MM-DD หรือ DD/MM/YYYY)

หากไม่พบข้อมูลใดให้ใส่ null

กฎสำคัญ:
1. เลขบัตรประชาชนต้องเป็นตัวเลข 13 หลักเท่านั้น ไม่มีขีดกลาง
2. ชื่อและนามสกุลเป็นภาษาไทย ไม่ใช่ภาษาอังกฤษ
3. วันที่ต้องเป็นรูปแบบ YYYY-MM-DD หรือ DD/MM/YYYY
4. ถ้าเป็นวันที่แบบพุทธศักราช (พ.ศ.) ให้แปลงเป็นคริสต์ศักราช (ค.ศ.) โดยลบ 543

ตอบกลับเฉพาะ JSON object เท่านั้น ไม่ต้องมีคำอธิบายเพิ่มเติม:
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

                # Validate that we got at least the ID number
                if not data.get("id_number"):
                    return {
                        "success": False,
                        "error": "Could not extract ID number from card image",
                        "error_code": "ocr_failed",
                    }

                # Clean up ID number (remove any non-digits)
                if data.get("id_number"):
                    data["id_number"] = "".join(filter(str.isdigit, str(data["id_number"])))

                # Ensure ID number is 13 digits
                if len(data.get("id_number", "")) != 13:
                    return {
                        "success": False,
                        "error": "Could not extract a 13-digit ID number",
                        "error_code": "ocr_failed",
                    }

                data["success"] = True
                data["error"] = None
                return data
            else:
                return {
                    "success": False,
                    "error": "Could not parse JSON from OCR result",
                    "error_code": "ocr_failed",
                }

        except json.JSONDecodeError:
            return {
                "success": False,
                "error": "Could not parse JSON from OCR result",
                "error_code": "ocr_failed",
            }
        except Exception:
            return {
                "success": False,
                "error": "OCR service unavailable",
                "error_code": "ocr_unavailable",
            }


# Singleton instance
_ocr_service_instance = None


def get_ocr_service() -> IDCardOCRService:
    """Get singleton instance of IDCardOCRService."""
    global _ocr_service_instance
    if _ocr_service_instance is None:
        _ocr_service_instance = IDCardOCRService()
    return _ocr_service_instance
