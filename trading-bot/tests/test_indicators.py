"""Indicator values checked against hand-computed numbers, plus causality."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from bot.indicators import atr, check_period, ema, highest, lowest, rsi, sma, true_range

NaN = math.nan


def series(values, start: str = "2024-01-01") -> pd.Series:
    idx = pd.date_range(start, periods=len(values), freq="D", tz="UTC")
    return pd.Series(values, index=idx, dtype=float)


def ohlc(rows: list[tuple[float, float, float]]) -> pd.DataFrame:
    """(high, low, close) rows -> bars frame (open = previous close)."""
    idx = pd.date_range("2024-01-01", periods=len(rows), freq="D", tz="UTC")
    df = pd.DataFrame(rows, columns=["high", "low", "close"], index=idx, dtype=float)
    df.insert(0, "open", df["close"].shift(1).fillna(df["close"]))
    df["volume"] = 1000.0
    return df


def random_bars(n: int = 300, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, n)))
    open_ = np.concatenate([[close[0]], close[:-1]])
    wick = np.abs(rng.normal(0, 0.01, n))
    idx = pd.date_range("2023-01-01", periods=n, freq="D", tz="UTC")
    return pd.DataFrame({
        "open": open_, "high": np.maximum(open_, close) * (1 + wick),
        "low": np.minimum(open_, close) * (1 - wick), "close": close, "volume": 1.0,
    }, index=idx)


def assert_values(actual: pd.Series, expected: list[float]) -> None:
    np.testing.assert_allclose(actual.to_numpy(), np.array(expected, dtype=float),
                               rtol=0, atol=1e-12, equal_nan=True)


# --------------------------------------------------------------------- SMA / EMA
def test_sma_matches_hand_computed_values_and_keeps_index():
    s = series([1, 2, 3, 4, 5, 6])
    out = sma(s, 3)
    assert_values(out, [NaN, NaN, 2, 3, 4, 5])
    assert out.index.equals(s.index)


def test_sma_of_period_one_is_the_series_itself():
    s = series([3.5, 1.0, 7.25])
    assert_values(sma(s, 1), [3.5, 1.0, 7.25])


def test_sma_longer_than_data_is_all_nan():
    assert sma(series([1, 2, 3]), 5).isna().all()


def test_ema_is_recursive_with_span_alpha_and_seeded_by_first_value():
    # span=3 -> alpha = 2/(3+1) = 0.5; y0 = x0, y_t = 0.5*y_{t-1} + 0.5*x_t
    assert_values(ema(series([1, 2, 3, 4]), 3), [1.0, 1.5, 2.25, 3.125])


def test_ema_of_constant_series_is_constant():
    assert_values(ema(series([7.0] * 5), 4), [7.0] * 5)


# ---------------------------------------------------------------------------- RSI
def test_rsi_mixed_moves_hand_computed():
    # changes: +1, -1, +1, +1 ; alpha = 1/2, seeded with the first change
    # avg_gain: 1, .5, .75, .875   avg_loss: 0, .5, .25, .125
    # RSI = 100*g/(g+l); the first n=2 values are NaN
    assert_values(rsi(series([1, 2, 1, 2, 3]), 2), [NaN, NaN, 50.0, 75.0, 87.5])


def test_rsi_period_three_hand_computed():
    # changes: +2, -1, +1, -2, 0 ; alpha = 1/3
    # avg_gain: 2, 4/3, 11/9, 22/27, 44/81
    # avg_loss: 0, 1/3, 2/9, 22/27, 44/81
    # idx3: 100*(11/9)/(13/9) = 1100/13 ; idx4: 50 ; idx5: 50
    expected = [NaN, NaN, NaN, 1100 / 13, 50.0, 50.0]
    assert_values(rsi(series([10, 12, 11, 12, 10, 10]), 3), expected)


def test_rsi_all_gains_is_100():
    out = rsi(series(np.arange(1.0, 21.0)), 14)
    assert out.iloc[:14].isna().all()
    assert (out.iloc[14:] == 100.0).all()


def test_rsi_all_losses_is_0():
    out = rsi(series(np.arange(20.0, 0.0, -1.0)), 5)
    assert out.iloc[:5].isna().all()
    assert (out.iloc[5:] == 0.0).all()


def test_rsi_flat_prices_is_50():
    out = rsi(series([42.0] * 10), 3)
    assert out.iloc[:3].isna().all()
    assert (out.iloc[3:] == 50.0).all()


def test_rsi_stays_100_when_gains_are_followed_by_flat_prices():
    # avg_gain decays but stays > 0 while avg_loss is exactly 0 -> 100, not 50
    out = rsi(series([1, 2, 3, 3, 3, 3, 3]), 2)
    assert (out.iloc[2:] == 100.0).all()


def test_rsi_flat_start_then_rally():
    # both averages 0 during the flat part -> 50; any gain afterwards -> 100
    out = rsi(series([5, 5, 5, 6, 7]), 2)
    assert_values(out, [NaN, NaN, 50.0, 100.0, 100.0])


def test_rsi_first_n_values_are_nan_even_with_little_data():
    assert rsi(series([1, 2, 3]), 3).isna().all()      # only 2 changes
    assert rsi(series([1]), 2).isna().all()
    assert rsi(pd.Series([], dtype=float), 2).empty


def test_rsi_matches_textbook_formula_and_is_bounded():
    s = random_bars(400)["close"]
    delta = s.diff()
    g = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    textbook = 100 - 100 / (1 + g / loss)
    out = rsi(s, 14)
    pd.testing.assert_series_equal(out, textbook, check_names=False, rtol=1e-12)
    assert out.dropna().between(0, 100).all()


def test_rsi_accepts_integer_series():
    s = pd.Series([1, 2, 1, 2, 3])
    assert_values(rsi(s, 2), [NaN, NaN, 50.0, 75.0, 87.5])


# ---------------------------------------------------------------------------- ATR
ATR_ROWS = [   # (high, low, close)
    (10, 8, 9),       # TR = 10-8 = 2 (no previous close)
    (11, 9, 10.5),    # TR = max(2, |11-9|, |9-9|) = 2
    (12, 11, 11.5),   # TR = max(1, |12-10.5|, |11-10.5|) = 1.5
    (11, 7, 8),       # TR = max(4, |11-11.5|, |7-11.5|) = 4.5
    (6, 5, 5.5),      # gap down: TR = max(1, |6-8|, |5-8|) = 3
]


def test_true_range_uses_previous_close_for_gaps():
    assert_values(true_range(ohlc(ATR_ROWS)), [2, 2, 1.5, 4.5, 3])


def test_true_range_gap_up():
    df = ohlc([(10, 9, 10), (15, 14, 14.5)])   # TR = max(1, 5, 4) = 5
    assert_values(true_range(df), [1, 5])


def test_atr_is_wilder_smoothed_true_range_hand_computed():
    # alpha = 1/2, seeded with TR0 = 2; first n-1 = 1 value NaN
    # 2 -> 2 ; .5*2+.5*1.5 = 1.75 ; .5*1.75+.5*4.5 = 3.125 ; .5*3.125+.5*3 = 3.0625
    assert_values(atr(ohlc(ATR_ROWS), 2), [NaN, 2.0, 1.75, 3.125, 3.0625])


def test_atr_period_one_is_true_range():
    df = ohlc(ATR_ROWS)
    pd.testing.assert_series_equal(atr(df, 1), true_range(df))


# -------------------------------------------------------------- highest / lowest
def test_highest_and_lowest_include_the_current_bar():
    s = series([1, 3, 2, 5, 4])
    assert_values(highest(s, 2), [NaN, 3, 3, 5, 5])
    assert_values(lowest(s, 2), [NaN, 1, 2, 2, 4])


def test_shifted_highest_means_previous_n_bars():
    s = series([1, 3, 2, 5, 4])
    assert_values(highest(s, 2).shift(1), [NaN, NaN, 3, 3, 5])
    assert_values(lowest(s, 3).shift(1), [NaN, NaN, NaN, 1, 2])


# ------------------------------------------------------------- shared properties
INDICATOR_CALLS = {
    "sma": lambda df: sma(df["close"], 10),
    "ema": lambda df: ema(df["close"], 10),
    "rsi": lambda df: rsi(df["close"], 14),
    "rsi2": lambda df: rsi(df["close"], 2),
    "atr": lambda df: atr(df, 14),
    "true_range": true_range,
    "highest": lambda df: highest(df["high"], 20),
    "lowest": lambda df: lowest(df["low"], 20),
}


@pytest.mark.parametrize("name", sorted(INDICATOR_CALLS))
def test_indicators_never_look_ahead(name):
    """Value at row i must not depend on rows after i: computing on a prefix
    gives exactly the full-data values truncated, even if the future is wild."""
    calc = INDICATOR_CALLS[name]
    df = random_bars(250)
    full = calc(df)
    crazy_future = df.copy()
    crazy_future.iloc[150:] = crazy_future.iloc[150:] * 50.0
    crazy = calc(crazy_future)
    for k in (1, 2, 15, 30, 100, 150, 249):
        pd.testing.assert_series_equal(calc(df.iloc[:k]), full.iloc[:k], check_exact=True)
        if k <= 150:
            pd.testing.assert_series_equal(crazy.iloc[:k], full.iloc[:k], check_exact=True)


@pytest.mark.parametrize("name", sorted(INDICATOR_CALLS))
def test_indicators_return_aligned_float_series_and_do_not_mutate_input(name):
    df = random_bars(60)
    before = df.copy()
    out = INDICATOR_CALLS[name](df)
    assert isinstance(out, pd.Series)
    assert out.index.equals(df.index)
    assert out.dtype == np.float64
    pd.testing.assert_frame_equal(df, before)


@pytest.mark.parametrize("func", [sma, ema, rsi, highest, lowest])
@pytest.mark.parametrize("bad", [0, -3, 2.5, 3.0, True, "14", None])
def test_series_indicators_reject_invalid_periods(func, bad):
    with pytest.raises(ValueError):
        func(series([1, 2, 3, 4]), bad)


@pytest.mark.parametrize("bad", [0, -1, 1.5, False])
def test_atr_rejects_invalid_periods(bad):
    with pytest.raises(ValueError):
        atr(ohlc(ATR_ROWS), bad)


def test_numpy_integer_periods_are_accepted():
    s = series([1, 2, 3, 4])
    assert_values(sma(s, np.int64(2)), [NaN, 1.5, 2.5, 3.5])


def test_check_period_minimum_and_message():
    assert check_period(0, "trend_sma", minimum=0) == 0
    assert check_period(np.int32(5)) == 5
    with pytest.raises(ValueError, match="slow must be an integer >= 1"):
        check_period(0, "slow")
