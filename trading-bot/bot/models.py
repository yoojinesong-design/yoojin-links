"""Core data types shared by every module.

Bars are plain pandas DataFrames (see ``BAR_COLUMNS``) rather than a custom
type, so indicators and strategies can use vectorised pandas code directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# A bars DataFrame has a tz-aware UTC DatetimeIndex holding each bar's OPEN
# time, sorted ascending, with exactly these float columns.
BAR_COLUMNS = ["open", "high", "low", "close", "volume"]


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class Action(str, Enum):
    BUY = "buy"    # enter (or stay in) a long position
    SELL = "sell"  # exit the long position
    HOLD = "hold"  # do nothing


@dataclass(frozen=True)
class Signal:
    action: Action
    reason: str = ""

    @classmethod
    def hold(cls, reason: str = "") -> "Signal":
        return cls(Action.HOLD, reason)


@dataclass
class Position:
    symbol: str
    qty: float              # base units (shares / coins); > 0 means long
    avg_entry_price: float
    market_price: float

    @property
    def market_value(self) -> float:
        return self.qty * self.market_price

    @property
    def unrealized_pnl(self) -> float:
        return (self.market_price - self.avg_entry_price) * self.qty

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.avg_entry_price <= 0:
            return 0.0
        return (self.market_price / self.avg_entry_price - 1.0) * 100.0


@dataclass
class Account:
    equity: float           # cash + market value of positions
    cash: float
    buying_power: float     # what can actually be spent right now
    currency: str = "USD"
    # Equity at the previous session close, when the broker reports it
    # (Alpaca ``last_equity``). Used as the daily-loss baseline.
    day_start_equity: float | None = None
    trading_blocked: bool = False
    # Symbols whose holdings could not be priced this time (valued at their last
    # known or entry price instead), so equity is uncertain: the engine makes no
    # new entries on such a snapshot but still runs exits for the other symbols.
    unpriced: tuple[str, ...] = ()


@dataclass
class OrderRequest:
    symbol: str
    side: Side
    qty: float              # base units, always > 0 (market orders only)
    reason: str = ""
    client_order_id: str | None = None


@dataclass
class OrderResult:
    id: str
    symbol: str
    side: Side
    qty: float
    # "filled" | "accepted" (sent, not yet filled) | "rejected"
    status: str
    filled_qty: float = 0.0
    filled_avg_price: float | None = None
    reason: str = ""
    raw: dict[str, Any] | None = field(default=None, repr=False)

    @property
    def ok(self) -> bool:
        return self.status in ("filled", "accepted")
