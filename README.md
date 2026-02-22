# hl-paper-mode

Paper trading safety layer for Hyperliquid. Intercepts orders from the real HL UI and simulates them locally — no keys, no signing, no real trades ever.

## Quickstart

```bash
cd hl-paper-mode

python3 -m venv .venv
source .venv/bin/activate

pip install -e ".[dev]"

PYTHONPATH=src python -m hl_paper.main
```

Server runs at `http://localhost:8000`. Live prices stream from the Hyperliquid public WebSocket.

### Chrome Extension

1. Open `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked** → select the `extension/` folder
4. Navigate to [app.hyperliquid.xyz](https://app.hyperliquid.xyz) — you should see a yellow **PAPER MODE** banner

## Usage

### Paper Mode

When enabled (default: **ON**), the extension intercepts order button clicks on the Hyperliquid UI. Instead of submitting real orders, it sends them to the local backend simulator which executes them against live market prices with realistic slippage and fees.

### DNR Failsafe

A declarativeNetRequest rule that hard-blocks POST requests to the Hyperliquid exchange API. **OFF by default.** Toggle it on via the extension popup if you want an extra safety net — useful if you suspect DOM interception missed a click.

## Architecture

- **Backend** — FastAPI server (`POST /api/v1/order`, `DELETE /api/v1/order/{id}`, `GET /api/v1/account`, `WS /ws/state`)
- **Engine** — Single-writer event loop. Processes price updates, order events, and cancels. Runs liquidation checks after every state mutation.
- **Execution** — Spread simulation (bid/ask from mid), slippage scaling, taker/maker fees, position management (increase, reduce, flip, leverage lock).
- **Extension Layer 1 (DOM)** — MutationObserver + capture-phase click listener. Primary interception method.
- **Extension Layer 2 (WS)** — MAIN world script overriding `WebSocket.prototype.send`. Best-effort backup.
- **Extension Layer 3 (DNR)** — Hard block on exchange endpoint. Failsafe, off by default.
- **Persistence** — SQLite via aiosqlite. State snapshots every 60s, fill log.

## Safety

- This is **not financial advice**. This tool is for paper trading simulation only.
- **Do not** use this with real funds or real API keys.
- Always verify the Paper Mode banner is visible before interacting with the HL UI.
- The backend must be running for orders to be captured. If it's offline, orders are blocked with an error.

## License

MIT
