from __future__ import annotations

from hl_paper.config import TAKER_FEE_RATE, TICK_SIZE
from hl_paper.math_core import (
    calc_exec_price,
    calc_fee,
    calc_rpnl,
    convert_size,
)
from hl_paper.models import (
    AccountState,
    Fill,
    OpenOrder,
    Position,
    Side,
)


def calc_spread(mid_price: float, tick: float = TICK_SIZE) -> tuple[float, float]:
    """Returns (bid, ask) from mid price."""
    half = tick / 2.0
    return mid_price - half, mid_price + half


def execute_market_order(
    symbol: str,
    side: Side,
    size_value: float,
    size_unit: str,
    mid_price: float,
    fee_rate: float = TAKER_FEE_RATE,
) -> Fill:
    """Execute a market order: compute exec price with slippage, size, fee."""
    exec_price = calc_exec_price(mid_price, side, size_value, size_unit)
    base_size = convert_size(size_value, size_unit, exec_price)
    notional = base_size * exec_price
    fee = calc_fee(notional, fee_rate)

    return Fill(
        symbol=symbol,
        side=side,
        size=base_size,
        price=exec_price,
        fee=fee,
    )


def check_limit_fill(
    order: OpenOrder,
    mid_price: float,
    tick: float = TICK_SIZE,
    fee_rate: float = TAKER_FEE_RATE,
) -> Fill | None:
    """Check if a limit order fills at current mid price.

    BUY fills when ask <= limit_price
    SELL fills when bid >= limit_price
    Fills at limit price. No partial fills.
    """
    bid, ask = calc_spread(mid_price, tick)

    if order.side == Side.BUY and ask <= order.limit_price:
        pass  # fills
    elif order.side == Side.SELL and bid >= order.limit_price:
        pass  # fills
    else:
        return None

    notional = order.size * order.limit_price
    fee = calc_fee(notional, fee_rate)

    return Fill(
        symbol=order.symbol,
        side=order.side,
        size=order.size,
        price=order.limit_price,
        fee=fee,
        order_id=order.order_id,
    )


def apply_fill_to_position(
    state: AccountState,
    fill: Fill,
    leverage: int,
) -> None:
    """Apply a fill to account state. Handles open/increase/reduce/close/flip.

    Raises ValueError on leverage mismatch when increasing.
    """
    symbol = fill.symbol
    pos = state.positions.get(symbol)

    if pos is None:
        # Open new position
        mmr = 1.0 / (2.0 * leverage)
        state.positions[symbol] = Position(
            symbol=symbol,
            side=fill.side,
            size=fill.size,
            entry_price=fill.price,
            leverage=leverage,
            mmr=mmr,
        )
        state.balance -= fill.fee
        return

    same_side = pos.side == fill.side

    if same_side:
        # Increase — leverage must match
        if leverage != pos.leverage:
            raise ValueError(
                f"Leverage mismatch: position has {pos.leverage}x, "
                f"order uses {leverage}x"
            )
        new_size = pos.size + fill.size
        new_entry = (pos.size * pos.entry_price + fill.size * fill.price) / new_size
        pos.size = new_size
        pos.entry_price = new_entry
        state.balance -= fill.fee
        return

    # Opposite side — reduce / close / flip
    if fill.size < pos.size:
        # Reduce
        rpnl = calc_rpnl(pos.side, pos.entry_price, fill.price, fill.size)
        pos.size -= fill.size
        state.balance += rpnl - fill.fee
    elif fill.size == pos.size:
        # Close
        rpnl = calc_rpnl(pos.side, pos.entry_price, fill.price, fill.size)
        del state.positions[symbol]
        state.balance += rpnl - fill.fee
    else:
        # Flip: close existing, open remainder opposite
        close_size = pos.size
        rpnl = calc_rpnl(pos.side, pos.entry_price, fill.price, close_size)
        state.balance += rpnl - fill.fee

        remainder = fill.size - close_size
        mmr = 1.0 / (2.0 * leverage)
        state.positions[symbol] = Position(
            symbol=symbol,
            side=fill.side,
            size=remainder,
            entry_price=fill.price,
            leverage=leverage,
            mmr=mmr,
        )
