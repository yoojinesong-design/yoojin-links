"""Strategy interface.

A strategy is a pure function of (closed bars, current position) -> Signal.
The SAME object is used by the live engine and the backtester, so what you
backtest is exactly what trades.

Rules every strategy must follow:
  * Only use ``bars`` passed in. The last row is the most recent CLOSED bar;
    there is no future data, and nothing may be cached between calls that
    would make results depend on call history.
  * Long-only: BUY means "be long", SELL means "exit the long".
  * Return HOLD (not raise) when there are fewer than ``min_bars`` rows or an
    indicator is still NaN.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd

from ..models import Position, Signal


class Strategy(ABC):
    name: str = "strategy"
    # One line for `python -m bot strategies`.
    description: str = ""
    # Default parameter values; subclasses override. Unknown keys passed to
    # __init__ raise ValueError so config typos fail loudly.
    defaults: dict[str, Any] = {}

    def __init__(self, **params: Any) -> None:
        unknown = set(params) - set(self.defaults)
        if unknown:
            raise ValueError(f"{self.name}: unknown parameter(s) {sorted(unknown)}; "
                             f"valid: {sorted(self.defaults)}")
        self.params: dict[str, Any] = {**self.defaults, **params}
        self.validate_params()

    def validate_params(self) -> None:
        """Raise ValueError for nonsensical parameter combinations."""

    @property
    @abstractmethod
    def min_bars(self) -> int:
        """Bars needed before the first valid signal (indicator warm-up)."""

    @abstractmethod
    def generate_signal(self, bars: pd.DataFrame, position: Position | None) -> Signal:
        """Decide what to do given closed ``bars`` and the open ``position``
        (None when flat)."""

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.params})"
