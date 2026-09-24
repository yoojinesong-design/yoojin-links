"""Tests for bot.engine: the live trading tick and loop.

Everything runs offline on a PaperBroker over a small deterministic fake feed,
with a scripted strategy and a clock the test controls.
"""
from __future__ import annotations

import csv
import json
import math
import threading
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

import pandas as pd
import pytest
from pandas.tseries.frequencies import to_offset

from bot.brokers.base import Broker, BrokerError
from bot.brokers.paper import PaperBroker
from bot.config import BotConfig, NotifyConfig
from bot.data import SyntheticFeed
from bot.engine import (
    MAX_BACKOFF_SECONDS,
    TRADE_COLUMNS,
    TickReport,
    TradingEngine,
    backoff_seconds,
    make_client_order_id,
)
from bot.models import Account, Action, OrderRequest, OrderResult, Position, Side, Signal
from bot.notify import Notifier
from bot.risk import RiskConfig, RiskManager
from bot.state import STATE_FILE, BotState, StateStore, set_kill_switch
from bot.strategies import create_strategy
from bot.strategies.base import Strategy
from bot.utils import timeframe_to_timedelta

# Thursday 14:30 UTC: with 1h bars the 14:00 bar is still forming and the last
# CLOSED bar is the one that opened at 13:00.
T0 = datetime(2026, 9, 24, 14, 30, tzinfo=timezone.utc)
TODAY = "2026-09-24"
LAST_CLOSED = pd.Timestamp("2026-09-24 13:00", tz="UTC")
TF = "1h"
LOOKBACK = 10
POLL = 60


# --------------------------------------------------------------------------- fakes


class Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: float) -> None:
        self.now += timedelta(**kwargs)


class FakeFeed:
    """Flat hourly bars ending with the bar forming at ``clock()``.

    Each symbol's bars carry a distinct volume code so the scripted strategy
    can tell whose bars it was given (strategies never see the symbol)."""

    def __init__(self, clock: Clock, prices: dict[str, float], include_forming: bool = True) -> None:
        self.clock = clock
        self.prices = dict(prices)
        self.codes = {symbol: float(i + 1) for i, symbol in enumerate(prices)}
        self.include_forming = include_forming
        self.market_open = True
        self.fail_bars: dict[str, Exception] = {}
        self.fail_price: dict[str, Exception] = {}
        self.bars_calls: list[tuple[str, str, int]] = []

    def symbol_for(self, bars: pd.DataFrame) -> str:
        code = float(bars["volume"].iloc[-1])
        return next(s for s, c in self.codes.items() if c == code)

    def get_bars(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        self.bars_calls.append((symbol, timeframe, limit))
        if symbol in self.fail_bars:
            raise self.fail_bars[symbol]
        td = timeframe_to_timedelta(timeframe)
        last = pd.Timestamp(self.clock()).floor(to_offset(td))
        if not self.include_forming:
            last -= td
        index = pd.date_range(end=last, periods=limit, freq=td)
        price = self.prices[symbol]
        return pd.DataFrame({"open": price, "high": price, "low": price, "close": price,
                             "volume": self.codes[symbol]}, index=index)

    def get_latest_price(self, symbol: str) -> float:
        if symbol in self.fail_price:
            raise self.fail_price[symbol]
        return self.prices[symbol]

    def is_market_open(self) -> bool:
        return self.market_open


class ScriptedStrategy(Strategy):
    """Returns whatever action the test scripted for each symbol (HOLD by default)."""

    name = "scripted"

    def __init__(self, feed: FakeFeed, actions: dict[str, Action] | None = None, min_bars: int = 5) -> None:
        self.feed = feed
        self.actions = dict(actions or {})
        self.fail: dict[str, Exception] = {}
        self._min_bars = min_bars
        self.calls: list[tuple[str, pd.Timestamp, int, Position | None]] = []
        super().__init__()

    @property
    def min_bars(self) -> int:
        return self._min_bars

    def generate_signal(self, bars: pd.DataFrame, position: Position | None) -> Signal:
        symbol = self.feed.symbol_for(bars)
        self.calls.append((symbol, bars.index[-1], len(bars), position))
        if symbol in self.fail:
            raise self.fail[symbol]
        action = self.actions.get(symbol, Action.HOLD)
        return Signal(action, f"scripted {action.value}")

    def symbols_called(self) -> list[str]:
        return [call[0] for call in self.calls]


class RecordingNotifier(Notifier):
    """A real Notifier with no destinations (so no network) that remembers messages."""

    def __init__(self) -> None:
        super().__init__(NotifyConfig(), mode="paper")
        self.trades: list[str] = []
        self.errors: list[str] = []

    def trade(self, text: str) -> None:
        self.trades.append(text)
        super().trade(text)

    def error(self, text: str) -> None:
        self.errors.append(text)
        super().error(text)


class RecordingEvent(threading.Event):
    """Stop event whose wait() returns at once and records the timeout.
    Sets itself after ``stop_after`` waits (if given)."""

    def __init__(self, stop_after: int | None = None) -> None:
        super().__init__()
        self.waits: list[float] = []
        self.stop_after = stop_after

    def wait(self, timeout: float | None = None) -> bool:
        self.waits.append(timeout)
        if self.stop_after is not None and len(self.waits) >= self.stop_after:
            self.set()
        return self.is_set()


@dataclass
class Harness:
    engine: TradingEngine
    broker: PaperBroker
    feed: FakeFeed
    strategy: ScriptedStrategy
    notifier: RecordingNotifier
    clock: Clock
    cfg: BotConfig
    store: StateStore

    def tick(self) -> TickReport:
        return self.engine.run_once()

    def state(self) -> BotState:
        return self.store.load()

    def save_state(self, **fields: object) -> None:
        self.store.save(BotState(**fields))

    def buy(self, symbol: str, qty: float) -> None:
        """Open a position directly at the broker (outside the engine)."""
        assert self.broker.submit_order(OrderRequest(symbol, Side.BUY, qty)).status == "filled"


def make_harness(tmp_path: Path, *, prices: dict[str, float] | None = None,
                 actions: dict[str, Action] | None = None, risk: RiskConfig | None = None,
                 min_bars: int = 5, timezone_name: str = "UTC", include_forming: bool = True,
                 broker: Broker | None = None, **cfg_overrides: object) -> Harness:
    clock = Clock(T0)
    feed = FakeFeed(clock, prices or {"AAA": 100.0, "BBB": 50.0}, include_forming=include_forming)
    paper = PaperBroker(feed, starting_cash=10_000.0, fee_pct=0.0, slippage_pct=0.0, clock=clock)
    settings: dict[str, object] = dict(
        symbols=list(feed.prices), timeframe=TF, bars_lookback=LOOKBACK, timezone=timezone_name,
        poll_interval_seconds=POLL, risk=risk or RiskConfig(), state_dir=tmp_path / "state",
        log_dir=tmp_path / "logs")
    cfg = BotConfig(**{**settings, **cfg_overrides})
    strategy = ScriptedStrategy(feed, actions, min_bars=min_bars)
    notifier = RecordingNotifier()
    store = StateStore(cfg.state_dir / STATE_FILE)
    engine = TradingEngine(cfg, broker if broker is not None else paper, strategy, RiskManager(cfg.risk),
                           store, notifier, clock=clock)
    return Harness(engine, paper, feed, strategy, notifier, clock, cfg, store)


def statuses(report: TickReport) -> list[tuple[str, str, str]]:
    return [(o.symbol, o.side.value, o.status) for o in report.orders]


def read_trades(h: Harness) -> list[dict[str, str]]:
    with (h.cfg.log_dir / "trades.csv").open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# --------------------------------------------------------------------------- kill switch / skips


def test_kill_switch_makes_no_broker_calls_and_writes_no_state(tmp_path):
    broker = Mock(spec=Broker)
    h = make_harness(tmp_path, broker=broker, actions={"AAA": Action.BUY})
    set_kill_switch(h.cfg.state_dir, True, "manual stop")

    report = h.tick()

    assert report.skipped == "kill_switch"
    assert broker.mock_calls == []
    assert report.orders == [] and report.errors == []
    assert h.strategy.calls == []
    assert not h.store.path.exists()


def test_kill_switch_removed_resumes_trading(tmp_path):
    h = make_harness(tmp_path, actions={"AAA": Action.BUY})
    set_kill_switch(h.cfg.state_dir, True)
    assert h.tick().skipped == "kill_switch"
    set_kill_switch(h.cfg.state_dir, False)

    report = h.tick()

    assert report.skipped is None
    assert statuses(report) == [("AAA", "buy", "filled")]


def test_market_closed_skips_symbols_but_rolls_day_and_saves_state(tmp_path):
    h = make_harness(tmp_path, actions={"AAA": Action.BUY, "BBB": Action.BUY})
    h.feed.market_open = False

    report = h.tick()

    assert report.skipped == "market_closed"
    assert report.orders == [] and report.errors == []
    assert h.feed.bars_calls == [] and h.strategy.calls == []
    assert report.equity == pytest.approx(10_000.0)
    state = h.state()
    assert state.day == TODAY and state.day_start_equity == pytest.approx(10_000.0)
    assert state.last_tick_at == T0.isoformat()


def test_trading_blocked_account_is_skipped(tmp_path):
    h = make_harness(tmp_path, actions={"AAA": Action.BUY})
    real = h.broker.get_account
    h.broker.get_account = lambda: replace(real(), trading_blocked=True)

    report = h.tick()

    assert report.skipped == "trading_blocked"
    assert report.orders == [] and report.errors == []
    assert h.strategy.calls == []
    assert h.state().last_tick_at is not None


# --------------------------------------------------------------------------- day roll


def test_first_tick_starts_the_day_with_current_equity_when_broker_has_no_baseline(tmp_path):
    h = make_harness(tmp_path)
    h.tick()
    state = h.state()
    assert state.day == TODAY
    assert state.day_start_equity == pytest.approx(10_000.0)
    assert state.trades_today == 0 and state.halted_today is False


def test_day_start_equity_prefers_the_brokers_value(tmp_path):
    h = make_harness(tmp_path)
    real = h.broker.get_account
    h.broker.get_account = lambda: replace(real(), day_start_equity=12_000.0)
    h.tick()
    assert h.state().day_start_equity == pytest.approx(12_000.0)


@pytest.mark.parametrize("bad", [None, 0.0, -5.0, math.nan, math.inf])
def test_day_start_equity_falls_back_to_equity_when_broker_value_unusable(tmp_path, bad):
    h = make_harness(tmp_path)
    real = h.broker.get_account
    h.broker.get_account = lambda: replace(real(), day_start_equity=bad)
    report = h.tick()
    assert report.errors == []
    assert h.state().day_start_equity == pytest.approx(10_000.0)


def test_new_day_resets_counters_but_keeps_evaluated_bars(tmp_path):
    h = make_harness(tmp_path)
    h.save_state(day="2026-09-23", day_start_equity=50_000.0, trades_today=7, halted_today=True,
                 last_signal_bar={"ZZZ": "2026-09-23T00:00:00+00:00"})

    report = h.tick()

    state = h.state()
    assert state.day == TODAY
    assert state.day_start_equity == pytest.approx(10_000.0)
    assert state.trades_today == 0 and state.halted_today is False and report.halted is False
    assert state.last_signal_bar["ZZZ"] == "2026-09-23T00:00:00+00:00"


def test_same_day_keeps_counters(tmp_path):
    h = make_harness(tmp_path)
    h.save_state(day=TODAY, day_start_equity=10_000.0, trades_today=4)
    h.tick()
    state = h.state()
    assert state.trades_today == 4 and state.day_start_equity == pytest.approx(10_000.0)


def test_trading_day_follows_the_configured_timezone(tmp_path):
    # 03:00 UTC on the 25th is still the evening of the 24th in New York.
    h = make_harness(tmp_path, timezone_name="America/New_York")
    h.clock.now = datetime(2026, 9, 25, 3, 0, tzinfo=timezone.utc)
    h.save_state(day=TODAY, day_start_equity=10_000.0, trades_today=3)
    h.tick()
    assert h.state().day == TODAY and h.state().trades_today == 3

    h.clock.advance(hours=2)  # 05:00 UTC = 01:00 in New York on the 25th
    h.tick()
    assert h.state().day == "2026-09-25" and h.state().trades_today == 0


def test_missing_day_start_equity_is_filled_in_later_the_same_day(tmp_path):
    h = make_harness(tmp_path)
    h.save_state(day=TODAY, day_start_equity=None)
    h.tick()
    assert h.state().day_start_equity == pytest.approx(10_000.0)


# --------------------------------------------------------------------------- daily loss limit


def test_daily_loss_halt_blocks_new_entries(tmp_path):
    h = make_harness(tmp_path, actions={"AAA": Action.BUY}, risk=RiskConfig(max_daily_loss_pct=3.0))
    h.save_state(day=TODAY, day_start_equity=20_000.0)  # equity 10k = -50% today

    report = h.tick()

    assert report.orders == []
    assert report.halted is True and h.state().halted_today is True
    assert "daily loss" in report.signals["AAA"]
    assert report.errors == []  # a risk halt is not an API error
    assert any("Daily loss limit hit" in m for m in h.notifier.errors)
    assert "AAA" in h.state().last_signal_bar  # the bar was evaluated: no retry this bar


def test_small_loss_below_limit_does_not_halt(tmp_path):
    h = make_harness(tmp_path, actions={"AAA": Action.BUY}, risk=RiskConfig(max_daily_loss_pct=3.0))
    h.save_state(day=TODAY, day_start_equity=10_200.0)  # -1.96%
    report = h.tick()
    assert report.halted is False
    assert statuses(report) == [("AAA", "buy", "filled")]


def test_daily_loss_halt_still_runs_strategy_exits_and_stops(tmp_path):
    h = make_harness(tmp_path, actions={"AAA": Action.SELL, "BBB": Action.HOLD},
                     risk=RiskConfig(max_daily_loss_pct=3.0, stop_loss_pct=5.0))
    h.buy("AAA", 10)
    h.buy("BBB", 10)
    h.feed.prices["BBB"] = 45.0  # 10% under entry: stop-loss
    h.save_state(day=TODAY, day_start_equity=100_000.0)

    report = h.tick()

    assert report.halted is True
    assert sorted(statuses(report)) == [("AAA", "sell", "filled"), ("BBB", "sell", "filled")]
    assert h.broker.get_positions() == {}
    assert [o.reason for o in report.orders if o.symbol == "BBB"] == ["stop_loss"]


def test_daily_loss_is_notified_once_per_day(tmp_path):
    h = make_harness(tmp_path, risk=RiskConfig(max_daily_loss_pct=3.0))
    h.save_state(day=TODAY, day_start_equity=20_000.0)
    h.tick()
    h.clock.advance(minutes=5)
    h.tick()
    assert sum("Daily loss limit hit" in m for m in h.notifier.errors) == 1


def test_disabled_daily_loss_limit_never_halts(tmp_path):
    h = make_harness(tmp_path, actions={"AAA": Action.BUY}, risk=RiskConfig(max_daily_loss_pct=None))
    h.save_state(day=TODAY, day_start_equity=100_000.0)
    report = h.tick()
    assert report.halted is False and len(report.orders) == 1


def test_flatten_on_daily_loss_closes_every_position_once(tmp_path):
    h = make_harness(tmp_path, risk=RiskConfig(max_daily_loss_pct=3.0, flatten_on_daily_loss=True,
                                               stop_loss_pct=None))
    h.buy("AAA", 10)
    h.buy("BBB", 20)
    h.save_state(day=TODAY, day_start_equity=100_000.0)

    report = h.tick()

    assert sorted(statuses(report)) == [("AAA", "sell", "filled"), ("BBB", "sell", "filled")]
    assert h.broker.get_positions() == {}
    assert len(read_trades(h)) == 2
    assert all("flatten" in row["reason"] for row in read_trades(h))
    assert report.equity == pytest.approx(10_000.0)

    h.clock.advance(minutes=5)
    assert h.tick().orders == []


def test_failed_flatten_is_retried_next_tick(tmp_path):
    h = make_harness(tmp_path, risk=RiskConfig(max_daily_loss_pct=3.0, flatten_on_daily_loss=True,
                                               stop_loss_pct=None))
    h.buy("AAA", 10)
    h.save_state(day=TODAY, day_start_equity=100_000.0)
    real = h.broker.close_all_positions
    h.broker.close_all_positions = Mock(side_effect=BrokerError("exchange timeout"))

    first = h.tick()
    assert any("closing all positions" in e for e in first.errors)
    assert "AAA" in h.broker.get_positions()

    h.broker.close_all_positions = real
    second = h.tick()
    assert statuses(second) == [("AAA", "sell", "filled")]
    assert h.broker.get_positions() == {}


# --------------------------------------------------------------------------- bars and evaluation


def test_incomplete_last_bar_is_dropped_and_lookback_respected(tmp_path):
    h = make_harness(tmp_path)
    h.tick()
    assert h.feed.bars_calls[0] == ("AAA", TF, LOOKBACK + 1)
    symbol, last_bar, n_bars, _ = h.strategy.calls[0]
    assert (symbol, last_bar, n_bars) == ("AAA", LAST_CLOSED, LOOKBACK)
    assert h.state().last_signal_bar["AAA"] == LAST_CLOSED.isoformat()


def test_feed_without_forming_bar_still_gets_lookback_closed_bars(tmp_path):
    h = make_harness(tmp_path, include_forming=False)
    h.tick()
    _, last_bar, n_bars, _ = h.strategy.calls[0]
    assert last_bar == LAST_CLOSED and n_bars == LOOKBACK


def test_bar_closing_exactly_now_counts_as_closed(tmp_path):
    h = make_harness(tmp_path)
    h.clock.now = datetime(2026, 9, 24, 14, 0, tzinfo=timezone.utc)
    h.tick()
    assert h.strategy.calls[0][1] == LAST_CLOSED


def test_same_closed_bar_is_not_evaluated_twice(tmp_path):
    h = make_harness(tmp_path, actions={"AAA": Action.BUY})
    first = h.tick()
    h.clock.advance(minutes=20)  # still inside the 14:00 bar
    second = h.tick()

    assert h.strategy.symbols_called() == ["AAA", "BBB"]
    assert len(first.orders) == 1 and second.orders == []
    assert "already evaluated" in second.signals["BBB"]

    h.clock.advance(minutes=20)  # 15:10: the 14:00 bar has closed
    h.tick()
    assert h.strategy.symbols_called() == ["AAA", "BBB", "AAA", "BBB"]
    assert h.strategy.calls[-1][1] == LAST_CLOSED + pd.Timedelta(hours=1)


def test_warming_up_symbol_is_skipped_without_marking(tmp_path):
    h = make_harness(tmp_path, min_bars=LOOKBACK + 5)
    report = h.tick()
    assert h.strategy.calls == []
    assert report.signals["AAA"].startswith("warming up")
    assert report.errors == [] and h.state().last_signal_bar == {}


def test_strategy_gets_position_marked_to_latest_price(tmp_path):
    h = make_harness(tmp_path, risk=RiskConfig(stop_loss_pct=None))
    h.buy("AAA", 5)
    h.feed.prices["AAA"] = 104.0
    h.tick()
    position = h.strategy.calls[0][3]
    assert position.symbol == "AAA" and position.qty == 5 and position.market_price == 104.0


def test_sell_signal_when_flat_and_buy_signal_when_long_do_nothing(tmp_path):
    h = make_harness(tmp_path, actions={"AAA": Action.SELL, "BBB": Action.BUY},
                     risk=RiskConfig(stop_loss_pct=None))
    h.buy("BBB", 10)
    report = h.tick()
    assert report.orders == [] and report.errors == []
    assert h.broker.get_positions()["BBB"].qty == 10
    assert set(h.state().last_signal_bar) == {"AAA", "BBB"}


def test_strategy_sell_exits_whole_position(tmp_path):
    h = make_harness(tmp_path, actions={"AAA": Action.SELL}, risk=RiskConfig(stop_loss_pct=None))
    h.buy("AAA", 7.5)
    report = h.tick()
    assert statuses(report) == [("AAA", "sell", "filled")]
    assert report.orders[0].qty == 7.5
    assert h.broker.get_positions() == {}


# --------------------------------------------------------------------------- protective exits


def test_stop_loss_is_checked_every_tick_even_after_bar_was_evaluated(tmp_path):
    h = make_harness(tmp_path, actions={"AAA": Action.BUY}, risk=RiskConfig(stop_loss_pct=5.0))
    first = h.tick()
    assert statuses(first) == [("AAA", "buy", "filled")]
    calls_after_first = len(h.strategy.calls)

    h.clock.advance(minutes=5)
    h.feed.prices["AAA"] = 94.0  # below the 95 stop
    second = h.tick()

    assert statuses(second) == [("AAA", "sell", "filled")]
    assert second.orders[0].reason == "stop_loss"
    assert second.signals["AAA"].startswith("sell: stop_loss")
    assert len(h.strategy.calls) == calls_after_first  # no strategy re-evaluation needed
    assert h.broker.get_positions() == {}


def test_price_above_stop_keeps_position(tmp_path):
    h = make_harness(tmp_path, actions={"AAA": Action.BUY}, risk=RiskConfig(stop_loss_pct=5.0))
    h.tick()
    h.clock.advance(minutes=5)
    h.feed.prices["AAA"] = 95.5
    assert h.tick().orders == []
    assert "AAA" in h.broker.get_positions()


def test_take_profit_exit(tmp_path):
    h = make_harness(tmp_path, risk=RiskConfig(stop_loss_pct=None, take_profit_pct=10.0))
    h.buy("AAA", 10)
    h.feed.prices["AAA"] = 111.0
    report = h.tick()
    assert statuses(report) == [("AAA", "sell", "filled")]
    assert report.orders[0].reason == "take_profit"


def test_no_reentry_on_the_same_bar_after_a_stop_out(tmp_path):
    h = make_harness(tmp_path, actions={"AAA": Action.BUY}, risk=RiskConfig(stop_loss_pct=5.0))
    h.buy("AAA", 10)  # bought outside the engine: the 13:00 bar is not evaluated yet
    h.feed.prices["AAA"] = 90.0
    stop = h.tick()
    assert statuses(stop) == [("AAA", "sell", "filled")]

    h.clock.advance(minutes=5)
    assert h.tick().orders == []  # the scripted BUY waits for the next closed bar

    h.clock.advance(hours=1)
    assert statuses(h.tick()) == [("AAA", "buy", "filled")]


def test_stop_exit_with_quantity_rounding_to_zero_sends_nothing(tmp_path):
    h = make_harness(tmp_path, risk=RiskConfig(stop_loss_pct=5.0))
    h.buy("AAA", 0.5)
    h.feed.prices["AAA"] = 50.0
    h.broker.normalize_qty = lambda symbol, qty: float(math.floor(qty))  # whole units only

    report = h.tick()

    assert report.orders == [] and report.errors == []
    assert "rounds down to 0" in report.signals["AAA"]


def test_sell_never_exceeds_the_held_quantity(tmp_path):
    h = make_harness(tmp_path, actions={"AAA": Action.SELL}, risk=RiskConfig(stop_loss_pct=None))
    h.buy("AAA", 3)
    h.broker.normalize_qty = lambda symbol, qty: qty * 2  # a buggy venue rule rounding UP
    submitted: list[OrderRequest] = []
    real_submit = h.broker.submit_order
    h.broker.submit_order = lambda order: submitted.append(order) or real_submit(order)

    h.tick()

    assert [o.qty for o in submitted] == [3]


# --------------------------------------------------------------------------- entries


def test_buy_is_sized_by_risk_manager_and_counted(tmp_path):
    h = make_harness(tmp_path, actions={"AAA": Action.BUY})  # defaults: 1% risk / 5% stop -> 20% of equity
    report = h.tick()
    assert statuses(report) == [("AAA", "buy", "filled")]
    assert report.orders[0].filled_qty == pytest.approx(20.0)
    assert h.state().trades_today == 1
    assert len(h.notifier.trades) == 1 and "BUY" in h.notifier.trades[0]


def test_entry_quantity_is_rounded_down_and_never_above_sized(tmp_path):
    h = make_harness(tmp_path, actions={"AAA": Action.BUY})
    h.broker.normalize_qty = lambda symbol, qty: qty * 1.5  # a buggy rule rounding UP
    report = h.tick()
    assert report.orders[0].qty == pytest.approx(20.0)


def test_entry_rounds_down_to_whole_units(tmp_path):
    h = make_harness(tmp_path, prices={"AAA": 30.0}, actions={"AAA": Action.BUY})
    h.broker.normalize_qty = lambda symbol, qty: float(math.floor(qty))  # 2000 / 30 = 66.67 -> 66
    report = h.tick()
    assert report.orders[0].qty == 66.0
    assert "rounded down to 66" in report.signals["AAA"]


def test_entry_that_rounds_below_minimum_is_skipped(tmp_path):
    h = make_harness(tmp_path, prices={"AAA": 3_000.0}, actions={"AAA": Action.BUY})
    h.broker.normalize_qty = lambda symbol, qty: float(math.floor(qty))  # 0.67 shares -> 0

    report = h.tick()

    assert report.orders == [] and report.errors == []
    assert "rounds down" in report.signals["AAA"]
    assert h.state().trades_today == 0
    assert "AAA" in h.state().last_signal_bar


def test_entry_rejected_by_risk_manager_is_explained(tmp_path):
    h = make_harness(tmp_path, actions={"BBB": Action.BUY}, risk=RiskConfig(max_open_positions=1))
    h.buy("AAA", 1)
    report = h.tick()
    assert report.orders == []
    assert "max open positions" in report.signals["BBB"]


def test_max_trades_per_day_blocks_further_entries_until_tomorrow(tmp_path):
    h = make_harness(tmp_path, actions={"AAA": Action.BUY, "BBB": Action.BUY},
                     risk=RiskConfig(max_trades_per_day=1))
    report = h.tick()
    assert statuses(report) == [("AAA", "buy", "filled")]
    assert "max trades per day" in report.signals["BBB"]
    assert h.state().trades_today == 1

    h.clock.advance(days=1)
    tomorrow = h.tick()
    assert statuses(tomorrow) == [("BBB", "buy", "filled")]
    assert h.state().trades_today == 1


def test_rejected_buy_does_not_count_as_a_trade(tmp_path):
    h = make_harness(tmp_path, actions={"AAA": Action.BUY})
    h.broker.submit_order = lambda order: OrderResult("x-1", order.symbol, order.side, order.qty,
                                                      "rejected", reason="insufficient buying power")
    report = h.tick()
    assert statuses(report) == [("AAA", "buy", "rejected")]
    assert h.state().trades_today == 0
    assert report.errors == []
    assert any("Order rejected" in m and "insufficient buying power" in m for m in h.notifier.errors)


def test_account_is_refreshed_between_symbols_so_two_buys_cannot_overspend(tmp_path):
    risk = RiskConfig(max_position_pct=60, max_total_exposure_pct=100, stop_loss_pct=None,
                      cash_buffer_pct=0, max_daily_loss_pct=None)
    h = make_harness(tmp_path, actions={"AAA": Action.BUY, "BBB": Action.BUY}, risk=risk)
    account_calls = []
    real = h.broker.get_account
    h.broker.get_account = lambda: account_calls.append(1) or real()

    report = h.tick()

    # Stale sizing would have tried 6000 for BBB too and been rejected.
    assert statuses(report) == [("AAA", "buy", "filled"), ("BBB", "buy", "filled")]
    assert report.orders[0].filled_qty * 100.0 == pytest.approx(6_000.0)
    assert report.orders[1].filled_qty * 50.0 == pytest.approx(4_000.0)
    assert 0.0 <= h.broker.cash < 1e-6
    assert len(account_calls) >= 3  # initial read + one refresh per order


def test_second_buy_is_skipped_when_first_used_all_cash(tmp_path):
    risk = RiskConfig(max_position_pct=100, max_total_exposure_pct=100, stop_loss_pct=None,
                      cash_buffer_pct=0, max_daily_loss_pct=None)
    h = make_harness(tmp_path, actions={"AAA": Action.BUY, "BBB": Action.BUY}, risk=risk)
    report = h.tick()
    assert statuses(report) == [("AAA", "buy", "filled")]
    assert "BBB" in report.signals and "not entering" in report.signals["BBB"]
    assert h.broker.cash >= 0.0


def test_client_order_ids_are_attached_and_unique(tmp_path):
    h = make_harness(tmp_path, actions={"AAA": Action.BUY, "BBB": Action.BUY})
    h.tick()
    ids = [fill["client_order_id"] for fill in h.broker.fills]
    assert ids[0].startswith("bot-AAA-buy-202609241300-")
    assert ids[1].startswith("bot-BBB-buy-202609241300-")
    assert len(set(ids)) == 2


def test_make_client_order_id_format():
    bar_key = "2026-09-24T13:00:00+00:00"
    first = make_client_order_id("BTC/USDT", Side.SELL, bar_key)
    second = make_client_order_id("BTC/USDT", Side.SELL, bar_key)
    assert first.startswith("bot-BTCUSDT-sell-202609241300-")
    assert first != second
    long_one = make_client_order_id("X" * 100, Side.BUY, bar_key)
    base, _, suffix = long_one.rpartition("-")
    assert len(base) == 48 and len(suffix) == 8


# --------------------------------------------------------------------------- pending orders


def test_symbol_with_open_order_is_skipped_entirely(tmp_path):
    h = make_harness(tmp_path, actions={"AAA": Action.BUY, "BBB": Action.BUY})
    h.broker.has_open_orders = lambda symbol: symbol == "AAA"

    report = h.tick()

    assert statuses(report) == [("BBB", "buy", "filled")]
    assert "pending" in report.signals["AAA"]
    assert [c[0] for c in h.feed.bars_calls] == ["BBB"]
    assert "AAA" not in h.state().last_signal_bar


def test_pending_order_also_defers_stop_loss_exit(tmp_path):
    h = make_harness(tmp_path, risk=RiskConfig(stop_loss_pct=5.0))
    h.buy("AAA", 10)
    h.feed.prices["AAA"] = 80.0
    h.broker.has_open_orders = lambda symbol: symbol == "AAA"
    assert h.tick().orders == []
    h.broker.has_open_orders = lambda symbol: False
    assert statuses(h.tick()) == [("AAA", "sell", "filled")]


# --------------------------------------------------------------------------- errors


def test_one_failing_symbol_does_not_block_others_and_is_retried(tmp_path):
    h = make_harness(tmp_path, actions={"AAA": Action.BUY, "BBB": Action.BUY})
    h.feed.fail_bars["AAA"] = RuntimeError("feed hiccup")

    first = h.tick()

    assert statuses(first) == [("BBB", "buy", "filled")]
    assert len(first.errors) == 1 and first.errors[0].startswith("AAA:")
    state = h.state()
    assert "AAA" not in state.last_signal_bar and "BBB" in state.last_signal_bar
    assert state.consecutive_errors == 1

    del h.feed.fail_bars["AAA"]
    h.clock.advance(minutes=5)  # same bar
    second = h.tick()

    assert statuses(second) == [("AAA", "buy", "filled")]
    assert h.strategy.symbols_called() == ["BBB", "AAA"]  # BBB's bar is not re-evaluated
    assert second.errors == [] and h.state().consecutive_errors == 0


def test_strategy_exception_is_recorded_per_symbol(tmp_path):
    h = make_harness(tmp_path, actions={"BBB": Action.BUY})
    h.strategy.fail["AAA"] = ValueError("bad indicator")
    report = h.tick()
    assert statuses(report) == [("BBB", "buy", "filled")]
    assert report.errors == ["AAA: ValueError: bad indicator"]
    assert "AAA" not in h.state().last_signal_bar


def test_price_failure_during_entry_is_retried_next_tick(tmp_path):
    h = make_harness(tmp_path, actions={"AAA": Action.BUY})
    h.feed.fail_price["AAA"] = RuntimeError("no quote")
    report = h.tick()
    assert report.orders == [] and len(report.errors) == 1
    assert "AAA" not in h.state().last_signal_bar

    del h.feed.fail_price["AAA"]
    assert statuses(h.tick()) == [("AAA", "buy", "filled")]


def test_broker_error_from_get_account_is_recorded_not_raised(tmp_path):
    h = make_harness(tmp_path, actions={"AAA": Action.BUY})
    real = h.broker.get_account
    h.broker.get_account = Mock(side_effect=BrokerError("alpaca: 503 service unavailable"))

    first = h.tick()
    assert first.errors == ["alpaca: 503 service unavailable"]
    assert first.orders == [] and h.strategy.calls == []
    assert first.equity is None
    assert h.state().consecutive_errors == 1
    assert h.notifier.errors == ["alpaca: 503 service unavailable"]

    h.tick()
    assert h.state().consecutive_errors == 2
    assert len(h.notifier.errors) == 1  # the same error is not re-notified every tick

    h.broker.get_account = real
    assert h.tick().errors == []
    assert h.state().consecutive_errors == 0


def test_unexpected_exception_from_broker_is_recorded_with_type(tmp_path):
    h = make_harness(tmp_path)
    h.broker.is_market_open = Mock(side_effect=ConnectionResetError("peer reset"))
    report = h.tick()
    assert report.errors == ["ConnectionResetError: peer reset"]


def test_refresh_failure_after_an_order_blocks_further_entries_this_tick(tmp_path):
    h = make_harness(tmp_path, actions={"AAA": Action.BUY, "BBB": Action.BUY})
    real = h.broker.get_account
    calls = {"n": 0}

    def flaky_account() -> Account:
        calls["n"] += 1
        if calls["n"] == 2:  # the refresh right after AAA's order
            raise BrokerError("account endpoint timeout")
        return real()

    h.broker.get_account = flaky_account
    first = h.tick()

    assert statuses(first) == [("AAA", "buy", "filled")]
    assert any("could not refresh" in e for e in first.errors)
    assert "not entering this tick" in first.signals["BBB"]
    state = h.state()
    assert "AAA" in state.last_signal_bar and "BBB" not in state.last_signal_bar
    assert state.trades_today == 1

    h.clock.advance(minutes=5)
    second = h.tick()
    assert statuses(second) == [("BBB", "buy", "filled")]  # no duplicate AAA buy
    assert h.state().trades_today == 2


def test_order_submission_failure_is_retried_and_blocks_other_entries(tmp_path):
    h = make_harness(tmp_path, actions={"AAA": Action.BUY, "BBB": Action.BUY})
    real_submit = h.broker.submit_order
    h.broker.submit_order = Mock(side_effect=BrokerError("connection dropped"))

    first = h.tick()

    assert first.orders == []
    assert first.errors == ["AAA: connection dropped"]
    assert "not entering this tick" in first.signals["BBB"]
    assert h.state().last_signal_bar == {} and h.state().trades_today == 0

    h.broker.submit_order = real_submit
    second = h.tick()
    assert statuses(second) == [("AAA", "buy", "filled"), ("BBB", "buy", "filled")]


def test_exits_still_run_after_a_failed_submission(tmp_path):
    h = make_harness(tmp_path, actions={"AAA": Action.BUY, "BBB": Action.SELL},
                     risk=RiskConfig(stop_loss_pct=None))
    h.buy("BBB", 10)
    real_submit = h.broker.submit_order

    def submit(order: OrderRequest) -> OrderResult:
        if order.symbol == "AAA":
            raise BrokerError("gateway error")
        return real_submit(order)

    h.broker.submit_order = submit
    report = h.tick()
    assert statuses(report) == [("BBB", "sell", "filled")]


def test_state_save_failure_is_reported(tmp_path):
    h = make_harness(tmp_path)
    h.store.save = Mock(side_effect=OSError("disk full"))
    report = h.tick()
    assert any("could not save bot state" in e for e in report.errors)


def test_state_load_failure_means_no_trading(tmp_path):
    broker = Mock(spec=Broker)
    h = make_harness(tmp_path, broker=broker)
    h.store.load = Mock(side_effect=PermissionError("denied"))
    report = h.tick()
    assert broker.mock_calls == []
    assert any("could not load bot state" in e for e in report.errors)


# --------------------------------------------------------------------------- trade log


def test_trades_csv_has_header_once_and_one_row_per_order(tmp_path):
    h = make_harness(tmp_path, actions={"AAA": Action.BUY}, risk=RiskConfig(stop_loss_pct=None))
    h.tick()
    h.clock.advance(hours=1)
    h.strategy.actions["AAA"] = Action.SELL
    h.tick()

    path = h.cfg.log_dir / "trades.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == ",".join(TRADE_COLUMNS)
    assert sum(line.startswith("time,") for line in lines) == 1
    rows = read_trades(h)
    assert [(r["symbol"], r["side"], r["status"]) for r in rows] == [("AAA", "buy", "filled"),
                                                                      ("AAA", "sell", "filled")]
    buy = rows[0]
    assert buy["mode"] == "paper" and buy["order_id"] == "paper-1"
    assert float(buy["qty"]) == pytest.approx(20.0) and float(buy["filled_avg_price"]) == pytest.approx(100.0)
    assert buy["reason"] == "scripted buy"
    assert buy["client_order_id"].startswith("bot-AAA-buy-")


def test_rejected_orders_are_logged_to_trades_csv(tmp_path):
    h = make_harness(tmp_path, actions={"AAA": Action.BUY})
    h.broker.submit_order = lambda order: OrderResult("r-1", order.symbol, order.side, order.qty,
                                                      "rejected", reason="market halted")
    h.tick()
    row = read_trades(h)[0]
    assert row["status"] == "rejected" and row["filled_avg_price"] == ""
    assert "market halted" in row["reason"]


def test_unwritable_trade_log_is_an_error_but_the_order_still_counts(tmp_path):
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("x")
    h = make_harness(tmp_path, actions={"AAA": Action.BUY}, log_dir=blocker / "logs")
    report = h.tick()
    assert statuses(report) == [("AAA", "buy", "filled")]
    assert any("could not write" in e for e in report.errors)
    assert h.state().trades_today == 1 and "AAA" in h.state().last_signal_bar


# --------------------------------------------------------------------------- run_forever


def test_run_forever_returns_immediately_when_stop_already_set(tmp_path):
    h = make_harness(tmp_path)
    h.engine.run_once = Mock()
    stop = threading.Event()
    stop.set()
    h.engine.run_forever(stop_event=stop)
    h.engine.run_once.assert_not_called()


def test_run_forever_waits_poll_interval_between_ticks_and_honours_max_ticks(tmp_path):
    h = make_harness(tmp_path)
    stop = RecordingEvent()
    h.engine.run_forever(stop_event=stop, max_ticks=3)
    assert stop.waits == [POLL, POLL]
    assert h.state().last_tick_at is not None


def test_run_forever_stops_when_event_is_set_during_wait(tmp_path):
    h = make_harness(tmp_path)
    h.engine.run_once = Mock(return_value=TickReport(started_at=T0))
    stop = RecordingEvent(stop_after=2)
    h.engine.run_forever(stop_event=stop)
    assert h.engine.run_once.call_count == 2


def test_run_forever_backs_off_on_consecutive_errors_and_alerts(tmp_path):
    h = make_harness(tmp_path)
    failing = TickReport(started_at=T0, errors=["boom"])
    h.engine.run_once = Mock(return_value=failing)
    stop = RecordingEvent()

    h.engine.run_forever(stop_event=stop, max_ticks=14)

    assert stop.waits[:6] == [60, 120, 240, 480, 900, 900]
    assert max(stop.waits) == MAX_BACKOFF_SECONDS
    alerts = [m for m in h.notifier.errors if "ticks in a row" in m]
    assert [a.split()[0] for a in alerts] == ["3", "13"]


def test_run_forever_survives_unexpected_exceptions_and_recovers(tmp_path):
    h = make_harness(tmp_path)
    ok = TickReport(started_at=T0)
    h.engine.run_once = Mock(side_effect=[KeyError("bug"), KeyError("bug"), ok, ok])
    stop = RecordingEvent()

    h.engine.run_forever(stop_event=stop, max_ticks=4)

    assert h.engine.run_once.call_count == 4
    assert stop.waits == [60, 120, 60]
    assert sum("unexpected error" in m for m in h.notifier.errors) == 1  # same bug notified once


@pytest.mark.parametrize(("poll", "errors", "expected"), [
    (300, 0, 300), (300, 1, 300), (300, 2, 600), (300, 3, 900), (300, 50, 900),
    (60, 5, 900), (60, 4, 480), (3600, 1, 900), (30, 10_000, 900),
])
def test_backoff_seconds(poll, errors, expected):
    assert backoff_seconds(poll, errors) == expected


# --------------------------------------------------------------------------- end to end


def test_end_to_end_with_synthetic_feed_and_real_strategy(tmp_path):
    clock = Clock(datetime(2026, 3, 2, 0, 30, tzinfo=timezone.utc))
    broker = PaperBroker(SyntheticFeed(seed=7, clock=clock), starting_cash=10_000.0, clock=clock)
    risk = RiskConfig(max_daily_loss_pct=None)
    cfg = BotConfig(symbols=["DEMO1", "DEMO2"], timeframe="1h", bars_lookback=40, timezone="UTC",
                    poll_interval_seconds=POLL, risk=risk, state_dir=tmp_path / "state",
                    log_dir=tmp_path / "logs")
    engine = TradingEngine(cfg, broker, create_strategy("sma_crossover", {"fast": 3, "slow": 8}),
                           RiskManager(risk), StateStore(cfg.state_dir / STATE_FILE),
                           RecordingNotifier(), clock=clock)
    orders = []
    for _ in range(96):
        report = engine.run_once()
        assert report.errors == [], report.errors
        assert broker.cash >= 0.0
        assert all(o.ok for o in report.orders)
        orders += report.orders
        clock.advance(minutes=30)

    assert orders, "the strategy should trade at least once over 48 hours of hourly bars"
    assert len(read_trades_at(cfg.log_dir)) == len(orders)
    state = json.loads((cfg.state_dir / STATE_FILE).read_text())
    assert set(state["last_signal_bar"]) == {"DEMO1", "DEMO2"}
    for pos in broker.get_positions().values():
        assert pos.qty > 0


def read_trades_at(log_dir: Path) -> list[dict[str, str]]:
    with (log_dir / "trades.csv").open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))
