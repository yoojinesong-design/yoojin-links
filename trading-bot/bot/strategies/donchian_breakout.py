"""Turtle-style Donchian channel breakout."""
from __future__ import annotations

import pandas as pd

from ..indicators import check_period, highest, lowest, sma
from ..models import Action, Position, Signal
from .base import Strategy


def _fmt(x: float) -> str:
    """Compact price for reason strings (works for BTC in KRW and sub-cent coins)."""
    return f"{x:,.2f}" if abs(x) >= 1 else f"{x:.4g}"


class DonchianBreakout(Strategy):
    """Buy a close above the previous ``entry_period`` bars' highest high;
    sell a close below the previous ``exit_period`` bars' lowest low."""

    name = "donchian_breakout"
    description = "Breakout: buy a close above the prior N-bar high, sell below the prior M-bar low."
    defaults = {"entry_period": 20, "exit_period": 10, "trend_sma": 0}

    def validate_params(self) -> None:
        p = self.params
        p["entry_period"] = check_period(p["entry_period"], "entry_period")
        p["exit_period"] = check_period(p["exit_period"], "exit_period")
        p["trend_sma"] = check_period(p["trend_sma"], "trend_sma (0 disables)", minimum=0)

    @property
    def min_bars(self) -> int:
        p = self.params
        return max(p["entry_period"], p["exit_period"], p["trend_sma"]) + 2

    def generate_signal(self, bars: pd.DataFrame, position: Position | None) -> Signal:
        if len(bars) < self.min_bars:
            return Signal.hold(f"warming up ({len(bars)}/{self.min_bars} bars)")
        p = self.params
        price = bars["close"].iloc[-1]
        # shift(1): the channel is built from the bars BEFORE the current one,
        # otherwise the current bar's own high could never be exceeded.
        upper = highest(bars["high"], p["entry_period"]).shift(1).iloc[-1]
        lower = lowest(bars["low"], p["exit_period"]).shift(1).iloc[-1]
        trend = sma(bars["close"], p["trend_sma"]).iloc[-1] if p["trend_sma"] > 0 else None
        if any(pd.isna(v) for v in (price, upper, lower, trend) if v is not None):
            return Signal.hold("indicators not ready (NaN)")

        if position is not None and position.qty > 0:
            if price < lower:
                return Signal(Action.SELL, f"close={_fmt(price)}<{p['exit_period']}-bar low={_fmt(lower)}")
            return Signal.hold(f"holding: close={_fmt(price)}>={p['exit_period']}-bar low={_fmt(lower)}")

        if not price > upper:
            return Signal.hold(f"close={_fmt(price)}<={p['entry_period']}-bar high={_fmt(upper)}")
        if trend is not None and not price > trend:
            return Signal.hold(f"breakout but close={_fmt(price)}<=SMA{p['trend_sma']}={_fmt(trend)}")
        trend_txt = f" & close>SMA{p['trend_sma']}" if trend is not None else ""
        return Signal(Action.BUY,
                      f"close={_fmt(price)}>{p['entry_period']}-bar high={_fmt(upper)}{trend_txt}")
