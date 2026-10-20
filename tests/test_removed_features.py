"""Removed surfaces return 404; no provider calls or database writes."""
import unittest

import httpx

from src.backend.main import app


class RemovedFeatureTests(unittest.IsolatedAsyncioTestCase):
    async def test_personal_verification_endpoints_are_not_exposed(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url='http://fixture.test') as client:
            for endpoint in ['/check-phone', '/check-bank', '/api/v2/verify-phone',
                             '/api/v2/verify-bank', '/api/v2/verify-social',
                             '/api/v2/verify-id-card', '/api/v2/verify-id-number']:
                with self.subTest(path=endpoint):
                    response = await client.post(endpoint, json={})
                    self.assertEqual(response.status_code, 404)
        active_routes = {route.path for route in app.routes}
        self.assertIn('/check-fraud', active_routes)
        self.assertIn('/api/history-shares', active_routes)


if __name__ == '__main__':
    unittest.main()
