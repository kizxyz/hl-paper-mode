from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable

import websockets

logger = logging.getLogger(__name__)

HL_WS_URL = "wss://api.hyperliquid.xyz/ws"


def parse_all_mids(msg: dict[str, Any]) -> dict[str, float] | None:
    """Parse an allMids channel message into {symbol: mid_price}.

    Returns None if the message is not an allMids update.
    """
    if msg.get("channel") != "allMids":
        return None

    data = msg.get("data")
    if data is None:
        return None

    mids = data.get("mids", {})
    return {symbol: float(price) for symbol, price in mids.items()}


async def subscribe_all_mids(
    on_prices: Callable[[dict[str, float]], Any],
    url: str = HL_WS_URL,
) -> None:
    """Connect to HL public WS and stream mid prices.

    Calls on_prices(dict[symbol, mid]) on each allMids update.
    Reconnects on disconnect.
    """
    subscribe_msg = json.dumps({
        "method": "subscribe",
        "subscription": {"type": "allMids"},
    })

    while True:
        try:
            async with websockets.connect(url) as ws:
                await ws.send(subscribe_msg)
                logger.info("Connected to HL WS, subscribed to allMids")

                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    mids = parse_all_mids(msg)
                    if mids is not None:
                        on_prices(mids)

        except (websockets.ConnectionClosed, OSError) as e:
            logger.warning("WS disconnected: %s — reconnecting in 3s", e)
            await asyncio.sleep(3)
