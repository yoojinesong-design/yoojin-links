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

from bot.brokers.base import Broker, BrokerError, OpenOrder
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
        self.max_bars: int | None = None  # a venue that serves only this much history

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
        if self.max_bars is not None:
            limit = min(limit, self.max_bars)
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
                 broker: Broker | None = None, shared_account: bool = False,
                 **cfg_overrides: object) -> Harness:
    """``shared_account``: the paper broker stands in for a real brokerage
    account, which can hold things the bot did not buy (``h.buy`` then plays
    the user trading by hand). By default it is the bot's own paper account,
    where the bot manages every holding."""
    clock = Clock(T0)
    feed = FakeFeed(clock, prices or {"AAA": 100.0, "BBB": 50.0}, include_forming=include_forming)
    paper = PaperBroker(feed, starting_cash=10_000.0, fee_pct=0.0, slippage_pct=0.0, clock=clock)
    paper.bot_owned_account = not shared_account
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
    real = h.broker.submit_order
    h.broker.submit_order = Mock(side_effect=BrokerError("exchange timeout"))

    first = h.tick()
    assert any("flatten" in e and "exchange timeout" in e for e in first.errors)
    assert "AAA" in h.broker.get_positions()

    h.broker.submit_order = real
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


def own_order(symbol: str, side: Side = Side.BUY) -> OpenOrder:
    return OpenOrder("bot-order-1", symbol, side, placed_by_bot=True)


def manual_order(symbol: str, side: Side = Side.BUY) -> OpenOrder:
    return OpenOrder("manual-1", symbol, side, placed_by_bot=False)


def test_symbol_with_the_bots_own_open_order_is_skipped_entirely(tmp_path):
    h = make_harness(tmp_path, actions={"AAA": Action.BUY, "BBB": Action.BUY})
    h.broker.open_orders = lambda symbol: [own_order(symbol)] if symbol == "AAA" else []

    report = h.tick()

    assert statuses(report) == [("BBB", "buy", "filled")]
    assert "pending" in report.signals["AAA"]
    assert [c[0] for c in h.feed.bars_calls] == ["BBB"]
    assert "AAA" not in h.state().last_signal_bar


def test_stop_loss_is_not_duplicated_while_the_bots_own_sell_is_working(tmp_path):
    h = make_harness(tmp_path, risk=RiskConfig(stop_loss_pct=5.0))
    h.buy("AAA", 10)
    h.feed.prices["AAA"] = 80.0
    h.broker.open_orders = lambda symbol: [own_order(symbol, Side.SELL)] if symbol == "AAA" else []
    report = h.tick()
    assert report.orders == []
    assert "already working" in report.signals["AAA"]
    h.broker.open_orders = lambda symbol: []
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


def test_a_failing_state_save_does_not_back_off_the_stop_loss_checks(tmp_path):
    # A full local disk says nothing about the broker API: every tick's broker
    # calls worked, so the stop-losses keep being checked every poll interval.
    h = make_harness(tmp_path, risk=RiskConfig(stop_loss_pct=10.0))
    h.buy("AAA", 10)
    h.store.save = Mock(side_effect=OSError(28, "No space left on device"))
    stop = RecordingEvent()
    h.engine.run_forever(stop_event=stop, max_ticks=5)
    assert stop.waits == [POLL] * 4


def test_state_that_cannot_be_saved_blocks_entries_before_any_order_even_in_a_fresh_process(tmp_path):
    # `once` from cron: a new engine per run, the disk is full. The state is
    # saved BEFORE trading, so no run buys, and the stop-loss still sells.
    clock = Clock(T0)
    feed = FakeFeed(clock, {"AAA": 100.0})
    broker = PaperBroker(feed, starting_cash=10_000.0, fee_pct=0.0, slippage_pct=0.0, clock=clock)
    broker.submit_order(OrderRequest("AAA", Side.BUY, 10))
    orders = []
    for price in (100.0, 90.0, 90.0, 81.0):  # all within one 1h bar
        feed.prices["AAA"] = price
        h = make_harness(tmp_path, prices={"AAA": 100.0}, actions={"AAA": Action.BUY}, broker=broker,
                         risk=RiskConfig(stop_loss_pct=8.0, max_trades_per_day=1))
        h.engine.clock = clock
        h.store.save = Mock(side_effect=OSError(28, "No space left on device"))
        report = h.tick()
        orders += [(o.side.value, o.status) for o in report.orders]
        assert any("could not save bot state" in e for e in report.errors)
        clock.advance(minutes=5)

    assert orders == [("sell", "filled")]  # the stop-out, and no buy in any run


def test_unreadable_state_blocks_entries_but_stop_losses_still_run(tmp_path):
    # e.g. bot_state.json rewritten 0600 by a `sudo ... once` run: the counters
    # are unknown, so no new entries, but the stop-loss must not be switched off.
    h = make_harness(tmp_path, actions={"BBB": Action.BUY}, risk=RiskConfig(stop_loss_pct=5.0))
    h.buy("AAA", 10)
    h.feed.prices["AAA"] = 50.0  # -50%
    h.store.load = Mock(side_effect=PermissionError(13, "Permission denied", "bot_state.json"))
    h.store.save = Mock(wraps=h.store.save)

    report = h.tick()

    assert statuses(report) == [("AAA", "sell", "filled")]
    assert "could not be read" in report.signals["BBB"]
    assert any("could not load bot state" in e and "Permission denied" in e for e in report.errors)
    h.store.save.assert_not_called()  # never overwrite the unreadable file
    assert report.failed is False


def test_unreadable_state_does_not_slow_down_the_stop_loss_checks(tmp_path):
    h = make_harness(tmp_path, risk=RiskConfig(stop_loss_pct=10.0))
    h.buy("AAA", 10)
    h.store.load = Mock(side_effect=PermissionError(13, "Permission denied"))
    stop = RecordingEvent()
    h.engine.run_forever(stop_event=stop, max_ticks=5)
    assert stop.waits == [POLL] * 4


def test_unreadable_state_later_in_a_run_keeps_what_the_bot_knew(tmp_path):
    h = make_harness(tmp_path, actions={"AAA": Action.BUY}, risk=RiskConfig(max_trades_per_day=1))
    h.tick()
    assert h.state().trades_today == 1
    h.store.load = Mock(side_effect=PermissionError(13, "Permission denied"))
    h.clock.advance(minutes=5)
    report = h.tick()
    assert report.orders == []
    assert h.engine._last_state.trades_today == 1


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
    failing = TickReport(started_at=T0, errors=["boom"], failed=True)
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


# --------------------------------------------------------------------------- regression: review findings


class AcceptingBroker(Broker):
    """Alpaca-like broker: a BUY is acknowledged as "accepted" and fills only
    when ``settle()`` runs, so until then positions and cash are unchanged and
    only buying power drops by the order's value (Alpaca reserves it)."""

    name = "accepting"

    def __init__(self, feed: FakeFeed, cash: float, buying_power: float | None = None,
                 holdings: dict[str, float] | None = None) -> None:
        self.feed = feed
        self.cash = cash
        self.base_buying_power = cash if buying_power is None else buying_power
        self.holdings = dict(holdings or {})  # symbol -> qty
        self.entries: dict[str, float] = {}   # symbol -> fill price (else the feed price)
        self.pending: list[OrderRequest] = []
        self.orders: list[OrderRequest] = []

    def get_bars(self, symbol, timeframe, limit):
        return self.feed.get_bars(symbol, timeframe, limit)

    def get_latest_price(self, symbol):
        return self.feed.get_latest_price(symbol)

    def get_account(self) -> Account:
        held = sum(qty * self.feed.prices[s] for s, qty in self.holdings.items())
        reserved = sum(o.qty * self.feed.prices[o.symbol] for o in self.pending)
        return Account(equity=self.cash + held, cash=self.cash,
                       buying_power=max(0.0, self.base_buying_power - reserved))

    def get_positions(self) -> dict[str, Position]:
        return {s: Position(s, qty, self.entries.get(s, self.feed.prices[s]), self.feed.prices[s])
                for s, qty in self.holdings.items() if qty > 0}

    def open_orders(self, symbol):
        return [OpenOrder(f"a-{i}", o.symbol, o.side, placed_by_bot=True)
                for i, o in enumerate(self.pending) if o.symbol == symbol]

    def submit_order(self, order: OrderRequest) -> OrderResult:
        self.orders.append(order)
        self.pending.append(order)
        return OrderResult(f"a-{len(self.orders)}", order.symbol, order.side, order.qty, "accepted")

    def cancel_all_orders(self):
        self.pending.clear()

    def settle(self) -> None:
        """The pending orders fill at the current feed price."""
        for order in self.pending:
            price, held = self.feed.prices[order.symbol], self.holdings.get(order.symbol, 0.0)
            if order.side is Side.BUY:
                self.entries[order.symbol] = (held * self.entries.get(order.symbol, price)
                                              + order.qty * price) / (held + order.qty)
                self.holdings[order.symbol], self.cash = held + order.qty, self.cash - order.qty * price
            else:
                qty = min(order.qty, held)
                self.holdings[order.symbol], self.cash = held - qty, self.cash + qty * price
        self.pending.clear()

    def buys(self) -> list[OrderRequest]:
        return [o for o in self.orders if o.side is Side.BUY]


def test_accepted_but_unfilled_buys_count_toward_position_and_exposure_caps(tmp_path):
    # Four BUY signals on one tick; the broker acks each BUY as "accepted" and
    # the fill lands after the tick (normal for Alpaca market orders).
    prices = {"AAA": 100.0, "BBB": 100.0, "CCC": 100.0, "DDD": 100.0}
    risk = RiskConfig(max_open_positions=2, max_total_exposure_pct=40, max_position_pct=20,
                      stop_loss_pct=None, cash_buffer_pct=0, max_daily_loss_pct=None)
    feed = FakeFeed(Clock(T0), prices)
    broker = AcceptingBroker(feed, cash=10_000.0)
    h = make_harness(tmp_path, prices=prices, actions={s: Action.BUY for s in prices}, risk=risk, broker=broker)
    h.engine.broker.feed = h.feed  # share the harness feed (and its clock)

    report = h.tick()

    assert [o.symbol for o in broker.buys()] == ["AAA", "BBB"]
    assert "max open positions" in report.signals["CCC"]
    assert sum(o.qty * prices[o.symbol] for o in broker.buys()) <= 0.4 * 10_000.0 + 1e-6


def test_accepted_buys_cannot_add_up_to_more_than_the_cash_on_a_margin_account(tmp_path):
    # Holding $6k of AAA with $4k cash; margin buying power ($7k) exceeds cash.
    # Alpaca's cash only drops on the fill, so each BUY alone looks affordable.
    prices = {"AAA": 100.0, "BBB": 100.0, "CCC": 100.0}
    risk = RiskConfig(max_open_positions=5, max_total_exposure_pct=100, max_position_pct=25,
                      stop_loss_pct=None, cash_buffer_pct=0, max_daily_loss_pct=None)
    feed = FakeFeed(Clock(T0), prices)
    broker = AcceptingBroker(feed, cash=4_000.0, buying_power=7_000.0, holdings={"AAA": 60.0})
    h = make_harness(tmp_path, prices=prices, actions={"BBB": Action.BUY, "CCC": Action.BUY}, risk=risk,
                     broker=broker)
    h.engine.broker.feed = h.feed

    h.tick()

    spent = sum(o.qty * prices[o.symbol] for o in broker.buys())
    assert [o.symbol for o in broker.buys()] == ["BBB", "CCC"]
    assert spent <= 4_000.0 + 1e-6  # never more than the cash: no borrowing on margin


def test_stop_loss_still_fires_while_an_order_not_placed_by_the_bot_is_open(tmp_path):
    h = make_harness(tmp_path, risk=RiskConfig(stop_loss_pct=5.0))
    h.buy("AAA", 10)
    h.feed.prices["AAA"] = 50.0  # -50%
    h.broker.open_orders = lambda symbol: [manual_order(symbol)] if symbol == "AAA" else []

    report = h.tick()

    assert statuses(report) == [("AAA", "sell", "filled")]
    assert report.orders[0].reason == "stop_loss"
    assert any("not placed by this bot" in m and "AAA" in m for m in h.notifier.errors)


def test_stop_loss_blocked_by_a_manual_order_is_reported_as_an_error(tmp_path):
    h = make_harness(tmp_path, risk=RiskConfig(stop_loss_pct=5.0))
    h.buy("AAA", 10)
    h.feed.prices["AAA"] = 50.0
    h.broker.open_orders = lambda symbol: [manual_order(symbol, Side.SELL)] if symbol == "AAA" else []
    h.broker.submit_order = lambda order: OrderResult("", order.symbol, order.side, order.qty, "rejected",
                                                      reason="no AAA available to sell")
    report = h.tick()

    assert statuses(report) == [("AAA", "sell", "rejected")]
    assert any(e.startswith("AAA:") and "not placed by this bot" in e for e in report.errors)


def test_manual_order_blocks_new_entries_but_not_strategy_exits(tmp_path):
    h = make_harness(tmp_path, actions={"AAA": Action.BUY, "BBB": Action.SELL},
                     risk=RiskConfig(stop_loss_pct=None))
    h.buy("BBB", 10)
    h.broker.open_orders = lambda symbol: [manual_order(symbol)]

    report = h.tick()

    assert statuses(report) == [("BBB", "sell", "filled")]
    assert "not placed by this bot" in report.signals["AAA"]
    assert "AAA" not in h.state().last_signal_bar  # re-checked next tick


def test_stop_loss_fires_even_when_bars_cannot_be_loaded(tmp_path):
    h = make_harness(tmp_path, actions={"AAA": Action.BUY}, risk=RiskConfig(stop_loss_pct=5.0))
    h.buy("AAA", 10)
    h.feed.prices["AAA"] = 50.0
    h.feed.fail_bars["AAA"] = BrokerError("candles endpoint 503")

    report = h.tick()

    assert statuses(report) == [("AAA", "sell", "filled")]
    assert report.errors == ["AAA: candles endpoint 503"]

    # Bars come back within the same bar: no re-entry on the bar the stop hit in.
    del h.feed.fail_bars["AAA"]
    h.clock.advance(minutes=5)
    assert h.tick().orders == []
    h.clock.advance(hours=1)
    assert statuses(h.tick()) == [("AAA", "buy", "filled")]


def test_stop_loss_fires_while_the_strategy_is_still_warming_up(tmp_path):
    h = make_harness(tmp_path, min_bars=LOOKBACK + 5, risk=RiskConfig(stop_loss_pct=5.0))
    h.buy("AAA", 10)
    h.feed.prices["AAA"] = 50.0
    report = h.tick()
    assert statuses(report) == [("AAA", "sell", "filled")]
    assert report.errors == []


def test_stop_loss_fires_even_if_open_orders_cannot_be_read(tmp_path):
    h = make_harness(tmp_path, risk=RiskConfig(stop_loss_pct=5.0))
    h.buy("AAA", 10)
    h.feed.prices["AAA"] = 50.0
    h.broker.open_orders = Mock(side_effect=BrokerError("orders endpoint 403"))
    report = h.tick()
    assert statuses(report) == [("AAA", "sell", "filled")]
    assert "AAA: orders endpoint 403" in report.errors


def test_one_unpriceable_holding_does_not_stop_the_other_positions_stops(tmp_path):
    h = make_harness(tmp_path, prices={"AAA": 100.0, "BBB": 50.0, "CCC": 10.0},
                     actions={"CCC": Action.BUY}, risk=RiskConfig(stop_loss_pct=5.0))
    h.buy("AAA", 10)
    h.buy("BBB", 10)
    h.feed.fail_price["AAA"] = BrokerError("AAA ticker unavailable")
    h.feed.prices["BBB"] = 25.0  # -50%

    report = h.tick()

    assert statuses(report) == [("BBB", "sell", "filled")]
    assert any(e.startswith("AAA:") and "ticker unavailable" in e for e in report.errors)
    assert "could not get a price" in report.signals["CCC"]  # equity uncertain: no new entries


def test_daily_baseline_is_the_brokers_own_value_after_a_paper_to_live_switch(tmp_path):
    h = make_harness(tmp_path, risk=RiskConfig(max_daily_loss_pct=3.0, flatten_on_daily_loss=True,
                                               stop_loss_pct=None))
    h.tick()  # paper: today's baseline is the 10,000 paper account
    assert h.state().day_start_equity == pytest.approx(10_000.0)

    h.buy("AAA", 1)
    h.engine.cfg = replace(h.cfg, mode="live")  # same state_dir, now a small live account
    h.broker.get_account = lambda: Account(equity=500.0, cash=400.0, buying_power=400.0,
                                           day_start_equity=500.0)
    h.clock.advance(minutes=5)
    report = h.tick()

    assert report.halted is False and h.state().halted_today is False
    assert report.orders == []  # nothing flattened: the live account is flat on the day
    assert not any("Daily loss limit hit" in m for m in h.notifier.errors)


def test_daily_baseline_restarts_when_the_account_changes_and_the_broker_has_none(tmp_path):
    h = make_harness(tmp_path, risk=RiskConfig(max_daily_loss_pct=3.0, stop_loss_pct=None))
    h.tick()
    h.save_state(**{**h.state().to_dict(), "trades_today": 3})
    h.engine.cfg = replace(h.cfg, mode="live")
    h.broker.get_account = lambda: Account(equity=500.0, cash=500.0, buying_power=500.0)
    h.clock.advance(minutes=5)

    report = h.tick()

    state = h.state()
    assert report.halted is False
    assert state.day_start_equity == pytest.approx(500.0) and state.trades_today == 0


def test_daily_loss_uses_the_brokers_baseline_even_when_a_stale_one_is_stored(tmp_path):
    h = make_harness(tmp_path, risk=RiskConfig(max_daily_loss_pct=3.0))
    h.tick()
    h.save_state(**{**h.state().to_dict(), "day_start_equity": 10_000.0})
    h.broker.get_account = lambda: Account(equity=45_000.0, cash=45_000.0, buying_power=45_000.0,
                                           day_start_equity=50_000.0)
    h.clock.advance(minutes=5)
    report = h.tick()
    assert report.halted is True  # -10% by the broker's own previous close


def test_failed_state_save_keeps_counters_in_memory_and_pauses_entries(tmp_path):
    # 20% of equity per position and a 10% stop: one stop-out loses 2% (limit 3%).
    h = make_harness(tmp_path, prices={"AAA": 100.0}, actions={"AAA": Action.BUY},
                     risk=RiskConfig(risk_per_trade_pct=2.0, stop_loss_pct=10.0, max_trades_per_day=1,
                                     max_daily_loss_pct=1.5))
    real_save, saves = h.store.save, []

    def save(state: BotState) -> None:  # the disk fills up after the first tick (its two saves)
        saves.append(state)
        if len(saves) > 2:
            raise OSError(28, "No space left on device")
        real_save(state)

    h.store.save = save
    buys, sells, halted = [], [], []
    for price in (100.0, 80.0, 80.0, 60.0, 60.0):  # all within the 14:00 bar; the disk fills after the first
        h.feed.prices["AAA"] = price
        report = h.tick()
        buys += [o for o in report.orders if o.side is Side.BUY]
        sells += [o for o in report.orders if o.side is Side.SELL]
        halted.append(report.halted)
        h.clock.advance(minutes=5)

    assert len(buys) == 1 and len(sells) == 1
    assert halted[-1] is True  # the loss limit still works without the state file
    assert any("could not save bot state" in e and "paused" in e for e in report.errors)

    h.clock.advance(hours=1)  # a new bar: still no entries while nothing can be saved
    report = h.tick()
    assert not [o for o in report.orders if o.side is Side.BUY]


def test_failed_state_save_still_lets_exits_run(tmp_path):
    h = make_harness(tmp_path, risk=RiskConfig(stop_loss_pct=5.0))
    h.store.save = Mock(side_effect=OSError(28, "No space left on device"))
    h.tick()
    h.buy("AAA", 10)
    h.feed.prices["AAA"] = 50.0
    h.clock.advance(minutes=5)
    assert statuses(h.tick()) == [("AAA", "sell", "filled")]


def test_per_symbol_errors_do_not_slow_down_the_loop(tmp_path):
    h = make_harness(tmp_path, risk=RiskConfig(stop_loss_pct=10.0))
    h.buy("AAA", 10)
    h.feed.fail_bars["BBB"] = BrokerError("BBB delisted")
    price_reads: list[str] = []
    real = h.feed.get_latest_price
    h.feed.get_latest_price = lambda symbol: price_reads.append(symbol) or real(symbol)
    stop = RecordingEvent()

    h.engine.run_forever(stop_event=stop, max_ticks=8)

    assert stop.waits == [POLL] * 7  # AAA's stop is still checked every poll interval
    assert price_reads.count("AAA") >= 8
    assert any("BBB delisted" in m for m in h.notifier.errors)
    alerts = [m for m in h.notifier.errors if "ticks in a row" in m]
    assert alerts and "BBB delisted" in alerts[0]


def test_tick_level_failures_still_back_off(tmp_path):
    h = make_harness(tmp_path)
    h.broker.get_account = Mock(side_effect=BrokerError("503"))
    stop = RecordingEvent()
    h.engine.run_forever(stop_event=stop, max_ticks=3)
    assert stop.waits == [POLL, 2 * POLL]


def test_daily_loss_flatten_sells_only_the_configured_symbols(tmp_path):
    h = make_harness(tmp_path, prices={"AAA": 100.0, "BBB": 50.0, "XYZ": 20.0}, symbols=["AAA", "BBB"],
                     risk=RiskConfig(max_daily_loss_pct=3.0, flatten_on_daily_loss=True, stop_loss_pct=None))
    h.buy("AAA", 10)
    h.buy("XYZ", 50)  # bought by hand; the bot does not manage it
    h.broker.close_all_positions = Mock(side_effect=AssertionError("account-wide flatten"))
    cancelled: list[list[str]] = []
    h.broker.cancel_orders = lambda symbols: cancelled.append(list(symbols))
    h.save_state(day=TODAY, day_start_equity=100_000.0)

    report = h.tick()

    assert statuses(report) == [("AAA", "sell", "filled")]
    assert "XYZ" in h.broker.get_positions()
    assert cancelled == []  # no order of the bot's is working; others' orders are never cancelled
    assert all("flatten" in row["reason"] for row in read_trades(h))


def test_partially_rejected_flatten_is_retried_next_tick(tmp_path):
    h = make_harness(tmp_path, risk=RiskConfig(max_daily_loss_pct=3.0, flatten_on_daily_loss=True,
                                               stop_loss_pct=None))
    h.buy("AAA", 10)
    h.buy("BBB", 20)
    h.save_state(day=TODAY, day_start_equity=100_000.0)
    real = h.broker.submit_order
    rejected: list[OrderRequest] = []

    def submit(order: OrderRequest) -> OrderResult:
        if order.symbol == "BBB" and not rejected:
            rejected.append(order)
            return OrderResult("r-1", "BBB", order.side, order.qty, "rejected", reason="insufficient qty available")
        return real(order)

    h.broker.submit_order = submit
    first = h.tick()
    assert sorted(statuses(first)) == [("AAA", "sell", "filled"), ("BBB", "sell", "rejected")]

    h.clock.advance(minutes=5)
    second = h.tick()
    assert statuses(second) == [("BBB", "sell", "filled")]
    assert h.broker.get_positions() == {}


def test_held_position_outside_symbols_is_reported_as_unmanaged(tmp_path):
    h = make_harness(tmp_path, prices={"AAA": 100.0, "BBB": 50.0, "OLD": 10.0}, symbols=["AAA", "BBB"],
                     risk=RiskConfig(stop_loss_pct=5.0))
    h.buy("OLD", 10)
    h.feed.prices["OLD"] = 5.0  # -50%, but OLD is no longer in `symbols`

    first = h.tick()
    assert "not managed" in first.signals["OLD"]
    assert first.orders == []
    assert sum("OLD" in m and "not managed" in m for m in h.notifier.errors) == 1

    h.clock.advance(minutes=5)
    second = h.tick()
    assert "not managed" in second.signals["OLD"]
    assert sum("OLD" in m and "not managed" in m for m in h.notifier.errors) == 1  # notified once


def test_custom_broker_that_only_reports_has_open_orders_still_blocks_duplicates(tmp_path):
    class LegacyPaper(PaperBroker):
        def has_open_orders(self, symbol: str) -> bool:
            return symbol == "AAA"

    clock = Clock(T0)
    feed = FakeFeed(clock, {"AAA": 100.0, "BBB": 50.0})
    legacy = LegacyPaper(feed, starting_cash=10_000.0, fee_pct=0.0, slippage_pct=0.0, clock=clock)
    h = make_harness(tmp_path, actions={"AAA": Action.BUY, "BBB": Action.BUY}, broker=legacy)
    h.engine.broker.feed = h.feed
    report = h.tick()
    assert statuses(report) == [("BBB", "buy", "filled")]
    assert "pending" in report.signals["AAA"]


# --------------------------------------------------------------------------- regression: holdings the bot did not buy


def test_holding_the_bot_did_not_buy_is_never_sold(tmp_path):
    # The account already holds 50 AAA (bought by hand long ago) when the bot
    # starts. Strategy SELL, a price far through the stop and a daily-loss
    # flatten all apply to the bot's own positions only: nothing is sold.
    h = make_harness(tmp_path, actions={"AAA": Action.SELL}, shared_account=True,
                     risk=RiskConfig(stop_loss_pct=5.0, take_profit_pct=10.0, max_daily_loss_pct=3.0,
                                     flatten_on_daily_loss=True))
    h.buy("AAA", 50)
    h.feed.prices["AAA"] = 50.0
    # A state the bot has run with before; the day's loss limit is hit: flatten.
    h.save_state(day=TODAY, day_start_equity=100_000.0, last_tick_at=T0.isoformat(), holdings_checked=True)

    report = h.tick()

    assert report.orders == []
    assert h.broker.get_positions()["AAA"].qty == 50
    assert report.halted is True
    notices = [m for m in h.notifier.errors if "AAA" in m and "did not buy" in m]
    assert len(notices) == 1 and "adopt_existing_positions" in notices[0]

    h.feed.prices["AAA"] = 500.0  # far above any take-profit: still left alone
    h.clock.advance(minutes=5)
    assert h.tick().orders == []
    assert len([m for m in h.notifier.errors if "did not buy" in m]) == 1  # notified once


def test_bot_does_not_buy_into_a_symbol_the_account_already_holds_without_it(tmp_path):
    h = make_harness(tmp_path, actions={"AAA": Action.BUY, "BBB": Action.BUY}, shared_account=True)
    h.buy("AAA", 5)
    report = h.tick()
    assert statuses(report) == [("BBB", "buy", "filled")]
    assert "did not buy" in report.signals["AAA"]


def test_bot_sells_only_what_it_bought_when_the_user_holds_more_of_the_symbol(tmp_path):
    h = make_harness(tmp_path, prices={"AAA": 100.0}, actions={"AAA": Action.BUY}, shared_account=True,
                     risk=RiskConfig(max_position_pct=10.0, stop_loss_pct=None))
    (bought,) = h.tick().orders
    h.buy("AAA", 50)  # the user adds 50 by hand
    h.clock.advance(minutes=5)
    h.tick()
    assert any("never the other 50" in m for m in h.notifier.errors)
    h.strategy.actions["AAA"] = Action.SELL
    h.clock.advance(hours=1)

    report = h.tick()

    assert statuses(report) == [("AAA", "sell", "filled")]
    assert report.orders[0].filled_qty == pytest.approx(bought.filled_qty)
    assert h.broker.get_positions()["AAA"].qty == pytest.approx(50.0)


def test_stop_loss_uses_the_bots_own_entry_price_not_the_blended_average(tmp_path):
    h = make_harness(tmp_path, prices={"AAA": 100.0}, actions={"AAA": Action.BUY}, shared_account=True,
                     risk=RiskConfig(max_position_pct=10.0, stop_loss_pct=5.0))
    (bought,) = h.tick().orders
    h.feed.prices["AAA"] = 40.0
    h.buy("AAA", 50)  # the user's cheap shares drag the account's average entry down to 50
    h.strategy.actions["AAA"] = Action.HOLD
    h.feed.prices["AAA"] = 90.0  # -10% for the bot's shares bought at 100
    h.clock.advance(minutes=5)

    report = h.tick()

    assert statuses(report) == [("AAA", "sell", "filled")]
    assert report.orders[0].filled_qty == pytest.approx(bought.filled_qty)
    assert "stop_loss" in report.signals["AAA"]


def test_adopt_existing_positions_lets_the_bot_manage_them(tmp_path):
    h = make_harness(tmp_path, shared_account=True, adopt_existing_positions=True,
                     risk=RiskConfig(stop_loss_pct=5.0))
    h.buy("AAA", 50)
    h.feed.prices["AAA"] = 50.0
    report = h.tick()
    assert statuses(report) == [("AAA", "sell", "filled")]
    assert not any("did not buy" in m for m in h.notifier.errors)


def test_a_buy_that_fills_after_the_tick_is_managed_once_it_fills(tmp_path):
    # Alpaca acknowledges a market BUY as "accepted"; it fills a moment later.
    prices = {"AAA": 100.0}
    broker = AcceptingBroker(FakeFeed(Clock(T0), prices), cash=10_000.0)
    h = make_harness(tmp_path, prices=prices, actions={"AAA": Action.BUY}, broker=broker,
                     risk=RiskConfig(stop_loss_pct=5.0, max_position_pct=20.0))
    h.engine.broker.feed = h.feed
    (buy,) = h.tick().orders
    assert buy.status == "accepted"
    broker.settle()
    h.feed.prices["AAA"] = 90.0  # through the 5% stop
    h.clock.advance(minutes=5)

    report = h.tick()

    assert [(o.symbol, o.side.value, o.qty) for o in report.orders] == [("AAA", "sell", buy.qty)]
    assert not any("did not buy" in m for m in h.notifier.errors)  # the unfilled sell is not "someone else's"


def test_a_bot_buy_that_never_filled_does_not_make_a_later_manual_buy_the_bots(tmp_path):
    prices = {"AAA": 100.0}
    broker = AcceptingBroker(FakeFeed(Clock(T0), prices), cash=10_000.0)
    h = make_harness(tmp_path, prices=prices, actions={"AAA": Action.BUY}, broker=broker,
                     risk=RiskConfig(stop_loss_pct=5.0, max_position_pct=20.0))
    h.engine.broker.feed = h.feed
    assert [o.status for o in h.tick().orders] == ["accepted"]
    broker.cancel_all_orders()  # it expired unfilled
    for _ in range(2):  # the bot sees the order gone, then trims its record to what is held
        h.clock.advance(minutes=5)
        assert h.tick().orders == []
    assert h.state().owned == {}

    broker.holdings["AAA"] = 10.0  # later the user buys 10 AAA by hand
    h.feed.prices["AAA"] = 50.0
    h.clock.advance(minutes=5)
    assert h.tick().orders == []
    assert any("AAA" in m and "did not buy" in m for m in h.notifier.errors)


def test_what_the_bot_bought_in_one_account_does_not_carry_over_to_another(tmp_path):
    h = make_harness(tmp_path, prices={"AAA": 100.0}, actions={"AAA": Action.BUY}, shared_account=True,
                     risk=RiskConfig(stop_loss_pct=5.0, max_position_pct=10.0))
    h.tick()
    assert "AAA" in h.state().owned
    h.engine.cfg = replace(h.cfg, mode="live")  # same state_dir, now the live account
    h.feed.prices["AAA"] = 50.0
    h.clock.advance(minutes=5)
    report = h.tick()
    assert report.orders == []  # the live AAA holding is not the one the paper bot bought
    assert h.state().owned == {}


# --------------------------------------------------------------------------- regression: prices, short history


def test_stop_loss_falls_back_to_the_brokers_position_price_when_the_price_read_fails(tmp_path):
    class PricedPositions(PaperBroker):
        """Positions carry the broker's own current price (like Alpaca's trading API)."""

        def get_positions(self):
            return {s: replace(p, market_price=80.0) for s, p in super().get_positions().items()}

        def get_account(self):
            return replace(super().get_account(), unpriced=())

    clock = Clock(T0)
    feed = FakeFeed(clock, {"AAA": 100.0, "BBB": 50.0})
    broker = PricedPositions(feed, starting_cash=10_000.0, fee_pct=0.0, slippage_pct=0.0, clock=clock)
    h = make_harness(tmp_path, broker=broker, risk=RiskConfig(stop_loss_pct=8.0))
    broker.submit_order(OrderRequest("AAA", Side.BUY, 10))
    feed.fail_price["AAA"] = BrokerError("market data API 503")
    sent: list[OrderRequest] = []
    broker.submit_order = lambda order: sent.append(order) or OrderResult(
        "x-1", order.symbol, order.side, order.qty, "accepted")

    report = h.tick()

    assert [(o.symbol, o.side, o.qty) for o in sent] == [("AAA", Side.SELL, 10)]
    assert "stop_loss" in report.signals["AAA"]
    assert "AAA: market data API 503" in report.errors


def test_no_fallback_price_for_a_holding_the_broker_itself_could_not_price(tmp_path):
    h = make_harness(tmp_path, risk=RiskConfig(stop_loss_pct=5.0))
    h.buy("AAA", 10)
    h.feed.prices["AAA"] = 50.0
    h.broker.get_latest_price("AAA")  # the paper broker's last known price is now 50 ...
    h.feed.fail_price["AAA"] = BrokerError("AAA ticker unavailable")  # ... and stale from here on
    report = h.tick()
    assert report.orders == []
    assert any(e.startswith("AAA:") for e in report.errors)


def test_a_symbol_that_can_never_warm_up_is_warned_about_once(tmp_path):
    # The venue serves 8 bars (7 closed); the strategy needs 9. `run` shows no
    # signals, so without a warning the bot would silently never trade.
    h = make_harness(tmp_path, prices={"AAA": 100.0}, min_bars=9)
    h.feed.max_bars = 8
    first = h.tick()
    h.clock.advance(hours=1)
    second = h.tick()
    assert first.signals["AAA"] == second.signals["AAA"] == "warming up (7/9 closed bars)"
    warnings = [m for m in h.notifier.errors if "AAA" in m and "only 7" in m and "needs 9" in m]
    assert len(warnings) == 1
    assert first.errors == [] and second.errors == []


# ------------------------------------------------------------------------ regression: orders whose outcome is unclear


def test_a_buy_whose_reply_was_lost_is_still_the_bots_and_keeps_its_stop_loss(tmp_path):
    # The BUY reaches the broker and fills, but the reply is lost (a read
    # timeout): the adapter raises "may or may not have reached" the broker.
    h = make_harness(tmp_path, prices={"AAA": 100.0}, actions={"AAA": Action.BUY}, shared_account=True,
                     risk=RiskConfig(stop_loss_pct=5.0, max_position_pct=20.0))
    real = h.broker.submit_order

    def fill_then_time_out(order: OrderRequest) -> OrderResult:
        real(order)
        raise BrokerError("submit_order(AAA) failed (ReadTimeout); the order may or may not have reached "
                          "the broker - check open orders")

    h.broker.submit_order = fill_then_time_out
    first = h.tick()
    assert first.orders == [] and any("may or may not" in e for e in first.errors)
    held = h.broker.get_positions()["AAA"].qty
    assert held == pytest.approx(20.0)

    h.broker.submit_order = real
    h.strategy.actions["AAA"] = Action.HOLD
    h.feed.prices["AAA"] = 80.0  # -20%, through the 5% stop
    for _ in range(2):
        h.clock.advance(minutes=5)
        report = h.tick()
        if report.orders:
            break

    assert [(o.symbol, o.side.value, o.filled_qty) for o in report.orders] == [("AAA", "sell", held)]
    assert "stop_loss" in report.signals["AAA"]
    assert not any("did not buy" in m or "not bought" in m for m in h.notifier.errors)


def test_a_buy_that_never_reached_the_broker_is_not_left_booked_as_the_bots(tmp_path):
    h = make_harness(tmp_path, prices={"AAA": 100.0}, actions={"AAA": Action.BUY}, shared_account=True,
                     risk=RiskConfig(stop_loss_pct=5.0, max_position_pct=20.0))
    real = h.broker.submit_order
    h.broker.submit_order = Mock(side_effect=BrokerError("connection refused"))
    assert h.tick().orders == []
    h.broker.submit_order = real
    h.strategy.actions["AAA"] = Action.HOLD  # the retry on the same bar decides not to buy
    for _ in range(2):  # the bot sees no order of its own working, then follows the holding
        h.clock.advance(minutes=5)
        assert h.tick().orders == []
    assert h.state().owned == {} and h.state().unsettled == []
    assert not any("did not buy" in m for m in h.notifier.errors)

    h.buy("AAA", 10)  # later the user buys 10 AAA by hand: not the bot's
    h.feed.prices["AAA"] = 50.0
    h.clock.advance(minutes=5)
    assert h.tick().orders == []
    assert any("AAA" in m and "did not buy" in m for m in h.notifier.errors)


def test_a_buy_that_failed_to_send_is_retried_on_the_same_bar(tmp_path):
    h = make_harness(tmp_path, prices={"AAA": 100.0}, actions={"AAA": Action.BUY}, shared_account=True,
                     risk=RiskConfig(stop_loss_pct=5.0, max_position_pct=20.0))
    real = h.broker.submit_order
    h.broker.submit_order = Mock(side_effect=BrokerError("connection refused"))
    h.tick()
    h.broker.submit_order = real
    h.clock.advance(minutes=5)
    report = h.tick()
    assert statuses(report) == [("AAA", "buy", "filled")]
    for _ in range(2):
        h.clock.advance(minutes=5)
        h.tick()
    assert h.state().owned["AAA"]["qty"] == pytest.approx(20.0)  # the failed attempt is not counted twice


def accepting_harness(tmp_path, holdings: dict[str, float], owned: dict[str, float],
                      **risk: object) -> tuple[Harness, AcceptingBroker]:
    prices = {symbol: 100.0 for symbol in holdings}
    broker = AcceptingBroker(FakeFeed(Clock(T0), prices), cash=8_000.0, holdings=holdings)
    h = make_harness(tmp_path, prices=prices, broker=broker, risk=RiskConfig(**risk))
    h.engine.broker.feed = h.feed
    h.save_state(owned={s: {"qty": q, "avg_entry_price": 100.0} for s, q in owned.items()})
    return h, broker


def test_a_stop_loss_sell_that_expires_unfilled_is_sent_again(tmp_path):
    h, broker = accepting_harness(tmp_path, {"AAA": 20.0}, {"AAA": 20.0}, stop_loss_pct=5.0)
    h.feed.prices["AAA"] = 94.0
    first = h.tick()
    assert [(o.side.value, o.qty, o.status) for o in first.orders] == [("sell", 20.0, "accepted")]
    assert h.state().owned["AAA"]["qty"] == 20.0  # not sold until it fills

    broker.pending.clear()  # the DAY order expires unfilled (a halt through the close)
    h.feed.prices["AAA"] = 60.0
    h.clock.advance(minutes=5)
    second = h.tick()

    assert [(o.side.value, o.qty) for o in second.orders] == [("sell", 20.0)]
    assert "stop_loss" in second.signals["AAA"]
    assert not any("did not buy" in m for m in h.notifier.errors)


def test_a_sell_that_filled_only_in_part_leaves_the_rest_the_bots(tmp_path):
    h, broker = accepting_harness(tmp_path, {"AAA": 20.0}, {"AAA": 20.0}, stop_loss_pct=5.0)
    h.feed.prices["AAA"] = 94.0
    assert [o.status for o in h.tick().orders] == ["accepted"]
    broker.holdings["AAA"], broker.cash = 15.0, broker.cash + 5 * 94.0  # 5 of 20 fill, then it is cancelled
    broker.pending.clear()
    h.feed.prices["AAA"] = 100.0
    for _ in range(2):
        h.clock.advance(minutes=5)
        assert h.tick().orders == []
    assert h.state().owned == {"AAA": {"qty": 15.0, "avg_entry_price": 100.0}}

    h.feed.prices["AAA"] = 80.0
    h.clock.advance(minutes=5)
    assert [(o.side.value, o.qty) for o in h.tick().orders] == [("sell", 15.0)]


def test_a_filled_sell_never_sells_the_users_own_shares_of_the_symbol(tmp_path):
    # The account holds 120 AAA: 20 the bot bought, 100 the user's own.
    h, broker = accepting_harness(tmp_path, {"AAA": 120.0}, {"AAA": 20.0}, stop_loss_pct=5.0)
    h.feed.prices["AAA"] = 94.0
    assert [(o.side.value, o.qty) for o in h.tick().orders] == [("sell", 20.0)]
    broker.settle()  # the bot's 20 are sold
    for _ in range(3):
        h.clock.advance(minutes=5)
        assert h.tick().orders == []  # the user's 100 are never sold, even through the stop
    assert h.state().owned == {}
    assert broker.holdings["AAA"] == pytest.approx(100.0)


def test_a_sell_whose_reply_was_lost_does_not_make_the_users_shares_the_bots(tmp_path):
    h = make_harness(tmp_path, prices={"AAA": 100.0}, actions={"AAA": Action.BUY}, shared_account=True,
                     risk=RiskConfig(stop_loss_pct=5.0, max_position_pct=20.0))
    h.tick()  # the bot buys 20
    h.buy("AAA", 50)  # the user buys 50
    real = h.broker.submit_order

    def fill_then_time_out(order: OrderRequest) -> OrderResult:
        real(order)
        raise BrokerError("submit_order(AAA) failed (ReadTimeout)")

    h.broker.submit_order = fill_then_time_out
    h.strategy.actions["AAA"] = Action.HOLD
    h.feed.prices["AAA"] = 90.0
    h.clock.advance(minutes=5)
    assert h.tick().orders == []  # the stop-loss sell went through, its reply was lost
    assert h.broker.get_positions()["AAA"].qty == pytest.approx(50.0)
    h.broker.submit_order = real
    for _ in range(3):
        h.clock.advance(minutes=5)
        assert h.tick().orders == []
    assert h.broker.get_positions()["AAA"].qty == pytest.approx(50.0)
    assert h.state().owned == {}


# --------------------------------------------------------------------------- regression: stock splits


def split(h: Harness, symbol: str, ratio: float) -> None:
    """Apply a split the way a broker does: more shares at a lower average price."""
    from bot.brokers.paper import _Holding

    held = h.broker._holdings[symbol]
    h.broker._holdings[symbol] = _Holding(held.qty * ratio, held.avg_entry_price / ratio)
    h.feed.prices[symbol] /= ratio


def test_a_forward_split_rescales_what_the_bot_owns_instead_of_stopping_out(tmp_path):
    h = make_harness(tmp_path, prices={"AAA": 500.0, "BBB": 50.0}, actions={"AAA": Action.BUY},
                     shared_account=True, risk=RiskConfig(stop_loss_pct=8.0, max_position_pct=25.0,
                                                          max_daily_loss_pct=3.0, flatten_on_daily_loss=True))
    h.tick()
    bought = h.state().owned["AAA"]["qty"]
    assert h.state().owned == {"AAA": {"qty": bought, "avg_entry_price": 500.0}}
    h.strategy.actions["AAA"] = Action.HOLD
    split(h, "AAA", 10)  # 10-for-1: ten times the shares at 50
    h.clock.advance(minutes=5)

    report = h.tick()

    assert report.orders == [] and report.halted is False
    assert h.state().owned == {"AAA": {"qty": pytest.approx(10 * bought), "avg_entry_price": pytest.approx(50.0)}}
    assert not any("did not buy" in m or "Daily loss" in m for m in h.notifier.errors)

    h.feed.prices["AAA"] = 45.0  # a real -10% move after the split: the whole position is stopped out
    h.clock.advance(minutes=5)
    assert [(o.side.value, o.filled_qty) for o in h.tick().orders] == [("sell", pytest.approx(10 * bought))]


def test_a_reverse_split_rescales_the_entry_price_so_the_stop_still_works(tmp_path):
    h = make_harness(tmp_path, prices={"AAA": 10.0}, actions={"AAA": Action.BUY}, shared_account=True,
                     risk=RiskConfig(stop_loss_pct=8.0, take_profit_pct=20.0, max_position_pct=25.0))
    h.tick()
    bought = h.state().owned["AAA"]["qty"]
    assert h.state().owned == {"AAA": {"qty": bought, "avg_entry_price": 10.0}}
    h.strategy.actions["AAA"] = Action.HOLD
    split(h, "AAA", 0.1)  # 1-for-10: a tenth of the shares at 100
    h.clock.advance(minutes=5)
    assert h.tick().orders == []  # no take-profit at an unchanged price
    assert h.state().owned == {"AAA": {"qty": pytest.approx(bought / 10), "avg_entry_price": pytest.approx(100.0)}}

    h.feed.prices["AAA"] = 90.0  # -10%
    h.clock.advance(minutes=5)
    report = h.tick()
    assert [(o.side.value, o.filled_qty) for o in report.orders] == [("sell", pytest.approx(bought / 10))]
    assert "stop_loss" in report.signals["AAA"]


def test_user_trades_in_the_symbol_are_not_mistaken_for_a_split(tmp_path):
    h = make_harness(tmp_path, prices={"AAA": 100.0}, actions={"AAA": Action.BUY}, shared_account=True,
                     risk=RiskConfig(stop_loss_pct=None, max_daily_loss_pct=None, max_position_pct=20.0))
    h.tick()
    bought = h.state().owned["AAA"]
    h.strategy.actions["AAA"] = Action.HOLD
    h.buy("AAA", 2 * bought["qty"])  # the user triples the holding at the same price
    h.clock.advance(minutes=5)
    h.tick()
    assert h.state().owned == {"AAA": bought}
    h.feed.prices["AAA"] = 20.0
    h.buy("AAA", 0.05 * bought["qty"])  # and adds a little far below the average cost
    h.clock.advance(minutes=5)
    h.tick()
    assert h.state().owned == {"AAA": bought}


# --------------------------------------------------------------------------- regression: notices across `once` runs


def test_the_short_history_warning_is_sent_once_across_separate_runs(tmp_path):
    h = make_harness(tmp_path, prices={"AAA": 100.0}, min_bars=9)
    h.feed.max_bars = 8
    h.tick()
    for _ in range(3):  # each `once` run is a new process with a new engine
        engine = TradingEngine(h.cfg, h.broker, h.strategy, RiskManager(h.cfg.risk), h.store, h.notifier,
                               clock=h.clock)
        h.clock.advance(hours=1)
        engine.run_once()
    assert len([m for m in h.notifier.errors if "AAA" in m and "needs 9" in m]) == 1

    h.feed.max_bars = None  # enough history now: warned again if it ever runs short later
    h.clock.advance(hours=1)
    h.tick()
    assert h.state().warned_short_history == []
    h.feed.max_bars = 8
    h.clock.advance(hours=1)
    h.tick()
    assert len([m for m in h.notifier.errors if "AAA" in m and "needs 9" in m]) == 2


def test_daily_loss_flatten_leaves_the_bots_working_sell_in_place_and_sells_the_rest(tmp_path):
    # AAA's stop-loss SELL is still working (a halted stock) when the daily
    # loss limit trips: it must not be cancelled (and then never re-sent).
    prices = {"AAA": 100.0, "BBB": 100.0}
    broker = AcceptingBroker(FakeFeed(Clock(T0), prices), cash=6_000.0, holdings={"AAA": 20.0, "BBB": 20.0})
    h = make_harness(tmp_path, prices=prices, broker=broker,
                     risk=RiskConfig(stop_loss_pct=5.0, max_daily_loss_pct=3.0, flatten_on_daily_loss=True))
    h.engine.broker.feed = h.feed
    h.save_state(day=TODAY, day_start_equity=10_000.0,
                 owned={s: {"qty": 20.0, "avg_entry_price": 100.0} for s in prices})
    h.feed.prices["AAA"] = 94.0
    assert [(o.symbol, o.side.value) for o in h.tick().orders] == [("AAA", "sell")]

    h.feed.prices["BBB"] = 80.0  # equity 9,480: -5.2%
    h.clock.advance(minutes=5)
    report = h.tick()

    assert report.halted is True and report.errors == []
    assert [(o.symbol, o.side.value, o.qty) for o in report.orders] == [("BBB", "sell", 20.0)]
    assert [(o.symbol, o.side) for o in broker.pending] == [("AAA", Side.SELL), ("BBB", Side.SELL)]


def test_a_bot_killed_while_its_buy_is_in_flight_still_manages_that_buy_after_a_restart(tmp_path):
    # SIGKILL (docker's stop grace running out, a cancelled `once`) lands after
    # the BUY reached the broker but before the tick's final save.
    h = make_harness(tmp_path, prices={"AAA": 100.0}, actions={"AAA": Action.BUY}, shared_account=True,
                     risk=RiskConfig(stop_loss_pct=5.0, max_position_pct=20.0))
    real = h.broker.submit_order

    def fill_then_die(order: OrderRequest) -> OrderResult:
        real(order)
        raise KeyboardInterrupt  # the process is killed while waiting for the reply

    h.broker.submit_order = fill_then_die
    with pytest.raises(KeyboardInterrupt):
        h.tick()
    held = h.broker.get_positions()["AAA"].qty
    assert h.state().owned["AAA"]["qty"] == pytest.approx(held)  # booked before the order went out
    assert h.state().trades_today == 1

    h.broker.submit_order = real
    h.strategy.actions["AAA"] = Action.HOLD
    h.feed.prices["AAA"] = 80.0
    restarted = TradingEngine(h.cfg, h.broker, h.strategy, RiskManager(h.cfg.risk), h.store, h.notifier,
                              clock=h.clock)
    for _ in range(2):
        h.clock.advance(minutes=5)
        report = restarted.run_once()
        if report.orders:
            break
    assert [(o.symbol, o.side.value, o.filled_qty) for o in report.orders] == [("AAA", "sell", held)]
    assert not any("did not buy" in m for m in h.notifier.errors)


def test_a_bot_killed_right_after_a_filled_order_keeps_it_booked(tmp_path):
    h = make_harness(tmp_path, prices={"AAA": 100.0}, actions={"AAA": Action.BUY}, shared_account=True,
                     risk=RiskConfig(stop_loss_pct=5.0, max_position_pct=20.0))
    h.notifier.trade = Mock(side_effect=KeyboardInterrupt)  # killed right after the reply came back
    with pytest.raises(KeyboardInterrupt):
        h.tick()
    state = h.state()
    assert state.owned == {"AAA": {"qty": pytest.approx(20.0), "avg_entry_price": pytest.approx(100.0)}}
    assert state.unsettled == [] and state.trades_today == 1


class TrackingBroker(AcceptingBroker):
    """AcceptingBroker that can say how much of each of its orders filled
    (like Alpaca's order lookup by client order id)."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fills: dict[str, float] = {}   # client order id -> filled qty, once finished

    def settle(self) -> None:
        for order in self.pending:
            self.fills[order.client_order_id] = order.qty
        super().settle()

    def cancel_all_orders(self) -> None:
        for order in self.pending:
            self.fills.setdefault(order.client_order_id, 0.0)
        super().cancel_all_orders()

    def order_filled_qty(self, symbol, client_order_id, order_id=""):
        if any(o.client_order_id == client_order_id for o in self.pending):
            raise BrokerError("still working")
        return self.fills.get(client_order_id, 0.0)


def test_no_stop_loss_sell_while_the_bots_own_buy_is_still_working(tmp_path):
    # The user buys 50 AAA by hand while the bot's BUY of 20 is still working:
    # until it fills, the bot cannot tell which shares are its own.
    prices = {"AAA": 100.0}
    broker = TrackingBroker(FakeFeed(Clock(T0), prices), cash=20_000.0)
    h = make_harness(tmp_path, prices=prices, actions={"AAA": Action.BUY}, broker=broker,
                     risk=RiskConfig(stop_loss_pct=5.0, max_position_pct=20.0))
    h.engine.broker.feed = h.feed
    assert [(o.side.value, o.status) for o in h.tick().orders] == [("buy", "accepted")]
    broker.holdings["AAA"] = 50.0  # the user's own
    h.feed.prices["AAA"] = 80.0
    h.clock.advance(minutes=5)

    report = h.tick()

    assert report.orders == []
    assert "still working" in report.signals["AAA"]


def test_a_buy_that_expired_unfilled_never_makes_the_users_shares_the_bots(tmp_path):
    prices = {"AAA": 100.0}
    broker = TrackingBroker(FakeFeed(Clock(T0), prices), cash=20_000.0)
    h = make_harness(tmp_path, prices=prices, actions={"AAA": Action.BUY}, broker=broker,
                     risk=RiskConfig(stop_loss_pct=5.0, max_position_pct=20.0))
    h.engine.broker.feed = h.feed
    h.tick()
    h.strategy.actions["AAA"] = Action.HOLD
    broker.holdings["AAA"] = 50.0  # the user buys 50 while the bot's BUY is working ...
    broker.cancel_all_orders()     # ... which then expires unfilled
    h.feed.prices["AAA"] = 80.0
    for _ in range(3):
        h.clock.advance(minutes=5)
        assert h.tick().orders == []
    assert h.state().owned == {} and h.state().pending_orders == {}
    assert broker.holdings["AAA"] == 50.0


def test_a_sell_the_broker_reports_filled_is_booked_by_what_filled(tmp_path):
    # The user holds 100 AAA next to the bot's 20. The bot's stop-loss SELL
    # fills 5, is cancelled, and then the user sells 30 of their own.
    prices = {"AAA": 100.0}
    broker = TrackingBroker(FakeFeed(Clock(T0), prices), cash=8_000.0, holdings={"AAA": 120.0})
    h = make_harness(tmp_path, prices=prices, broker=broker, risk=RiskConfig(stop_loss_pct=5.0))
    h.engine.broker.feed = h.feed
    h.save_state(owned={"AAA": {"qty": 20.0, "avg_entry_price": 100.0}})
    h.feed.prices["AAA"] = 94.0
    (sell,) = h.tick().orders
    assert (sell.side, sell.qty, sell.status) == (Side.SELL, 20.0, "accepted")
    broker.fills[broker.pending[0].client_order_id] = 5.0
    broker.pending.clear()
    broker.holdings["AAA"] = 120.0 - 5.0 - 30.0
    h.feed.prices["AAA"] = 100.0
    for _ in range(2):
        h.clock.advance(minutes=5)
        assert h.tick().orders == []
    assert h.state().owned == {"AAA": {"qty": 15.0, "avg_entry_price": 100.0}}


# --------------------------------------------------------------------------- regression: the bot's record survives


def _stop_harness(tmp_path, **risk):
    """A real account where the bot buys 10 AAA at 100 (10% of 10,000) with a 5% stop."""
    return make_harness(tmp_path, prices={"AAA": 100.0}, actions={"AAA": Action.BUY}, shared_account=True,
                        risk=RiskConfig(**{"stop_loss_pct": 5.0, "max_position_pct": 10.0, **risk}))


def test_switching_to_another_account_and_back_keeps_what_the_bot_bought_there(tmp_path):
    h = _stop_harness(tmp_path, max_daily_loss_pct=None)
    h.engine.cfg = replace(h.cfg, mode="live")
    assert statuses(h.tick()) == [("AAA", "buy", "filled")]
    h.strategy.actions["AAA"] = Action.HOLD
    h.engine.cfg = replace(h.cfg, mode="paper")  # a day on paper, same state_dir
    h.clock.advance(minutes=5)
    h.tick()
    assert h.state().owned == {}
    assert any("account changed" in m and "AAA" in m for m in h.notifier.errors)

    h.engine.cfg = replace(h.cfg, mode="live")  # back to live: its record comes back
    h.feed.prices["AAA"] = 50.0
    h.clock.advance(minutes=5)
    report = h.tick()

    assert statuses(report) == [("AAA", "sell", "filled")]
    assert "stop_loss" in report.signals["AAA"]


def test_a_state_file_that_disappears_while_the_bot_runs_is_written_again_from_memory(tmp_path):
    h = _stop_harness(tmp_path)
    h.tick()
    h.store.path.unlink()  # e.g. someone cleared state/ while `run` kept going
    h.strategy.actions["AAA"] = Action.HOLD
    h.feed.prices["AAA"] = 50.0
    h.clock.advance(minutes=5)

    report = h.tick()

    assert statuses(report) == [("AAA", "sell", "filled")]
    assert any("state file" in m and "missing" in m for m in h.notifier.errors)
    assert h.store.path.exists() and h.state().last_tick_at is not None


def test_a_fresh_state_does_not_claim_the_bot_did_not_buy_what_the_account_holds(tmp_path):
    # e.g. the GitHub Actions cache expired: no state file, and the account
    # holds a configured symbol the bot may well have bought itself.
    h = make_harness(tmp_path, shared_account=True)
    h.buy("AAA", 10)
    h.tick()
    (notice,) = [m for m in h.notifier.errors if m.startswith("AAA")]
    assert "no record" in notice and "lost" in notice and "no stop-loss" in notice
    assert "did not buy" not in notice


def test_a_corrupt_state_file_is_left_in_place_and_the_running_bot_keeps_what_it_knew(tmp_path):
    h = _stop_harness(tmp_path)
    h.tick()
    h.store.path.write_text('{"day": "2026-09-24", typo', encoding="utf-8")  # a bad hand edit
    h.strategy.actions["AAA"] = Action.HOLD
    h.feed.prices["AAA"] = 90.0
    h.clock.advance(minutes=5)

    report = h.tick()

    assert statuses(report) == [("AAA", "sell", "filled")]
    assert any("corrupt" in e for e in report.errors)
    assert h.store.path.read_text(encoding="utf-8") == '{"day": "2026-09-24", typo'


def test_exits_made_while_the_state_file_could_not_be_read_are_not_undone_by_the_older_file(tmp_path):
    h = _stop_harness(tmp_path)
    h.tick()  # the bot buys 10 AAA
    h.buy("AAA", 50)  # then the user buys 50 by hand
    h.strategy.actions["AAA"] = Action.HOLD
    real_load = h.store.load
    h.store.load = Mock(side_effect=PermissionError(13, "Permission denied"))
    h.feed.prices["AAA"] = 94.0
    h.clock.advance(minutes=5)
    assert statuses(h.tick()) == [("AAA", "sell", "filled")]  # the bot's 10 stop out
    h.store.load = real_load

    for _ in range(2):
        h.clock.advance(minutes=5)
        assert h.tick().orders == []
    assert h.broker.get_positions()["AAA"].qty == pytest.approx(50.0)  # the user's 50 stay


def test_a_buy_of_the_bots_that_fills_right_after_the_positions_read_is_not_bought_twice(tmp_path):
    prices = {"AAA": 100.0}
    broker = AcceptingBroker(FakeFeed(Clock(T0), prices), cash=10_000.0)
    h = make_harness(tmp_path, prices=prices, actions={"AAA": Action.BUY}, broker=broker,
                     risk=RiskConfig(stop_loss_pct=5.0, max_position_pct=20.0))
    h.engine.broker.feed = h.feed
    assert [o.status for o in h.tick().orders] == ["accepted"]
    real_positions = broker.get_positions

    def read_then_fill():
        broker.get_positions = real_positions
        held = real_positions()
        broker.settle()  # fills just after this tick's positions read
        return held

    broker.get_positions = read_then_fill
    h.clock.advance(hours=1)  # a new bar: the strategy says BUY again

    assert h.tick().orders == []
    assert len(broker.buys()) == 1 and h.state().owned["AAA"]["qty"] == pytest.approx(20.0)


def test_a_failed_account_reread_after_a_flatten_never_sells_the_users_shares(tmp_path):
    h = _stop_harness(tmp_path, max_position_pct=20.0, max_daily_loss_pct=3.0, flatten_on_daily_loss=True)
    h.tick()  # the bot buys 20 AAA
    h.buy("AAA", 30)  # the user buys 30 by hand
    h.strategy.actions["AAA"] = Action.HOLD
    h.feed.prices["AAA"] = 80.0  # the daily-loss limit and the stop both trip
    real = h.broker.get_account
    calls = {"n": 0}

    def flaky_account() -> Account:
        calls["n"] += 1
        if calls["n"] == 2:  # the re-read right after the flatten sell
            raise BrokerError("account endpoint timeout")
        return real()

    h.broker.get_account = flaky_account
    h.clock.advance(minutes=5)

    report = h.tick()

    assert [(o.side.value, o.qty) for o in report.orders] == [("sell", 20.0)]
    assert h.broker.get_positions()["AAA"].qty == pytest.approx(30.0)


def test_a_brokers_own_day_start_follows_its_trading_day_not_the_configured_timezone(tmp_path):
    # Alpaca's day start is the previous New York close. With timezone:
    # Asia/Seoul, Seoul's midnight falls mid-session: it must not drop the
    # withdrawal booked that morning (a false -5% halt against 10,000).
    h = make_harness(tmp_path, timezone_name="Asia/Seoul", risk=RiskConfig(max_daily_loss_pct=3.0))
    h.broker.trading_day_timezone = "America/New_York"
    real = h.broker.get_account
    h.broker.get_account = lambda: replace(real(), day_start_equity=10_000.0)
    h.clock.now = datetime(2026, 9, 24, 14, 0, tzinfo=timezone.utc)  # 10:00 New York, 23:00 Seoul
    h.tick()
    h.broker._cash -= 500.0  # a withdrawal
    h.clock.advance(minutes=30)
    assert h.tick().halted is False
    h.clock.advance(hours=1)  # 11:30 New York, 00:30 the next day in Seoul

    report = h.tick()

    assert report.halted is False
    assert h.state().day == TODAY and h.state().external_flow == pytest.approx(-500.0)


# --------------------------------------------------------------------------- regression: review round 2


def test_a_reverse_split_that_pays_cash_for_a_fraction_never_sells_the_users_shares(tmp_path):
    # 115 AAA: 15 the bot bought, 100 the user's. A 1-for-10 reverse split
    # leaves 11 shares at 1,000 and pays cash for the other half share.
    h, broker = accepting_harness(tmp_path, {"AAA": 115.0}, {"AAA": 15.0}, stop_loss_pct=5.0, take_profit_pct=20.0)
    broker.entries["AAA"] = 100.0
    assert h.tick().orders == []
    broker.holdings["AAA"], broker.entries["AAA"], h.feed.prices["AAA"] = 11.0, 1_000.0, 1_000.0
    broker.cash += 0.5 * 1_000.0
    h.clock.advance(minutes=5)

    assert h.tick().orders == []  # no take-profit at an unchanged value
    assert h.state().owned == {"AAA": {"qty": pytest.approx(1.5), "avg_entry_price": pytest.approx(1_000.0)}}
    h.feed.prices["AAA"] = 900.0  # a real -10%: only the bot's share of the holding is sold
    h.clock.advance(minutes=5)
    assert [(o.side.value, o.qty) for o in h.tick().orders] == [("sell", pytest.approx(1.5))]


def test_a_reverse_split_with_cash_in_lieu_keeps_the_stop_loss_on_the_bots_own_shares(tmp_path):
    h, broker = accepting_harness(tmp_path, {"AAA": 15.0}, {"AAA": 15.0}, stop_loss_pct=5.0)
    broker.entries["AAA"] = 100.0
    h.tick()
    broker.holdings["AAA"], broker.entries["AAA"], h.feed.prices["AAA"] = 1.0, 1_000.0, 1_000.0  # 1.5 -> 1 + cash
    h.clock.advance(minutes=5)
    assert h.tick().orders == []
    assert h.state().owned == {"AAA": {"qty": 1.0, "avg_entry_price": pytest.approx(1_000.0)}}
    h.feed.prices["AAA"] = 700.0
    h.clock.advance(minutes=5)
    assert [(o.side.value, o.qty) for o in h.tick().orders] == [("sell", 1.0)]


def test_a_buy_that_fills_away_from_its_sizing_price_is_not_taken_for_a_split(tmp_path):
    prices = {"AAA": 100.0}
    broker = TrackingBroker(FakeFeed(Clock(T0), prices), cash=10_000.0)
    h = make_harness(tmp_path, prices=prices, actions={"AAA": Action.BUY}, broker=broker,
                     risk=RiskConfig(stop_loss_pct=None, max_position_pct=20.0))
    h.engine.broker.feed = h.feed
    h.notifier.send = Mock()
    assert [o.status for o in h.tick().orders] == ["accepted"]
    h.feed.prices["AAA"] = 94.5  # it fills 5.5% lower (a trading halt)
    broker.settle()
    h.clock.advance(minutes=5)
    h.tick()
    assert not any("split" in str(call) for call in h.notifier.send.call_args_list)
    assert h.state().owned["AAA"]["qty"] == pytest.approx(20.0)


def test_a_sell_that_fills_mid_tick_is_not_reported_as_shares_the_bot_did_not_buy(tmp_path):
    prices = {"AAA": 100.0}
    broker = TrackingBroker(FakeFeed(Clock(T0), prices), cash=0.0, holdings={"AAA": 100.0})
    h = make_harness(tmp_path, prices=prices, broker=broker, risk=RiskConfig(stop_loss_pct=5.0))
    h.engine.broker.feed = h.feed
    h.save_state(owned={"AAA": {"qty": 100.0, "avg_entry_price": 100.0}})
    h.feed.prices["AAA"] = 94.0
    assert [(o.side.value, o.status) for o in h.tick().orders] == [("sell", "accepted")]
    h.clock.advance(minutes=5)
    assert h.tick().orders == []  # still working (a trading halt)
    real_positions = broker.get_positions

    def read_then_fill():
        held = real_positions()
        broker.settle()  # the sell fills right after this tick's positions read
        return held

    broker.get_positions = read_then_fill
    h.strategy.actions["AAA"] = Action.BUY
    h.clock.advance(hours=1)

    report = h.tick()

    assert report.orders == [] and h.state().owned == {}
    assert not any("did not buy" in m for m in h.notifier.errors)
    assert "not entering this tick" in report.signals["AAA"]
    assert h.state().last_signal_bar["AAA"] == LAST_CLOSED.isoformat()  # the new bar is looked at again next tick


def test_a_sale_by_hand_is_not_booked_as_a_withdrawal_when_its_price_cannot_be_read(tmp_path):
    # The user sells their 2 AAA at 1,500 (bought at 2,000): a real -10% day.
    h = make_harness(tmp_path, prices={"AAA": 2_000.0}, shared_account=True,
                     risk=RiskConfig(max_daily_loss_pct=3.0))
    h.buy("AAA", 2)
    assert h.tick().halted is False
    h.feed.prices["AAA"] = 1_500.0
    assert h.broker.submit_order(OrderRequest("AAA", Side.SELL, 2)).status == "filled"
    h.feed.fail_price["AAA"] = BrokerError("ticker unavailable")
    h.clock.advance(minutes=5)

    report = h.tick()

    assert report.halted is True
    assert h.state().external_flow == 0.0


def test_a_stop_loss_sell_rejected_every_tick_does_not_let_a_deposit_hide_a_loss(tmp_path):
    h = make_harness(tmp_path, prices={"AAA": 100.0}, actions={"AAA": Action.BUY},
                     risk=RiskConfig(risk_per_trade_pct=10.0, max_position_pct=50.0, stop_loss_pct=5.0,
                                     max_daily_loss_pct=3.0))
    assert statuses(h.tick()) == [("AAA", "buy", "filled")]  # 50 AAA, 5,000 cash left
    h.strategy.actions["AAA"] = Action.HOLD
    real = h.broker.submit_order
    h.broker.submit_order = lambda order: (real(order) if order.side is Side.BUY else OrderResult(
        "", order.symbol, order.side, order.qty, "rejected", reason="no shares available"))
    h.feed.prices["AAA"] = 94.0
    h.clock.advance(minutes=5)
    assert statuses(h.tick()) == [("AAA", "sell", "rejected")]
    h.broker._cash += 5_000.0  # a deposit ...
    h.feed.prices["AAA"] = 80.0  # ... and a loss of 1,000 on the day (-6.7% of 15,000)
    h.clock.advance(minutes=5)

    report = h.tick()

    assert h.state().external_flow == pytest.approx(5_000.0)
    assert report.halted is True


def test_a_buy_still_working_from_an_earlier_tick_counts_toward_the_position_limit(tmp_path):
    prices = {"AAA": 100.0, "BBB": 100.0}
    broker = AcceptingBroker(FakeFeed(Clock(T0), prices), cash=10_000.0)
    h = make_harness(tmp_path, prices=prices, actions={"AAA": Action.BUY}, broker=broker,
                     risk=RiskConfig(max_open_positions=1, max_total_exposure_pct=20.0, stop_loss_pct=None,
                                     max_daily_loss_pct=None, cash_buffer_pct=0.0))
    h.engine.broker.feed = h.feed
    assert [(o.symbol, o.status) for o in h.tick().orders] == [("AAA", "accepted")]
    h.strategy.actions = {"BBB": Action.BUY}
    h.clock.advance(hours=1)  # a new bar; AAA's buy is still working (a trading halt)

    report = h.tick()

    assert report.orders == []
    assert "max open positions" in report.signals["BBB"]


def test_after_a_lost_state_the_first_look_at_the_holdings_says_there_is_no_record(tmp_path):
    # The state is lost and the bot restarts while the market is closed.
    h = _stop_harness(tmp_path)
    h.tick()
    h.store.path.unlink()
    h.strategy.actions["AAA"] = Action.HOLD
    engine = TradingEngine(h.cfg, h.broker, h.strategy, RiskManager(h.cfg.risk), h.store, h.notifier,
                           clock=h.clock)
    h.feed.market_open = False
    h.clock.advance(minutes=5)
    assert engine.run_once().skipped == "market_closed"
    h.feed.market_open = True
    h.clock.advance(minutes=5)
    engine.run_once()

    (notice,) = [m for m in h.notifier.errors if m.startswith("AAA")]
    assert "no record" in notice and "did not buy" not in notice


def test_a_state_older_than_the_account_is_not_traded_on(tmp_path):
    # Run N sells the bot's 10 AAA by its stop-loss, but its state is not saved
    # (a failed GitHub Actions cache save): run N+1 gets run N-1's state back.
    h = _stop_harness(tmp_path)
    sent: list[str] = []
    real = h.broker.submit_order

    def recording(order: OrderRequest) -> OrderResult:
        sent.append(order.client_order_id)
        return real(order)

    h.broker.submit_order = recording
    h.broker.latest_bot_order_id = lambda: sent[-1] if sent else None

    def run() -> TickReport:  # each `once` run is a new process
        h.clock.advance(minutes=15)
        return TradingEngine(h.cfg, h.broker, h.strategy, RiskManager(h.cfg.risk), h.store, h.notifier,
                             clock=h.clock).run_once()

    assert statuses(run()) == [("AAA", "buy", "filled")]
    h.strategy.actions["AAA"] = Action.HOLD
    h.buy("AAA", 5)  # the user's own 5
    assert run().orders == []  # a restart with a current state trades as usual
    older = h.store.path.read_bytes()
    h.feed.prices["AAA"] = 94.0
    assert statuses(run()) == [("AAA", "sell", "filled")]
    h.store.path.write_bytes(older)  # run N's save was lost

    report = run()

    assert report.orders == [] and report.failed is True
    assert any("does not know" in e for e in report.errors)
    assert h.broker.get_positions()["AAA"].qty == pytest.approx(5.0)
