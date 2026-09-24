"""Tests for bot.brokers.paper.PaperBroker: simulated fills, cash safety, persistence."""
from __future__ import annotations

import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from bot.brokers import paper as paper_mod
from bot.brokers.base import Broker, BrokerError
from bot.brokers.paper import MAX_FILLS, PaperBroker
from bot.data import SyntheticFeed, generate_synthetic_bars
from bot.models import OrderRequest, Side
from bot.utils import floor_to_step

T0 = datetime(2026, 9, 24, 14, 30, tzinfo=timezone.utc)


class FakeFeed:
    """Minimal DataFeed with prices the test controls."""

    def __init__(self, prices: dict[str, float] | None = None) -> None:
        self.prices = dict(prices or {"AAPL": 100.0, "MSFT": 50.0})
        self.bars_calls: list[tuple[str, str, int]] = []

    def get_bars(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        self.bars_calls.append((symbol, timeframe, limit))
        return generate_synthetic_bars(limit, timeframe)

    def get_latest_price(self, symbol: str) -> float:
        return self.prices[symbol]


class ExchangeLikeFeed(FakeFeed):
    """Feed with venue rules, like a CCXTBroker used as a feed."""

    def __init__(self, prices: dict[str, float], step: float = 0.001, min_cost: float = 5_000.0,
                 market_open: bool = True) -> None:
        super().__init__(prices)
        self.step, self.min_cost, self.market_open = step, min_cost, market_open

    def normalize_qty(self, symbol: str, qty: float) -> float:
        return floor_to_step(qty, self.step)

    def min_order_notional(self, symbol: str) -> float:
        return self.min_cost

    def is_market_open(self) -> bool:
        return self.market_open


def make_broker(prices: dict[str, float] | None = None, **kwargs) -> tuple[PaperBroker, FakeFeed]:
    feed = FakeFeed(prices)
    kwargs.setdefault("clock", lambda: T0)
    return PaperBroker(feed, **kwargs), feed


def buy(symbol: str, qty: float, reason: str = "") -> OrderRequest:
    return OrderRequest(symbol=symbol, side=Side.BUY, qty=qty, reason=reason)


def sell(symbol: str, qty: float, reason: str = "") -> OrderRequest:
    return OrderRequest(symbol=symbol, side=Side.SELL, qty=qty, reason=reason)


def assert_equity_identity(broker: PaperBroker, feed: FakeFeed) -> None:
    account = broker.get_account()
    positions = broker.get_positions()
    expected = broker.cash + sum(p.qty * feed.prices[s] for s, p in positions.items())
    assert account.equity == pytest.approx(expected, rel=1e-12, abs=1e-9)
    assert account.cash == broker.cash >= 0
    assert account.buying_power == account.cash


# =========================================================================== construction


def test_is_a_broker_named_paper_with_a_fresh_account():
    broker, _ = make_broker(starting_cash=5_000, currency="KRW")
    assert isinstance(broker, Broker)
    assert broker.name == "paper"
    account = broker.get_account()
    assert (account.equity, account.cash, account.buying_power) == (5_000, 5_000, 5_000)
    assert account.currency == "KRW"
    assert account.day_start_equity is None and account.trading_blocked is False
    assert broker.get_positions() == {} and broker.fills == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"starting_cash": 0},
        {"starting_cash": -1},
        {"starting_cash": float("nan")},
        {"fee_pct": -0.1},
        {"fee_pct": 100},
        {"slippage_pct": -1},
        {"slippage_pct": float("inf")},
        {"min_notional": -1},
    ],
)
def test_rejects_nonsense_settings(kwargs):
    with pytest.raises(ValueError):
        PaperBroker(FakeFeed(), **kwargs)


# =========================================================================== buys


def test_buy_fills_at_price_plus_slippage_and_pays_fee_from_cash():
    broker, _ = make_broker(starting_cash=10_000, fee_pct=0.1, slippage_pct=0.05)
    result = broker.submit_order(buy("AAPL", 10, reason="sma cross"))
    fill_price = 100.0 * 1.0005
    fee = 10 * fill_price * 0.001
    assert result.status == "filled" and result.ok
    assert result.id == "paper-1"
    assert result.side is Side.BUY and result.symbol == "AAPL"
    assert result.filled_qty == 10 and result.qty == 10
    assert result.filled_avg_price == pytest.approx(fill_price)
    assert result.reason == "sma cross"
    assert broker.cash == pytest.approx(10_000 - 10 * fill_price - fee)
    pos = broker.get_positions()["AAPL"]
    assert pos.qty == 10 and pos.avg_entry_price == pytest.approx(fill_price) and pos.market_price == 100.0
    assert result.raw["fee"] == pytest.approx(fee)
    assert result.raw["time"] == T0.isoformat()


def test_order_ids_increment_including_rejections():
    broker, _ = make_broker()
    ids = [broker.submit_order(buy("AAPL", 1)).id,
           broker.submit_order(sell("MSFT", 1)).id,  # rejected: no position
           broker.submit_order(sell("AAPL", 1)).id]
    assert ids == ["paper-1", "paper-2", "paper-3"]


def test_buy_costing_more_than_cash_is_rejected_and_nothing_changes():
    broker, _ = make_broker(starting_cash=1_000)
    result = broker.submit_order(buy("AAPL", 11))
    assert result.status == "rejected" and not result.ok
    assert "insufficient cash" in result.reason
    assert result.filled_qty == 0 and result.filled_avg_price is None
    assert broker.cash == 1_000 and broker.get_positions() == {} and broker.fills == []


def test_buy_that_only_the_fee_makes_unaffordable_is_rejected():
    broker, _ = make_broker(starting_cash=1_000, fee_pct=1.0, slippage_pct=0.0)
    assert broker.submit_order(buy("AAPL", 9.95)).status == "rejected"  # 995 + 9.95 fee > 1000
    assert broker.submit_order(buy("AAPL", 9.9)).status == "filled"     # 990 + 9.90 fee <= 1000
    assert broker.cash == pytest.approx(0.1)


def test_buy_spending_exactly_all_cash_leaves_zero_not_negative():
    broker, _ = make_broker({"X": 2.0}, starting_cash=100, fee_pct=0.0, slippage_pct=0.0)
    assert broker.submit_order(buy("X", 50)).status == "filled"
    assert broker.cash == 0.0
    assert broker.submit_order(buy("X", 0.5)).status == "rejected"
    assert broker.cash == 0.0


def test_buy_below_min_notional_is_rejected():
    broker, _ = make_broker({"X": 1.0}, min_notional=10.0, slippage_pct=0.0)
    result = broker.submit_order(buy("X", 9))
    assert result.status == "rejected" and "below minimum" in result.reason
    assert broker.min_order_notional("X") == 10.0


@pytest.mark.parametrize("qty", [0, -1, float("nan"), float("inf")])
def test_non_positive_or_non_finite_quantity_is_rejected(qty):
    broker, _ = make_broker()
    for order in (buy("AAPL", qty), sell("AAPL", qty)):
        result = broker.submit_order(order)
        assert result.status == "rejected"
    assert broker.cash == 10_000


def test_buy_quantity_is_rounded_down_to_the_default_step():
    broker, _ = make_broker()
    result = broker.submit_order(buy("AAPL", 1.23456789))
    assert result.filled_qty == pytest.approx(1.234567)
    assert result.filled_qty <= 1.23456789
    assert broker.normalize_qty("AAPL", 1.23456789) == pytest.approx(1.234567)
    assert broker.submit_order(buy("AAPL", 4e-7)).status == "rejected"  # rounds to 0


def test_adding_to_a_position_uses_weighted_average_entry():
    broker, feed = make_broker(slippage_pct=0.0, fee_pct=0.0)
    broker.submit_order(buy("AAPL", 10))           # 10 @ 100
    feed.prices["AAPL"] = 130.0
    broker.submit_order(buy("AAPL", 5))            # 5 @ 130
    pos = broker.get_positions()["AAPL"]
    assert pos.qty == 15
    assert pos.avg_entry_price == pytest.approx((10 * 100 + 5 * 130) / 15)
    assert pos.market_price == 130.0


def test_average_entry_includes_slippage_but_not_fees():
    broker, _ = make_broker(slippage_pct=1.0, fee_pct=0.5)
    broker.submit_order(buy("AAPL", 2))
    assert broker.get_positions()["AAPL"].avg_entry_price == pytest.approx(101.0)


def test_side_given_as_plain_string_works():
    broker, _ = make_broker()
    result = broker.submit_order(OrderRequest(symbol="AAPL", side="buy", qty=1))  # type: ignore[arg-type]
    assert result.status == "filled" and result.side is Side.BUY


# =========================================================================== sells


def test_sell_fills_at_price_minus_slippage_and_credits_proceeds_minus_fee():
    broker, feed = make_broker(fee_pct=0.1, slippage_pct=0.05)
    broker.submit_order(buy("AAPL", 10))
    cash_before = broker.cash
    feed.prices["AAPL"] = 110.0
    result = broker.submit_order(sell("AAPL", 10, reason="take profit"))
    fill_price = 110.0 * 0.9995
    fee = 10 * fill_price * 0.001
    assert result.status == "filled" and result.filled_qty == 10
    assert result.filled_avg_price == pytest.approx(fill_price)
    assert broker.cash == pytest.approx(cash_before + 10 * fill_price - fee)
    assert broker.get_positions() == {}
    entry = 100.0 * 1.0005
    assert result.raw["realized_pnl"] == pytest.approx((fill_price - entry) * 10 - fee)


def test_sell_without_position_is_rejected_never_short():
    broker, _ = make_broker()
    result = broker.submit_order(sell("AAPL", 1))
    assert result.status == "rejected" and "no AAPL position" in result.reason
    assert broker.get_positions() == {} and broker.cash == 10_000


def test_sell_more_than_held_sells_only_what_is_held():
    broker, _ = make_broker()
    broker.submit_order(buy("AAPL", 3))
    result = broker.submit_order(sell("AAPL", 10))
    assert result.status == "filled"
    assert result.qty == 10 and result.filled_qty == 3
    assert "filled 3 of 10" in result.reason
    assert broker.get_positions() == {}
    assert broker.submit_order(sell("AAPL", 1)).status == "rejected"


def test_partial_sell_keeps_average_entry():
    broker, feed = make_broker(slippage_pct=0.0, fee_pct=0.0)
    broker.submit_order(buy("AAPL", 10))
    feed.prices["AAPL"] = 90.0
    broker.submit_order(sell("AAPL", 4))
    pos = broker.get_positions()["AAPL"]
    assert pos.qty == pytest.approx(6) and pos.avg_entry_price == 100.0


def test_partial_sell_below_min_notional_is_rejected_but_full_close_is_allowed():
    broker, feed = make_broker({"X": 10.0}, min_notional=5.0, slippage_pct=0.0, fee_pct=0.0)
    broker.submit_order(buy("X", 1))
    feed.prices["X"] = 2.0                     # position now worth 2 < minimum
    assert broker.submit_order(sell("X", 0.5)).status == "rejected"
    assert broker.submit_order(sell("X", 1)).status == "filled"
    assert broker.get_positions() == {}


def write_account(path: Path, qty: float, cash: float = 1_000.0) -> None:
    path.write_text(json.dumps({"cash": cash, "currency": "USD",
                                "positions": {"X": {"qty": qty, "avg_entry_price": 10.0}}}))


def test_sell_leaving_float_dust_closes_the_whole_position(tmp_path):
    path = tmp_path / "paper_account.json"
    write_account(path, qty=1.0000000000001)
    broker = PaperBroker(FakeFeed({"X": 10.0}), state_path=path)
    result = broker.submit_order(sell("X", 1.0))
    assert result.status == "filled" and result.filled_qty == 1.0000000000001
    assert broker.get_positions() == {}


def test_sell_leaving_less_than_the_venue_step_closes_the_whole_position(tmp_path):
    path = tmp_path / "paper_account.json"
    write_account(path, qty=1.0004)  # e.g. bought outside the bot
    broker = PaperBroker(ExchangeLikeFeed({"X": 10.0}, step=0.001, min_cost=1.0), state_path=path)
    result = broker.submit_order(sell("X", 1.0))
    assert result.filled_qty == 1.0004
    assert broker.get_positions() == {}


def test_partial_sell_leaving_a_sellable_remainder_stays_partial(tmp_path):
    path = tmp_path / "paper_account.json"
    write_account(path, qty=1.002)
    broker = PaperBroker(ExchangeLikeFeed({"X": 10.0}, step=0.001, min_cost=1.0), state_path=path)
    assert broker.submit_order(sell("X", 1.0)).filled_qty == 1.0
    assert broker.get_positions()["X"].qty == pytest.approx(0.002)


def test_sell_quantity_is_rounded_down():
    broker, _ = make_broker(slippage_pct=0.0, fee_pct=0.0)
    broker.submit_order(buy("AAPL", 5))
    result = broker.submit_order(sell("AAPL", 1.9999999))
    assert result.filled_qty == pytest.approx(1.999999)
    assert broker.get_positions()["AAPL"].qty == pytest.approx(3.000001)


# =========================================================================== account invariants


def test_equity_is_cash_plus_positions_marked_to_latest_price():
    broker, feed = make_broker()
    broker.submit_order(buy("AAPL", 20))
    broker.submit_order(buy("MSFT", 40))
    feed.prices.update(AAPL=120.0, MSFT=45.0)
    account = broker.get_account()
    assert account.equity == pytest.approx(broker.cash + 20 * 120.0 + 40 * 45.0)
    positions = broker.get_positions()
    assert positions["AAPL"].market_price == 120.0
    assert positions["MSFT"].unrealized_pnl < 0
    assert_equity_identity(broker, feed)


def test_random_order_flow_never_makes_cash_or_quantity_negative():
    rng = random.Random(1234)
    broker, feed = make_broker({"A": 10.0, "B": 250.0, "C": 0.5}, starting_cash=2_000, fee_pct=0.25,
                               slippage_pct=0.2, min_notional=1.0)
    for _ in range(400):
        symbol = rng.choice(["A", "B", "C"])
        feed.prices[symbol] *= math.exp(rng.gauss(0, 0.05))
        qty = rng.choice([rng.uniform(0, 5), rng.uniform(0, 500), rng.uniform(0, 1e-5)])
        order = buy(symbol, qty) if rng.random() < 0.55 else sell(symbol, qty)
        result = broker.submit_order(order)
        assert result.status in ("filled", "rejected")
        assert result.filled_qty <= order.qty
        assert broker.cash >= 0
        assert all(p.qty > 0 for p in broker.get_positions().values())
        assert_equity_identity(broker, feed)


def test_close_all_positions_sells_everything():
    broker, _ = make_broker()
    broker.submit_order(buy("AAPL", 5))
    broker.submit_order(buy("MSFT", 7))
    results = broker.close_all_positions()
    assert sorted(r.symbol for r in results) == ["AAPL", "MSFT"]
    assert all(r.status == "filled" and r.side is Side.SELL for r in results)
    assert broker.get_positions() == {}
    assert broker.get_account().equity == broker.cash


def test_orders_never_stay_open():
    broker, _ = make_broker()
    broker.submit_order(buy("AAPL", 1))
    broker.cancel_all_orders()
    assert broker.has_open_orders("AAPL") is False


def test_fill_history_is_capped():
    broker, _ = make_broker({"X": 1.0}, starting_cash=1e9, fee_pct=0.0, slippage_pct=0.0)
    for _ in range(MAX_FILLS + 20):
        broker.submit_order(buy("X", 2))
    fills = broker.fills
    assert len(fills) == MAX_FILLS
    assert fills[-1]["id"] == f"paper-{MAX_FILLS + 20}"
    fills[0]["qty"] = -1  # copies: the broker's history is untouched
    assert broker.fills[0]["qty"] == 2


def test_reset_restores_starting_cash_and_keeps_ids_unique():
    broker, _ = make_broker(starting_cash=3_000)
    broker.submit_order(buy("AAPL", 5))
    broker.reset()
    assert broker.cash == 3_000 and broker.get_positions() == {} and broker.fills == []
    assert broker.submit_order(buy("AAPL", 1)).id == "paper-2"


# =========================================================================== feed delegation


def test_market_data_is_delegated_to_the_feed():
    broker, feed = make_broker()
    bars = broker.get_bars("AAPL", "1h", 12)
    assert feed.bars_calls == [("AAPL", "1h", 12)] and len(bars) == 12
    assert broker.get_latest_price("MSFT") == 50.0


def test_venue_rules_come_from_the_feed_when_it_has_them():
    feed = ExchangeLikeFeed({"BTC/KRW": 100_000_000.0}, step=0.0001, min_cost=5_000.0)
    broker = PaperBroker(feed, starting_cash=1_000_000, currency="KRW", min_notional=1.0,
                         slippage_pct=0.0, fee_pct=0.05)
    assert broker.normalize_qty("BTC/KRW", 0.00123456) == pytest.approx(0.0012)
    assert broker.min_order_notional("BTC/KRW") == 5_000.0
    result = broker.submit_order(buy("BTC/KRW", 0.00123456))
    assert result.filled_qty == pytest.approx(0.0012)
    rejected = broker.submit_order(buy("BTC/KRW", 0.00004))  # below the 0.0001 step
    assert rejected.status == "rejected" and "rounds down to 0" in rejected.reason


def test_min_notional_from_feed_rejects_small_buys():
    feed = ExchangeLikeFeed({"BTC/KRW": 100_000_000.0}, step=0.00001, min_cost=5_000.0)
    broker = PaperBroker(feed, starting_cash=1_000_000, currency="KRW", slippage_pct=0.0, fee_pct=0.0)
    result = broker.submit_order(buy("BTC/KRW", 0.00004))  # 4,000 KRW < 5,000
    assert result.status == "rejected" and "below minimum 5000.00 KRW" in result.reason
    assert broker.submit_order(buy("BTC/KRW", 0.00005)).status == "filled"


def test_market_clock_comes_from_the_feed_when_it_has_one():
    assert make_broker()[0].is_market_open() is True
    closed = PaperBroker(ExchangeLikeFeed({"X": 1.0}, market_open=False))
    assert closed.is_market_open() is False


class BrokenFeed(FakeFeed):
    def get_latest_price(self, symbol: str) -> float:
        raise ConnectionError("exchange unreachable")

    def get_bars(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        raise TimeoutError("slow")


def test_feed_failures_become_broker_errors_and_no_order_executes():
    broker = PaperBroker(BrokenFeed())
    with pytest.raises(BrokerError, match="exchange unreachable"):
        broker.submit_order(buy("AAPL", 1))
    with pytest.raises(BrokerError, match="slow"):
        broker.get_bars("AAPL", "1d", 5)
    assert broker.cash == 10_000 and broker.fills == []


def test_feed_broker_errors_pass_through_unchanged():
    class Feed(FakeFeed):
        def get_latest_price(self, symbol: str) -> float:
            raise BrokerError("original")

    with pytest.raises(BrokerError, match="^original$"):
        PaperBroker(Feed()).get_latest_price("AAPL")


@pytest.mark.parametrize("bad_price", [0.0, -5.0, float("nan"), float("inf"), None, "abc"])
def test_invalid_feed_price_raises_instead_of_filling(bad_price):
    broker, feed = make_broker()
    feed.prices["AAPL"] = bad_price  # type: ignore[assignment]
    with pytest.raises(BrokerError, match="invalid price"):
        broker.submit_order(buy("AAPL", 1))
    assert broker.cash == 10_000 and broker.get_positions() == {}


def test_positions_are_never_marked_to_an_invalid_price():
    broker, feed = make_broker()
    broker.submit_order(buy("AAPL", 1))
    feed.prices["AAPL"] = float("nan")
    account = broker.get_account()
    assert account.unpriced == ("AAPL",)  # flagged, valued at the last good price instead
    assert math.isfinite(account.equity)
    assert broker.get_positions()["AAPL"].market_price == 100.0
    with pytest.raises(BrokerError):
        broker.get_latest_price("AAPL")


def test_invalid_venue_rules_from_the_feed_raise():
    class Feed(FakeFeed):
        def normalize_qty(self, symbol: str, qty: float) -> float:
            return float("nan")

    broker = PaperBroker(Feed())
    with pytest.raises(BrokerError):
        broker.submit_order(buy("AAPL", 1))
    assert broker.get_positions() == {}


def test_feed_rounding_up_is_never_trusted():
    class Feed(FakeFeed):
        def normalize_qty(self, symbol: str, qty: float) -> float:
            return qty * 2  # a buggy venue rule must not make us buy more

    broker = PaperBroker(Feed(), slippage_pct=0.0, fee_pct=0.0)
    assert broker.submit_order(buy("AAPL", 3)).filled_qty == 3


def test_works_on_top_of_the_synthetic_feed():
    feed = SyntheticFeed(clock=lambda: T0)
    broker = PaperBroker(feed, clock=lambda: T0)
    price = feed.get_latest_price("SPY")
    result = broker.submit_order(buy("SPY", 10))
    assert result.filled_avg_price == pytest.approx(price * 1.0005)
    assert broker.get_account().equity == pytest.approx(broker.cash + 10 * price)
    assert broker.get_bars("SPY", "1d", 5).iloc[-1]["close"] == price


# =========================================================================== persistence


def test_state_round_trips_through_the_file(tmp_path):
    path = tmp_path / "nested" / "paper_account.json"
    broker, feed = make_broker(state_path=path)
    broker.submit_order(buy("AAPL", 10, reason="entry"))
    broker.submit_order(buy("MSFT", 4))
    broker.submit_order(sell("AAPL", 3))
    assert path.exists()
    assert [p.name for p in path.parent.iterdir()] == ["paper_account.json"]  # no temp files left

    restored = PaperBroker(feed, state_path=path, clock=lambda: T0)
    assert restored.cash == broker.cash
    assert restored.get_positions() == broker.get_positions()
    assert restored.fills == broker.fills
    assert restored.submit_order(buy("AAPL", 1)).id == "paper-4"


def test_state_file_is_plain_json_with_the_account(tmp_path):
    path = tmp_path / "paper_account.json"
    broker, _ = make_broker(state_path=path, currency="USD")
    broker.submit_order(buy("AAPL", 2))
    data = json.loads(path.read_text())
    assert data["currency"] == "USD" and data["starting_cash"] == 10_000
    assert data["cash"] == broker.cash
    assert data["positions"]["AAPL"]["qty"] == 2
    assert data["fills"][0]["symbol"] == "AAPL" and data["next_order_id"] == 2


def test_no_file_is_written_until_a_fill(tmp_path):
    path = tmp_path / "paper_account.json"
    broker, _ = make_broker(state_path=path)
    broker.submit_order(sell("AAPL", 1))  # rejected
    assert not path.exists()


def test_persisted_fill_history_is_capped(tmp_path, monkeypatch):
    monkeypatch.setattr(paper_mod, "MAX_FILLS", 5)
    path = tmp_path / "paper_account.json"
    broker, feed = make_broker(state_path=path)
    for _ in range(8):
        broker.submit_order(buy("AAPL", 1))
    assert len(json.loads(path.read_text())["fills"]) == 5
    assert [f["id"] for f in PaperBroker(feed, state_path=path).fills] == [f"paper-{i}" for i in range(4, 9)]


def test_reset_is_persisted(tmp_path):
    path = tmp_path / "paper_account.json"
    broker, feed = make_broker(state_path=path, starting_cash=2_000)
    broker.submit_order(buy("AAPL", 5))
    broker.reset()
    restored = PaperBroker(feed, state_path=path, starting_cash=2_000)
    assert restored.cash == 2_000 and restored.get_positions() == {}


def test_saved_balance_wins_over_a_changed_starting_cash(tmp_path):
    path = tmp_path / "paper_account.json"
    broker, feed = make_broker(state_path=path, starting_cash=1_000)
    broker.submit_order(buy("AAPL", 1))
    restored = PaperBroker(feed, state_path=path, starting_cash=50_000)
    assert restored.cash == broker.cash
    restored.reset()
    assert restored.cash == 50_000


def test_failed_save_means_the_order_did_not_happen(tmp_path, monkeypatch):
    path = tmp_path / "paper_account.json"
    broker, _ = make_broker(state_path=path)
    broker.submit_order(buy("AAPL", 1))

    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(paper_mod, "_atomic_write_json", boom)
    with pytest.raises(BrokerError, match="NOT executed"):
        broker.submit_order(buy("AAPL", 2))
    assert broker.get_positions()["AAPL"].qty == 1
    assert len(broker.fills) == 1


def test_atomic_write_leaves_old_file_intact_when_writing_fails(tmp_path, monkeypatch):
    path = tmp_path / "paper_account.json"
    broker, _ = make_broker(state_path=path)
    broker.submit_order(buy("AAPL", 1))
    before = path.read_text()

    def fail_replace(src, dst):
        raise OSError("replace failed")

    monkeypatch.setattr(paper_mod.os, "replace", fail_replace)
    with pytest.raises(BrokerError):
        broker.submit_order(buy("AAPL", 1))
    assert path.read_text() == before
    assert [p.name for p in tmp_path.iterdir()] == ["paper_account.json"]


@pytest.mark.parametrize(
    "content",
    [
        "{not json",
        "[]",
        json.dumps({"positions": {}}),
        json.dumps({"cash": -5, "positions": {}}),
        json.dumps({"cash": "lots"}),
        json.dumps({"cash": 100, "positions": {"AAPL": {"qty": -1, "avg_entry_price": 10}}}),
        json.dumps({"cash": 100, "positions": {"AAPL": {"qty": 1}}}),
        json.dumps({"cash": 100, "positions": ["AAPL"]}),
        json.dumps({"cash": 100, "fills": "nope"}),
        json.dumps({"cash": 100, "next_order_id": 0}),
    ],
)
def test_corrupt_state_file_raises_instead_of_silently_resetting(tmp_path, content):
    path = tmp_path / "paper_account.json"
    path.write_text(content)
    with pytest.raises(BrokerError, match="corrupt"):
        PaperBroker(FakeFeed(), state_path=path)
    assert path.read_text() == content  # left for the user to inspect


def test_state_file_in_another_currency_is_refused(tmp_path):
    path = tmp_path / "paper_account.json"
    broker, feed = make_broker(state_path=path, currency="USD")
    broker.submit_order(buy("AAPL", 1))
    with pytest.raises(BrokerError, match="USD, not KRW"):
        PaperBroker(feed, state_path=path, currency="KRW")


def test_minimal_state_file_loads_with_defaults(tmp_path):
    path = tmp_path / "paper_account.json"
    path.write_text(json.dumps({"cash": 1234.5, "unknown_future_key": 1}))
    broker = PaperBroker(FakeFeed(), state_path=path)
    assert broker.cash == 1234.5 and broker.get_positions() == {}
    assert broker.submit_order(buy("AAPL", 1)).id == "paper-1"


# ---- regression: one unpriceable holding ---------------------------------------


def test_one_holding_that_cannot_be_priced_does_not_fail_the_account_read():
    broker, feed = make_broker({"AAPL": 100.0, "MSFT": 50.0}, fee_pct=0.0, slippage_pct=0.0)
    broker.submit_order(OrderRequest("AAPL", Side.BUY, 10))
    broker.submit_order(OrderRequest("MSFT", Side.BUY, 10))
    feed.prices["AAPL"] = 110.0
    broker.get_account()  # a good read: 110 is the last known AAPL price

    real = feed.get_latest_price

    def price(symbol: str) -> float:
        if symbol == "AAPL":
            raise RuntimeError("AAPL feed down")
        return real(symbol)

    feed.get_latest_price = price
    account = broker.get_account()
    positions = broker.get_positions()

    assert account.unpriced == ("AAPL",)
    assert account.equity == pytest.approx(broker.cash + 10 * 110.0 + 10 * 50.0)
    assert positions["AAPL"].market_price == 110.0 and positions["MSFT"].market_price == 50.0
    with pytest.raises(BrokerError, match="AAPL feed down"):
        broker.get_latest_price("AAPL")  # the symbol itself still reports its error


def test_unpriceable_holding_never_priced_before_is_valued_at_its_entry_price():
    broker, feed = make_broker({"AAPL": 100.0}, fee_pct=0.0, slippage_pct=0.0)
    broker.submit_order(OrderRequest("AAPL", Side.BUY, 10))
    fresh = PaperBroker(feed, state_path=None, clock=lambda: T0)
    fresh._holdings = dict(broker._holdings)
    feed.get_latest_price = lambda symbol: (_ for _ in ()).throw(RuntimeError("down"))
    account = fresh.get_account()
    assert account.unpriced == ("AAPL",)
    assert fresh.get_positions()["AAPL"].market_price == pytest.approx(100.0)
