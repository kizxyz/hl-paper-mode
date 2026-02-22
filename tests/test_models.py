import pytest
from pydantic import ValidationError

from hl_paper.models import (
    AccountState,
    OrderIntent,
    OrderType,
    Position,
    Side,
    SizeUnit,
)


def _market_order(**overrides) -> dict:
    base = {
        "symbol": "BTC",
        "side": "BUY",
        "order_type": "MARKET",
        "size_value": 5000,
        "size_unit": "USD",
        "leverage": 10,
        "limit_price": None,
        "reduce_only": False,
        "client_id": "ext-123",
        "timestamp": 1700000000,
    }
    base.update(overrides)
    return base


class TestOrderIntent:
    def test_valid_market_order(self):
        o = OrderIntent(**_market_order())
        assert o.symbol == "BTC"
        assert o.side == Side.BUY
        assert o.order_type == OrderType.MARKET
        assert o.size_unit == SizeUnit.USD
        assert o.size_value == 5000
        assert o.leverage == 10

    def test_valid_limit_order(self):
        o = OrderIntent(**_market_order(order_type="LIMIT", limit_price=50000.0))
        assert o.order_type == OrderType.LIMIT
        assert o.limit_price == 50000.0

    def test_missing_required_field(self):
        data = _market_order()
        del data["symbol"]
        with pytest.raises(ValidationError):
            OrderIntent(**data)

    def test_invalid_side(self):
        with pytest.raises(ValidationError):
            OrderIntent(**_market_order(side="LONG"))

    def test_invalid_size_unit(self):
        with pytest.raises(ValidationError):
            OrderIntent(**_market_order(size_unit="CONTRACTS"))


class TestPosition:
    def test_side_sign_long(self):
        p = Position(symbol="ETH", side=Side.BUY, size=1.0, entry_price=3000.0)
        assert p.side_sign == 1

    def test_side_sign_short(self):
        p = Position(symbol="ETH", side=Side.SELL, size=1.0, entry_price=3000.0)
        assert p.side_sign == -1

    def test_notional(self):
        p = Position(symbol="BTC", side=Side.BUY, size=0.5, entry_price=60000.0)
        assert p.notional == 30000.0


class TestAccountState:
    def test_defaults(self):
        a = AccountState()
        assert a.balance == 10_000.0
        assert a.positions == {}
