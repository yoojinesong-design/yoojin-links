"""Tests for bot.data: synthetic bars, CSV loading and the data feeds (all offline)."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from bot.data import (
    DEFAULT_SYNTHETIC_END,
    CSVFeed,
    DataFeed,
    SyntheticFeed,
    generate_synthetic_bars,
    load_csv_bars,
)
from bot.models import BAR_COLUMNS
from bot.utils import SUPPORTED_TIMEFRAMES, drop_incomplete_bars, timeframe_to_timedelta, validate_bars

UTC = timezone.utc


def assert_canonical(bars: pd.DataFrame) -> None:
    assert list(bars.columns) == BAR_COLUMNS
    assert isinstance(bars.index, pd.DatetimeIndex)
    assert str(bars.index.tz) == "UTC"
    assert bars.index.is_monotonic_increasing and bars.index.is_unique
    assert all(bars[c].dtype == np.float64 for c in BAR_COLUMNS)
    assert not bars[["open", "high", "low", "close"]].isna().any().any()
    pd.testing.assert_frame_equal(validate_bars(bars), bars)


def assert_valid_ohlc(bars: pd.DataFrame) -> None:
    assert (bars["low"] > 0).all()
    assert (bars["low"] <= bars[["open", "close"]].min(axis=1)).all()
    assert (bars["high"] >= bars[["open", "close"]].max(axis=1)).all()


def write_csv(tmp_path: Path, text: str, name: str = "bars.csv") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


class FixedClock:
    """A clock the test can move."""

    def __init__(self, now: datetime) -> None:
        self.now = now
        self.calls = 0

    def __call__(self) -> datetime:
        self.calls += 1
        return self.now


# =========================================================================== generate_synthetic_bars


def test_synthetic_bars_are_canonical_with_valid_ohlc_and_positive_volume():
    bars = generate_synthetic_bars(1500)
    assert len(bars) == 1500
    assert_canonical(bars)
    assert_valid_ohlc(bars)
    assert (bars["volume"] > 0).all()


def test_synthetic_bars_are_deterministic_for_a_seed():
    pd.testing.assert_frame_equal(generate_synthetic_bars(500, seed=7), generate_synthetic_bars(500, seed=7))


def test_different_seeds_give_different_prices():
    a, b = generate_synthetic_bars(300, seed=1), generate_synthetic_bars(300, seed=2)
    assert a.index.equals(b.index)
    assert not np.allclose(a["close"], b["close"])


def test_synthetic_bars_all_close_by_the_fixed_default_end():
    bars = generate_synthetic_bars(100)
    assert DEFAULT_SYNTHETIC_END.isoformat() == "2026-01-01T00:00:00+00:00"
    assert bars.index[-1] == pd.Timestamp("2025-12-31", tz="UTC")
    assert len(drop_incomplete_bars(bars, "1d", DEFAULT_SYNTHETIC_END)) == 100


@pytest.mark.parametrize("timeframe", SUPPORTED_TIMEFRAMES)
def test_synthetic_bars_are_aligned_and_evenly_spaced_for_every_timeframe(timeframe):
    td = timeframe_to_timedelta(timeframe)
    end = datetime(2025, 6, 3, 13, 47, 29, tzinfo=UTC)  # deliberately not aligned
    bars = generate_synthetic_bars(400, timeframe, end=end)
    assert_canonical(bars)
    assert_valid_ohlc(bars)
    assert (bars.index.to_series().diff().dropna() == td).all()
    epoch = pd.Timestamp(0, tz="UTC")
    assert all((t - epoch) % td == timedelta(0) for t in bars.index[[0, -1]])
    last_close = bars.index[-1] + td
    assert last_close <= pd.Timestamp(end) < last_close + td  # newest bar closed, next one would not have


def test_synthetic_end_naive_is_utc_and_other_timezones_are_converted():
    naive = generate_synthetic_bars(50, "1h", end=datetime(2025, 1, 1, 12))
    aware = generate_synthetic_bars(50, "1h", end=datetime(2025, 1, 1, 12, tzinfo=UTC))
    seoul = generate_synthetic_bars(50, "1h", end=datetime(2025, 1, 1, 21, tzinfo=timezone(timedelta(hours=9))))
    pd.testing.assert_frame_equal(naive, aware)
    pd.testing.assert_frame_equal(seoul, aware)
    assert aware.index[-1] == pd.Timestamp("2025-01-01 11:00", tz="UTC")


def test_synthetic_first_bar_opens_at_start_price():
    bars = generate_synthetic_bars(10, start_price=250.0)
    assert bars["open"].iloc[0] == pytest.approx(250.0)


def test_synthetic_single_bar():
    bars = generate_synthetic_bars(1)
    assert len(bars) == 1
    assert_valid_ohlc(bars)


def test_synthetic_zero_volatility_is_still_valid():
    bars = generate_synthetic_bars(200, annual_vol=0.0)
    assert_valid_ohlc(bars)
    assert (bars["high"] == bars[["open", "close"]].max(axis=1)).all()


def test_synthetic_long_history_stays_positive_and_finite():
    bars = generate_synthetic_bars(5000, seed=3)
    assert np.isfinite(bars.to_numpy()).all()
    assert (bars["low"] > 0).all()


def test_synthetic_prices_have_both_up_and_down_regimes():
    close = generate_synthetic_bars(1500)["close"]
    quarterly = close.iloc[::63].pct_change().dropna()
    assert (quarterly > 0.05).any() and (quarterly < -0.05).any()


@pytest.mark.parametrize("seed", [1, 42, 123])
def test_synthetic_prices_give_moving_average_crossovers_to_trade(seed):
    close = generate_synthetic_bars(1500, seed=seed)["close"]
    above = (close.rolling(20).mean() > close.rolling(50).mean())[50:]
    crossings = int((above != above.shift()).sum()) - 1
    assert crossings >= 6


@pytest.mark.parametrize(
    "kwargs",
    [
        {"n_bars": 0},
        {"n_bars": -5},
        {"n_bars": 2.5},
        {"n_bars": True},
        {"n_bars": 10, "start_price": 0},
        {"n_bars": 10, "start_price": float("nan")},
        {"n_bars": 10, "annual_vol": -0.1},
        {"n_bars": 10, "annual_drift": float("inf")},
        {"n_bars": 10, "timeframe": "1y"},
        {"n_bars": 10, "timeframe": "0m"},
    ],
)
def test_synthetic_rejects_bad_arguments(kwargs):
    with pytest.raises(ValueError):
        generate_synthetic_bars(**kwargs)


# =========================================================================== SyntheticFeed

NOW = datetime(2026, 9, 24, 13, 37, 12, 345678, tzinfo=UTC)


def test_synthetic_feed_satisfies_the_datafeed_protocol():
    assert isinstance(SyntheticFeed(), DataFeed)
    assert isinstance(CSVFeed({"X": generate_synthetic_bars(5)}), DataFeed)


@pytest.mark.parametrize("timeframe", SUPPORTED_TIMEFRAMES)
def test_synthetic_feed_returns_limit_bars_ending_with_the_forming_bar(timeframe):
    td = timeframe_to_timedelta(timeframe)
    bars = SyntheticFeed(clock=lambda: NOW).get_bars("AAPL", timeframe, 120)
    assert len(bars) == 120
    assert_canonical(bars)
    assert_valid_ohlc(bars)
    assert (bars["volume"] >= 0).all()
    assert (bars.index.to_series().diff().dropna() == td).all()
    assert bars.index[-1] <= pd.Timestamp(NOW) < bars.index[-1] + td  # last bar is forming
    closed = drop_incomplete_bars(bars, timeframe, NOW)
    assert len(closed) == 119
    assert closed.index.equals(bars.index[:-1])


def test_synthetic_feed_bars_are_identical_whatever_the_clock_time():
    clock = FixedClock(NOW)
    feed = SyntheticFeed(seed=5, clock=clock)
    early = feed.get_bars("BTC/USDT", "1h", 50)
    clock.now = NOW + timedelta(hours=7, minutes=23, seconds=5)
    late = feed.get_bars("BTC/USDT", "1h", 50)
    completed_early = early.iloc[:-1]
    overlap = completed_early.index.intersection(late.index)
    assert len(overlap) == 41
    pd.testing.assert_frame_equal(completed_early.loc[overlap], late.loc[overlap])


def test_synthetic_feed_is_stateless_across_instances_and_request_order():
    a = SyntheticFeed(seed=9, clock=lambda: NOW)
    b = SyntheticFeed(seed=9, clock=lambda: NOW)
    a.get_bars("ETH/USDT", "1d", 10)  # extra calls must not change anything
    a.get_latest_price("SPY")
    pd.testing.assert_frame_equal(a.get_bars("SPY", "15m", 30), b.get_bars("SPY", "15m", 30))
    assert a.get_latest_price("SPY") == b.get_latest_price("SPY")


def test_synthetic_feed_different_limits_agree_on_shared_bars():
    feed = SyntheticFeed(clock=lambda: NOW)
    small, large = feed.get_bars("QQQ", "1d", 20), feed.get_bars("QQQ", "1d", 300)
    pd.testing.assert_frame_equal(small, large.iloc[-20:])


def test_synthetic_feed_forming_bar_grows_into_the_completed_bar():
    clock = FixedClock(datetime(2026, 3, 2, 10, 20, tzinfo=UTC))
    feed = SyntheticFeed(clock=clock)
    forming = feed.get_bars("AAPL", "1h", 3).iloc[-1]
    clock.now = datetime(2026, 3, 2, 12, 5, tzinfo=UTC)
    done = feed.get_bars("AAPL", "1h", 5).loc[pd.Timestamp("2026-03-02 10:00", tz="UTC")]
    assert forming["open"] == done["open"]
    assert forming["high"] <= done["high"] and forming["low"] >= done["low"]
    assert forming["volume"] <= done["volume"]


def test_synthetic_feed_latest_price_is_the_forming_close_for_every_timeframe():
    feed = SyntheticFeed(clock=lambda: NOW)
    price = feed.get_latest_price("BTC/USDT")
    for timeframe in SUPPORTED_TIMEFRAMES:
        forming = feed.get_bars("BTC/USDT", timeframe, 3).iloc[-1]
        assert forming["close"] == price
        assert forming["low"] <= price <= forming["high"]


def test_synthetic_feed_price_is_continuous_across_bar_boundaries():
    clock = FixedClock(datetime(2026, 5, 5, 23, 59, 59, 999999, tzinfo=UTC))
    feed = SyntheticFeed(clock=clock)
    just_before = feed.get_latest_price("MSFT")
    clock.now = datetime(2026, 5, 6, 0, 0, 1, tzinfo=UTC)
    bars = feed.get_bars("MSFT", "1d", 3)
    assert bars["close"].iloc[-2] == pytest.approx(just_before, rel=1e-6)
    assert bars["open"].iloc[-1] == bars["close"].iloc[-2]  # completed close == next open


def test_synthetic_feed_at_exact_bar_open_the_forming_bar_is_flat():
    at_open = datetime(2026, 5, 6, tzinfo=UTC)
    feed = SyntheticFeed(clock=lambda: at_open)
    bar = feed.get_bars("MSFT", "1d", 2).iloc[-1]
    assert bar.name == pd.Timestamp(at_open)
    assert bar["open"] == bar["high"] == bar["low"] == bar["close"] == feed.get_latest_price("MSFT")
    assert bar["volume"] == 0


def test_synthetic_feed_reads_the_clock_on_every_call():
    clock = FixedClock(NOW)
    feed = SyntheticFeed(clock=clock)
    first = feed.get_latest_price("AAPL")
    clock.now = NOW + timedelta(hours=3)
    assert feed.get_latest_price("AAPL") != first
    assert clock.calls == 2


def test_synthetic_feed_naive_clock_is_treated_as_utc():
    naive = SyntheticFeed(clock=lambda: NOW.replace(tzinfo=None))
    aware = SyntheticFeed(clock=lambda: NOW)
    pd.testing.assert_frame_equal(naive.get_bars("X", "4h", 10), aware.get_bars("X", "4h", 10))


def test_synthetic_feed_symbols_and_seeds_differ():
    feed = SyntheticFeed(clock=lambda: NOW)
    assert feed.get_latest_price("AAPL") != feed.get_latest_price("MSFT")
    assert SyntheticFeed(seed=1, clock=lambda: NOW).get_latest_price("AAPL") != feed.get_latest_price("AAPL")


def test_synthetic_feed_start_price_scales_prices():
    base = SyntheticFeed(clock=lambda: NOW).get_latest_price("AAPL")
    scaled = SyntheticFeed(start_price=50_000.0, clock=lambda: NOW).get_latest_price("AAPL")
    assert scaled == pytest.approx(base * 500.0)


def test_synthetic_feed_prices_stay_in_a_sane_range_over_years():
    feed = SyntheticFeed(clock=lambda: NOW)
    for symbol in ("AAPL", "BTC/USDT", "KRW-BTC", "SPY"):
        close = feed.get_bars(symbol, "1d", 2000)["close"]
        assert close.min() > 20 and close.max() < 500
        daily = np.log(close).diff().dropna()
        assert 0.003 < daily.std() < 0.06  # moves like a real asset, not flat, not wild


@pytest.mark.parametrize("limit", [0, -1, 2.5, True])
def test_synthetic_feed_rejects_bad_limits(limit):
    with pytest.raises(ValueError):
        SyntheticFeed(clock=lambda: NOW).get_bars("AAPL", "1d", limit)


def test_synthetic_feed_rejects_bad_timeframe_and_start_price():
    with pytest.raises(ValueError):
        SyntheticFeed(clock=lambda: NOW).get_bars("AAPL", "3y", 5)
    with pytest.raises(ValueError):
        SyntheticFeed(start_price=0)


# =========================================================================== load_csv_bars

@pytest.fixture
def load_text(tmp_path):
    """Write CSV text to a temp file and load it."""
    def load(text: str) -> pd.DataFrame:
        return load_csv_bars(write_csv(tmp_path, text))
    return load


YAHOO = """Date,Open,High,Low,Close,Adj Close,Volume
2024-01-03,184.22,185.88,183.43,184.25,183.73,58414500
2024-01-02,187.15,188.44,183.89,185.64,185.12,82488700
2024-01-04,182.15,183.09,180.88,181.91,181.40,71983600
"""


def test_csv_yahoo_format_uses_close_not_adj_close_and_sorts(load_text):
    bars = load_text(YAHOO)
    assert_canonical(bars)
    assert list(bars.index) == [pd.Timestamp(d, tz="UTC") for d in ("2024-01-02", "2024-01-03", "2024-01-04")]
    assert bars["close"].tolist() == [185.64, 184.25, 181.91]
    assert bars["volume"].iloc[0] == 82488700.0
    assert bars.index.name is None


def test_csv_accepts_string_path(tmp_path):
    path = write_csv(tmp_path, YAHOO)
    pd.testing.assert_frame_equal(load_csv_bars(str(path)), load_csv_bars(path))


def test_csv_uses_adj_close_only_when_close_is_missing(load_text):
    bars = load_text("date,open,high,low,adj_close,volume\n2024-01-02,10,12,9,11.5,100\n")
    assert bars["close"].iloc[0] == 11.5


def test_csv_headers_are_case_space_bom_and_star_insensitive(load_text):
    text = "\ufeff DATE , Open ,HIGH,low,Close*,Adj Close**, VOLUME \n2024-01-02,10,12,9,11,10.5,100\n"
    bars = load_text(text)
    assert bars.iloc[0].tolist() == [10.0, 12.0, 9.0, 11.0, 100.0]


def test_csv_volume_is_optional_and_blank_volume_is_zero(load_text):
    bars = load_text("time,open,high,low,close\n2024-01-02T00:00:00Z,1,2,0.5,1.5\n")
    assert bars["volume"].tolist() == [0.0]
    bars = load_text("time,open,high,low,close,volume\n2024-01-02,1,2,0.5,1.5,\n")
    assert bars["volume"].tolist() == [0.0]


def test_csv_epoch_seconds_and_milliseconds_give_the_same_bars(load_text):
    rows = [(1704153600, 1, 2, 0.5, 1.5, 10), (1704240000, 1.5, 2.5, 1, 2, 20)]
    secs = "timestamp,open,high,low,close,volume\n" + "\n".join(",".join(map(str, r)) for r in rows)
    millis = "Timestamp,Open,High,Low,Close,Volume\n" + "\n".join(
        ",".join(map(str, (r[0] * 1000, *r[1:]))) for r in rows)
    a, b = load_text(secs), load_text(millis)
    pd.testing.assert_frame_equal(a, b)
    assert a.index[0] == pd.Timestamp("2024-01-02", tz="UTC")


def test_csv_fractional_epoch_seconds(load_text):
    bars = load_text("time,open,high,low,close\n1704153600.5,1,2,0.5,1.5\n")
    assert bars.index[0] == pd.Timestamp("2024-01-02 00:00:00.5", tz="UTC")


def test_csv_yyyymmdd_integers_are_dates_not_epoch_seconds(load_text):
    bars = load_text("date,open,high,low,close\n20240102,1,2,0.5,1.5\n20240103,1,2,0.5,1.5\n")
    assert bars.index[0] == pd.Timestamp("2024-01-02", tz="UTC")


def test_csv_timezone_offsets_are_converted_to_utc(load_text):
    text = ("datetime,open,high,low,close\n"
            "2024-03-08 00:00:00-05:00,1,2,0.5,1.5\n2024-03-11 00:00:00-04:00,1,2,0.5,1.5\n")
    bars = load_text(text)
    assert list(bars.index) == [pd.Timestamp("2024-03-08 05:00", tz="UTC"), pd.Timestamp("2024-03-11 04:00", tz="UTC")]


def test_csv_duplicate_timestamps_keep_the_last_row_with_a_warning(caplog, load_text):
    text = "date,open,high,low,close\n2024-01-02,1,2,0.5,1.5\n2024-01-02,1,3,0.5,2.5\n"
    with caplog.at_level(logging.WARNING, logger="bot.data"):
        bars = load_text(text)
    assert len(bars) == 1 and bars["close"].iloc[0] == 2.5
    assert "duplicate timestamp" in caplog.text


def test_csv_separate_date_and_time_columns_are_combined(load_text):
    text = "Date,Time,Open,High,Low,Close\n2024-01-02,09:30,1,2,0.5,1.5\n2024-01-02,09:35,1.5,2,1,1.8\n"
    bars = load_text(text)
    assert list(bars.index) == [pd.Timestamp("2024-01-02 09:30", tz="UTC"), pd.Timestamp("2024-01-02 09:35", tz="UTC")]


def test_csv_prefers_a_full_timestamp_column_over_a_date_column(load_text):
    text = "date,timestamp,open,high,low,close\n2024-01-02,1704186000000,1,2,0.5,1.5\n"
    assert load_text(text).index[0] == pd.Timestamp("2024-01-02 09:00", tz="UTC")


def test_csv_quoted_thousands_separators(load_text):
    bars = load_text('date,open,high,low,close,volume\n2024-01-02,"1,000.5","1,200",900,"1,100","2,000,000"\n')
    assert bars.iloc[0].tolist() == [1000.5, 1200.0, 900.0, 1100.0, 2_000_000.0]


def test_csv_null_price_rows_are_skipped_with_a_warning(caplog, load_text):
    text = YAHOO + "2024-01-05,null,null,null,null,null,null\n"
    with caplog.at_level(logging.WARNING, logger="bot.data"):
        bars = load_text(text)
    assert len(bars) == 3
    assert "without prices" in caplog.text


def test_csv_round_trip_of_a_pandas_written_frame(tmp_path):
    bars = generate_synthetic_bars(30, "1h")
    path = tmp_path / "saved.csv"
    bars.to_csv(path)  # unnamed index column
    pd.testing.assert_frame_equal(load_csv_bars(path), bars, check_freq=False)


@pytest.mark.parametrize(
    "text, message",
    [
        ("", "empty"),
        ("date,open,high,low,close\n", "no data rows"),
        ("open,high,low,close\n1,2,0.5,1.5\n", "no date/time column"),
        ("date,open,high,close\n2024-01-02,1,2,1.5\n", "low"),
        ("date,open,high,low\n2024-01-02,1,2,0.5\n", "close"),
        ("date,open,high,low,close\n2024-01-02,1,2,oops,1.5\n", "line(s) 2"),
        ("date,open,high,low,close\n2024-01-02,1,2,0.5,1.5\n2024-01-03,1,2,,1.5\n", "line(s) 3"),
        ("date,open,high,low,close\n2024-01-02,1,2,0,1.5\n", "price <= 0"),
        ("date,open,high,low,close\n2024-01-02,-1,2,0.5,1.5\n", "price <= 0"),
        ("date,open,high,low,close,volume\n2024-01-02,1,2,0.5,1.5,-3\n", "negative volume"),
        ("date,open,high,low,close\n,1,2,0.5,1.5\n", "missing date"),
        ("date,open,high,low,close\nnot-a-date,1,2,0.5,1.5\n", "cannot parse dates"),
        ("date,open,high,low,close\n2024-01-02,null,null,null,null\n", "no rows with prices"),
    ],
)
def test_csv_bad_files_raise_clear_value_errors(text, message, load_text):
    with pytest.raises(ValueError, match=re.escape(message)):
        load_text(text)


def _daily_csv_text(date_format: str, periods: int = 60) -> str:
    days = pd.bdate_range("2023-01-03", periods=periods)
    rows = [f"{day.strftime(date_format)},{100 + i},{101 + i},{99 + i},{100.5 + i},1000"
            for i, day in enumerate(days)]
    return "Date,Open,High,Low,Close,Volume\n" + "\n".join(rows) + "\n"


@pytest.mark.parametrize("date_format", ["%d/%m/%Y", "%d.%m.%Y", "%d-%m-%Y"])
def test_csv_day_first_dates_are_read_day_first_not_scrambled(tmp_path, date_format):
    # The first date (03/01/2023) is ambiguous; pandas guesses month-first from it,
    # fails on the 13th and used to fall back to per-row parsing that put days
    # 1-12 of every month into the wrong month.
    iso = load_csv_bars(write_csv(tmp_path, _daily_csv_text("%Y-%m-%d"), "iso.csv"))
    day_first = load_csv_bars(write_csv(tmp_path, _daily_csv_text(date_format), "eu.csv"))
    pd.testing.assert_frame_equal(day_first, iso)


def test_csv_us_month_first_dates_still_work(tmp_path):
    iso = load_csv_bars(write_csv(tmp_path, _daily_csv_text("%Y-%m-%d"), "iso.csv"))
    us = load_csv_bars(write_csv(tmp_path, _daily_csv_text("%m/%d/%Y"), "us.csv"))
    pd.testing.assert_frame_equal(us, iso)


def test_csv_dates_that_read_both_day_first_and_month_first_are_refused(load_text):
    # Every day and month is <= 12: 02/01 could be 2 Jan or 1 Feb.
    text = "date,open,high,low,close\n01/02/2024,1,2,0.5,1.5\n02/02/2024,1,2,0.5,1.5\n03/02/2024,1,2,0.5,1.5\n"
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        load_text(text)


def test_csv_mixed_formats_that_parse_out_of_order_are_refused(load_text):
    text = ("date,open,high,low,close\n2024-01-02,1,2,0.5,1.5\n03/01/2024 00:00,1,2,0.5,1.5\n"
            "2024-01-04,1,2,0.5,1.5\n")
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        load_text(text)


def test_csv_missing_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_csv_bars(tmp_path / "nope.csv")


def test_csv_inconsistent_high_low_is_loaded_with_a_warning(caplog, load_text):
    with caplog.at_level(logging.WARNING, logger="bot.data"):
        bars = load_text("date,open,high,low,close\n2024-01-02,10,9,8,9.5\n")
    assert len(bars) == 1
    assert "high/low" in caplog.text


# =========================================================================== CSVFeed


@pytest.fixture
def daily_csv(tmp_path) -> Path:
    path = tmp_path / "daily.csv"
    generate_synthetic_bars(40, "1d").to_csv(path, index_label="date")
    return path


def test_csv_feed_returns_the_last_bars_and_latest_close(daily_csv):
    feed = CSVFeed({"AAPL": daily_csv})
    expected = load_csv_bars(daily_csv)
    bars = feed.get_bars("AAPL", "1d", 10)
    pd.testing.assert_frame_equal(bars, expected.iloc[-10:])
    assert feed.get_latest_price("AAPL") == expected["close"].iloc[-1]
    assert feed.symbols == ["AAPL"]
    assert len(feed.get_bars("AAPL", "1d", 1000)) == 40


def test_csv_feed_accepts_dataframes_and_returns_copies():
    source = generate_synthetic_bars(20)
    feed = CSVFeed({"X": source})
    bars = feed.get_bars("X", "1d", 5)
    bars.loc[:, "close"] = -1.0
    assert (feed.get_bars("X", "1d", 5)["close"] > 0).all()
    source.loc[:, "close"] = -1.0
    assert feed.get_latest_price("X") > 0


def test_csv_feed_unknown_symbol_raises_value_error(daily_csv):
    feed = CSVFeed({"AAPL": daily_csv})
    with pytest.raises(ValueError, match="MSFT"):
        feed.get_bars("MSFT", "1d", 5)
    with pytest.raises(ValueError, match="MSFT"):
        feed.get_latest_price("MSFT")


def test_csv_feed_with_clock_only_shows_bars_opened_so_far():
    bars = generate_synthetic_bars(30, "1d")
    clock = FixedClock((bars.index[9] + pd.Timedelta(hours=5)).to_pydatetime())
    feed = CSVFeed({"X": bars}, clock=clock)
    visible = feed.get_bars("X", "1d", 100)
    assert visible.index[-1] == bars.index[9]  # the forming bar is the last one
    assert len(drop_incomplete_bars(visible, "1d", clock.now)) == 9
    assert feed.get_latest_price("X") == bars["close"].iloc[9]
    clock.now = bars.index[0].to_pydatetime() - timedelta(days=1)
    assert feed.get_bars("X", "1d", 5).empty
    with pytest.raises(ValueError, match="no X bars"):
        feed.get_latest_price("X")


def test_csv_feed_warns_once_on_timeframe_mismatch(caplog):
    feed = CSVFeed({"X": generate_synthetic_bars(30, "1h")})
    with caplog.at_level(logging.WARNING, logger="bot.data"):
        feed.get_bars("X", "1d", 5)
        feed.get_bars("X", "1d", 5)
        feed.get_bars("X", "1h", 5)
    assert caplog.text.count("resample") == 1


def test_csv_feed_needs_symbols_and_valid_limit():
    with pytest.raises(ValueError):
        CSVFeed({})
    with pytest.raises(ValueError):
        CSVFeed({"X": generate_synthetic_bars(5)}).get_bars("X", "1d", 0)
