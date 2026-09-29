"""ID Card OCR Service using Google Gemini Vision."""

import google.generativeai as genai
from PIL import Image
import base64
import io
import json
import re
from typing import Dict, Any

from ..core.config import settings


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
        try:
            # Remove data URI prefix if present
            if ',' in image_base64 and image_base64.startswith('data:'):
                image_base64 = image_base64.split(',')[1]

            # Decode base64 image
            image_data = base64.b64decode(image_base64)
            image = Image.open(io.BytesIO(image_data))

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
                        "raw_response": text
                    }

                # Clean up ID number (remove any non-digits)
                if data.get("id_number"):
                    data["id_number"] = "".join(filter(str.isdigit, str(data["id_number"])))

                # Ensure ID number is 13 digits
                if len(data.get("id_number", "")) != 13:
                    return {
                        "success": False,
                        "error": f"Invalid ID number length: {len(data.get('id_number', ''))} (expected 13)",
                        "raw_response": text
                    }

                data["success"] = True
                data["error"] = None
                return data
            else:
                return {
                    "success": False,
                    "error": "Could not parse JSON from OCR result",
                    "raw_response": text
                }

        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"JSON parsing error: {str(e)}",
                "raw_response": text if 'text' in locals() else None
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"OCR extraction failed: {str(e)}"
            }


# Singleton instance
_ocr_service_instance = None


def get_ocr_service() -> IDCardOCRService:
    """Get singleton instance of IDCardOCRService."""
    global _ocr_service_instance
    if _ocr_service_instance is None:
        _ocr_service_instance = IDCardOCRService()
    return _ocr_service_instance
