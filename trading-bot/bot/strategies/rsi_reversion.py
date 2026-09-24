"""Connors-style RSI(2) mean reversion: buy short, sharp dips in an uptrend."""
from __future__ import annotations

import math
import numbers

import pandas as pd

from ..indicators import check_period, rsi, sma
from ..models import Action, Position, Signal
from .base import Strategy


def _fmt(x: float) -> str:
    """Compact price for reason strings (works for BTC in KRW and sub-cent coins)."""
    return f"{x:,.2f}" if abs(x) >= 1 else f"{x:.4g}"


def _level(value: object, name: str) -> float:
    """An RSI threshold: a finite real number (bools and strings rejected)."""
    if isinstance(value, bool) or not isinstance(value, numbers.Real) or not math.isfinite(value):
        raise ValueError(f"rsi_reversion: {name} must be a number, got {value!r}")
    return float(value)


class RSIReversion(Strategy):
    """Buy when RSI(2) is deeply oversold above the trend SMA; sell on RSI
    strength or a close back above the short exit SMA."""

    name = "rsi_reversion"
    description = "Mean reversion: buy oversold RSI(2) dips in an uptrend, sell the bounce."
    defaults = {"rsi_period": 2, "entry_rsi": 10, "exit_rsi": 70, "trend_sma": 200, "exit_sma": 5}

    def validate_params(self) -> None:
        p = self.params
        p["rsi_period"] = check_period(p["rsi_period"], "rsi_period", minimum=2)
        p["trend_sma"] = check_period(p["trend_sma"], "trend_sma (0 disables)", minimum=0)
        p["exit_sma"] = check_period(p["exit_sma"], "exit_sma (0 disables)", minimum=0)
        entry, exit_ = _level(p["entry_rsi"], "entry_rsi"), _level(p["exit_rsi"], "exit_rsi")
        if not 0 < entry < exit_ < 100:
            raise ValueError(f"{self.name}: need 0 < entry_rsi < exit_rsi < 100, "
                             f"got entry_rsi={entry:g}, exit_rsi={exit_:g}")

    @property
    def min_bars(self) -> int:
        p = self.params
        # 10x the RSI period lets Wilder smoothing forget its starting value.
        return max(p["trend_sma"], p["exit_sma"], p["rsi_period"] * 10) + 1

    def generate_signal(self, bars: pd.DataFrame, position: Position | None) -> Signal:
        if len(bars) < self.min_bars:
            return Signal.hold(f"warming up ({len(bars)}/{self.min_bars} bars)")
        p = self.params
        close = bars["close"]
        price = close.iloc[-1]
        r = rsi(close, p["rsi_period"]).iloc[-1]
        trend = sma(close, p["trend_sma"]).iloc[-1] if p["trend_sma"] > 0 else None
        exit_ma = sma(close, p["exit_sma"]).iloc[-1] if p["exit_sma"] > 0 else None
        if any(pd.isna(v) for v in (price, r, trend, exit_ma) if v is not None):
            return Signal.hold("indicators not ready (NaN)")

        rsi_txt = f"RSI({p['rsi_period']})={r:.1f}"
        if position is not None and position.qty > 0:
            if r > p["exit_rsi"]:
                return Signal(Action.SELL, f"{rsi_txt}>{p['exit_rsi']:g}")
            if exit_ma is not None and price > exit_ma:
                return Signal(Action.SELL, f"close={_fmt(price)}>SMA{p['exit_sma']}={_fmt(exit_ma)}")
            return Signal.hold(f"holding: {rsi_txt}<={p['exit_rsi']:g}")

        if r >= p["entry_rsi"]:
            return Signal.hold(f"{rsi_txt}>={p['entry_rsi']:g}")
        if trend is not None and not price > trend:
            return Signal.hold(f"{rsi_txt} but close={_fmt(price)}<=SMA{p['trend_sma']}={_fmt(trend)}")
        trend_txt = f" & close>SMA{p['trend_sma']}" if trend is not None else ""
        return Signal(Action.BUY, f"{rsi_txt}<{p['entry_rsi']:g}{trend_txt}")
