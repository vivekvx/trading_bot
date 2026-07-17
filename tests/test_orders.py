"""
Unit tests for bot/orders.py using a mocked FuturesTestnetClient so no real
network calls or API credentials are needed to run the test suite.

Run with:
    python -m unittest discover tests
"""

import unittest
from unittest.mock import MagicMock

from bot.client import BinanceClientError
from bot.orders import place_order


class TestPlaceOrder(unittest.TestCase):
    def test_successful_market_order(self):
        fake_client = MagicMock()
        fake_client.create_order.return_value = {
            "orderId": 1,
            "status": "FILLED",
            "executedQty": "0.01",
            "avgPrice": "65000.0",
        }
        result = place_order(fake_client, "BTCUSDT", "BUY", "MARKET", 0.01)
        self.assertTrue(result.success)
        self.assertEqual(result.response["orderId"], 1)
        fake_client.create_order.assert_called_once()

    def test_successful_limit_order(self):
        fake_client = MagicMock()
        fake_client.create_order.return_value = {
            "orderId": 2,
            "status": "NEW",
            "executedQty": "0.00",
            "avgPrice": "0.00",
        }
        result = place_order(fake_client, "ETHUSDT", "SELL", "LIMIT", 0.5, 3200)
        self.assertTrue(result.success)
        self.assertEqual(result.request.price, 3200.0)

    def test_invalid_input_never_calls_api(self):
        fake_client = MagicMock()
        result = place_order(fake_client, "BTCUSDT", "SELL", "LIMIT", 0.5)  # no price
        self.assertFalse(result.success)
        self.assertIn("Price is required", result.error)
        fake_client.create_order.assert_not_called()

    def test_api_failure_is_captured_not_raised(self):
        fake_client = MagicMock()
        fake_client.create_order.side_effect = BinanceClientError(
            "Binance API error: Insufficient margin"
        )
        result = place_order(fake_client, "BTCUSDT", "BUY", "MARKET", 100)
        self.assertFalse(result.success)
        self.assertIn("Insufficient margin", result.error)

    def test_summary_includes_key_fields(self):
        fake_client = MagicMock()
        fake_client.create_order.return_value = {
            "orderId": 3,
            "status": "FILLED",
            "executedQty": "0.01",
            "avgPrice": "65000.0",
        }
        result = place_order(fake_client, "BTCUSDT", "BUY", "MARKET", 0.01)
        summary = result.summary()
        self.assertIn("Order ID:", summary)
        self.assertIn("SUCCESS", summary)


if __name__ == "__main__":
    unittest.main()
