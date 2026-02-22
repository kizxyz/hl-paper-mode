from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from hl_paper.models import Position, Side


def calc_upnl(side: Side, size: float, mark_price: float, entry_price: float) -> float:
    """uPnL = side_sign * size * (price - entry)"""
    from hl_paper.models import Side as _Side

    sign = 1 if side == _Side.BUY else -1
    return sign * size * (mark_price - entry_price)


def calc_equity(balance: float, positions: Sequence[Position], mark_price: float) -> float:
    """equity = balance + sum(uPnL)"""
    total_upnl = sum(
        calc_upnl(p.side, p.size, mark_price, p.entry_price) for p in positions
    )
    return balance + total_upnl


def calc_maintenance_margin(size: float, price: float, max_leverage: int) -> float:
    """MM = size * price * mmr, where mmr = 1 / (2 * max_leverage)"""
    mmr = 1.0 / (2.0 * max_leverage)
    return size * price * mmr


def is_liquidatable(equity: float, total_mm: float) -> bool:
    """equity <= total_MM → liquidate"""
    return equity <= total_mm


def calc_liq_price(
    side: Side, entry: float, balance: float, size: float, mmr: float
) -> float:
    """Single-position liquidation price (UI display only).

    Long:  P = (entry - balance/size) / (1 - mmr)
    Short: P = (balance/size + entry) / (1 + mmr)
    """
    from hl_paper.models import Side as _Side

    if side == _Side.BUY:
        return (entry - balance / size) / (1.0 - mmr)
    else:
        return (balance / size + entry) / (1.0 + mmr)


def calc_slippage(notional: float) -> float:
    """slippage = (notional / 100000) * 0.0001"""
    return (notional / 100_000.0) * 0.0001


def apply_slippage(price: float, side: Side, slippage: float) -> float:
    """BUY: price *= (1 + slippage), SELL: price *= (1 - slippage)"""
    from hl_paper.models import Side as _Side

    if side == _Side.BUY:
        return price * (1.0 + slippage)
    else:
        return price * (1.0 - slippage)


def calc_fee(notional: float, fee_rate: float) -> float:
    """fee = notional * fee_rate"""
    return notional * fee_rate


def convert_size(size_value: float, size_unit: str, exec_price: float) -> float:
    """Convert order size to base units.

    USD  → base_size = size_value / exec_price
    BASE → base_size = size_value
    """
    if size_unit == "USD":
        return size_value / exec_price
    return size_value
