"""Relocation checks only: no external requests, scripts or database writes."""
import ast
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ProjectStructureTests(unittest.TestCase):
    def test_vercel_and_api_entrypoints_are_unchanged(self):
        config = json.loads((ROOT / 'vercel.json').read_text(encoding='utf-8'))
        self.assertEqual(config['services']['web']['root'], 'src/frontend')
        self.assertEqual(config['services']['api']['entrypoint'], 'Dockerfile')
        docker = (ROOT / 'Dockerfile').read_text(encoding='utf-8')
        self.assertIn('uvicorn src.backend.main:app', docker)
        self.assertNotIn('deploy/local-url-renderer', docker)

    def test_local_renderer_copy_sources_and_repo_root_still_resolve(self):
        directory = ROOT / 'deploy/local-url-renderer'
        docker = (directory / 'Dockerfile').read_text(encoding='utf-8')
        self.assertIn('COPY deploy/local-url-renderer/requirements.txt', docker)
        self.assertIn('src.backend.services.renderer_worker_app', docker)
        self.assertEqual(directory.resolve().parents[1], ROOT)
        self.assertTrue((ROOT / 'src/backend/services/renderer_worker_app.py').is_file())
        self.assertNotIn('onrender.com', docker)

    def test_data_scripts_resolve_root_without_executing_them(self):
        for source in (ROOT / 'scripts/data').glob('*.py'):
            with self.subTest(file=source.name):
                text = source.read_text(encoding='utf-8')
                ast.parse(text)
                self.assertEqual(source.resolve().parents[2], ROOT)
                self.assertTrue("parents[2]" in text or "'..', '..'" in text)

    def test_frontend_filenames_public_assets_and_inactive_verify_are_retained(self):
        for filename in ['verify.jsx', 'IDCardScanner.jsx', 'verify.css']:
            self.assertTrue((ROOT / 'src/frontend/src/legacy/verify' / filename).is_file())
        self.assertTrue((ROOT / 'src/frontend/public/img/logo.png').is_file())
        self.assertTrue((ROOT / 'src/frontend/src/features/scanner/scanner.jsx').is_file())


if __name__ == '__main__':
    unittest.main()
