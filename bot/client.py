"""
Thin wrapper around python-binance's Client, pinned to Binance Futures
Testnet (USDT-M). Keeping this isolated means orders.py / cli.py never touch
python-binance directly, so the underlying HTTP library could be swapped out
later without touching business logic.
"""

import logging
import time
import uuid
from typing import Any, Dict, Optional

import requests.exceptions
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException, BinanceRequestException

from .constants import FUTURES_TESTNET_BASE_URL, ORDER_TYPE_LIMIT, TIME_IN_FORCE_GTC

logger = logging.getLogger("trading_bot.client")

REQUEST_TIMEOUT_SECONDS = 10  # connect + read timeout per HTTP call
MAX_ORDER_ATTEMPTS = 3  # initial attempt + up to 2 retries
RETRY_BACKOFF_BASE_SECONDS = 1.5  # exponential: 1.5s, 3s, ...


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

        self._client = Client(
            api_key,
            api_secret,
            testnet=True,
            requests_params={"timeout": REQUEST_TIMEOUT_SECONDS},
        )
        # As of mid-2026, Binance folded the standalone Futures Testnet into
        # "Demo Trading" under the main account, with a new API host
        # (demo-fapi.binance.com). python-binance's built-in testnet=True flag
        # may still point at the old testnet.binancefuture.com host, so we
        # override it explicitly here to the current one.
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

        Retry behavior is deliberately conservative: order placement is not
        naturally idempotent, so a naive "retry on any failure" approach can
        double-place an order if the first request actually succeeded but the
        response was lost to a timeout. To avoid that:

        1. Every order gets a unique client-generated ID (newClientOrderId).
        2. On a network/timeout failure (request status genuinely unknown),
           we first look the order up by that ID before retrying. If it
           exists, the original request succeeded — we return it, no retry.
           If it doesn't exist, it's safe to retry.
        3. Definitive API rejections (bad symbol, insufficient margin, filter
           violations) are never retried — retrying identical bad input just
           fails identically again.
        """
        client_order_id = f"bot_{uuid.uuid4().hex[:20]}"
        params: Dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
            "newClientOrderId": client_order_id,
        }

        if order_type == ORDER_TYPE_LIMIT:
            params["price"] = price
            params["timeInForce"] = TIME_IN_FORCE_GTC

        # INFO, single line, one entry per request — kept deliberately terse
        # so the log file stays a useful audit trail rather than noise.
        logger.info("REQUEST  %s", params)

        for attempt in range(1, MAX_ORDER_ATTEMPTS + 1):
            try:
                response = self._client.futures_create_order(**params)
                logger.info(
                    "RESPONSE symbol=%s orderId=%s clientOrderId=%s status=%s "
                    "executedQty=%s avgPrice=%s (attempt %d/%d)",
                    response.get("symbol"),
                    response.get("orderId"),
                    client_order_id,
                    response.get("status"),
                    response.get("executedQty"),
                    response.get("avgPrice"),
                    attempt,
                    MAX_ORDER_ATTEMPTS,
                )
                return response

            except (BinanceAPIException, BinanceOrderException) as exc:
                # Definitive rejection from Binance — retrying won't help.
                logger.error("ERROR (api, not retrying) symbol=%s -> %s", symbol, exc)
                raise BinanceClientError(f"Binance API error: {exc}") from exc

            except BinanceRequestException as exc:
                logger.error("ERROR (malformed request, not retrying) symbol=%s -> %s", symbol, exc)
                raise BinanceClientError(f"Request error: {exc}") from exc

            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
            ) as exc:
                logger.warning(
                    "Network failure on attempt %d/%d (clientOrderId=%s): %s",
                    attempt, MAX_ORDER_ATTEMPTS, client_order_id, exc,
                )

                # Request outcome is unknown — it may have gone through on
                # Binance's side despite the timeout. Check before retrying.
                existing = self._find_by_client_order_id(symbol, client_order_id)
                if existing is not None:
                    logger.info(
                        "Order clientOrderId=%s was actually placed despite "
                        "the network error — returning it, no retry needed.",
                        client_order_id,
                    )
                    return existing

                if attempt == MAX_ORDER_ATTEMPTS:
                    logger.error(
                        "ERROR (network, retries exhausted) symbol=%s clientOrderId=%s",
                        symbol, client_order_id,
                    )
                    raise BinanceClientError(
                        f"Network error after {MAX_ORDER_ATTEMPTS} attempts: {exc}. "
                        f"Order was NOT confirmed placed (clientOrderId={client_order_id})."
                    ) from exc

                backoff = RETRY_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                logger.info("Retrying in %.1fs...", backoff)
                time.sleep(backoff)

            except Exception as exc:  # noqa: BLE001 - last-resort safety net, logged
                logger.exception("ERROR (unexpected, not retrying) symbol=%s", symbol)
                raise BinanceClientError(f"Unexpected error: {exc}") from exc

        # Unreachable in practice (loop always returns or raises), but keeps
        # type checkers happy and fails loudly if the logic above changes.
        raise BinanceClientError("Order placement failed for an unknown reason.")

    def _find_by_client_order_id(
        self, symbol: str, client_order_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Look up an order by its client-generated ID, used to check whether a
        request that appeared to fail (timeout) actually succeeded. Returns
        None if no such order exists yet, rather than raising, since "not
        found" is an expected outcome here, not an error.
        """
        try:
            return self._client.futures_get_order(
                symbol=symbol, origClientOrderId=client_order_id
            )
        except (BinanceAPIException, BinanceOrderException) as exc:
            # Binance returns an "order does not exist" API error for a
            # not-yet-placed clientOrderId — that's the expected case, not
            # a failure. Treat it as "not found".
            logger.debug("Order lookup for clientOrderId=%s: not found (%s)", client_order_id, exc)
            return None
        except Exception:  # noqa: BLE001
            # If the lookup itself fails (e.g. also a network error), don't
            # mask that — surface it distinctly rather than assuming "not
            # found" and silently placing a possible duplicate.
            logger.exception(
                "Could not verify whether clientOrderId=%s was placed; "
                "aborting retry rather than risking a duplicate order.",
                client_order_id,
            )
            raise

    def get_order_status(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Fetch the current status of a previously placed order."""
        try:
            response = self._client.futures_get_order(symbol=symbol, orderId=order_id)
            logger.info("Order status response: %s", response)
            return response
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to fetch order status")
            raise BinanceClientError(f"Failed to fetch order status: {exc}") from exc
