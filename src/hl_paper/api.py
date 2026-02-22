from __future__ import annotations

from fastapi import FastAPI, HTTPException

from hl_paper.engine import Engine
from hl_paper.models import OrderIntent


def create_app(engine: Engine | None = None) -> FastAPI:
    engine = engine or Engine()
    app = FastAPI(title="HL Paper Mode")

    @app.post("/api/v1/order")
    def post_order(intent: OrderIntent):
        result = engine.on_order(intent)
        if result["status"] == "rejected":
            raise HTTPException(status_code=400, detail=result)
        return result

    @app.delete("/api/v1/order/{order_id}")
    def delete_order(order_id: str):
        result = engine.on_cancel(order_id)
        if result["status"] == "not_found":
            raise HTTPException(status_code=404, detail=result)
        return result

    @app.get("/api/v1/account")
    def get_account():
        return engine.state.model_dump()

    return app
