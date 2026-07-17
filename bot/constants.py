"""Shared constants — single source of truth for enums used across modules."""

SIDE_BUY = "BUY"
SIDE_SELL = "SELL"
VALID_SIDES = {SIDE_BUY, SIDE_SELL}

ORDER_TYPE_MARKET = "MARKET"
ORDER_TYPE_LIMIT = "LIMIT"
VALID_ORDER_TYPES = {ORDER_TYPE_MARKET, ORDER_TYPE_LIMIT}

TIME_IN_FORCE_GTC = "GTC"

FUTURES_TESTNET_BASE_URL = "https://demo-fapi.binance.com"
