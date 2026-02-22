import pytest

from hl_paper.math_core import (
    apply_slippage,
    calc_equity,
    calc_exec_price,
    calc_fee,
    calc_liq_price,
    calc_maintenance_margin,
    calc_rpnl,
    calc_slippage,
    calc_upnl,
    convert_size,
    is_liquidatable,
    round_to_step,
    round_to_tick,
)
from hl_paper.models import Position, Side


# ---------------------------------------------------------------------------
# uPnL
# ---------------------------------------------------------------------------
class TestCalcUpnl:
    def test_long_profit(self):
        # Long 1 BTC @ 50000, price now 51000 → +1000
        assert calc_upnl(Side.BUY, 1.0, 51000.0, 50000.0) == pytest.approx(1000.0)

    def test_long_loss(self):
        # Long 1 BTC @ 50000, price now 49000 → -1000
        assert calc_upnl(Side.BUY, 1.0, 49000.0, 50000.0) == pytest.approx(-1000.0)

    def test_short_profit(self):
        # Short 1 BTC @ 50000, price now 49000 → +1000
        assert calc_upnl(Side.SELL, 1.0, 49000.0, 50000.0) == pytest.approx(1000.0)

    def test_short_loss(self):
        # Short 1 BTC @ 50000, price now 51000 → -1000
        assert calc_upnl(Side.SELL, 1.0, 51000.0, 50000.0) == pytest.approx(-1000.0)

    def test_zero_size(self):
        assert calc_upnl(Side.BUY, 0.0, 51000.0, 50000.0) == 0.0

    def test_fractional_size(self):
        # Long 0.5 BTC @ 60000, price 62000 → 0.5 * 2000 = 1000
        assert calc_upnl(Side.BUY, 0.5, 62000.0, 60000.0) == pytest.approx(1000.0)


# ---------------------------------------------------------------------------
# Maintenance Margin
# ---------------------------------------------------------------------------
class TestMaintenanceMargin:
    def test_basic(self):
        # MM = size * price * mmr, mmr = 1/(2*max_lev)
        # size=1, price=50000, max_lev=10 → mmr=0.05 → MM=2500
        assert calc_maintenance_margin(1.0, 50000.0, 10) == pytest.approx(2500.0)

    def test_higher_leverage(self):
        # max_lev=50 → mmr=0.01 → MM=500
        assert calc_maintenance_margin(1.0, 50000.0, 50) == pytest.approx(500.0)

    def test_fractional_size(self):
        # size=0.1, price=50000, max_lev=20 → mmr=0.025 → MM=125
        assert calc_maintenance_margin(0.1, 50000.0, 20) == pytest.approx(125.0)


# ---------------------------------------------------------------------------
# Equity
# ---------------------------------------------------------------------------
class TestCalcEquity:
    def test_no_positions(self):
        assert calc_equity(10000.0, [], 50000.0) == pytest.approx(10000.0)

    def test_with_profitable_long(self):
        pos = Position(symbol="BTC", side=Side.BUY, size=1.0, entry_price=50000.0)
        # equity = 10000 + (51000 - 50000) = 11000
        assert calc_equity(10000.0, [pos], 51000.0) == pytest.approx(11000.0)

    def test_with_losing_short(self):
        pos = Position(symbol="BTC", side=Side.SELL, size=1.0, entry_price=50000.0)
        # equity = 10000 + (-1)*(51000 - 50000) = 9000
        assert calc_equity(10000.0, [pos], 51000.0) == pytest.approx(9000.0)


# ---------------------------------------------------------------------------
# Liquidation Check
# ---------------------------------------------------------------------------
class TestIsLiquidatable:
    def test_not_liquidatable(self):
        assert is_liquidatable(5000.0, 2500.0) is False

    def test_exactly_at_margin(self):
        # equity == total_mm → NOT liquidated (strict <)
        assert is_liquidatable(2500.0, 2500.0) is False

    def test_below_margin(self):
        assert is_liquidatable(2000.0, 2500.0) is True

    def test_empty_account_not_liquidatable(self):
        # No positions → never liquidate, even if equity is 0
        assert is_liquidatable(0.0, 0.0, has_positions=False) is False
        assert is_liquidatable(100.0, 200.0, has_positions=False) is False


# ---------------------------------------------------------------------------
# Liquidation Price (UI only)
# ---------------------------------------------------------------------------
class TestCalcLiqPrice:
    def test_long(self):
        # Long: P = (entry - balance/size) / (1 - mmr)
        # entry=50000, balance=5000, size=1, mmr=0.05
        # P = (50000 - 5000) / (1 - 0.05) = 45000 / 0.95 ≈ 47368.42
        result = calc_liq_price(Side.BUY, 50000.0, 5000.0, 1.0, 0.05)
        assert result == pytest.approx(47368.421, rel=1e-3)

    def test_short(self):
        # Short: P = (balance/size + entry) / (1 + mmr)
        # entry=50000, balance=5000, size=1, mmr=0.05
        # P = (5000 + 50000) / (1 + 0.05) = 55000 / 1.05 ≈ 52380.95
        result = calc_liq_price(Side.SELL, 50000.0, 5000.0, 1.0, 0.05)
        assert result == pytest.approx(52380.952, rel=1e-3)


# ---------------------------------------------------------------------------
# Slippage
# ---------------------------------------------------------------------------
class TestSlippage:
    def test_small_order(self):
        # notional=10000 → slippage = (10000/100000) * 0.0001 = 0.00001
        assert calc_slippage(10000.0) == pytest.approx(0.00001)

    def test_large_order(self):
        # notional=500000 → slippage = (500000/100000) * 0.0001 = 0.0005
        assert calc_slippage(500000.0) == pytest.approx(0.0005)

    def test_apply_buy(self):
        # BUY → price goes up
        result = apply_slippage(50000.0, Side.BUY, 0.0001)
        assert result == pytest.approx(50005.0)

    def test_apply_sell(self):
        # SELL → price goes down
        result = apply_slippage(50000.0, Side.SELL, 0.0001)
        assert result == pytest.approx(49995.0)


# ---------------------------------------------------------------------------
# Fees
# ---------------------------------------------------------------------------
class TestCalcFee:
    def test_taker(self):
        # notional=50000, rate=0.00045 → fee=22.5
        assert calc_fee(50000.0, 0.00045) == pytest.approx(22.5)

    def test_maker(self):
        # notional=50000, rate=0.00015 → fee=7.5
        assert calc_fee(50000.0, 0.00015) == pytest.approx(7.5)


# ---------------------------------------------------------------------------
# Size Conversion
# ---------------------------------------------------------------------------
class TestConvertSize:
    def test_usd_to_base(self):
        # 5000 USD at price 50000 → 0.1 base
        assert convert_size(5000.0, "USD", 50000.0) == pytest.approx(0.1)

    def test_base_passthrough(self):
        assert convert_size(0.5, "BASE", 50000.0) == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Realized PnL (side-aware)
# ---------------------------------------------------------------------------
class TestCalcRpnl:
    def test_long_reduce_profit(self):
        # Long: close 0.5 BTC, entry=50000, exit=52000
        # rpnl = 1 * (52000 - 50000) * 0.5 = 1000
        assert calc_rpnl(Side.BUY, 50000.0, 52000.0, 0.5) == pytest.approx(1000.0)

    def test_long_reduce_loss(self):
        # rpnl = 1 * (48000 - 50000) * 0.5 = -1000
        assert calc_rpnl(Side.BUY, 50000.0, 48000.0, 0.5) == pytest.approx(-1000.0)

    def test_short_reduce_profit(self):
        # Short: close 1 BTC, entry=50000, exit=48000
        # rpnl = -1 * (48000 - 50000) * 1 = 2000
        assert calc_rpnl(Side.SELL, 50000.0, 48000.0, 1.0) == pytest.approx(2000.0)

    def test_short_reduce_loss(self):
        # Short: close 1 BTC, entry=50000, exit=52000
        # rpnl = -1 * (52000 - 50000) * 1 = -2000
        assert calc_rpnl(Side.SELL, 50000.0, 52000.0, 1.0) == pytest.approx(-2000.0)


# ---------------------------------------------------------------------------
# Liq Price Edge Cases
# ---------------------------------------------------------------------------
class TestCalcLiqPriceEdge:
    def test_zero_size_returns_none(self):
        assert calc_liq_price(Side.BUY, 50000.0, 5000.0, 0.0, 0.05) is None

    def test_negative_size_returns_none(self):
        assert calc_liq_price(Side.SELL, 50000.0, 5000.0, -1.0, 0.05) is None

    def test_negative_result_returns_none(self):
        # Long with huge balance → formula yields negative price
        # P = (50000 - 100000/1) / (1 - 0.05) = -50000/0.95 < 0
        assert calc_liq_price(Side.BUY, 50000.0, 100000.0, 1.0, 0.05) is None


# ---------------------------------------------------------------------------
# Exec Price (USD slippage ordering)
# ---------------------------------------------------------------------------
class TestCalcExecPrice:
    def test_buy_usd(self):
        # $5000 at mid=50000 → base=0.1, mid_notional=5000
        # slippage = (5000/100000)*0.0001 = 0.000005
        # exec = 50000 * (1 + 0.000005) = 50000.25
        result = calc_exec_price(50000.0, Side.BUY, 5000.0, "USD")
        assert result == pytest.approx(50000.25)

    def test_sell_base(self):
        # 1 BTC at mid=50000, mid_notional=50000
        # slippage = (50000/100000)*0.0001 = 0.00005
        # exec = 50000 * (1 - 0.00005) = 49997.5
        result = calc_exec_price(50000.0, Side.SELL, 1.0, "BASE")
        assert result == pytest.approx(49997.5)


# ---------------------------------------------------------------------------
# Rounding Utilities
# ---------------------------------------------------------------------------
class TestRounding:
    def test_round_to_tick(self):
        assert round_to_tick(50000.13, 0.1) == pytest.approx(50000.1)
        assert round_to_tick(50000.15, 0.1) == pytest.approx(50000.2)

    def test_round_to_step(self):
        assert round_to_step(0.1234, 0.001) == pytest.approx(0.123)
        assert round_to_step(0.1235, 0.001) == pytest.approx(0.124)

    def test_zero_tick_passthrough(self):
        assert round_to_tick(50000.13, 0.0) == pytest.approx(50000.13)

    def test_zero_step_passthrough(self):
        assert round_to_step(0.1234, 0.0) == pytest.approx(0.1234)
