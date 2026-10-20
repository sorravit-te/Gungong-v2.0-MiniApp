"""Relocation checks only: no external requests, scripts or database writes."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ProjectStructureTests(unittest.TestCase):
    def test_cloud_deployment_files_are_not_included(self):
        for filename in ['vercel.json', '.vercelignore', 'Dockerfile',
                         'env.example/.env.vercel.example', 'env.example/.env.example',
                         'docs']:
            with self.subTest(file=filename):
                self.assertFalse((ROOT / filename).exists())
        self.assertEqual(list((ROOT / 'scripts/legacy/cloud-run').glob('*.sh')), [])
        self.assertTrue((ROOT / 'src/backend/main.py').is_file())

    def test_readme_consolidates_essential_notes_and_existing_mascots(self):
        readme = (ROOT / 'README.md').read_text(encoding='utf-8')
        for index in range(1, 5):
            asset = f'src/frontend/public/img/mascot_{index:02d}.png'
            self.assertIn(f'src="{asset}"', readme)
            self.assertTrue((ROOT / asset).is_file())
        for note in ['expire after 7 days', 'emulator only', 'VITE_*',
                     'not guarantees of safety', 'Git history']:
            self.assertIn(note, readme)
        for overview in ['LINE MINI App', '## What you can do', '## Tech stack',
                         'Gemini 3.5 Flash-Lite', 'Share Target Picker',
                         'Cloud Firestore', 'LangChain']:
            self.assertIn(overview, readme)
        self.assertNotIn('verification are not supported', readme)
        for source in [ROOT / 'README.md', ROOT / 'src/frontend/README.md',
                       ROOT / 'scripts/local-url-renderer/README.md']:
            self.assertNotIn('](../../docs/', source.read_text(encoding='utf-8'))

    def test_local_renderer_copy_sources_and_repo_root_still_resolve(self):
        directory = ROOT / 'scripts/local-url-renderer'
        docker = (directory / 'Dockerfile').read_text(encoding='utf-8')
        self.assertIn('COPY scripts/local-url-renderer/requirements.txt', docker)
        self.assertIn('src.backend.services.renderer_worker_app', docker)
        self.assertEqual(directory.resolve().parents[1], ROOT)
        self.assertTrue((ROOT / 'src/backend/services/renderer_worker_app.py').is_file())
        self.assertNotIn('onrender.com', docker)

    def test_secrets_and_local_worker_build_context_remain_excluded(self):
        ignored = (ROOT / '.gitignore').read_text(encoding='utf-8').splitlines()
        for filename in ['.env', '.env.*', 'secrets/', 'service-account.json', '*.pem', '*.key']:
            self.assertIn(filename, ignored)
        self.assertIn('!.env.example', ignored)
        context = (ROOT / '.dockerignore').read_text(encoding='utf-8').splitlines()
        for filename in ['.env', '.env.*', 'secrets', '**/secrets',
                         'service-account.json', '**/service-account.json', '*.pem', '*.key']:
            self.assertIn(filename, context)

    def test_data_scripts_resolve_root_without_executing_them(self):
        for source in (ROOT / 'scripts/data').glob('*.py'):
            with self.subTest(file=source.name):
                text = source.read_text(encoding='utf-8')
                ast.parse(text)
                self.assertEqual(source.resolve().parents[2], ROOT)
                self.assertTrue("parents[2]" in text or "'..', '..'" in text)

    def test_removed_verification_sources_are_absent_and_active_scanner_remains(self):
        for filename in ['verify.jsx', 'IDCardScanner.jsx', 'verify.css']:
            self.assertFalse((ROOT / 'src/frontend/src/legacy/verify' / filename).exists())
        self.assertTrue((ROOT / 'src/frontend/public/img/logo.png').is_file())
        self.assertTrue((ROOT / 'src/frontend/src/features/scanner/scanner.jsx').is_file())


if __name__ == '__main__':
    unittest.main()
