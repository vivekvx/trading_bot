"""
Unit tests for bot/validators.py.

Run with:
    python -m unittest discover tests
"""

import unittest

from bot.validators import ValidationError, validate_order


class TestValidateOrder(unittest.TestCase):
    def test_valid_market_order_normalizes_case(self):
        order = validate_order("btcusdt", "buy", "market", 0.01)
        self.assertEqual(order.symbol, "BTCUSDT")
        self.assertEqual(order.side, "BUY")
        self.assertEqual(order.order_type, "MARKET")
        self.assertIsNone(order.price)

    def test_valid_limit_order_keeps_price(self):
        order = validate_order("ETHUSDT", "SELL", "LIMIT", 0.5, 3200)
        self.assertEqual(order.price, 3200.0)

    def test_limit_order_without_price_raises(self):
        with self.assertRaises(ValidationError):
            validate_order("BTCUSDT", "SELL", "LIMIT", 0.01)

    def test_market_order_ignores_stray_price(self):
        order = validate_order("BTCUSDT", "BUY", "MARKET", 0.01, price=99999)
        self.assertIsNone(order.price)

    def test_negative_quantity_raises(self):
        with self.assertRaises(ValidationError):
            validate_order("BTCUSDT", "BUY", "MARKET", -1)

    def test_zero_quantity_raises(self):
        with self.assertRaises(ValidationError):
            validate_order("BTCUSDT", "BUY", "MARKET", 0)

    def test_non_numeric_quantity_raises(self):
        with self.assertRaises(ValidationError):
            validate_order("BTCUSDT", "BUY", "MARKET", "abc")

    def test_invalid_side_raises(self):
        with self.assertRaises(ValidationError):
            validate_order("BTCUSDT", "HOLD", "MARKET", 1)

    def test_invalid_order_type_raises(self):
        with self.assertRaises(ValidationError):
            validate_order("BTCUSDT", "BUY", "STOP", 1)

    def test_invalid_symbol_raises(self):
        with self.assertRaises(ValidationError):
            validate_order("btc-usdt!", "BUY", "MARKET", 1)

    def test_negative_limit_price_raises(self):
        with self.assertRaises(ValidationError):
            validate_order("BTCUSDT", "BUY", "LIMIT", 1, price=-100)


if __name__ == "__main__":
    unittest.main()
