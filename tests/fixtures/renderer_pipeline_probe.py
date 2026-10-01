"""Host API -> actual HTTP -> isolated Docker Chromium -> staged verdict.

Use only with the controlled fixture server. All AI/reputation responses are
mocks; no provider, database, history or external website requests are made.
"""

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

from pydantic import SecretStr
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.backend.core.config import settings
from tests.test_url_staged_routing import candidate


async def main():
    logging.disable(logging.CRITICAL)
    results = []
    for case, expected in [('benign', 'NO_THREAT_FOUND'), ('risk', 'SUSPICIOUS'), ('private', 'INVALID')]:
        shell = f'<html><body><div id=root></div><script src="/{case}.js"></script></body></html>'
        verifier, gemini, vt, _, _ = candidate(page=shell, vt_status='timeout', gemini_result={
            'assessment': 'clean', 'evidence_sufficient': True, 'category': 'SAFE_NORMAL',
            'confidence_score': 90, 'reason_th': 'เป็นหน้าข้อมูลห้องสมุด ไม่มีการขอข้อมูลหรือชำระเงิน',
        })
        verifier.render_check = verifier._default_render_check
        started = time.monotonic()
        with patch.object(settings, 'url_render_enabled', True), patch.object(
            settings, 'url_render_worker_url', 'http://127.0.0.1:8071',
        ), patch.object(settings, 'url_render_worker_token', SecretStr(os.environ['URL_RENDER_WORKER_TOKEN'])):
            result = await verifier.verify('https://spa.test/' + case)
        assert result['verification_verdict'] == expected, (case, result['verification_verdict'], result['checks'].get('render'))
        assert result['checks']['render']['source'] == 'isolated_local_worker'
        if case == 'benign':
            gemini.assert_awaited_once()
            vt.assert_not_awaited()
            assert result['checks']['content']['source'] == 'bounded_rendered_page_evidence'
        elif case == 'risk':
            gemini.assert_not_awaited()
            vt.assert_awaited_once()
            assert result['checks']['virustotal']['status'] == 'timeout'
        else:
            gemini.assert_not_awaited()
            vt.assert_not_awaited()
        elapsed = time.monotonic() - started
        assert elapsed < 9
        results.append({'case': case, 'verdict': expected, 'duration_s': round(elapsed, 3),
                        'gemini_mock_calls': gemini.await_count, 'vt_mock_calls': vt.await_count})
    headers = {'Authorization': 'Bearer ' + os.environ['URL_RENDER_WORKER_TOKEN']}
    async with httpx.AsyncClient(trust_env=False, timeout=0.6) as client:
        try:
            await client.post('http://127.0.0.1:8071/render', headers=headers,
                              json={'url': 'https://spa.test/slow', 'timeout': 4.0})
            raise AssertionError('Slow worker should outlast the controlled client timeout')
        except httpx.TimeoutException:
            pass
    cleanup_started = time.monotonic()
    async with httpx.AsyncClient(trust_env=False, timeout=1) as client:
        while time.monotonic() - cleanup_started < 2.4:
            state = (await client.get('http://127.0.0.1:8071/fixture/state', headers=headers)).json()
            if state['available_slots'] == 1 and state['active_browser_processes'] == 0:
                break
            await asyncio.sleep(0.05)
        else:
            raise AssertionError('Disconnected request left owned browser work running')
    results.append({'case': 'caller_disconnect', 'cleanup_s': round(time.monotonic() - cleanup_started, 3),
                    'active_browser_processes': 0})
    print(json.dumps({'isolated_pipeline': 'PASS', 'live_provider_calls': 0, 'firestore_calls': 0,
                      'results': results}, ensure_ascii=False))


if __name__ == '__main__':
    asyncio.run(main())
