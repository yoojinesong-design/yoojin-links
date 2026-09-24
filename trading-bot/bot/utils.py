"""Small helpers: timeframes, closed-bar filtering, bar validation."""
from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone

import pandas as pd

from .models import BAR_COLUMNS

_TF_RE = re.compile(r"^(\d+)([mhdw])$")
_TF_UNITS = {"m": "minutes", "h": "hours", "d": "days", "w": "weeks"}

SUPPORTED_TIMEFRAMES = ("1m", "5m", "15m", "30m", "1h", "4h", "1d")


def timeframe_to_timedelta(timeframe: str) -> timedelta:
    """'15m' -> 15 minutes, '1h' -> 1 hour, '1d' -> 1 day."""
    m = _TF_RE.match(timeframe.strip().lower())
    if not m:
        raise ValueError(f"Unsupported timeframe {timeframe!r}; use one of {SUPPORTED_TIMEFRAMES}")
    return timedelta(**{_TF_UNITS[m.group(2)]: int(m.group(1))})


def bars_per_year(timeframe: str, trading_days_per_year: int = 365) -> float:
    """Number of bars in a year, for annualising returns/Sharpe.

    Stocks trade ~252 days a year with a ~6.5h session, crypto 365 x 24h.
    For intraday stock bars this is an approximation.
    """
    td = timeframe_to_timedelta(timeframe)
    if td >= timedelta(days=1):
        return trading_days_per_year / (td / timedelta(days=1))
    hours_per_day = 24.0 if trading_days_per_year >= 365 else 6.5
    return trading_days_per_year * hours_per_day * 3600.0 / td.total_seconds()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def drop_incomplete_bars(bars: pd.DataFrame, timeframe: str, now: datetime | None = None) -> pd.DataFrame:
    """Keep only bars whose period has fully ended by ``now``.

    Exchanges return the still-forming bar as the last row; trading on it
    would be look-ahead in a backtest and noise in live trading.
    """
    if bars.empty:
        return bars
    now = now or utcnow()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    closes_at = bars.index + timeframe_to_timedelta(timeframe)
    return bars[closes_at <= pd.Timestamp(now)]


def validate_bars(bars: pd.DataFrame) -> pd.DataFrame:
    """Return bars in canonical form or raise ValueError.

    Canonical: UTC tz-aware DatetimeIndex (bar open time), ascending, unique,
    float columns exactly ``BAR_COLUMNS``, no NaN prices.
    """
    missing = [c for c in BAR_COLUMNS if c not in bars.columns]
    if missing:
        raise ValueError(f"bars missing columns {missing}")
    if not isinstance(bars.index, pd.DatetimeIndex):
        raise ValueError("bars index must be a DatetimeIndex")
    out = bars[BAR_COLUMNS].astype(float)
    if out.index.tz is None:
        out.index = out.index.tz_localize("UTC")
    else:
        out.index = out.index.tz_convert("UTC")
    out = out[~out.index.duplicated(keep="last")].sort_index()
    if out[["open", "high", "low", "close"]].isna().any().any():
        raise ValueError("bars contain NaN prices")
    return out


def floor_to_step(value: float, step: float) -> float:
    """Round ``value`` DOWN to a multiple of ``step`` (never order more than intended)."""
    if step <= 0:
        return value
    return math.floor(value / step + 1e-9) * step
