"""Strategy behaviour: registry, parameter validation, warm-up, no look-ahead,
and the long-only state machine (never BUY when long, never SELL when flat)."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from bot.indicators import rsi, sma
from bot.models import Action, Position, Signal
from bot.strategies import (
    STRATEGIES,
    DonchianBreakout,
    RSIReversion,
    SMACrossover,
    Strategy,
    create_strategy,
)

LONG = Position(symbol="TEST", qty=10.0, avg_entry_price=100.0, market_price=100.0)


def bars_from(close, high=None, low=None) -> pd.DataFrame:
    """Canonical daily bars from closes; high/low default to the close."""
    close = np.asarray(close, dtype=float)
    idx = pd.date_range("2024-01-01", periods=len(close), freq="D", tz="UTC")
    return pd.DataFrame({
        "open": close,
        "high": close if high is None else np.asarray(high, dtype=float),
        "low": close if low is None else np.asarray(low, dtype=float),
        "close": close,
        "volume": 1000.0,
    }, index=idx)


def regime_bars(n: int = 500, seed: int = 11) -> pd.DataFrame:
    """Random walk with bull/bear/sideways regimes so every strategy trades."""
    rng = np.random.default_rng(seed)
    drift = np.repeat(rng.choice([-0.004, 0.0, 0.004], size=n // 50 + 1), 50)[:n]
    close = 100 * np.exp(np.cumsum(drift + rng.normal(0, 0.015, n)))
    open_ = np.concatenate([[100.0], close[:-1]])
    wick = np.abs(rng.normal(0, 0.005, n))
    idx = pd.date_range("2022-01-01", periods=n, freq="D", tz="UTC")
    return pd.DataFrame({
        "open": open_, "high": np.maximum(open_, close) * (1 + wick),
        "low": np.minimum(open_, close) * (1 - wick), "close": close, "volume": 1000.0,
    }, index=idx)


# Small periods keep the property tests fast; defaults are covered too.
CONFIGS = [
    ("sma_crossover", {"fast": 5, "slow": 20}),
    ("sma_crossover", {}),
    ("rsi_reversion", {"trend_sma": 50, "exit_sma": 5, "entry_rsi": 15, "exit_rsi": 65}),
    ("rsi_reversion", {}),
    ("rsi_reversion", {"trend_sma": 0, "exit_sma": 0}),
    ("donchian_breakout", {"entry_period": 10, "exit_period": 5}),
    ("donchian_breakout", {"trend_sma": 50}),
]
CONFIG_IDS = [f"{name}-{params or 'defaults'}" for name, params in CONFIGS]
BARS = regime_bars()


def _signals(strategy: Strategy, bars: pd.DataFrame, position: Position | None) -> list[Signal]:
    return [strategy.generate_signal(bars.iloc[:k], position) for k in range(1, len(bars) + 1)]


# ------------------------------------------------------------------ registry
def test_registry_lists_the_three_strategies_by_config_name():
    assert STRATEGIES == {
        "sma_crossover": SMACrossover,
        "rsi_reversion": RSIReversion,
        "donchian_breakout": DonchianBreakout,
    }
    for name, cls in STRATEGIES.items():
        assert issubclass(cls, Strategy) and cls.name == name
        assert cls.description and cls.__doc__


@pytest.mark.parametrize("name, defaults, min_bars", [
    ("sma_crossover", {"fast": 20, "slow": 50}, 51),
    ("rsi_reversion", {"rsi_period": 2, "entry_rsi": 10, "exit_rsi": 70,
                       "trend_sma": 200, "exit_sma": 5}, 201),
    ("donchian_breakout", {"entry_period": 20, "exit_period": 10, "trend_sma": 0}, 22),
])
def test_create_strategy_uses_spec_defaults(name, defaults, min_bars):
    for params in (None, {}):
        strategy = create_strategy(name, params)
        assert isinstance(strategy, STRATEGIES[name])
        assert strategy.params == defaults
        assert strategy.min_bars == min_bars


def test_create_strategy_merges_overrides_without_touching_class_defaults():
    strategy = create_strategy("sma_crossover", {"fast": 10})
    assert strategy.params == {"fast": 10, "slow": 50}
    assert SMACrossover.defaults == {"fast": 20, "slow": 50}
    assert create_strategy("sma_crossover").params["fast"] == 20


@pytest.mark.parametrize("name", ["nope", "SMA_CROSSOVER", "", None, 3])
def test_create_strategy_rejects_unknown_names_listing_valid_ones(name):
    with pytest.raises(ValueError) as err:
        create_strategy(name)
    for valid in STRATEGIES:
        assert valid in str(err.value)


@pytest.mark.parametrize("params", [[("fast", 5)], "fast=5", 5, {1: 5}])
def test_create_strategy_rejects_params_that_are_not_a_name_value_mapping(params):
    with pytest.raises(ValueError, match="params must be a mapping"):
        create_strategy("sma_crossover", params)


@pytest.mark.parametrize("name", sorted(STRATEGIES))
def test_unknown_param_names_are_rejected(name):
    with pytest.raises(ValueError, match="unknown parameter"):
        create_strategy(name, {"typo_period": 5})


INVALID_PARAMS = [
    ("sma_crossover", {"fast": 50, "slow": 50}),
    ("sma_crossover", {"fast": 60, "slow": 50}),
    ("sma_crossover", {"fast": 0}),
    ("sma_crossover", {"fast": -5}),
    ("sma_crossover", {"slow": 20.5}),
    ("sma_crossover", {"slow": 30.0}),
    ("sma_crossover", {"fast": True}),
    ("sma_crossover", {"fast": "10"}),
    ("sma_crossover", {"fast": None}),
    ("rsi_reversion", {"rsi_period": 1}),
    ("rsi_reversion", {"rsi_period": 0}),
    ("rsi_reversion", {"rsi_period": 2.0}),
    ("rsi_reversion", {"entry_rsi": 70, "exit_rsi": 70}),
    ("rsi_reversion", {"entry_rsi": 80}),
    ("rsi_reversion", {"entry_rsi": 0}),
    ("rsi_reversion", {"entry_rsi": -5}),
    ("rsi_reversion", {"exit_rsi": 100}),
    ("rsi_reversion", {"exit_rsi": 150}),
    ("rsi_reversion", {"entry_rsi": "10"}),
    ("rsi_reversion", {"entry_rsi": True}),
    ("rsi_reversion", {"entry_rsi": math.nan}),
    ("rsi_reversion", {"exit_rsi": math.inf}),
    ("rsi_reversion", {"exit_rsi": None}),
    ("rsi_reversion", {"trend_sma": -1}),
    ("rsi_reversion", {"exit_sma": -1}),
    ("rsi_reversion", {"trend_sma": 200.0}),
    ("rsi_reversion", {"exit_sma": None}),
    ("donchian_breakout", {"entry_period": 0}),
    ("donchian_breakout", {"exit_period": 0}),
    ("donchian_breakout", {"entry_period": -1}),
    ("donchian_breakout", {"trend_sma": -1}),
    ("donchian_breakout", {"entry_period": 20.5}),
    ("donchian_breakout", {"exit_period": "10"}),
    ("donchian_breakout", {"entry_period": False}),
]


@pytest.mark.parametrize("name, params", INVALID_PARAMS)
def test_invalid_param_values_are_rejected(name, params):
    with pytest.raises(ValueError):
        create_strategy(name, params)
    with pytest.raises(ValueError):
        STRATEGIES[name](**params)


@pytest.mark.parametrize("name, params, min_bars", [
    ("sma_crossover", {"fast": 1, "slow": 2}, 3),
    ("sma_crossover", {"fast": np.int64(3), "slow": np.int32(7)}, 8),
    ("rsi_reversion", {"trend_sma": 0, "exit_sma": 0}, 21),
    ("rsi_reversion", {"rsi_period": 14, "trend_sma": 50}, 141),
    ("rsi_reversion", {"trend_sma": 20, "exit_sma": 300}, 301),
    ("rsi_reversion", {"entry_rsi": 5.5, "exit_rsi": np.float64(95.5)}, 201),
    ("donchian_breakout", {"entry_period": 1, "exit_period": 1}, 3),
    ("donchian_breakout", {"entry_period": 55, "exit_period": 20, "trend_sma": 100}, 102),
])
def test_valid_edge_params_are_accepted_and_min_bars_follows_spec(name, params, min_bars):
    assert create_strategy(name, params).min_bars == min_bars


# ------------------------------------------------------------------- warm-up
@pytest.mark.parametrize("name, params", CONFIGS, ids=CONFIG_IDS)
@pytest.mark.parametrize("position", [None, LONG], ids=["flat", "long"])
def test_hold_during_warm_up(name, params, position):
    strategy = create_strategy(name, params)
    for n in (0, 1, 2, strategy.min_bars - 1):
        signal = strategy.generate_signal(BARS.iloc[:n], position)
        assert signal == Signal(Action.HOLD, signal.reason)
        assert "warming up" in signal.reason
    ready = strategy.generate_signal(BARS.iloc[:strategy.min_bars], position)
    assert "warming up" not in ready.reason


def test_warm_up_holds_even_when_the_setup_is_perfect():
    rising = bars_from(100 + np.arange(30.0))
    strategy = create_strategy("sma_crossover", {"fast": 2, "slow": 4})
    assert strategy.generate_signal(rising.iloc[:4], None).action is Action.HOLD
    assert strategy.generate_signal(rising.iloc[:5], None).action is Action.BUY


@pytest.mark.parametrize("name, params", CONFIGS, ids=CONFIG_IDS)
@pytest.mark.parametrize("position", [None, LONG], ids=["flat", "long"])
def test_nan_price_gives_hold_not_an_exception(name, params, position):
    strategy = create_strategy(name, params)
    bars = BARS.iloc[:strategy.min_bars + 5].copy()
    bars.iloc[-1, bars.columns.get_loc("close")] = math.nan
    bars.iloc[-3, bars.columns.get_loc("high")] = math.nan
    assert strategy.generate_signal(bars, position).action is Action.HOLD


# -------------------------------------------------------- long-only state machine
@pytest.mark.parametrize("name, params", CONFIGS, ids=CONFIG_IDS)
def test_never_buy_when_long_never_sell_when_flat(name, params):
    strategy = create_strategy(name, params)
    flat = _signals(strategy, BARS, None)
    long = _signals(strategy, BARS, LONG)
    assert all(s.action is not Action.SELL for s in flat)
    assert all(s.action is not Action.BUY for s in long)
    # The data really exercises both entries and exits.
    assert any(s.action is Action.BUY for s in flat)
    assert any(s.action is Action.SELL for s in long)
    assert all(s.reason for s in flat + long)


@pytest.mark.parametrize("name, params", CONFIGS, ids=CONFIG_IDS)
def test_zero_quantity_position_is_treated_as_flat(name, params):
    strategy = create_strategy(name, params)
    empty = Position("TEST", qty=0.0, avg_entry_price=100.0, market_price=100.0)
    for k in range(strategy.min_bars, len(BARS), 7):
        window = BARS.iloc[:k]
        assert strategy.generate_signal(window, empty) == strategy.generate_signal(window, None)


@pytest.mark.parametrize("name, params", CONFIGS, ids=CONFIG_IDS)
def test_walk_forward_alternates_entries_and_exits(name, params):
    """Feed bars one at a time like the live engine, acting on every signal."""
    strategy = create_strategy(name, params)
    position: Position | None = None
    actions = []
    for k in range(1, len(BARS) + 1):
        signal = strategy.generate_signal(BARS.iloc[:k], position)
        assert signal.action is not (Action.BUY if position else Action.SELL)
        if signal.action is Action.BUY:
            price = BARS["close"].iloc[k - 1]
            position = Position("TEST", qty=1.0, avg_entry_price=price, market_price=price)
        elif signal.action is Action.SELL:
            position = None
        if signal.action is not Action.HOLD:
            actions.append(signal.action)
    assert actions, "strategy never traded on regime data"
    assert actions[0] is Action.BUY
    assert all(a is not b for a, b in zip(actions, actions[1:]))


# ---------------------------------------------------------------- no look-ahead
@pytest.mark.parametrize("name, params", CONFIGS, ids=CONFIG_IDS)
@pytest.mark.parametrize("position", [None, LONG], ids=["flat", "long"])
def test_signal_ignores_future_rows(name, params, position):
    """The signal for a window is identical whether the window is a standalone
    frame or a slice of a longer frame whose future rows are garbage."""
    strategy = create_strategy(name, params)
    cuts = np.linspace(strategy.min_bars - 1, len(BARS) - 1, 12).astype(int)
    for k in cuts:
        window = BARS.iloc[:k].copy()
        expected = strategy.generate_signal(window, position)
        for garbage in (1000.0, 1e-6, math.nan):
            with_future = BARS.copy()
            with_future.iloc[k:] = with_future.iloc[k:] * garbage
            assert strategy.generate_signal(with_future.iloc[:k], position) == expected
        extended = pd.concat([window, regime_bars(50, seed=99).set_axis(
            BARS.index[-1] + pd.Timedelta(days=1) + pd.to_timedelta(np.arange(50), "D"))])
        assert strategy.generate_signal(extended.iloc[:k], position) == expected


@pytest.mark.parametrize("name, params", CONFIGS, ids=CONFIG_IDS)
def test_signals_do_not_depend_on_call_order_or_mutate_bars(name, params):
    strategy = create_strategy(name, params)
    before = BARS.copy()
    cuts = list(range(strategy.min_bars, len(BARS), 11))
    forward = {k: strategy.generate_signal(BARS.iloc[:k], None) for k in cuts}
    rng = np.random.default_rng(0)
    for k in rng.permutation(cuts):
        assert strategy.generate_signal(BARS.iloc[:k], None) == forward[k]
        assert create_strategy(name, params).generate_signal(BARS.iloc[:k], None) == forward[k]
    pd.testing.assert_frame_equal(BARS, before)


def test_sma_crossover_decision_at_each_bar_matches_that_bars_averages():
    strategy = create_strategy("sma_crossover", {"fast": 5, "slow": 20})
    fast, slow = sma(BARS["close"], 5), sma(BARS["close"], 20)
    for k in range(strategy.min_bars - 1, len(BARS)):
        window = BARS.iloc[:k + 1]
        flat, long = strategy.generate_signal(window, None), strategy.generate_signal(window, LONG)
        assert (flat.action is Action.BUY) == (fast.iloc[k] > slow.iloc[k])
        assert (long.action is Action.SELL) == (fast.iloc[k] < slow.iloc[k])


def test_rsi_reversion_decision_at_each_bar_matches_that_bars_indicators():
    params = {"trend_sma": 50, "exit_sma": 5, "entry_rsi": 15, "exit_rsi": 65}
    strategy = create_strategy("rsi_reversion", params)
    close = BARS["close"]
    r, trend, exit_ma = rsi(close, 2), sma(close, 50), sma(close, 5)
    for k in range(strategy.min_bars - 1, len(BARS)):
        window = BARS.iloc[:k + 1]
        buy = r.iloc[k] < 15 and close.iloc[k] > trend.iloc[k]
        sell = r.iloc[k] > 65 or close.iloc[k] > exit_ma.iloc[k]
        assert (strategy.generate_signal(window, None).action is Action.BUY) == buy
        assert (strategy.generate_signal(window, LONG).action is Action.SELL) == sell


def test_donchian_decision_at_each_bar_uses_only_previous_bars_channel():
    strategy = create_strategy("donchian_breakout", {"entry_period": 10, "exit_period": 5})
    upper = BARS["high"].rolling(10).max().shift(1)
    lower = BARS["low"].rolling(5).min().shift(1)
    close = BARS["close"]
    for k in range(strategy.min_bars - 1, len(BARS)):
        window = BARS.iloc[:k + 1]
        assert (strategy.generate_signal(window, None).action is Action.BUY) == (close.iloc[k] > upper.iloc[k])
        assert (strategy.generate_signal(window, LONG).action is Action.SELL) == (close.iloc[k] < lower.iloc[k])


# ---------------------------------------------------------------- SMA crossover
SMA_FAST = {"fast": 2, "slow": 4}   # min_bars = 5


def test_sma_crossover_buys_when_fast_above_slow_hand_computed():
    bars = bars_from([10, 10, 10, 10, 11, 12])   # SMA2 = 11.5, SMA4 = 10.75
    strategy = create_strategy("sma_crossover", SMA_FAST)
    assert strategy.generate_signal(bars, None) == Signal(Action.BUY, "SMA2=11.50 > SMA4=10.75")
    held = strategy.generate_signal(bars, LONG)
    assert held.action is Action.HOLD and ">" in held.reason


def test_sma_crossover_sells_when_fast_below_slow_hand_computed():
    bars = bars_from([12, 12, 12, 12, 11, 10])   # SMA2 = 10.5, SMA4 = 11.25
    strategy = create_strategy("sma_crossover", SMA_FAST)
    assert strategy.generate_signal(bars, LONG) == Signal(Action.SELL, "SMA2=10.50 < SMA4=11.25")
    assert strategy.generate_signal(bars, None).action is Action.HOLD


def test_sma_crossover_holds_when_averages_are_equal():
    bars = bars_from([10.0] * 8)
    strategy = create_strategy("sma_crossover", SMA_FAST)
    for position in (None, LONG):
        signal = strategy.generate_signal(bars, position)
        assert signal.action is Action.HOLD and "=" in signal.reason


def test_sma_crossover_is_state_based_not_only_on_the_cross_bar():
    bars = bars_from(100 + np.arange(40.0))       # crossed long ago, still trending up
    assert create_strategy("sma_crossover", SMA_FAST).generate_signal(bars, None).action is Action.BUY


@pytest.mark.parametrize("price, fragment", [(150_000_000.0, "172,500,000.00"), (0.00001234, "e-05")])
def test_reason_formats_large_and_tiny_prices(price, fragment):
    bars = bars_from(price * np.array([1, 1, 1, 1, 1.1, 1.2]))
    signal = create_strategy("sma_crossover", SMA_FAST).generate_signal(bars, None)
    assert signal.action is Action.BUY and fragment in signal.reason


# ---------------------------------------------------------------- RSI reversion
RSI_PARAMS = {"rsi_period": 2, "entry_rsi": 10, "exit_rsi": 70, "trend_sma": 30, "exit_sma": 3}


def dip_in_uptrend() -> pd.DataFrame:
    # 40 bars rising by 2 (avg gain 2, avg loss 0), then two drops of 8:
    # gain 1 / loss 4, then gain .5 / loss 6 -> RSI(2) = 100*.5/6.5 = 7.69
    # SMA30 = (sum(124..178 step 2) + 170 + 162) / 30 = 152 < close 162
    # SMA3 = (178 + 170 + 162) / 3 = 170 > close
    return bars_from(np.concatenate([100 + 2 * np.arange(40.0), [170.0, 162.0]]))


def test_rsi_reversion_buys_oversold_dip_above_trend():
    bars = dip_in_uptrend()
    assert rsi(bars["close"], 2).iloc[-1] == pytest.approx(100 * 0.5 / 6.5)
    signal = create_strategy("rsi_reversion", RSI_PARAMS).generate_signal(bars, None)
    assert signal == Signal(Action.BUY, "RSI(2)=7.7<10 & close>SMA30")


def test_rsi_reversion_holds_the_dip_while_long():
    signal = create_strategy("rsi_reversion", RSI_PARAMS).generate_signal(dip_in_uptrend(), LONG)
    assert signal.action is Action.HOLD


def test_rsi_reversion_warm_up_boundary_is_exact():
    strategy = create_strategy("rsi_reversion", RSI_PARAMS)   # min_bars = 31
    bars = dip_in_uptrend()
    assert strategy.generate_signal(bars.iloc[-31:], None).action is Action.BUY
    assert "warming up" in strategy.generate_signal(bars.iloc[-30:], None).reason


def test_rsi_reversion_trend_filter_blocks_dips_in_downtrend():
    falling = bars_from(200 - 2 * np.arange(40.0))   # RSI(2) = 0, close far below SMA30
    blocked = create_strategy("rsi_reversion", RSI_PARAMS).generate_signal(falling, None)
    assert blocked.action is Action.HOLD and "SMA30" in blocked.reason
    no_filter = create_strategy("rsi_reversion", {**RSI_PARAMS, "trend_sma": 0})
    assert no_filter.generate_signal(falling, None) == Signal(Action.BUY, "RSI(2)=0.0<10")


def test_rsi_reversion_sells_on_strong_rsi():
    rising = bars_from(100 + np.arange(40.0))       # RSI(2) = 100
    signal = create_strategy("rsi_reversion", RSI_PARAMS).generate_signal(rising, LONG)
    assert signal == Signal(Action.SELL, "RSI(2)=100.0>70")


def test_rsi_reversion_sells_on_close_above_exit_sma_even_with_modest_rsi():
    # after the dip, +6: gain .25+3 = 3.25, loss 3 -> RSI 52 <= 70
    # SMA3 = (170 + 162 + 168) / 3 = 166.67 < close 168
    bars = bars_from(np.concatenate([dip_in_uptrend()["close"].to_numpy(), [168.0]]))
    assert rsi(bars["close"], 2).iloc[-1] == pytest.approx(100 * 3.25 / 6.25)
    strategy = create_strategy("rsi_reversion", RSI_PARAMS)
    assert strategy.generate_signal(bars, LONG) == Signal(Action.SELL, "close=168.00>SMA3=166.67")
    no_sma_exit = create_strategy("rsi_reversion", {**RSI_PARAMS, "exit_sma": 0})
    assert no_sma_exit.generate_signal(bars, LONG).action is Action.HOLD


def test_rsi_reversion_thresholds_are_strict():
    flat = bars_from([50.0] * 30)                  # RSI = 50, close == SMA
    at_entry = create_strategy("rsi_reversion",
                               {"entry_rsi": 50, "exit_rsi": 60, "trend_sma": 0, "exit_sma": 3})
    assert at_entry.generate_signal(flat, None).action is Action.HOLD      # 50 is not < 50
    assert at_entry.generate_signal(flat, LONG).action is Action.HOLD      # close == SMA3
    at_exit = create_strategy("rsi_reversion",
                              {"entry_rsi": 40, "exit_rsi": 50, "trend_sma": 0, "exit_sma": 0})
    assert at_exit.generate_signal(flat, LONG).action is Action.HOLD       # 50 is not > 50


# ------------------------------------------------------------ Donchian breakout
DON_PARAMS = {"entry_period": 3, "exit_period": 2, "trend_sma": 0}   # min_bars = 5
DON_HIGH = [10.0, 10.5, 11.0, 10.8]
DON_LOW = [9.0, 9.2, 9.8, 10.0]
DON_CLOSE = [9.5, 10.0, 10.5, 10.2]


def donchian_bars(close: float, high: float, low: float) -> pd.DataFrame:
    """Four fixed bars plus a current bar: previous 3 highs max = 11.0,
    previous 2 lows min = 9.8."""
    return bars_from(DON_CLOSE + [close], DON_HIGH + [high], DON_LOW + [low])


def test_donchian_buys_close_above_previous_highs_excluding_current_bar():
    # Current high 12 is above the close: if the channel included the current
    # bar a breakout could never trigger.
    bars = donchian_bars(close=11.5, high=12.0, low=10.5)
    signal = create_strategy("donchian_breakout", DON_PARAMS).generate_signal(bars, None)
    assert signal == Signal(Action.BUY, "close=11.50>3-bar high=11.00")


@pytest.mark.parametrize("close", [11.0, 10.9])
def test_donchian_needs_a_strict_breakout(close):
    bars = donchian_bars(close=close, high=12.0, low=10.5)
    assert create_strategy("donchian_breakout", DON_PARAMS).generate_signal(bars, None).action is Action.HOLD


def test_donchian_breakout_while_long_is_hold():
    bars = donchian_bars(close=11.5, high=12.0, low=10.5)
    assert create_strategy("donchian_breakout", DON_PARAMS).generate_signal(bars, LONG).action is Action.HOLD


def test_donchian_sells_close_below_previous_lows():
    bars = donchian_bars(close=9.5, high=10.0, low=9.4)
    strategy = create_strategy("donchian_breakout", DON_PARAMS)
    assert strategy.generate_signal(bars, LONG) == Signal(Action.SELL, "close=9.50<2-bar low=9.80")
    assert strategy.generate_signal(bars, None).action is Action.HOLD


@pytest.mark.parametrize("close", [9.8, 9.9])
def test_donchian_exit_is_strict(close):
    bars = donchian_bars(close=close, high=10.0, low=9.0)
    assert create_strategy("donchian_breakout", DON_PARAMS).generate_signal(bars, LONG).action is Action.HOLD


def test_donchian_trend_filter_blocks_breakouts_below_the_sma():
    close = [20, 20, 20, 20, 10, 10.2, 10.1, 10.3, 11.5]
    high = [c + 0.2 for c in close[:-1]] + [12.0]
    low = [c - 0.2 for c in close]
    bars = bars_from(close, high, low)    # prev 3 highs = 10.5; SMA7 = 92.1 / 7 = 13.16
    params = {**DON_PARAMS, "trend_sma": 7}
    blocked = create_strategy("donchian_breakout", params).generate_signal(bars, None)
    assert blocked == Signal(Action.HOLD, "breakout but close=11.50<=SMA7=13.16")
    unfiltered = create_strategy("donchian_breakout", DON_PARAMS).generate_signal(bars, None)
    assert unfiltered.action is Action.BUY


def test_donchian_trend_filter_allows_breakouts_above_the_sma():
    close = [9.0, 9.5, 10.0, 10.5, 10.2, 10.4, 10.3, 11.5]
    bars = bars_from(close, [c + 0.2 for c in close], [c - 0.2 for c in close])
    signal = create_strategy("donchian_breakout", {**DON_PARAMS, "trend_sma": 5}).generate_signal(bars, None)
    assert signal.action is Action.BUY and signal.reason.endswith("& close>SMA5")
