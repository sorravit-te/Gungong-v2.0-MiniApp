"""Focused Thai ID verification tests using synthetic identifiers and mocks only."""

import base64
import io
import os
import unittest
from unittest.mock import patch

os.environ["DEBUG"] = "false"

from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from PIL import Image

from src.backend.routers import verification as verification_router
from src.backend.services.id_card_ocr_service import IDCardOCRService
from src.backend.services.id_card_service import IDCardService
from src.backend.utils.thai_id_validator import normalize_thai_id, validate_thai_id


# Leading zero is intentionally used to keep these checksum fixtures synthetic.
SYNTHETIC_VALID_ID = "0000000000001"
SYNTHETIC_FORMATTED_ID = "0-0000-00000-00-1"
SYNTHETIC_INVALID_CHECKSUM = "0000000000000"


class FakeSnapshot:
    def __init__(self, data=None):
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return self._data


class FakeDocument:
    def __init__(self, snapshot=None, error=None):
        self.snapshot = snapshot or FakeSnapshot()
        self.error = error

    def get(self):
        if self.error:
            raise self.error
        return self.snapshot


class FakeFirestore:
    def __init__(self, records=None, error=None):
        self.records = records or {}
        self.error = error
        self.last_document_id = None

    def collection(self, _name):
        return self

    def document(self, document_id):
        self.last_document_id = document_id
        data = self.records.get(document_id)
        return FakeDocument(FakeSnapshot(data), self.error)


class FakeDatabaseService:
    def __init__(self, records=None, error=None):
        self.db = FakeFirestore(records, error)


class FakeOCRService:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def extract_id_card_data(self, _image_base64):
        self.calls += 1
        return self.result


class StubIDCardService:
    def __init__(self, manual_result=None, image_result=None, error=None):
        self.manual_result = manual_result
        self.image_result = image_result
        self.error = error

    def verify_id_number_only(self, _id_number):
        if self.error:
            raise self.error
        return self.manual_result

    def verify_id_card(self, _image_base64):
        if self.error:
            raise self.error
        return self.image_result


def make_client():
    app = FastAPI()
    app.state.limiter = verification_router.limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(verification_router.router)
    return TestClient(app)


class ThaiIDChecksumTests(unittest.TestCase):
    def test_valid_invalid_and_normalization(self):
        self.assertEqual(normalize_thai_id(SYNTHETIC_FORMATTED_ID), SYNTHETIC_VALID_ID)
        self.assertTrue(validate_thai_id(SYNTHETIC_VALID_ID))
        self.assertTrue(validate_thai_id(SYNTHETIC_FORMATTED_ID))
        self.assertFalse(validate_thai_id(SYNTHETIC_INVALID_CHECKSUM))


class IDCardOCRValidationTests(unittest.TestCase):
    def setUp(self):
        self.service = IDCardOCRService.__new__(IDCardOCRService)

    def test_rejects_empty_invalid_base64_and_non_image_payloads(self):
        cases = (
            ("", "Image payload is required"),
            ("not-valid-base64!", "Image payload is not valid base64"),
            (base64.b64encode(b"not an image").decode("ascii"), "Image payload is not a valid image"),
        )
        for payload, expected_error in cases:
            with self.subTest(expected_error=expected_error):
                result = self.service.extract_id_card_data(payload)
                self.assertFalse(result["success"])
                self.assertEqual(result["error"], expected_error)
                self.assertEqual(result["error_code"], "invalid_image")

    def test_ocr_parse_failure_does_not_return_raw_model_text(self):
        image_buffer = io.BytesIO()
        Image.new("RGB", (2, 2), "white").save(image_buffer, format="PNG")
        payload = base64.b64encode(image_buffer.getvalue()).decode("ascii")

        class FakeResponse:
            text = f"unparseable private OCR output {SYNTHETIC_VALID_ID}"

        class FakeModel:
            def generate_content(self, _content):
                return FakeResponse()

        self.service.model = FakeModel()
        result = self.service.extract_id_card_data(payload)

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "ocr_failed")
        self.assertNotIn("raw_response", result)
        self.assertNotIn(SYNTHETIC_VALID_ID, str(result))


class IDCardServiceTests(unittest.TestCase):
    def test_manual_valid_not_blacklisted_normalizes_and_does_not_initialize_ocr(self):
        database = FakeDatabaseService()
        service = IDCardService(db_service=database)

        with patch(
            "src.backend.services.id_card_service.get_ocr_service",
            side_effect=AssertionError("manual verification must not initialize OCR"),
        ):
            result = service.verify_id_number_only(SYNTHETIC_FORMATTED_ID)

        self.assertTrue(result["success"])
        self.assertTrue(result["is_valid_format"])
        self.assertTrue(result["is_safe"])
        self.assertEqual(result["risk_level"], "LOW")
        self.assertEqual(result["id_number"], SYNTHETIC_VALID_ID)
        self.assertEqual(database.db.last_document_id, SYNTHETIC_VALID_ID)

    def test_manual_invalid_checksum_is_not_safe(self):
        service = IDCardService(db_service=FakeDatabaseService())
        result = service.verify_id_number_only(SYNTHETIC_INVALID_CHECKSUM)

        self.assertTrue(result["success"])
        self.assertFalse(result["is_valid_format"])
        self.assertFalse(result["is_safe"])
        self.assertEqual(result["risk_level"], "MEDIUM")

    def test_shared_blacklist_risk_thresholds(self):
        cases = ((1, "LOW"), (5, "MEDIUM"), (10, "HIGH"), (20, "CRITICAL"))
        for report_count, expected_risk in cases:
            with self.subTest(report_count=report_count):
                database = FakeDatabaseService({
                    SYNTHETIC_VALID_ID: {
                        "report_count": report_count,
                        "category": "synthetic-test",
                    }
                })
                service = IDCardService(db_service=database)
                result = service.verify_id_number_only(SYNTHETIC_VALID_ID)

                self.assertTrue(result["is_blacklisted"])
                self.assertFalse(result["is_safe"])
                self.assertEqual(result["risk_level"], expected_risk)

    def test_manual_blacklist_error_fails_closed(self):
        database = FakeDatabaseService(error=RuntimeError("synthetic database failure"))
        result = IDCardService(db_service=database).verify_id_number_only(SYNTHETIC_VALID_ID)

        self.assertFalse(result["success"])
        self.assertFalse(result["is_safe"])
        self.assertEqual(result["error"], "Blacklist service unavailable")
        self.assertEqual(result["error_code"], "blacklist_unavailable")

    def test_image_success_uses_mocked_ocr(self):
        ocr = FakeOCRService({
            "success": True,
            "id_number": SYNTHETIC_FORMATTED_ID,
            "name_th": "บุคคลทดสอบ",
            "surname_th": "ข้อมูลสมมติ",
        })
        service = IDCardService(db_service=FakeDatabaseService(), ocr_service=ocr)
        result = service.verify_id_card("synthetic-image")

        self.assertTrue(result["success"])
        self.assertTrue(result["is_safe"])
        self.assertEqual(result["id_number"], SYNTHETIC_VALID_ID)
        self.assertEqual(ocr.calls, 1)

    def test_image_ocr_failure_is_structured(self):
        ocr = FakeOCRService({
            "success": False,
            "error": "Image payload is not a valid image",
            "error_code": "invalid_image",
        })
        result = IDCardService(
            db_service=FakeDatabaseService(),
            ocr_service=ocr,
        ).verify_id_card("synthetic-image")

        self.assertFalse(result["success"])
        self.assertFalse(result["is_safe"])
        self.assertEqual(result["error_code"], "invalid_image")

    def test_image_blacklist_error_fails_closed(self):
        ocr = FakeOCRService({"success": True, "id_number": SYNTHETIC_VALID_ID})
        database = FakeDatabaseService(error=RuntimeError("synthetic database failure"))
        result = IDCardService(db_service=database, ocr_service=ocr).verify_id_card("synthetic-image")

        self.assertFalse(result["success"])
        self.assertFalse(result["is_safe"])
        self.assertEqual(result["error_code"], "blacklist_unavailable")


class IDCardEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = make_client()

    def post_manual(self, service, id_number=SYNTHETIC_VALID_ID):
        with patch.object(verification_router, "get_id_card_service", return_value=service):
            return self.client.post("/api/v2/verify-id-number", json={"id_number": id_number})

    def post_image(self, service):
        with patch.object(verification_router, "get_id_card_service", return_value=service):
            return self.client.post("/api/v2/verify-id-card", json={"image_base64": "c3ludGhldGlj"})

    def test_manual_endpoint_valid_invalid_and_blacklisted_results(self):
        cases = (
            (
                SYNTHETIC_FORMATTED_ID,
                FakeDatabaseService(),
                {"id_number": SYNTHETIC_VALID_ID, "is_safe": True, "risk_level": "LOW"},
            ),
            (
                SYNTHETIC_INVALID_CHECKSUM,
                FakeDatabaseService(),
                {"id_number": SYNTHETIC_INVALID_CHECKSUM, "is_safe": False, "risk_level": "MEDIUM"},
            ),
            (
                SYNTHETIC_VALID_ID,
                FakeDatabaseService({
                    SYNTHETIC_VALID_ID: {
                        "report_count": 20,
                        "category": "synthetic-test",
                    }
                }),
                {"id_number": SYNTHETIC_VALID_ID, "is_safe": False, "risk_level": "CRITICAL"},
            ),
        )
        for id_number, database, expected in cases:
            with self.subTest(risk=expected["risk_level"]), patch(
                "src.backend.services.id_card_service.get_ocr_service",
                side_effect=AssertionError("manual endpoint must not initialize OCR"),
            ):
                response = self.post_manual(IDCardService(db_service=database), id_number)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["content-type"].split(";")[0], "application/json")
                self.assertEqual(response.json()["id_number"], expected["id_number"])
                self.assertEqual(response.json()["is_safe"], expected["is_safe"])
                self.assertEqual(response.json()["risk_level"], expected["risk_level"])

    def test_manual_blacklist_failure_returns_json_503(self):
        database = FakeDatabaseService(error=RuntimeError("synthetic database failure"))
        response = self.post_manual(IDCardService(db_service=database))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["content-type"].split(";")[0], "application/json")
        self.assertEqual(response.json(), {"detail": "Blacklist service unavailable"})

    def test_image_validation_failure_returns_json_400(self):
        failure = {
            "success": False,
            "error": "Image payload is not a valid image",
            "error_code": "invalid_image",
            "is_safe": False,
        }
        response = self.post_image(StubIDCardService(image_result=failure))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.headers["content-type"].split(";")[0], "application/json")
        self.assertEqual(response.json(), {"detail": "Image payload is not a valid image"})

    def test_image_blacklist_failure_returns_json_503(self):
        failure = {
            "success": False,
            "error": "Blacklist service unavailable",
            "error_code": "blacklist_unavailable",
            "is_safe": False,
        }
        response = self.post_image(StubIDCardService(image_result=failure))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": "Blacklist service unavailable"})

    def test_unexpected_failure_returns_safe_json_500(self):
        response = self.post_manual(StubIDCardService(
            error=RuntimeError("private path C:/secrets/service-account.json"),
        ))

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.headers["content-type"].split(";")[0], "application/json")
        self.assertEqual(response.json(), {"detail": "ID number verification failed"})
        self.assertNotIn("service-account", response.text)


if __name__ == "__main__":
    unittest.main()
