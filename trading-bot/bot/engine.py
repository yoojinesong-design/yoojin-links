"""The live trading loop.

One :meth:`TradingEngine.run_once` tick reads the account, applies the daily
limits, and for every configured symbol fetches CLOSED bars, asks the strategy
for a signal, sizes it with the :class:`~bot.risk.RiskManager` and sends a
market order. :meth:`TradingEngine.run_forever` repeats that on a timer.

Safety rules enforced here, on top of the risk manager and broker adapters:

* kill switch file present -> the tick does nothing, not even API reads;
* no new order for a symbol while a previous one is still working;
* each closed bar is evaluated once, but protective stops are checked every tick;
* daily loss limit hit -> no new entries for the rest of the day (exits still run);
* account and positions are re-read after every order, so the next symbol is
  sized against the cash that is really left; if that re-read (or an order
  submission) fails, no further entries are made in this tick;
* order sizes are rounded DOWN and never exceed what was sized or held.
"""
from __future__ import annotations

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

from .brokers.base import BrokerError
from .models import Account, Action, OrderRequest, OrderResult, Position, Side, Signal
from .state import kill_switch_active
from .utils import drop_incomplete_bars, utcnow, validate_bars

if TYPE_CHECKING:
    from .brokers.base import Broker
    from .config import BotConfig
    from .notify import Notifier
    from .risk import RiskManager
    from .state import BotState, StateStore
    from .strategies.base import Strategy

logger = logging.getLogger(__name__)

TRADES_FILE = "trades.csv"
TRADE_COLUMNS = ("time", "mode", "symbol", "side", "qty", "filled_qty", "status",
                 "filled_avg_price", "reason", "order_id", "client_order_id")
MAX_BACKOFF_SECONDS = 900
ERROR_ALERT_AFTER = 3      # notify when this many ticks in a row had errors ...
ERROR_ALERT_EVERY = 10     # ... and again every this many ticks after that
_CLIENT_ID_BASE_LEN = 48


@dataclass
class TickReport:
    started_at: datetime
    skipped: str | None = None          # "kill_switch" | "trading_blocked" | "market_closed" | None
    orders: list[OrderResult] = field(default_factory=list)
    signals: dict[str, str] = field(default_factory=dict)   # symbol -> "buy: reason" etc.
    errors: list[str] = field(default_factory=list)
    equity: float | None = None
    halted: bool = False


@dataclass
class _Tick:
    """Mutable working set of one tick."""
    state: BotState
    report: TickReport
    account: Account
    positions: dict[str, Position]
    # Set when something makes the account snapshot untrustworthy for the rest
    # of the tick (failed re-read or failed order submission). Exits still run.
    entries_blocked: str | None = None


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
            self._error(report, f"cannot check the kill switch in {self.cfg.state_dir} ({exc}); not trading")
            return self._end_tick(report)
        if killed:
            logger.warning("Kill switch is ON (%s): skipping tick, no orders sent", Path(self.cfg.state_dir) / "KILL")
            report.skipped = "kill_switch"
            return self._end_tick(report)

        try:
            state = self.store.load()
        except Exception as exc:  # e.g. permission denied: never trade without our counters
            self._error(report, f"could not load bot state ({_describe(exc)}); not trading", exc)
            return self._end_tick(report)

        try:
            self._tick(state, report)
        except Exception as exc:
            self._error(report, _describe(exc), exc)

        state.consecutive_errors = state.consecutive_errors + 1 if report.errors else 0
        state.last_tick_at = now.isoformat()
        report.halted = state.halted_today
        try:
            self.store.save(state)
        except Exception as exc:
            self._error(report, f"could not save bot state ({_describe(exc)})", exc)
        return self._end_tick(report)

    def run_forever(self, stop_event: threading.Event | None = None, max_ticks: int | None = None) -> None:
        """Run ticks every ``poll_interval_seconds`` until ``stop_event`` is set
        (or ``max_ticks`` ticks ran). Waits on the event, so a signal handler
        that sets it stops the loop promptly. Backs off after failing ticks."""
        stop = stop_event if stop_event is not None else threading.Event()
        poll = self.cfg.poll_interval_seconds
        ticks = failures = 0
        logger.info("Trading loop started: %s mode, %s, every %ss", self.cfg.mode.upper(),
                    ", ".join(self.cfg.symbols), poll)
        while not stop.is_set():
            try:
                failed = bool(self.run_once().errors)
            except Exception as exc:  # a bug: keep the loop alive, keep the traceback
                logger.exception("Unexpected error in trading tick; the loop keeps running")
                message = f"unexpected error in trading tick: {type(exc).__name__}: {exc}"
                if message not in self._recent_errors:
                    self.notifier.error(message)
                self._recent_errors = {message}
                failed = True
            ticks += 1
            failures = failures + 1 if failed else 0
            if failures == ERROR_ALERT_AFTER or (
                    failures > ERROR_ALERT_AFTER and (failures - ERROR_ALERT_AFTER) % ERROR_ALERT_EVERY == 0):
                self.notifier.error(f"{failures} ticks in a row had errors; still retrying (see the logs)")
            if max_ticks is not None and ticks >= max_ticks:
                break
            delay = backoff_seconds(poll, failures)
            if failures:
                logger.warning("Tick had errors (%d in a row); next try in %.0fs", failures, delay)
            if stop.wait(delay):
                break
        logger.info("Trading loop stopped after %d tick(s)", ticks)

    # ------------------------------------------------------------------ tick
    def _tick(self, state: BotState, report: TickReport) -> None:
        account = self.broker.get_account()
        report.equity = account.equity
        if account.trading_blocked:
            logger.warning("The broker reports trading is blocked on this account; skipping tick")
            report.skipped = "trading_blocked"
            return
        self._roll_day(state, account)
        if not self.broker.is_market_open():
            logger.info("Market is closed; nothing to do this tick")
            report.skipped = "market_closed"
            return

        tick = _Tick(state, report, account, self._open_positions())
        self._check_daily_loss(tick)
        for symbol in self.cfg.symbols:
            try:
                self._process_symbol(symbol, tick)
            except Exception as exc:  # one bad symbol must not stop the others
                self._error(report, f"{symbol}: {_describe(exc)}", exc)
        report.equity = tick.account.equity

    def _roll_day(self, state: BotState, account: Account) -> None:
        today = self._now().astimezone(self.tz).date().isoformat()
        start = _positive(account.day_start_equity) or _positive(account.equity)
        if state.day != today:
            logger.info("New trading day %s (%s); day start equity %s", today, self.cfg.timezone, start)
            state.day, state.day_start_equity = today, start
            state.trades_today, state.halted_today = 0, False
        elif state.day_start_equity is None:  # equity was unusable when the day started
            state.day_start_equity = start

    def _check_daily_loss(self, tick: _Tick) -> None:
        state, cfg = tick.state, self.risk.config
        start = state.day_start_equity
        if not state.halted_today and start and self.risk.daily_loss_breached(tick.account.equity, start):
            state.halted_today = True
            change = (tick.account.equity / start - 1.0) * 100.0
            action = "closing all positions" if cfg.flatten_on_daily_loss else "open positions are kept"
            self.notifier.error(
                f"Daily loss limit hit: equity {tick.account.equity:,.2f} is {change:.2f}% vs "
                f"{start:,.2f} at the start of {state.day} (limit -{cfg.max_daily_loss_pct}%). "
                f"No new entries until tomorrow; {action}.")
        if state.halted_today and cfg.flatten_on_daily_loss and self._flattened_day != state.day:
            self._flatten(tick)

    def _flatten(self, tick: _Tick) -> None:
        if not tick.positions:
            self._flattened_day = tick.state.day
            return
        logger.warning("Daily loss limit: closing all positions (%s)", ", ".join(tick.positions))
        try:
            results = self.broker.close_all_positions()
        except Exception as exc:
            tick.entries_blocked = "flatten failed"
            self._error(tick.report, f"closing all positions after the daily loss limit failed "
                                     f"(retrying next tick): {_describe(exc)}", exc)
            return
        self._flattened_day = tick.state.day
        for result in results:
            self._record_order(tick, result, "daily loss limit: flatten", None)
        self._refresh(tick)

    def _process_symbol(self, symbol: str, tick: _Tick) -> None:
        report, state = tick.report, tick.state
        if self.broker.has_open_orders(symbol):
            report.signals[symbol] = "skip: an earlier order is still pending"
            return
        bars = self._closed_bars(symbol)
        needed = max(int(self.strategy.min_bars), 1)
        if len(bars) < needed:
            report.signals[symbol] = f"warming up ({len(bars)}/{needed} closed bars)"
            return
        bar_key = bars.index[-1].isoformat()

        pos = tick.positions.get(symbol)
        if pos is not None:
            price = self.broker.get_latest_price(symbol)
            pos = replace(pos, market_price=price)
            exit_reason = self.risk.exit_reason(pos, price)
            if exit_reason:  # protective exit: checked every tick, even mid-bar
                report.signals[symbol] = (f"sell: {exit_reason} (price {price:.6g}, "
                                          f"entry {pos.avg_entry_price:.6g})")
                if self._sell(tick, pos, exit_reason, bar_key):
                    # Deliberately marked: the protective exit is this bar's
                    # decision, so the strategy is not asked to re-enter on the
                    # same closed bar right after a stop-out (fee churn).
                    state.last_signal_bar[symbol] = bar_key
                return

        if state.last_signal_bar.get(symbol) == bar_key:
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
            evaluated = self._enter(tick, symbol, signal, text, bar_key)
        if evaluated:
            state.last_signal_bar[symbol] = bar_key

    def _closed_bars(self, symbol: str) -> pd.DataFrame:
        lookback, timeframe = self.cfg.bars_lookback, self.cfg.timeframe
        bars = validate_bars(self.broker.get_bars(symbol, timeframe, lookback + 1))
        return drop_incomplete_bars(bars, timeframe, self._now()).tail(lookback)

    def _sell(self, tick: _Tick, pos: Position, reason: str, bar_key: str) -> bool:
        """Sell the whole position (rounded down to the venue's step, never
        more than held). False when the quantity rounds down to nothing."""
        qty = min(self.broker.normalize_qty(pos.symbol, pos.qty), pos.qty)
        if not qty > 0:
            logger.warning("%s: position of %g rounds down to 0; cannot sell it", pos.symbol, pos.qty)
            tick.report.signals[pos.symbol] += f" (not selling: {pos.qty:g} rounds down to 0)"
            return False
        self._submit(tick, pos.symbol, Side.SELL, qty, reason, bar_key)
        return True

    def _enter(self, tick: _Tick, symbol: str, signal: Signal, text: str, bar_key: str) -> bool:
        """Try a new long entry. Returns False only when a temporary problem
        blocked it (so the bar is evaluated again next tick)."""
        state, cfg, report = tick.state, self.risk.config, tick.report
        if state.halted_today:
            blocked = "daily loss limit hit, no new entries today"
        elif state.trades_today >= cfg.max_trades_per_day:
            blocked = f"max trades per day reached ({state.trades_today}/{cfg.max_trades_per_day})"
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
        qty, why = self.risk.entry_qty(symbol, price, signal, tick.account, tick.positions, broker_min)
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
        result = self._submit(tick, symbol, Side.BUY, qty, signal.reason or "strategy entry", bar_key)
        if result.ok:
            state.trades_today += 1
        return True

    def _submit(self, tick: _Tick, symbol: str, side: Side, qty: float, reason: str, bar_key: str) -> OrderResult:
        order = OrderRequest(symbol=symbol, side=side, qty=qty, reason=reason,
                             client_order_id=make_client_order_id(symbol, side, bar_key))
        logger.info("Submitting %s %.8g %s (%s) [%s]", side.value.upper(), qty, symbol, reason, order.client_order_id)
        try:
            result = self.broker.submit_order(order)
        except Exception:
            # The order may or may not have reached the broker, so cash is
            # uncertain: size nothing else against it this tick.
            tick.entries_blocked = f"an order for {symbol} failed to submit"
            raise
        self._record_order(tick, result, reason, order.client_order_id)
        self._refresh(tick)
        return result

    def _refresh(self, tick: _Tick) -> None:
        try:
            tick.account = self.broker.get_account()
            tick.positions = self._open_positions()
        except Exception as exc:
            tick.entries_blocked = "could not re-read the account after an order"
            self._error(tick.report, f"could not refresh account/positions after an order: {_describe(exc)}", exc)

    def _open_positions(self) -> dict[str, Position]:
        return {symbol: pos for symbol, pos in self.broker.get_positions().items() if pos.qty > 0}

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
        row = {
            "time": self._now().isoformat(), "mode": self.cfg.mode, "symbol": result.symbol, "side": side,
            "qty": result.qty, "filled_qty": result.filled_qty, "status": result.status,
            "filled_avg_price": "" if result.filled_avg_price is None else result.filled_avg_price,
            "reason": full_reason, "order_id": result.id, "client_order_id": client_order_id or "",
        }
        try:
            self._append_trade_row(row)
        except OSError as exc:
            self._error(tick.report, f"could not write {self.trades_path}: {exc}")

    def _append_trade_row(self, row: dict[str, object]) -> None:
        path = self.trades_path
        path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not path.exists() or path.stat().st_size == 0
        with path.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=TRADE_COLUMNS)
            if write_header:
                writer.writeheader()
            writer.writerow(row)

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
    base = f"bot-{clean_symbol}-{Side(side).value}-{stamp}"[:_CLIENT_ID_BASE_LEN]
    return f"{base}-{uuid.uuid4().hex[:8]}"


def _positive(value: object) -> float | None:
    """``value`` as a float when it is a finite number > 0, else None."""
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 and not isinstance(value, bool) else None


def _combine_reasons(ours: str, broker: str) -> str:
    if not broker or broker in ours:
        return ours
    if not ours or broker.startswith(ours):
        return broker
    return f"{ours}; broker: {broker}"


def _describe(exc: BaseException) -> str:
    return str(exc) if isinstance(exc, BrokerError) else f"{type(exc).__name__}: {exc}"


__all__ = ["TickReport", "TradingEngine", "backoff_seconds", "make_client_order_id"]
