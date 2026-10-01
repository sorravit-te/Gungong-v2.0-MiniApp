"""False-alarm controls and cross-request evidence; no live URL/API/DB calls."""

import asyncio
import time
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from src.backend.routers import fraud
from src.backend.services.database_service import DatabaseService
from src.backend.services.url_reputation_service import URLReputationService
from src.backend.services.url_risk_evidence_service import lookup_recent_risk, save_recent_risk
from src.backend.services.url_safety_service import RedirectHTTPResponse, SafeRedirectResolver
from src.backend.services.url_verification_service import extract_page_evidence
from src.backend.services.virustotal_service import VirusTotalResult
from tests.test_url_verification_service import BENIGN_PAGE, FakeDatabase, gemini_clean, service
from tests.test_url_staged_routing import candidate, public_dns


class FalseAlarmTests(unittest.IsolatedAsyncioTestCase):
    async def test_fake_bank_cannot_suppress_password_risk_with_news_keyword(self):
        verifier, _, _, _, _ = candidate(
            page='<title>Bank news</title><form><p>Bank login password</p><input type=password></form>',
            vt_status='timeout',
        )
        result = await verifier.verify('https://fake-bank.test/')
        self.assertEqual(result['verification_verdict'], 'SUSPICIOUS')

    async def test_ordinary_same_origin_login_needs_ai_not_automatic_risk(self):
        page = BENIGN_PAGE + "<form action='/login'><input type=password></form>"
        verifier, gemini, vt, _, _ = candidate(page=page, trusted_origins=[])
        result = await verifier.verify("https://ordinary.test/login")
        self.assertEqual(result['verification_verdict'], 'NO_THREAT_FOUND')
        gemini.assert_awaited_once()
        vt.assert_not_awaited()

    async def test_single_vt_detection_warns_without_claiming_confirmation(self):
        verifier, gemini, vt, _, _ = candidate()
        gemini.return_value.update(assessment="uncertain", evidence_sufficient=False)
        vt.return_value = VirusTotalResult("malicious", "https://unknown.test/", malicious_count=1, total_scanners=92)
        result = await verifier.verify("https://unknown.test/")
        self.assertEqual(result['verification_verdict'], 'SUSPICIOUS')
        self.assertFalse(result['is_safe'])
        self.assertEqual(result['checks']['virustotal']['provider_status'], 'malicious')
        self.assertEqual(result['checks']['virustotal']['reason'], 'single_engine_detection')

    async def test_multiple_vt_detections_remain_malicious(self):
        verifier, gemini, vt, _, _ = candidate()
        gemini.return_value.update(assessment="uncertain", evidence_sufficient=False)
        vt.return_value = VirusTotalResult("malicious", "https://unknown.test/", malicious_count=2)
        result = await verifier.verify("https://unknown.test/")
        self.assertEqual(result['verification_verdict'], 'MALICIOUS')

    async def test_ai_cannot_assert_clean_or_malicious_from_empty_page(self):
        verifier = service()
        for assessment, category in [('clean', 'SAFE_NORMAL'), ('malicious', 'SCAM_MALICIOUS')]:
            verifier.gemini_check = AsyncMock(return_value={
                **await gemini_clean('', None), 'assessment': assessment, 'category': category,
            })
            result = await verifier._gemini_evidence('https://example.com/', extract_page_evidence('https://example.com/', ''))
            self.assertEqual(result['status'], 'uncertain')
            self.assertFalse(result['evidence_sufficient'])
            self.assertIn('ไม่เพียงพอ', result['reason_th'])

    async def test_two_reported_origins_use_generic_mislabeled_html_path(self):
        # Controlled fixtures, not claims about the live sites or their ownership.
        for url in [
            'https://codex-resets.com/?fbclid=synthetic',
            'https://www.sfcinema.com/en/showtime/synthetic?fbclid=synthetic',
            'https://unrelated.test/catalogue?ref=synthetic',
        ]:
            with self.subTest(url=url):
                verifier, gemini, vt, _, _ = candidate(trusted_origins=[])
                verifier.redirect_resolver = SafeRedirectResolver(
                    resolver=public_dns,
                    client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(
                        lambda request: httpx.Response(200, headers={'content-type': 'application/octet-stream'},
                                                      content=('<!doctype html><html><body>' + BENIGN_PAGE + '</body></html>').encode()),
                    ), follow_redirects=False, trust_env=False),
                )
                result = await verifier.verify(url)
                self.assertEqual(result['verification_verdict'], 'NO_THREAT_FOUND')
                gemini.assert_awaited_once()
                vt.assert_not_awaited()

    async def test_risk_memory_failure_prevents_benign_fast_path(self):
        verifier, gemini, vt, _, _ = candidate()
        verifier.risk_check = AsyncMock(return_value={'status': 'error', 'complete': False})
        result = await verifier.verify('https://www.youtube.com/')
        self.assertEqual(result['verification_verdict'], 'INCOMPLETE')
        self.assertIsNone(result['is_safe'])


class RiskMemoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_router_cache_guard_and_pipeline_share_overall_deadline(self):
        db = FakeDatabase()
        db.get_cached_result = lambda *args, **kwargs: (time.sleep(0.02) or None)
        db.get_url_risk_evidence = lambda url: (time.sleep(0.02) or {'status': 'not_listed', 'complete': True})
        verifier, gemini, _, _, _ = candidate()
        cancelled = asyncio.Event()
        async def slow(*args):
            try:
                await asyncio.sleep(1)
            finally:
                cancelled.set()
        gemini.side_effect = slow
        budget = SimpleNamespace(DATABASE_OPERATION_TIMEOUT=0.03, MAX_TOTAL_PROCESSING_TIME=0.08)
        request = fraud.FraudCheckRequest(message='https://unknown.test/', message_type='link')
        with patch.object(fraud, 'get_database_service', return_value=db), patch.object(fraud, 'get_url_verification_service', return_value=verifier), patch.object(fraud, 'get_performance_config', return_value=budget):
            started = time.monotonic()
            result = await fraud._check_link_request(request)
        self.assertLess(time.monotonic()-started, 0.2)
        self.assertEqual(result['verification_verdict'], 'INCOMPLETE')
        self.assertTrue(cancelled.is_set())

    async def test_failed_persistence_or_no_remaining_budget_retains_process_guard(self):
        for persist in [True, False]:
            db = FakeDatabase()
            db.save_url_risk_evidence = MagicMock(return_value=False)
            response = {'original_url': 'https://example.com/', 'final_url': 'https://example.com/',
                        'checks': {'virustotal': {'status': 'suspicious', 'complete': True, 'malicious_count': 1}}}
            self.assertFalse(await save_recent_risk(db, response, persist=persist))
            result = await lookup_recent_risk(db, ['https://example.com/'])
            self.assertEqual(result['status'], 'suspicious')
            self.assertEqual(result['storage'], 'process_memory')
            if not persist:
                db.save_url_risk_evidence.assert_not_called()

    async def test_two_requests_replay_unreadable_vt_positive_then_readable_page(self):
        class Store(FakeDatabase):
            def __init__(self):
                super().__init__()
                self.observations = {}

            def get_url_risk_evidence(self, url):
                return self.observations.get(url, {'status': 'not_listed', 'complete': True})

            def save_url_risk_evidence(self, url, evidence, ttl_seconds):
                super().save_url_risk_evidence(url, evidence, ttl_seconds)
                self.observations[url] = {'status': 'suspicious', 'complete': True, 'evidence': evidence}
                return True

        url = 'https://codex-resets.com/?fbclid=synthetic-replay'
        db = Store()
        verifier, gemini, vt, _, request = candidate(page='', trusted_origins=[])
        vt.return_value = VirusTotalResult('malicious', url, malicious_count=1, suspicious_count=1, total_scanners=92)
        verifier.risk_check = lambda urls: lookup_recent_risk(db, urls)
        fraud_request = fraud.FraudCheckRequest(message=url, message_type='link')
        with patch.object(fraud, 'get_database_service', return_value=db), patch.object(fraud, 'get_url_verification_service', return_value=verifier):
            first = await fraud._check_link_request(fraud_request)
            self.assertEqual(first['verification_verdict'], 'SUSPICIOUS')
            self.assertFalse(first['verification_complete'])
            self.assertTrue(db.saved_risk)
            writes = len(db.saved_risk)
            request.side_effect = lambda _url, _timeout: RedirectHTTPResponse(
                200, {'content-type': 'text/html'}, BENIGN_PAGE.encode(),
            )
            vt.return_value = VirusTotalResult('timeout', url)
            second = await fraud._check_link_request(fraud_request)
        self.assertEqual(second['verification_verdict'], 'SUSPICIOUS')
        self.assertFalse(second['is_safe'])
        self.assertEqual(second['checks']['content']['status'], 'clean')
        self.assertEqual(len(db.saved_risk), writes)
        self.assertEqual(gemini.await_count, 1)
        self.assertEqual(vt.await_count, 2)

    async def test_incomplete_positive_saved_but_clean_never_saved(self):
        db = FakeDatabase()
        response = {
            'original_url': 'https://short.test/one', 'final_url': 'https://destination.test/',
            'verification_complete': False,
            'checks': {'virustotal': {'status': 'suspicious', 'provider_status': 'malicious',
                                      'complete': True, 'malicious_count': 1}},
        }
        self.assertTrue(await save_recent_risk(db, response))
        self.assertEqual(len(db.saved_risk), 2)
        self.assertEqual(db.saved_risk[0][2], 900)
        before = len(db.saved_risk)
        response['checks']['virustotal']['status'] = 'clean'
        self.assertFalse(await save_recent_risk(db, response))
        self.assertEqual(len(db.saved_risk), before)

    async def test_inherited_or_cached_detections_do_not_extend_expiry(self):
        db = FakeDatabase()
        self.assertFalse(await save_recent_risk(db, {
            'original_url': 'https://example.com/', 'checks': {
                'risk_history': {'status': 'suspicious', 'complete': True},
                'virustotal': {'status': 'malicious', 'complete': True, 'cached': True},
            },
        }))
        self.assertFalse(db.saved_risk)

    async def test_recent_positive_beats_cached_benign_and_vt_timeout(self):
        verifier, gemini, vt, _, _ = candidate(vt_status='timeout')
        cached = await service().verify('https://example.com/')
        cached['cached'] = True
        db = FakeDatabase(cached)
        db.risk = {'status': 'suspicious', 'complete': True, 'reason': 'recent_detection_requires_confirmation'}
        verifier.risk_check = AsyncMock(return_value=db.risk)
        request = fraud.FraudCheckRequest(message='https://example.com/', message_type='link')
        with patch.object(fraud, 'get_database_service', return_value=db), patch.object(fraud, 'get_url_verification_service', return_value=verifier):
            result = await fraud._check_link_request(request)
        self.assertEqual(result['verification_verdict'], 'SUSPICIOUS')
        self.assertFalse(result['cached'])
        self.assertFalse(result['is_safe'])
        self.assertFalse(db.saved_results)
        gemini.assert_not_awaited()
        vt.assert_awaited_once()

    async def test_lookup_checks_both_original_and_final(self):
        db = FakeDatabase()
        db.get_url_risk_evidence = MagicMock(side_effect=[
            {'status': 'not_listed', 'complete': True},
            {'status': 'suspicious', 'complete': True},
        ])
        result = await lookup_recent_risk(db, ['https://short.test/', 'https://final.test/'])
        self.assertEqual(result['status'], 'suspicious')
        self.assertEqual(db.get_url_risk_evidence.call_count, 2)

    async def test_slow_risk_lookup_is_bounded(self):
        db = FakeDatabase()
        db.get_url_risk_evidence = lambda url: (time.sleep(0.04) or {'status': 'not_listed', 'complete': True})
        with patch('src.backend.services.url_risk_evidence_service.get_performance_config', return_value=SimpleNamespace(URL_RISK_LOOKUP_TIMEOUT=0.01)):
            started = time.monotonic()
            result = await lookup_recent_risk(db, ['https://example.com/'])
        self.assertLess(time.monotonic() - started, 0.1)
        self.assertEqual(result['status'], 'timeout')


class RiskStorageTests(unittest.TestCase):
    def test_risk_read_budget_is_dedicated_and_does_not_change_writes_or_global(self):
        from src.backend.core.performance_config import PerformanceConfig
        config = PerformanceConfig()
        db, reference = self.db(None)
        self.assertEqual(db.get_url_risk_evidence('https://ordinary.test/')['status'], 'not_listed')
        reference.get.assert_called_once_with(timeout=1.0, retry=None)
        self.assertEqual(config.URL_RISK_READ_TIMEOUT, 1.0)
        self.assertEqual(config.URL_RISK_LOOKUP_TIMEOUT, 1.2)
        self.assertEqual(config.DATABASE_OPERATION_TIMEOUT, 0.5)
        self.assertEqual(config.URL_EXPANSION_TIMEOUT, 3.0)
        self.assertEqual(config.CONTENT_FETCH_TIMEOUT, 2.0)
        self.assertEqual(config.MAX_TOTAL_PROCESSING_TIME, 9.0)

    def test_risk_timeout_preserves_sanitized_diagnostics_never_benign(self):
        from google.api_core.exceptions import DeadlineExceeded
        db, reference = self.db(None)
        reference.get.side_effect = DeadlineExceeded('SECRET_QUERY_AND_CREDENTIAL_MUST_NOT_BE_LOGGED')
        with self.assertLogs('src.backend.services.database_service', level='WARNING') as logs:
            result = db.get_url_risk_evidence('https://ordinary.test/?private=secret')
        self.assertEqual(result['status'], 'timeout')
        self.assertFalse(result['complete'])
        self.assertEqual(result['error_type'], 'DeadlineExceeded')
        self.assertNotIn('SECRET_QUERY', str(result)+str(logs.output))
        self.assertNotIn('ordinary.test', str(logs.output))
        reference.get.assert_called_once_with(timeout=1.0, retry=None)

    def db(self, data):
        instance = DatabaseService.__new__(DatabaseService)
        instance.db = MagicMock()
        reference = instance.db.collection.return_value.document.return_value
        reference.get.return_value = SimpleNamespace(exists=bool(data), to_dict=lambda: data)
        return instance, reference

    def test_expired_positive_is_not_a_permanent_blacklist(self):
        now = datetime.now(timezone.utc)
        db, reference = self.db({'observed_at': now-timedelta(hours=2), 'expires_at': now-timedelta(hours=1)})
        self.assertEqual(db.get_url_risk_evidence('https://example.com/')['status'], 'not_listed')
        self.assertIsNone(reference.get.call_args.kwargs['retry'])
        reference.delete.assert_not_called()

    def test_live_positive_has_provenance_not_a_safe_label(self):
        now = datetime.now(timezone.utc)
        db, _ = self.db({'observed_at': now, 'expires_at': now+timedelta(minutes=10),
                         'evidence': {'virustotal': {'status': 'suspicious'}}})
        result = db.get_url_risk_evidence('https://example.com/')
        self.assertEqual(result['status'], 'suspicious')
        self.assertIn('expires_at', result)

    def test_storage_rejects_negative_write(self):
        db, reference = self.db(None)
        self.assertFalse(db.save_url_risk_evidence('https://example.com/', {'vt': {'status': 'clean'}}, 900))
        reference.set.assert_not_called()

    def test_weak_write_cannot_shorten_live_stronger_record(self):
        now = datetime.now(timezone.utc)
        db, reference = self.db({'observed_at': now, 'expires_at': now+timedelta(minutes=50)})
        self.assertTrue(db.save_url_risk_evidence('https://example.com/', {'vt': {'status': 'suspicious'}}, 900))
        reference.create.assert_not_called()
        reference.update.assert_not_called()

    def test_positive_update_uses_compare_and_set_without_retry(self):
        now = datetime.now(timezone.utc)
        db, reference = self.db({'observed_at': now, 'expires_at': now+timedelta(seconds=10)})
        reference.get.return_value.update_time = now
        self.assertTrue(db.save_url_risk_evidence('https://example.com/', {'vt': {'status': 'malicious'}}, 3600))
        db.db.write_option.assert_called_once_with(last_update_time=now)
        self.assertIsNone(reference.update.call_args.kwargs['retry'])


class ReputationProviderTests(unittest.IsolatedAsyncioTestCase):
    def provider(self, handler, provider='safe_browsing'):
        return URLReputationService(provider=provider, api_key='SYNTHETIC', client_factory=lambda: httpx.AsyncClient(
            transport=httpx.MockTransport(handler), follow_redirects=False, trust_env=False,
        ))

    async def test_disabled_does_not_contact_google(self):
        client = MagicMock()
        result = await URLReputationService(provider='disabled', client_factory=client).check_urls(['https://example.com/'])
        self.assertEqual(result['status'], 'skipped_not_needed')
        client.assert_not_called()

    async def test_no_match_is_not_clean_evidence_and_is_cached(self):
        handler = MagicMock(return_value=httpx.Response(200, json={'cacheDuration': '60s'}))
        provider = self.provider(handler)
        for _ in range(2):
            result = await provider.check_urls(['https://example.com/'])
            self.assertEqual(result['status'], 'not_listed')
        self.assertEqual(handler.call_count, 1)

    async def test_google_threat_match_is_malicious(self):
        provider = self.provider(lambda request: httpx.Response(200, json={
            'threats': [{'url': 'https://example.com/', 'threatTypes': ['SOCIAL_ENGINEERING']}], 'cacheDuration': '30s',
        }))
        self.assertEqual((await provider.check_urls(['https://example.com/']))['status'], 'malicious')

    async def test_web_risk_no_match_and_expiring_match(self):
        provider = self.provider(lambda request: httpx.Response(200, json={}), provider='web_risk')
        self.assertEqual((await provider.check_urls(['https://example.com/']))['status'], 'not_listed')
        expires = (datetime.now(timezone.utc)+timedelta(seconds=30)).isoformat()
        provider = self.provider(lambda request: httpx.Response(200, json={'threat': {'threatTypes': ['MALWARE'], 'expireTime': expires}}), provider='web_risk')
        self.assertEqual((await provider.check_urls(['https://example.com/']))['status'], 'malicious')

    async def test_failures_never_become_clean(self):
        for code, payload in [(429, {}), (503, {}), (200, []), (200, {'threats': 'bad', 'cacheDuration': '60s'})]:
            provider = self.provider(lambda request: httpx.Response(code, json=payload))
            result = await provider.check_urls(['https://example.com/'])
            self.assertNotIn(result['status'], {'clean', 'not_listed'})
            self.assertFalse(result['complete'])

    async def test_provider_timeout_cancels_request(self):
        cancelled = asyncio.Event()
        async def slow(request):
            try:
                await asyncio.sleep(1)
            finally:
                cancelled.set()
        provider = self.provider(slow)
        provider.timeout = 0.01
        result = await provider.check_urls(['https://example.com/'])
        self.assertEqual(result['status'], 'timeout')
        self.assertTrue(cancelled.is_set())

    async def test_missing_key_does_not_contact_google(self):
        client = MagicMock()
        result = await URLReputationService(provider='safe_browsing', api_key='', client_factory=client).check_urls(['https://example.com/'])
        self.assertEqual(result['status'], 'unavailable')
        client.assert_not_called()

    async def test_configured_provider_failure_cannot_enter_trusted_fast_path(self):
        verifier, gemini, vt, _, _ = candidate()
        verifier.reputation_check = AsyncMock(return_value={'status': 'timeout', 'complete': False})
        with patch.object(fraud.settings, 'url_reputation_provider', 'safe_browsing'):
            result = await verifier.verify('https://www.youtube.com/')
        self.assertEqual(result['verification_verdict'], 'INCOMPLETE')
        self.assertTrue(result['checks']['external_reputation']['required'])
        self.assertIsNone(result['is_safe'])

    async def test_provider_expiry_caps_persistent_risk_and_aggregate_cache(self):
        db = FakeDatabase()
        expires = (datetime.now(timezone.utc)+timedelta(seconds=20)).isoformat()
        response = {
            'original_url': 'https://bad.test/', 'final_url': 'https://normal.test/',
            'category': 'SCAM_MALICIOUS', 'is_fraud': True, 'is_safe': False,
            'verification_verdict': 'MALICIOUS',
            'checks': {'external_reputation': {'status': 'malicious', 'complete': True,
                                               'checked_url': 'https://bad.test/', 'evidence_expires_at': expires}},
        }
        self.assertTrue(await save_recent_risk(db, response))
        self.assertEqual(len(db.saved_risk), 1)
        self.assertEqual(db.saved_risk[0][0], 'https://bad.test/')
        self.assertLessEqual(db.saved_risk[0][2], 20)
        fraud._save_complete_link_cache(db, fraud.FraudCheckRequest(message='https://bad.test/'), response, 'synthetic-key')
        self.assertLessEqual(db.saved_results[0]['cache_ttl_days']*86400, 20)
