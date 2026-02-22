"""Entry point — wires engine, WS feed, persistence, and FastAPI together."""
from __future__ import annotations

import asyncio
import logging
import time

import uvicorn

from hl_paper.api import create_app
from hl_paper.config import SNAPSHOT_INTERVAL_S
from hl_paper.engine import Engine
from hl_paper.persistence import StateStore
from hl_paper.ws_feed import subscribe_all_mids

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("hl_paper")

DB_PATH = "hl_paper.db"


async def main() -> None:
    # 1. Init persistence
    store = StateStore(DB_PATH)
    await store.init()

    # 2. Load saved state or start fresh
    saved = await store.load_snapshot()
    if saved:
        logger.info("Loaded saved state: balance=%.2f, %d positions",
                     saved.balance, len(saved.positions))
        engine = Engine(state=saved)
    else:
        logger.info("No saved state — starting fresh")
        engine = Engine()

    # 3. Create FastAPI app
    app = create_app(engine)

    # 4. Periodic snapshot task
    async def snapshot_loop():
        while True:
            await asyncio.sleep(SNAPSHOT_INTERVAL_S)
            try:
                await store.save_snapshot(engine.state)
                logger.info("Snapshot saved (balance=%.2f, %d positions)",
                            engine.state.balance, len(engine.state.positions))
            except Exception as e:
                logger.error("Snapshot failed: %s", e)

    # 5. WS price feed callback
    price_count = 0

    def on_prices(mids: dict[str, float]) -> None:
        nonlocal price_count
        for symbol, price in mids.items():
            engine.on_price_update(symbol, price)
        price_count += 1
        if price_count == 1:
            logger.info("First price update: %d symbols (e.g. BTC=%.2f)",
                        len(mids), mids.get("BTC", 0))

    # 6. Start all tasks
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)

    async with asyncio.TaskGroup() as tg:
        tg.create_task(server.serve())
        tg.create_task(subscribe_all_mids(on_prices))
        tg.create_task(snapshot_loop())

    await store.close()


if __name__ == "__main__":
    asyncio.run(main())
