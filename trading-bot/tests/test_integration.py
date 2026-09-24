"""Cross-module tests: the real modules wired together the way the CLI wires them.

Offline: prices come from synthetic bars, a CSV replay feed, or a real
``ccxt.upbit`` object whose network methods are replaced with canned data.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import ccxt
import pandas as pd
import pytest

from bot.backtest import BacktestConfig, run_backtest
from bot.brokers.ccxt_broker import CCXTBroker
from bot.brokers.paper import PaperBroker
from bot.config import BotConfig, NotifyConfig, load_config
from bot.data import CSVFeed, generate_synthetic_bars
from bot.engine import TradingEngine
from bot.models import Action, Position, Signal
from bot.notify import Notifier
from bot.risk import RiskConfig, RiskManager
from bot.state import STATE_FILE, StateStore
from bot.strategies import create_strategy
from bot.strategies.base import Strategy

ROOT = Path(__file__).resolve().parents[1]


class Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def engine_for(cfg: BotConfig, broker, strategy: Strategy, clock: Clock) -> TradingEngine:
    return TradingEngine(cfg, broker, strategy, RiskManager(cfg.risk), StateStore(cfg.state_dir / STATE_FILE),
                         Notifier(NotifyConfig(), mode=cfg.mode), clock=clock)


# --------------------------------------------------------------------------- backtest == live


def test_live_engine_trades_on_the_same_bars_as_the_backtest(tmp_path):
    """What you backtest is what trades: replaying history bar by bar through the
    live engine (paper broker on a CSV replay feed) enters and exits on exactly
    the bars where the backtester's orders fill."""
    bars = generate_synthetic_bars(400, "1d", seed=3)
    risk = RiskConfig(risk_per_trade_pct=1.0, stop_loss_pct=None, max_position_pct=50.0,
                      max_total_exposure_pct=100.0, max_daily_loss_pct=None, max_trades_per_day=10,
                      min_order_notional=1.0, cash_buffer_pct=1.0)
    lookback = 60

    backtest = run_backtest(create_strategy("sma_crossover", {"fast": 5, "slow": 20}), {"SYM": bars},
                            BacktestConfig(lookback=lookback, timeframe="1d", risk=risk))
    trades = backtest.trades
    assert len(trades) >= 5, "the scenario should trade several times"
    expected_entries = [t.entry_time for t in trades]
    expected_exits = [t.exit_time for t in trades if t.exit_reason != "end_of_backtest"]

    clock = Clock(bars.index[0].to_pydatetime())
    broker = PaperBroker(CSVFeed({"SYM": bars}, clock=clock), starting_cash=10_000.0, clock=clock)
    cfg = BotConfig(symbols=["SYM"], timeframe="1d", bars_lookback=lookback, timezone="UTC", risk=risk,
                    state_dir=tmp_path / "state", log_dir=tmp_path / "logs")
    engine = engine_for(cfg, broker, create_strategy("sma_crossover", {"fast": 5, "slow": 20}), clock)
    for bar_open in bars.index[1:]:
        # One second into bar k: bars up to k-1 are closed, like the backtest's close of k-1.
        clock.now = bar_open.to_pydatetime() + timedelta(seconds=1)
        report = engine.run_once()
        assert report.errors == []

    def fill_bars(side: str) -> list[pd.Timestamp]:
        return [pd.Timestamp(f["time"]).floor("1D") for f in broker.fills if f["side"] == side]

    assert fill_bars("buy") == expected_entries
    assert fill_bars("sell") == expected_exits
    rows = (cfg.log_dir / "trades.csv").read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 1 + len(broker.fills)  # header + one row per order


# --------------------------------------------------------------------------- crypto paper mode


class OfflineUpbit(ccxt.upbit):
    """The real ccxt Upbit class (precision, options, ids) with canned market data."""

    def __init__(self, bars: dict[str, pd.DataFrame]) -> None:
        super().__init__({"enableRateLimit": False})
        self.bars = bars
        self.prices = {symbol: float(frame["close"].iloc[-1]) for symbol, frame in bars.items()}
        self.fetch = self._no_network  # the low-level HTTP method

    @staticmethod
    def _no_network(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("test tried to reach the network")

    def fetch_markets(self, params=None):
        markets = []
        for symbol in self.bars:
            base, quote = symbol.split("/")
            markets.append({
                "id": f"{quote}-{base}", "symbol": symbol, "base": base, "quote": quote, "baseId": base,
                "quoteId": quote, "type": "spot", "spot": True, "margin": False, "swap": False,
                "future": False, "option": False, "contract": False, "active": True,
                "precision": {"amount": 1e-8, "price": 1000.0},
                "limits": {"amount": {"min": None, "max": None}, "cost": {"min": None, "max": None}},
            })
        return markets

    def fetch_ohlcv(self, symbol, timeframe="1m", since=None, limit=None, params=None):
        frame = self.bars[symbol].tail(limit or len(self.bars[symbol]))
        times = [int(t.timestamp() * 1000) for t in frame.index]
        return [[t, *row] for t, row in zip(times, frame.to_numpy().tolist(), strict=True)]

    def fetch_ticker(self, symbol, params=None):
        return {"symbol": symbol, "last": self.prices[symbol]}


class BuyWhenFlat(Strategy):
    name = "buy_when_flat"
    defaults: dict = {}

    @property
    def min_bars(self) -> int:
        return 2

    def generate_signal(self, bars: pd.DataFrame, position: Position | None) -> Signal:
        return Signal(Action.BUY, "scripted entry") if position is None else Signal.hold("scripted hold")


def test_crypto_paper_mode_sizes_and_exits_with_the_exchange_rules(tmp_path):
    """configs/crypto.yaml in paper mode: a local PaperBroker on Upbit public
    prices. Sizing, the 5,000 KRW minimum and quantity precision come from the
    exchange adapter; a stop-loss sells the whole position, leaving no dust."""
    cfg = load_config(ROOT / "configs" / "crypto.yaml", env={})
    cfg = replace(cfg, state_dir=tmp_path / "state", log_dir=tmp_path / "logs", symbols=["BTC/KRW"])
    end = datetime(2026, 1, 1, tzinfo=timezone.utc)
    bars = {"BTC/KRW": generate_synthetic_bars(160, "4h", seed=5, start_price=90_000_000.0, end=end)}
    exchange = OfflineUpbit(bars)
    feed = CCXTBroker("upbit", ["BTC/KRW"], exchange=exchange)
    clock = Clock(end + timedelta(minutes=1))
    broker = PaperBroker(feed, starting_cash=cfg.broker.starting_cash, fee_pct=cfg.broker.fee_pct,
                         slippage_pct=cfg.broker.slippage_pct, state_path=cfg.state_dir / "paper_account.json",
                         currency="KRW", clock=clock)
    assert broker.min_order_notional("BTC/KRW") == 5_000.0  # Upbit's KRW minimum, via the adapter
    engine = engine_for(cfg, broker, BuyWhenFlat(), clock)

    first = engine.run_once()
    assert first.errors == []
    (buy,) = first.orders
    assert buy.status == "filled" and buy.side.value == "buy"
    assert buy.filled_qty == round(buy.filled_qty, 8)  # Upbit amount precision (1e-8 BTC)
    price = exchange.prices["BTC/KRW"]
    # 2% risk / 10% stop = 20% of the 1,000,000 KRW account.
    assert 200_000.0 - price * 1e-8 < buy.filled_qty * price <= 200_000.0  # rounded DOWN by < one step
    assert broker.cash == pytest.approx(1_000_000 - buy.filled_qty * buy.filled_avg_price * 1.0005)

    exchange.prices["BTC/KRW"] = price * 0.85  # through the 10% stop
    second = engine.run_once()
    assert second.errors == []
    (sell,) = second.orders
    assert sell.side.value == "sell" and sell.filled_qty == buy.filled_qty
    assert "stop_loss" in second.signals["BTC/KRW"]
    assert broker.get_positions() == {}
    assert broker.get_account().equity == pytest.approx(broker.cash)
    assert 1_000_000 * 0.96 < broker.cash < 1_000_000 * 0.975  # a 15% drop on 20% of the account, plus costs

    # The stop-out is this bar's decision: no immediate re-entry on the same closed bar.
    third = engine.run_once()
    assert third.orders == [] and "already evaluated" in third.signals["BTC/KRW"]
