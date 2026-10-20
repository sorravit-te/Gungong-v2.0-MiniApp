"""Firestore credential transport; no real keys or RPCs."""

import contextlib
import io
import json
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pydantic import SecretStr
from src.backend.core.config import Settings
from src.backend.services import database_service as database



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
