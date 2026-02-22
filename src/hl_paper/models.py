from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from hl_paper.config import DEFAULT_LEVERAGE, STARTING_BALANCE


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class SizeUnit(str, Enum):
    USD = "USD"
    BASE = "BASE"


class OrderIntent(BaseModel):
    symbol: str
    side: Side
    order_type: OrderType
    size_value: float
    size_unit: SizeUnit
    leverage: int
    limit_price: Optional[float] = None
    reduce_only: bool = False
    client_id: str
    timestamp: int


class Position(BaseModel):
    symbol: str
    side: Side
    size: float = 0.0
    entry_price: float = 0.0
    leverage: int = DEFAULT_LEVERAGE
    mmr: float = 0.0

    @property
    def notional(self) -> float:
        return self.size * self.entry_price

    @property
    def side_sign(self) -> int:
        return 1 if self.side == Side.BUY else -1


class AccountState(BaseModel):
    balance: float = STARTING_BALANCE
    positions: dict[str, Position] = Field(default_factory=dict)
