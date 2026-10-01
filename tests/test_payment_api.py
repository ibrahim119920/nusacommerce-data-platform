"""Day 3 failure policies without real delays or external APIs."""
import unittest
from unittest.mock import Mock
import requests
from nusacommerce.ingestion.payment_api import PaymentApiClient, PaymentApiError, PaymentPage
from nusacommerce.ingestion.payment_service import PaymentIngestionService


def response(status, body=None, headers=None):
    result = Mock(status_code=status, headers=headers or {})
    result.json.return_value = body
    return result


class PaymentApiTests(unittest.TestCase):
    def client(self, results):
        session, sleeper = Mock(), Mock()
        session.get.side_effect = results
        return PaymentApiClient("http://fixture", session=session, sleeper=sleeper), session, sleeper

    def test_429_retries_same_cursor(self):
        client, session, sleeper = self.client([
            response(429, headers={"Retry-After":"2"}),
            response(200,{"data":[],"next_cursor":None})])
        self.assertEqual(client.fetch_page("cursor2").data, [])
        self.assertEqual(session.get.call_count,2)
        self.assertEqual(session.get.call_args_list[0],session.get.call_args_list[1])
        sleeper.assert_called_once_with(2)

    def test_503_stops_at_three_attempts(self):
        client, session, sleeper = self.client([response(503)]*3)
        with self.assertRaises(PaymentApiError):
            client.fetch_page()
        self.assertEqual(session.get.call_count,3)
        self.assertEqual(sleeper.call_count,2)

    def test_401_not_retried(self):
        client, session, sleeper = self.client([response(401)])
        with self.assertRaises(PaymentApiError):
            client.fetch_page()
        self.assertEqual(session.get.call_count,1)
        sleeper.assert_not_called()

    def test_timeout_then_success(self):
        client, session, _ = self.client([
            requests.Timeout(),response(200,{"data":[],"next_cursor":None})])
        client.fetch_page()
        self.assertEqual(session.get.call_count,2)

    def test_invalid_response_shape(self):
        client, _, _ = self.client([response(200,{"data":"wrong","next_cursor":None})])
        with self.assertRaises(PaymentApiError):
            client.fetch_page()

    def test_persistence_failure_stops_pagination(self):
        client, repo = Mock(), Mock()
        client.fetch_page.return_value = PaymentPage([{"payment_id":"p"}],"next")
        repo.insert_page.side_effect = RuntimeError()
        with self.assertRaises(RuntimeError):
            PaymentIngestionService(client,repo).run()
        self.assertEqual(client.fetch_page.call_count,1)

    def test_repeated_cursor_stops(self):
        client, repo = Mock(), Mock()
        client.fetch_page.return_value = PaymentPage([],"same")
        repo.insert_page.return_value = 0
        with self.assertRaises(PaymentApiError):
            PaymentIngestionService(client,repo).run()
        self.assertEqual(client.fetch_page.call_count,2)
