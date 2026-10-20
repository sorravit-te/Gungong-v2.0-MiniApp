"""Message payload checks only: no external LINE or database requests."""
import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from linebot.v3.messaging.models import FlexContainer
from src.backend.services.line_service import LineService
from src.backend.utils.result_presentation import resolve_result_verdict


def texts(value):
    if isinstance(value, dict):
        if value.get('type') == 'text':
            yield value.get('text', '')
        for child in value.values():
            yield from texts(child)
    elif isinstance(value, list):
        for child in value:
            yield from texts(child)


class ResultMessagePresentationTests(unittest.TestCase):
    def test_shared_link_qr_text_contract_matches_actual_flex_designs(self):
        cases = json.loads((Path(__file__).parent / 'fixtures/result_presentation_cases.json').read_text(encoding='utf-8'))
        colors = {'green': '#4AB918', 'red': '#FF3B30', 'yellow': '#FF9500'}
        for case in cases:
            with self.subTest(name=case['name']):
                source = case['result']
                original = json.dumps(source)
                if case['type'] in {'link', 'qr'}:
                    message = LineService.create_url_verification_flex_message(None, source)
                else:
                    message = LineService.create_fraud_flex_message(None, source.get('category'),
                        source.get('is_fraud'), is_safe=source.get('is_safe'),
                        url_check=source.get('url_check'), has_malicious_urls=source.get('has_malicious_urls', False))
                self.assertEqual(message['contents']['styles']['body']['backgroundColor'], colors[case['tone']])
                self.assertIsNotNone(FlexContainer.from_dict(message['contents']))
                self.assertNotIn('ปลอดภัย', ' '.join(texts(message)))
                self.assertFalse(any('%' in text for text in texts(message)))
                self.assertEqual(json.dumps(source), original)

    def test_missing_and_conflicting_text_flags_never_make_unknown_green(self):
        self.assertEqual(resolve_result_verdict({'is_fraud': False, 'is_safe': False}), 'INCOMPLETE')
        self.assertEqual(resolve_result_verdict({'is_fraud': True, 'is_safe': True}), 'SUSPICIOUS')

    def test_text_results_keep_designs_but_hide_scores_and_open_history(self):
        for fraud in [True, False]:
            with self.subTest(fraud=fraud):
                message = LineService.create_fraud_flex_message(None, 'TEST', fraud,
                    history_id='stored_record', confidence_score=97,
                    similarity_data={'danger_analysis': {'danger_percentage': 95}})
                self.assertFalse(any('%' in text or 'ความมั่นใจ' in text for text in texts(message)))
                query = parse_qs(urlsplit(message['contents']['body']['action']['uri']).query)
                self.assertEqual(query, {'section': ['history'], 'historyId': ['stored_record']})
                self.assertIsNotNone(FlexContainer.from_dict(message['contents']))

    def test_url_results_open_the_saved_record_without_changing_verdict(self):
        for verdict in ['NO_THREAT_FOUND', 'SUSPICIOUS', 'MALICIOUS', 'INCOMPLETE', 'INVALID']:
            with self.subTest(verdict=verdict):
                source = {'verification_verdict': verdict, 'history_id': 'owned-record'}
                before = json.dumps(source)
                message = LineService.create_url_verification_flex_message(None, source)
                query = parse_qs(urlsplit(message['contents']['body']['action']['uri']).query)
                self.assertEqual(query, {'section': ['history'], 'historyId': ['owned-record']})
                self.assertFalse(any('%' in text for text in texts(message)))
                self.assertEqual(json.dumps(source), before)

    def test_missing_or_untrusted_record_id_opens_history_list(self):
        for history_id in [None, '../../private', 'x&section=report', 'a' * 129]:
            message = LineService.create_fraud_flex_message(None, 'TEST', False, history_id=history_id)
            query = parse_qs(urlsplit(message['contents']['body']['action']['uri']).query)
            self.assertEqual(query, {'section': ['history']})
