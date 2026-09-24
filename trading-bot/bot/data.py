"""Market data: synthetic price history, CSV loading and simple data feeds.

A *data feed* is anything with ``get_bars`` and ``get_latest_price`` (see
:class:`DataFeed`). Every broker is one, and the paper broker sits on top of
one to simulate fills. All bars returned here are canonical (see
``utils.validate_bars``): UTC bar-open-time index, float OHLCV columns.
"""
from __future__ import annotations

import logging
import math
import numbers
import re
import warnings
import zlib
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol, runtime_checkable

import numpy as np
import pandas as pd

from .utils import timeframe_to_timedelta, utcnow, validate_bars

logger = logging.getLogger(__name__)

# Fixed default end for synthetic history so backtests and tests are reproducible.
DEFAULT_SYNTHETIC_END = datetime(2026, 1, 1, tzinfo=timezone.utc)

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_DAY_S = 86_400.0
# Resolution pandas gives new datetime indexes by default ("us" on pandas 3,
# "ns" before). Every index built here uses it so frames compare cleanly.
_TIME_UNIT = pd.date_range("2000-01-01", periods=1, tz="UTC").unit


@runtime_checkable
class DataFeed(Protocol):
    """Source of bars and prices. Brokers satisfy it, as do the feeds below."""

    def get_bars(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        """Most recent ``limit`` canonical bars; the last one may still be forming."""
        ...

    def get_latest_price(self, symbol: str) -> float:
        """Last traded price."""
        ...


# --------------------------------------------------------------------------- helpers


def _as_utc(dt: datetime) -> datetime:
    """Naive datetimes are taken to be UTC."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _bar_length(timeframe: str) -> timedelta:
    td = timeframe_to_timedelta(timeframe)
    if td <= timedelta(0):
        raise ValueError(f"timeframe must be longer than zero, got {timeframe!r}")
    return td


def _bar_index(first_open: datetime, periods: int, td: timedelta) -> pd.DatetimeIndex:
    return pd.date_range(start=first_open, periods=periods, freq=td).as_unit(_TIME_UNIT)


def _is_finite_number(value: object) -> bool:
    return isinstance(value, numbers.Real) and not isinstance(value, bool) and math.isfinite(value)


def _check_limit(limit: int) -> None:
    if isinstance(limit, bool) or not isinstance(limit, numbers.Integral) or limit < 1:
        raise ValueError(f"limit must be a whole number >= 1, got {limit!r}")


# --------------------------------------------------------------------------- synthetic history

# regime: (annual drift added to ``annual_drift``, volatility multiplier, probability).
# Offsets balance out (0.40 * 0.30 == 0.25 * 0.48), so the long-run drift is ~annual_drift.
_REGIMES = (
    ("bull", 0.30, 0.85, 0.40),
    ("bear", -0.48, 1.35, 0.25),
    ("sideways", 0.0, 0.65, 0.35),
)
_REGIME_DAYS = (21.0, 150.0)  # each regime lasts 3 weeks to 5 months


def generate_synthetic_bars(
    n_bars: int,
    timeframe: str = "1d",
    seed: int = 42,
    start_price: float = 100.0,
    end: datetime | None = None,
    annual_drift: float = 0.08,
    annual_vol: float = 0.25,
) -> pd.DataFrame:
    """Deterministic regime-switching geometric Brownian motion bars.

    Bull, bear and sideways regimes lasting weeks to months alternate at
    random, so trend-following and mean-reversion strategies both find
    something to trade. The same arguments always return the same frame.

    Bars are aligned to the timeframe (on a 24/7 calendar) and have all closed
    by ``end`` (default 2026-01-01 UTC): the last bar opens at
    ``floor(end, timeframe) - timeframe``. The first bar opens at ``start_price``.
    """
    if isinstance(n_bars, bool) or not isinstance(n_bars, numbers.Integral) or n_bars < 1:
        raise ValueError(f"n_bars must be a whole number >= 1, got {n_bars!r}")
    if not _is_finite_number(start_price) or start_price <= 0:
        raise ValueError(f"start_price must be > 0, got {start_price!r}")
    if not _is_finite_number(annual_vol) or annual_vol < 0:
        raise ValueError(f"annual_vol must be >= 0, got {annual_vol!r}")
    if not _is_finite_number(annual_drift):
        raise ValueError(f"annual_drift must be a finite number, got {annual_drift!r}")
    td = _bar_length(timeframe)
    n = int(n_bars)
    end_utc = _as_utc(end if end is not None else DEFAULT_SYNTHETIC_END)
    first_open = _EPOCH + ((end_utc - _EPOCH) // td - n) * td

    rng = np.random.default_rng(seed)
    bar_days = td / timedelta(days=1)
    drift, vol = np.empty(n), np.empty(n)
    probs = [p for *_, p in _REGIMES]
    i = 0
    while i < n:
        _, offset, vol_mult, _ = _REGIMES[rng.choice(len(_REGIMES), p=probs)]
        length = max(1, round(rng.uniform(*_REGIME_DAYS) / bar_days))
        drift[i:i + length] = annual_drift + offset
        vol[i:i + length] = annual_vol * vol_mult
        i += length

    dt = bar_days / 365.0
    sd = vol * math.sqrt(dt)
    z = rng.standard_normal((5, n))
    ret = (drift - 0.5 * vol**2) * dt + sd * z[0]  # open -> close
    gap = 0.1 * sd * z[1]                           # previous close -> open
    gap[0] = 0.0
    log_close = math.log(start_price) + np.cumsum(gap + ret)
    close = np.exp(log_close)
    open_ = np.exp(log_close - ret)
    # Multiplying by exp(>=0) / exp(<=0) keeps low <= open, close <= high exactly.
    high = np.maximum(open_, close) * np.exp(0.5 * sd * np.abs(z[2]))
    low = np.minimum(open_, close) * np.exp(-0.5 * sd * np.abs(z[3]))
    volume = 1e6 * bar_days * np.exp(0.3 * z[4]) * (1.0 + 20.0 * np.abs(ret))

    frame = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=_bar_index(first_open, n, td),
    )
    return validate_bars(frame)


# --------------------------------------------------------------------------- CSV

_DATETIME_HEADERS = ("datetime", "timestamp", "date time", "open time")
# Last resort: the unnamed first column pandas writes for a DataFrame index.
_INDEX_HEADERS = ("unnamed: 0", "index")
_CLOSE_HEADERS = ("close", "adj close", "adjclose", "adjusted close")
_PRICES = ("open", "high", "low", "close")


def _norm_header(name: object) -> str:
    """'  Adj_Close* ' -> 'adj close' (case, spacing, underscores, BOM, Yahoo '*')."""
    text = str(name).replace("\ufeff", "").strip().lower().rstrip("*").strip()
    return re.sub(r"[\s_]+", " ", text)


def _lines(mask: pd.Series) -> str:
    """CSV line numbers (header is line 1) of the True rows, abbreviated."""
    rows = [int(i) + 2 for i in np.flatnonzero(mask.to_numpy())]
    return ", ".join(map(str, rows[:5])) + (f" (+{len(rows) - 5} more)" if len(rows) > 5 else "")


def _to_number(column: pd.Series) -> pd.Series:
    """Parse numbers, tolerating thousands separators; unparseable -> NaN."""
    return pd.to_numeric(column.str.strip().str.replace(",", "", regex=False), errors="coerce")


def _parse_times(column: pd.Series, where: str) -> pd.DatetimeIndex:
    """Dates/datetimes (naive = UTC, offsets honoured), epoch s/ms/us/ns or YYYYMMDD."""
    text = column.str.strip()
    missing = text.isna() | (text == "")
    if missing.any():
        raise ValueError(f"{where}: missing date/time on line(s) {_lines(missing)}")
    numeric = pd.to_numeric(text, errors="coerce")
    try:
        if numeric.notna().all():
            integral = bool((numeric == np.floor(numeric)).all())
            if integral and numeric.min() >= 19000101 and numeric.max() <= 21001231:
                times = pd.to_datetime(text, format="%Y%m%d", utc=True)
            else:
                magnitude = float(numeric.abs().max())
                unit = "s" if magnitude < 1e11 else "ms" if magnitude < 1e14 else "us" if magnitude < 1e17 else "ns"
                times = pd.to_datetime(numeric.astype("int64") if integral else numeric, unit=unit, utc=True)
        else:
            times = _parse_date_strings(text, where)
    except (ValueError, TypeError, OverflowError) as exc:
        if str(exc).startswith(where):
            raise
        raise ValueError(f"{where}: cannot parse dates ({exc})") from exc
    return pd.DatetimeIndex(times).as_unit(_TIME_UNIT).rename(None)


_ISO_HINT = "write the dates as YYYY-MM-DD (ISO), e.g. 2024-01-31"
_YEAR_FIRST = re.compile(r"\s*\d{4}\D")


def _parse_date_strings(text: pd.Series, where: str) -> pd.Series:
    """Date strings in ONE consistent format: month-first or day-first (e.g.
    31/01/2024), never a per-row mix of both. pandas infers the format from
    the first row and guesses month-first when that row is ambiguous (02/01),
    so the day-first reading is tried too and a file that reads both ways
    differently is refused rather than guessed."""
    def strict(dayfirst: bool) -> pd.Series | None:
        try:
            with warnings.catch_warnings():  # "Parsing dates in %d/%m/%Y format when dayfirst=False"
                warnings.simplefilter("ignore", UserWarning)
                return pd.to_datetime(text, utc=True, dayfirst=dayfirst)
        except (ValueError, TypeError, OverflowError):
            return None

    month_first = strict(dayfirst=False)
    # Year-first dates (2024-01-02) are never day-first; pandas would read them as YYYY-DD-MM.
    day_first = None if _YEAR_FIRST.match(str(text.iloc[0])) else strict(dayfirst=True)
    if month_first is not None and day_first is not None and not month_first.equals(day_first):
        raise ValueError(f"{where}: the dates can be read day-first or month-first (e.g. "
                         f"{text.iloc[0]!r}), so which one is meant is unclear; {_ISO_HINT}")
    if month_first is not None or day_first is not None:
        return month_first if month_first is not None else day_first
    # Mixed formats: each row parsed on its own. Only trusted when that keeps
    # the file's order (a day-first/month-first mix scrambles the rows).
    times = pd.to_datetime(text, utc=True, format="mixed")
    index = pd.DatetimeIndex(times)
    if not (index.is_monotonic_increasing or index.is_monotonic_decreasing):
        raise ValueError(f"{where}: the dates are in mixed formats and do not come out in file order, "
                         f"so some were probably misread; {_ISO_HINT}")
    return times


def load_csv_bars(path: str | Path) -> pd.DataFrame:
    """Load OHLCV bars from a CSV file into canonical form.

    Headers are matched case-insensitively: a time column named datetime,
    timestamp, date or time, or separate date and time columns (ISO strings,
    naive = UTC, or epoch seconds / milliseconds); open, high, low, close
    (``adj close`` only when there is no ``close``); optional volume
    (missing -> 0). Duplicate timestamps keep the last row (with a warning).
    Rows whose four prices are all empty (e.g. Yahoo "null" holiday rows) are
    dropped with a warning; any other missing, non-numeric or non-positive
    price raises ValueError.
    """
    path = Path(path)
    where = str(path)
    try:
        raw = pd.read_csv(path, dtype=str, skipinitialspace=True)
    except pd.errors.EmptyDataError as exc:
        raise ValueError(f"{where}: CSV file is empty") from exc

    columns: dict[str, str] = {}
    for col in raw.columns:
        columns.setdefault(_norm_header(col), col)

    def pick(names: Iterable[str]) -> str | None:
        return next((columns[n] for n in names if n in columns), None)

    date_col, clock_col = pick(["date"]), pick(["time"])
    if (time_col := pick(_DATETIME_HEADERS)) is not None:
        times = raw[time_col]
    elif date_col is not None and clock_col is not None:  # separate "Date" and "Time" columns
        times = raw[date_col].str.strip() + " " + raw[clock_col].str.strip()
    elif (time_col := date_col or clock_col or pick(_INDEX_HEADERS)) is not None:
        times = raw[time_col]
    else:
        raise ValueError(f"{where}: no date/time column (expected one of date, datetime, timestamp, time); "
                         f"found {list(raw.columns)}")
    sources = {"open": pick(["open"]), "high": pick(["high"]), "low": pick(["low"]), "close": pick(_CLOSE_HEADERS)}
    missing = [name for name, col in sources.items() if col is None]
    if missing:
        raise ValueError(f"{where}: missing column(s) {missing}; found {list(raw.columns)}")
    if raw.empty:
        raise ValueError(f"{where}: no data rows")

    frame = pd.DataFrame({name: _to_number(raw[col]) for name, col in sources.items()})
    volume_col = pick(["volume", "vol"])
    frame["volume"] = _to_number(raw[volume_col]).fillna(0.0) if volume_col else 0.0

    blank = frame[list(_PRICES)].isna().all(axis=1)
    if blank.all():
        raise ValueError(f"{where}: no rows with prices")
    if blank.any():
        logger.warning("%s: skipping %d row(s) without prices (line(s) %s)", where, int(blank.sum()), _lines(blank))
    bad = frame[list(_PRICES)].isna().any(axis=1) & ~blank
    if bad.any():
        raise ValueError(f"{where}: missing or non-numeric price on line(s) {_lines(bad)}")
    non_positive = (frame[list(_PRICES)] <= 0).any(axis=1)
    if non_positive.any():
        raise ValueError(f"{where}: price <= 0 on line(s) {_lines(non_positive)}")
    if (frame["volume"] < 0).any():
        raise ValueError(f"{where}: negative volume on line(s) {_lines(frame['volume'] < 0)}")

    frame.index = _parse_times(times, where)
    frame = frame[~blank.to_numpy()]
    duplicated = frame.index.duplicated(keep="last")
    if duplicated.any():
        logger.warning("%s: %d duplicate timestamp(s); keeping the last row of each", where, int(duplicated.sum()))
    inconsistent = (frame["high"] < frame[["open", "close", "low"]].max(axis=1)) | (
        frame["low"] > frame[["open", "close", "high"]].min(axis=1))
    if inconsistent.any():
        logger.warning("%s: %d bar(s) have high/low outside open/close", where, int(inconsistent.sum()))
    return validate_bars(frame)


# --------------------------------------------------------------------------- synthetic live feed

# Deterministic noise layers (knot spacing in seconds, log-price amplitude):
# coarse layers give multi-week swings, fine layers intraday wiggles. Knot
# values are hashed from (seed, symbol, layer, knot index), so the price at
# any instant is a pure function of time; no state, no history to replay.
_NOISE_LAYERS = (
    (30 * 86_400, 0.08), (7 * 86_400, 0.04), (86_400, 0.015), (4 * 3_600, 0.006),
    (3_600, 0.004), (900, 0.002), (300, 0.0012), (60, 0.0006),
)
_SAMPLES_PER_BAR = 16  # price samples per bar used for high/low
_REF_S = datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp()  # prices ~start_price around here
_U64 = np.uint64


def _mix(x: np.ndarray) -> np.ndarray:
    """SplitMix64 finaliser: a fast, well-distributed 64-bit hash (wraps on overflow)."""
    x = x + _U64(0x9E3779B97F4A7C15)
    x = (x ^ (x >> _U64(30))) * _U64(0xBF58476D1CE4E5B9)
    x = (x ^ (x >> _U64(27))) * _U64(0x94D049BB133111EB)
    return x ^ (x >> _U64(31))


def _key(*parts: int) -> np.ndarray:
    h = np.zeros(1, dtype=np.uint64)
    for part in parts:
        h = _mix(h ^ _U64(part & 0xFFFFFFFFFFFFFFFF))
    return h


def _uniform(key: np.ndarray, idx: np.ndarray) -> np.ndarray:
    """Deterministic uniforms in (0, 1), one per integer index."""
    h = _mix(key ^ np.asarray(idx, dtype=np.int64).view(np.uint64))
    return ((h >> _U64(11)).astype(np.float64) + 0.5) / 2.0**53


def _gauss(key: np.ndarray, idx: np.ndarray) -> np.ndarray:
    """Deterministic standard normals, one per integer index (Box-Muller)."""
    idx = np.asarray(idx, dtype=np.int64)
    u1 = _uniform(key, idx)
    u2 = _uniform(_mix(key), idx)
    return np.sqrt(-2.0 * np.log(u1)) * np.cos(2.0 * np.pi * u2)


@dataclass(frozen=True)
class _PathParams:
    trend: float    # log-price drift per day
    a1: float
    p1: float       # days
    phi1: float
    a2: float
    p2: float
    phi2: float


class SyntheticFeed:
    """Stateless, deterministic synthetic prices for demos and the ``sim`` broker.

    The log price at time t (days since 2024-01-01) is::

        log(start_price) + trend*t + A1*sin(2πt/P1 + φ1) + A2*sin(2πt/P2 + φ2) + noise(t)

    with trend/A/P/φ derived from ``crc32(symbol)`` and ``seed``, and noise a
    sum of piecewise-linear layers (month down to minute scale) whose knots are
    hashed from (seed, symbol, layer, knot index). The price is therefore a pure
    function of time: a bar for a given (seed, symbol, timeframe, open time) is
    identical whenever it is requested, all timeframes share one price path, and
    the forming bar's close-so-far equals ``get_latest_price()`` at that instant.
    """

    def __init__(self, seed: int = 42, start_price: float = 100.0, clock: Callable[[], datetime] = utcnow) -> None:
        if not _is_finite_number(start_price) or start_price <= 0:
            raise ValueError(f"start_price must be > 0, got {start_price!r}")
        self.seed = int(seed)
        self.start_price = float(start_price)
        self.clock = clock

    def get_bars(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        """The last ``limit`` bars, ending with the bar forming at ``clock()``
        (callers drop it with ``utils.drop_incomplete_bars``)."""
        _check_limit(limit)
        td = _bar_length(timeframe)
        now = self._now()
        forming_open = _EPOCH + ((now - _EPOCH) // td) * td
        first_open = forming_open - (int(limit) - 1) * td
        step = td.total_seconds()
        opens = first_open.timestamp() + step * np.arange(int(limit))
        # Sample each bar at fixed points; clipping to `now` means the forming bar
        # only sees prices so far and ends exactly on the latest price.
        grid = opens[:, None] + step * (np.arange(_SAMPLES_PER_BAR + 1) / _SAMPLES_PER_BAR)
        now_s = now.timestamp()
        prices = np.exp(self._log_price(symbol, np.minimum(grid, now_s)))
        open_, close = prices[:, 0], prices[:, -1]

        bar_ids = np.round(opens / step).astype(np.int64)
        noise = _gauss(_key(self.seed, zlib.crc32(symbol.encode()), 1_000, int(step)), bar_ids)
        elapsed = np.clip((now_s - opens) / step, 0.0, 1.0)
        volume = 1e6 * (step / _DAY_S) * np.exp(0.3 * noise) * (1.0 + 20.0 * np.abs(np.log(close / open_))) * elapsed

        frame = pd.DataFrame(
            {"open": open_, "high": prices.max(axis=1), "low": prices.min(axis=1), "close": close, "volume": volume},
            index=_bar_index(first_open, int(limit), td),
        )
        return validate_bars(frame)

    def get_latest_price(self, symbol: str) -> float:
        """Price at ``clock()``: the close-so-far of every timeframe's forming bar."""
        return float(np.exp(self._log_price(symbol, np.array([self._now().timestamp()]))[0]))

    def _now(self) -> datetime:
        return _as_utc(self.clock())

    def _params(self, crc: int) -> _PathParams:
        u = _uniform(_key(self.seed, crc, 0), np.arange(7))
        return _PathParams(
            trend=(-0.05 + 0.20 * u[0]) / 365.0,  # -5% .. +15% a year
            a1=0.08 + 0.17 * u[1], p1=90.0 + 150.0 * u[2], phi1=2 * math.pi * u[3],
            a2=0.02 + 0.04 * u[4], p2=12.0 + 30.0 * u[5], phi2=2 * math.pi * u[6],
        )

    def _log_price(self, symbol: str, t: np.ndarray) -> np.ndarray:
        """Log price at Unix times ``t`` (seconds, any shape)."""
        crc = zlib.crc32(symbol.encode())
        p = self._params(crc)
        days = (t - _REF_S) / _DAY_S
        out = (math.log(self.start_price) + p.trend * days
               + p.a1 * np.sin(2 * math.pi * days / p.p1 + p.phi1)
               + p.a2 * np.sin(2 * math.pi * days / p.p2 + p.phi2))
        for layer, (spacing, amplitude) in enumerate(_NOISE_LAYERS, start=1):
            x = t / spacing
            knot = np.floor(x)
            w = x - knot
            knot = knot.astype(np.int64)
            key = _key(self.seed, crc, layer)
            out = out + amplitude * ((1.0 - w) * _gauss(key, knot) + w * _gauss(key, knot + 1))
        return out


# --------------------------------------------------------------------------- CSV feed


class CSVFeed:
    """DataFeed over preloaded CSV files, for replay and tests.

    ``paths`` maps symbol -> CSV path (a canonical bars DataFrame is accepted
    too). The files must already be in the timeframe you request; a mismatch
    is logged once. With a ``clock``, only bars that have opened by ``clock()``
    are visible (the last may be the forming one), so a replay can step through
    history. ``get_latest_price`` is the close of the last visible bar.
    """

    def __init__(self, paths: Mapping[str, str | Path | pd.DataFrame],
                 clock: Callable[[], datetime] | None = None) -> None:
        if not paths:
            raise ValueError("CSVFeed needs at least one symbol")
        self._bars = {
            symbol: validate_bars(src) if isinstance(src, pd.DataFrame) else load_csv_bars(src)
            for symbol, src in paths.items()
        }
        self.clock = clock
        self._checked: set[tuple[str, str]] = set()

    @property
    def symbols(self) -> list[str]:
        return list(self._bars)

    def get_bars(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        _check_limit(limit)
        self._check_timeframe(symbol, timeframe)
        return self._visible(symbol).tail(int(limit)).copy()

    def get_latest_price(self, symbol: str) -> float:
        bars = self._visible(symbol)
        if bars.empty:
            raise ValueError(f"CSVFeed: no {symbol} bars at or before {self._now()}")
        return float(bars["close"].iloc[-1])

    def _now(self) -> datetime | None:
        return _as_utc(self.clock()) if self.clock is not None else None

    def _all(self, symbol: str) -> pd.DataFrame:
        try:
            return self._bars[symbol]
        except KeyError:
            raise ValueError(f"CSVFeed has no data for {symbol!r}; loaded: {sorted(self._bars)}") from None

    def _visible(self, symbol: str) -> pd.DataFrame:
        bars = self._all(symbol)
        now = self._now()
        return bars if now is None else bars[bars.index <= pd.Timestamp(now)]

    def _check_timeframe(self, symbol: str, timeframe: str) -> None:
        td = _bar_length(timeframe)
        index = self._all(symbol).index
        if (symbol, timeframe) in self._checked:
            return
        self._checked.add((symbol, timeframe))
        if len(index) >= 3:
            spacing = pd.Series(index).diff().median()
            if spacing != pd.Timedelta(td):
                logger.warning("CSVFeed: %s bars are %s apart but timeframe %s was requested; "
                               "resample the file to %s bars", symbol, spacing, timeframe, timeframe)


__all__ = [
    "DEFAULT_SYNTHETIC_END",
    "CSVFeed",
    "DataFeed",
    "SyntheticFeed",
    "generate_synthetic_bars",
    "load_csv_bars",
]
