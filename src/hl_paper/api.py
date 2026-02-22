from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect

from hl_paper.engine import Engine
from hl_paper.models import OrderIntent

logger = logging.getLogger(__name__)


def create_app(engine: Engine | None = None) -> FastAPI:
    engine = engine or Engine()
    app = FastAPI(title="HL Paper Mode")
    ws_clients: set[WebSocket] = set()

    async def broadcast_state() -> None:
        if not ws_clients:
            return
        data = engine.state.model_dump()
        dead: list[WebSocket] = []
        for ws in ws_clients:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            ws_clients.discard(ws)

    @app.post("/api/v1/order")
    async def post_order(intent: OrderIntent):
        result = engine.on_order(intent)
        if result["status"] == "rejected":
            raise HTTPException(status_code=400, detail=result)
        await broadcast_state()
        return result

    @app.delete("/api/v1/order/{order_id}")
    async def delete_order(order_id: str):
        result = engine.on_cancel(order_id)
        if result["status"] == "not_found":
            raise HTTPException(status_code=404, detail=result)
        await broadcast_state()
        return result

    @app.get("/api/v1/account")
    def get_account():
        return engine.state.model_dump()

    @app.websocket("/ws/state")
    async def ws_state(websocket: WebSocket):
        await websocket.accept()
        ws_clients.add(websocket)
        try:
            # Send initial state
            await websocket.send_json(engine.state.model_dump())
            # Keep alive — wait for client disconnect
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            ws_clients.discard(websocket)

    return app
