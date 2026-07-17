#!/usr/bin/env python3
"""
CLI entry point for the Simplified Trading Bot (Binance Futures Testnet).

Examples:
    # Market order
    python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.01

    # Limit order
    python cli.py --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.01 --price 65000
"""

import argparse
import os
import sys

from dotenv import load_dotenv

from bot.client import BinanceClientError, FuturesTestnetClient
from bot.logging_config import setup_logging
from bot.orders import place_order


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Place MARKET or LIMIT orders on Binance Futures Testnet (USDT-M)."
    )
    parser.add_argument("--symbol", required=True, help="Trading pair, e.g. BTCUSDT")
    parser.add_argument("--side", required=True, choices=["BUY", "SELL", "buy", "sell"])
    parser.add_argument(
        "--type", dest="order_type", required=True,
        choices=["MARKET", "LIMIT", "market", "limit"],
    )
    parser.add_argument("--quantity", required=True, type=float, help="Order quantity")
    parser.add_argument(
        "--price", required=False, type=float,
        help="Limit price (required for LIMIT orders)",
    )
    return parser


def main() -> int:
    load_dotenv()  # loads BINANCE_API_KEY / BINANCE_API_SECRET from .env if present
    logger = setup_logging()

    parser = build_parser()
    args = parser.parse_args()

    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")

    try:
        client = FuturesTestnetClient(api_key, api_secret)
    except BinanceClientError as exc:
        logger.error("Startup failed: %s", exc)
        print(f"❌ {exc}")
        return 1

    result = place_order(
        client,
        symbol=args.symbol,
        side=args.side,
        order_type=args.order_type,
        quantity=args.quantity,
        price=args.price,
    )

    print(result.summary())
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
