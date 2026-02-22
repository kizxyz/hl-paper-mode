import pytest
from fastapi.testclient import TestClient

from hl_paper.api import create_app
from hl_paper.engine import Engine


@pytest.fixture
def client():
    engine = Engine()
    engine.on_price_update("BTC", 50000.0)
    engine.on_price_update("ETH", 3000.0)
    app = create_app(engine)
    return TestClient(app)


class TestPostOrder:
    def test_market_order(self, client):
        resp = client.post("/api/v1/order", json={
            "symbol": "BTC",
            "side": "BUY",
            "order_type": "MARKET",
            "size_value": 5000,
            "size_unit": "USD",
            "leverage": 10,
            "reduce_only": False,
            "client_id": "t1",
            "timestamp": 1000,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "filled"

    def test_invalid_payload(self, client):
        resp = client.post("/api/v1/order", json={"symbol": "BTC"})
        assert resp.status_code == 422


class TestGetAccount:
    def test_account_state(self, client):
        resp = client.get("/api/v1/account")
        assert resp.status_code == 200
        data = resp.json()
        assert "balance" in data
        assert "positions" in data


class TestDeleteOrder:
    def test_cancel_order(self, client):
        # Place a limit order first
        client.post("/api/v1/order", json={
            "symbol": "BTC",
            "side": "BUY",
            "order_type": "LIMIT",
            "size_value": 0.1,
            "size_unit": "BASE",
            "leverage": 10,
            "limit_price": 45000.0,
            "reduce_only": False,
            "client_id": "t2",
            "timestamp": 1000,
        })

        # Get account to find the order id
        acct = client.get("/api/v1/account").json()
        oid = list(acct["open_orders"].keys())[0]

        resp = client.delete(f"/api/v1/order/{oid}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_cancel_nonexistent(self, client):
        resp = client.delete("/api/v1/order/fake-id")
        assert resp.status_code == 404


class TestWsState:
    def test_ws_connects_and_receives(self, client):
        with client.websocket_connect("/ws/state") as ws:
            # Should receive initial state on connect
            data = ws.receive_json()
            assert "balance" in data
            assert "positions" in data
