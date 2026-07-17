# Simplified Trading Bot — Binance Futures Testnet (USDT-M)

A small, structured Python CLI app that places MARKET and LIMIT orders
(BUY/SELL) on Binance Futures Testnet, with input validation, logging, and
error handling.

## Project Structure

```
trading_bot/
  bot/
    __init__.py
    client.py         # Binance client wrapper (Futures Testnet)
    orders.py          # order placement logic
    validators.py       # input validation
    constants.py         # shared enums (sides, order types, URLs)
    logging_config.py   # logging setup
  tests/
    test_validators.py  # input validation unit tests
    test_orders.py       # order-flow unit tests (mocked client, no network)
    test_client_retry.py # retry/timeout safety tests (no duplicate orders)
  cli.py               # CLI entry point
  README.md
  requirements.txt
  .env.example
```

## Setup

1. **Create/access your Binance Demo Trading account**
   As of mid-2026, Binance folded the standalone Futures Testnet into "Demo
   Trading," accessed via your regular Binance account (`testnet.binancefuture.com`
   now redirects to `demo.binance.com`). Log in, switch into Demo Trading mode.

2. **Generate API credentials**
   From the account menu, open **Demo Trading API** → **API Management** →
   **Create API** → **System generated** (HMAC). Enable **Reading**,
   **Spot & Margin & Stock Trading**, and **Futures** permissions. Copy the
   API Key and Secret immediately — the secret is only shown once. These are
   demo-only credentials, separate from any real Binance API keys.

3. **Clone this repo and install dependencies**
   ```bash
   git clone <this-repo-url>
   cd trading_bot
   python -m venv venv
   source venv/bin/activate      # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

4. **Set your API credentials**
   Copy `.env.example` to `.env` and fill in your testnet key/secret:
   ```bash
   cp .env.example .env
   ```
   ```
   BINANCE_API_KEY=your_testnet_api_key_here
   BINANCE_API_SECRET=your_testnet_api_secret_here
   ```
   The app loads these via `python-dotenv`; they are never hardcoded or logged.

## How to Run

**Market order:**
```bash
python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.01
```

**Limit order:**
```bash
python cli.py --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.01 --price 65000
```

Each run prints:
- The order request summary (symbol, side, type, quantity, price)
- The order response (orderId, status, executedQty, avgPrice)
- A clear ✅ SUCCESS or ❌ FAILURE message

All requests, responses, and errors are also written to `trading_bot.log`
(rotating file, 3 backups, 2MB each) in the project root — this is the file
to submit as evidence of MARKET and LIMIT orders.

## Tests

Validation and order-flow logic are covered by unit tests using a mocked
Binance client (no real network calls or credentials required):

```bash
python -m unittest discover tests -v
```

## Retries & Timeouts

Every HTTP call has an explicit 10s timeout. Order placement retries up to
twice on network failures (connection errors, read timeouts) — but not
naively:

- Each order gets a unique client-generated ID (`newClientOrderId`).
- On a timeout, the request's outcome is unknown — it may have reached
  Binance despite the client not getting a response. Before retrying, the
  bot looks up the order by that client ID. If it exists, the original
  request succeeded and is returned as-is — no duplicate order is placed.
- Definitive API rejections (bad symbol, insufficient margin, filter
  violations) are never retried, since retrying identical invalid input
  just fails identically again — only genuine network-level failures are.

See `tests/test_client_retry.py` for the scenarios this guards against.

## Error Handling

The app handles and logs, without crashing:
- **Invalid input** — bad symbol format, invalid side/type, non-numeric or
  non-positive quantity, missing price on LIMIT orders (`validators.py`)
- **API errors** — rejected orders, invalid symbol, insufficient testnet
  balance, etc. (`BinanceAPIException` / `BinanceOrderException`)
- **Network failures** — timeouts / connection errors are caught and
  reported cleanly instead of raising a raw traceback

## Assumptions

- **Testnet endpoint**: the task spec listed `testnet.binancefuture.com` as
  the base URL. As of mid-2026 Binance retired that standalone testnet and
  folded it into "Demo Trading" (`demo-fapi.binance.com`), reachable only
  through a regular Binance account's API Management page. This app targets
  the current live endpoint rather than the deprecated one.
- Only USDT-M Futures (not Coin-M) is in scope, per the task description.
- LIMIT orders use `timeInForce=GTC` (Good-Til-Cancelled) since the task
  spec didn't require configurable time-in-force.
- Quantity/price precision (tick size / lot size per symbol) is left to
  Binance's own validation — the app doesn't second-guess exchange filters,
  it just surfaces the API's error message if a filter is violated.
- Credentials are read from environment variables / `.env`, never passed as
  CLI arguments, to avoid them leaking into shell history or logs.

## Bonus (optional)

Not implemented in this submission — core requirements only, to stay inside
the ~60 minute estimate. Natural next step would be a Stop-Limit order type
added as `bot/orders.py::place_stop_limit_order`, following the same
validate → client.create_order → OrderResult pattern as MARKET/LIMIT.
