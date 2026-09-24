"""Command-line interface: ``python -m bot <command>``.

Commands (``python -m bot <command> -h`` for details):

  demo         zero-setup tour: backtests + a few simulated trading checks
  strategies   list the built-in strategies and their default settings
  backtest     test the configured strategy on history (synthetic, CSV or broker data)
  once         run one trading check and exit (for cron / GitHub Actions)
  run          trade automatically until Ctrl-C / SIGTERM
  status       account, positions, bot state and kill switch
  flatten      sell every open position (needs --yes)
  kill/resume  turn the kill switch on / off

Exit codes: 0 ok, 1 runtime/broker error (or a check that had errors),
2 configuration or usage problem, 130 interrupted.
"""
from __future__ import annotations

import argparse
import json
import logging
import logging.handlers
import math
import os
import shlex
import signal
import sys
import tempfile
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from . import __version__
from .brokers.base import BrokerError
from .config import BotConfig, ConfigError, NotifyConfig, assert_live_allowed, load_config
from .models import OrderResult, Position
from .risk import RiskConfig, RiskManager
from .state import STATE_FILE, BotState, kill_switch_active, kill_switch_reason, set_kill_switch
from .strategies import STRATEGIES, create_strategy
from .utils import timeframe_to_timedelta, utcnow

try:
    import fcntl
except ImportError:  # Windows: no advisory file locks
    fcntl = None  # type: ignore[assignment]

if TYPE_CHECKING:
    import pandas as pd

    from .backtest import BacktestResult
    from .brokers.base import Broker
    from .engine import TickReport, TradingEngine
    from .strategies.base import Strategy

logger = logging.getLogger(__name__)

EXIT_OK, EXIT_ERROR, EXIT_USAGE, EXIT_INTERRUPTED = 0, 1, 2, 130

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = "config.yaml"
DEMO_CONFIG = "configs/demo.yaml"
LOCK_FILE = "bot.lock"
LOG_FILE = "bot.log"
LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_BACKUPS = 5
DEFAULT_BACKTEST_BARS = 1000
# Seconds between the LIVE warning and the first live tick (Ctrl-C aborts).
LIVE_START_DELAY_SECONDS = 10

DEMO_BARS = 1500
DEMO_TICKS = 3
DEMO_LOOKBACK = 300
DEMO_SYMBOLS = (("SIM-A", 100.0), ("SIM-B", 40.0), ("SIM-C", 250.0))  # name, start price

# Console log level per command. Commands that print their own report only
# show errors (warnings would repeat what they print); ``run`` shows its
# activity. The log file always gets INFO (DEBUG with -v).
_CONSOLE_LEVELS = {"run": logging.INFO, "backtest": logging.WARNING, "demo": logging.WARNING}
_SKIPPED = {
    "kill_switch": "the kill switch is ON: nothing was checked and no orders were sent",
    "trading_blocked": "the broker reports that trading is blocked on this account",
    "market_closed": "the market is closed; nothing to do until it opens",
}
_LIVE_WARNING = "\n".join([
    "!" * 66,
    "!!! LIVE TRADING: this bot places REAL orders with REAL money,",
    "!!! automatically, until you stop it. You can lose money fast,",
    "!!! including through bugs, outages and bad fills.",
    "!!!   Pause trading:    python -m bot kill",
    "!!!   Sell everything:  python -m bot flatten --yes",
    "!" * 66,
])


class CLIError(Exception):
    """A problem reported to the user as a plain message (no traceback)."""

    def __init__(self, message: str, code: int = EXIT_ERROR) -> None:
        super().__init__(message)
        self.code = code


# --------------------------------------------------------------------------- entry point
def main(argv: Sequence[str] | None = None) -> int:
    """Run one CLI command and return its exit code."""
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # --help / --version, or a usage error argparse already printed
        return exc.code if isinstance(exc.code, int) else (EXIT_OK if exc.code is None else EXIT_USAGE)
    if args.command is None:
        parser.print_help()
        return EXIT_USAGE

    console_level = logging.DEBUG if args.verbose else _CONSOLE_LEVELS.get(args.command, logging.ERROR)
    args.logs = _LogSetup(console_level, verbose=args.verbose)
    try:
        return args.handler(args)
    except ConfigError as exc:
        _error(f"Configuration problem: {exc}")
        return EXIT_USAGE
    except CLIError as exc:
        _error(str(exc))
        return exc.code
    except BrokerError as exc:
        _error(f"Broker error: {exc}")
        return EXIT_ERROR
    except BrokenPipeError:  # output piped into e.g. `head`, which exited early
        return EXIT_ERROR
    except OSError as exc:
        _error(f"File or system error: {exc}")
        return EXIT_ERROR
    except KeyboardInterrupt:
        _error("Interrupted.")
        return EXIT_INTERRUPTED
    finally:
        args.logs.close()


def build_parser() -> argparse.ArgumentParser:
    # -c/-v are accepted before AND after the command (``run -c x.yaml`` is what
    # people type). SUPPRESS keeps a subcommand from resetting a global value.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-c", "--config", default=argparse.SUPPRESS, metavar="PATH",
                        help=f"config file (default: {DEFAULT_CONFIG})")
    common.add_argument("-v", "--verbose", action="store_true", default=argparse.SUPPRESS,
                        help="show debug logs")

    parser = argparse.ArgumentParser(
        prog="python -m bot",
        description="Automated trading bot. Paper trading (simulated money) unless you opt in to live trading.",
        epilog="New here? Start with:  python -m bot demo",
    )
    parser.add_argument("-c", "--config", default=None, metavar="PATH",
                        help=f"config file (default: {DEFAULT_CONFIG}; the demo uses {DEMO_CONFIG})")
    parser.add_argument("-v", "--verbose", action="store_true", default=False, help="show debug logs")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    def add(name: str, handler: Any, text: str) -> argparse.ArgumentParser:
        p = sub.add_parser(name, parents=[common], help=text, description=text)
        p.set_defaults(handler=handler)
        return p

    p = add("demo", cmd_demo, "zero-setup tour: no keys, no internet, no real money")
    p.add_argument("--bars", type=_positive_int, default=DEMO_BARS, metavar="N",
                   help=f"days of made-up history to backtest (default {DEMO_BARS})")
    p.add_argument("--ticks", type=_positive_int, default=DEMO_TICKS, metavar="N",
                   help=f"simulated trading checks to run (default {DEMO_TICKS})")

    add("strategies", cmd_strategies, "list the built-in strategies and their default settings")

    p = add("backtest", cmd_backtest, "test the configured strategy on historical data")
    source = p.add_mutually_exclusive_group()
    source.add_argument("--synthetic", action="store_true", help="use made-up prices (no network)")
    source.add_argument("--csv", action="append", type=_csv_spec, metavar="SYMBOL=PATH",
                        help="load one symbol's bars from a CSV file (repeatable)")
    p.add_argument("--bars", type=_positive_int, default=None, metavar="N",
                   help=f"bars per symbol (default {DEFAULT_BACKTEST_BARS}; with --csv: keep the last N)")
    p.add_argument("--out", type=Path, default=None, metavar="DIR",
                   help="folder for equity.csv, trades.csv, metrics.json (default results/<timestamp>)")

    add("once", cmd_once, "run one trading check and exit (for cron / GitHub Actions)")

    p = add("run", cmd_run, "trade automatically until Ctrl-C")
    p.add_argument("--max-ticks", type=_positive_int, default=None, metavar="N",
                   help="stop after N checks (default: run until stopped)")

    add("status", cmd_status, "show account, positions, bot state and kill switch")

    p = add("flatten", cmd_flatten, "sell ALL open positions at the market price")
    p.add_argument("--yes", action="store_true", help="confirm that you really want to sell everything")

    p = add("kill", cmd_kill, "turn the kill switch ON: the bot stops placing orders")
    p.add_argument("--reason", default="", help="note saved with the kill switch")

    add("resume", cmd_resume, "turn the kill switch OFF: the bot may trade again")
    return parser


# --------------------------------------------------------------------------- commands
def cmd_strategies(args: argparse.Namespace) -> int:
    print("Built-in strategies (pick one with strategy.name in your config):")
    for name, cls in STRATEGIES.items():
        strategy = create_strategy(name)
        description = cls.description or (cls.__doc__ or "").strip().split("\n")[0]
        print(f"\n  {name}")
        if description:
            print(f"    {description}")
        print(f"    Defaults: {_params_text(strategy.params)}  (needs {strategy.min_bars} bars of history)")
    print("\nChange settings under strategy.params, for example:")
    print("  strategy:\n    name: rsi_reversion\n    params:\n      entry_rsi: 5")
    print("Then test it before trading:  python -m bot backtest --synthetic")
    return EXIT_OK


def cmd_demo(args: argparse.Namespace) -> int:
    from .backtest import BacktestConfig, run_backtest
    from .data import generate_synthetic_bars

    path = Path(args.config).expanduser() if args.config else _find_demo_config()
    cfg = load_config(path, env={})  # the demo never reads secrets: no notifications, no keys
    if cfg.broker.type != "sim":
        raise ConfigError(f"the demo runs only on the built-in simulator (broker type sim), but {path} uses "
                          f"broker type {cfg.broker.type}. Run `python -m bot demo` without -c to use {DEMO_CONFIG}.")
    strategies = {name: create_strategy(name) for name in STRATEGIES}
    needed = max(s.min_bars for s in strategies.values()) + 1
    if args.bars < needed:
        raise CLIError(f"--bars must be at least {needed} so every strategy can warm up", EXIT_USAGE)

    b = cfg.broker
    print("=" * 66)
    print(" Trading bot demo: no API keys, no internet, no real money")
    print("=" * 66)
    print(f"\nStep 1 of 2: backtest the {len(strategies)} built-in strategies (default settings) on "
          f"{args.bars:,} days\nof made-up prices for {len(DEMO_SYMBOLS)} symbols, starting with "
          f"{_money(b.starting_cash, _currency(cfg))}, fee {b.fee_pct:g}% + slippage {b.slippage_pct:g}% "
          "per trade.\n")
    data = {symbol: generate_synthetic_bars(args.bars, "1d", seed=b.sim_seed + i, start_price=price)
            for i, (symbol, price) in enumerate(DEMO_SYMBOLS)}
    results = {}
    for name, strategy in strategies.items():
        bt_cfg = BacktestConfig(starting_cash=b.starting_cash, fee_pct=b.fee_pct, slippage_pct=b.slippage_pct,
                                lookback=max(DEMO_LOOKBACK, strategy.min_bars), timeframe="1d",
                                trading_days_per_year=365, timezone="UTC", risk=cfg.risk)
        results[name] = run_backtest(strategy, data, bt_cfg)
    print(_comparison_table(results))
    print("\n  Buy & hold = holding all symbols equally over the same period, for comparison.")
    print("  Made-up prices: this shows how the tools work, not what you would earn.")

    step = timeframe_to_timedelta(cfg.timeframe)
    print(f"\nStep 2 of 2: the live trading loop, {args.ticks} checks on the simulator with a temporary "
          f"paper account.\n  Symbols {', '.join(cfg.symbols)} | {cfg.timeframe} bars | strategy "
          f"{_strategy_label(cfg)}\n  The simulator fast-forwards one {cfg.timeframe} bar between checks, "
          "so you do not have to wait.")
    with tempfile.TemporaryDirectory(prefix="bot-demo-") as tmp:
        _demo_ticks(cfg, Path(tmp), args.ticks, step)

    steps = [
        ("python -m bot strategies", "what each strategy does"),
        ("python -m bot backtest --synthetic -c configs/stocks.yaml", "a daily-bar strategy on made-up prices"),
        (f"python -m bot run -c {shlex.quote(_display_path(path))}", "paper-trade on the simulator, Ctrl-C stops"),
    ]
    width = max(len(command) for command, _ in steps)
    print("\nNext steps:")
    for command, what in steps:
        print(f"  {command:<{width}}  # {what}")
    print("  configs/stocks.yaml (Alpaca paper account) and configs/crypto.yaml (Upbit prices, local paper")
    print("  account) are ready-made examples. Paper-trade for weeks before even thinking about live mode.")
    return EXIT_OK


def cmd_backtest(args: argparse.Namespace) -> int:
    from .backtest import BacktestConfig, run_backtest

    cfg = _load(args)
    strategy = _make_strategy(cfg)
    bars = args.bars or DEFAULT_BACKTEST_BARS
    if args.csv:
        data = _csv_data(args.csv, args.bars)
        source = "CSV files"
    elif args.synthetic:
        data = _synthetic_data(cfg, bars)
        source = f"synthetic prices (seed {cfg.broker.sim_seed}, no network)"
    else:
        data = _fetch_data(cfg, bars)
        source = f"{cfg.broker.type} market data"
    longest = max(len(frame) for frame in data.values())
    if longest < strategy.min_bars + 1:
        raise CLIError(f"not enough history: {longest} bars, but {cfg.strategy.name} needs {strategy.min_bars} "
                       "bars just to warm up; use more --bars (or a longer CSV)", EXIT_USAGE)

    b = cfg.broker
    bt_cfg = BacktestConfig(
        starting_cash=b.starting_cash, fee_pct=b.fee_pct, slippage_pct=b.slippage_pct,
        lookback=cfg.bars_lookback, timeframe=cfg.timeframe,
        trading_days_per_year=252 if b.type == "alpaca" else 365,
        timezone=cfg.timezone, risk=cfg.risk,
    )
    print(f"Backtest: {_strategy_label(cfg)}")
    print(f"Data:     {source}; " + ", ".join(f"{s} {len(f):,} bars" for s, f in data.items()))
    print(f"Costs:    fee {b.fee_pct:g}% + slippage {b.slippage_pct:g}% per trade, "
          f"starting cash {_money(b.starting_cash, _currency(cfg))}\n")
    try:
        result = run_backtest(strategy, data, bt_cfg)
    except ValueError as exc:
        raise CLIError(f"backtest failed: {exc}") from exc
    print(result.summary())
    out = args.out if args.out is not None else Path("results") / datetime.now().strftime("%Y%m%d-%H%M%S")
    result.save(out)
    print(f"\nSaved equity.csv, trades.csv and metrics.json to {out}")
    print("Backtests are optimistic: real fills, outages and changing markets will differ.")
    return EXIT_OK


def cmd_once(args: argparse.Namespace) -> int:
    cfg = _load(args)
    assert_live_allowed(cfg)
    with _InstanceLock(cfg.state_dir):
        broker = _make_broker(cfg)
        engine = _build_engine(cfg, broker)
        if cfg.is_live:
            print("LIVE mode: real orders with real money.")
        report = engine.run_once()
    print(f"{_mode_label(cfg)} check at {_ts(report.started_at)} | {_broker_label(cfg)} | "
          f"{cfg.strategy.name} on {cfg.timeframe} bars")
    _print_report(report, _currency(cfg))
    return EXIT_ERROR if report.errors else EXIT_OK


def cmd_run(args: argparse.Namespace) -> int:
    cfg = _load(args)
    assert_live_allowed(cfg)
    stop = threading.Event()
    with _InstanceLock(cfg.state_dir):
        broker = _make_broker(cfg)
        engine = _build_engine(cfg, broker)
        print(_banner(cfg, args))
        if cfg.is_live:
            logger.warning("LIVE trading started: real orders with real money")
        with _stop_on_signals(stop):
            delay = LIVE_START_DELAY_SECONDS
            if cfg.is_live and delay > 0:
                print(f"Starting LIVE trading in {delay}s. Press Ctrl-C now to abort.", flush=True)
                if stop.wait(delay):
                    print("Aborted before the first check: no orders were sent.")
                    return EXIT_OK
            engine.run_forever(stop, max_ticks=args.max_ticks)
    print("Bot stopped. Open positions (if any) stay open; start the bot again to keep managing them.")
    return EXIT_OK


def cmd_status(args: argparse.Namespace) -> int:
    cfg = _load(args)
    broker = _make_broker(cfg)
    code = EXIT_OK
    print(f"{_mode_label(cfg)} | {_broker_label(cfg)} | {_strategy_label(cfg)} on {cfg.timeframe} bars")
    print(f"Config: {cfg.config_path}")

    account = None
    print("\nAccount")
    try:
        account = broker.get_account()
        positions = {s: p for s, p in broker.get_positions().items() if p.qty > 0}
    except BrokerError as exc:
        print(f"  Could not read the account from the broker: {exc}")
        code = EXIT_ERROR
    else:
        cur = account.currency
        print(f"  Equity        {_money(account.equity, cur)}")
        print(f"  Cash          {_money(account.cash, cur)}")
        print(f"  Buying power  {_money(account.buying_power, cur)}")
        try:
            print(f"  Market        {'open' if broker.is_market_open() else 'closed'}")
        except BrokerError as exc:
            print(f"  Market        unknown ({exc})")
        if account.trading_blocked:
            print("  WARNING: the broker reports that trading is BLOCKED on this account")
        print(f"\nPositions ({len(positions)})")
        print(_positions_table(positions) if positions else "  none")

    state_path = cfg.state_dir / STATE_FILE
    state, problem = _read_state(state_path)
    print("\nBot state")
    if problem:
        print(f"  {problem}")
    elif state is None:
        print(f"  The bot has not run yet (no {state_path}).")
    else:
        print(f"  Last check        {_ago(state.last_tick_at)}")
        if state.day:
            day = f"{state.day} ({cfg.timezone})"
            if state.day_start_equity:
                day += f", started at {state.day_start_equity:,.2f}"
                if account is not None:
                    day += f" ({_pct((account.equity / state.day_start_equity - 1) * 100, signed=True)} since)"
            print(f"  Trading day       {day}")
        print(f"  New trades today  {state.trades_today} of max {cfg.risk.max_trades_per_day}")
        print(f"  Daily loss halt   {'YES: no new entries until tomorrow' if state.halted_today else 'no'}")
        print(f"  Errors in a row   {state.consecutive_errors}")
        for symbol, bar in sorted(state.last_signal_bar.items()):
            print(f"  Last bar {symbol:<9}{bar}")

    print(f"\nKill switch: {_kill_text(cfg, args)}")
    return code


def cmd_flatten(args: argparse.Namespace) -> int:
    if not args.yes:
        _error("flatten sells EVERY open position at the market price. Nothing was done.\n"
               f"To confirm, run:  {_hint(args, 'flatten --yes')}")
        return EXIT_USAGE
    from .brokers.paper import PaperBroker

    cfg = _load(args)
    assert_live_allowed(cfg)
    lock = _InstanceLock(cfg.state_dir)
    bot_running = not lock.acquire()
    try:
        broker = _make_broker(cfg)
        if bot_running:
            if isinstance(broker, PaperBroker):
                raise CLIError("the bot is running right now and keeps this simulated paper account in its "
                               "memory, so it would undo a flatten from here. Stop it first (Ctrl-C), then "
                               "run flatten again.")
            print("Note: the bot is running; it may buy again on its next signal. "
                  f"Pause it with:  {_hint(args, 'kill')}")
        print(f"Closing all positions | {_mode_label(cfg)} | {_broker_label(cfg)}")
        logger.warning("flatten: closing all positions (%s mode)", cfg.mode)
        results = broker.close_all_positions()
    finally:
        lock.release()

    if not results:
        print("No open positions to close (any working orders were cancelled).")
    for result in results:
        line = _order_text(result)
        logger.warning("flatten: %s", line)
        print(f"  {line}")
    rejected = [r for r in results if not r.ok]
    if results:
        print(f"{len(results) - len(rejected)} of {len(results)} sell order(s) sent."
              + (" Some were REJECTED: check them with the broker." if rejected else ""))
    if not kill_switch_active(cfg.state_dir):
        print(f"The bot will open new positions on its next buy signal. To stop that too:  {_hint(args, 'kill')}")
    return EXIT_ERROR if rejected else EXIT_OK


def cmd_kill(args: argparse.Namespace) -> int:
    cfg = _load(args)
    previous = kill_switch_reason(cfg.state_dir)
    if previous is not None and not args.reason:
        print(f"Kill switch was already ON{_reason_suffix(previous)}. Nothing changed.")
    else:
        reason = args.reason or f"manual kill switch, {utcnow():%Y-%m-%d %H:%M} UTC"
        set_kill_switch(cfg.state_dir, True, reason)
        print(f"Kill switch is ON ({reason}).")
    print("  The bot keeps running but checks nothing and places NO orders until you resume.")
    print(f"  Open positions are NOT sold. To sell everything:  {_hint(args, 'flatten --yes')}")
    print(f"  To allow trading again:  {_hint(args, 'resume')}")
    return EXIT_OK


def cmd_resume(args: argparse.Namespace) -> int:
    cfg = _load(args)
    previous = kill_switch_reason(cfg.state_dir)
    if previous is None:
        print("Kill switch is already OFF: the bot is allowed to trade.")
        return EXIT_OK
    set_kill_switch(cfg.state_dir, False)
    print("Kill switch is OFF: the bot trades again on its next check."
          + (f"\n  It had been turned on with the note: {previous}" if previous else ""))
    return EXIT_OK


# --------------------------------------------------------------------------- building blocks
def _load(args: argparse.Namespace) -> BotConfig:
    """Resolve the config path, load ``.env`` files, validate the config and
    start file logging in its log_dir."""
    path = _config_path(args)
    _load_env_files(path)
    cfg = load_config(path)
    args.logs.add_file(Path(cfg.log_dir))
    logger.info("python -m bot %s (config %s, %s mode)", args.command, cfg.config_path, cfg.mode)
    return cfg


def _config_path(args: argparse.Namespace) -> Path:
    if args.config:
        return Path(args.config).expanduser()
    path = Path(DEFAULT_CONFIG)
    if not path.is_file():
        raise ConfigError(
            f"no config file given and {DEFAULT_CONFIG} does not exist in {Path.cwd()}. "
            f"Pass one with -c (e.g. `python -m bot {args.command} -c {DEMO_CONFIG}`) or copy an example "
            f"from configs/ to {DEFAULT_CONFIG}. Just exploring? Run `python -m bot demo`.")
    return path


def _find_demo_config() -> Path:
    for base in (Path.cwd(), PROJECT_ROOT):
        candidate = base / DEMO_CONFIG
        if candidate.is_file():
            return candidate
    raise ConfigError(f"cannot find {DEMO_CONFIG}; run from the trading-bot folder or pass a sim config with -c")


def _load_env_files(config_path: Path) -> list[Path]:
    """Load ``.env`` from the working directory and the config's directory.
    Variables already set in the real environment always win."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        logger.warning("python-dotenv is not installed; .env files are ignored")
        return []
    loaded = []
    for directory in dict.fromkeys([Path.cwd().resolve(), config_path.expanduser().resolve().parent]):
        env_file = directory / ".env"
        if env_file.is_file():
            load_dotenv(env_file, override=False)
            loaded.append(env_file)
            logger.debug("Loaded environment variables from %s", env_file)
    return loaded


def _make_strategy(cfg: BotConfig) -> Strategy:
    try:
        return create_strategy(cfg.strategy.name, dict(cfg.strategy.params))
    except (ValueError, TypeError) as exc:
        raise ConfigError(f"strategy: {exc}") from exc


def _make_broker(cfg: BotConfig) -> Broker:
    from .brokers import make_broker

    assert_live_allowed(cfg)  # refuse real money before any broker object exists
    return make_broker(cfg)


def _build_engine(cfg: BotConfig, broker: Broker, clock: Any = None) -> TradingEngine:
    from .engine import TradingEngine
    from .notify import Notifier
    from .state import StateStore

    try:
        risk = RiskManager(cfg.risk)
    except ValueError as exc:
        raise ConfigError(f"risk: {exc}") from exc
    extra = {} if clock is None else {"clock": clock}
    return TradingEngine(cfg, broker, _make_strategy(cfg), risk, StateStore(Path(cfg.state_dir) / STATE_FILE),
                         Notifier(cfg.notify, mode=cfg.mode), **extra)


def _synthetic_data(cfg: BotConfig, bars: int) -> dict[str, pd.DataFrame]:
    from .data import generate_synthetic_bars

    return {symbol: generate_synthetic_bars(bars, cfg.timeframe, seed=cfg.broker.sim_seed + i)
            for i, symbol in enumerate(cfg.symbols)}


def _csv_data(specs: list[tuple[str, str]], bars: int | None) -> dict[str, pd.DataFrame]:
    from .data import load_csv_bars

    data: dict[str, pd.DataFrame] = {}
    for symbol, path in specs:
        if symbol in data:
            raise CLIError(f"--csv: {symbol} is given twice", EXIT_USAGE)
        try:
            frame = load_csv_bars(path)
        except (OSError, ValueError) as exc:
            raise CLIError(f"--csv {symbol}: cannot load {path}: {exc}", EXIT_USAGE) from exc
        if frame.empty:
            raise CLIError(f"--csv {symbol}: {path} has no bars", EXIT_USAGE)
        data[symbol] = frame.tail(bars) if bars else frame
    return data


def _fetch_data(cfg: BotConfig, bars: int) -> dict[str, pd.DataFrame]:
    from .brokers import make_broker
    from .utils import drop_incomplete_bars, validate_bars

    # A backtest only reads market data, so always build the PAPER variant of
    # the broker (public exchange data for ccxt, not the testnet): it can never
    # reach a live account and needs no live-trading confirmation.
    data_cfg = replace(cfg, mode="paper", broker=replace(cfg.broker, use_sandbox=False))
    broker = make_broker(data_cfg)
    data: dict[str, pd.DataFrame] = {}
    for symbol in cfg.symbols:
        print(f"Fetching {bars:,} {cfg.timeframe} bars for {symbol} ...", flush=True)
        try:
            frame = drop_incomplete_bars(validate_bars(broker.get_bars(symbol, cfg.timeframe, bars)), cfg.timeframe)
        except ValueError as exc:
            raise CLIError(f"{symbol}: the broker returned unusable bars: {exc}") from exc
        if frame.empty:
            raise CLIError(f"{symbol}: the broker returned no bars")
        if len(frame) < bars:
            print(f"  Note: got {len(frame):,} of the {bars:,} bars asked for (the venue's history limit)")
        data[symbol] = frame
    return data


def _demo_ticks(cfg: BotConfig, workdir: Path, ticks: int, step: timedelta) -> None:
    """Run ``ticks`` engine checks on a throwaway sim paper account in ``workdir``."""
    from .brokers.paper import PaperBroker
    from .data import SyntheticFeed

    clock = _SteppingClock(_floor_time(utcnow(), step) + timedelta(seconds=1), step)
    demo_cfg = replace(cfg, state_dir=workdir / "state", log_dir=workdir / "logs", notify=NotifyConfig())
    b = cfg.broker
    broker = PaperBroker(SyntheticFeed(seed=b.sim_seed, clock=clock), starting_cash=b.starting_cash,
                         fee_pct=b.fee_pct, slippage_pct=b.slippage_pct,
                         state_path=demo_cfg.state_dir / "paper_account.json", clock=clock)
    engine = _build_engine(demo_cfg, broker, clock=clock)
    currency = _currency(cfg)
    for i in range(1, ticks + 1):
        if i > 1:
            clock.advance()
        report = engine.run_once()
        print(f"\nCheck {i} of {ticks} ({_ts(report.started_at)})")
        _print_report(report, currency)

    account = broker.get_account()
    positions = broker.get_positions()
    print(f"\nPaper account after {ticks} checks: equity {_money(account.equity, currency)}, "
          f"cash {_money(account.cash, currency)} (started with {_money(b.starting_cash, currency)})")
    print(_positions_table(positions) if positions else "  No open positions.")


class _SteppingClock:
    """Demo clock: frozen during a check, jumps one bar between checks."""

    def __init__(self, start: datetime, step: timedelta) -> None:
        self.now = start
        self.step = step

    def __call__(self) -> datetime:
        return self.now

    def advance(self) -> None:
        self.now += self.step


def _floor_time(when: datetime, step: timedelta) -> datetime:
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    return epoch + ((when - epoch) // step) * step


class _InstanceLock:
    """Exclusive lock on ``state_dir/bot.lock`` so two bot processes never trade
    the same account and state at once (they could send duplicate orders).
    A no-op where ``fcntl`` is unavailable (Windows)."""

    def __init__(self, state_dir: Path) -> None:
        self.path = Path(state_dir) / LOCK_FILE
        self._fh: Any = None

    def acquire(self) -> bool:
        """True when acquired, False when another process holds the lock."""
        if fcntl is None:
            return True
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(self.path, "a+", encoding="utf-8")  # noqa: SIM115 - held until release()
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            return False
        fh.seek(0)
        fh.truncate()
        fh.write(f"{os.getpid()}\n")
        fh.flush()
        self._fh = fh
        return True

    def release(self) -> None:
        if self._fh is not None:
            self._fh.close()  # closing the file releases the lock
            self._fh = None

    def __enter__(self) -> _InstanceLock:
        if not self.acquire():
            raise CLIError(f"another bot process is already running with the state folder {self.path.parent}. "
                           "Refusing to start a second one: two bots on one account could place duplicate "
                           "orders. Stop the other one first (Ctrl-C in its window).")
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.release()


@contextmanager
def _stop_on_signals(stop: threading.Event) -> Iterator[None]:
    """SIGINT (Ctrl-C) / SIGTERM set ``stop`` so the loop ends after the current
    step; a second Ctrl-C aborts immediately. Handlers are restored afterwards."""
    if threading.current_thread() is not threading.main_thread():
        yield
        return

    def handler(signum: int, frame: object) -> None:
        if stop.is_set():
            raise KeyboardInterrupt
        logger.warning("Received %s: stopping after the current step (press Ctrl-C again to force)",
                       signal.Signals(signum).name)
        stop.set()

    previous = {}
    for sig in (signal.SIGINT, getattr(signal, "SIGTERM", None)):
        if sig is not None:
            previous[sig] = signal.signal(sig, handler)
    try:
        yield
    finally:
        for sig, old in previous.items():
            signal.signal(sig, old)


class _LogSetup:
    """Console logging (stderr) now, plus a rotating ``bot.log`` once the
    config's log_dir is known. Everything is undone by :meth:`close`, so
    ``main()`` can run many times in one process (tests)."""

    def __init__(self, console_level: int, verbose: bool = False) -> None:
        self.root = logging.getLogger()
        self.previous_level = self.root.level
        self.file_level = logging.DEBUG if verbose else logging.INFO
        self.handlers: list[logging.Handler] = []
        console = logging.StreamHandler(sys.stderr)
        console.setLevel(console_level)
        console.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S"))
        self._add(console)

    def add_file(self, log_dir: Path) -> None:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            handler = logging.handlers.RotatingFileHandler(
                log_dir / LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUPS, encoding="utf-8")
        except OSError as exc:
            logger.warning("Cannot write %s (%s); logging to the console only", log_dir / LOG_FILE, exc)
            return
        handler.setLevel(self.file_level)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
        self._add(handler)

    def _add(self, handler: logging.Handler) -> None:
        self.handlers.append(handler)
        self.root.addHandler(handler)
        # Only as verbose as the most verbose handler: cheap debug calls stay cheap.
        self.root.setLevel(min(h.level for h in self.handlers))

    def close(self) -> None:
        for handler in self.handlers:
            self.root.removeHandler(handler)
            handler.close()
        self.handlers.clear()
        self.root.setLevel(self.previous_level)


# --------------------------------------------------------------------------- output helpers
def _print_report(report: TickReport, currency: str) -> None:
    if report.skipped:
        print(f"  Skipped: {_SKIPPED.get(report.skipped, report.skipped)}")
    width = max((len(s) for s in report.signals), default=0)
    for symbol, text in report.signals.items():
        print(f"  {symbol:<{width}}  {text}")
    for order in report.orders:
        print(f"  -> {_order_text(order)}")
    if not report.orders and not report.skipped:
        print("  No orders this time.")
    if report.halted:
        print("  Daily loss limit reached: no new entries for the rest of the day (exits still run).")
    for error in report.errors:
        print(f"  ERROR: {error}")
    if report.equity is not None:
        print(f"  Equity: {_money(report.equity, currency)}")


def _order_text(order: OrderResult) -> str:
    side = getattr(order.side, "value", str(order.side)).upper()
    status = {"filled": "filled", "accepted": "sent, waiting to fill", "rejected": "REJECTED"}.get(
        order.status, order.status)
    price = f" @ {_price(order.filled_avg_price)}" if order.filled_avg_price else ""
    reason = f" ({order.reason})" if order.reason else ""
    return f"{side} {_qty(order.qty)} {order.symbol}: {status}{price}{reason}"


def _positions_table(positions: dict[str, Position]) -> str:
    rows = [(p.symbol, _qty(p.qty), _price(p.avg_entry_price), _price(p.market_price),
             _pct(p.unrealized_pnl_pct, signed=True), f"{p.unrealized_pnl:+,.2f}", f"{p.market_value:,.2f}")
            for p in positions.values()]
    return _table(("Symbol", "Qty", "Avg entry", "Price", "P&L %", "P&L", "Value"), rows)


def _comparison_table(results: dict[str, BacktestResult]) -> str:
    rows = []
    for name, result in results.items():
        m = result.metrics
        rows.append((name, _pct(m.get("total_return_pct"), signed=True),
                     _pct(m.get("buy_and_hold_return_pct"), signed=True), _pct(m.get("cagr_pct"), signed=True),
                     _pct(m.get("max_drawdown_pct")), _num(m.get("sharpe")), _int(m.get("num_trades")),
                     _pct(m.get("win_rate_pct"))))
    headers = ("Strategy", "Return", "Buy & hold", "CAGR", "Max drawdown", "Sharpe", "Trades", "Win rate")
    return _table(headers, rows)


def _table(headers: Sequence[str], rows: Sequence[Sequence[str]], indent: str = "  ") -> str:
    """First column left-aligned, the rest right-aligned."""
    widths = [max(len(cell) for cell in column) for column in zip(headers, *rows)]

    def line(cells: Sequence[str]) -> str:
        return indent + "  ".join(c.ljust(w) if i == 0 else c.rjust(w)
                                  for i, (c, w) in enumerate(zip(cells, widths))).rstrip()

    return "\n".join([line(headers), indent + "  ".join("-" * w for w in widths), *map(line, rows)])


def _banner(cfg: BotConfig, args: argparse.Namespace) -> str:
    rule = "=" * 66
    risk = _risk_lines(cfg.risk)
    rows = [
        ("Mode", _mode_label(cfg)),
        ("Broker", _broker_label(cfg)),
        ("Symbols", ", ".join(cfg.symbols)),
        ("Timeframe", f"{cfg.timeframe} bars, checking every {cfg.poll_interval_seconds}s"),
        ("Strategy", _strategy_label(cfg)),
        ("Risk", risk[0]), *(("", text) for text in risk[1:]),
        ("Trading day", f"midnight to midnight {cfg.timezone} (for daily limits)"),
        ("State", str(cfg.state_dir)),
        ("Logs", f"{Path(cfg.log_dir) / LOG_FILE} (trades in trades.csv)"),
        ("Kill switch", _kill_text(cfg, args)),
        ("Stop", "Ctrl-C (or SIGTERM)"),
    ]
    lines = [rule, f" Trading bot {__version__}", rule, *(f" {k:<12} {v}" for k, v in rows), rule]
    if cfg.is_live:
        lines = [_LIVE_WARNING, *lines]
    return "\n".join(lines)


def _risk_lines(r: RiskConfig) -> list[str]:
    stop = f"stop-loss {r.stop_loss_pct:g}%" if r.stop_loss_pct else "no stop-loss"
    target = f"take-profit {r.take_profit_pct:g}%" if r.take_profit_pct else "no take-profit"
    if r.max_daily_loss_pct:
        daily = f"daily loss limit {r.max_daily_loss_pct:g}%" + (" (then sell all)" if r.flatten_on_daily_loss else "")
    else:
        daily = "no daily loss limit"
    return [
        f"{r.risk_per_trade_pct:g}% of equity at risk per trade, {stop}, {target}",
        f"max {r.max_position_pct:g}% per position, {r.max_total_exposure_pct:g}% invested, "
        f"{r.max_open_positions} positions",
        f"{daily}, max {r.max_trades_per_day} new trades a day",
    ]


def _kill_text(cfg: BotConfig, args: argparse.Namespace) -> str:
    reason = kill_switch_reason(cfg.state_dir)
    if reason is None:
        return f"OFF (trading allowed; pause with `{_hint(args, 'kill')}`)"
    return f"ON{_reason_suffix(reason)}: no orders will be placed. Allow trading with `{_hint(args, 'resume')}`"


def _read_state(path: Path) -> tuple[BotState | None, str | None]:
    """(state, problem). Read-only: unlike ``StateStore.load`` a corrupt file is left in place."""
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, None
    except (OSError, UnicodeDecodeError) as exc:
        return None, f"Cannot read {path}: {exc}"
    try:
        return BotState.from_dict(json.loads(raw)), None
    except (ValueError, TypeError) as exc:
        return None, f"{path} is unreadable ({exc}); the bot starts a fresh state on its next check."


def _mode_label(cfg: BotConfig) -> str:
    return "LIVE (real money)" if cfg.is_live else "PAPER (simulated money)"


def _broker_label(cfg: BotConfig) -> str:
    b = cfg.broker
    if b.type == "sim":
        return "built-in simulator (made-up prices)"
    if b.type == "alpaca":
        return f"Alpaca {'LIVE' if cfg.is_live else 'paper'} account ({b.data_feed} data)"
    if cfg.is_live:
        return f"{b.exchange} LIVE account"
    if b.use_sandbox:
        return f"{b.exchange} testnet account"
    return f"{b.exchange} public prices + local paper account"


def _strategy_label(cfg: BotConfig) -> str:
    return f"{cfg.strategy.name} ({_params_text(_make_strategy(cfg).params)})"


def _params_text(params: dict[str, Any]) -> str:
    return ", ".join(f"{k}={v}" for k, v in params.items()) or "no parameters"


def _currency(cfg: BotConfig) -> str:
    if cfg.broker.type == "ccxt" and cfg.symbols:
        return cfg.symbols[0].partition("/")[2] or "USD"
    return "USD"


def _hint(args: argparse.Namespace, command: str) -> str:
    config = getattr(args, "config", None)
    return f"python -m bot {command}" + (f" -c {shlex.quote(str(config))}" if config else "")


def _display_path(path: Path) -> str:
    """``path`` relative to the working directory when it is inside it."""
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


def _reason_suffix(reason: str) -> str:
    return f" ({reason})" if reason else ""


def _error(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)


def _ts(when: datetime) -> str:
    return when.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _ago(iso: str | None) -> str:
    if not iso:
        return "never"
    try:
        when = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    seconds = (utcnow() - when).total_seconds()
    if seconds < 0:
        return _ts(when)
    for unit, size in (("day", 86400), ("h", 3600), ("min", 60)):
        if seconds >= size:
            n = int(seconds // size)
            return f"{_ts(when)} ({n} {unit}{'s' if unit == 'day' and n > 1 else ''} ago)"
    return f"{_ts(when)} (just now)"


def _finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _num(value: object, fmt: str = ",.2f") -> str:
    if isinstance(value, float) and math.isinf(value):
        return "inf" if value > 0 else "-inf"
    return format(value, fmt) if _finite(value) else "n/a"


def _pct(value: object, signed: bool = False) -> str:
    return _num(value, "+,.2f" if signed else ",.2f") + ("%" if _finite(value) else "")


def _int(value: object) -> str:
    return f"{int(value):,}" if _finite(value) else "n/a"  # type: ignore[call-overload]


def _money(value: float, currency: str) -> str:
    return f"{_num(value)} {currency}"


def _qty(value: float) -> str:
    return _num(value, ",.8g")


def _price(value: float | None) -> str:
    if not _finite(value):
        return "n/a"
    return f"{value:,.2f}" if abs(value) >= 1 else f"{value:.6g}"  # type: ignore[arg-type]


def _positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected a whole number, got {text!r}") from None
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be at least 1, got {value}")
    return value


def _csv_spec(text: str) -> tuple[str, str]:
    symbol, sep, path = text.partition("=")
    if not sep or not symbol.strip() or not path.strip():
        raise argparse.ArgumentTypeError(f"expected SYMBOL=PATH (e.g. SPY=data/spy.csv), got {text!r}")
    return symbol.strip(), path.strip()


__all__ = ["CLIError", "build_parser", "main"]
