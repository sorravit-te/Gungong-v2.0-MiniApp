"""Signed bot URL events reuse the Mini App pipeline; no real network or secrets."""

import base64
import hashlib
import hmac
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import BackgroundTasks, FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from linebot.v3.messaging.models import FlexContainer

from src.backend.routers import fraud, webhook
from src.backend.services.line_service import LineService
from tests.test_url_staged_routing import candidate
from tests.test_url_verification_service import FakeDatabase, gemini_uncertain


class URLRecognitionTests(unittest.TestCase):
    def test_single_urls_include_bare_idn_encoded_private_and_invalid_urls(self):
        for message in [
            " https://www.ilaw.or.th/%E0%B8%A3%E0%B8%B9%E0%B9%89 ",
            "example.com", "bücher.example/path", "http://127.0.0.1/",
            "localhost", "http:///missing", "file:///etc/passwd", "ftp://example.com",
        ]:
            with self.subTest(message=message):
                self.assertTrue(webhook._is_url_only(message))

    def test_text_and_multiple_urls_stay_on_existing_message_path(self):
        for message in ["", "สวัสดีครับ", "ช่วยดู https://example.com",
                        "https://a.test https://b.test", "รับเงินคลิก https://a.test"]:
            with self.subTest(message=message):
                self.assertFalse(webhook._is_url_only(message))


class WebhookURLRoutingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.secret = "test-only-secret"
        self.line = Mock(spec=LineService)
        self.line.create_url_verification_flex_message.side_effect = (
            lambda result: LineService.create_url_verification_flex_message(None, result)
        )
        self.db = FakeDatabase()
        for target, name, value in [
            (webhook, "settings", SimpleNamespace(line_channel_secret=self.secret)),
            (webhook, "LINE_SERVICE_AVAILABLE", True),
            (webhook, "get_line_service", Mock(return_value=self.line)),
            (fraud, "get_database_service", Mock(return_value=self.db)),
            (fraud, "lookup_recent_risk", AsyncMock(return_value={
                "status": "not_listed", "complete": True, "required": True,
            })),
            (fraud, "save_recent_risk", AsyncMock()),
        ]:
            patcher = patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    async def send(self, message, *, source=None, mentioned=False):
        event = {
            "type": "message", "replyToken": "fake-reply-token",
            "source": source or {"type": "user", "userId": "TEST_ONLY"},
            "message": {"type": "text", "text": message, "quoteToken": "fake-quote"},
        }
        if mentioned:
            event["message"]["mention"] = {"mentionees": [{"type": "bot"}]}
        body = json.dumps({"events": [event]}).encode()

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        signature = base64.b64encode(hmac.new(
            self.secret.encode(), body, hashlib.sha256,
        ).digest()).decode()
        tasks = BackgroundTasks()
        response = await webhook.webhook(Request({"type": "http"}, receive), tasks, signature)
        await tasks()
        self.assertEqual(response, {"status": "ok"})

    async def run_candidate(self, message, **options):
        verifier, gemini, vt, local, requester = candidate(**options)
        with patch.object(fraud, "get_url_verification_service", return_value=verifier), patch.object(
            webhook, "get_prescreen_service",
        ) as prescreen, patch.object(webhook, "get_fraud_detector") as legacy_ai, patch.object(
            webhook, "get_virustotal_service",
        ) as legacy_vt, patch.object(webhook, "get_database_service") as legacy_db:
            await self.send(message)
        prescreen.assert_not_called()
        legacy_ai.assert_not_called()
        legacy_vt.assert_not_called()
        legacy_db.assert_not_called()
        self.line.reply_message.assert_called_once()
        result = self.line.create_url_verification_flex_message.call_args.args[0]
        return result, gemini, vt, requester

    async def test_unknown_benign_calls_gemini_once_vt_zero_and_saves_link_history(self):
        url = "https://www.ilaw.or.th/%E0%B8%A3%E0%B8%B9%E0%B9%89"
        result, gemini, vt, requester = await self.run_candidate(url)
        self.assertEqual(result["verification_verdict"], "NO_THREAT_FOUND")
        gemini.assert_awaited_once()
        vt.assert_not_awaited()
        requester.assert_awaited_once()
        self.assertEqual(len(self.db.saved_history), 1)
        entry = self.db.saved_history[0]
        self.assertEqual(entry["message_type"], "link")
        self.assertEqual(entry["message"], url)
        self.assertEqual(entry["url_check_result"]["verification_verdict"], "NO_THREAT_FOUND")
        self.assertIn("policy_version", self.db.saved_results[0]["url_check_result"])

    async def test_trusted_benign_skips_both_providers(self):
        result, gemini, vt, _ = await self.run_candidate("https://www.youtube.com/")
        self.assertEqual(result["verification_verdict"], "NO_THREAT_FOUND")
        gemini.assert_not_awaited()
        vt.assert_not_awaited()

    async def test_core_unreadable_is_incomplete_not_cached_safe(self):
        result, _, _, _ = await self.run_candidate("https://unreadable.test/", page="")
        self.assertEqual(result["verification_verdict"], "INCOMPLETE")
        self.assertIsNot(result["is_safe"], True)
        self.assertEqual(self.db.saved_results, [])
        self.assertEqual(self.db.saved_history[0]["message_type"], "link")
        reply = self.line.reply_message.call_args.kwargs["flex_message"]
        self.assertIn("ยังสรุปไม่ได้", reply["alt_text"])

    async def test_suspicious_core_and_vt_timeout_remains_suspicious(self):
        result, _, vt, _ = await self.run_candidate(
            "https://fake-bank.test/", vt_status="timeout",
            page="<title>Bank login</title><form><input type=password><input name=otp></form>",
        )
        self.assertEqual(result["verification_verdict"], "SUSPICIOUS")
        vt.assert_awaited_once()

    async def test_vt_malicious_dominates_uncertain_gemini(self):
        result, gemini, vt, _ = await self.run_candidate(
            "https://unknown.test/", vt_status="malicious", gemini_result=gemini_uncertain,
        )
        self.assertEqual(result["verification_verdict"], "MALICIOUS")
        gemini.assert_awaited_once()
        vt.assert_awaited_once()

    async def test_private_url_invalid_without_fetch_or_providers(self):
        result, gemini, vt, requester = await self.run_candidate("http://127.0.0.1/")
        self.assertEqual(result["verification_verdict"], "INVALID")
        requester.assert_not_awaited()
        gemini.assert_not_awaited()
        vt.assert_not_awaited()

    async def test_bot_uses_miniapp_cache_and_still_saves_link_history(self):
        verifier, gemini, vt, _, requester = candidate()
        with patch.object(fraud, "get_url_verification_service", return_value=verifier):
            miniapp = await fraud._check_link_request(fraud.FraudCheckRequest(
                message="example.com", message_type="link", user_id="TEST_ONLY",
            ))
            self.db.cached = {**miniapp, "cached": True}
            await self.send("https://example.com/")
        bot = self.line.create_url_verification_flex_message.call_args.args[0]
        self.assertEqual(bot["verification_verdict"], miniapp["verification_verdict"])
        self.assertTrue(bot["cached"])
        gemini.assert_awaited_once()
        requester.assert_awaited_once()
        vt.assert_not_awaited()
        self.assertEqual(len(self.db.saved_history), 2)
        self.assertTrue(all(row["message_type"] == "link" for row in self.db.saved_history))

    async def test_group_opt_in_preserved(self):
        with patch.object(webhook, "_check_link_request", new_callable=AsyncMock) as check:
            await self.send("https://example.com/", source={"type": "group", "groupId": "TEST_GROUP"})
        check.assert_not_awaited()
        self.line.reply_message.assert_not_called()

    async def test_signed_http_url_event_reaches_shared_route(self):
        app = FastAPI()
        app.include_router(webhook.router)
        body = json.dumps({"events": [{
            "type": "message", "replyToken": "fake-reply",
            "source": {"type": "user", "userId": "TEST_ONLY"},
            "message": {"type": "text", "text": "https://example.com/"},
        }]}).encode()
        signature = base64.b64encode(hmac.new(
            self.secret.encode(), body, hashlib.sha256,
        ).digest()).decode()
        with patch.object(webhook, "_check_link_request", new_callable=AsyncMock,
                          return_value={"verification_verdict": "INCOMPLETE"}) as check:
            response = TestClient(app).post("/webhook", content=body, headers={
                "Content-Type": "application/json", "X-Line-Signature": signature,
            })
        self.assertEqual(response.status_code, 200)
        check.assert_awaited_once()
        self.assertIsInstance(check.await_args.args[1], BackgroundTasks)

    async def test_mentioned_group_url_uses_shared_pipeline(self):
        result = {"verification_verdict": "INCOMPLETE", "reason_th": "ตรวจสอบได้ไม่ครบ"}
        with patch.object(webhook, "_check_link_request", new_callable=AsyncMock,
                          return_value=result) as check:
            await self.send("https://example.com/", mentioned=True,
                            source={"type": "group", "groupId": "TEST_GROUP"})
        check.assert_awaited_once()
        self.assertEqual(check.await_args.args[0].user_id, "TEST_GROUP")
        self.assertEqual(check.await_args.args[0].message_type, "link")
        self.line.reply_message.assert_called_once()

    async def test_old_message_cache_cannot_override_new_url_verdict(self):
        self.db.cached = {"category": "SCAM_MALICIOUS", "is_fraud": True,
                          "is_safe": False, "cached": True}
        result, gemini, vt, _ = await self.run_candidate("https://normal.test/")
        self.assertFalse(result["cached"])
        self.assertEqual(result["verification_verdict"], "NO_THREAT_FOUND")
        gemini.assert_awaited_once()
        vt.assert_not_awaited()

    async def test_ordinary_text_keeps_legacy_detection(self):
        detector = Mock()
        detector.classify_with_details_async = AsyncMock(return_value={
            "category": "SAFE_NORMAL", "is_fraud": False, "is_safe": True,
            "reason_th": "ข้อความทั่วไป", "keywords_found": [],
        })
        prescreen = Mock()
        prescreen.check_message.return_value = SimpleNamespace(
            confidence=0.0, analysis_message="สวัสดีครับ", matched_patterns=[],
            is_educational_context=False, urls_found=[],
        )
        with patch.object(webhook, "_check_link_request", new_callable=AsyncMock) as check, patch.object(
            webhook, "get_prescreen_service", return_value=prescreen,
        ), patch.object(webhook, "get_fraud_detector", return_value=detector), patch.object(
            webhook, "get_virustotal_service", return_value=None,
        ), patch.object(webhook, "get_database_service", return_value=None), patch.object(
            webhook, "get_fraud_message_service", return_value=None,
        ), patch.object(webhook, "get_similarity_service", return_value=None):
            await self.send("สวัสดีครับ")
        check.assert_not_awaited()
        prescreen.check_message.assert_called_once_with("สวัสดีครับ", allow_network=False)
        detector.classify_with_details_async.assert_awaited_once_with("สวัสดีครับ")
        self.line.create_url_verification_flex_message.assert_not_called()


class URLFlexTests(unittest.TestCase):
    def test_incomplete_uses_yellow_gradient_card_without_risk_percentage(self):
        source = {
            "verification_verdict": "INCOMPLETE", "reason_th": "อ่านหน้าเว็บได้ไม่ครบ",
            "confidence_score": 100, "is_fraud": True,
            "checks": {"gemini": {"reason_th": "คำอธิบายภาษาไทยจาก AI"}},
        }
        original = json.dumps(source, ensure_ascii=False)
        result = LineService.create_url_verification_flex_message(None, source)
        body = result["contents"]["body"]
        self.assertEqual(result["contents"]["size"], "mega")
        self.assertEqual(body["background"], {
            "type": "linearGradient", "angle": "135deg",
            "startColor": "#FFD060", "endColor": "#FF9500",
        })
        self.assertEqual(body["action"]["uri"], "https://miniapp.line.me/2008548759-KkM4Noxa")
        self.assertEqual(body["contents"][1], {
            "type": "image", "url": "https://img.icons8.com/ios-filled/100/ffffff/question-mark.png",
            "size": "xs", "aspectRatio": "1:1", "margin": "md",
        })
        self.assertEqual(body["contents"][4]["width"], "60%")
        self.assertEqual(body["contents"][-1]["text"], "see more >")
        self.assertEqual(result["contents"]["styles"]["body"]["backgroundColor"], "#FF9500")
        serialized = json.dumps(result, ensure_ascii=False)
        for text in ["ยังสรุปไม่ได้", "ตรวจสอบได้ไม่ครบ", "ข้อมูลยังไม่เพียงพอ"]:
            self.assertIn(text, serialized)
        summary = body["contents"][5]
        self.assertEqual(summary["backgroundColor"], body["contents"][4]["backgroundColor"])
        self.assertEqual(summary["contents"], [{
            "type": "text", "text": "ข้อมูลยังไม่เพียงพอ", "size": "sm",
            "color": "#ffffff", "align": "center", "wrap": False,
        }])
        self.assertNotIn("อ่านหน้าเว็บได้ไม่ครบ", serialized)
        self.assertNotIn("คำอธิบายภาษาไทยจาก AI", serialized)
        texts = []

        def collect_texts(item):
            if isinstance(item, dict):
                if item.get("type") == "text":
                    texts.append(item["text"])
                for value in item.values():
                    collect_texts(value)
            elif isinstance(item, list):
                for value in item:
                    collect_texts(value)

        collect_texts(result)
        # Percent-based layout width is allowed; a made-up risk percentage is not.
        self.assertFalse(any("%" in text for text in texts))
        self.assertNotIn("เสี่ยงอันตราย", serialized)
        self.assertNotIn("อันตราย!", serialized)
        self.assertEqual(json.dumps(source, ensure_ascii=False), original)
        self.assertIsNotNone(FlexContainer.from_dict(result["contents"]))

    def test_other_url_verdicts_retain_existing_card_layout(self):
        for verdict in ["NO_THREAT_FOUND", "SUSPICIOUS", "MALICIOUS", "INVALID"]:
            with self.subTest(verdict=verdict):
                result = LineService.create_url_verification_flex_message(None, {
                    "verification_verdict": verdict, "reason_th": "เหตุผลภาษาไทย",
                })
                self.assertNotIn("background", result["contents"]["body"])
                self.assertIn("footer", result["contents"])
                self.assertEqual(result["contents"]["body"]["contents"][0]["text"],
                                 "GunGong · ผลการตรวจสอบลิงก์")

    def test_incomplete_keeps_full_explanation_in_source_not_compact_card(self):
        source = {
            "verification_verdict": "INCOMPLETE", "reason_th": "เนื้อหาอ่านได้ไม่ครบ",
            "checks": {"gemini": {"reason_th": "AI ไม่พบหลักฐานหลอกลวง"}},
        }
        result = LineService.create_url_verification_flex_message(None, source)
        self.assertIn("ยังสรุปไม่ได้", result["alt_text"])
        self.assertNotIn("AI ไม่พบหลักฐานหลอกลวง", json.dumps(result, ensure_ascii=False))
        self.assertEqual(source["reason_th"], "เนื้อหาอ่านได้ไม่ครบ")
        self.assertEqual(source["checks"]["gemini"]["reason_th"], "AI ไม่พบหลักฐานหลอกลวง")

    def test_all_verdicts_are_sdk_valid_and_never_claim_absolute_safety(self):
        for verdict in ["NO_THREAT_FOUND", "SUSPICIOUS", "MALICIOUS", "INCOMPLETE", "INVALID", None]:
            with self.subTest(verdict=verdict):
                result = LineService.create_url_verification_flex_message(None, {
                    "verification_verdict": verdict, "reason_th": "เหตุผลภาษาไทย",
                    "confidence_score": 100, "is_fraud": False,
                })
                self.assertIsNotNone(FlexContainer.from_dict(result["contents"]))
                serialized = json.dumps(result, ensure_ascii=False)
                self.assertNotIn("ปลอดภัย", serialized)
                self.assertNotIn("100%", serialized)
                if verdict == "INCOMPLETE":
                    self.assertIn("ข้อมูลยังไม่เพียงพอ", serialized)
                    self.assertNotIn("เหตุผลภาษาไทย", serialized)
                else:
                    self.assertIn("เหตุผลภาษาไทย", serialized)
                if verdict in {"INCOMPLETE", None}:
                    self.assertIn("ยังสรุปไม่ได้", result["alt_text"])


if __name__ == "__main__":
    unittest.main()
