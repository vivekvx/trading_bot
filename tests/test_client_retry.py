"""
Tests for the retry/timeout logic in bot/client.py.

These specifically exercise the safety property that matters for order
placement: a network timeout must never result in a duplicate order, and a
definitive API rejection must never be retried.

Run with:
    python -m unittest discover tests
"""

import unittest
from unittest.mock import MagicMock, patch

import requests.exceptions
from binance.exceptions import BinanceAPIException

from bot.client import BinanceClientError, FuturesTestnetClient


def make_client_with_mocked_binance():
    """
    Build a FuturesTestnetClient with its internal python-binance Client
    replaced by a MagicMock, so no real network calls happen.
    """
    with patch("bot.client.Client") as MockClient:
        instance = FuturesTestnetClient("fake_key", "fake_secret")
        return instance, MockClient.return_value


class TestRetryLogic(unittest.TestCase):
    def test_success_on_first_attempt_no_retry(self):
        client, mock_binance = make_client_with_mocked_binance()
        mock_binance.futures_create_order.return_value = {
            "symbol": "BTCUSDT", "orderId": 1, "status": "FILLED",
            "executedQty": "0.01", "avgPrice": "65000",
        }
        result = client.create_order("BTCUSDT", "BUY", "MARKET", 0.01)
        self.assertEqual(result["orderId"], 1)
        self.assertEqual(mock_binance.futures_create_order.call_count, 1)

    def test_definitive_api_rejection_is_never_retried(self):
        client, mock_binance = make_client_with_mocked_binance()
        mock_binance.futures_create_order.side_effect = BinanceAPIException(
            MagicMock(text='{"code":-2019,"msg":"Margin is insufficient."}'),
            -2019, '{"code":-2019,"msg":"Margin is insufficient."}',
        )
        with self.assertRaises(BinanceClientError):
            client.create_order("BTCUSDT", "BUY", "MARKET", 100)
        # Must fail fast — retrying identical bad input is pointless.
        self.assertEqual(mock_binance.futures_create_order.call_count, 1)

    def test_timeout_then_order_confirmed_placed_is_not_duplicated(self):
        """
        Simulates the dangerous case: the create_order call times out, but
        the order actually went through on Binance's side. The client must
        detect this via the client order ID lookup and NOT place a second
        order.
        """
        client, mock_binance = make_client_with_mocked_binance()
        mock_binance.futures_create_order.side_effect = requests.exceptions.Timeout(
            "Read timed out"
        )
        mock_binance.futures_get_order.return_value = {
            "symbol": "BTCUSDT", "orderId": 42, "status": "FILLED",
            "executedQty": "0.01", "avgPrice": "65000",
        }

        with patch("bot.client.time.sleep"):  # skip real backoff delay in tests
            result = client.create_order("BTCUSDT", "BUY", "MARKET", 0.01)

        self.assertEqual(result["orderId"], 42)
        # The order-placement call was attempted once; the second "attempt"
        # was resolved via lookup, not a second real order placement.
        self.assertEqual(mock_binance.futures_create_order.call_count, 1)
        mock_binance.futures_get_order.assert_called_once()

    def test_timeout_then_genuinely_not_placed_retries_and_succeeds(self):
        client, mock_binance = make_client_with_mocked_binance()
        mock_binance.futures_create_order.side_effect = [
            requests.exceptions.Timeout("Read timed out"),
            {
                "symbol": "BTCUSDT", "orderId": 7, "status": "FILLED",
                "executedQty": "0.01", "avgPrice": "65000",
            },
        ]
        # Lookup after the timeout finds nothing — safe to retry.
        mock_binance.futures_get_order.side_effect = BinanceAPIException(
            MagicMock(text='{"code":-2013,"msg":"Order does not exist."}'),
            -2013, '{"code":-2013,"msg":"Order does not exist."}',
        )

        with patch("bot.client.time.sleep"):
            result = client.create_order("BTCUSDT", "BUY", "MARKET", 0.01)

        self.assertEqual(result["orderId"], 7)
        self.assertEqual(mock_binance.futures_create_order.call_count, 2)

    def test_all_retries_exhausted_raises_with_client_order_id(self):
        client, mock_binance = make_client_with_mocked_binance()
        mock_binance.futures_create_order.side_effect = requests.exceptions.ConnectionError(
            "Connection refused"
        )
        mock_binance.futures_get_order.side_effect = BinanceAPIException(
            MagicMock(text='{"code":-2013,"msg":"Order does not exist."}'),
            -2013, '{"code":-2013,"msg":"Order does not exist."}',
        )

        with patch("bot.client.time.sleep"):
            with self.assertRaises(BinanceClientError) as ctx:
                client.create_order("BTCUSDT", "BUY", "MARKET", 0.01)

        self.assertIn("NOT confirmed placed", str(ctx.exception))
        self.assertEqual(mock_binance.futures_create_order.call_count, 3)


if __name__ == "__main__":
    unittest.main()
