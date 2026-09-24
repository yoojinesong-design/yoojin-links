"""Technical indicators as pure functions.

Every function returns a float Series aligned to the input index and is
causal: the value at row ``i`` depends only on rows ``0..i``, so computing an
indicator on a prefix of the data gives exactly the same numbers as computing
it on the full data and truncating. Rows without enough history are NaN.
"""
from __future__ import annotations

import numbers

import numpy as np
import pandas as pd


def check_period(n: object, name: str = "n", minimum: int = 1) -> int:
    """Return ``n`` as an int, or raise ValueError unless it is an integer >= ``minimum``.

    Bools and floats are rejected (``20.5`` bars is meaningless, and a silent
    ``int()`` could hide a config typo).
    """
    if isinstance(n, bool) or not isinstance(n, numbers.Integral) or n < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}, got {n!r}")
    return int(n)


def sma(s: pd.Series, n: int) -> pd.Series:
    """Simple moving average of the last ``n`` values (NaN for the first n-1)."""
    n = check_period(n)
    return s.rolling(n, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    """Exponential moving average, ``span=n``, recursive form (``adjust=False``).

    Seeded with the first value, so there is no NaN warm-up; allow a few
    multiples of ``n`` bars before trusting it.
    """
    n = check_period(n)
    return s.ewm(span=n, adjust=False).mean()


def _wilder(s: pd.Series, n: int) -> pd.Series:
    """Wilder's smoothing (an EMA with alpha = 1/n), NaN until n observations."""
    return s.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    """Wilder's Relative Strength Index in [0, 100].

    Average gain/loss use Wilder smoothing of the bar-to-bar changes. Only
    gains -> 100, only losses -> 0, no movement at all -> 50. The first ``n``
    values are NaN (n changes are needed).
    """
    n = check_period(n)
    delta = s.astype(float).diff()
    # np.maximum/minimum keep the leading NaN (and are ~10x faster than clip).
    gain = _wilder(np.maximum(delta, 0.0), n).to_numpy()
    loss = _wilder(-np.minimum(delta, 0.0), n).to_numpy()
    total = gain + loss
    # 100 - 100 / (1 + gain/loss) == 100 * gain / (gain + loss): no special
    # case needed for loss == 0; the 0/0 "flat" case is mapped to 50.
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(total > 0, 100.0 * gain / total, 50.0)
    out[np.isnan(total)] = np.nan
    return pd.Series(out, index=s.index, name=s.name)


def true_range(df: pd.DataFrame) -> pd.Series:
    """max(high - low, |high - prev close|, |low - prev close|); the first bar
    has no previous close, so its true range is simply high - low."""
    prev_close = df["close"].shift(1)
    ranges = pd.concat(
        [df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()],
        axis=1,
    )
    return ranges.max(axis=1, skipna=True).astype(float)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """Wilder's Average True Range over ``n`` bars (first n-1 values NaN)."""
    n = check_period(n)
    return _wilder(true_range(df), n)


def highest(s: pd.Series, n: int) -> pd.Series:
    """Rolling max over the last ``n`` bars INCLUDING the current one.

    Use ``highest(s, n).shift(1)`` for "the previous n bars".
    """
    n = check_period(n)
    return s.rolling(n, min_periods=n).max()


def lowest(s: pd.Series, n: int) -> pd.Series:
    """Rolling min over the last ``n`` bars INCLUDING the current one."""
    n = check_period(n)
    return s.rolling(n, min_periods=n).min()
