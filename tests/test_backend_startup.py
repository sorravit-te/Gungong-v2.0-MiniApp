"""Cold imports and real TF-IDF behavior, without provider/database requests."""

import contextlib
import io
import builtins
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.backend.services.fraud_message_service import FraudMessageService
from src.backend.services import similarity_service


class BackendStartupTests(unittest.TestCase):
    def test_cold_app_import_does_not_load_unused_sklearn(self):
        # A fresh interpreter prevents another test's sklearn cache hiding an
        # eager import. Import every router, not only the health module.
        result = subprocess.run(
            [sys.executable, '-c',
             'import sys; import src.backend.main; '
             'assert not any(m == "sklearn" or m.startswith("sklearn.") '
             'for m in sys.modules); print("LAZY_ML_PASS")'],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, 'Cold import failed; output withheld')
        self.assertIn('LAZY_ML_PASS', result.stdout)

    def test_deduplication_still_computes_real_similarity(self):
        db = MagicMock()
        doc = SimpleNamespace(id='fixture', to_dict=lambda: {
            'message_text': 'fraud investment guaranteed profit',
        })
        db.collection.return_value.limit.return_value.stream.return_value = [doc]
        service = FraudMessageService(SimpleNamespace(db=db))
        tokenizer = SimpleNamespace(word_tokenize=lambda text, engine: text.split())
        real_import = builtins.__import__

        def import_without_corpus_download(name, *args, **kwargs):
            return tokenizer if name == 'pythainlp.tokenize' else real_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=import_without_corpus_download):
            result = service._find_similar_message('fraud investment guaranteed profit')
        self.assertEqual(result['id'], 'fixture')
        self.assertAlmostEqual(result['similarity'], 1.0)

    def test_empty_deduplication_does_not_need_ml(self):
        db = MagicMock()
        db.collection.return_value.limit.return_value.stream.return_value = []
        service = FraudMessageService(SimpleNamespace(db=db))
        self.assertIsNone(service._find_similar_message('fixture message'))

    def test_similarity_service_still_loads_vectors_and_scores(self):
        provider = MagicMock()
        provider.get_all_fraud_messages.return_value = [{
            'message_text': 'fraud investment guaranteed profit',
            'category': 'SCAM_MALICIOUS', 'confidence_score': 90,
        }]
        service = similarity_service.SimilarityService()
        with patch.object(similarity_service, 'get_fraud_message_service', return_value=provider), \
                patch.object(service, 'tokenize_thai', side_effect=lambda text: text), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(service.load_fraud_messages_from_db(), 1)
            result = service.calculate_danger_score('fraud investment guaranteed profit')
        self.assertAlmostEqual(result['similarity_score'], 1.0)
        self.assertEqual(result['danger_percentage'], 100.0)
        self.assertEqual(result['similar_messages'][0]['classification'], 'SCAM_MALICIOUS')


if __name__ == '__main__':
    unittest.main()
