"""Offline Docker fixture: real sandboxed Chromium, controlled HTTP resources.

Not copied into the worker image. Mount only this test file read-only; never
mount the repository or credentials. No external/provider/Firestore calls.
"""

import asyncio
import importlib.util
import json
import os
import sys
import time
from unittest.mock import patch

import httpx

sys.path.insert(0, '/app')

from src.backend.services import renderer_worker_app as worker
from src.backend.services import url_renderer_service as renderer_module
from src.backend.services.url_renderer_service import BoundedPageRenderer, ResourceResponse
from src.backend.services.url_safety_service import validate_public_url

TEXT = 'Our public community library provides books, educational resources, opening hours and local events for visitors.'


async def fixture_dns(_hostname, _port):
    return ['93.184.216.34']


async def fixture_validate(url):
    return await validate_public_url(url, fixture_dns)


async def main():
    worker.assert_worker_environment()
    assert importlib.util.find_spec('google') is None, 'No Google SDK belongs in worker'
    assert not os.path.exists('/app/src/backend/main.py')
    assert not os.path.exists('/app/src/backend/services/database_service.py')
    fetches = []

    async def fetch(url, _timeout, _max_bytes):
        fetches.append(url)
        if url.startswith('http://'):
            raise AssertionError('Private target must not reach resource fetcher')
        if url.endswith('.js'):
            if url.endswith('/risk.js'):
                script = "document.body.innerHTML='<p>Bank login password verification. Enter your password to restore your banking account immediately.</p><form><input type=password><input name=otp></form>';"
            elif url.endswith('/private.js'):
                script = "location.href='http://169.254.169.254/latest/meta-data/';"
            elif url.endswith('/missing.js'):
                return ResourceResponse(404, {'content-type': 'text/javascript'}, b'')
            elif url.endswith('/slow.js'):
                script = "setTimeout(() => { document.body.textContent='late page'; }, 10000);"
            else:
                script = f'document.body.textContent={TEXT!r};'
            return ResourceResponse(200, {'content-type': 'text/javascript'}, script.encode())
        case = url.rsplit('/', 1)[-1]
        if case not in {'benign', 'risk', 'private', 'denied', 'missing', 'slow'}:
            raise AssertionError('Unexpected fixture resource')
        body = f'<html><body>{TEXT if case in {"denied", "missing"} else ""}<div id=root></div>'
        if case != 'denied':
            body += f'<script src="/{case}.js"></script>'
        return ResourceResponse(403 if case == 'denied' else 200, {'content-type': 'text/html'}, (body + '</body></html>').encode())

    engine = BoundedPageRenderer(fetcher=fetch, max_concurrency=1)
    app = worker.create_app(engine)
    if '--serve' in sys.argv:
        # Test-only controlled source. This file is NOT in the worker image.
        import uvicorn
        from fastapi import HTTPException, Request

        @app.get('/fixture/state')
        async def fixture_state(request: Request):
            if request.headers.get('authorization') != 'Bearer ' + os.environ['URL_RENDER_WORKER_TOKEN']:
                raise HTTPException(403)
            active_browsers = 0
            for entry in os.listdir('/proc'):
                if not entry.isdigit():
                    continue
                try:
                    with open('/proc/' + entry + '/comm') as proc_file:
                        name = proc_file.read().strip()
                    with open('/proc/' + entry + '/status') as proc_file:
                        zombie = any(line.startswith('State:') and '\tZ' in line for line in proc_file)
                    if (name.startswith('chrome') or name == 'node') and not zombie:
                        active_browsers += 1
                except (OSError, ProcessLookupError):
                    pass
            return {'available_slots': engine._slots._value, 'active_browser_processes': active_browsers}
        with patch.object(worker, 'validate_public_url', fixture_validate), patch.object(
            renderer_module, 'validate_public_url', fixture_validate,
        ):
            await uvicorn.Server(uvicorn.Config(app, host='0.0.0.0', port=8071,
                                               access_log=False, log_level='warning')).serve()
        return
    headers = {'Authorization': 'Bearer ' + os.environ['URL_RENDER_WORKER_TOKEN']}
    results = []
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://worker') as client:
        with patch.object(worker, 'validate_public_url', fixture_validate):
            for case in ['benign', 'risk', 'private', 'denied', 'missing']:
                started = time.monotonic()
                response = await client.post('/render', headers=headers, json={'url': 'https://spa.test/' + case})
                assert response.status_code == 200
                data = response.json()
                if case in {'benign', 'risk'}:
                    assert data['status'] == 'clean' and data['complete'] is True, data.get('reason')
                    assert len(data['visible_text']) >= 80
                    if case == 'risk':
                        assert 'type="password"' in data['html']
                elif case == 'private':
                    assert data['status'] == 'blocked', (data['status'], data.get('reason'))
                else:
                    assert data['status'] != 'clean' and data['complete'] is False
                assert engine._slots._value == 1
                results.append({'case': case, 'status': data['status'], 'complete': data['complete'],
                                'visible_text_chars': len(data.get('visible_text', '')),
                                'duration_s': round(time.monotonic() - started, 3)})
        private = await client.post('/render', headers=headers, json={'url': 'http://169.254.169.254/'})
        assert private.json()['status'] == 'blocked'
        assert (await client.post('/render', json={'url': 'https://spa.test/benign'})).status_code == 403
    assert all(url.startswith('https://spa.test/') for url in fetches)
    print(json.dumps({'offline_fixture': 'PASS', 'sandbox': True, 'provider_calls': 0,
                      'firestore_calls': 0, 'results': results}, ensure_ascii=False))


if __name__ == '__main__':
    asyncio.run(main())
