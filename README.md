# hl-paper-mode

Paper trading mode for [Hyperliquid](https://app.hyperliquid.xyz). Uses the real HL interface but intercepts every order before it reaches the exchange, routing it to a local simulator instead. No API keys, no signing, no real trades — ever.

## Features

- **Live prices** — Streams all mid prices from the Hyperliquid public WebSocket
- **Realistic execution** — Spread simulation, notional-based slippage, taker/maker fees
- **Full position management** — Open, increase, reduce, close, and flip positions with leverage lock enforcement
- **Risk engine** — Maintenance margin tracking, automatic liquidation of worst-performing positions
- **3-layer interception** — DOM capture, WebSocket patch, and network-level failsafe
- **State persistence** — SQLite snapshots every 60s with fill history
- **92 unit tests** covering math, execution, engine, API, and edge cases

## How It Works

```
You → HL UI → Extension intercepts click → Local backend simulates order → Overlay shows result
```

The Chrome extension watches for order button clicks on the Hyperliquid UI. When Paper Mode is on, it blocks the real submission and sends the order intent to a FastAPI backend running on your machine. The backend executes against live market prices with simulated slippage and fees, then streams the updated state back to the UI overlay.

## Architecture

### Backend (Python/FastAPI)

| Component | Purpose |
|---|---|
| **Engine** | Single-writer event loop — all state mutations flow through here |
| **Execution** | Spread (bid/ask from mid), slippage scaling, fee calculation, position updates |
| **Math Core** | Pure functions — uPnL, equity, maintenance margin, liquidation price |
| **WS Feed** | Connects to `wss://api.hyperliquid.xyz/ws`, subscribes to `allMids` |
| **Persistence** | SQLite snapshots + fill log via aiosqlite |
| **API** | `POST /api/v1/order` · `DELETE /api/v1/order/{id}` · `GET /api/v1/account` · `WS /ws/state` |

### Extension (Chrome MV3)

| Layer | Method | Role |
|---|---|---|
| **Layer 1 — DOM** | MutationObserver + capture-phase click | Primary interception |
| **Layer 2 — WS** | `WebSocket.prototype.send` override (MAIN world) | Best-effort backup |
| **Layer 3 — DNR** | declarativeNetRequest blocking POST to exchange | Failsafe (off by default) |

## Setup

### Backend

```bash
git clone https://github.com/kizxyz/hl-paper-mode.git
cd hl-paper-mode

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

PYTHONPATH=src python -m hl_paper.main
```

Server starts at `http://localhost:8000` and connects to the Hyperliquid WebSocket automatically.

### Chrome Extension

1. Open `chrome://extensions`
2. Enable **Developer mode** (top right)
3. Click **Load unpacked** → select the `extension/` folder
4. Go to [app.hyperliquid.xyz](https://app.hyperliquid.xyz) — a yellow **PAPER MODE** banner confirms it's active

Use the extension popup to toggle Paper Mode and the DNR failsafe.

## Safety

- This tool simulates trades locally. **No real orders are ever sent.**
- No API keys or wallet signing is involved at any point.
- The backend must be running for orders to be captured. If it's offline, orders are blocked with an error toast.
- Always verify the yellow Paper Mode banner is visible before placing orders.
- **This is not financial advice.** Use at your own risk.

## Roadmap

- [ ] Deploy backend to cloud (Railway / Fly.io) for persistent state
- [ ] Publish to Chrome Web Store
- [ ] Overlay UI improvements — live PnL, position table, equity chart
- [ ] Multi-asset liquidation price display
- [ ] Trade history export (CSV)

## License

[MIT](LICENSE)
