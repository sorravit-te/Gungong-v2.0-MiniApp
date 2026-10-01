"""Bare-domain input convenience must not bypass the real URL pipeline."""

import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from src.backend.main import app
from src.backend.routers import fraud as fraud_router
from src.backend.services.url_safety_service import (
    URLSafetyError,
    normalize_public_url,
    normalize_user_url,
)
from tests.test_url_staged_routing import candidate
from tests.test_url_verification_service import FakeDatabase


class URLInputNormalizationTests(unittest.TestCase):
    def test_bare_domains_paths_queries_fragments_idn_and_ports_default_to_https(self):
        cases = {
            "example.com": "https://example.com/",
            "  WWW.Example.COM  ": "https://www.example.com/",
            "example.com/A%2Fb?q=x%20y#part": "https://example.com/A%2Fb?q=x%20y#part",
            "example.com?x=1#part": "https://example.com/?x=1#part",
            "example.com:8443/path": "https://example.com:8443/path",
            "bücher.example/": "https://xn--bcher-kva.example/",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalize_user_url(raw), expected)

    def test_explicit_http_and_https_are_not_replaced(self):
        for raw in ["http://example.com/path?q=1", "HTTPS://EXAMPLE.COM:443/A"]:
            self.assertEqual(normalize_user_url(raw), normalize_public_url(raw))

    def test_unsupported_schemes_and_malformed_input_are_never_rewritten(self):
        for raw in [
            "", "hello", "/example.com", "//example.com", "example..com",
            "example.com:bad", "user@example.com", "example.com\\evil.test",
            "http:///missing", "javascript:alert(1)", "javascript:example.com",
            "data:text/plain,example.com", "file:///example.com", "ftp://example.com",
            "javascript:443", "example.com@127.0.0.1",
        ]:
            with self.subTest(raw=raw):
                with self.assertRaises(URLSafetyError):
                    normalize_user_url(raw)

    def test_redirect_and_policy_normalizer_remains_strict(self):
        with self.assertRaises(URLSafetyError):
            normalize_public_url("example.com")
        with self.assertRaises(ValueError):
            candidate(trusted_origins=["library.test"])


class BareDomainPipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_bare_domain_runs_content_and_one_gemini_without_vt(self):
        verifier, gemini, vt, local, requester = candidate()
        result = await verifier.verify("example.com/path?q=1#part")
        normalized = "https://example.com/path?q=1#part"
        self.assertEqual(result["verification_verdict"], "NO_THREAT_FOUND")
        self.assertEqual(result["verification_route"], "AI_CONFIRMATION")
        self.assertEqual(result["original_url"], normalized)
        self.assertEqual(result["final_url"], normalized)
        self.assertEqual(result["redirect_chain"], [normalized])
        self.assertTrue(result["checks"]["content"]["evidence_sufficient"])
        requester.assert_awaited_once()
        self.assertEqual(requester.await_args.args[0], normalized)
        local.assert_awaited_once_with(normalized)
        gemini.assert_awaited_once()
        self.assertEqual(gemini.await_args.args[0], normalized)
        vt.assert_not_awaited()

    async def test_bare_trusted_domain_uses_generic_fast_path(self):
        verifier, gemini, vt, _, requester = candidate(trusted_origins=["https://library.test"])
        result = await verifier.verify("library.test/catalogue")
        self.assertEqual(result["verification_verdict"], "NO_THREAT_FOUND")
        self.assertEqual(result["verification_route"], "FAST_SAFE")
        requester.assert_awaited_once()
        gemini.assert_not_awaited()
        vt.assert_not_awaited()

    async def test_bare_non_public_targets_are_invalid_without_fetch_or_providers(self):
        for raw in [
            "localhost", "localhost:8000", "127.0.0.1", "192.168.1.1",
            "169.254.169.254/latest/meta-data", "100.64.0.1", "[::1]", "[fc00::1]",
            "private.test",
        ]:
            with self.subTest(raw=raw):
                verifier, gemini, vt, local, requester = candidate()
                result = await verifier.verify(raw)
                self.assertEqual(result["verification_verdict"], "INVALID")
                self.assertEqual(result["checks"]["redirect"]["reason"], "non_public_target")
                requester.assert_not_awaited()
                local.assert_not_awaited()
                gemini.assert_not_awaited()
                vt.assert_not_awaited()

    async def test_explicit_unsupported_scheme_is_invalid_without_fetch(self):
        for raw in ["javascript:example.com", "file:///example.com", "ftp://example.com"]:
            with self.subTest(raw=raw):
                verifier, gemini, vt, _, requester = candidate()
                result = await verifier.verify(raw)
                self.assertEqual(result["verification_verdict"], "INVALID")
                self.assertEqual(result["checks"]["redirect"]["reason"], "unsupported_scheme")
                requester.assert_not_awaited()
                gemini.assert_not_awaited()
                vt.assert_not_awaited()

    async def test_bare_domain_redirect_to_private_is_still_blocked(self):
        verifier, gemini, vt, _, requester = candidate(redirects={
            "https://example.com/": "http://169.254.169.254/",
        })
        result = await verifier.verify("example.com")
        self.assertEqual(result["verification_verdict"], "INVALID")
        requester.assert_awaited_once()
        self.assertEqual(requester.await_args.args[0], "https://example.com/")
        gemini.assert_not_awaited()
        vt.assert_not_awaited()

    async def test_bare_suspicious_page_still_escalates_to_vt(self):
        verifier, _, vt, _, _ = candidate(
            page="<title>Bank login</title><form><input type=password><input name=otp></form>",
            vt_status="timeout",
        )
        result = await verifier.verify("fake-bank.test")
        self.assertEqual(result["verification_verdict"], "SUSPICIOUS")
        vt.assert_awaited_once_with("https://fake-bank.test/")

    async def test_cache_and_history_use_canonical_url_but_keep_original_input(self):
        verifier, gemini, vt, _, requester = candidate()
        db = FakeDatabase()
        db.get_cached_result = Mock(wraps=db.get_cached_result)
        with patch.object(fraud_router, "get_database_service", return_value=db), patch.object(
            fraud_router, "get_url_verification_service", return_value=verifier,
        ):
            first = await fraud_router._check_link_request(fraud_router.FraudCheckRequest(
                message="example.com", message_type="link", user_id="TEST_MOCK_ONLY",
            ))
            cache_key = db.saved_results[0]["cache_key"]
            self.assertEqual(cache_key, fraud_router._link_cache_key("https://example.com/"))
            db.cached = {**first, "cached": True}
            second = await fraud_router._check_link_request(fraud_router.FraudCheckRequest(
                message="https://example.com/", message_type="link", user_id="TEST_MOCK_ONLY",
            ))
        self.assertEqual(second["verification_verdict"], "NO_THREAT_FOUND")
        self.assertTrue(second["cached"])
        self.assertEqual(db.get_cached_result.call_args_list[0].kwargs["cache_key"], cache_key)
        self.assertEqual(db.get_cached_result.call_args_list[1].kwargs["cache_key"], cache_key)
        self.assertEqual([entry["message"] for entry in db.saved_history], ["example.com", "https://example.com/"])
        self.assertTrue(all(entry["message_type"] == "link" for entry in db.saved_history))
        requester.assert_awaited_once()
        gemini.assert_awaited_once()
        vt.assert_not_awaited()

    async def test_check_fraud_endpoint_accepts_bare_domain_on_cache_miss(self):
        verifier, gemini, vt, _, requester = candidate()
        with patch.object(fraud_router, "get_database_service", return_value=FakeDatabase()), patch.object(
            fraud_router, "get_url_verification_service", return_value=verifier,
        ):
            response = TestClient(app).post("/check-fraud", json={
                "message": "example.com", "message_type": "link",
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["verification_verdict"], "NO_THREAT_FOUND")
        self.assertEqual(response.json()["final_url"], "https://example.com/")
        requester.assert_awaited_once()
        gemini.assert_awaited_once()
        vt.assert_not_awaited()
