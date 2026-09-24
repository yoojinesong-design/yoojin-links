"""Tests for bot.utils helpers shared by every broker and the backtester."""
from __future__ import annotations

import math
import random
from datetime import datetime, timezone

import pandas as pd
import pytest

from bot.utils import drop_incomplete_bars, floor_to_step


@pytest.mark.parametrize("value, step, expected", [
    (2.9999, 1.0, 2.0),
    (66.6667, 1.0, 66.0),
    (7.99, 0.25, 7.75),
    (0.0000019, 1e-6, 0.000001),
    (1.23456789e-7, 1e-6, 0.0),
    (1234.5678919, 1e-6, 1234.567891),
])
def test_floor_to_step_rounds_down(value, step, expected):
    assert floor_to_step(value, step) == expected


@pytest.mark.parametrize("value, step", [
    (1234.567891, 1e-6),     # 1234.567891 / 1e-6 == 1234567890.9999998 in floats
    (1.0, 1e-9),             # 1.0 / 1e-9 lands just below 1e9
    (0.1 + 0.2, 0.1),        # 0.30000000000000004
    (3e-6, 1e-6),
])
def test_floor_to_step_keeps_values_already_on_the_grid(value, step):
    result = floor_to_step(value, step)
    assert result == pytest.approx(value, rel=1e-12, abs=0)
    assert result == float(f"{value:.9f}".rstrip("0"))  # and without float noise


def test_floor_to_step_never_drops_a_step_from_exact_multiples():
    """The old ``floor(value / step + 1e-9)`` dropped a whole step for ~0.25% of
    6-decimal quantities, e.g. leaving 0.000001 of a share after "sell all"."""
    rng = random.Random(7)
    for _ in range(20_000):
        units = rng.randint(1, 10**11)
        value = float(f"{units / 1e6:.6f}")
        assert floor_to_step(value, 1e-6) == value


def test_floor_to_step_never_rounds_up_between_grid_points():
    rng = random.Random(11)
    for _ in range(20_000):
        value = rng.uniform(0, 1e5)
        result = floor_to_step(value, 1e-6)
        assert result <= value * (1 + 1e-15)
        assert value - result < 1e-6 + 1e-9


@pytest.mark.parametrize("step", [0, -1.0])
def test_floor_to_step_with_no_step_returns_the_value(step):
    assert floor_to_step(3.14159, step) == 3.14159


def test_floor_to_step_passes_nan_through_and_returns_floats():
    assert math.isnan(floor_to_step(math.nan, 1e-6))
    assert isinstance(floor_to_step(10, 1), float)


def test_drop_incomplete_bars_keeps_bars_closed_by_now():
    index = pd.date_range("2026-01-01", periods=3, freq="1h", tz="UTC")
    bars = pd.DataFrame({c: [1.0, 2.0, 3.0] for c in ("open", "high", "low", "close", "volume")}, index=index)
    now = datetime(2026, 1, 1, 2, 0, tzinfo=timezone.utc)  # the 01:00 bar closes exactly now
    assert list(drop_incomplete_bars(bars, "1h", now).index) == list(index[:2])
    assert list(drop_incomplete_bars(bars, "1h", now.replace(tzinfo=None)).index) == list(index[:2])
