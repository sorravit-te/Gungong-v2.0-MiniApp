"""Message payload checks only: no external LINE or database requests."""
import json
import unittest
from urllib.parse import urlsplit, parse_qs
from linebot.v3.messaging.models import FlexContainer
from src.backend.services.line_service import LineService
from src.backend.utils.flex_templates import create_id_card_verification_flex


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

    def test_remaining_legacy_id_card_template_has_no_risk_percentage(self):
        for blacklisted, valid in [(True, True), (False, True), (False, False)]:
            message = create_id_card_verification_flex('test', 'Name', 'Surname', 'date', 'address',
                blacklisted, valid, 'LOW', 0)
            self.assertFalse(any('%' in text for text in texts(message.to_dict())))
