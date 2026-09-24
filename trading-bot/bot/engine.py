"""The live trading loop.

One :meth:`TradingEngine.run_once` tick reads the account, applies the daily
limits, and for every configured symbol fetches CLOSED bars, asks the strategy
for a signal, sizes it with the :class:`~bot.risk.RiskManager` and sends a
market order. :meth:`TradingEngine.run_forever` repeats that on a timer.

Safety rules enforced here, on top of the risk manager and broker adapters:

* kill switch file present -> the tick does nothing, not even API reads;
* the bot manages, and ever sells, only what it bought itself (``BotState.owned``,
  from its own orders): a holding already in the account, even in one of the
  configured symbols, is left alone and blocks new entries in that symbol,
  unless ``adopt_existing_positions`` is set (a local paper account holds only
  the bot's own trades, so there it manages everything); a short position a
  person opened on a margin account also blocks entries (a BUY would cover it);
* an order whose reply was lost (a timeout: it may have reached the broker) is
  booked as sent, so a BUY that did fill keeps its stop-loss; a SELL comes off
  the bot's record only as far as it fills (one that expires unfilled is sent
  again); a stock split rescales the record instead of looking like a crash;
* protective stops (stop-loss / take-profit) are checked every tick, FIRST:
  before any open-order, candle-data or warm-up check that could hold them up;
  when the latest price cannot be read, against the broker's position price;
* no new order for a symbol while one of the bot's own orders is still working;
  an order someone else placed (e.g. by hand) blocks new entries, never exits;
* each closed bar is evaluated once;
* daily loss limit hit -> no new entries for the rest of the day (exits still
  run); the optional flatten sells only the bot's positions and cancels only
  its own working orders; money that moves in or out of the account without
  the bot trading (a deposit, a withdrawal, a trade in an asset the bot does
  not value) is not counted as a gain or loss (measured only between ticks
  with no order of the bot's in flight, whose account and positions reads
  cannot straddle one of its fills);
* account and positions are re-read after every order, so the next symbol is
  sized against the cash that is really left, and BUYs the broker accepted but
  has not filled yet still count toward the position/exposure/cash limits; if
  that re-read (or an order submission) fails, or a holding could not be
  priced, no further entries are made in this tick;
* the state file is saved before any order, and again around each order
  (booked as sent before it goes out, as reported once its reply is in), so a
  crash mid-tick never forgets what the bot bought: if saving fails, the
  counters are kept in memory and no new entries are made until a save
  succeeds; if it cannot be read, no new entries either; exits and
  stop-losses still run;
* order sizes are rounded DOWN and never exceed what was sized or held.
"""
from __future__ import annotations

import copy
import csv
import logging
import math
import re
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import pandas as pd

from .brokers.base import BOT_ORDER_PREFIX, BrokerError, OpenOrder
from .models import Account, Action, OrderRequest, OrderResult, Position, Side, Signal
from .state import BotState, kill_switch_active, loss_baseline
from .utils import drop_incomplete_bars, timeframe_to_timedelta, utcnow, validate_bars

if TYPE_CHECKING:
    from .brokers.base import Broker
    from .config import BotConfig
    from .notify import Notifier
    from .risk import RiskManager
    from .state import StateStore
    from .strategies.base import Strategy

logger = logging.getLogger(__name__)

TRADES_FILE = "trades.csv"
TRADE_COLUMNS = ("time", "mode", "symbol", "side", "qty", "filled_qty", "status",
                 "filled_avg_price", "reason", "order_id", "client_order_id")
MAX_BACKOFF_SECONDS = 900
ERROR_ALERT_AFTER = 3      # notify when this many ticks in a row had errors ...
ERROR_ALERT_EVERY = 10     # ... and again every this many ticks after that
_CLIENT_ID_BASE_LEN = 48
# last_signal_bar value after a protective exit made while the bars could not
# be loaded: "stop@<ISO time>". Bars that had already closed by then count as
# evaluated, so the strategy does not re-enter on them right after the stop.
_STOP_MARK = "stop@"
# Relative slack when comparing a holding with what the bot owns (float noise).
_QTY_TOLERANCE = 1e-9
# Money moved without trading is logged when it is at least this share of equity.
_FLOW_LOG_SHARE = 0.001
# What an order books in the state (restored when its reply replaces the write-ahead booking).
_LEDGER_FIELDS = ("owned", "unsettled", "pending_orders", "seen_holdings", "trades_today")
# A holding whose quantity changed by at least this factor while its cost
# (qty x the broker's average price) stayed within _SPLIT_COST_TOLERANCE is
# taken to be a stock split (or another corporate action of that kind).
_SPLIT_MIN_CHANGE = 0.05
_SPLIT_COST_TOLERANCE = 0.01


@dataclass
class TickReport:
    started_at: datetime
    skipped: str | None = None          # "kill_switch" | "trading_blocked" | "market_closed" | None
    orders: list[OrderResult] = field(default_factory=list)
    signals: dict[str, str] = field(default_factory=dict)   # symbol -> "buy: reason" etc.
    errors: list[str] = field(default_factory=list)
    equity: float | None = None
    halted: bool = False
    # True when the tick as a whole failed (kill switch check, account/
    # positions/market clock read, or an unexpected error), as opposed to
    # errors confined to single symbols or to the local state file. Only this
    # slows the loop down (it is there to spare a failing broker API).
    failed: bool = False


@dataclass
class _Tick:
    """Mutable working set of one tick."""
    state: BotState
    report: TickReport
    account: Account
    # Every long holding the broker reports (the bot's or not): sizing counts
    # all of them toward the position and exposure limits.
    holdings: dict[str, Position]
    # The part of `holdings` the bot manages: configured symbols, at most the
    # quantity it bought itself (see TradingEngine._managed_positions).
    positions: dict[str, Position]
    # Set when something makes the account snapshot untrustworthy for the rest
    # of the tick (failed re-read or failed order submission). Exits still run.
    entries_blocked: str | None = None
    # The state file could not be read and nothing was left in memory: which
    # holdings the bot bought is unknown this tick.
    ledger_unknown: bool = False
    # BUYs sent this tick that the broker accepted but has not filled yet, so
    # its positions (and, on Alpaca, its cash) do not show them.
    pending: dict[str, Position] = field(default_factory=dict)
    # Symbols the bot sent an order for this tick.
    ordered: set[str] = field(default_factory=set)
    # Short positions (qty < 0) a person holds on a margin account.
    shorts: dict[str, Position] = field(default_factory=dict)
    # An order of the bot's was still settling when the tick started, so it
    # may fill between the account and the positions reads.
    settling: bool = False
    # False when the state file could not be read: it is never overwritten then.
    may_save: bool = True


class TradingEngine:
    def __init__(self, cfg: BotConfig, broker: Broker, strategy: Strategy, risk: RiskManager,
                 state_store: StateStore, notifier: Notifier, clock: Callable[[], datetime] = utcnow) -> None:
        self.cfg = cfg
        self.broker = broker
        self.strategy = strategy
        self.risk = risk
        self.store = state_store
        self.notifier = notifier
        self.clock = clock
        self.tz = ZoneInfo(cfg.timezone)
        self.trades_path = Path(cfg.log_dir) / TRADES_FILE
        # Trading day on which the daily-loss flatten completed. In memory only:
        # after a restart a halted day with open positions is flattened again.
        self._flattened_day: str | None = None
        # Errors from the previous tick: an identical error is notified once, not every tick.
        self._recent_errors: set[str] = set()
        self._tick_errors: set[str] = set()
        # The state of a tick whose save failed. It is used instead of the (older)
        # file until a save works again, so the daily counters are never lost.
        self._unsaved_state: BotState | None = None
        # The last state loaded or saved: stands in when the file cannot be read.
        self._last_state: BotState | None = None

    # ------------------------------------------------------------------ public
    def run_once(self) -> TickReport:
        """One pass over all symbols. Never raises for broker/API errors: they
        are logged, notified and listed in ``report.errors``."""
        now = self._now()
        report = TickReport(started_at=now)
        self._tick_errors = set()
        try:
            killed = kill_switch_active(self.cfg.state_dir)
        except OSError as exc:
            report.failed = True
            self._error(report, f"cannot check the kill switch in {self.cfg.state_dir} ({exc}); not trading")
            return self._end_tick(report)
        if killed:
            logger.warning("Kill switch is ON (%s): skipping tick, no orders sent", Path(self.cfg.state_dir) / "KILL")
            report.skipped = "kill_switch"
            return self._end_tick(report)

        unreadable = blank = False
        if self._unsaved_state is not None:
            # The file is older than what we know: keep counting from memory.
            state = self._unsaved_state
        else:
            try:
                state = self.store.load()
            except Exception as exc:  # e.g. permission denied
                # No new entries without the counters, but stop-losses and exits
                # still run: with what the bot last knew, else a blank state
                # (then it cannot tell which holdings it bought on a real account).
                last = self._last_state
                unreadable, blank = True, last is None
                state = BotState() if last is None else copy.deepcopy(last)
                self._error(report, f"could not load bot state ({_describe(exc)}); no new entries until it can "
                                    f"be read ({self._unreadable_exits_note()})", exc)

        # Fail closed: the counters (today's trades, the loss halt, the evaluated
        # bars, what the bot bought) must be on disk before any order, or a
        # restart or the next `once` would forget them.
        save_failed = not unreadable and not self._save(state, report)
        try:
            self._tick(state, report, unreadable=unreadable, ledger_unknown=blank)
        except Exception as exc:
            report.failed = True
            self._error(report, _describe(exc), exc)

        state.consecutive_errors = state.consecutive_errors + 1 if report.errors else 0
        state.last_tick_at = now.isoformat()
        report.halted = state.halted_today
        if not unreadable:  # never overwrite a file that could not be read (it may be fine)
            self._save(state, report, quiet=save_failed)
        if not blank:
            self._last_state = state
        return self._end_tick(report)

    def _save(self, state: BotState, report: TickReport, quiet: bool = False) -> bool:
        """Save the state. A failure (local disk/permissions, not the broker) is
        reported but does not slow the loop: it keeps the state in memory and
        pauses new entries until a save works again."""
        try:
            self.store.save(state)
        except Exception as exc:
            self._unsaved_state = state
            message = (f"could not save bot state ({_describe(exc)}); new entries are paused until it can be "
                       "saved (exits and stop-losses still run)")
            if quiet:
                logger.error("%s", message)
            else:
                self._error(report, message, exc)
            return False
        if self._unsaved_state is not None:
            logger.warning("Bot state saved again; new entries are allowed")
        self._unsaved_state = None
        return True

    def _unreadable_exits_note(self) -> str:
        if self._last_state is not None or self._adopts_all():
            return "stop-losses and exits still run"
        return ("stop-losses and exits run only once it can be read: without it the bot cannot tell which "
                "holdings it bought itself")

    def run_forever(self, stop_event: threading.Event | None = None, max_ticks: int | None = None) -> None:
        """Run ticks every ``poll_interval_seconds`` until ``stop_event`` is set
        (or ``max_ticks`` ticks ran). Waits on the event, so a signal handler
        that sets it stops the loop promptly. Backs off after ticks that failed
        as a whole (``TickReport.failed``, a broker/API or unexpected failure);
        errors confined to one symbol or to the local state file keep the
        normal interval so the positions' stops are still checked on time.
        Repeated errors of any kind are notified."""
        stop = stop_event if stop_event is not None else threading.Event()
        poll = self.cfg.poll_interval_seconds
        ticks = failures = error_ticks = 0
        logger.info("Trading loop started: %s mode, %s, every %ss", self.cfg.mode.upper(),
                    ", ".join(self.cfg.symbols), poll)
        while not stop.is_set():
            try:
                report = self.run_once()
                failed, errors = report.failed, list(report.errors)
            except Exception as exc:  # a bug: keep the loop alive, keep the traceback
                logger.exception("Unexpected error in trading tick; the loop keeps running")
                message = f"unexpected error in trading tick: {type(exc).__name__}: {exc}"
                if message not in self._recent_errors:
                    self.notifier.error(message)
                self._recent_errors = {message}
                failed, errors = True, [message]
            ticks += 1
            # Only a failure of the tick as a whole backs off: errors confined to
            # one symbol must not delay the other positions' stop-loss checks.
            failures = failures + 1 if failed else 0
            error_ticks = error_ticks + 1 if errors else 0
            if error_ticks == ERROR_ALERT_AFTER or (
                    error_ticks > ERROR_ALERT_AFTER and (error_ticks - ERROR_ALERT_AFTER) % ERROR_ALERT_EVERY == 0):
                self.notifier.error(f"{error_ticks} ticks in a row had errors; still retrying. "
                                    f"Latest: {'; '.join(errors)}")
            if max_ticks is not None and ticks >= max_ticks:
                break
            delay = backoff_seconds(poll, failures)
            if failures:
                logger.warning("Tick failed (%d in a row); next try in %.0fs", failures, delay)
            if stop.wait(delay):
                break
        logger.info("Trading loop stopped after %d tick(s)", ticks)

    # ------------------------------------------------------------------ tick
    def _tick(self, state: BotState, report: TickReport, unreadable: bool = False,
              ledger_unknown: bool = False) -> None:
        account = self.broker.get_account()
        report.equity = account.equity
        if account.trading_blocked:
            logger.warning("The broker reports trading is blocked on this account; skipping tick")
            report.skipped = "trading_blocked"
            return
        fresh_baseline = self._roll_day(state, account)
        if not self.broker.is_market_open():
            logger.info("Market is closed; nothing to do this tick")
            report.skipped = "market_closed"
            return

        holdings, shorts = self._read_holdings()
        tick = _Tick(state, report, account, holdings, {}, ledger_unknown=ledger_unknown, shorts=shorts,
                     settling=any(symbol in self.cfg.symbols for symbol in state.unsettled), may_save=not unreadable)
        self._reconcile_ledger(tick)
        tick.positions = self._managed_positions(state, holdings)
        if unreadable:
            tick.entries_blocked = "the bot state file could not be read"
        elif self._unsaved_state is not None:
            tick.entries_blocked = "the bot state file could not be saved"
        if not fresh_baseline and not tick.settling:
            self._track_external_flows(tick)
        self._check_priced(tick)
        self._check_daily_loss(tick)
        for symbol in self.cfg.symbols:
            try:
                self._process_symbol(symbol, tick)
            except Exception as exc:  # one bad symbol must not stop the others
                self._error(report, f"{symbol}: {_describe(exc)}", exc)
        self._report_unmanaged(tick)
        self._remember_holdings(tick)
        state.warned_short_history = [s for s in state.warned_short_history if s in self.cfg.symbols]
        report.equity = tick.account.equity

    def _roll_day(self, state: BotState, account: Account) -> bool:
        """Start a new trading day (or account) when due. True when the loss
        baseline was just set from the current equity, which then already
        includes any money moved since the last tick."""
        today = self._now().astimezone(self.tz).date().isoformat()
        key = self._account_key(account)
        broker_start = _positive(account.day_start_equity)
        start = broker_start or (None if account.unpriced else _positive(account.equity))
        switched = state.account_key is not None and state.account_key != key
        fresh = False
        if switched:
            # What the bot bought in the other account is not in this one.
            state.owned, state.unsettled, state.notified_unmanaged = {}, [], []
            state.pending_orders, state.seen_holdings = {}, {}
        if state.day != today or switched:
            if state.day == today:
                logger.warning("The account changed (%s -> %s): today's counters, the loss baseline and the "
                               "record of what the bot bought start over", state.account_key, key)
            else:
                logger.info("New trading day %s (%s); day start equity %s", today, self.cfg.timezone, start)
            state.day, state.day_start_equity = today, start
            state.trades_today, state.halted_today = 0, False
            state.external_flow, state.flow_cash, state.flow_holdings = 0.0, None, {}
            fresh = broker_start is None
        elif broker_start is not None:
            # The broker's own previous-close equity (Alpaca last_equity) always
            # wins over a stored value, which may come from another account.
            state.day_start_equity = broker_start
        elif state.day_start_equity is None:  # equity was unusable when the day started
            state.day_start_equity = start
            state.external_flow = 0.0
            fresh = start is not None
        state.account_key = key
        return fresh

    def _account_key(self, account: Account) -> str:
        return account_key(self.cfg, account.currency)

    def _check_priced(self, tick: _Tick) -> None:
        if tick.account.unpriced and not tick.entries_blocked:
            names = ", ".join(tick.account.unpriced)
            logger.warning("Could not price %s: no new entries this tick (exits still run)", names)
            tick.entries_blocked = f"could not get a price for {names}, so the account value is uncertain"

    def _check_daily_loss(self, tick: _Tick) -> None:
        state, cfg = tick.state, self.risk.config
        start = loss_baseline(state)
        # An incomplete valuation (a holding could not be priced) never trips the
        # limit or a flatten; entries are already blocked for such a snapshot.
        if (not state.halted_today and start and not tick.account.unpriced
                and self.risk.daily_loss_breached(tick.account.equity, start)):
            state.halted_today = True
            change = (tick.account.equity / start - 1.0) * 100.0
            action = "closing the bot's positions" if cfg.flatten_on_daily_loss else "open positions are kept"
            moved = (f", after {state.external_flow:+,.2f} moved in/out without trading"
                     if state.external_flow else "")
            self.notifier.error(
                f"Daily loss limit hit: equity {tick.account.equity:,.2f} is {change:.2f}% vs "
                f"{start:,.2f} at the start of {state.day}{moved} (limit -{cfg.max_daily_loss_pct}%). "
                f"No new entries until tomorrow; {action}.")
        if state.halted_today and cfg.flatten_on_daily_loss and self._flattened_day != state.day:
            self._flatten(tick)

    def _flatten(self, tick: _Tick) -> None:
        """Sell the bot's positions (never other holdings in the account, nor
        the part of a holding it did not buy) and cancel the bot's own working
        BUYs in the configured symbols. Orders someone else placed (e.g. a
        person's stop order on shares the bot does not manage) are left alone,
        and a position the bot is already selling is not sold twice. Marked
        done only when every sell went through, so a rejected one (or one still
        working) is looked at again next tick."""
        held = [symbol for symbol in self.cfg.symbols if symbol in tick.positions]
        if held:
            logger.warning("Daily loss limit: closing the bot's positions (%s)", ", ".join(held))
        done = True
        stamp = self._now().isoformat()
        for symbol in self.cfg.symbols:
            working: list[OpenOrder] = []
            try:
                working = self.broker.open_orders(symbol)
                self._note_settled(tick, symbol, working)
                mine = [order for order in working if order.placed_by_bot]
                if symbol in tick.positions and any(order.side is Side.SELL for order in mine):
                    done = False  # already being sold
                    continue
                if self._cancel_own_buys(symbol, mine) and symbol in tick.positions:
                    done = False  # sold once that buy has settled: how much of the holding is the bot's is open
                    continue
            except Exception as exc:
                done = False
                self._error(tick.report, f"{symbol}: checking or cancelling the bot's own orders for the daily-loss "
                                         f"flatten failed (retrying next tick): {_describe(exc)}", exc)
                if self._has_pending(tick.state, symbol):
                    continue  # an earlier order of the bot's may have filled: never sell blind (the user's shares)
            pos = tick.positions.get(symbol)
            if pos is None:
                continue
            try:
                result = self._sell(tick, pos, "daily loss limit: flatten", stamp)
            except Exception as exc:
                done = False
                self._error(tick.report, f"{symbol}: daily-loss flatten sell failed (retrying next tick): "
                                         f"{_describe(exc)}", exc)
                continue
            if result is not None and not result.ok:
                done = False
                others = ", ".join(order.id or "?" for order in working if not order.placed_by_bot)
                if others:
                    self._error(tick.report, f"{symbol}: the daily-loss flatten sell was rejected while an order not "
                                             f"placed by this bot is working on {symbol} ({others}); it may be "
                                             "locking the position. Cancel it or sell by hand.")
        if done:
            self._flattened_day = tick.state.day

    def _cancel_own_buys(self, symbol: str, mine: list[OpenOrder]) -> bool:
        """Cancel the bot's own working BUYs on ``symbol`` (a fill would open a
        new position on a day it stopped trading). Its SELLs keep working.
        True when it cancelled any."""
        buys = [order for order in mine if order.side is not Side.SELL]
        for order in buys:
            if order.id:
                self.broker.cancel_order(symbol, order.id)
            else:  # an adapter that cannot identify its orders (it only reports has_open_orders)
                self.broker.cancel_orders([symbol])
        return bool(buys)

    def _process_symbol(self, symbol: str, tick: _Tick) -> None:
        report, state = tick.report, tick.state
        pos = tick.positions.get(symbol)
        if pos is not None:
            price, price_error = self._position_price(tick, pos)
            pos = replace(pos, market_price=price)
            exit_reason = self.risk.exit_reason(pos, price)
            if exit_reason:  # checked every tick, even mid-bar, before anything that could hold it up
                try:
                    self._protective_exit(tick, pos, exit_reason)
                finally:
                    if price_error is not None:
                        raise price_error
                return
            if price_error is not None:  # no fresh price: nothing else to decide on this tick
                raise price_error

        working = self.broker.open_orders(symbol)
        if self._note_settled(tick, symbol, working) and pos is not None:
            # A sell of the bot's just settled: go on with what is left of the position.
            left = tick.positions.get(symbol)
            pos = None if left is None else replace(left, market_price=pos.market_price)
        if any(order.placed_by_bot for order in working):
            report.signals[symbol] = "skip: an earlier order from this bot is still pending"
            return
        bars = self._closed_bars(symbol)
        needed = max(int(self.strategy.min_bars), 1)
        if len(bars) < needed:
            report.signals[symbol] = f"warming up ({len(bars)}/{needed} closed bars)"
            self._warn_short_history(state, symbol, len(bars), needed)
            return
        if symbol in state.warned_short_history:
            state.warned_short_history.remove(symbol)
        bar_key = bars.index[-1].isoformat()
        if self._already_evaluated(state, symbol, bars.index[-1]):
            state.last_signal_bar[symbol] = bar_key
            report.signals[symbol] = f"hold: waiting for the next bar ({bar_key} already evaluated)"
            return

        signal = self.strategy.generate_signal(bars, pos)
        text = f"{signal.action.value}: {signal.reason}" if signal.reason else signal.action.value
        report.signals[symbol] = text
        logger.info("%s %s -> %s", symbol, bar_key, text)
        evaluated = True
        if signal.action is Action.SELL and pos is not None:
            self._sell(tick, pos, signal.reason or "strategy exit", bar_key)
        elif signal.action is Action.BUY and pos is None:
            if working:  # only orders the bot did not place are left here
                report.signals[symbol] = (f"{text} (not entering: an open order not placed by this bot is "
                                          f"working on {symbol}; the bot enters once it is gone)")
                evaluated = False
            else:
                evaluated = self._enter(tick, symbol, signal, text, bar_key)
        if evaluated:
            state.last_signal_bar[symbol] = bar_key

    def _position_price(self, tick: _Tick, pos: Position) -> tuple[float, Exception | None]:
        """(latest price, None); when the price read fails, (the broker's own
        position price, the error), so a stop-loss does not depend on a second
        API (Alpaca prices positions on its trading API, quotes on its market-
        data API). Not for a holding the broker could not price itself."""
        try:
            return self.broker.get_latest_price(pos.symbol), None
        except Exception as exc:
            fallback = _positive(pos.market_price)
            if fallback is None or pos.symbol in tick.account.unpriced:
                raise
            logger.warning("%s: latest price unavailable (%s); checking the stop-loss/take-profit against the "
                           "broker's position price %g", pos.symbol, _describe(exc), fallback)
            return fallback, exc

    def _warn_short_history(self, state: BotState, symbol: str, have: int, needed: int) -> None:
        """Once per symbol (kept in the state, so `once` runs do not repeat it;
        again if it warms up and later runs short): a symbol stuck warming up
        never trades, and `run` shows no signals, so say so instead of only
        reporting "0 orders"."""
        if symbol in state.warned_short_history:
            return
        state.warned_short_history.append(symbol)
        timeframe, strategy = self.cfg.timeframe, getattr(self.strategy, "name", "the strategy")
        message = (f"{symbol}: only {have} closed {timeframe} bars are available (asked for "
                   f"{self.cfg.bars_lookback}), but {strategy} needs {needed}, so the bot does not trade "
                   f"{symbol} until there is enough history. If the venue caps its history (some return at "
                   "most 200 candles), it never will: lower the strategy's periods or use a longer timeframe.")
        logger.warning("%s", message)
        self.notifier.error(message)

    def _protective_exit(self, tick: _Tick, pos: Position, reason: str) -> None:
        """Stop-loss / take-profit sell. Neither a working order someone else
        placed nor missing candle data may hold it up; only the bot's own
        working SELL does (it is already exiting). Problems reading orders or
        bars are raised after the sell, so they are still reported."""
        symbol, report = pos.symbol, tick.report
        report.signals[symbol] = (f"sell: {reason} (price {pos.market_price:.6g}, "
                                  f"entry {pos.avg_entry_price:.6g})")
        problems: list[Exception] = []
        try:
            working = self.broker.open_orders(symbol)
        except Exception as exc:  # unknown: sell anyway (brokers cap a sell at what is available) ...
            if self._has_pending(tick.state, symbol):
                raise  # ... unless an earlier order of the bot's may have filled: never sell blind
            working = []
            problems.append(exc)
        else:
            if self._note_settled(tick, symbol, working):
                left = tick.positions.get(symbol)
                if left is None:
                    report.signals[symbol] += " (the bot's earlier order leaves it nothing to sell)"
                    return
                pos = replace(left, market_price=pos.market_price)
        mine = [order for order in working if order.placed_by_bot]
        if any(order.side is Side.SELL for order in mine):
            report.signals[symbol] += " (an exit order from this bot is already working)"
            return
        if mine:  # its BUY: until it fills, the holding may also be shares someone else bought meanwhile
            what = "buy" if any(order.side is Side.BUY for order in mine) else "order"
            report.signals[symbol] += f" (not yet: the bot's own {what} is still working; checked again once it fills)"
            return
        bar_key = None
        try:
            bars = self._closed_bars(symbol)
            bar_key = bars.index[-1].isoformat() if len(bars) else None
        except Exception as exc:
            problems.append(exc)
        result = self._sell(tick, pos, reason, bar_key or self._now().isoformat())
        if result is not None:
            # Deliberately marked: the protective exit is this bar's decision, so
            # the strategy is not asked to re-enter on the same closed bar right
            # after a stop-out (fee churn). Without bars, the stop time is kept.
            tick.state.last_signal_bar[symbol] = bar_key or f"{_STOP_MARK}{self._now().isoformat()}"
        others = [order for order in working if not order.placed_by_bot]
        if others and result is not None:
            ids = ", ".join(order.id or "?" for order in others)
            if result.ok:
                self.notifier.error(f"{symbol}: {reason} triggered while an order not placed by this bot is "
                                    f"working on {symbol} ({ids}); the bot sold anyway and left that order in "
                                    "place. Check it.")
            else:
                self._error(report, f"{symbol}: {reason} sell was rejected while an order not placed by this bot "
                                    f"is working on {symbol} ({ids}); it may be locking the position. Cancel it "
                                    "or sell by hand.")
        if problems:
            raise problems[0]

    def _already_evaluated(self, state: BotState, symbol: str, bar_open: pd.Timestamp) -> bool:
        mark = state.last_signal_bar.get(symbol)
        if mark is None:
            return False
        if mark == bar_open.isoformat():
            return True
        if not mark.startswith(_STOP_MARK):
            return False
        try:
            stopped_at = pd.Timestamp(mark[len(_STOP_MARK):])
            if stopped_at.tzinfo is None:
                stopped_at = stopped_at.tz_localize("UTC")
            return bar_open + timeframe_to_timedelta(self.cfg.timeframe) <= stopped_at
        except (ValueError, TypeError):
            return False

    def _closed_bars(self, symbol: str) -> pd.DataFrame:
        lookback, timeframe = self.cfg.bars_lookback, self.cfg.timeframe
        bars = validate_bars(self.broker.get_bars(symbol, timeframe, lookback + 1))
        return drop_incomplete_bars(bars, timeframe, self._now()).tail(lookback)

    def _sell(self, tick: _Tick, pos: Position, reason: str, bar_key: str) -> OrderResult | None:
        """Sell the whole (managed) position: rounded down to the venue's step,
        never more than the bot holds. None when that rounds down to nothing."""
        qty = min(self.broker.normalize_qty(pos.symbol, pos.qty), pos.qty)
        if not qty > 0:
            logger.warning("%s: position of %g rounds down to 0; cannot sell it", pos.symbol, pos.qty)
            signals = tick.report.signals
            signals[pos.symbol] = signals.get(pos.symbol, "sell") + f" (not selling: {pos.qty:g} rounds down to 0)"
            return None
        return self._submit(tick, pos.symbol, Side.SELL, qty, reason, bar_key, pos.market_price)

    def _enter(self, tick: _Tick, symbol: str, signal: Signal, text: str, bar_key: str) -> bool:
        """Try a new long entry. Returns False only when a temporary problem
        blocked it (so the bar is evaluated again next tick)."""
        state, cfg, report = tick.state, self.risk.config, tick.report
        held = tick.holdings.get(symbol)
        if state.halted_today:
            blocked = "daily loss limit hit, no new entries today"
        elif state.trades_today >= cfg.max_trades_per_day:
            blocked = f"max trades per day reached ({state.trades_today}/{cfg.max_trades_per_day})"
        elif held is not None and not tick.ledger_unknown:
            blocked = (f"the account already holds {held.qty:.8g} {_units(symbol)} that this bot did not buy; "
                       "it does not add to a holding it does not manage")
        elif symbol in tick.shorts:
            blocked = (f"the account is short {-tick.shorts[symbol].qty:.8g} {_units(symbol)} (not opened by this "
                       "bot); a buy would cover it")
        elif tick.entries_blocked:
            report.signals[symbol] = f"{text} (not entering this tick: {tick.entries_blocked})"
            return False
        else:
            blocked = None
        if blocked:
            report.signals[symbol] = f"{text} (not entering: {blocked})"
            logger.info("%s: buy signal ignored: %s", symbol, blocked)
            return True

        price = self.broker.get_latest_price(symbol)
        broker_min = self.broker.min_order_notional(symbol)
        account, positions = self._sizing_view(tick)
        qty, why = self.risk.entry_qty(symbol, price, signal, account, positions, broker_min)
        if qty > 0:
            sized = qty
            qty = min(self.broker.normalize_qty(symbol, qty), sized)
            minimum = max(cfg.min_order_notional, broker_min)
            if not qty > 0 or qty * price < minimum:
                why = (f"{sized:.6g} rounds down to {qty:.6g} = {max(qty, 0.0) * price:.2f}, "
                       f"below the minimum order {minimum:.2f}")
                qty = 0.0
            elif qty < sized * (1.0 - 1e-4):  # only worth mentioning when it changes the size noticeably
                why = f"{why}; rounded down to {qty:.8g}"
        if not qty > 0:
            report.signals[symbol] = f"{text} (not entering: {why})"
            logger.info("%s: buy signal not taken: %s", symbol, why)
            return True
        report.signals[symbol] = f"{text} ({why})"
        result = self._submit(tick, symbol, Side.BUY, qty, signal.reason or "strategy entry", bar_key, price)
        if result.ok and result.status != "filled":
            tick.pending[symbol] = Position(symbol, qty, price, price)
        return True

    def _sizing_view(self, tick: _Tick) -> tuple[Account, dict[str, Position]]:
        """Account and positions to size a new entry against: the broker's, plus
        this tick's accepted-but-unfilled BUYs, which count toward the position
        and exposure limits and come out of cash. (Alpaca and ccxt already take
        working orders out of buying power, but not out of cash.)"""
        waiting = {s: p for s, p in tick.pending.items() if s not in tick.holdings}
        if not waiting:
            return tick.account, tick.holdings
        reserved = sum(p.market_value for p in waiting.values())
        account = replace(tick.account, cash=max(0.0, tick.account.cash - reserved))
        return account, {**waiting, **tick.holdings}

    def _submit(self, tick: _Tick, symbol: str, side: Side, qty: float, reason: str, bar_key: str,
                ref_price: float) -> OrderResult:
        """Send one market order. A BUY counts toward today's trades once sent.

        Write-ahead: the order is booked as sent with its outcome unknown, and
        saved, BEFORE it goes out. A crash or kill while it is in flight, or a
        reply that is lost (a timeout: it may have reached the broker), then
        still leaves it booked: a BUY that filled keeps its stop-loss, a SELL
        that filled is not counted as the bot's any more. The symbol stays
        unsettled until no order of the bot's is working on it; then the record
        is corrected to what the broker reports filled (looked up by the client
        order id), else to how the holding changed. Once the reply is in, the
        order is booked as reported instead, and saved again."""
        order = OrderRequest(symbol=symbol, side=side, qty=qty, reason=reason,
                             client_order_id=make_client_order_id(symbol, side, bar_key))
        state = tick.state
        tick.ordered.add(symbol)
        logger.info("Submitting %s %.8g %s (%s) [%s]", side.value.upper(), qty, symbol, reason, order.client_order_id)
        before = {name: copy.deepcopy(getattr(state, name)) for name in _LEDGER_FIELDS}
        self._record_in_ledger(tick, OrderResult("", symbol, side, qty, "accepted", reason="in flight"), ref_price,
                               order.client_order_id)
        if side is Side.BUY:
            state.trades_today += 1
        self._save_around_order(tick)
        try:
            result = self.broker.submit_order(order)
        except Exception:
            # Cash is uncertain now: size nothing else against it this tick. The
            # entry is retried on the same bar, so it is not counted yet.
            state.trades_today = before["trades_today"]
            tick.entries_blocked = f"an order for {symbol} failed to submit"
            raise
        for name, value in before.items():
            setattr(state, name, value)
        self._record_in_ledger(tick, result, ref_price, order.client_order_id)
        if side is Side.BUY and result.ok:
            state.trades_today += 1
        self._save_around_order(tick)
        self._record_order(tick, result, reason, order.client_order_id)
        self._refresh(tick)
        return result

    def _save_around_order(self, tick: _Tick) -> None:
        """Save what an order booked right away, not only at the end of the
        tick. A failure is reported by the end-of-tick save; it pauses new
        entries for the rest of the tick. Never over a file that could not be read."""
        if tick.may_save and not self._save(tick.state, tick.report, quiet=True):
            tick.entries_blocked = tick.entries_blocked or "the bot state file could not be saved"

    def _refresh(self, tick: _Tick) -> None:
        try:
            tick.account = self.broker.get_account()
            tick.holdings, tick.shorts = self._read_holdings()
            tick.positions = self._managed_positions(tick.state, tick.holdings)
        except Exception as exc:
            tick.entries_blocked = "could not re-read the account after an order"
            self._error(tick.report, f"could not refresh account/positions after an order: {_describe(exc)}", exc)
            return
        self._check_priced(tick)

    def _read_holdings(self) -> tuple[dict[str, Position], dict[str, Position]]:
        """The account's long holdings, and the short positions a person holds
        (a margin account) from the same read."""
        holdings = self._open_positions()
        return holdings, {s: p for s, p in self.broker.short_positions().items() if p.qty < 0}

    def _open_positions(self) -> dict[str, Position]:
        return {symbol: pos for symbol, pos in self.broker.get_positions().items() if pos.qty > 0}

    # ------------------------------------------------------------------ what the bot owns
    def _adopts_all(self) -> bool:
        """Manage every holding in the configured symbols: opted in, or a local
        paper account (which only ever holds the bot's own trades)."""
        return bool(self.cfg.adopt_existing_positions or getattr(self.broker, "bot_owned_account", False))

    def _managed_positions(self, state: BotState, holdings: dict[str, Position]) -> dict[str, Position]:
        """The positions the bot manages: in the configured symbols, at most the
        quantity it bought itself, at its own average entry price (a broker's
        average blends in shares the bot did not buy, even after some are sold)."""
        managed: dict[str, Position] = {}
        for symbol in self.cfg.symbols:
            pos = holdings.get(symbol)
            if pos is None:
                continue
            if self._adopts_all():
                managed[symbol] = pos
                continue
            own = state.owned.get(symbol)
            if own:
                managed[symbol] = replace(pos, qty=min(pos.qty, own["qty"]), avg_entry_price=own["avg_entry_price"])
        return managed

    def _record_in_ledger(self, tick: _Tick, result: OrderResult, ref_price: float,
                          client_order_id: str | None = None) -> None:
        """Book one of the bot's own orders in ``state.owned``. A BUY the
        broker accepted but has not reported filled is booked in full, as if
        it fills (a market order); a SELL only as far as it is reported filled.
        Either way it waits in ``state.pending_orders`` and the symbol is
        unsettled until no order of the bot's is working on it; then the
        record is corrected to what really filled (see _settle_orders)."""
        state = tick.state
        if not result.ok:
            return
        symbol, side = result.symbol, Side(result.side)
        filled = _positive(result.filled_qty) or 0.0
        if result.status == "filled":
            self._book(tick, symbol, side, filled or result.qty, result.filled_avg_price, ref_price)
            return
        if symbol not in state.unsettled:
            state.unsettled.append(symbol)
        booked = result.qty if side is Side.BUY else min(filled, result.qty)
        self._book(tick, symbol, side, booked, result.filled_avg_price, ref_price)
        if client_order_id and result.qty > 0:
            held = tick.holdings.get(symbol)
            state.pending_orders[client_order_id] = {
                "symbol": symbol, "side": side.value, "qty": float(result.qty), "booked": float(booked),
                "held": float(held.qty) if held is not None else 0.0, "order_id": str(result.id or "")}

    def _book(self, tick: _Tick, symbol: str, side: Side, qty: float, fill_price: float | None,
              ref_price: float) -> None:
        """Add a bought quantity to ``owned`` (at the fill price, else the
        price the order was sized at), or take a sold one off."""
        state = tick.state
        if not qty > 0:
            return
        own = state.owned.get(symbol)
        if side is Side.SELL:
            if own is not None:
                if own["qty"] - qty <= own["qty"] * _QTY_TOLERANCE:
                    del state.owned[symbol]
                else:
                    own["qty"] -= qty
            return
        price = _positive(fill_price) or _positive(ref_price)
        held, avg = (own["qty"], own["avg_entry_price"]) if own else (0.0, 0.0)
        total = held + qty
        if price is None:
            price = avg or 0.0
        if price > 0:
            state.owned[symbol] = {"qty": total, "avg_entry_price": (held * avg + qty * price) / total}
            if symbol not in tick.holdings:
                # What the broker will hold once it fills (the bot only buys a
                # symbol the account does not hold): a split before the bot
                # sees the holding is still recognised as one.
                state.seen_holdings[symbol] = [qty, price]

    def _has_pending(self, state: BotState, symbol: str) -> bool:
        return any(order["symbol"] == symbol for order in state.pending_orders.values())

    def _note_settled(self, tick: _Tick, symbol: str, working: list[OpenOrder]) -> bool:
        """No order from the bot is working on ``symbol`` any more: its orders
        still waiting are settled now (_settle_orders), so a part that filled is
        never sold again and a part that did not stays the bot's. Whatever else
        changed, the ledger is trimmed to the broker's holding from the next
        tick (whose holdings are read after this). True when it settled now;
        raises (and stays unsettled, retried next tick) when that cannot be
        told yet."""
        state = tick.state
        if symbol not in state.unsettled or any(order.placed_by_bot for order in working):
            return False
        if self._has_pending(state, symbol):
            self._settle_orders(tick, symbol)
            tick.positions = self._managed_positions(state, tick.holdings)
        state.unsettled.remove(symbol)
        return True

    def _settle_orders(self, tick: _Tick, symbol: str) -> None:
        """Correct ``owned`` for the bot's finished orders on ``symbol`` to
        what really filled: what the broker reports for each, else how the
        holding changed since it was sent (a fresh read: the tick's may predate
        the fill). Raises while one is still working."""
        orders = self._pending_on(tick.state, symbol)
        fills = [self._order_fill(symbol, cid, order) for cid, order in orders]
        change = 0.0
        if any(fill is None for fill in fills):
            held = self._open_positions().get(symbol)
            change = (held.qty if held is not None else 0.0) - min(order["held"] for _, order in orders)
        for (cid, order), fill in zip(orders, fills):
            if fill is None:  # by the holding: a BUY raised it, a SELL lowered it
                buy = order["side"] == Side.BUY.value
                fill = min(order["qty"], max(change if buy else -change, 0.0))
                change += -fill if buy else fill
            self._apply_fill(tick, symbol, cid, order, fill)

    def _settle_finished(self, tick: _Tick, symbol: str) -> None:
        """At the start of a tick: settle the bot's orders on ``symbol`` when
        the broker reports every one of them finished (its own record, not the
        tick's holdings, which may predate a fill), so a stock split overnight
        is seen against what really filled. Otherwise they wait for
        _note_settled. The symbol stays unsettled for the rest of the tick."""
        orders = self._pending_on(tick.state, symbol)
        try:
            fills = [self._order_fill(symbol, cid, order) for cid, order in orders]
        except BrokerError:  # one is still working
            return
        if all(fill is not None for fill in fills):
            for (cid, order), fill in zip(orders, fills):
                self._apply_fill(tick, symbol, cid, order, fill)

    def _apply_fill(self, tick: _Tick, symbol: str, client_order_id: str, order: dict, fill: float) -> None:
        """Book what one finished order of the bot's really filled: a BUY that
        did not fill (or not all of it) is taken back off, a SELL comes off as
        far as it filled."""
        state = tick.state
        fill = min(max(fill, 0.0), order["qty"])
        buy = order["side"] == Side.BUY.value
        self._book(tick, symbol, Side.SELL, (order["booked"] - fill) if buy else (fill - order["booked"]), None, 0.0)
        seen = state.seen_holdings.get(symbol)
        if buy and seen is not None and order["held"] == 0 and fill > 0:
            state.seen_holdings[symbol] = [fill, seen[1]]  # what the broker holds after it
        del state.pending_orders[client_order_id]
        if fill < order["qty"] * (1.0 - _QTY_TOLERANCE):
            logger.warning("%s: %g of the bot's %s of %g did not fill (expired, cancelled or rejected)%s",
                           symbol, order["qty"] - fill, order["side"], order["qty"],
                           "; the bot still manages those shares" if not buy else "")

    def _pending_on(self, state: BotState, symbol: str) -> list[tuple[str, dict]]:
        return [(cid, order) for cid, order in state.pending_orders.items() if order["symbol"] == symbol]

    def _order_fill(self, symbol: str, client_order_id: str, order: dict) -> float | None:
        """What the broker says filled of one finished order of the bot's
        (None: it cannot tell). Raises BrokerError while it is still working."""
        try:
            fill = self.broker.order_filled_qty(symbol, client_order_id, order["order_id"])
        except BrokerError:
            raise
        except Exception as exc:  # an adapter bug must not hold up stop-losses: go by the holding
            logger.warning("%s: looking up order %s failed: %s", symbol, client_order_id, _describe(exc))
            return None
        return fill if fill is None or math.isfinite(fill) else None

    def _reconcile_ledger(self, tick: _Tick) -> None:
        """Settle the bot's orders the broker reports finished, rescale
        ``owned`` for a stock split (only where no order of the bot's is
        pending: its fill must not look like one), then trim it to the broker's
        holding for settled symbols: shares sold elsewhere (by hand,
        `flatten`), a buy that was cancelled or only partly filled, or a fee
        taken in the coin. A symbol with an unsettled order of the bot is not
        trimmed until it settles."""
        state = tick.state
        for symbol in sorted({order["symbol"] for order in state.pending_orders.values()}):
            if symbol not in state.unsettled:  # always settled through _note_settled
                state.unsettled.append(symbol)
            self._settle_finished(tick, symbol)
        for symbol in list(state.owned):
            if not self._has_pending(state, symbol):
                self._check_split(tick, symbol)
        for symbol in list(state.owned):
            if symbol in state.unsettled:
                continue
            own, pos = state.owned[symbol], tick.holdings.get(symbol)
            if pos is None:
                del state.owned[symbol]
                logger.info("%s: the bot's position is gone (sold or never filled)", symbol)
            elif pos.qty < own["qty"] * (1.0 - _QTY_TOLERANCE):
                logger.info("%s: the bot owned %g but the account holds only %g; counting %g as the bot's",
                            symbol, own["qty"], pos.qty, pos.qty)
                own["qty"] = pos.qty

    def _check_split(self, tick: _Tick, symbol: str) -> None:
        """A holding whose quantity changed by a clear factor at an unchanged
        cost (qty x the broker's average price) was split (or reverse split):
        the broker then reports N times the shares at 1/N the average price,
        and the bars are split-adjusted, but the bot's own record is not. It
        is rescaled the same way, or the old entry price would fire a false
        stop-loss (or, after a reverse split, never fire one). A trade changes
        the cost, a split does not; and it is only checked while no order of
        the bot's is pending on the symbol, so its own fill cannot look like one."""
        state = tick.state
        seen, pos, own = state.seen_holdings.get(symbol), tick.holdings.get(symbol), state.owned.get(symbol)
        if seen is None or pos is None or own is None:
            return
        old_qty, old_avg = seen
        ratio = pos.qty / old_qty
        old_cost, new_cost = old_qty * old_avg, pos.qty * pos.avg_entry_price
        if (not math.isfinite(ratio) or abs(ratio - 1.0) < _SPLIT_MIN_CHANGE or not old_cost > 0
                or abs(new_cost / old_cost - 1.0) > _SPLIT_COST_TOLERANCE):
            return
        before = (own["qty"], own["avg_entry_price"])
        own["qty"], own["avg_entry_price"] = own["qty"] * ratio, own["avg_entry_price"] / ratio
        state.seen_holdings[symbol] = [pos.qty, pos.avg_entry_price]
        if (flow := state.flow_holdings.get(symbol)) is not None:
            state.flow_holdings[symbol] = [flow[0] * ratio, flow[1] / ratio]
        units = _units(symbol)
        message = (f"{symbol}: the holding went from {old_qty:.8g} to {pos.qty:.8g} {units} at the same cost, a "
                   f"stock split (x{ratio:.6g}). The bot now counts its {own['qty']:.8g} {units} at an entry of "
                   f"{own['avg_entry_price']:.6g} (was {before[0]:.8g} at {before[1]:.6g}).")
        logger.warning("%s", message)
        self.notifier.send(message, "warning")

    def _report_unmanaged(self, tick: _Tick) -> None:
        """Holdings the bot leaves alone (no stop-loss, no exits, no flatten):
        symbols the config does not list, and in a configured symbol whatever
        the bot did not buy itself. Notified once per symbol (kept in the
        state, so `once` runs do not repeat it); again if it goes and returns."""
        state = tick.state
        current: set[str] = set()
        for symbol, short in tick.shorts.items():
            if symbol not in self.cfg.symbols:
                continue
            current.add(symbol)
            units = _units(symbol)
            note = f"the account is short {-short.qty:.8g} {units}: not the bot's, and it never covers it"
            signals = tick.report.signals
            signals[symbol] = f"{signals[symbol]} | {note}" if symbol in signals else note
            if symbol not in state.notified_unmanaged:
                state.notified_unmanaged.append(symbol)
                self.notifier.error(f"{symbol}: the account is short {-short.qty:.8g} {units} (sold short, not by "
                                    f"this bot). The bot never buys to cover it: it makes no {symbol} entries while "
                                    "the short position is open.")
        for symbol, held in tick.holdings.items():
            if symbol not in self.cfg.symbols:
                current.add(symbol)
                tick.report.signals[symbol] = ("held but not in `symbols`: not managed by the bot "
                                               "(no stop-loss, no exits)")
                message = (f"{symbol} is held but is not in `symbols`, so it is not managed by the bot: no "
                           "stop-loss and no exits. If the bot bought it, add it back to `symbols` or sell it "
                           "yourself; if you bought it by hand, you can ignore this.")
            else:
                managed = tick.positions.get(symbol)
                extra = held.qty - (managed.qty if managed else 0.0)
                if (extra <= held.qty * _QTY_TOLERANCE or tick.ledger_unknown
                        or symbol in state.unsettled or symbol in tick.ordered):
                    continue
                current.add(symbol)
                units = _units(symbol)
                note = f"{extra:.8g} {units} in the account were not bought by this bot: left alone"
                signals = tick.report.signals
                signals[symbol] = f"{signals[symbol]} | {note}" if symbol in signals else note
                if managed is None:
                    message = (f"{symbol}: the account holds {held.qty:.8g} {units} that this bot did not buy. "
                               "It leaves them alone: no stop-loss, no strategy exits, no flatten, and no new "
                               f"{symbol} entries while they are held. To let the bot manage (and possibly sell) "
                               "them, set adopt_existing_positions: true in the config.")
                else:
                    message = (f"{symbol}: the account holds {held.qty:.8g} {units}, of which this bot bought "
                               f"{managed.qty:.8g}. It manages and sells only those, never the other {extra:.8g}.")
            if symbol not in state.notified_unmanaged:
                state.notified_unmanaged.append(symbol)
                self.notifier.error(message)
        state.notified_unmanaged = [s for s in state.notified_unmanaged if s in current]

    # ------------------------------------------------------------------ money moved without trading
    def _track_external_flows(self, tick: _Tick) -> None:
        """Money that entered or left the account since the last tick today
        without the bot trading, added to the day's loss baseline: a deposit
        or withdrawal, or a trade in an asset the broker does not value here
        (ccxt values only the configured coins). A trade in a holding it does
        value swaps cash for an asset of about the same value and nets out.
        Holdings are valued at the last tick's prices (a new one at its entry
        price), so price moves stay gains and losses."""
        state = tick.state
        if state.flow_cash is None:
            return
        flow = tick.account.cash - state.flow_cash
        current = {**tick.holdings, **tick.shorts}  # a short is a negative quantity
        for symbol in set(state.flow_holdings) | set(current):
            old_qty, old_price = state.flow_holdings.get(symbol, (0.0, 0.0))
            pos = current.get(symbol)
            new_qty = pos.qty if pos is not None else 0.0
            if new_qty == old_qty:
                continue
            ref = (_positive(old_price) if old_qty != 0 else None) or (
                (_positive(pos.avg_entry_price) or _positive(pos.market_price)) if pos is not None else None)
            flow += (new_qty - old_qty) * (ref or 0.0)
        if not flow or not math.isfinite(flow):
            return
        state.external_flow += flow
        if abs(flow) >= _FLOW_LOG_SHARE * max(abs(tick.account.equity), 1.0):
            logger.warning("%s %s moved in/out of the account without the bot trading (a deposit, a "
                           "withdrawal, or a trade in an asset the bot does not value); the daily loss baseline "
                           "is now %s", f"{flow:+,.2f}", tick.account.currency, _fmt_money(loss_baseline(state)))

    def _remember_holdings(self, tick: _Tick) -> None:
        """Keep the broker's holdings of what the bot owns (to recognise a
        split), and this tick's cash and holdings as the next tick's reference
        for money moved in or out: only from a consistent snapshot. After an
        order of the bot's (sent this tick, or still settling from an earlier
        one) the cash and the positions reads can straddle its fill, or one of
        them failed, which would book the bot's own trade as money moved in or
        out of the account; the next tick then starts a new reference instead."""
        state = tick.state
        seen = {s: v for s, v in state.seen_holdings.items() if s in state.owned}
        for symbol in state.owned:
            pos = tick.holdings.get(symbol)
            if pos is not None and _positive(pos.qty) and _positive(pos.avg_entry_price):
                seen[symbol] = [float(pos.qty), float(pos.avg_entry_price)]
        state.seen_holdings = seen
        if tick.ordered or tick.settling:
            state.flow_cash, state.flow_holdings = None, {}
            return
        state.flow_cash = float(tick.account.cash) if math.isfinite(tick.account.cash) else None
        state.flow_holdings = {s: [float(p.qty), float(p.market_price)]
                               for s, p in {**tick.holdings, **tick.shorts}.items()
                               if math.isfinite(p.qty) and math.isfinite(p.market_price)}

    # ------------------------------------------------------------------ records
    def _record_order(self, tick: _Tick, result: OrderResult, reason: str, client_order_id: str | None) -> None:
        tick.report.orders.append(result)
        full_reason = _combine_reasons(reason, result.reason)
        price = f" @ {result.filled_avg_price:.6g}" if result.filled_avg_price else ""
        side = result.side.value if isinstance(result.side, Side) else str(result.side)
        text = f"{side.upper()} {result.qty:.8g} {result.symbol} {result.status}{price} ({full_reason}) [{result.id}]"
        if result.ok:
            self.notifier.trade(text)
        else:
            self.notifier.error(f"Order rejected: {text}")
        row = trade_row(result, self._now(), self.cfg.mode, full_reason, client_order_id)
        try:
            append_trade_row(self.trades_path, row)
        except OSError as exc:
            self._error(tick.report, f"could not write {self.trades_path}: {exc}")

    def _error(self, report: TickReport, message: str, exc: BaseException | None = None) -> None:
        report.errors.append(message)
        self._tick_errors.add(message)
        if exc is not None and not isinstance(exc, BrokerError):
            logger.error("Unexpected error: %s", message, exc_info=exc)
        if message in self._recent_errors:
            logger.error("%s (same as last tick; not notified again)", message)
        else:
            self.notifier.error(message)  # also logs it

    def _end_tick(self, report: TickReport) -> TickReport:
        self._recent_errors = self._tick_errors
        if report.skipped:
            logger.info("Tick skipped: %s", report.skipped)
        else:
            equity = "n/a" if report.equity is None else f"{report.equity:,.2f}"
            logger.info("Tick done: equity %s, %d order(s), %d error(s)%s", equity, len(report.orders),
                        len(report.errors), ", HALTED for the day" if report.halted else "")
        return report

    def _now(self) -> datetime:
        now = self.clock()
        return now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now


def account_key(cfg: BotConfig, currency: str) -> str:
    """Which account a state belongs to (``BotState.account_key``): mode,
    broker, venue (+ testnet) and currency."""
    b = cfg.broker
    venue = (b.exchange or "") + (" sandbox" if b.use_sandbox else "")
    return f"{cfg.mode}:{b.type}:{venue}:{currency}"


def trade_row(result: OrderResult, when: datetime, mode: str, reason: str,
              client_order_id: str | None = None) -> dict[str, object]:
    """One ``trades.csv`` row (``TRADE_COLUMNS``) for an order result."""
    side = result.side.value if isinstance(result.side, Side) else str(result.side)
    return {
        "time": when.isoformat(), "mode": mode, "symbol": result.symbol, "side": side,
        "qty": result.qty, "filled_qty": result.filled_qty, "status": result.status,
        "filled_avg_price": "" if result.filled_avg_price is None else result.filled_avg_price,
        "reason": reason, "order_id": result.id, "client_order_id": client_order_id or "",
    }


def append_trade_row(path: Path, row: dict[str, object]) -> None:
    """Append ``row`` to the trade log at ``path`` (header on first write)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=TRADE_COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def backoff_seconds(poll_interval: float, consecutive_errors: int) -> float:
    """Wait before the next tick: the poll interval normally, and
    ``min(poll * 2**(n-1), 900)`` after ``n`` failing ticks in a row.

    The 15-minute cap also applies when ``poll_interval_seconds`` is longer
    than that: a bot that normally checks hourly retries a failed check after
    15 minutes, so a transient outage does not delay its stop-loss checks by
    a whole interval."""
    if consecutive_errors <= 0:
        return float(poll_interval)
    return float(min(poll_interval * 2 ** min(consecutive_errors - 1, 30), MAX_BACKOFF_SECONDS))


def make_client_order_id(symbol: str, side: Side, bar_key: str) -> str:
    """``bot-<symbol>-<side>-<bar time>`` (at most 48 chars) plus a random
    suffix, since brokers such as Alpaca require unique client order ids."""
    clean_symbol = re.sub(r"[^A-Za-z0-9]", "", symbol) or "x"
    stamp = re.sub(r"[^0-9]", "", bar_key)[:12]
    base = f"{BOT_ORDER_PREFIX}{clean_symbol}-{Side(side).value}-{stamp}"[:_CLIENT_ID_BASE_LEN]
    return f"{base}-{uuid.uuid4().hex[:8]}"


def _positive(value: object) -> float | None:
    """``value`` as a float when it is a finite number > 0, else None."""
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 and not isinstance(value, bool) else None


def _units(symbol: str) -> str:
    """What a quantity of ``symbol`` is counted in: 'BTC' for 'BTC/KRW', else the symbol."""
    return symbol.partition("/")[0] or symbol


def _fmt_money(value: float | None) -> str:
    return "unknown" if value is None else f"{value:,.2f}"


def _combine_reasons(ours: str, broker: str) -> str:
    if not broker or broker in ours:
        return ours
    if not ours or broker.startswith(ours):
        return broker
    return f"{ours}; broker: {broker}"


def _describe(exc: BaseException) -> str:
    return str(exc) if isinstance(exc, BrokerError) else f"{type(exc).__name__}: {exc}"


__all__ = ["TRADES_FILE", "TRADE_COLUMNS", "TickReport", "TradingEngine", "account_key", "append_trade_row",
           "backoff_seconds", "make_client_order_id", "trade_row"]
