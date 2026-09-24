"""Trend following: be long while the fast SMA is above the slow SMA."""
from __future__ import annotations

import pandas as pd

from ..indicators import check_period, sma
from ..models import Action, Position, Signal
from .base import Strategy


def _fmt(x: float) -> str:
    """Compact price for reason strings (works for BTC in KRW and sub-cent coins)."""
    return f"{x:,.2f}" if abs(x) >= 1 else f"{x:.4g}"


class SMACrossover(Strategy):
    """Long while SMA(fast) > SMA(slow); exit when SMA(fast) < SMA(slow)."""

    name = "sma_crossover"
    description = "Trend following: long while the fast SMA is above the slow SMA."
    defaults = {"fast": 20, "slow": 50}

    def validate_params(self) -> None:
        p = self.params
        fast = p["fast"] = check_period(p["fast"], "fast")
        slow = p["slow"] = check_period(p["slow"], "slow")
        if fast >= slow:
            raise ValueError(f"{self.name}: fast ({fast}) must be < slow ({slow})")

    @property
    def min_bars(self) -> int:
        return self.params["slow"] + 1

    def generate_signal(self, bars: pd.DataFrame, position: Position | None) -> Signal:
        if len(bars) < self.min_bars:
            return Signal.hold(f"warming up ({len(bars)}/{self.min_bars} bars)")
        fast_n, slow_n = self.params["fast"], self.params["slow"]
        close = bars["close"]
        fast, slow = sma(close, fast_n).iloc[-1], sma(close, slow_n).iloc[-1]
        if pd.isna(fast) or pd.isna(slow):
            return Signal.hold("indicators not ready (NaN)")

        op = ">" if fast > slow else "<" if fast < slow else "="
        reason = f"SMA{fast_n}={_fmt(fast)} {op} SMA{slow_n}={_fmt(slow)}"
        long = position is not None and position.qty > 0
        if not long and fast > slow:
            return Signal(Action.BUY, reason)
        if long and fast < slow:
            return Signal(Action.SELL, reason)
        return Signal.hold(reason)
