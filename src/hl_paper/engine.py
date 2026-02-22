from __future__ import annotations

import uuid
from typing import Any

from hl_paper.config import TICK_SIZE
from hl_paper.execution import (
    apply_fill_to_position,
    check_limit_fill,
    execute_market_order,
)
from hl_paper.math_core import (
    calc_equity,
    calc_maintenance_margin,
    calc_rpnl,
    is_liquidatable,
)
from hl_paper.models import (
    AccountState,
    OpenOrder,
    OrderIntent,
    OrderType,
    Side,
)


class Engine:
    """Single-writer simulation engine.

    All state mutations go through this class.
    Event flow: event → engine → mutate state → (emit WS) → (queue DB write)
    """

    def __init__(self, state: AccountState | None = None) -> None:
        self.state = state or AccountState()
        self.prices: dict[str, float] = {}
        self._ws_listeners: list = []

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def on_price_update(self, symbol: str, price: float) -> None:
        """PriceUpdate event — store latest mid price, check limit fills."""
        self.prices[symbol] = price
        self._check_limit_fills(symbol)

    def on_order(self, intent: OrderIntent) -> dict[str, Any]:
        """OrderEvent — validate, execute or rest."""
        mid = self.prices.get(intent.symbol)
        if mid is None:
            return {"status": "rejected", "reason": "no price available"}

        # Leverage check for existing position (same-side increase)
        pos = self.state.positions.get(intent.symbol)
        if pos is not None and pos.side == intent.side and intent.leverage != pos.leverage:
            return {
                "status": "rejected",
                "reason": f"leverage mismatch: position has {pos.leverage}x, order uses {intent.leverage}x",
            }

        if intent.order_type == OrderType.MARKET:
            return self._execute_market(intent, mid)

        # Limit order
        return self._handle_limit(intent, mid)

    def on_cancel(self, order_id: str) -> dict[str, Any]:
        """CancelEvent — remove open order."""
        if order_id not in self.state.open_orders:
            return {"status": "not_found"}

        del self.state.open_orders[order_id]
        return {"status": "cancelled", "order_id": order_id}

    # ------------------------------------------------------------------
    # Liquidation
    # ------------------------------------------------------------------

    def check_liquidations(self) -> list[str]:
        """Liquidation loop per spec: while equity < total_MM, close worst position."""
        closed: list[str] = []

        while True:
            positions = list(self.state.positions.values())
            if not positions:
                break

            # Compute equity using per-symbol prices
            total_upnl = 0.0
            total_mm = 0.0
            worst_symbol = None
            worst_upnl = float("inf")

            for p in positions:
                mark = self.prices.get(p.symbol, p.entry_price)
                sign = 1 if p.side == Side.BUY else -1
                upnl = sign * p.size * (mark - p.entry_price)
                total_upnl += upnl
                total_mm += calc_maintenance_margin(p.size, mark, p.leverage)

                if upnl < worst_upnl:
                    worst_upnl = upnl
                    worst_symbol = p.symbol

            equity = self.state.balance + total_upnl

            if not is_liquidatable(equity, total_mm, has_positions=True):
                break

            # Close worst position at mark
            p = self.state.positions[worst_symbol]
            mark = self.prices.get(worst_symbol, p.entry_price)
            rpnl = calc_rpnl(p.side, p.entry_price, mark, p.size)
            self.state.balance += rpnl
            del self.state.positions[worst_symbol]
            closed.append(worst_symbol)

        return closed

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _execute_market(self, intent: OrderIntent, mid: float) -> dict[str, Any]:
        fill = execute_market_order(
            symbol=intent.symbol,
            side=intent.side,
            size_value=intent.size_value,
            size_unit=intent.size_unit.value,
            mid_price=mid,
        )

        try:
            apply_fill_to_position(self.state, fill, intent.leverage)
        except ValueError as e:
            return {"status": "rejected", "reason": str(e)}

        self.check_liquidations()
        return {"status": "filled", "fill": fill.model_dump()}

    def _handle_limit(self, intent: OrderIntent, mid: float) -> dict[str, Any]:
        from hl_paper.math_core import convert_size

        base_size = convert_size(intent.size_value, intent.size_unit.value, mid)

        order = OpenOrder(
            order_id=str(uuid.uuid4()),
            symbol=intent.symbol,
            side=intent.side,
            order_type=intent.order_type,
            size=base_size,
            limit_price=intent.limit_price,
            leverage=intent.leverage,
            reduce_only=intent.reduce_only,
            client_id=intent.client_id,
            timestamp=intent.timestamp,
        )

        # Check if it fills immediately
        fill = check_limit_fill(order, mid)
        if fill is not None:
            try:
                apply_fill_to_position(self.state, fill, intent.leverage)
            except ValueError as e:
                return {"status": "rejected", "reason": str(e)}
            self.check_liquidations()
            return {"status": "filled", "fill": fill.model_dump(), "order_id": order.order_id}

        # Rest the order
        self.state.open_orders[order.order_id] = order
        return {"status": "resting", "order_id": order.order_id}

    def _check_limit_fills(self, symbol: str) -> None:
        """Check all resting orders for the given symbol against new price."""
        mid = self.prices.get(symbol)
        if mid is None:
            return

        to_remove: list[str] = []
        for oid, order in self.state.open_orders.items():
            if order.symbol != symbol:
                continue

            fill = check_limit_fill(order, mid)
            if fill is not None:
                try:
                    apply_fill_to_position(self.state, fill, order.leverage)
                except ValueError:
                    pass  # reject silently for resting orders
                to_remove.append(oid)

        for oid in to_remove:
            del self.state.open_orders[oid]

        if to_remove:
            self.check_liquidations()
