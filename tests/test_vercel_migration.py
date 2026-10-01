"""Deployment contract and credential transport; no real keys or RPCs."""

import contextlib
import ast
import io
import json
import os
import re
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from pydantic import SecretStr
from src.backend.core.config import Settings
from src.backend.services import database_service as database

ROOT = Path(__file__).resolve().parents[1]


class VercelConfigurationTests(unittest.TestCase):
    @staticmethod
    def service_for(url):
        """Contract model; actual Vercel routing needs CLI/preview validation."""
        path = urlsplit(url).path
        config = json.loads((ROOT / 'vercel.json').read_text(encoding='utf-8'))
        for rule in config['rewrites']:
            source = rule['source']
            if source == '/(.*)':
                return rule['destination']['service']
            prefix = source.removesuffix('/:path*')
            if path == prefix or (source.endswith('/:path*') and path.startswith(prefix + '/')):
                return rule['destination']['service']
        raise AssertionError('Missing catch-all')

    def test_static_frontend_and_existing_container_share_one_origin(self):
        config = json.loads((ROOT / 'vercel.json').read_text(encoding='utf-8'))
        self.assertNotIn('experimentalServices', config)
        self.assertTrue(config['fluid'])
        self.assertEqual(config['regions'], ['sin1'])
        self.assertIs(config['trailingSlash'], False)
        self.assertEqual(config['services']['api'], {
            'root': '.', 'runtime': 'container', 'entrypoint': 'Dockerfile',
        })
        self.assertEqual(config['services']['web'], {
            'root': 'src/frontend', 'framework': 'vite', 'installCommand': 'npm ci',
            'buildCommand': 'npm run build', 'outputDirectory': 'dist',
        })
        self.assertEqual(config['rewrites'][-1],
                         {'source': '/(.*)', 'destination': {'service': 'web'}})
        self.assertNotIn('onrender.com', json.dumps(config))
        dockerfile = (ROOT / 'Dockerfile').read_text(encoding='utf-8')
        self.assertIn('npm run build', dockerfile)
        self.assertIn('/build/src/frontend/dist ./src/backend/static', dockerfile)
        self.assertIn('USER appuser', dockerfile)
        self.assertIn('${PORT:-10000}', dockerfile)

    def test_all_declared_backend_routes_are_routed_without_prefix_changes(self):
        route_count = 0
        for source_file in (ROOT / 'src/backend/routers').glob('*.py'):
            tree = ast.parse(source_file.read_text(encoding='utf-8'))
            prefix = ''
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'APIRouter':
                    for keyword in node.keywords:
                        if keyword.arg == 'prefix':
                            prefix = ast.literal_eval(keyword.value)
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name) and node.func.value.id == 'router'
                        and node.func.attr in {'get', 'post', 'put', 'patch', 'delete'}):
                    route = prefix + ast.literal_eval(node.args[0])
                    path = re.sub(r'\{[^}]+\}', 'fixture-entry', route)
                    with self.subTest(path=path):
                        self.assertEqual(self.service_for(path), 'api')
                        self.assertEqual(self.service_for(path + '/'), 'api')
                    route_count += 1
        self.assertGreaterEqual(route_count, 20)

    def test_frontend_paths_do_not_start_api_container(self):
        for path in ['/', '/assets/index.js', '/img/logo.png', '/scanner', '/check-fraud-lookalike']:
            with self.subTest(path=path):
                self.assertEqual(self.service_for(path), 'web')

    def test_queries_nested_routes_and_unknown_api_paths_stay_on_backend(self):
        for path in ['/cache-entries?limit=10', '/history/fixture-entry',
                     '/api/v2/verify-id-card', '/api/not-a-real-endpoint', '/openapi.json']:
            with self.subTest(path=path):
                self.assertEqual(self.service_for(path), 'api')

    def test_local_vercel_link_and_environment_artifacts_are_not_tracked(self):
        lines = (ROOT / '.gitignore').read_text(encoding='utf-8').splitlines()
        self.assertIn('.vercel/', lines)
        self.assertIn('!.env.*.example', lines)
        self.assertNotIn('.env*', lines, 'CLI linking must not hide tracked-safe example templates')

    def test_upload_and_container_context_exclude_secret_files(self):
        for filename in ['.vercelignore', '.dockerignore']:
            lines = (ROOT / filename).read_text(encoding='utf-8').splitlines()
            for protected in ['.env', '.env.*', 'secrets', '**/secrets',
                              'service-account.json', '**/service-account.json', '*.pem', '*.key']:
                self.assertTrue(protected in lines or '**/' + protected in lines, (filename, protected))

    def test_environment_template_does_not_enable_browser_or_uploads(self):
        template = (ROOT / '.env.vercel.example').read_text(encoding='utf-8')
        self.assertIn('GOOGLE_SERVICE_ACCOUNT_JSON=', template)
        self.assertIn('URL_RENDER_ENABLED=false', template)
        self.assertIn('VIRUSTOTAL_SUBMIT_UNKNOWN_URLS=false', template)
        self.assertIn('PORT=10000', template)
        self.assertNotIn('GOOGLE_APPLICATION_CREDENTIALS=', template)
        self.assertNotIn('BEGIN PRIVATE KEY', template)


class InlineFirestoreCredentialTests(unittest.TestCase):
    def initialize(self, secret=None, path=None, emulator=False, credential_error=None):
        settings = SimpleNamespace(firestore_project_id='fixture-project',
                                   google_service_account_json=SecretStr(secret) if secret is not None else None,
                                   google_application_credentials=path)
        output = io.StringIO()
        with patch.dict(os.environ, {'USE_FIREBASE_EMULATOR': str(emulator).lower()}, clear=True), \
             patch.object(database, 'settings', settings), \
             patch.object(database.firestore, 'Client') as client, \
             patch.object(database.service_account.Credentials, 'from_service_account_info', side_effect=credential_error) as credentials, \
             contextlib.redirect_stdout(output):
            try:
                database.DatabaseService()
            except Exception as exc:
                return client, credentials, output.getvalue(), exc
        return client, credentials, output.getvalue(), None

    def test_inline_credentials_are_passed_without_creating_file_or_using_old_path(self):
        info = {'type': 'service_account', 'private_key': 'fixture-secret', 'project_id': 'fixture-project'}
        client, credentials, output, error = self.initialize(json.dumps(info), '/etc/secrets/missing.json')
        self.assertIsNone(error)
        credentials.assert_called_once_with(info)
        client.assert_called_once_with(project='fixture-project', database='(default)', credentials=credentials.return_value)
        self.assertNotIn('fixture-secret', output)
        self.assertNotIn('CREDENTIALS', output)

    def test_missing_inline_credentials_preserves_existing_adc_behavior(self):
        client, credentials, _, error = self.initialize()
        self.assertIsNone(error)
        credentials.assert_not_called()
        client.assert_called_once_with(project='fixture-project', database='(default)')

    def test_existing_file_configuration_is_preserved(self):
        client, credentials, output, error = self.initialize(path='/fixture/credentials.json')
        self.assertIsNone(error)
        credentials.assert_not_called()
        client.assert_called_once_with(project='fixture-project', database='(default)')
        self.assertIn('Set GOOGLE_APPLICATION_CREDENTIALS', output)

    def test_invalid_json_or_wrong_credential_type_does_not_fall_back(self):
        for secret in ['', 'fixture-secret-invalid-json', '[]', '{"type":"authorized_user"}']:
            with self.subTest(value_length=len(secret)):
                client, credentials, output, error = self.initialize(secret)
                self.assertIsInstance(error, ValueError)
                self.assertEqual(str(error), 'Invalid GOOGLE_SERVICE_ACCOUNT_JSON configuration')
                client.assert_not_called()
                credentials.assert_not_called()
                self.assertNotIn('fixture-secret', output)

    def test_provider_error_does_not_expose_key_in_logs_or_exception(self):
        client, _, output, error = self.initialize(
            '{"type":"service_account"}', credential_error=ValueError('fixture-private-key-secret'),
        )
        client.assert_not_called()
        self.assertIsInstance(error, ValueError)
        self.assertNotIn('fixture-private-key-secret', str(error) + output)

    def test_emulator_does_not_parse_or_send_inline_credentials(self):
        client, credentials, _, error = self.initialize('invalid-unused-secret', emulator=True)
        self.assertIsNone(error)
        credentials.assert_not_called()
        client.assert_called_once_with(project='fixture-project', database='(default)')

    def test_explicit_database_id_is_preserved(self):
        with patch.dict(os.environ, {'FIRESTORE_DATABASE_ID': 'fixture-db'}, clear=True), \
             patch.object(database, 'settings', SimpleNamespace(
                 firestore_project_id='fixture-project', google_service_account_json=SecretStr('{"type":"service_account"}'),
                 google_application_credentials=None)), \
             patch.object(database.firestore, 'Client') as client, \
             patch.object(database.service_account.Credentials, 'from_service_account_info') as credentials, \
             contextlib.redirect_stdout(io.StringIO()):
            database.DatabaseService()
        client.assert_called_once_with(project='fixture-project', database='fixture-db', credentials=credentials.return_value)

    def test_settings_repr_masks_server_side_secret(self):
        config = Settings(_env_file=None, google_service_account_json='fixture-private-key-secret')
        self.assertNotIn('fixture-private-key-secret', repr(config))
        self.assertEqual(config.google_service_account_json.get_secret_value(), 'fixture-private-key-secret')


if __name__ == '__main__':
    unittest.main()
