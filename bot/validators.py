"""
Input validation for CLI-supplied order parameters.

Keeping validation separate from the CLI and the API-client layers makes it
independently testable and reusable (e.g. from a future web UI).
"""

import re
from dataclasses import dataclass
from typing import Optional

from .constants import ORDER_TYPE_LIMIT, VALID_ORDER_TYPES, VALID_SIDES

# Binance USDT-M perpetual symbols are upper-case and end in USDT (most common case)
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]{5,20}$")


class ValidationError(Exception):
    """Raised when user-supplied order parameters fail validation."""


@dataclass
class OrderRequest:
    symbol: str
    side: str
    order_type: str
    quantity: float
    price: Optional[float] = None


def validate_order(
    symbol: str,
    side: str,
    order_type: str,
    quantity: float,
    price: Optional[float] = None,
) -> OrderRequest:
    """
    Validate raw CLI input and return a normalized OrderRequest.
    Raises ValidationError with a human-readable message on failure.
    """
    symbol = (symbol or "").strip().upper()
    side = (side or "").strip().upper()
    order_type = (order_type or "").strip().upper()

    if not SYMBOL_PATTERN.match(symbol):
        raise ValidationError(
            f"Invalid symbol '{symbol}'. Expected format like 'BTCUSDT'."
        )

    if side not in VALID_SIDES:
        raise ValidationError(f"Invalid side '{side}'. Must be one of {VALID_SIDES}.")

    if order_type not in VALID_ORDER_TYPES:
        raise ValidationError(
            f"Invalid order type '{order_type}'. Must be one of {VALID_ORDER_TYPES}."
        )

    try:
        quantity = float(quantity)
    except (TypeError, ValueError):
        raise ValidationError(f"Quantity must be a number, got '{quantity}'.")

    if quantity <= 0:
        raise ValidationError("Quantity must be greater than 0.")

    normalized_price = None
    if order_type == ORDER_TYPE_LIMIT:
        if price is None:
            raise ValidationError("Price is required for LIMIT orders.")
        try:
            normalized_price = float(price)
        except (TypeError, ValueError):
            raise ValidationError(f"Price must be a number, got '{price}'.")
        if normalized_price <= 0:
            raise ValidationError("Price must be greater than 0.")
    elif price is not None:
        # Price provided for a MARKET order — not an error, just ignored.
        normalized_price = None

    return OrderRequest(
        symbol=symbol,
        side=side,
        order_type=order_type,
        quantity=quantity,
        price=normalized_price,
    )
