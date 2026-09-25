"""Tests for bot.backtest: execution timing, protective exits, risk gates,
accounting invariants, metrics and output files. All offline, tiny datasets."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from bot.backtest import BacktestConfig, BacktestResult, Trade, max_drawdown_pct, run_backtest
from bot.data import generate_synthetic_bars
from bot.models import Action, Position, Signal
from bot.risk import RiskConfig
from bot.strategies.base import Strategy
from bot.strategies.sma_crossover import SMACrossover
from bot.utils import bars_per_year, floor_to_step

T0 = pd.Timestamp("2024-01-01", tz="UTC")  # a Monday
BUY, SELL = Action.BUY, Action.SELL

# Risk settings where no cap binds unless a test lowers it on purpose.
LOOSE = RiskConfig(
    risk_per_trade_pct=100.0,
    max_position_pct=100.0,
    max_total_exposure_pct=100.0,
    max_open_positions=10,
    max_daily_loss_pct=None,
    flatten_on_daily_loss=False,
    stop_loss_pct=None,
    take_profit_pct=None,
    max_trades_per_day=100,
    min_order_notional=0.0,
    cash_buffer_pct=0.0,
)


def day(n: int) -> pd.Timestamp:
    return T0 + pd.Timedelta(days=n)


def hour(n: int) -> pd.Timestamp:
    return T0 + pd.Timedelta(hours=n)


def config(risk: dict | None = None, **kw) -> BacktestConfig:
    """Frictionless by default; tests opt in to fees/slippage/limits."""
    base = dict(starting_cash=10_000.0, fee_pct=0.0, slippage_pct=0.0, lookback=300,
                timeframe="1d", trading_days_per_year=365, timezone="UTC",
                risk=replace(LOOSE, **(risk or {})))
    return BacktestConfig(**{**base, **kw})


def bars(rows: list, start: pd.Timestamp = T0, freq: str = "1D", tag: float = 1.0,
         index: pd.DatetimeIndex | None = None) -> pd.DataFrame:
    """Rows are (open, high, low, close) tuples or a single price for a flat bar.
    ``tag`` goes in the volume column so a strategy can tell symbols apart."""
    ohlc = [(r, r, r, r) if isinstance(r, (int, float)) else r for r in rows]
    if index is None:
        index = pd.date_range(start, periods=len(ohlc), freq=freq)
    frame = pd.DataFrame(ohlc, columns=["open", "high", "low", "close"], index=index, dtype=float)
    frame["volume"] = float(tag)
    return frame


@dataclass
class Call:
    tag: float
    time: pd.Timestamp
    n_bars: int
    position: Position | None
    window: pd.DataFrame


class Scripted(Strategy):
    """Returns scripted actions keyed by bar time, or by (tag, bar time) for
    multi-symbol tests (tag = the volume value). Records every call."""

    name = "scripted"
    defaults: dict = {}

    def __init__(self, script: dict | None = None, min_bars: int = 1) -> None:
        super().__init__()
        self.script = script or {}
        self._min_bars = min_bars
        self.calls: list[Call] = []

    @property
    def min_bars(self) -> int:
        return self._min_bars

    def generate_signal(self, bars: pd.DataFrame, position: Position | None) -> Signal:
        t, tag = bars.index[-1], float(bars["volume"].iloc[-1])
        self.calls.append(Call(tag, t, len(bars), position, bars))
        action = self.script.get((tag, t), self.script.get(t, Action.HOLD))
        return Signal(action, f"scripted {action.value}")


class LookAheadSpy(Scripted):
    """Asserts, on every call, that it only sees the past: the window is exactly
    the true history up to its last bar, and time never runs backwards across
    calls (so no call ever saw a bar later than the simulation's current time)."""

    def __init__(self, truth: dict[float, pd.DataFrame], lookback: int, **kw) -> None:
        super().__init__(**kw)
        self.truth = truth
        self.lookback = lookback
        self.now: pd.Timestamp | None = None

    def generate_signal(self, bars: pd.DataFrame, position: Position | None) -> Signal:
        t, tag = bars.index[-1], float(bars["volume"].iloc[-1])
        assert self.now is None or t >= self.now, f"time went backwards: {t} after {self.now}"
        self.now = t
        assert bars.index.max() == t and bars.index.is_monotonic_increasing
        expected = self.truth[tag].loc[:t].tail(self.lookback)
        pd.testing.assert_frame_equal(bars, expected, check_freq=False)
        return super().generate_signal(bars, position)


def closes_on_timeline(result: BacktestResult, data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Latest known close per symbol at every timeline point (0 before the first bar)."""
    closes = pd.DataFrame({s: f["close"] for s, f in data.items()}).reindex(result.equity_curve.index)
    return closes.ffill().fillna(0.0)


def assert_invariants(result: BacktestResult, data: dict[str, pd.DataFrame], starting_cash: float) -> None:
    marked = result.cash + (result.holdings * closes_on_timeline(result, data)).sum(axis=1)
    np.testing.assert_allclose(result.equity_curve.to_numpy(), marked.to_numpy(), rtol=1e-12, atol=1e-9)
    assert (result.cash >= 0).all(), "cash went negative (leverage)"
    assert (result.holdings >= 0).all().all(), "negative quantity (short)"
    # Everything is closed at the end, and every fee belongs to a trade.
    assert result.holdings.iloc[-1].eq(0).all()
    assert result.equity_curve.iloc[-1] == pytest.approx(result.cash.iloc[-1])
    assert sum(t.pnl for t in result.trades) == pytest.approx(result.metrics["final_equity"] - starting_cash)
    assert sum(t.fees for t in result.trades) == pytest.approx(result.metrics["fees_paid"])
    for t in result.trades:
        assert t.qty > 0 and t.fees >= 0 and t.entry_time <= t.exit_time


# --------------------------------------------------------------------------- execution timing


def test_buy_and_sell_fill_at_next_open_with_slippage_and_fees_exact_numbers():
    data = {"A": bars([
        (100, 101, 99, 100),
        (100, 101, 99, 100),   # BUY at this close
        (110, 112, 109, 111),  # buy fills at this open: 110 * 1.0005
        (115, 116, 114, 115),  # SELL at this close
        (120, 121, 119, 120),  # sell fills at this open: 120 * 0.9995
        (120, 121, 119, 120),
    ])}
    cfg = config(risk={"max_position_pct": 50.0}, fee_pct=0.1, slippage_pct=0.05, qty_step=1.0)
    result = run_backtest(Scripted({day(1): BUY, day(3): SELL}), data, cfg)

    (trade,) = result.trades
    entry_px, exit_px = 110 * 1.0005, 120 * 0.9995
    entry_fee, exit_fee = 50 * entry_px * 0.001, 50 * exit_px * 0.001
    assert trade.symbol == "A"
    assert (trade.entry_time, trade.exit_time) == (day(2), day(4))
    assert trade.qty == 50.0  # 50% of 10,000 at the signal close of 100
    assert trade.entry_price == pytest.approx(110.055, rel=1e-12)
    assert trade.exit_price == pytest.approx(119.94, rel=1e-12)
    assert trade.fees == pytest.approx(entry_fee + exit_fee, rel=1e-12)
    pnl = (exit_px - entry_px) * 50 - entry_fee - exit_fee
    assert trade.pnl == pytest.approx(pnl, rel=1e-12) and trade.pnl == pytest.approx(482.75025)
    assert trade.pnl_pct == pytest.approx(pnl / (50 * entry_px) * 100, rel=1e-12)
    assert trade.exit_reason == "signal"

    cash_after_buy = 10_000 - 50 * entry_px - entry_fee
    final = cash_after_buy + 50 * exit_px - exit_fee
    np.testing.assert_allclose(result.cash.to_numpy(),
                               [10_000, 10_000, cash_after_buy, cash_after_buy, final, final], rtol=1e-12)
    np.testing.assert_allclose(result.equity_curve.to_numpy(), [
        10_000, 10_000, cash_after_buy + 50 * 111, cash_after_buy + 50 * 115, final, final], rtol=1e-12)
    assert list(result.holdings["A"]) == [0, 0, 50, 50, 0, 0]
    assert result.metrics["final_equity"] == pytest.approx(final)
    assert result.metrics["fees_paid"] == pytest.approx(entry_fee + exit_fee)
    assert result.metrics["num_trades"] == 1.0
    assert_invariants(result, data, 10_000)


def test_nothing_fills_at_the_signal_bar_close():
    data = {"A": bars([100, 100, 200])}
    result = run_backtest(Scripted({day(0): BUY}), data, config())
    # Signal at day 0's close; the fill is day 1's open, not day 0's close.
    assert list(result.holdings["A"])[:2] == [0, 100]
    assert result.trades[0].entry_time == day(1)


def test_orders_queued_on_the_last_bar_never_fill():
    data = {"A": bars([100, 100, 100])}
    result = run_backtest(Scripted({day(2): BUY}), data, config())
    assert result.trades == []
    assert result.equity_curve.iloc[-1] == 10_000
    assert result.metrics["fees_paid"] == 0


def test_default_qty_step_rounds_quantity_down():
    data = {"A": bars([300, 300, 300])}
    result = run_backtest(Scripted({day(0): BUY}), data, config(risk={"max_position_pct": 10.0}))
    qty = result.trades[0].qty
    assert qty == floor_to_step(1000 / 300, 1e-6)
    assert qty <= 1000 / 300


# --------------------------------------------------------------------------- no look-ahead


def test_strategy_only_ever_sees_the_past_across_symbols_and_calendars():
    weekdays = pd.bdate_range(T0, periods=15, tz="UTC")
    stock = bars(list(np.linspace(100, 120, 15)), index=weekdays, tag=1)
    crypto = bars(list(np.linspace(50, 40, 21)), tag=2)
    lookback = 4
    spy = LookAheadSpy({1.0: stock, 2.0: crypto}, lookback=lookback, min_bars=2,
                       script={(1.0, weekdays[3]): BUY, (2.0, day(5)): BUY, (1.0, weekdays[9]): SELL})
    result = run_backtest(spy, {"S": stock, "C": crypto}, config(lookback=lookback))

    # One call per bar per symbol once warmed up, window capped at lookback.
    assert sum(c.tag == 1.0 for c in spy.calls) == len(stock) - 1
    assert sum(c.tag == 2.0 for c in spy.calls) == len(crypto) - 1
    assert max(c.n_bars for c in spy.calls) == lookback
    assert min(c.n_bars for c in spy.calls) == 2
    assert len(result.trades) == 2


def test_future_bars_do_not_change_past_decisions():
    base = generate_synthetic_bars(160, seed=3)
    poisoned = base.copy()
    poisoned.iloc[100:, :4] = poisoned.iloc[100:, :4] * 5.0  # absurd future prices
    cfg = BacktestConfig(risk=replace(RiskConfig(), take_profit_pct=8.0), trading_days_per_year=365)
    strategy = SMACrossover(fast=5, slow=20)
    clean = run_backtest(strategy, {"X": base}, cfg)
    dirty = run_backtest(strategy, {"X": poisoned}, cfg)

    cutoff = base.index[99]
    # Up to the last bar before the poison, the curves are identical (bar 100 is
    # where the poisoned data starts, so fills at its open may differ).
    pd.testing.assert_series_equal(clean.equity_curve.loc[:cutoff], dirty.equity_curve.loc[:cutoff])
    closed_before = [t for t in clean.trades if t.exit_time <= cutoff]
    assert closed_before and closed_before == [t for t in dirty.trades if t.exit_time <= cutoff]


def test_strategy_receives_the_open_position_marked_at_the_close():
    data = {"A": bars([100, (100, 101, 99, 102), 104, 103])}
    spy = Scripted({day(0): BUY})
    run_backtest(spy, data, config(risk={"max_position_pct": 50.0}))
    positions = [c.position for c in spy.calls]
    assert positions[0] is None
    assert positions[1] == Position("A", 50.0, 100.0, 102.0)
    assert positions[2] == Position("A", 50.0, 100.0, 104.0)


def test_signals_start_only_after_min_bars_and_window_is_capped_at_lookback():
    data = {"A": bars(list(range(100, 110)))}
    spy = Scripted(min_bars=3)
    run_backtest(spy, data, config(lookback=5))
    assert [c.n_bars for c in spy.calls] == [3, 4, 5, 5, 5, 5, 5, 5]
    assert spy.calls[0].time == day(2)
    for call in spy.calls:
        pd.testing.assert_frame_equal(call.window, data["A"].loc[:call.time].tail(5), check_freq=False)


# --------------------------------------------------------------------------- protective exits


def stop_cfg(**risk) -> BacktestConfig:
    return config(risk={"stop_loss_pct": 5.0, **risk}, slippage_pct=0.05)


def test_stop_loss_gap_down_fills_at_the_open_not_the_stop():
    data = {"A": bars([100, (100, 101, 99, 100), (90, 91, 88, 89), 89])}
    result = run_backtest(Scripted({day(0): BUY}), data, stop_cfg())
    (trade,) = result.trades
    stop = 100 * 1.0005 * 0.95
    assert 90 < stop
    assert trade.exit_reason == "stop_loss"
    assert trade.exit_time == day(2)
    assert trade.exit_price == pytest.approx(90 * 0.9995, rel=1e-12)


def test_stop_loss_inside_the_bar_fills_at_the_stop_price():
    data = {"A": bars([100, (100, 101, 99, 100), (99, 99.5, 94, 96), 96])}
    result = run_backtest(Scripted({day(0): BUY}), data, stop_cfg())
    (trade,) = result.trades
    assert trade.exit_reason == "stop_loss"
    assert trade.exit_price == pytest.approx(100 * 1.0005 * 0.95 * 0.9995, rel=1e-12)


def test_stop_wins_over_take_profit_when_both_are_touched_in_one_bar():
    data = {"A": bars([100, 100, (100, 110, 90, 100), 100])}
    cfg = config(risk={"stop_loss_pct": 5.0, "take_profit_pct": 5.0})
    (trade,) = run_backtest(Scripted({day(0): BUY}), data, cfg).trades
    assert trade.exit_reason == "stop_loss"
    assert trade.exit_price == pytest.approx(95.0)


def test_stop_can_trigger_on_the_entry_bar():
    data = {"A": bars([100, (100, 101, 94, 96), 96])}
    result = run_backtest(Scripted({day(0): BUY}), data, config(risk={"stop_loss_pct": 5.0}))
    (trade,) = result.trades
    assert trade.entry_time == trade.exit_time == day(1)
    assert trade.exit_reason == "stop_loss"
    assert trade.exit_price == pytest.approx(95.0)
    assert result.holdings["A"].eq(0).all()  # flat at every close
    assert result.equity_curve.iloc[1] == pytest.approx(10_000 * 0.95)


def test_take_profit_fills_at_target_inside_the_bar_and_at_open_on_a_gap_up():
    cfg = config(risk={"take_profit_pct": 5.0})
    inside = {"A": bars([100, 100, (100, 107, 99, 101), 101])}
    gap = {"A": bars([100, 100, (108, 110, 107, 109), 109])}
    (t1,) = run_backtest(Scripted({day(0): BUY}), inside, cfg).trades
    (t2,) = run_backtest(Scripted({day(0): BUY}), gap, cfg).trades
    assert (t1.exit_reason, t1.exit_price) == ("take_profit", pytest.approx(105.0))
    assert (t2.exit_reason, t2.exit_price) == ("take_profit", pytest.approx(108.0))


def test_no_protective_exit_when_levels_are_not_touched_or_disabled():
    data = {"A": bars([100, 100, (100, 104.9, 95.1, 100), 100])}
    touched = run_backtest(Scripted({day(0): BUY}), data,
                           config(risk={"stop_loss_pct": 5.0, "take_profit_pct": 5.0}))
    disabled = run_backtest(Scripted({day(0): BUY}), {"A": bars([100, 100, (100, 200, 1, 100), 100])},
                            config(risk={"stop_loss_pct": 0, "take_profit_pct": None}))
    assert [t.exit_reason for t in touched.trades] == ["end_of_backtest"]
    assert [t.exit_reason for t in disabled.trades] == ["end_of_backtest"]


# --------------------------------------------------------------------------- long-only discipline


def test_sell_while_flat_and_buy_while_long_do_nothing():
    data = {"A": bars([100] * 6)}
    script = {day(0): SELL, day(1): BUY, day(2): BUY, day(3): BUY}
    result = run_backtest(Scripted(script), data, config(risk={"max_position_pct": 50.0}))
    assert len(result.trades) == 1
    assert result.holdings["A"].max() == 50.0
    assert (result.holdings["A"] <= 50.0).all()


def test_queued_buy_shrinks_to_affordable_so_cash_never_goes_negative():
    # No cash buffer: 100 shares sized at the close cost 10,000 + a 0.1% fee at the open.
    data = {"A": bars([100, 100, 100])}
    result = run_backtest(Scripted({day(0): BUY}), data, config(fee_pct=0.1))
    qty = result.trades[0].qty
    assert qty == floor_to_step(10_000 / (100 * 1.001), 1e-6) < 100
    assert result.cash.min() >= 0
    assert_invariants(result, data, 10_000)


def test_queued_buy_shrinks_after_gap_up():
    data = {"A": bars([100, 125, 125])}
    result = run_backtest(Scripted({day(0): BUY}), data, config())
    assert result.trades[0].qty == floor_to_step(10_000 / 125, 1e-6)
    assert result.cash.min() >= 0


def test_queued_buy_dropped_when_what_is_left_is_below_minimum_notional():
    a = bars([100, 150, 150], tag=1)
    b = bars([100, 100, 100], tag=2)
    cfg = config(risk={"max_position_pct": 60.0, "min_order_notional": 2_000.0})
    result = run_backtest(Scripted({(1.0, day(0)): BUY, (2.0, day(0)): BUY}), {"A": a, "B": b}, cfg)
    # A (60 sh) gaps up and takes 9,000; B's 40 sh would shrink to 10 sh = 1,000 < 2,000.
    assert [t.symbol for t in result.trades] == ["A"]
    assert result.holdings["B"].eq(0).all()
    assert result.cash.min() >= 0


def test_sells_fill_before_buys_at_the_same_open():
    b = bars([100, 100, 100, 150, 150], tag=2)
    a = bars([100, 100, 100, 100, 100], tag=1)
    script = {(1.0, day(0)): BUY, (1.0, day(2)): SELL, (2.0, day(2)): BUY}
    cfg = config(risk={"max_position_pct": 60.0})
    # B is listed first, so only the sells-first rule frees A's cash for B's gap-up fill.
    result = run_backtest(Scripted(script), {"B": b, "A": a}, cfg)
    b_trade = next(t for t in result.trades if t.symbol == "B")
    assert b_trade.qty == 40.0 and b_trade.entry_price == 150.0
    assert result.cash.min() >= 0


# --------------------------------------------------------------------------- risk gates with queued buys


def three_symbols(prices: list | None = None) -> dict[str, pd.DataFrame]:
    prices = prices or [100, 100, 100, 100]
    return {s: bars(prices, tag=i) for i, s in enumerate(["A", "B", "C"], start=1)}


def buy_all_at(t: pd.Timestamp) -> Scripted:
    return Scripted({(tag, t): BUY for tag in (1.0, 2.0, 3.0)})


def test_max_open_positions_counts_queued_buys():
    cfg = config(risk={"max_open_positions": 2, "max_position_pct": 30.0})
    result = run_backtest(buy_all_at(day(0)), three_symbols(), cfg)
    assert result.holdings.iloc[1].to_dict() == {"A": 30.0, "B": 30.0, "C": 0.0}
    assert ((result.holdings > 0).sum(axis=1) <= 2).all()


def test_total_exposure_cap_counts_queued_buys():
    cfg = config(risk={"max_total_exposure_pct": 50.0, "max_position_pct": 30.0})
    result = run_backtest(buy_all_at(day(0)), three_symbols(), cfg)
    assert result.holdings.iloc[1].to_dict() == {"A": 30.0, "B": 20.0, "C": 0.0}


def test_buying_power_excludes_cash_reserved_by_queued_buys():
    cfg = config(risk={"max_position_pct": 60.0})
    result = run_backtest(buy_all_at(day(0)), three_symbols(), cfg)
    assert result.holdings.iloc[1].to_dict() == {"A": 60.0, "B": 40.0, "C": 0.0}
    assert result.cash.iloc[1] == pytest.approx(0.0)


def test_reserved_cash_includes_expected_slippage_and_fees():
    cfg = config(risk={"max_position_pct": 60.0, "cash_buffer_pct": 1.0}, fee_pct=0.1, slippage_pct=0.05)
    result = run_backtest(buy_all_at(day(0)), three_symbols(), cfg)
    per_share = 100 * 1.0005 * 1.001  # expected fill incl. slippage + fee
    held = result.holdings.iloc[1]
    b_qty = floor_to_step((10_000 - 60 * per_share) * 0.99 / 100, 1e-6)
    c_qty = floor_to_step((10_000 - (60 + b_qty) * per_share) * 0.99 / 100, 1e-6)
    assert (held["A"], held["B"], held["C"]) == (60.0, b_qty, c_qty)
    assert 0 < c_qty < 1  # only the small remainder is left for the third symbol
    assert result.cash.min() >= 0


def test_zero_cash_buffer_entry_is_shrunk_at_the_fill_to_cover_its_own_costs():
    cfg = config(risk={"max_position_pct": 60.0}, fee_pct=0.1, slippage_pct=0.05)
    result = run_backtest(buy_all_at(day(0)), three_symbols(), cfg)
    cash_after_a = 10_000 - 60 * 100.05 * 1.001
    assert result.holdings.iloc[1]["B"] == floor_to_step(cash_after_a / (100.05 * 1.001), 1e-6)
    assert 0 <= result.cash.iloc[1] < 0.01


def test_max_trades_per_day_limits_new_entries_until_the_next_day():
    cfg = config(risk={"max_trades_per_day": 1, "max_position_pct": 30.0})
    script = {(tag, t): BUY for tag in (1.0, 2.0) for t in (day(0), day(1))}
    data = {s: bars([100] * 4, tag=i) for i, s in enumerate(["A", "B"], start=1)}
    result = run_backtest(Scripted(script), data, cfg)
    entries = {t.symbol: t.entry_time for t in result.trades}
    assert entries == {"A": day(1), "B": day(2)}


# --------------------------------------------------------------------------- daily loss limit


def loss_day_data() -> dict[str, pd.DataFrame]:
    # A is bought at day 1's open and loses 10% by day 1's close (-5% of equity).
    return {"A": bars([100, (100, 100, 90, 90), 90, 90, 90], tag=1), "B": bars([50] * 5, tag=2)}


def test_daily_loss_limit_blocks_new_entries_for_the_rest_of_the_day():
    script = {(1.0, day(0)): BUY, (2.0, day(1)): BUY, (2.0, day(2)): BUY}
    cfg = config(risk={"max_daily_loss_pct": 3.0, "max_position_pct": 50.0})
    result = run_backtest(Scripted(script), loss_day_data(), cfg)
    entries = {t.symbol: t.entry_time for t in result.trades}
    # Day 1 is halted. B's BUY at day 1's close is sent at day 2's open, a new
    # day, so (as in live trading) the halt no longer applies to it.
    assert entries == {"A": day(1), "B": day(2)}
    assert {t.symbol: t.exit_reason for t in result.trades} == {"A": "end_of_backtest", "B": "end_of_backtest"}


def test_daily_loss_limit_disabled_allows_entries():
    script = {(1.0, day(0)): BUY, (2.0, day(1)): BUY}
    cfg = config(risk={"max_daily_loss_pct": None, "max_position_pct": 50.0})
    entries = {t.symbol: t.entry_time for t in run_backtest(Scripted(script), loss_day_data(), cfg).trades}
    assert entries == {"A": day(1), "B": day(2)}


def test_daily_loss_limit_flattens_where_the_bar_crosses_it_when_configured():
    # 50 A from 100 to a low of 90: the account crosses -3% (9,700) at 94, where
    # the live engine, checking on every tick, sells.
    cfg = config(risk={"max_daily_loss_pct": 3.0, "max_position_pct": 50.0, "flatten_on_daily_loss": True})
    result = run_backtest(Scripted({(1.0, day(0)): BUY}), loss_day_data(), cfg)
    (trade,) = result.trades
    assert trade.exit_reason == "daily_loss_limit"
    assert trade.exit_time == day(1)
    assert trade.exit_price == pytest.approx(94.0)


def test_a_dip_through_the_daily_loss_limit_that_recovers_by_the_close_still_flattens():
    # 90 A bought at 100 (90% of 10,000); the next day dips to 95 (-4.5% of the
    # account) and closes at 99.5 (-0.45%), then A rallies to 110. The live
    # engine sells in the dip, where the account crosses -3%: at 96.67.
    data = {"A": bars([100, 100, (100, 100.5, 95, 99.5), 110, 110])}
    cfg = config(risk={"max_daily_loss_pct": 3.0, "max_position_pct": 90.0, "flatten_on_daily_loss": True})
    result = run_backtest(Scripted({day(0): BUY}), data, cfg)
    (trade,) = result.trades
    assert (trade.exit_reason, trade.exit_time) == ("daily_loss_limit", day(2))
    assert trade.exit_price == pytest.approx(96.0 + 2 / 3)
    assert result.metrics["final_equity"] == pytest.approx(9_700.0)


def test_a_dip_through_the_daily_loss_limit_inside_a_bar_halts_later_entries_that_day():
    a = bars([100, 100, (100, 100, 92, 99.5)] + [99.5] * 3, freq="1h", tag=1)  # -4% of the account at the low
    b = bars([50] * 6, freq="1h", tag=2)
    script = {(1.0, hour(0)): BUY, (2.0, hour(2)): BUY}
    cfg = config(risk={"max_daily_loss_pct": 3.0, "max_position_pct": 50.0}, timeframe="1h")
    result = run_backtest(Scripted(script), {"A": a, "B": b}, cfg)
    assert [t.symbol for t in result.trades] == ["A"]


def test_daily_loss_limit_cancels_buys_still_waiting_for_their_open():
    # B trades weekdays only: its buy queued on Friday waits for Monday's open.
    # A's crash on Saturday trips the limit, which must cancel B's queued entry.
    fri = pd.Timestamp("2024-01-05", tz="UTC")
    a = bars([100, 100, (100, 100, 80, 80), 80, 80], start=fri - pd.Timedelta(days=1), tag=1)
    b_index = pd.DatetimeIndex([fri - pd.Timedelta(days=1), fri, fri + pd.Timedelta(days=3)])
    b = bars([50, 50, 50], index=b_index, tag=2)
    script = {(1.0, fri - pd.Timedelta(days=1)): BUY, (2.0, fri): BUY}
    cfg = config(risk={"max_daily_loss_pct": 3.0, "max_position_pct": 40.0})
    result = run_backtest(Scripted(script), {"A": a, "B": b}, cfg)
    assert [t.symbol for t in result.trades] == ["A"]
    assert result.holdings["B"].eq(0).all()


def test_daily_loss_day_boundary_follows_configured_timezone():
    # Hourly bars from 2024-01-01 00:00 UTC (= Dec 31 19:00 in New York).
    n = 12
    a = bars([100, (100, 100, 90, 90)] + [90] * (n - 2), freq="1h", tag=1)
    b = bars([50] * n, freq="1h", tag=2)
    script = {(1.0, hour(0)): BUY, **{(2.0, hour(h)): BUY for h in range(1, n)}}
    risk = {"max_daily_loss_pct": 3.0, "max_position_pct": 40.0}
    ny = run_backtest(Scripted(script), {"A": a, "B": b},
                      config(risk=risk, timeframe="1h", timezone="America/New_York"))
    utc = run_backtest(Scripted(script), {"A": a, "B": b}, config(risk=risk, timeframe="1h"))
    # New York's new day starts at 05:00 UTC: B's buy at the 04:00 bar's close is
    # sent at 05:00, on the new day, so it fills then (as in live trading).
    assert {t.symbol: t.entry_time for t in ny.trades} == {"A": hour(1), "B": hour(5)}
    # In UTC the whole run is one halted day: B never enters.
    assert [t.symbol for t in utc.trades] == ["A"]


# --------------------------------------------------------------------------- multi-symbol, invariants


def test_multi_symbol_different_calendars_fill_at_each_symbols_own_next_open():
    thu = pd.Timestamp("2024-01-04", tz="UTC")
    fri = thu + pd.Timedelta(days=1)
    stock_days = pd.DatetimeIndex([thu, fri, thu + pd.Timedelta(days=4), thu + pd.Timedelta(days=5)])
    stock = bars([100, 100, (104, 106, 103, 105), 107], index=stock_days, tag=1)
    crypto = bars([50, 50, (51, 52, 50, 51), 52, 53, 54], start=thu, tag=2)
    script = {(1.0, fri): BUY, (2.0, fri): BUY}
    data = {"S": stock, "C": crypto}
    cfg = config(risk={"max_position_pct": 40.0}, fee_pct=0.1, slippage_pct=0.05)
    spy = Scripted(script)
    result = run_backtest(spy, data, cfg)

    assert len(result.equity_curve) == 6  # union of both calendars
    entries = {t.symbol: (t.entry_time, t.entry_price) for t in result.trades}
    assert entries["C"] == (fri + pd.Timedelta(days=1), pytest.approx(51 * 1.0005))  # Saturday
    assert entries["S"] == (stock_days[2], pytest.approx(104 * 1.0005))              # Monday
    sat, sun = fri + pd.Timedelta(days=1), fri + pd.Timedelta(days=2)
    assert result.holdings.loc[sat, "S"] == 0 and result.holdings.loc[sat, "C"] > 0
    assert result.holdings.loc[sun, "S"] == 0
    # The stock is only evaluated on its own bars.
    assert [c.time for c in spy.calls if c.tag == 1.0] == list(stock_days)
    assert_invariants(result, data, 10_000)


def test_invariants_hold_on_synthetic_multi_symbol_run():
    data = {
        "AAA": generate_synthetic_bars(400, seed=1),
        "BBB": generate_synthetic_bars(300, seed=2, start_price=20.0),
        "CCC": generate_synthetic_bars(350, seed=3, start_price=500.0,
                                       end=pd.Timestamp("2025-11-01", tz="UTC").to_pydatetime()),
    }
    risk = replace(RiskConfig(), stop_loss_pct=4.0, take_profit_pct=12.0, max_open_positions=2,
                   max_daily_loss_pct=2.0, flatten_on_daily_loss=True)
    cfg = BacktestConfig(risk=risk, trading_days_per_year=365, lookback=60)
    result = run_backtest(SMACrossover(fast=5, slow=20), data, cfg)

    assert result.metrics["num_trades"] > 5
    assert_invariants(result, data, cfg.starting_cash)
    assert ((result.holdings > 0).sum(axis=1) <= 2).all()
    assert {t.exit_reason for t in result.trades} <= {
        "signal", "stop_loss", "take_profit", "daily_loss_limit", "end_of_backtest"}
    # Deterministic.
    again = run_backtest(SMACrossover(fast=5, slow=20), data, cfg)
    pd.testing.assert_series_equal(result.equity_curve, again.equity_curve)
    assert result.trades == again.trades


def test_input_bars_are_not_modified():
    data = {"A": generate_synthetic_bars(80, seed=5)}
    before = data["A"].copy()
    run_backtest(SMACrossover(fast=3, slow=10), data, BacktestConfig())
    pd.testing.assert_frame_equal(data["A"], before)


# --------------------------------------------------------------------------- end of backtest


def test_open_positions_are_force_closed_at_the_last_close_with_costs():
    data = {"A": bars([100, 100, (110, 121, 109, 120)])}
    cfg = config(fee_pct=0.1, slippage_pct=0.05, qty_step=1.0, risk={"max_position_pct": 50.0})
    result = run_backtest(Scripted({day(0): BUY}), data, cfg)
    (trade,) = result.trades
    assert trade.exit_reason == "end_of_backtest"
    assert trade.exit_time == day(2)
    assert trade.exit_price == pytest.approx(120 * 0.9995)
    assert result.equity_curve.iloc[-1] == result.metrics["final_equity"] == result.cash.iloc[-1]
    assert result.holdings.iloc[-1]["A"] == 0
    assert_invariants(result, data, 10_000)


# --------------------------------------------------------------------------- metrics


def test_max_drawdown_on_known_curves():
    assert max_drawdown_pct(pd.Series([100, 120, 90, 110, 130, 65.0])) == pytest.approx(-50.0)
    assert max_drawdown_pct(pd.Series([100, 120, 90, 110.0])) == pytest.approx(-25.0)
    assert max_drawdown_pct(pd.Series([100, 101, 102.0])) == 0.0
    assert math.isnan(max_drawdown_pct(pd.Series([], dtype=float)))


def test_metrics_on_a_known_equity_curve():
    data = {"A": bars([100, (100, 100, 100, 100), 120, 90, 110])}
    result = run_backtest(Scripted({day(0): BUY}), data, config())
    m = result.metrics
    expected_curve = [10_000, 10_000, 12_000, 9_000, 11_000]
    np.testing.assert_allclose(result.equity_curve.to_numpy(), expected_curve)
    assert m["total_return_pct"] == pytest.approx(10.0)
    assert m["max_drawdown_pct"] == pytest.approx(-25.0)
    assert m["final_equity"] == pytest.approx(11_000)
    assert m["exposure_pct"] == pytest.approx(100.0)  # holding at all 4 closes after the 1-bar warm-up
    assert m["buy_and_hold_return_pct"] == pytest.approx(10.0)
    assert m["num_trades"] == 1 and m["win_rate_pct"] == 100.0
    assert m["profit_factor"] == math.inf
    assert m["fees_paid"] == 0.0

    rets = pd.Series(expected_curve, dtype=float).pct_change().dropna()
    per_year = bars_per_year("1d", 365)
    assert m["sharpe"] == pytest.approx(rets.mean() / rets.std() * math.sqrt(per_year))
    assert m["volatility_ann_pct"] == pytest.approx(rets.std() * math.sqrt(per_year) * 100)
    years = 4 / 365.25  # from the first open a fill can happen at (day 1) to the last close
    assert m["cagr_pct"] == pytest.approx((1.1 ** (1 / years) - 1) * 100)
    assert m["start"] == day(0).timestamp() and m["end"] == day(4).timestamp()
    assert m["tradable_from"] == day(1).timestamp() and m["warmup_bars"] == 1


def test_sharpe_annualisation_uses_trading_days_per_year():
    data = {"A": bars([100, 100, 120, 90, 110])}
    m365 = run_backtest(Scripted({day(0): BUY}), data, config()).metrics
    m252 = run_backtest(Scripted({day(0): BUY}), data, config(trading_days_per_year=252)).metrics
    assert m252["sharpe"] == pytest.approx(m365["sharpe"] * math.sqrt(252 / 365))


def test_win_rate_avg_trade_and_profit_factor():
    data = {"A": bars([100, 100, 110, 110, 100, 90, 90])}
    script = {day(0): BUY, day(2): SELL, day(3): BUY, day(4): SELL}
    result = run_backtest(Scripted(script), data, config(risk={"max_position_pct": 50.0}))
    first, second = result.trades
    assert first.pnl == pytest.approx(50 * 10) and first.pnl_pct == pytest.approx(10.0)
    assert second.pnl < 0 and second.pnl_pct == pytest.approx(-10.0)  # in at 100, out at 90
    m = result.metrics
    assert m["num_trades"] == 2 and m["win_rate_pct"] == 50.0
    assert m["avg_trade_pct"] == pytest.approx((first.pnl_pct + second.pnl_pct) / 2)
    assert m["profit_factor"] == pytest.approx(first.pnl / -second.pnl)


def test_metrics_without_any_trade_are_nan_safe():
    result = run_backtest(Scripted(), {"A": bars([100, 101, 99, 100])}, config())
    m = result.metrics
    assert m["num_trades"] == 0 and m["total_return_pct"] == 0 and m["max_drawdown_pct"] == 0
    assert m["exposure_pct"] == 0 and m["sharpe"] == 0 and m["volatility_ann_pct"] == 0
    for key in ("win_rate_pct", "avg_trade_pct", "profit_factor"):
        assert math.isnan(m[key])
    assert all(isinstance(v, float) for v in m.values())
    assert "n/a" in result.summary()


def test_single_bar_backtest_does_not_crash():
    result = run_backtest(Scripted({day(0): BUY}), {"A": bars([100])}, config())
    assert result.trades == [] and len(result.equity_curve) == 1
    assert math.isnan(result.metrics["sharpe"])
    assert math.isnan(result.metrics["buy_and_hold_return_pct"])  # never tradable
    result.summary()


def test_buy_and_hold_starts_at_first_tradable_open_with_entry_costs_equal_weight():
    a = bars([100, 100, 104, 105, 110], tag=1)
    b = bars([50, 50, 40, 45, 60], tag=2)
    short = bars([10, 10], start=day(3), tag=3)  # too short to ever trade: excluded
    cfg = config(fee_pct=0.1, slippage_pct=0.05)
    m = run_backtest(Scripted(min_bars=2), {"A": a, "B": b, "C": short}, cfg).metrics
    cost = 1.0005 * 1.001
    expected = ((110 / (104 * cost) - 1) + (60 / (40 * cost) - 1)) / 2 * 100
    assert m["buy_and_hold_return_pct"] == pytest.approx(expected)


# --------------------------------------------------------------------------- summary and files


def trading_result() -> BacktestResult:
    data = {"A": bars([100, 100, 110, 110, 100, 90, 90])}
    script = {day(0): BUY, day(2): SELL, day(3): BUY}
    return run_backtest(Scripted(script), data, config(risk={"max_position_pct": 50.0}, fee_pct=0.1))


def test_summary_is_an_aligned_table_of_key_metrics():
    text = trading_result().summary()
    for label in ("Final equity", "Total return", "CAGR", "Max drawdown", "Sharpe", "Win rate",
                  "Profit factor", "Fees paid", "Buy & hold return", "Trades"):
        assert label in text
    assert "2024-01-01 -> 2024-01-07" in text
    assert "Exits: end_of_backtest 1, signal 1" in text
    table = [line for line in text.splitlines() if line.startswith(("Final equity", "Total return", "Trades"))]
    assert len({len(line) for line in table}) == 1  # right-aligned values


def test_summary_hides_cagr_when_the_data_is_too_short_to_annualise():
    data = {"A": bars([100, 100, 101, 99, 100], freq="1h")}  # 5 hours, 4 after the 1-bar warm-up
    result = run_backtest(Scripted({hour(0): BUY}), data, config(timeframe="1h"))
    assert math.isfinite(result.metrics["cagr_pct"])  # the metric itself is still computed
    text = result.summary()
    cagr_line = next(line for line in text.splitlines() if line.startswith("CAGR"))
    assert cagr_line.split()[-1] == "n/a"
    assert "4.0 hours, too short to annualise" in text


def test_summary_shows_cagr_for_a_long_enough_period():
    data = {"A": bars([100] * 40)}  # 40 days
    text = run_backtest(Scripted(), data, config()).summary()
    cagr_line = next(line for line in text.splitlines() if line.startswith("CAGR"))
    assert cagr_line.split()[-1] == "+0.00%"
    assert "too short to annualise" not in text


def test_summary_renders_infinite_profit_factor():
    data = {"A": bars([100, 100, 120])}
    text = run_backtest(Scripted({day(0): BUY}), data, config()).summary()
    assert "inf" in text


def test_save_writes_equity_trades_and_strict_json_metrics(tmp_path: Path):
    result = trading_result()
    out = tmp_path / "nested" / "run"
    result.save(out)

    equity = pd.read_csv(out / "equity.csv", index_col="time", parse_dates=True)
    assert list(equity.columns) == ["equity", "cash", "qty_A"]
    np.testing.assert_allclose(equity["equity"].to_numpy(), result.equity_curve.to_numpy())

    trades = pd.read_csv(out / "trades.csv")
    assert list(trades.columns) == list(Trade.__dataclass_fields__)
    assert list(trades["exit_reason"]) == ["signal", "end_of_backtest"]
    assert pd.Timestamp(trades["entry_time"][0]) == day(1)

    def reject(value: str):
        raise AssertionError(f"non-standard JSON constant {value}")

    metrics = json.loads((out / "metrics.json").read_text(), parse_constant=reject)
    assert metrics["num_trades"] == 2
    assert metrics["start_time"].startswith("2024-01-01")
    assert set(result.metrics) <= set(metrics)


def test_save_handles_no_trades_and_non_finite_metrics(tmp_path: Path):
    result = run_backtest(Scripted(), {"A": bars([100, 100])}, config())
    result.save(tmp_path)
    assert pd.read_csv(tmp_path / "trades.csv").empty
    metrics = json.loads((tmp_path / "metrics.json").read_text())
    assert metrics["win_rate_pct"] is None and metrics["profit_factor"] is None

    winner = run_backtest(Scripted({day(0): BUY}), {"A": bars([100, 100, 120])}, config())
    winner.save(tmp_path / "w")
    assert json.loads((tmp_path / "w" / "metrics.json").read_text())["profit_factor"] == "inf"


# --------------------------------------------------------------------------- validation


@pytest.mark.parametrize("overrides, match", [
    ({"starting_cash": 0}, "starting_cash"),
    ({"starting_cash": math.nan}, "starting_cash"),
    ({"fee_pct": -0.1}, "fee_pct"),
    ({"slippage_pct": 100}, "slippage_pct"),
    ({"lookback": 0}, "lookback"),
    ({"trading_days_per_year": 0}, "trading_days_per_year"),
    ({"timeframe": "7x"}, "timeframe"),
    ({"timezone": "Mars/Olympus"}, "timezone"),
    ({"qty_step": -1}, "qty_step"),
])
def test_invalid_config_is_rejected(overrides, match):
    with pytest.raises(ValueError, match=match):
        run_backtest(Scripted(), {"A": bars([100, 100])}, config(**overrides))


def test_invalid_risk_config_is_rejected():
    with pytest.raises(ValueError, match="max_open_positions"):
        run_backtest(Scripted(), {"A": bars([100, 100])}, config(risk={"max_open_positions": 0}))


def test_lookback_shorter_than_strategy_warmup_is_rejected():
    with pytest.raises(ValueError, match="min_bars"):
        run_backtest(Scripted(min_bars=10), {"A": bars([100] * 20)}, config(lookback=5))


@pytest.mark.parametrize("data, match", [
    ({}, "no data"),
    ({"A": bars([100]).iloc[:0]}, "no bars"),
    ({"A": bars([100, 0])}, "> 0"),
    ({"A": bars([100, 100]).drop(columns="volume")}, "missing columns"),
])
def test_bad_data_is_rejected(data, match):
    with pytest.raises(ValueError, match=match):
        run_backtest(Scripted(), data, config())


# --------------------------------------------------------------------------- regression: gate day


def test_daily_loss_halt_applies_on_the_day_the_buy_is_sent_like_live():
    # Daily bars: A and B (30% each) fall 8% on day 1 -> equity -4.8%, limit 3%.
    # C's BUY at day 1's close is sent at day 2's open: a new trading day, and
    # the live engine (which sees day 1's bar only on day 2) takes it.
    fall = [100, (100, 100, 92, 92), 92, 92]
    data = {"A": bars(fall, tag=1), "B": bars(fall, tag=2), "C": bars([50] * 4, tag=3)}
    script = {(1.0, day(0)): BUY, (2.0, day(0)): BUY, (3.0, day(1)): BUY}
    cfg = config(risk={"max_daily_loss_pct": 3.0, "max_position_pct": 30.0})

    result = run_backtest(Scripted(script), data, cfg)

    assert {t.symbol: t.entry_time for t in result.trades} == {"A": day(1), "B": day(1), "C": day(2)}


def test_daily_loss_halt_still_drops_a_buy_that_fills_later_the_same_day():
    fall = [100, (100, 100, 92, 92), 92, 92, 92]
    data = {"A": bars(fall, freq="1h", tag=1), "B": bars(fall, freq="1h", tag=2),
            "C": bars([50] * 5, freq="1h", tag=3)}
    script = {(1.0, hour(0)): BUY, (2.0, hour(0)): BUY, (3.0, hour(1)): BUY, (3.0, hour(2)): BUY}
    cfg = config(risk={"max_daily_loss_pct": 3.0, "max_position_pct": 30.0}, timeframe="1h")

    result = run_backtest(Scripted(script), data, cfg)

    assert sorted(t.symbol for t in result.trades) == ["A", "B"]


def test_max_trades_per_day_counts_on_the_day_the_buy_is_sent():
    # One entry a day: BUYs at day 0's close for A and B. A is sent (and counted)
    # on day 1; B, queued at day 1's close, is sent on day 2.
    cfg = config(risk={"max_trades_per_day": 1, "max_position_pct": 30.0})
    script = {(1.0, day(0)): BUY, (2.0, day(0)): BUY, (2.0, day(1)): BUY}
    data = {s: bars([100] * 4, tag=i) for i, s in enumerate(["A", "B"], start=1)}
    result = run_backtest(Scripted(script), data, cfg)
    assert {t.symbol: t.entry_time for t in result.trades} == {"A": day(1), "B": day(2)}


# --------------------------------------------------------------------------- regression: rotation, open gaps


def rotation_data(order: tuple[str, ...] = ("A", "B", "C")) -> dict[str, pd.DataFrame]:
    tags = {"A": 1, "B": 2, "C": 3}
    return {s: bars([100] * 6, tag=tags[s]) for s in order}


ROTATION = {(1.0, day(0)): BUY, (2.0, day(0)): BUY, (1.0, day(2)): SELL, (3.0, day(2)): BUY}


def test_exit_queued_earlier_in_the_same_close_frees_its_slot_for_a_later_symbol():
    # Like the live engine, which sells A (and re-reads the account) before it
    # sizes C, the next symbol in `symbols` order.
    cfg = config(risk={"max_open_positions": 2, "max_position_pct": 40.0})
    result = run_backtest(Scripted(ROTATION), rotation_data(), cfg)
    entries = sorted((t.symbol, t.entry_time) for t in result.trades)
    assert entries == [("A", day(1)), ("B", day(1)), ("C", day(3))]


def test_exit_of_a_later_symbol_does_not_free_a_slot_for_an_earlier_one():
    # symbols [C, A, B]: live sizes C before it sells A, so the slots are still full.
    cfg = config(risk={"max_open_positions": 2, "max_position_pct": 40.0})
    result = run_backtest(Scripted(ROTATION), rotation_data(("C", "A", "B")), cfg)
    assert sorted(t.symbol for t in result.trades) == ["A", "B"]


def test_exit_queued_earlier_in_the_same_close_frees_its_cash_when_fully_invested():
    cfg = config(risk={"max_open_positions": 5, "max_position_pct": 50.0})
    result = run_backtest(Scripted(ROTATION), rotation_data(), cfg)
    assert ("C", day(3)) in [(t.symbol, t.entry_time) for t in result.trades]
    assert result.cash.min() >= 0


def gap_open_data(gap_open: float) -> dict[str, pd.DataFrame]:
    # A is bought at day 1's open (45% of equity) and gaps to ``gap_open`` at day 2's open.
    a = bars([100, 100, (gap_open, gap_open, gap_open, gap_open), gap_open], tag=1)
    return {"A": a, "B": bars([50] * 4, tag=2)}


def test_daily_loss_limit_applies_to_an_entry_at_a_gap_down_open():
    # Live on Alpaca compares the first tick after the open with the previous
    # close: -8% on 45% of equity is -3.6%, past the 3% limit, so B is not bought.
    script = {(1.0, day(0)): BUY, (2.0, day(1)): BUY}
    cfg = config(risk={"max_daily_loss_pct": 3.0, "max_position_pct": 45.0})
    result = run_backtest(Scripted(script), gap_open_data(92.0), cfg)
    assert [t.symbol for t in result.trades] == ["A"]


def test_gap_down_inside_the_daily_loss_limit_still_enters():
    script = {(1.0, day(0)): BUY, (2.0, day(1)): BUY}
    cfg = config(risk={"max_daily_loss_pct": 3.0, "max_position_pct": 45.0})
    result = run_backtest(Scripted(script), gap_open_data(96.0), cfg)  # -1.8% of equity
    assert {t.symbol: t.entry_time for t in result.trades} == {"A": day(1), "B": day(2)}


def test_gap_down_through_the_daily_loss_limit_flattens_at_that_open_when_configured():
    script = {(1.0, day(0)): BUY}
    cfg = config(risk={"max_daily_loss_pct": 3.0, "max_position_pct": 45.0, "flatten_on_daily_loss": True})
    result = run_backtest(Scripted(script), gap_open_data(92.0), cfg)
    (trade,) = result.trades
    assert (trade.exit_reason, trade.exit_time, trade.exit_price) == ("daily_loss_limit", day(2), 92.0)


# --------------------------------------------------------------------------- regression: the open comes first


def test_a_gap_up_through_the_take_profit_exits_there_even_if_the_bar_then_falls_through_the_stop():
    # Earnings gap: opens at 112 (target 110), then reverses to a low of 94
    # (stop 95). The open is known before the high and the low: live sells there.
    data = {"A": bars([100, (100, 101, 99, 100), (112, 113, 94, 96), 96])}
    cfg = config(risk={"stop_loss_pct": 5.0, "take_profit_pct": 10.0})
    result = run_backtest(Scripted({day(0): BUY}), data, cfg)
    (trade,) = result.trades
    assert (trade.exit_reason, trade.exit_time, trade.exit_price) == ("take_profit", day(2), 112.0)
    assert result.metrics["final_equity"] == pytest.approx(11_200.0)


def gap_stop_data(order: tuple[str, ...] = ("A", "B")) -> dict[str, pd.DataFrame]:
    # A (bought at day 1's open) opens day 4 at 90, through its 5% stop; B has
    # a one-bar BUY signal at day 3's close, when the only slot is A's.
    frames = {"A": bars([100, 100, 100, 100, (90, 91, 89, 90), 90], tag=1), "B": bars([50] * 6, tag=2)}
    return {symbol: frames[symbol] for symbol in order}


GAP_STOP = {(1.0, day(0)): BUY, (2.0, day(3)): BUY}


def test_a_gap_stop_at_the_open_frees_its_slot_for_a_later_symbols_entry_at_that_open():
    # Live, at day 4's first tick: A is stopped out, then B (next in `symbols`)
    # is sized with the slot free and bought at the same open.
    cfg = config(risk={"max_open_positions": 1, "max_position_pct": 50.0, "stop_loss_pct": 5.0})
    result = run_backtest(Scripted(GAP_STOP), gap_stop_data(), cfg)
    entries = {t.symbol: (t.entry_time, t.entry_price) for t in result.trades}
    assert entries == {"A": (day(1), 100.0), "B": (day(4), 50.0)}
    assert [(t.symbol, t.exit_reason, t.exit_time) for t in result.trades if t.symbol == "A"] == [
        ("A", "stop_loss", day(4))]
    assert result.cash.min() >= 0


def test_a_gap_stop_of_a_later_symbol_does_not_free_a_slot_for_an_earlier_one():
    # symbols [B, A]: live sizes B before it looks at A's stop, so the slot is still taken.
    cfg = config(risk={"max_open_positions": 1, "max_position_pct": 50.0, "stop_loss_pct": 5.0})
    result = run_backtest(Scripted(GAP_STOP), gap_stop_data(("B", "A")), cfg)
    assert [t.symbol for t in result.trades] == ["A"]


# --------------------------------------------------------------------------- regression: warm-up bars


def test_warm_up_bars_do_not_dilute_the_annualised_metrics():
    # The same trades on the same prices, once with a 1-bar warm-up and once
    # after 40 extra flat bars the strategy needs as history first.
    prices = [100, 100, 104, 101, 108, 103, 110, 107, 112, 109, 115, 111]
    warmup = 40
    plain = bars(prices, start=day(0))
    padded = bars([100] * warmup + prices, start=day(-warmup))
    script = {day(0): BUY, day(5): SELL, day(6): BUY}
    a = run_backtest(Scripted(script, min_bars=1), {"A": plain}, config()).metrics
    b = run_backtest(Scripted(script, min_bars=warmup + 1), {"A": padded}, config()).metrics
    for key in ("total_return_pct", "cagr_pct", "sharpe", "volatility_ann_pct", "exposure_pct",
                "max_drawdown_pct", "buy_and_hold_return_pct"):
        assert b[key] == pytest.approx(a[key], rel=1e-9, abs=1e-12), key
    assert a["tradable_from"] == b["tradable_from"] == day(1).timestamp()
    assert (a["warmup_bars"], b["warmup_bars"]) == (1, warmup + 1)


def test_summary_shows_the_warm_up_and_the_trading_period():
    data = {"A": bars([100] * 10 + [100, 101, 102, 103, 104])}
    text = run_backtest(Scripted({day(10): BUY}, min_bars=11), data, config()).summary()
    assert "2024-01-01 -> 2024-01-15 (15 bars)" in text
    assert "2024-01-12 -> 2024-01-15" in text and "11 warm-up bars" in text


# --------------------------------------------------------------------------- regression: the floor before the target


def test_a_bar_through_the_take_profit_and_the_daily_loss_floor_counts_the_floor_first():
    # Bought at 100 with the whole account; the next bar spans 96..111: the
    # order of its low and high is unknown, so the low (the floor) comes first.
    data = {"A": bars([100, (100, 111, 96, 105), 105])}
    cfg = config(risk={"max_daily_loss_pct": 3.0, "flatten_on_daily_loss": True, "take_profit_pct": 10.0})
    result = run_backtest(Scripted({day(0): BUY}), data, cfg)
    (trade,) = result.trades
    assert (trade.exit_reason, trade.exit_time) == ("daily_loss_limit", day(1))
    assert trade.exit_price == pytest.approx(97.0)  # where the account crossed -3%
