"""Event-driven backtester.

Replays history bar by bar through the SAME ``Strategy`` and ``RiskManager``
objects the live engine uses, so what you backtest is what trades:

* The strategy only ever sees bars up to and including the current one
  (its last ``lookback`` rows), exactly like the live engine's closed bars.
* Orders decided at a bar's close fill at that symbol's NEXT bar open, with
  slippage against us and a fee on the notional.
* Stop-loss / take-profit levels are checked every bar, including the bar a
  position was opened on. The open comes first: a bar that opens through
  either level exits at the open, with that level's reason (as the live
  engine's first tick after the open sees it). Otherwise the bar's low / high
  are checked, and the stop wins when both levels were touched inside the bar
  (the order of the high and the low is unknown).
* Long-only, no leverage: a queued buy that is no longer affordable at the
  open is shrunk or dropped, so cash never goes negative.
* The daily entry gates (loss-limit halt, max trades per day) apply on the day
  a buy is SENT, i.e. its fill bar, like the live engine: a signal at a day's
  last close is sent the next day, after the daily counters reset. The loss
  limit is checked at each open too (holdings valued at the open), before
  queued buys fill, as the live engine does on its first tick of a session,
  and at each bar's lows: the live engine checks it on every tick, so a dip
  through the limit halts the day (and with flatten_on_daily_loss sells where
  the account crosses it) even when the bar recovers by its close. The lows
  of several symbols in one bar are taken as reached together, and before any
  take-profit at a high in that bar (a worst case, like the stop-loss).
* An exit queued at a close frees its position slot and (estimated) cash for
  the symbols after it in the same close, like the live engine, which sells
  and re-reads the account before sizing the next symbol. Likewise at an open:
  symbols are walked in order, and a holding whose open is through its stop
  or target is sold before the later symbols' buys fill, so a buy that was
  skipped at the close only for want of a slot or cash is sized again then.
* CAGR, Sharpe, volatility and time in market cover the trading period: from
  the first bar a fill can happen (the open after the strategy's first signal
  bar), like buy & hold. The warm-up bars before it, when the strategy cannot
  trade yet (the live bot fetches that history instead), are left out.

Invariant: at every bar, equity == cash + sum(qty * latest close).
"""
from __future__ import annotations

import json
import logging
import math
import numbers
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import numpy as np
import pandas as pd

from .models import Account, Action, Position, Side, Signal
from .risk import RiskConfig, RiskManager
from .strategies.base import Strategy
from .utils import bars_per_year, floor_to_step, timeframe_to_timedelta, validate_bars

logger = logging.getLogger(__name__)

# summary() leaves CAGR out below this many days of data (see there).
MIN_DAYS_FOR_CAGR = 30

# Exit reasons recorded on trades.
EXIT_SIGNAL = "signal"
EXIT_STOP = "stop_loss"
EXIT_TAKE_PROFIT = "take_profit"
EXIT_DAILY_LOSS = "daily_loss_limit"
EXIT_END = "end_of_backtest"


@dataclass
class BacktestConfig:
    starting_cash: float = 10_000.0
    fee_pct: float = 0.1
    slippage_pct: float = 0.05
    lookback: int = 300              # same window the live engine feeds the strategy
    timeframe: str = "1d"
    trading_days_per_year: int = 252 # 252 stocks, 365 crypto (for annualisation)
    timezone: str = "UTC"            # trading-day boundaries for the daily loss limit
    risk: RiskConfig = field(default_factory=RiskConfig)
    # Order quantities are rounded DOWN to this step (the live brokers' default
    # is 1e-6; use 1.0 to simulate whole shares). 0 disables rounding.
    qty_step: float = 1e-6

    def validate(self) -> None:
        """Raise ValueError on nonsensical settings (risk settings included)."""
        errors: list[str] = []
        if not _is_number(self.starting_cash) or self.starting_cash <= 0:
            errors.append(f"starting_cash must be > 0, got {self.starting_cash!r}")
        for name in ("fee_pct", "slippage_pct"):
            value = getattr(self, name)
            if not _is_number(value) or not 0 <= value < 100:
                errors.append(f"{name} must be >= 0 and < 100, got {value!r}")
        for name in ("lookback", "trading_days_per_year"):
            value = getattr(self, name)
            if not isinstance(value, numbers.Integral) or isinstance(value, bool) or value < 1:
                errors.append(f"{name} must be a whole number >= 1, got {value!r}")
        if not _is_number(self.qty_step) or self.qty_step < 0:
            errors.append(f"qty_step must be >= 0, got {self.qty_step!r}")
        try:
            timeframe_to_timedelta(self.timeframe)
        except (ValueError, AttributeError):
            errors.append(f"unsupported timeframe {self.timeframe!r}")
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError, TypeError):
            errors.append(f"unknown timezone {self.timezone!r} (use an IANA name like 'America/New_York')")
        if errors:
            raise ValueError("invalid backtest settings: " + "; ".join(errors))
        self.risk.validate()


@dataclass
class Trade:
    symbol: str
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_price: float   # fill price incl. slippage
    exit_price: float    # fill price incl. slippage
    qty: float
    pnl: float           # net of entry and exit fees
    pnl_pct: float       # pnl / (entry_price * qty) * 100
    fees: float          # entry + exit fees
    exit_reason: str     # signal | stop_loss | take_profit | daily_loss_limit | end_of_backtest


@dataclass
class BacktestResult:
    equity_curve: pd.Series            # indexed by bar time
    trades: list[Trade]
    metrics: dict[str, float]
    # Additive detail (not in the original contract): cash and per-symbol
    # quantity held after each bar, so the equity curve can be audited.
    cash: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    holdings: pd.DataFrame = field(default_factory=pd.DataFrame)
    strategy: str = ""

    def summary(self) -> str:
        """Aligned human-readable table of the headline metrics."""
        m = self.metrics
        span_days = self._span_days()
        # Compounding a few days' return over a whole year gives absurd numbers
        # (e.g. -1% in 13 hours -> "CAGR -99.98%"), so it is not shown then.
        too_short = span_days is not None and span_days < MIN_DAYS_FOR_CAGR
        rows: list[tuple[str, str]] = [
            ("Final equity", _fmt_num(m.get("final_equity"))),
            ("Total return", _fmt_pct(m.get("total_return_pct"), signed=True)),
            ("CAGR", "n/a" if too_short else _fmt_pct(m.get("cagr_pct"), signed=True)),
            ("Max drawdown", _fmt_pct(m.get("max_drawdown_pct"))),
            ("Sharpe (ann.)", _fmt_num(m.get("sharpe"))),
            ("Volatility (ann.)", _fmt_pct(m.get("volatility_ann_pct"))),
            ("Trades", _fmt_int(m.get("num_trades"))),
            ("Win rate", _fmt_pct(m.get("win_rate_pct"))),
            ("Avg trade", _fmt_pct(m.get("avg_trade_pct"), signed=True)),
            ("Profit factor", _fmt_num(m.get("profit_factor"))),
            ("Time in market", _fmt_pct(m.get("exposure_pct"))),
            ("Fees paid", _fmt_num(m.get("fees_paid"))),
            ("Buy & hold return", _fmt_pct(m.get("buy_and_hold_return_pct"), signed=True)),
        ]
        width = max(len(label) for label, _ in rows)
        value_width = max(len(value) for _, value in rows)
        lines = []
        if self.strategy:
            lines.append(f"Strategy: {self.strategy}")
        lines.append(f"Period:   {_fmt_date(m.get('start'))} -> {_fmt_date(m.get('end'))} "
                     f"({len(self.equity_curve):,} bars)")
        warmup, tradable_from = m.get("warmup_bars", math.nan), m.get("tradable_from", math.nan)
        if math.isfinite(warmup) and warmup > 0 and math.isfinite(tradable_from):
            lines.append(f"Trading:  {_fmt_date(tradable_from)} -> {_fmt_date(m.get('end'))} (after "
                         f"{int(warmup):,} warm-up bar{'s' if warmup != 1 else ''}; CAGR, Sharpe, volatility and "
                         "time in market cover this)")
        lines.append("-" * (width + 2 + value_width))
        lines += [f"{label:<{width}}  {value:>{value_width}}" for label, value in rows]
        if self.trades:
            counts: dict[str, int] = {}
            for trade in self.trades:
                counts[trade.exit_reason] = counts.get(trade.exit_reason, 0) + 1
            lines.append("Exits: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
        if too_short and span_days is not None:
            lines.append(f"Note: the trading period covers only {_fmt_span(span_days)}, too short to annualise:")
            lines.append("      CAGR is not shown and the annualised Sharpe/volatility are rough. Use more bars.")
        return "\n".join(lines)

    def _span_days(self) -> float | None:
        """Calendar time the trading period covers (its first open to the last
        close; see ``tradable_from``), in days."""
        index = self.equity_curve.index
        if len(index) < 2 or not isinstance(index, pd.DatetimeIndex):
            return None
        bar = pd.Series(index).diff().median()
        start = index[0]
        tradable_from = self.metrics.get("tradable_from")
        if tradable_from is not None and math.isfinite(tradable_from):
            start = pd.Timestamp(tradable_from, unit="s", tz="UTC")
        return float((index[-1] - start + bar) / pd.Timedelta(days=1))

    def save(self, out_dir: Path) -> None:
        """Write ``equity.csv``, ``trades.csv`` and ``metrics.json`` into ``out_dir``."""
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)

        equity = pd.DataFrame({"equity": self.equity_curve})
        if len(self.cash) == len(self.equity_curve):
            equity["cash"] = self.cash.to_numpy()
        if not self.holdings.empty and len(self.holdings) == len(self.equity_curve):
            for symbol in self.holdings.columns:
                equity[f"qty_{symbol}"] = self.holdings[symbol].to_numpy()
        equity.index.name = "time"
        equity.to_csv(out / "equity.csv")

        columns = [f for f in Trade.__dataclass_fields__]
        trades = pd.DataFrame([asdict(t) for t in self.trades], columns=columns)
        for col in ("entry_time", "exit_time"):
            trades[col] = [pd.Timestamp(v).isoformat() for v in trades[col]]
        trades.to_csv(out / "trades.csv", index=False)

        metrics: dict[str, object] = {k: _json_number(v) for k, v in self.metrics.items()}
        metrics["start_time"] = _fmt_date(self.metrics.get("start"), iso=True)
        metrics["end_time"] = _fmt_date(self.metrics.get("end"), iso=True)
        metrics["tradable_from_time"] = _fmt_date(self.metrics.get("tradable_from"), iso=True)
        if self.strategy:
            metrics["strategy"] = self.strategy
        (out / "metrics.json").write_text(json.dumps(metrics, indent=2, allow_nan=False) + "\n",
                                          encoding="utf-8")


def run_backtest(strategy: Strategy, data: dict[str, pd.DataFrame], cfg: BacktestConfig) -> BacktestResult:
    """Simulate ``strategy`` over ``data`` ({symbol: bars}) and return the
    equity curve, closed trades and summary metrics. See the module docstring
    for the execution model. Raises ValueError for bad settings or data."""
    return _Simulation(strategy, data, cfg).run()


def max_drawdown_pct(equity: pd.Series) -> float:
    """Largest peak-to-trough fall of ``equity`` in percent (<= 0), NaN if empty."""
    eq = pd.Series(equity, dtype=float).dropna()
    if eq.empty:
        return math.nan
    drawdown = (eq / eq.cummax() - 1.0) * 100.0
    return float(min(drawdown.min(), 0.0))


# --------------------------------------------------------------------------- simulation


@dataclass
class _Holding:
    qty: float
    entry_price: float
    entry_time: pd.Timestamp
    entry_fee: float


@dataclass
class _Order:
    """A market order decided at a close, to fill at the symbol's next open."""
    side: Side
    qty: float
    reason: str
    ref_price: float = 0.0     # close when queued (buys: counts toward exposure)
    reserved: float = 0.0      # buys: cash earmarked incl. slippage and fee


class _Simulation:
    def __init__(self, strategy: Strategy, data: dict[str, pd.DataFrame], cfg: BacktestConfig) -> None:
        cfg.validate()
        self.cfg = cfg
        self.strategy = strategy
        self.risk = RiskManager(cfg.risk)
        self.min_bars = max(1, int(strategy.min_bars))
        if cfg.lookback < self.min_bars:
            raise ValueError(f"lookback ({cfg.lookback}) must be >= {strategy!r} min_bars ({self.min_bars}), "
                             "otherwise the strategy can never trade")
        self.frames = _prepare_data(data)
        self.symbols = list(self.frames)
        self.prices = {s: f[["open", "high", "low", "close"]].to_numpy() for s, f in self.frames.items()}
        self.slip = cfg.slippage_pct / 100.0
        self.fee_rate = cfg.fee_pct / 100.0
        self.min_notional = max(0.0, float(cfg.risk.min_order_notional))

        self.cash = float(cfg.starting_cash)
        self.equity = self.cash
        self.fees_paid = 0.0
        self.holdings: dict[str, _Holding] = {}
        self.queued: dict[str, _Order] = {}
        # BUY signals skipped at the last close for want of a slot or cash:
        # sized again at the next open if an exit there made room (see run).
        self.deferred: dict[str, tuple[Signal, float]] = {}
        self.last_close: dict[str, float] = {}
        self.trades: list[Trade] = []

        self.day: date | None = None
        self.day_start_equity = self.cash
        self.trades_today = 0
        self.halted = False

    # ---- main loop ---------------------------------------------------------
    def run(self) -> BacktestResult:
        timeline = self.frames[self.symbols[0]].index
        for symbol in self.symbols[1:]:
            timeline = timeline.union(self.frames[symbol].index)
        days = timeline.tz_convert(ZoneInfo(self.cfg.timezone)).date

        # active[k] = [(symbol, row in that symbol's frame)] for bars at timeline[k]
        active: list[list[tuple[str, int]]] = [[] for _ in range(len(timeline))]
        for symbol in self.symbols:
            for row, k in enumerate(timeline.get_indexer(self.frames[symbol].index)):
                active[k].append((symbol, row))

        equity_pts = np.empty(len(timeline))
        cash_pts = np.empty(len(timeline))
        qty_pts = np.zeros((len(timeline), len(self.symbols)))
        in_market = np.zeros(len(timeline), dtype=bool)

        for k, t in enumerate(timeline):
            bars = active[k]
            self._roll_day(days[k])
            # 1. Orders queued at the previous close fill at this open. Sells
            #    first so their proceeds are available to buys.
            for symbol, row in bars:
                if (order := self.queued.get(symbol)) is not None and order.side is Side.SELL:
                    self._fill_queued(symbol, row, t)
            #    The live engine checks the daily loss limit on its first tick
            #    after the open, before any entry: a gap down can halt the day.
            self._check_daily_loss_at_open(bars, t)
            #    Then symbol by symbol, in `symbols` order like that tick: a
            #    holding whose open is through its stop or target is sold at the
            #    open, freeing its slot and cash for the symbols after it; queued
            #    buys fill; a buy skipped at the close for want of a slot or cash
            #    is sized again once an exit at this open made room for it.
            freed = False
            for symbol, row in bars:
                deferred = self.deferred.pop(symbol, None)
                if self._protective_exit(symbol, row, t, at_open=True):
                    freed = True
                elif (order := self.queued.get(symbol)) is not None and order.side is Side.BUY:
                    self._fill_queued(symbol, row, t)
                elif deferred is not None and freed and not self.halted and symbol not in self.holdings:
                    self._queue_buy(symbol, deferred[1], deferred[0], t)
                    self.deferred.pop(symbol, None)
                    if symbol in self.queued:
                        self._fill_queued(symbol, row, t)
            # 2. Protective exits inside the bar (entry bar included): the lows
            #    first (stop-losses, then the daily loss limit at the lows), and
            #    only then take-profits at the highs, as the order of the high
            #    and the low is unknown (the worst case, like a single stop).
            for symbol, row in bars:
                self._protective_exit(symbol, row, t, take_profit=False)
            self._check_daily_loss_intrabar(bars, t)
            for symbol, row in bars:
                self._protective_exit(symbol, row, t)
            # 3. Mark to market at the close; daily loss limit.
            for symbol, row in bars:
                self.last_close[symbol] = float(self.prices[symbol][row, 3])
            self.equity = self._mark_to_market()
            self._check_daily_loss(t)
            equity_pts[k] = self.equity
            cash_pts[k] = self.cash
            for j, symbol in enumerate(self.symbols):
                if (h := self.holdings.get(symbol)) is not None:
                    qty_pts[k, j] = h.qty
            in_market[k] = bool(self.holdings)
            # 4. Strategy decisions at the close, for fills at the next open.
            for symbol, row in bars:
                self._on_close(symbol, row, t)

        for symbol, order in self.queued.items():
            logger.debug("%s: %s order queued at the last bar never filled (end of data)",
                         symbol, order.side.value)
        self.queued.clear()
        # Force-close whatever is still open at each symbol's last close.
        for symbol in list(self.holdings):
            frame = self.frames[symbol]
            price = float(frame["close"].iloc[-1]) * (1.0 - self.slip)
            self._sell(symbol, price, frame.index[-1], EXIT_END)
        equity_pts[-1] = cash_pts[-1] = self.equity = self.cash
        qty_pts[-1, :] = 0.0

        index = pd.DatetimeIndex(timeline, name="time")
        equity_curve = pd.Series(equity_pts, index=index, name="equity")
        first = self._first_tradable_bar(timeline)
        metrics = _metrics(
            equity_curve, self.trades, self.cfg, fees_paid=self.fees_paid,
            exposure_pct=float(in_market[first or 0:].mean() * 100.0),
            buy_and_hold_pct=self._buy_and_hold_pct(), first_tradable=first,
        )
        return BacktestResult(
            equity_curve=equity_curve,
            trades=self.trades,
            metrics=metrics,
            cash=pd.Series(cash_pts, index=index, name="cash"),
            holdings=pd.DataFrame(qty_pts, index=index, columns=self.symbols),
            strategy=repr(self.strategy),
        )

    # ---- steps -------------------------------------------------------------
    def _roll_day(self, day: date) -> None:
        if day != self.day:
            self.day = day
            self.day_start_equity = self.equity  # equity at the previous close
            self.trades_today = 0
            self.halted = False

    def _fill_queued(self, symbol: str, row: int, t: pd.Timestamp) -> None:
        order = self.queued.pop(symbol)
        open_ = float(self.prices[symbol][row, 0])
        if order.side is Side.SELL:
            if symbol in self.holdings:
                self._sell(symbol, open_ * (1.0 - self.slip), t, order.reason)
        elif symbol not in self.holdings:
            # Gated with the counters of the day the order is sent (this bar),
            # as the live engine does after its day roll.
            if self.halted:
                logger.debug("%s %s: queued buy dropped, daily loss limit hit", t, symbol)
            elif self.trades_today >= self.cfg.risk.max_trades_per_day:
                logger.debug("%s %s: queued buy dropped, max trades per day reached", t, symbol)
            elif self._buy(symbol, open_ * (1.0 + self.slip), order.qty, t):
                self.trades_today += 1

    def _protective_exit(self, symbol: str, row: int, t: pd.Timestamp, at_open: bool = False,
                         take_profit: bool = True) -> bool:
        """Stop-loss / take-profit. The open comes first: a bar that opens
        through either level exits at the open with that level's reason (what
        the live engine's first tick sees). Otherwise, inside the bar, the stop
        wins when both levels were touched. ``at_open``: only the open;
        ``take_profit=False``: not the bar's high. True when it sold."""
        holding = self.holdings.get(symbol)
        if holding is None:
            return False
        open_, high, low, _ = (float(x) for x in self.prices[symbol][row])
        pos = Position(symbol, holding.qty, holding.entry_price, market_price=open_)
        # Same comparisons as the live engine, applied to the open, then the bar's extremes.
        reason = self.risk.exit_reason(pos, open_)
        if reason in (EXIT_STOP, EXIT_TAKE_PROFIT):
            self._sell(symbol, open_ * (1.0 - self.slip), t, reason)
            return True
        if at_open:
            return False
        stop, target = self.risk.stop_price(pos), self.risk.take_profit_price(pos)
        if stop is not None and self.risk.exit_reason(pos, low) == EXIT_STOP:
            self._sell(symbol, stop * (1.0 - self.slip), t, EXIT_STOP)
        elif take_profit and target is not None and self.risk.exit_reason(pos, high) == EXIT_TAKE_PROFIT:
            self._sell(symbol, target * (1.0 - self.slip), t, EXIT_TAKE_PROFIT)
        else:
            return False
        return True

    def _check_daily_loss(self, t: pd.Timestamp) -> None:
        if self.halted or not self.risk.daily_loss_breached(self.equity, self.day_start_equity):
            return
        self._halt(t, self.equity)
        if self.cfg.risk.flatten_on_daily_loss:
            for symbol, holding in self.holdings.items():
                self.queued.setdefault(symbol, _Order(Side.SELL, holding.qty, EXIT_DAILY_LOSS))

    def _check_daily_loss_at_open(self, bars: list[tuple[str, int]], t: pd.Timestamp) -> None:
        """The loss limit against the holdings valued at this bar's opens (the
        last close for symbols without a bar now), before queued buys fill. A
        flatten sells at this open where the symbol trades, else at its next."""
        if self.halted:
            return
        opens = {symbol: float(self.prices[symbol][row, 0]) for symbol, row in bars}
        equity = self.cash + sum(h.qty * opens.get(s, self.last_close[s]) for s, h in self.holdings.items())
        if not self.risk.daily_loss_breached(equity, self.day_start_equity):
            return
        self._halt(t, equity)
        if self.cfg.risk.flatten_on_daily_loss:
            for symbol, holding in list(self.holdings.items()):
                if symbol in opens:
                    self._sell(symbol, opens[symbol] * (1.0 - self.slip), t, EXIT_DAILY_LOSS)
                else:
                    self.queued.setdefault(symbol, _Order(Side.SELL, holding.qty, EXIT_DAILY_LOSS))

    def _check_daily_loss_intrabar(self, bars: list[tuple[str, int]], t: pd.Timestamp) -> None:
        """The loss limit against the holdings valued at this bar's lows (the
        last close for symbols without a bar now). A flatten sells where the
        account crosses the limit as the holdings move from their opens to
        their lows together; symbols without a bar now sell at their next open."""
        if self.halted or not self.holdings:
            return
        rows = {symbol: self.prices[symbol][row] for symbol, row in bars if symbol in self.holdings}

        def value(column: int) -> float:
            return self.cash + sum(h.qty * (float(rows[s][column]) if s in rows else self.last_close[s])
                                   for s, h in self.holdings.items())

        low = value(2)
        if not self.risk.daily_loss_breached(low, self.day_start_equity):
            return
        self._halt(t, low)
        if not self.cfg.risk.flatten_on_daily_loss:
            return
        opened = value(0)
        floor = self.day_start_equity * (1.0 - float(self.cfg.risk.max_daily_loss_pct or 0.0) / 100.0)
        share = min(max((opened - floor) / (opened - low), 0.0), 1.0) if opened > low else 1.0
        for symbol, holding in list(self.holdings.items()):
            if symbol in rows:
                open_, low_ = float(rows[symbol][0]), float(rows[symbol][2])
                self._sell(symbol, (open_ + share * (low_ - open_)) * (1.0 - self.slip), t, EXIT_DAILY_LOSS)
            else:
                self.queued.setdefault(symbol, _Order(Side.SELL, holding.qty, EXIT_DAILY_LOSS))

    def _halt(self, t: pd.Timestamp, equity: float) -> None:
        """Daily loss limit hit: no new entries today; buys still queued are dropped."""
        self.halted = True
        self.deferred.clear()
        logger.info("%s: daily loss limit hit (equity %.2f vs day start %.2f); no new entries today",
                    t, equity, self.day_start_equity)
        for symbol in [s for s, o in self.queued.items() if o.side is Side.BUY]:
            del self.queued[symbol]

    def _on_close(self, symbol: str, row: int, t: pd.Timestamp) -> None:
        if row + 1 < self.min_bars:
            return
        window = self.frames[symbol].iloc[max(0, row + 1 - self.cfg.lookback): row + 1]
        close = self.last_close[symbol]
        holding = self.holdings.get(symbol)
        pos = Position(symbol, holding.qty, holding.entry_price, close) if holding else None
        signal = self.strategy.generate_signal(window, pos)
        if signal.action is Action.SELL:
            if holding is not None and symbol not in self.queued:
                self.queued[symbol] = _Order(Side.SELL, holding.qty, EXIT_SIGNAL)
                logger.debug("%s %s: queue sell (%s)", t, symbol, signal.reason)
        elif signal.action is Action.BUY and holding is None and symbol not in self.queued:
            self._queue_buy(symbol, close, signal, t)

    def _queue_buy(self, symbol: str, price: float, signal: Signal, t: pd.Timestamp) -> None:
        # The halt and the day's trade count are checked when the order is sent
        # (_fill_queued): this close may be the last of the day. Only a count that
        # no day could accept is ruled out here.
        queued_buys = {s: o for s, o in self.queued.items() if o.side is Side.BUY}
        if len(queued_buys) >= self.cfg.risk.max_trades_per_day:
            logger.debug("%s %s: buy skipped, max trades per day already queued", t, symbol)
            return
        reserved = sum(o.reserved for o in queued_buys.values())
        # Exits already queued at this close (by symbols earlier in the loop, or
        # a flatten) free their slot and cash, as the live engine's SELL and
        # account re-read do before it sizes the next symbol in `symbols` order.
        exiting = {s for s, o in self.queued.items() if o.side is Side.SELL and s in self.holdings}
        proceeds = sum(self.holdings[s].qty * self.last_close[s] * (1.0 - self.slip) * (1.0 - self.fee_rate)
                       for s in exiting)
        cash = self.cash + proceeds
        account = Account(equity=self.equity, cash=cash, buying_power=max(0.0, cash - reserved))
        positions = {s: Position(s, h.qty, h.entry_price, self.last_close[s])
                     for s, h in self.holdings.items() if s not in exiting}
        positions.update({s: Position(s, o.qty, o.ref_price, o.ref_price) for s, o in queued_buys.items()})

        qty, why = self.risk.entry_qty(symbol, price, signal, account, positions)
        qty = floor_to_step(qty, self.cfg.qty_step)
        if qty <= 0 or qty * price < self.min_notional:
            logger.debug("%s %s: buy skipped (%s)", t, symbol, why)
            self.deferred[symbol] = (signal, price)
            return
        reserved_cost = qty * price * (1.0 + self.slip) * (1.0 + self.fee_rate)
        self.queued[symbol] = _Order(Side.BUY, qty, signal.reason, ref_price=price, reserved=reserved_cost)
        logger.debug("%s %s: queue buy %s (%s)", t, symbol, why, signal.reason)

    # ---- fills -------------------------------------------------------------
    def _buy(self, symbol: str, price: float, qty: float, t: pd.Timestamp) -> bool:
        """Fill a queued buy (shrunk to what cash affords). False when dropped."""
        affordable = self._affordable_qty(price)
        if qty > affordable:
            logger.debug("%s %s: queued buy of %g shrunk to affordable %g", t, symbol, qty, affordable)
            qty = affordable
        cost = qty * price
        if qty <= 0 or cost < self.min_notional:
            logger.debug("%s %s: queued buy dropped (not affordable at %.6g)", t, symbol, price)
            return False
        fee = cost * self.fee_rate
        self.cash -= cost + fee
        self.fees_paid += fee
        self.holdings[symbol] = _Holding(qty=qty, entry_price=price, entry_time=t, entry_fee=fee)
        logger.debug("%s %s: bought %g @ %.6g (fee %.4f)", t, symbol, qty, price, fee)
        return True

    def _affordable_qty(self, price: float) -> float:
        """Largest qty (on the step grid) whose cost + fee fits in cash."""
        qty = floor_to_step(self.cash / (price * (1.0 + self.fee_rate)), self.cfg.qty_step)
        step = self.cfg.qty_step
        while qty > 0 and qty * price + qty * price * self.fee_rate > self.cash:
            qty = floor_to_step(qty - step, step) if step > 0 else qty * (1.0 - 1e-12)
        return max(qty, 0.0)

    def _sell(self, symbol: str, price: float, t: pd.Timestamp, reason: str) -> None:
        holding = self.holdings.pop(symbol)
        proceeds = holding.qty * price
        fee = proceeds * self.fee_rate
        self.cash += proceeds - fee
        self.fees_paid += fee
        cost_basis = holding.qty * holding.entry_price
        pnl = proceeds - cost_basis - holding.entry_fee - fee
        self.trades.append(Trade(
            symbol=symbol,
            entry_time=holding.entry_time,
            exit_time=t,
            entry_price=holding.entry_price,
            exit_price=price,
            qty=holding.qty,
            pnl=pnl,
            pnl_pct=pnl / cost_basis * 100.0 if cost_basis > 0 else 0.0,
            fees=holding.entry_fee + fee,
            exit_reason=reason,
        ))
        logger.debug("%s %s: sold %g @ %.6g (%s, pnl %.2f)", t, symbol, holding.qty, price, reason, pnl)

    # ---- helpers -----------------------------------------------------------
    def _mark_to_market(self) -> float:
        return self.cash + sum(h.qty * self.last_close[s] for s, h in self.holdings.items())

    def _first_tradable_bar(self, timeline: pd.DatetimeIndex) -> int | None:
        """Timeline position of the first bar a fill can happen at: the one
        after the earliest first signal bar (row ``min_bars - 1``) of any
        symbol. None when no symbol ever has enough bars to trade."""
        signal_bars = [timeline.get_loc(frame.index[self.min_bars - 1])
                       for frame in self.frames.values() if len(frame) >= self.min_bars]
        if not signal_bars or min(signal_bars) + 1 >= len(timeline):
            return None
        return int(min(signal_bars)) + 1

    def _buy_and_hold_pct(self) -> float:
        """Equal-weight buy & hold from each symbol's first possible fill (the
        open after its first signal bar), same slippage + fee on entry, valued
        at its last close."""
        returns = []
        for frame in self.frames.values():
            if len(frame) <= self.min_bars:
                continue
            entry = float(frame["open"].iloc[self.min_bars]) * (1.0 + self.slip) * (1.0 + self.fee_rate)
            returns.append(float(frame["close"].iloc[-1]) / entry - 1.0)
        return float(np.mean(returns) * 100.0) if returns else math.nan


def _prepare_data(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    if not data:
        raise ValueError("no data: pass at least one symbol's bars")
    frames: dict[str, pd.DataFrame] = {}
    for symbol, bars in data.items():
        if not isinstance(symbol, str) or not symbol:
            raise ValueError(f"symbol names must be non-empty strings, got {symbol!r}")
        try:
            frame = validate_bars(bars)
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError(f"{symbol}: invalid bars: {exc}") from exc
        if frame.empty:
            raise ValueError(f"{symbol}: no bars")
        if (frame[["open", "high", "low", "close"]] <= 0).any().any():
            raise ValueError(f"{symbol}: prices must be > 0")
        frames[symbol] = frame
    return frames


# --------------------------------------------------------------------------- metrics


def _metrics(equity: pd.Series, trades: list[Trade], cfg: BacktestConfig, *, fees_paid: float,
             exposure_pct: float, buy_and_hold_pct: float, first_tradable: int | None = None) -> dict[str, float]:
    """Headline metrics. CAGR, Sharpe and volatility cover the trading period,
    from bar ``first_tradable`` (the first a fill can happen at) on; the bars
    before it are the strategy's warm-up, flat by construction. Total return
    and drawdown are the same over either span."""
    start_cash = float(cfg.starting_cash)
    final = float(equity.iloc[-1])
    total_return = (final / start_cash - 1.0) * 100.0
    first = first_tradable or 0

    span = equity.index[-1] - equity.index[first] + timeframe_to_timedelta(cfg.timeframe)
    years = span / pd.Timedelta(days=365.25)
    if final <= 0:
        cagr = -100.0
    elif years > 0:
        cagr = ((final / start_cash) ** (1.0 / years) - 1.0) * 100.0
    else:
        cagr = math.nan

    # From the close before the first tradable bar: the first return is that bar's.
    returns = equity.iloc[max(first - 1, 0):].pct_change().dropna()
    per_year = bars_per_year(cfg.timeframe, cfg.trading_days_per_year)
    if len(returns) < 2:
        sharpe = volatility = math.nan
    else:
        std = float(returns.std(ddof=1))
        volatility = std * math.sqrt(per_year) * 100.0
        sharpe = float(returns.mean()) / std * math.sqrt(per_year) if std > 0 else 0.0

    pnls = [t.pnl for t in trades]
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = -sum(p for p in pnls if p < 0)
    if not trades:
        profit_factor = math.nan
    elif gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    else:
        profit_factor = math.inf if gross_profit > 0 else math.nan

    return {
        "total_return_pct": total_return,
        "cagr_pct": cagr,
        "max_drawdown_pct": max_drawdown_pct(equity),
        "sharpe": sharpe,
        "volatility_ann_pct": volatility,
        "num_trades": float(len(trades)),
        "win_rate_pct": sum(p > 0 for p in pnls) / len(trades) * 100.0 if trades else math.nan,
        "avg_trade_pct": float(np.mean([t.pnl_pct for t in trades])) if trades else math.nan,
        "profit_factor": profit_factor,
        "exposure_pct": exposure_pct,
        "fees_paid": fees_paid,
        "buy_and_hold_return_pct": buy_and_hold_pct,
        "final_equity": final,
        # Bar times as POSIX seconds (metrics are all floats); summary()/save() render dates.
        "start": equity.index[0].timestamp(),
        "end": equity.index[-1].timestamp(),
        # The trading period: from this bar on, after `warmup_bars` warm-up bars.
        "tradable_from": equity.index[first_tradable].timestamp() if first_tradable is not None else math.nan,
        "warmup_bars": float(first_tradable if first_tradable is not None else len(equity)),
    }


# --------------------------------------------------------------------------- formatting


def _is_number(value: object) -> bool:
    return isinstance(value, numbers.Real) and not isinstance(value, bool) and math.isfinite(value)


def _fmt_num(value: float | None) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    if math.isinf(value):
        return "inf" if value > 0 else "-inf"
    return f"{value:,.2f}"


def _fmt_pct(value: float | None, signed: bool = False) -> str:
    text = _fmt_num(value)
    if text in ("n/a", "inf", "-inf"):
        return text
    return f"{value:+,.2f}%" if signed else f"{text}%"


def _fmt_int(value: float | None) -> str:
    return "n/a" if value is None or not math.isfinite(value) else f"{int(value):,}"


def _fmt_date(value: float | None, iso: bool = False) -> str | None:
    if value is None or not math.isfinite(value):
        return None if iso else "n/a"
    ts = datetime.fromtimestamp(value, tz=timezone.utc)
    if iso:
        return ts.isoformat()
    return ts.strftime("%Y-%m-%d") if ts.hour == ts.minute == 0 else ts.strftime("%Y-%m-%d %H:%M")


def _fmt_span(days: float) -> str:
    return f"{days:.1f} days" if days >= 1 else f"{days * 24:.1f} hours"


def _json_number(value: object) -> object:
    """NaN -> null, +/-inf -> "inf"/"-inf" (strict JSON has neither)."""
    if isinstance(value, numbers.Real) and not isinstance(value, bool):
        value = float(value)
        if math.isnan(value):
            return None
        if math.isinf(value):
            return "inf" if value > 0 else "-inf"
    return value


__all__ = ["BacktestConfig", "BacktestResult", "Trade", "run_backtest", "max_drawdown_pct"]
