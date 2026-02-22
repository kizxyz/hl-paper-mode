import pytest

from hl_paper.config import MAKER_FEE_RATE, TAKER_FEE_RATE, TICK_SIZE
from hl_paper.execution import (
    calc_spread,
    execute_market_order,
    check_limit_fill,
    apply_fill_to_position,
)
from hl_paper.models import (
    AccountState,
    Fill,
    OpenOrder,
    OrderIntent,
    OrderType,
    Position,
    Side,
    SizeUnit,
)


# ---------------------------------------------------------------------------
# Spread
# ---------------------------------------------------------------------------
class TestCalcSpread:
    def test_spread(self):
        bid, ask = calc_spread(50000.0, TICK_SIZE)
        assert bid == pytest.approx(49999.95)
        assert ask == pytest.approx(50000.05)

    def test_spread_symmetry(self):
        bid, ask = calc_spread(100.0, 0.01)
        assert ask - 100.0 == pytest.approx(100.0 - bid)


# ---------------------------------------------------------------------------
# Market Order Execution
# ---------------------------------------------------------------------------
class TestExecuteMarketOrder:
    def test_buy_market(self):
        fill = execute_market_order(
            symbol="BTC",
            side=Side.BUY,
            size_value=5000.0,
            size_unit="USD",
            mid_price=50000.0,
        )
        assert fill.side == Side.BUY
        assert fill.size > 0
        assert fill.price > 50000.0  # slippage pushes buy price up
        assert fill.fee > 0

    def test_sell_market(self):
        fill = execute_market_order(
            symbol="ETH",
            side=Side.SELL,
            size_value=1.0,
            size_unit="BASE",
            mid_price=3000.0,
        )
        assert fill.side == Side.SELL
        assert fill.size == pytest.approx(1.0)
        assert fill.price < 3000.0  # slippage pushes sell price down
        assert fill.fee > 0


# ---------------------------------------------------------------------------
# Limit Fill Check
# ---------------------------------------------------------------------------
class TestCheckLimitFill:
    def test_buy_limit_fills(self):
        order = OpenOrder(
            order_id="1", symbol="BTC", side=Side.BUY,
            order_type=OrderType.LIMIT, size=0.1,
            limit_price=50000.0, leverage=10,
        )
        # ask <= limit → fill
        filled = check_limit_fill(order, mid_price=49990.0, tick=TICK_SIZE)
        assert filled is not None
        assert filled.price == 50000.0  # fills at limit price

    def test_buy_limit_no_fill(self):
        order = OpenOrder(
            order_id="1", symbol="BTC", side=Side.BUY,
            order_type=OrderType.LIMIT, size=0.1,
            limit_price=49000.0, leverage=10,
        )
        # ask > limit → no fill
        filled = check_limit_fill(order, mid_price=50000.0, tick=TICK_SIZE)
        assert filled is None

    def test_sell_limit_fills(self):
        order = OpenOrder(
            order_id="1", symbol="BTC", side=Side.SELL,
            order_type=OrderType.LIMIT, size=0.1,
            limit_price=50000.0, leverage=10,
        )
        # bid >= limit → fill
        filled = check_limit_fill(order, mid_price=50010.0, tick=TICK_SIZE)
        assert filled is not None
        assert filled.price == 50000.0

    def test_sell_limit_no_fill(self):
        order = OpenOrder(
            order_id="1", symbol="BTC", side=Side.SELL,
            order_type=OrderType.LIMIT, size=0.1,
            limit_price=51000.0, leverage=10,
        )
        filled = check_limit_fill(order, mid_price=50000.0, tick=TICK_SIZE)
        assert filled is None


# ---------------------------------------------------------------------------
# Position Updates
# ---------------------------------------------------------------------------
class TestApplyFillToPosition:
    def test_open_new_position(self):
        state = AccountState()
        fill = Fill(symbol="BTC", side=Side.BUY, size=0.1, price=50000.0, fee=2.25)

        apply_fill_to_position(state, fill, leverage=10)

        pos = state.positions["BTC"]
        assert pos.side == Side.BUY
        assert pos.size == pytest.approx(0.1)
        assert pos.entry_price == pytest.approx(50000.0)
        assert pos.leverage == 10
        assert state.balance == pytest.approx(10000.0 - 2.25)

    def test_increase_same_side(self):
        state = AccountState()
        state.positions["BTC"] = Position(
            symbol="BTC", side=Side.BUY, size=0.1,
            entry_price=50000.0, leverage=10, mmr=0.05,
        )
        fill = Fill(symbol="BTC", side=Side.BUY, size=0.1, price=52000.0, fee=2.34)

        apply_fill_to_position(state, fill, leverage=10)

        pos = state.positions["BTC"]
        # weighted avg: (0.1*50000 + 0.1*52000) / 0.2 = 51000
        assert pos.size == pytest.approx(0.2)
        assert pos.entry_price == pytest.approx(51000.0)
        assert state.balance == pytest.approx(10000.0 - 2.34)

    def test_leverage_mismatch_rejected(self):
        state = AccountState()
        state.positions["BTC"] = Position(
            symbol="BTC", side=Side.BUY, size=0.1,
            entry_price=50000.0, leverage=10, mmr=0.05,
        )
        fill = Fill(symbol="BTC", side=Side.BUY, size=0.1, price=52000.0, fee=2.0)

        with pytest.raises(ValueError, match="[Ll]everage"):
            apply_fill_to_position(state, fill, leverage=20)

    def test_reduce_position(self):
        state = AccountState()
        state.positions["BTC"] = Position(
            symbol="BTC", side=Side.BUY, size=1.0,
            entry_price=50000.0, leverage=10, mmr=0.05,
        )
        # Sell 0.5 to reduce long
        fill = Fill(symbol="BTC", side=Side.SELL, size=0.5, price=52000.0, fee=11.7)

        apply_fill_to_position(state, fill, leverage=10)

        pos = state.positions["BTC"]
        assert pos.size == pytest.approx(0.5)
        assert pos.entry_price == pytest.approx(50000.0)  # entry unchanged on reduce
        # rpnl = 1 * (52000 - 50000) * 0.5 = 1000
        # balance = 10000 + 1000 - 11.7 = 10988.3
        assert state.balance == pytest.approx(10988.3)

    def test_close_position(self):
        state = AccountState()
        state.positions["BTC"] = Position(
            symbol="BTC", side=Side.BUY, size=0.5,
            entry_price=50000.0, leverage=10, mmr=0.05,
        )
        fill = Fill(symbol="BTC", side=Side.SELL, size=0.5, price=51000.0, fee=11.475)

        apply_fill_to_position(state, fill, leverage=10)

        assert "BTC" not in state.positions
        # rpnl = 1 * (51000-50000) * 0.5 = 500
        # balance = 10000 + 500 - 11.475 = 10488.525
        assert state.balance == pytest.approx(10488.525)

    def test_flip_position(self):
        state = AccountState()
        state.positions["BTC"] = Position(
            symbol="BTC", side=Side.BUY, size=0.3,
            entry_price=50000.0, leverage=10, mmr=0.05,
        )
        # Sell 0.5 → close 0.3 long, open 0.2 short
        fill = Fill(symbol="BTC", side=Side.SELL, size=0.5, price=51000.0, fee=11.0)

        apply_fill_to_position(state, fill, leverage=10)

        pos = state.positions["BTC"]
        assert pos.side == Side.SELL
        assert pos.size == pytest.approx(0.2)
        assert pos.entry_price == pytest.approx(51000.0)

    def test_short_reduce(self):
        state = AccountState()
        state.positions["ETH"] = Position(
            symbol="ETH", side=Side.SELL, size=10.0,
            entry_price=3000.0, leverage=5, mmr=0.1,
        )
        # Buy 5 to reduce short
        fill = Fill(symbol="ETH", side=Side.BUY, size=5.0, price=2800.0, fee=6.3)

        apply_fill_to_position(state, fill, leverage=5)

        pos = state.positions["ETH"]
        assert pos.size == pytest.approx(5.0)
        # rpnl = -1 * (2800 - 3000) * 5 = 1000
        # balance = 10000 + 1000 - 6.3 = 10993.7
        assert state.balance == pytest.approx(10993.7)
