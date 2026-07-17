"""
Thin wrapper around python-binance's Client, pinned to Binance Futures
Testnet (USDT-M). Keeping this isolated means orders.py / cli.py never touch
python-binance directly, so the underlying HTTP library could be swapped out
later without touching business logic.
"""

import logging
from typing import Any, Dict, Optional

from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException, BinanceRequestException

from .constants import FUTURES_TESTNET_BASE_URL, ORDER_TYPE_LIMIT, TIME_IN_FORCE_GTC

logger = logging.getLogger("trading_bot.client")


class BinanceClientError(Exception):
    """Raised when the Binance API call fails (network, auth, or API error)."""


class FuturesTestnetClient:
    """
    Wraps `binance.client.Client`, configured against the Futures Testnet.

    Usage:
        client = FuturesTestnetClient(api_key, api_secret)
        response = client.create_order(symbol="BTCUSDT", side="BUY", ...)
    """

    def __init__(self, api_key: str, api_secret: str):
        if not api_key or not api_secret:
            raise BinanceClientError(
                "Missing API credentials. Set BINANCE_API_KEY and "
                "BINANCE_API_SECRET (env vars or .env file)."
            )

        self._client = Client(api_key, api_secret, testnet=True)
        # Belt-and-braces: python-binance's testnet flag already points futures
        # requests at testnet.binancefuture.com, but we set it explicitly too
        # in case the installed version's default changes.
        self._client.FUTURES_URL = FUTURES_TESTNET_BASE_URL + "/fapi"

        logger.debug("Initialized FuturesTestnetClient against %s", FUTURES_TESTNET_BASE_URL)

    def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Place a MARKET or LIMIT order on Futures Testnet.
        Returns the raw response dict from Binance on success.
        Raises BinanceClientError on any failure (network/auth/API/order).
        """
        params: Dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
        }

        if order_type == ORDER_TYPE_LIMIT:
            params["price"] = price
            params["timeInForce"] = TIME_IN_FORCE_GTC

        # INFO, single line, one entry per request — kept deliberately terse
        # so the log file stays a useful audit trail rather than noise.
        logger.info("REQUEST  %s", params)

        try:
            response = self._client.futures_create_order(**params)
            logger.info(
                "RESPONSE symbol=%s orderId=%s status=%s executedQty=%s avgPrice=%s",
                response.get("symbol"),
                response.get("orderId"),
                response.get("status"),
                response.get("executedQty"),
                response.get("avgPrice"),
            )
            return response

        except (BinanceAPIException, BinanceOrderException) as exc:
            logger.error("ERROR (api) symbol=%s -> %s", symbol, exc)
            raise BinanceClientError(f"Binance API error: {exc}") from exc

        except BinanceRequestException as exc:
            logger.error("ERROR (request) symbol=%s -> %s", symbol, exc)
            raise BinanceClientError(f"Request error: {exc}") from exc

        except (ConnectionError, TimeoutError) as exc:
            logger.error("ERROR (network) symbol=%s -> %s", symbol, exc)
            raise BinanceClientError(f"Network error: {exc}") from exc

        except Exception as exc:  # noqa: BLE001 - last-resort safety net, logged
            logger.exception("ERROR (unexpected) symbol=%s", symbol)
            raise BinanceClientError(f"Unexpected error: {exc}") from exc

    def get_order_status(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Fetch the current status of a previously placed order."""
        try:
            response = self._client.futures_get_order(symbol=symbol, orderId=order_id)
            logger.info("Order status response: %s", response)
            return response
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to fetch order status")
            raise BinanceClientError(f"Failed to fetch order status: {exc}") from exc
