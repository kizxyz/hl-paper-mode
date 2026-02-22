import asyncio

import pytest

from hl_paper.engine import Engine
from hl_paper.models import AccountState, OrderIntent, OrderType, Side, SizeUnit


@pytest.fixture
def engine():
    return Engine()


# ---------------------------------------------------------------------------
# Price Update
# ---------------------------------------------------------------------------
class TestPriceUpdate:
    def test_price_stored(self, engine):
        engine.on_price_update("BTC", 50000.0)
        assert engine.prices["BTC"] == 50000.0

    def test_price_update_overwrites(self, engine):
        engine.on_price_update("BTC", 50000.0)
        engine.on_price_update("BTC", 51000.0)
        assert engine.prices["BTC"] == 51000.0


# ---------------------------------------------------------------------------
# Order Submission
# ---------------------------------------------------------------------------
class TestOrderSubmission:
    def test_market_order_fills_immediately(self, engine):
        engine.on_price_update("BTC", 50000.0)

        result = engine.on_order(OrderIntent(
            symbol="BTC", side=Side.BUY, order_type=OrderType.MARKET,
            size_value=5000.0, size_unit=SizeUnit.USD, leverage=10,
            client_id="c1", timestamp=1000,
        ))

        assert result["status"] == "filled"
        assert "BTC" in engine.state.positions

    def test_limit_order_rests(self, engine):
        engine.on_price_update("BTC", 50000.0)

        result = engine.on_order(OrderIntent(
            symbol="BTC", side=Side.BUY, order_type=OrderType.LIMIT,
            size_value=0.1, size_unit=SizeUnit.BASE, leverage=10,
            limit_price=48000.0, client_id="c2", timestamp=1000,
        ))

        assert result["status"] == "resting"
        assert len(engine.state.open_orders) == 1

    def test_limit_order_fills_at_market(self, engine):
        engine.on_price_update("BTC", 47000.0)

        result = engine.on_order(OrderIntent(
            symbol="BTC", side=Side.BUY, order_type=OrderType.LIMIT,
            size_value=0.1, size_unit=SizeUnit.BASE, leverage=10,
            limit_price=48000.0, client_id="c3", timestamp=1000,
        ))

        assert result["status"] == "filled"

    def test_no_price_rejects(self, engine):
        result = engine.on_order(OrderIntent(
            symbol="BTC", side=Side.BUY, order_type=OrderType.MARKET,
            size_value=5000.0, size_unit=SizeUnit.USD, leverage=10,
            client_id="c4", timestamp=1000,
        ))

        assert result["status"] == "rejected"


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------
class TestCancel:
    def test_cancel_existing(self, engine):
        engine.on_price_update("BTC", 50000.0)
        engine.on_order(OrderIntent(
            symbol="BTC", side=Side.BUY, order_type=OrderType.LIMIT,
            size_value=0.1, size_unit=SizeUnit.BASE, leverage=10,
            limit_price=48000.0, client_id="c5", timestamp=1000,
        ))
        oid = list(engine.state.open_orders.keys())[0]

        result = engine.on_cancel(oid)
        assert result["status"] == "cancelled"
        assert len(engine.state.open_orders) == 0

    def test_cancel_nonexistent(self, engine):
        result = engine.on_cancel("fake-id")
        assert result["status"] == "not_found"


# ---------------------------------------------------------------------------
# Liquidation
# ---------------------------------------------------------------------------
class TestLiquidation:
    def test_liquidation_closes_position(self, engine):
        engine.state.balance = 100.0
        engine.on_price_update("BTC", 50000.0)

        # Open a long with tiny balance
        engine.on_order(OrderIntent(
            symbol="BTC", side=Side.BUY, order_type=OrderType.MARKET,
            size_value=0.1, size_unit=SizeUnit.BASE, leverage=50,
            client_id="c6", timestamp=1000,
        ))

        # Price crashes — should trigger liquidation
        engine.on_price_update("BTC", 40000.0)
        engine.check_liquidations()

        assert "BTC" not in engine.state.positions

    def test_no_liquidation_when_healthy(self, engine):
        engine.on_price_update("BTC", 50000.0)

        engine.on_order(OrderIntent(
            symbol="BTC", side=Side.BUY, order_type=OrderType.MARKET,
            size_value=1000.0, size_unit=SizeUnit.USD, leverage=10,
            client_id="c7", timestamp=1000,
        ))

        engine.on_price_update("BTC", 49900.0)
        engine.check_liquidations()

        assert "BTC" in engine.state.positions


# ---------------------------------------------------------------------------
# Leverage Mismatch via Engine
# ---------------------------------------------------------------------------
class TestLeverageMismatch:
    def test_rejected_by_engine(self, engine):
        engine.on_price_update("BTC", 50000.0)

        engine.on_order(OrderIntent(
            symbol="BTC", side=Side.BUY, order_type=OrderType.MARKET,
            size_value=1000.0, size_unit=SizeUnit.USD, leverage=10,
            client_id="c8", timestamp=1000,
        ))

        result = engine.on_order(OrderIntent(
            symbol="BTC", side=Side.BUY, order_type=OrderType.MARKET,
            size_value=1000.0, size_unit=SizeUnit.USD, leverage=20,
            client_id="c9", timestamp=1001,
        ))

        assert result["status"] == "rejected"
        assert "leverage" in result.get("reason", "").lower()
