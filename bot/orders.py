"""
Order placement logic: sits between the CLI layer and the API client layer.

Responsible for:
- validating input (via validators.py)
- calling the API client
- shaping a clean, printable summary of request + response
"""

import logging
from typing import Any, Dict, Optional

from .client import BinanceClientError, FuturesTestnetClient
from .validators import OrderRequest, ValidationError, validate_order

logger = logging.getLogger("trading_bot.orders")


class OrderResult:
    """Simple container for a completed (or failed) order attempt."""

    def __init__(
        self,
        request: OrderRequest,
        success: bool,
        response: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ):
        self.request = request
        self.success = success
        self.response = response or {}
        self.error = error

    def summary(self) -> str:
        lines = [
            "----- Order Request -----",
            f"Symbol:   {self.request.symbol}",
            f"Side:     {self.request.side}",
            f"Type:     {self.request.order_type}",
            f"Quantity: {self.request.quantity}",
        ]
        if self.request.price is not None:
            lines.append(f"Price:    {self.request.price}")

        if self.success:
            lines += [
                "----- Order Response -----",
                f"Order ID:     {self.response.get('orderId', 'N/A')}",
                f"Status:       {self.response.get('status', 'N/A')}",
                f"Executed Qty: {self.response.get('executedQty', 'N/A')}",
                f"Avg Price:    {self.response.get('avgPrice', 'N/A')}",
                "",
                "✅ SUCCESS: Order placed successfully.",
            ]
        else:
            lines += [
                "----- Order Response -----",
                f"❌ FAILURE: {self.error}",
            ]

        return "\n".join(lines)


def place_order(
    client: FuturesTestnetClient,
    symbol: str,
    side: str,
    order_type: str,
    quantity: float,
    price: Optional[float] = None,
) -> OrderResult:
    """
    Validate input, place the order via the given client, and return an
    OrderResult. Never raises — all failure modes are captured in the result
    so the CLI layer can decide how to present them.
    """
    try:
        order_request = validate_order(symbol, side, order_type, quantity, price)
    except ValidationError as exc:
        logger.warning("Validation failed: %s", exc)
        # Build a best-effort request object purely for display purposes.
        fallback = OrderRequest(
            symbol=(symbol or "").upper(),
            side=(side or "").upper(),
            order_type=(order_type or "").upper(),
            quantity=quantity or 0,
            price=price,
        )
        return OrderResult(fallback, success=False, error=str(exc))

    try:
        response = client.create_order(
            symbol=order_request.symbol,
            side=order_request.side,
            order_type=order_request.order_type,
            quantity=order_request.quantity,
            price=order_request.price,
        )
        return OrderResult(order_request, success=True, response=response)

    except BinanceClientError as exc:
        return OrderResult(order_request, success=False, error=str(exc))
