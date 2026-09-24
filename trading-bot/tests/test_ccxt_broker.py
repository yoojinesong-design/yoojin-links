"""Offline tests for the ccxt crypto broker.

The fake exchange subclasses ``ccxt.Exchange`` so market lookup, precision
(``amount_to_precision`` / ``cost_to_precision``) and the error classes are
the real ccxt code; only the network methods are replaced with canned data,
and the low-level HTTP method raises so nothing can reach the internet.
"""
from __future__ import annotations

import copy
import json
import logging
import math
from pathlib import Path
from typing import Any

import ccxt
import pandas as pd
import pytest
from ccxt.base.decimal_to_precision import TICK_SIZE

from bot.brokers.base import BrokerError
from bot.brokers.ccxt_broker import CCXTBroker, map_order_status, ohlcv_to_bars
from bot.models import BAR_COLUMNS, OrderRequest, Side

HOUR_MS = 3_600_000
T0 = 1_704_067_200_000  # 2024-01-01T00:00:00Z


def _no_network(*args: Any, **kwargs: Any) -> Any:
    raise AssertionError("test tried to make a real HTTP request")


def spot_market(symbol: str, *, amount_step: float = 1e-8, price_step: float = 0.01,
                amount_min: float | None = None, amount_max: float | None = None,
                cost_min: float | None = None, cost_max: float | None = None,
                **extra: Any) -> dict[str, Any]:
    base, quote = symbol.split("/")
    market = {
        "id": base + quote, "symbol": symbol, "base": base, "quote": quote,
        "baseId": base, "quoteId": quote, "type": "spot", "spot": True, "margin": False,
        "swap": False, "future": False, "option": False, "contract": False, "active": True,
        "precision": {"amount": amount_step, "price": price_step},
        "limits": {"amount": {"min": amount_min, "max": amount_max},
                   "cost": {"min": cost_min, "max": cost_max}},
    }
    market.update(extra)
    return market


def default_markets() -> list[dict[str, Any]]:
    return [
        spot_market("BTC/USDT", amount_step=1e-8, amount_min=1e-5, cost_min=5.0),
        spot_market("ETH/USDT", amount_step=1e-4, amount_min=1e-4, cost_min=5.0),
    ]


def hourly_rows(n: int, start_ms: int = T0, price: float = 100.0) -> list[list[float]]:
    return [[start_ms + i * HOUR_MS, price + i, price + i + 2, price + i - 1, price + i + 1, 10.0 + i]
            for i in range(n)]


class FakeExchange(ccxt.Exchange):
    """ccxt exchange whose network methods return canned data and record calls."""

    def __init__(self, markets: list[dict[str, Any]] | None = None, *, exchange_id: str = "fakex",
                 buy_by_cost: bool = False, has_cost_method: bool = True,
                 page_limit: int | None = None, sandbox_url: bool = True) -> None:
        super().__init__({"enableRateLimit": False})
        self.id = exchange_id
        self.precisionMode = TICK_SIZE
        self.has = dict(self.has, fetchCurrencies=False, fetchOHLCV=True, fetchOrder=True,
                        fetchOpenOrders=True, createMarketBuyOrderWithCost=has_cost_method)
        if buy_by_cost:
            self.options["createMarketBuyOrderRequiresPrice"] = True
        self.timeframes = {tf: tf for tf in ("1m", "5m", "15m", "30m", "1h", "4h", "1d")}
        self.urls = dict(self.urls, api={"public": "https://api.fake"},
                         test={"public": "https://testnet.fake"} if sandbox_url else None)
        self.features = {"spot": {"fetchOHLCV": {"limit": page_limit}}} if page_limit else None
        self.page_limit = page_limit
        self.market_list = markets if markets is not None else default_markets()
        self.load_calls = 0
        self.load_error: Exception | None = None
        self.candles: dict[str, list[list[float]]] = {"BTC/USDT": hourly_rows(10)}
        self.tickers: dict[str, Any] = {"BTC/USDT": {"last": 20_000.0}, "ETH/USDT": {"last": 1_500.0}}
        self.balance: dict[str, Any] = {"free": {"USDT": 10_000.0}, "used": {"USDT": 0.0},
                                        "total": {"USDT": 10_000.0}}
        self.calls: list[tuple[Any, ...]] = []
        self.order_response: dict[str, Any] | None = None   # None -> filled at the ticker price
        self.order_error: Exception | None = None
        self.fetched_order: Any = None
        self.fetch_order_error: Exception | None = None
        self.open_orders: dict[str, list[dict[str, Any]]] = {}
        self.cancel_errors: dict[str, Exception] = {}
        self.fetch = _no_network  # the low-level HTTP method

    # -- helpers ---------------------------------------------------------------
    def set_balance(self, code: str, total: float, free: float | None = None) -> None:
        free = total if free is None else free
        self.balance["total"][code] = total
        self.balance["free"][code] = free
        self.balance["used"][code] = total - free

    def names(self) -> list[str]:
        return [call[0] for call in self.calls]

    def _fill(self, symbol: str, side: str, amount: float | None, cost: float | None) -> dict[str, Any]:
        if self.order_error is not None:
            raise self.order_error
        if self.order_response is not None:
            return copy.deepcopy(self.order_response)
        price = self.tickers[symbol]["last"]
        filled = amount if amount is not None else cost / price
        return {"id": f"ord-{len(self.calls)}", "symbol": symbol, "side": side, "status": "closed",
                "amount": filled, "filled": filled, "average": price, "cost": filled * price}

    # -- ccxt API --------------------------------------------------------------
    def load_markets(self, reload=False, params=None):
        self.load_calls += 1
        if self.load_error is not None:
            raise self.load_error
        return super().load_markets(reload, params or {})

    def fetch_markets(self, params=None):
        return copy.deepcopy(self.market_list)

    def fetch_ohlcv(self, symbol, timeframe="1m", since=None, limit=None, params=None):
        self.calls.append(("fetch_ohlcv", symbol, timeframe, since, limit))
        if self.page_limit is not None and limit is not None and limit > self.page_limit:
            raise ccxt.BadRequest(f"count must be <= {self.page_limit}")
        rows = self.candles.get(symbol, [])
        if isinstance(rows, Exception):
            raise rows
        if since is not None:
            rows = [row for row in rows if row[0] >= since]
            return copy.deepcopy(rows[:limit] if limit else rows)
        return copy.deepcopy(rows[-limit:] if limit else rows)

    def fetch_ticker(self, symbol, params=None):
        self.calls.append(("fetch_ticker", symbol))
        ticker = self.tickers[symbol]
        if isinstance(ticker, Exception):
            raise ticker
        return dict(ticker)

    def fetch_balance(self, params=None):
        self.calls.append(("fetch_balance",))
        if isinstance(self.balance, Exception):
            raise self.balance
        return copy.deepcopy(self.balance)

    def create_order(self, symbol, type, side, amount, price=None, params=None):
        self.calls.append(("create_order", symbol, type, side, amount, price))
        return self._fill(symbol, side, amount, None)

    def create_market_buy_order_with_cost(self, symbol, cost, params=None):
        self.calls.append(("create_market_buy_order_with_cost", symbol, cost))
        return self._fill(symbol, "buy", None, cost)

    def fetch_order(self, id, symbol=None, params=None):
        self.calls.append(("fetch_order", id, symbol))
        if self.fetch_order_error is not None:
            raise self.fetch_order_error
        return copy.deepcopy(self.fetched_order)

    def fetch_open_orders(self, symbol=None, since=None, limit=None, params=None):
        self.calls.append(("fetch_open_orders", symbol))
        orders = self.open_orders.get(symbol, [])
        if isinstance(orders, Exception):
            raise orders
        return copy.deepcopy(orders)

    def cancel_order(self, id, symbol=None, params=None):
        self.calls.append(("cancel_order", id, symbol))
        if id in self.cancel_errors:
            raise self.cancel_errors[id]
        return {"id": id, "status": "canceled"}

    def set_sandbox_mode(self, enabled):
        self.calls.append(("set_sandbox_mode", enabled))
        super().set_sandbox_mode(enabled)


def make_broker(ex: FakeExchange | None = None, symbols: tuple[str, ...] = ("BTC/USDT", "ETH/USDT"),
                keys: bool = True, **kwargs: Any) -> CCXTBroker:
    ex = ex if ex is not None else FakeExchange()
    broker = CCXTBroker(ex.id, list(symbols), api_key="key" if keys else None,
                        secret="secret" if keys else None, exchange=ex, **kwargs)
    broker.fill_poll_delay = 0
    return broker


def buy(symbol: str = "BTC/USDT", qty: float = 0.1, reason: str = "") -> OrderRequest:
    return OrderRequest(symbol=symbol, side=Side.BUY, qty=qty, reason=reason)


def sell(symbol: str = "BTC/USDT", qty: float = 0.1, reason: str = "") -> OrderRequest:
    return OrderRequest(symbol=symbol, side=Side.SELL, qty=qty, reason=reason)


def order_calls(ex: FakeExchange) -> list[tuple[Any, ...]]:
    return [c for c in ex.calls if c[0] in ("create_order", "create_market_buy_order_with_cost")]


# ---------------------------------------------------------------------------
# OHLCV conversion and market data
# ---------------------------------------------------------------------------
def test_ohlcv_rows_become_canonical_utc_bars_sorted_and_deduplicated():
    rows = [[T0 + HOUR_MS, 2, 3, 1, 2.5, 7], [T0, 1, 2, 0.5, 1.5, 5], [T0 + HOUR_MS, 2, 3, 1, 2.6, 8]]
    bars = ohlcv_to_bars(rows)
    assert list(bars.columns) == BAR_COLUMNS
    assert all(dtype == "float64" for dtype in bars.dtypes)
    assert str(bars.index.tz) == "UTC"
    assert list(bars.index) == [pd.Timestamp("2024-01-01T00:00Z"), pd.Timestamp("2024-01-01T01:00Z")]
    assert bars["close"].iloc[-1] == 2.6  # duplicate timestamp: last one wins


def test_ohlcv_missing_volume_becomes_zero_and_candles_without_prices_are_dropped(caplog):
    rows = [[T0, 1, 2, 0.5, 1.5, None], [T0 + HOUR_MS, None, 3, 1, 2.5, 5], [T0 + 2 * HOUR_MS, 2, 3, 1, 2.5]]
    with caplog.at_level(logging.WARNING):
        bars = ohlcv_to_bars(rows)
    assert len(bars) == 2
    assert bars["volume"].tolist() == [0.0, 0.0]
    assert "malformed" in caplog.text


def test_ohlcv_empty_input_gives_empty_canonical_frame():
    bars = ohlcv_to_bars([])
    assert bars.empty and list(bars.columns) == BAR_COLUMNS
    assert str(bars.index.tz) == "UTC"


def test_get_bars_asks_exchange_for_exactly_limit_candles():
    ex = FakeExchange()
    broker = make_broker(ex)
    bars = broker.get_bars("BTC/USDT", "1h", 5)
    assert ex.calls == [("fetch_ohlcv", "BTC/USDT", "1h", None, 5)]
    assert len(bars) == 5
    assert bars.index[-1] == pd.Timestamp(T0 + 9 * HOUR_MS, unit="ms", tz="UTC")
    assert bars["close"].iloc[-1] == 110.0


def test_get_bars_rejects_timeframe_the_exchange_does_not_offer():
    ex = FakeExchange()
    ex.timeframes = {"1h": "60", "1d": "D"}
    with pytest.raises(BrokerError, match="4h"):
        make_broker(ex).get_bars("BTC/USDT", "4h", 5)
    assert not ex.calls


def test_get_bars_fails_clearly_without_ohlcv_support():
    ex = FakeExchange()
    ex.has["fetchOHLCV"] = False
    with pytest.raises(BrokerError, match="OHLCV"):
        make_broker(ex).get_bars("BTC/USDT", "1h", 5)


def test_get_bars_empty_response_is_an_error():
    ex = FakeExchange()
    ex.candles["BTC/USDT"] = []
    with pytest.raises(BrokerError, match="no 1h candles"):
        make_broker(ex).get_bars("BTC/USDT", "1h", 5)


@pytest.mark.parametrize("limit", [0, -1, 2.5])
def test_get_bars_rejects_bad_limit(limit):
    with pytest.raises(ValueError):
        make_broker().get_bars("BTC/USDT", "1h", limit)


def test_get_bars_unknown_symbol_is_broker_error():
    with pytest.raises(BrokerError, match="no market 'DOGE/USDT'"):
        make_broker().get_bars("DOGE/USDT", "1h", 5)


def test_get_bars_network_failure_is_broker_error():
    ex = FakeExchange()
    ex.candles["BTC/USDT"] = ccxt.RequestTimeout("timed out")
    with pytest.raises(BrokerError, match="RequestTimeout"):
        make_broker(ex).get_bars("BTC/USDT", "1h", 5)


def test_get_bars_pages_backwards_when_exchange_caps_candles_per_request():
    ex = FakeExchange(page_limit=200)
    ex.candles["BTC/USDT"] = hourly_rows(1000)
    bars = make_broker(ex).get_bars("BTC/USDT", "1h", 450)
    expected = ohlcv_to_bars(hourly_rows(1000)).tail(450)
    pd.testing.assert_frame_equal(bars, expected)
    fetches = [c for c in ex.calls if c[0] == "fetch_ohlcv"]
    assert all(limit <= 200 for *_, limit in fetches)
    assert fetches[0] == ("fetch_ohlcv", "BTC/USDT", "1h", None, 200)
    assert len(fetches) == 3


def test_get_bars_paging_stops_when_history_runs_out():
    ex = FakeExchange(page_limit=200)
    ex.candles["BTC/USDT"] = hourly_rows(250)
    bars = make_broker(ex).get_bars("BTC/USDT", "1h", 450)
    assert len(bars) == 250
    assert bars.index.is_monotonic_increasing and bars.index.is_unique


def test_get_bars_within_page_limit_is_a_single_request():
    ex = FakeExchange(page_limit=200)
    ex.candles["BTC/USDT"] = hourly_rows(300)
    assert len(make_broker(ex).get_bars("BTC/USDT", "1h", 200)) == 200
    assert ex.calls == [("fetch_ohlcv", "BTC/USDT", "1h", None, 200)]


@pytest.mark.parametrize("ticker, expected", [
    ({"last": 101.5, "bid": 100.0, "ask": 103.0}, 101.5),
    ({"last": None, "bid": 99.0, "ask": 101.0}, 100.0),
    ({"last": 0, "bid": None, "ask": 101.0, "close": 98.0}, 98.0),
])
def test_latest_price_uses_last_then_mid_then_close(ticker, expected):
    ex = FakeExchange()
    ex.tickers["BTC/USDT"] = ticker
    assert make_broker(ex).get_latest_price("BTC/USDT") == expected


def test_latest_price_without_any_usable_price_is_an_error():
    ex = FakeExchange()
    ex.tickers["BTC/USDT"] = {"last": None, "bid": 0, "ask": None, "close": float("nan")}
    with pytest.raises(BrokerError, match="no usable price"):
        make_broker(ex).get_latest_price("BTC/USDT")


def test_latest_price_network_failure_is_broker_error():
    ex = FakeExchange()
    ex.tickers["BTC/USDT"] = ccxt.ExchangeNotAvailable("down")
    with pytest.raises(BrokerError, match="network"):
        make_broker(ex).get_latest_price("BTC/USDT")


# ---------------------------------------------------------------------------
# Construction, public-only mode, markets
# ---------------------------------------------------------------------------
def test_public_mode_serves_market_data_without_keys():
    ex = FakeExchange()
    broker = make_broker(ex, keys=False)
    assert not broker.has_credentials
    assert len(broker.get_bars("BTC/USDT", "1h", 3)) == 3
    assert broker.get_latest_price("BTC/USDT") == 20_000.0
    assert broker.normalize_qty("BTC/USDT", 0.123456789) == 0.12345678
    assert broker.min_order_notional("BTC/USDT") == 5.0


@pytest.mark.parametrize("call", [
    lambda b: b.get_account(),
    lambda b: b.get_positions(),
    lambda b: b.submit_order(buy()),
    lambda b: b.cancel_all_orders(),
    lambda b: b.has_open_orders("BTC/USDT"),
    lambda b: b.close_all_positions(),
])
def test_public_mode_refuses_account_and_order_methods(call):
    ex = FakeExchange()
    with pytest.raises(BrokerError, match="API keys required"):
        call(make_broker(ex, keys=False))
    assert not ex.calls  # nothing private was attempted


@pytest.mark.parametrize("api_key, secret", [("key", None), (None, "secret"), ("key", "")])
def test_only_one_of_key_and_secret_is_a_config_error(api_key, secret):
    with pytest.raises(ValueError, match="both api_key and secret"):
        CCXTBroker("fakex", ["BTC/USDT"], api_key=api_key, secret=secret, exchange=FakeExchange())


def test_symbols_must_share_one_quote_currency():
    with pytest.raises(ValueError, match="one quote currency"):
        CCXTBroker("fakex", ["BTC/KRW", "ETH/USDT"], exchange=FakeExchange())


@pytest.mark.parametrize("symbols", [[], "BTC/USDT", ["BTCUSDT"], ["BTC/USDT:USDT"], ["/USDT"],
                                     ["BTC/"], ["BTC/ETH/USDT"], [None]])
def test_invalid_symbol_lists_are_rejected(symbols):
    with pytest.raises(ValueError):
        CCXTBroker("fakex", symbols, exchange=FakeExchange())


def test_quote_currency_is_the_account_currency_and_name_includes_exchange():
    broker = make_broker(symbols=("BTC/USDT", "ETH/USDT", "BTC/USDT"))
    assert broker.currency == broker.quote_currency == "USDT"
    assert broker.symbols == ["BTC/USDT", "ETH/USDT"]  # duplicates dropped, order kept
    assert broker.name == "ccxt:fakex"


def test_construction_makes_no_exchange_calls_and_markets_load_once():
    ex = FakeExchange()
    broker = make_broker(ex)
    assert ex.load_calls == 0
    broker.get_latest_price("BTC/USDT")
    broker.normalize_qty("ETH/USDT", 1.0)
    broker.min_order_notional("BTC/USDT")
    assert ex.load_calls == 1


def test_failed_market_load_is_broker_error_and_retried_next_time():
    ex = FakeExchange()
    ex.load_error = ccxt.NetworkError("boom")
    broker = make_broker(ex)
    with pytest.raises(BrokerError, match="load_markets"):
        broker.get_latest_price("BTC/USDT")
    ex.load_error = None
    assert broker.get_latest_price("BTC/USDT") == 20_000.0
    assert ex.load_calls == 2


def test_non_spot_market_is_refused():
    swap = spot_market("BTC/USDT", type="swap", spot=False, swap=True, contract=True)
    broker = make_broker(FakeExchange([swap]), symbols=("BTC/USDT",))
    with pytest.raises(BrokerError, match="not a spot market"):
        broker.get_latest_price("BTC/USDT")


def test_unknown_exchange_id_is_a_value_error_mentioning_ccxt_exchanges():
    with pytest.raises(ValueError, match=r"ccxt\.exchanges") as info:
        CCXTBroker("binanse", ["BTC/USDT"])
    assert "binance" in str(info.value)  # close-match hint


def test_real_ccxt_exchange_is_built_with_rate_limit_and_credentials():
    public = CCXTBroker("upbit", ["BTC/KRW"])
    assert isinstance(public.exchange, ccxt.upbit)
    assert public.exchange.enableRateLimit is True
    assert not public.exchange.apiKey
    private = CCXTBroker("okx", ["BTC/USDT"], api_key="k", secret="s", password="p")
    assert (private.exchange.apiKey, private.exchange.secret, private.exchange.password) == ("k", "s", "p")
    assert private.has_credentials


def test_sandbox_mode_is_enabled_on_the_exchange():
    ex = FakeExchange()
    make_broker(ex, sandbox=True)
    assert ("set_sandbox_mode", True) in ex.calls
    assert ex.urls["api"] == {"public": "https://testnet.fake"}


def test_sandbox_on_real_binance_switches_to_testnet_urls():
    broker = CCXTBroker("binance", ["BTC/USDT"], api_key="k", secret="s", sandbox=True)
    assert broker.exchange.isSandboxModeEnabled
    assert broker.exchange.urls["api"] == broker.exchange.urls["test"]


@pytest.mark.parametrize("build", [
    lambda: CCXTBroker("upbit", ["BTC/KRW"], sandbox=True),   # real ccxt: no testnet (crashes in ccxt)
    lambda: make_broker(FakeExchange(sandbox_url=False), sandbox=True),
])
def test_sandbox_unsupported_is_a_clear_value_error(build):
    with pytest.raises(ValueError, match="sandbox"):
        build()


# ---------------------------------------------------------------------------
# Account and positions
# ---------------------------------------------------------------------------
def test_account_equity_is_quote_plus_holdings_at_latest_prices():
    ex = FakeExchange()
    ex.set_balance("USDT", 1_000.0, free=800.0)
    ex.set_balance("BTC", 0.5)
    ex.set_balance("ETH", 0.0)
    account = make_broker(ex).get_account()
    assert account.cash == 1_000.0
    assert account.buying_power == 800.0
    assert account.equity == pytest.approx(1_000.0 + 0.5 * 20_000.0)
    assert account.currency == "USDT"
    assert account.day_start_equity is None and not account.trading_blocked
    assert ("fetch_ticker", "ETH/USDT") not in ex.calls  # nothing held -> no price needed


def test_account_with_missing_or_null_balances_counts_them_as_zero():
    ex = FakeExchange()
    ex.balance = {"info": {}, "free": {}, "used": {}, "total": {"USDT": None}}
    account = make_broker(ex).get_account()
    assert (account.equity, account.cash, account.buying_power) == (0.0, 0.0, 0.0)


def test_account_reads_per_currency_balance_shape():
    ex = FakeExchange()
    ex.balance = {"USDT": {"free": 50.0, "used": 0.0, "total": 50.0}, "BTC": {"free": 0.1, "total": 0.1}}
    account = make_broker(ex).get_account()
    assert account.cash == 50.0 and account.buying_power == 50.0
    assert account.equity == pytest.approx(50.0 + 2_000.0)


def test_positions_ignore_dust_and_include_locked_coins():
    ex = FakeExchange()
    ex.set_balance("BTC", 0.0001)                # 2 USDT < 5 USDT minimum -> dust
    ex.set_balance("ETH", 2.0, free=0.5)         # 1.5 ETH locked in an order: still ours
    positions = make_broker(ex).get_positions()
    assert list(positions) == ["ETH/USDT"]
    eth = positions["ETH/USDT"]
    assert eth.qty == 2.0 and eth.market_price == 1_500.0


def test_positions_use_the_stored_entry_price(tmp_path):
    path = tmp_path / "entries.json"
    path.write_text(json.dumps({"BTC/USDT": {"qty": 0.5, "avg_entry_price": 18_000.0}}))
    ex = FakeExchange()
    ex.set_balance("BTC", 0.5)
    position = make_broker(ex, entries_path=path).get_positions()["BTC/USDT"]
    assert position.avg_entry_price == 18_000.0
    assert position.unrealized_pnl == pytest.approx(0.5 * 2_000.0)


def test_unknown_entry_uses_current_price_warns_once_and_stays_anchored(tmp_path, caplog):
    path = tmp_path / "entries.json"
    ex = FakeExchange()
    ex.set_balance("BTC", 0.5)
    broker = make_broker(ex, entries_path=path)
    with caplog.at_level(logging.WARNING, logger="bot.brokers.ccxt_broker"):
        first = broker.get_positions()["BTC/USDT"]
        ex.tickers["BTC/USDT"] = {"last": 18_000.0}
        second = broker.get_positions()["BTC/USDT"]
    assert first.avg_entry_price == 20_000.0
    assert second.avg_entry_price == 20_000.0  # a stop-loss keeps a fixed reference
    assert second.market_price == 18_000.0
    assert sum("entry price" in r.getMessage() for r in caplog.records) == 1
    assert json.loads(path.read_text())["BTC/USDT"]["avg_entry_price"] == 20_000.0


# ---------------------------------------------------------------------------
# Entry-price store
# ---------------------------------------------------------------------------
def test_buys_store_weighted_average_entry_and_persist(tmp_path):
    path = tmp_path / "state" / "entries.json"
    ex = FakeExchange()
    broker = make_broker(ex, entries_path=path)
    ex.tickers["BTC/USDT"] = {"last": 100.0}
    assert broker.submit_order(buy(qty=0.1)).status == "filled"
    ex.set_balance("BTC", 0.1)
    ex.tickers["BTC/USDT"] = {"last": 200.0}
    assert broker.submit_order(buy(qty=0.3)).status == "filled"
    expected = {"qty": pytest.approx(0.4), "avg_entry_price": pytest.approx((0.1 * 100 + 0.3 * 200) / 0.4)}
    assert broker.entries["BTC/USDT"] == expected
    reloaded = make_broker(FakeExchange(), entries_path=path)
    assert reloaded.entries["BTC/USDT"] == expected


def test_buy_uses_the_exchange_fill_price_not_the_ticker(tmp_path):
    ex = FakeExchange()
    ex.order_response = {"id": "o1", "status": "closed", "filled": 0.1, "average": 20_100.0}
    broker = make_broker(ex, entries_path=tmp_path / "e.json")
    broker.submit_order(buy(qty=0.1))
    assert broker.entries["BTC/USDT"]["avg_entry_price"] == 20_100.0


def test_buy_replaces_stale_entry_when_nothing_is_held(tmp_path):
    path = tmp_path / "entries.json"
    path.write_text(json.dumps({"BTC/USDT": {"qty": 1.0, "avg_entry_price": 50_000.0}}))
    ex = FakeExchange()  # no BTC balance: the old position was closed elsewhere
    broker = make_broker(ex, entries_path=path)
    broker.submit_order(buy(qty=0.1))
    assert broker.entries["BTC/USDT"] == {"qty": 0.1, "avg_entry_price": 20_000.0}


def test_selling_out_removes_the_entry(tmp_path):
    path = tmp_path / "entries.json"
    path.write_text(json.dumps({"BTC/USDT": {"qty": 0.4, "avg_entry_price": 150.0}}))
    ex = FakeExchange()
    ex.set_balance("BTC", 0.4)
    broker = make_broker(ex, entries_path=path)
    assert broker.submit_order(sell(qty=0.4)).status == "filled"
    assert broker.entries == {}
    assert json.loads(path.read_text()) == {}


def test_partial_sell_keeps_average_and_reduces_qty(tmp_path):
    path = tmp_path / "entries.json"
    path.write_text(json.dumps({"BTC/USDT": {"qty": 0.4, "avg_entry_price": 15_000.0}}))
    ex = FakeExchange()
    ex.set_balance("BTC", 0.4)
    broker = make_broker(ex, entries_path=path)
    broker.submit_order(sell(qty=0.1))
    assert broker.entries["BTC/USDT"] == {"qty": pytest.approx(0.3), "avg_entry_price": 15_000.0}


def test_sell_leaving_only_dust_removes_the_entry(tmp_path):
    path = tmp_path / "entries.json"
    path.write_text(json.dumps({"BTC/USDT": {"qty": 0.4001, "avg_entry_price": 15_000.0}}))
    ex = FakeExchange()
    ex.set_balance("BTC", 0.4)  # exchange fee was taken in BTC
    broker = make_broker(ex, entries_path=path)
    broker.submit_order(sell(qty=0.4001))
    assert "BTC/USDT" not in broker.entries  # 0.0001 BTC = 2 USDT < 5 USDT minimum


def test_corrupt_entries_file_is_moved_aside_and_store_starts_empty(tmp_path, caplog):
    path = tmp_path / "entries.json"
    path.write_text("{not json")
    with caplog.at_level(logging.WARNING):
        broker = make_broker(entries_path=path)
    assert broker.entries == {}
    assert not path.exists()
    assert (tmp_path / "entries.json.corrupt").read_text() == "{not json"
    assert "unreadable" in caplog.text


def test_invalid_stored_entries_are_ignored(tmp_path):
    path = tmp_path / "entries.json"
    path.write_text(json.dumps({
        "BTC/USDT": {"qty": 0.1, "avg_entry_price": 100.0},
        "ETH/USDT": {"qty": "abc", "avg_entry_price": 1.0},
        "XRP/USDT": {"qty": 1.0, "avg_entry_price": -5},
        "SOL/USDT": "nonsense",
    }))
    assert make_broker(entries_path=path).entries == {"BTC/USDT": {"qty": 0.1, "avg_entry_price": 100.0}}


def test_failing_to_save_entries_after_an_order_does_not_raise(tmp_path, caplog):
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("")
    broker = make_broker(entries_path=blocker / "entries.json")
    with caplog.at_level(logging.ERROR):
        result = broker.submit_order(buy(qty=0.1))
    assert result.status == "filled"
    assert "could not save entry prices" in caplog.text


# ---------------------------------------------------------------------------
# Order placement
# ---------------------------------------------------------------------------
def test_market_buy_by_amount_sends_truncated_amount():
    ex = FakeExchange()
    result = make_broker(ex).submit_order(buy(qty=0.123456789, reason="sma cross"))
    assert order_calls(ex) == [("create_order", "BTC/USDT", "market", "buy", 0.12345678, None)]
    assert result.status == "filled" and result.ok
    assert result.qty == 0.12345678
    assert result.filled_qty == 0.12345678
    assert result.filled_avg_price == 20_000.0
    assert result.side is Side.BUY and result.symbol == "BTC/USDT"
    assert result.reason == "sma cross"
    assert result.id.startswith("ord-")


@pytest.mark.parametrize("qty, step, expected", [
    (0.0019999, 0.001, 0.001),
    (0.99999999, 0.01, 0.99),
    (1.0, 0.01, 1.0),
    (123.456, 1.0, 123.0),
])
def test_amount_precision_always_rounds_down(qty, step, expected):
    ex = FakeExchange([spot_market("BTC/USDT", amount_step=step)])
    broker = make_broker(ex, symbols=("BTC/USDT",))
    assert broker.normalize_qty("BTC/USDT", qty) == expected
    ex.tickers["BTC/USDT"] = {"last": 5_000.0}
    ex.set_balance("USDT", 1e9)
    broker.submit_order(buy(qty=qty))
    assert order_calls(ex)[-1][4] == expected


def test_market_buy_by_cost_uses_create_market_buy_order_with_cost():
    ex = FakeExchange(buy_by_cost=True)
    result = make_broker(ex).submit_order(buy(qty=0.25))
    assert order_calls(ex) == [("create_market_buy_order_with_cost", "BTC/USDT", 5_000.0)]
    assert result.status == "filled"
    assert result.filled_qty == pytest.approx(0.25)
    assert result.qty == 0.25


def test_market_buy_by_cost_without_cost_method_passes_price():
    ex = FakeExchange(buy_by_cost=True, has_cost_method=False)
    make_broker(ex).submit_order(buy(qty=0.25))
    assert order_calls(ex) == [("create_order", "BTC/USDT", "market", "buy", 0.25, 20_000.0)]


def test_market_buy_cost_flag_nested_under_create_order_options_is_honoured():
    ex = FakeExchange()
    ex.options["createOrder"] = {"createMarketBuyOrderRequiresPrice": True}
    make_broker(ex).submit_order(buy(qty=0.25))
    assert order_calls(ex)[0][0] == "create_market_buy_order_with_cost"


def test_upbit_buys_by_cost_even_without_the_option():
    ex = FakeExchange(exchange_id="upbit")
    make_broker(ex).submit_order(buy(qty=0.25))
    assert order_calls(ex)[0][0] == "create_market_buy_order_with_cost"


def test_sells_are_by_amount_even_on_cost_based_exchanges():
    ex = FakeExchange(buy_by_cost=True)
    ex.set_balance("BTC", 1.0)
    make_broker(ex).submit_order(sell(qty=0.5))
    assert order_calls(ex) == [("create_order", "BTC/USDT", "market", "sell", 0.5, None)]


def test_real_ccxt_upbit_market_buy_sends_krw_cost_and_reads_back_the_fill():
    """End to end through ccxt's own upbit code, with the HTTP layer stubbed."""
    ex = ccxt.upbit({"apiKey": "k", "secret": "s"})
    ex.fetch = _no_network
    ex.set_markets([spot_market("BTC/KRW", amount_step=1e-8, price_step=1e-8, id="KRW-BTC",
                                baseId="BTC", quoteId="KRW")])
    ex.fetch_ticker = lambda symbol, params=None: {"symbol": symbol, "last": 50_000_000.0}
    ex.fetch_balance = lambda params=None: {"free": {"KRW": 1_000_000.0}, "total": {"KRW": 1_000_000.0}}
    sent: list[dict[str, Any]] = []

    def private_post_orders(request):
        sent.append(dict(request))
        return {"uuid": "u-1", "side": "bid", "ord_type": "price", "price": request["price"], "state": "wait",
                "market": "KRW-BTC", "created_at": "2026-01-01T09:00:00+09:00", "executed_volume": "0",
                "trades_count": 0}

    ex.privatePostOrders = private_post_orders
    ex.fetch_order = lambda id, symbol=None, params=None: {
        "id": id, "symbol": symbol, "status": "canceled", "filled": 0.00199, "average": 50_100_000.0,
        "cost": 99_699.0}
    broker = CCXTBroker("upbit", ["BTC/KRW"], api_key="k", secret="s", exchange=ex)
    broker.fill_poll_delay = 0
    assert broker.min_order_notional("BTC/KRW") == 5_000.0

    result = broker.submit_order(buy("BTC/KRW", qty=0.002))
    assert sent == [{"market": "KRW-BTC", "side": "bid", "ord_type": "price", "price": "100000"}]
    # Upbit reports a spent market buy as "cancel"; it is a fill, not a rejection.
    assert result.status == "filled"
    assert result.filled_qty == 0.00199 and result.filled_avg_price == 50_100_000.0
    assert broker.entries["BTC/KRW"] == {"qty": 0.00199, "avg_entry_price": 50_100_000.0}


def test_real_ccxt_binance_buys_by_amount():
    ex = ccxt.binance({"apiKey": "k", "secret": "s"})
    ex.fetch = _no_network
    ex.set_markets([spot_market("BTC/USDT", amount_step=1e-5, cost_min=5.0)])
    ex.fetch_ticker = lambda symbol, params=None: {"last": 20_000.0}
    ex.fetch_balance = lambda params=None: {"free": {"USDT": 1_000.0}, "total": {"USDT": 1_000.0}}
    calls: list[tuple[Any, ...]] = []
    ex.create_order = lambda *args, **kwargs: calls.append(args) or {"id": "b1", "status": "closed",
                                                                     "filled": args[3], "average": 20_000.0}
    broker = CCXTBroker("binance", ["BTC/USDT"], api_key="k", secret="s", exchange=ex)
    assert broker.submit_order(buy(qty=0.0123456)).status == "filled"
    assert calls == [("BTC/USDT", "market", "buy", 0.01234)]


# ---------------------------------------------------------------------------
# Local rejections: nothing is sent
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("market, qty, fragment", [
    (spot_market("BTC/USDT", amount_min=0.01), 0.005, "amount 0.005 BTC is below the exchange minimum"),
    (spot_market("BTC/USDT", amount_max=1.0), 2.0, "above the exchange maximum"),
    (spot_market("BTC/USDT", cost_min=10.0), 0.0004, "order value 8 USDT is below the exchange minimum 10"),
    (spot_market("BTC/USDT", cost_max=1_000.0), 0.1, "order value 2000 USDT is above"),
    (spot_market("BTC/USDT", limits={"amount": {}, "cost": {}, "market": {"min": 0.5}}), 0.1,
     "market-order amount"),
    (spot_market("BTC/USDT", amount_step=0.001), 0.0009, "below BTC/USDT's amount precision"),
])
def test_orders_outside_market_limits_are_rejected_before_sending(market, qty, fragment):
    ex = FakeExchange([market])
    result = make_broker(ex, symbols=("BTC/USDT",)).submit_order(buy(qty=qty))
    assert result.status == "rejected" and not result.ok
    assert fragment in result.reason
    assert not order_calls(ex)


def test_cost_minimum_also_applies_to_cost_based_buys():
    ex = FakeExchange(buy_by_cost=True)
    result = make_broker(ex).submit_order(buy(qty=0.0002))  # 4 USDT < 5 USDT
    assert result.status == "rejected" and "below the exchange minimum 5" in result.reason
    assert not order_calls(ex)


def test_buy_larger_than_free_quote_balance_is_rejected_locally():
    ex = FakeExchange()
    ex.set_balance("USDT", 1_000.0, free=100.0)
    result = make_broker(ex).submit_order(buy(qty=0.01))  # 200 USDT
    assert result.status == "rejected" and "insufficient USDT" in result.reason
    assert not order_calls(ex)


@pytest.mark.parametrize("qty", [0.0, -1.0, float("nan"), float("inf")])
def test_invalid_quantities_are_rejected(qty):
    ex = FakeExchange()
    result = make_broker(ex).submit_order(buy(qty=qty))
    assert result.status == "rejected" and "invalid quantity" in result.reason
    assert not order_calls(ex)


def test_orders_for_unconfigured_symbols_are_rejected():
    ex = FakeExchange()
    result = make_broker(ex, symbols=("BTC/USDT",)).submit_order(buy("ETH/USDT", qty=1.0))
    assert result.status == "rejected" and "not one of the configured symbols" in result.reason
    assert not order_calls(ex)


def test_inactive_market_is_rejected():
    ex = FakeExchange([spot_market("BTC/USDT", active=False)])
    result = make_broker(ex, symbols=("BTC/USDT",)).submit_order(buy(qty=0.1))
    assert result.status == "rejected" and "not active" in result.reason
    assert not order_calls(ex)


def test_sell_is_capped_to_the_free_balance_never_short():
    ex = FakeExchange()
    ex.set_balance("BTC", 0.5, free=0.3)
    result = make_broker(ex).submit_order(sell(qty=0.5, reason="stop_loss"))
    assert order_calls(ex) == [("create_order", "BTC/USDT", "market", "sell", 0.3, None)]
    assert result.qty == 0.3
    assert "stop_loss" in result.reason and "capped to available 0.3 BTC" in result.reason


def test_sell_without_holdings_is_rejected():
    ex = FakeExchange()
    result = make_broker(ex).submit_order(sell(qty=0.5))
    assert result.status == "rejected" and "no BTC available" in result.reason
    assert not order_calls(ex)


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("error", [
    ccxt.InsufficientFunds("not enough USDT"),
    ccxt.InvalidOrder("lot size"),
    ccxt.OrderNotFillable("no liquidity"),
    ccxt.BadRequest("bad param"),
    ccxt.BadSymbol("bad symbol"),
    ccxt.MarketClosed("halted"),
])
def test_exchange_business_rejections_become_rejected_results(error):
    ex = FakeExchange()
    ex.order_error = error
    result = make_broker(ex).submit_order(buy(qty=0.01))
    assert result.status == "rejected"
    assert type(error).__name__ in result.reason and str(error) in result.reason
    assert result.qty == 0.01


@pytest.mark.parametrize("error", [
    ccxt.NetworkError("reset"),
    ccxt.RequestTimeout("timeout"),
    ccxt.ExchangeNotAvailable("maintenance"),
    ccxt.DDoSProtection("slow down"),
    ccxt.RateLimitExceeded("429"),
])
def test_network_errors_while_ordering_raise_broker_error(error):
    ex = FakeExchange()
    ex.order_error = error
    with pytest.raises(BrokerError, match="may or may not have reached the exchange"):
        make_broker(ex).submit_order(buy(qty=0.01))


@pytest.mark.parametrize("error", [ccxt.AuthenticationError("bad key"), ccxt.ExchangeError("??"),
                                   RuntimeError("bug")])
def test_other_order_failures_raise_broker_error(error):
    ex = FakeExchange()
    ex.order_error = error
    with pytest.raises(BrokerError):
        make_broker(ex).submit_order(buy(qty=0.01))


def test_read_failures_before_ordering_send_nothing():
    ex = FakeExchange()
    ex.tickers["BTC/USDT"] = ccxt.RequestTimeout("slow")
    with pytest.raises(BrokerError):
        make_broker(ex).submit_order(buy(qty=0.01))
    ex = FakeExchange()
    ex.balance = ccxt.AuthenticationError("invalid key")
    with pytest.raises(BrokerError, match="API key rejected"):
        make_broker(ex).submit_order(buy(qty=0.01))
    assert not order_calls(ex)


def test_account_read_errors_are_broker_errors():
    ex = FakeExchange()
    ex.balance = ccxt.ExchangeNotAvailable("down")
    broker = make_broker(ex)
    with pytest.raises(BrokerError):
        broker.get_account()
    with pytest.raises(BrokerError):
        broker.get_positions()


# ---------------------------------------------------------------------------
# Status mapping and fill details
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("status, filled, expected", [
    ("closed", None, "filled"),
    ("closed", 1.0, "filled"),
    ("open", 0.0, "accepted"),
    ("open", 0.5, "accepted"),
    (None, None, "accepted"),
    ("canceled", 0.0, "rejected"),
    ("canceled", None, "rejected"),
    ("cancelled", 0.0, "rejected"),
    ("rejected", None, "rejected"),
    ("expired", 0.0, "rejected"),
    ("canceled", 0.2, "filled"),
])
def test_map_order_status(status, filled, expected):
    assert map_order_status(status, filled) == expected


def test_open_order_is_reread_to_get_the_fill():
    ex = FakeExchange()
    ex.order_response = {"id": "o1", "status": "open", "filled": 0.0}
    ex.fetched_order = {"id": "o1", "status": "closed", "filled": 0.01, "average": 20_050.0}
    result = make_broker(ex).submit_order(buy(qty=0.01))
    assert ("fetch_order", "o1", "BTC/USDT") in ex.calls
    assert result.status == "filled" and result.filled_avg_price == 20_050.0


def test_open_order_stays_accepted_when_it_cannot_be_reread(tmp_path):
    ex = FakeExchange()
    ex.order_response = {"id": "o1", "status": "open", "filled": 0.0}
    ex.fetch_order_error = ccxt.RequestTimeout("slow")
    broker = make_broker(ex, entries_path=tmp_path / "e.json")
    result = broker.submit_order(buy(qty=0.01))
    assert result.status == "accepted" and result.ok
    assert result.id == "o1" and result.filled_qty == 0.0
    # assumed to fill at the ticker price so a stop-loss has a reference
    assert broker.entries["BTC/USDT"] == {"qty": 0.01, "avg_entry_price": 20_000.0}


def test_order_is_not_reread_when_exchange_lacks_fetch_order():
    ex = FakeExchange()
    ex.has["fetchOrder"] = False
    ex.order_response = {"id": "o1", "status": "open"}
    assert make_broker(ex).submit_order(buy(qty=0.01)).status == "accepted"
    assert "fetch_order" not in ex.names()


def test_cancelled_order_without_fill_is_rejected_and_records_nothing(tmp_path):
    ex = FakeExchange()
    ex.order_response = {"id": "o1", "status": "canceled", "filled": 0.0}
    broker = make_broker(ex, entries_path=tmp_path / "e.json")
    result = broker.submit_order(buy(qty=0.01))
    assert result.status == "rejected" and "canceled" in result.reason
    assert broker.entries == {}


def test_partially_filled_then_cancelled_order_reports_the_fill():
    ex = FakeExchange()
    ex.order_response = {"id": "o1", "status": "canceled", "filled": 0.004, "average": 20_000.0}
    result = make_broker(ex).submit_order(buy(qty=0.01))
    assert result.status == "filled" and result.filled_qty == 0.004
    assert "partially filled" in result.reason


def test_closed_order_without_fill_details_counts_as_fully_filled():
    ex = FakeExchange()
    ex.has["fetchOrder"] = False
    ex.order_response = {"id": "o1", "status": "closed", "filled": None, "cost": 200.0}
    result = make_broker(ex).submit_order(buy(qty=0.01))
    assert result.status == "filled" and result.filled_qty == 0.01
    assert result.filled_avg_price is None


def test_average_price_is_derived_from_cost_when_missing():
    ex = FakeExchange()
    ex.order_response = {"id": "o1", "status": "closed", "filled": 0.01, "average": None, "cost": 201.0}
    assert make_broker(ex).submit_order(buy(qty=0.01)).filled_avg_price == pytest.approx(20_100.0)


def test_unprocessable_response_after_sending_never_raises(monkeypatch):
    ex = FakeExchange()
    broker = make_broker(ex)

    def explode(*args, **kwargs):
        raise RuntimeError("bug")

    monkeypatch.setattr(broker, "_record_fill", explode)
    result = broker.submit_order(buy(qty=0.01))
    assert result.status == "accepted"  # sent: the engine must not retry it
    assert result.id.startswith("ord-")


# ---------------------------------------------------------------------------
# Open orders, cancel, flatten
# ---------------------------------------------------------------------------
def test_has_open_orders_queries_the_symbol():
    ex = FakeExchange()
    ex.open_orders["ETH/USDT"] = [{"id": "x1", "status": "open"}]
    broker = make_broker(ex)
    assert broker.has_open_orders("ETH/USDT") is True
    assert broker.has_open_orders("BTC/USDT") is False
    assert ("fetch_open_orders", "ETH/USDT") in ex.calls


def test_cancel_all_orders_cancels_every_configured_symbol_and_ignores_already_gone():
    ex = FakeExchange()
    ex.open_orders = {"BTC/USDT": [{"id": "a"}, {"id": "b"}], "ETH/USDT": [{"id": "c"}]}
    ex.cancel_errors = {"b": ccxt.OrderNotFound("gone")}
    make_broker(ex).cancel_all_orders()
    cancels = [c for c in ex.calls if c[0] == "cancel_order"]
    assert cancels == [("cancel_order", "a", "BTC/USDT"), ("cancel_order", "b", "BTC/USDT"),
                       ("cancel_order", "c", "ETH/USDT")]


def test_cancel_all_orders_tries_everything_then_reports_failures():
    ex = FakeExchange()
    ex.open_orders = {"BTC/USDT": ccxt.NetworkError("down"), "ETH/USDT": [{"id": "c"}, {"id": "d"}]}
    ex.cancel_errors = {"c": ccxt.ExchangeError("nope")}
    with pytest.raises(BrokerError, match="incomplete"):
        make_broker(ex).cancel_all_orders()
    assert ("cancel_order", "d", "ETH/USDT") in ex.calls


def test_close_all_positions_sells_every_non_dust_holding():
    ex = FakeExchange()
    ex.set_balance("BTC", 0.5)
    ex.set_balance("ETH", 0.001)  # 1.5 USDT: dust, cannot be sold
    results = make_broker(ex).close_all_positions()
    assert [(r.symbol, r.side, r.qty, r.status) for r in results] == [("BTC/USDT", Side.SELL, 0.5, "filled")]
    assert order_calls(ex) == [("create_order", "BTC/USDT", "market", "sell", 0.5, None)]


# ---------------------------------------------------------------------------
# Market rules
# ---------------------------------------------------------------------------
def test_min_order_notional_uses_market_cost_minimum_else_default():
    ex = FakeExchange([spot_market("BTC/USDT", cost_min=10.0), spot_market("ETH/USDT")])
    broker = make_broker(ex)
    assert broker.min_order_notional("BTC/USDT") == 10.0
    assert broker.min_order_notional("ETH/USDT") == 1.0


def test_min_order_notional_knows_upbit_krw_minimum():
    ex = FakeExchange([spot_market("BTC/KRW")], exchange_id="upbit")
    assert make_broker(ex, symbols=("BTC/KRW",)).min_order_notional("BTC/KRW") == 5_000.0


@pytest.mark.parametrize("qty, expected", [
    (0.123456789, 0.12345678),
    (0.000009, 0.0),            # below the 1e-5 amount minimum
    (1e-9, 0.0),                # below the precision step
    (0.0, 0.0),
    (-1.0, 0.0),
    (float("nan"), 0.0),
    (float("inf"), 0.0),
])
def test_normalize_qty(qty, expected):
    assert make_broker().normalize_qty("BTC/USDT", qty) == expected


def test_normalize_qty_respects_market_order_minimum():
    ex = FakeExchange([spot_market("BTC/USDT", limits={"amount": {"min": None}, "market": {"min": 0.1}})])
    broker = make_broker(ex, symbols=("BTC/USDT",))
    assert broker.normalize_qty("BTC/USDT", 0.05) == 0.0
    assert broker.normalize_qty("BTC/USDT", 0.15) == 0.15


def test_normalize_qty_unknown_symbol_is_broker_error():
    with pytest.raises(BrokerError):
        make_broker().normalize_qty("DOGE/USDT", 1.0)


def test_can_serve_as_price_feed_for_paper_broker():
    """Public CCXTBroker has everything PaperBroker looks for on its feed."""
    broker = make_broker(keys=False)
    for attr in ("get_bars", "get_latest_price", "normalize_qty", "min_order_notional", "is_market_open"):
        assert callable(getattr(broker, attr))
    assert broker.is_market_open() is True
    assert math.isclose(broker.get_latest_price("ETH/USDT"), 1_500.0)
    assert isinstance(Path(__file__), Path)


# ---- regression: one unpriceable holding / minimum order value units -----------


def test_one_holding_that_cannot_be_priced_does_not_fail_the_account_read():
    ex = FakeExchange()
    broker = make_broker(ex)
    ex.set_balance("BTC", 0.1)
    ex.set_balance("ETH", 2.0)
    broker.get_account()  # both priced: remembers their last prices
    ex.tickers["ETH/USDT"] = ccxt.ExchangeNotAvailable("ETH ticker down")

    account = broker.get_account()
    positions = broker.get_positions()

    assert account.unpriced == ("ETH/USDT",)
    assert account.equity == pytest.approx(10_000.0 + 0.1 * 20_000.0 + 2.0 * 1_500.0)
    assert set(positions) == {"BTC/USDT", "ETH/USDT"}
    assert positions["ETH/USDT"].market_price == 1_500.0


def test_delisted_holding_does_not_fail_the_account_read():
    ex = FakeExchange()
    broker = make_broker(ex)
    ex.set_balance("BTC", 0.1)
    ex.set_balance("ETH", 2.0)
    ex.market_list = [m for m in ex.market_list if m["symbol"] != "ETH/USDT"]  # gone after a restart

    account = broker.get_account()

    assert account.unpriced == ("ETH/USDT",)
    assert account.equity == pytest.approx(10_000.0 + 0.1 * 20_000.0)
    assert set(broker.get_positions()) == {"BTC/USDT"}


def test_engine_still_stops_out_one_coin_when_another_cannot_be_priced(tmp_path):
    from datetime import datetime, timezone

    from bot.config import BotConfig, BrokerConfig, NotifyConfig
    from bot.engine import TradingEngine
    from bot.notify import Notifier
    from bot.risk import RiskConfig, RiskManager
    from bot.state import STATE_FILE, BotState, StateStore
    from bot.strategies import create_strategy

    entries = tmp_path / "entries.json"
    entries.write_text(json.dumps({"BTC/USDT": {"qty": 0.1, "avg_entry_price": 40_000.0}}))
    # The bot bought that BTC itself (its own record), so it manages it.
    StateStore(tmp_path / "state" / STATE_FILE).save(
        BotState(owned={"BTC/USDT": {"qty": 0.1, "avg_entry_price": 40_000.0}}))
    ex = FakeExchange()
    broker = make_broker(ex, entries_path=entries)
    ex.set_balance("BTC", 0.1)  # bought at 40k, now 20k: -50% with a 5% stop
    ex.set_balance("ETH", 2.0)
    ex.tickers["ETH/USDT"] = ccxt.ExchangeNotAvailable("ETH ticker down")
    risk = RiskConfig(stop_loss_pct=5.0)
    cfg = BotConfig(symbols=["BTC/USDT", "ETH/USDT"], timeframe="1h", bars_lookback=5, timezone="UTC",
                    broker=BrokerConfig(type="ccxt", exchange="fakex"), risk=risk,
                    state_dir=tmp_path / "state", log_dir=tmp_path / "logs")
    clock = lambda: datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)  # noqa: E731
    engine = TradingEngine(cfg, broker, create_strategy("sma_crossover", {"fast": 2, "slow": 3}),
                           RiskManager(risk), StateStore(cfg.state_dir / STATE_FILE),
                           Notifier(NotifyConfig()), clock=clock)

    report = engine.run_once()

    assert ("create_order", "BTC/USDT", "market", "sell", 0.1, None) in ex.calls
    assert any("ETH" in error for error in report.errors)


def upbit_exchange(*market_ids: str) -> FakeExchange:
    """A FakeExchange carrying upbit's own parsed markets (cost.min is None)."""
    parsed = [ccxt.upbit().parse_market({"market": market_id}) for market_id in market_ids]
    return FakeExchange(parsed, exchange_id="upbit")


def test_btc_quoted_market_without_a_reported_minimum_is_not_one_whole_btc():
    from bot.models import Account, Action, Signal
    from bot.risk import RiskConfig, RiskManager

    broker = make_broker(upbit_exchange("BTC-ETH", "BTC-XRP"), symbols=("ETH/BTC", "XRP/BTC"), keys=False)
    minimum = broker.min_order_notional("ETH/BTC")
    assert minimum < 0.001

    risk = RiskManager(RiskConfig(min_order_notional=0.00005, max_position_pct=20.0, stop_loss_pct=None))
    qty, why = risk.entry_qty("ETH/BTC", 0.05, Signal(Action.BUY), Account(0.5, 0.5, 0.5), {}, minimum)
    assert qty > 0, why  # a 0.1 BTC entry is not "below minimum"


def test_upbit_krw_minimum_is_still_known_without_keys():
    broker = make_broker(upbit_exchange("KRW-BTC"), symbols=("BTC/KRW",), keys=False)
    assert broker.min_order_notional("BTC/KRW") == 5_000.0


def test_minimum_order_value_comes_from_the_private_market_endpoint_when_keys_are_set():
    class UpbitWithChance(FakeExchange):
        def fetch_market(self, symbol, params=None):
            self.calls.append(("fetch_market", symbol))
            return {"limits": {"cost": {"min": 0.0005}}}

    ex = UpbitWithChance([ccxt.upbit().parse_market({"market": "BTC-ETH"})], exchange_id="upbit")
    broker = make_broker(ex, symbols=("ETH/BTC",))
    assert broker.min_order_notional("ETH/BTC") == 0.0005
    assert broker.min_order_notional("ETH/BTC") == 0.0005
    assert ex.names().count("fetch_market") == 1  # looked up once, then cached


def test_usd_quoted_market_without_a_reported_minimum_keeps_the_1_unit_floor():
    ex = FakeExchange([spot_market("BTC/USDT")])
    assert make_broker(ex, symbols=("BTC/USDT",)).min_order_notional("BTC/USDT") == 1.0


# ---- regression: open orders tell the bot's own from others; per-symbol cancel -----


def test_open_orders_tell_the_bots_own_orders_from_manual_ones():
    ex = FakeExchange()
    broker = make_broker(ex)
    ex.order_response = {"id": "ord-bot", "symbol": "BTC/USDT", "side": "buy", "status": "open",
                         "amount": 0.1, "filled": 0.0}
    ex.fetched_order = dict(ex.order_response)
    broker.submit_order(buy("BTC/USDT", 0.1))
    ex.open_orders["BTC/USDT"] = [
        {"id": "ord-bot", "side": "buy", "status": "open"},
        {"id": "manual-1", "side": "sell", "status": "open"},
        {"id": "x-2", "clientOrderId": "bot-BTCUSDT-buy-2024", "side": "buy", "status": "open"},
    ]

    orders = broker.open_orders("BTC/USDT")

    assert [(o.id, o.side, o.placed_by_bot) for o in orders] == [
        ("ord-bot", Side.BUY, True), ("manual-1", Side.SELL, False), ("x-2", Side.BUY, True)]
    assert broker.has_open_orders("BTC/USDT") is True
    assert broker.has_open_orders("ETH/USDT") is False


def test_cancel_orders_only_touches_the_given_symbols():
    ex = FakeExchange()
    ex.open_orders = {"BTC/USDT": [{"id": "a"}], "ETH/USDT": [{"id": "c"}]}
    make_broker(ex).cancel_orders(["BTC/USDT"])
    assert [c for c in ex.calls if c[0] == "cancel_order"] == [("cancel_order", "a", "BTC/USDT")]


# ---------------------------------------------------------------------------
# regression: the engine on a real (shared) exchange account
# ---------------------------------------------------------------------------
class _PriceTagStrategy:
    """BUY on bars whose price is above ``buy_above`` (tells symbols apart), else HOLD."""

    name = "price_tag"
    min_bars = 2

    def __init__(self, buy_above: float | None = None, sell: bool = False) -> None:
        self.buy_above = buy_above
        self.sell = sell

    def generate_signal(self, bars, position):
        from bot.models import Action, Signal
        if self.sell and position is not None:
            return Signal(Action.SELL, "scripted sell")
        if self.buy_above is not None and position is None and bars["close"].iloc[-1] > self.buy_above:
            return Signal(Action.BUY, "scripted buy")
        return Signal.hold("scripted hold")


def ccxt_engine(tmp_path, broker, strategy=None, owned: dict | None = None, **risk):
    from datetime import datetime, timezone

    from bot.config import BotConfig, BrokerConfig, NotifyConfig
    from bot.engine import TradingEngine
    from bot.notify import Notifier
    from bot.risk import RiskConfig, RiskManager
    from bot.state import STATE_FILE, BotState, StateStore

    class Recorder(Notifier):
        def __init__(self) -> None:
            super().__init__(NotifyConfig(), mode="live")
            self.errors: list[str] = []

        def error(self, text: str) -> None:
            self.errors.append(text)
            super().error(text)

    store = StateStore(tmp_path / "state" / STATE_FILE)
    if owned:
        store.save(BotState(owned=owned))
    cfg = BotConfig(mode="live", symbols=["BTC/USDT", "ETH/USDT"], timeframe="1h", bars_lookback=5,
                    timezone="UTC", broker=BrokerConfig(type="ccxt", exchange="fakex"), risk=RiskConfig(**risk),
                    state_dir=tmp_path / "state", log_dir=tmp_path / "logs")
    notifier = Recorder()
    clock = lambda: datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)  # noqa: E731
    engine = TradingEngine(cfg, broker, strategy or _PriceTagStrategy(), RiskManager(cfg.risk), store,
                           notifier, clock=clock)
    return engine, notifier


def test_engine_on_a_live_account_leaves_coins_the_user_already_held_alone(tmp_path):
    # A leftover TESTNET entry (BTC at 30,000) sits in the same state folder,
    # and the live account holds the user's own 0.5 BTC, now at 26,000.
    from bot.brokers import ccxt_entries_file
    state = tmp_path / "state"
    state.mkdir()
    (state / ccxt_entries_file("fakex", sandbox=True)).write_text(
        json.dumps({"BTC/USDT": {"qty": 1.0, "avg_entry_price": 30_000.0}}))
    ex = FakeExchange()
    ex.tickers["BTC/USDT"] = {"last": 26_000.0}
    ex.set_balance("BTC", 0.5)
    ex.candles["ETH/USDT"] = hourly_rows(10)
    broker = make_broker(ex, entries_path=state / ccxt_entries_file("fakex", sandbox=False))
    engine, notifier = ccxt_engine(tmp_path, broker, _PriceTagStrategy(sell=True), stop_loss_pct=10.0)

    report = engine.run_once()

    assert order_calls(ex) == [] and report.orders == []
    assert "BTC/USDT" not in broker.entries or broker.entries["BTC/USDT"]["avg_entry_price"] == 26_000.0
    assert any("BTC/USDT" in m and "did not buy" in m for m in notifier.errors)


def test_moving_cash_into_a_coin_outside_symbols_is_not_a_daily_loss(tmp_path):
    ex = FakeExchange()
    ex.set_balance("USDT", 8_000.0)
    ex.set_balance("BTC", 0.1)  # the bot's, 2,000 USDT
    ex.candles["ETH/USDT"] = hourly_rows(10)
    broker = make_broker(ex)
    engine, notifier = ccxt_engine(tmp_path, broker, owned={"BTC/USDT": {"qty": 0.1, "avg_entry_price": 20_000.0}},
                                   max_daily_loss_pct=5.0, flatten_on_daily_loss=True, stop_loss_pct=None)
    assert engine.run_once().halted is False  # day start: 10,000

    ex.set_balance("USDT", 7_000.0)  # the user buys 1,000 USDT of XRP by hand
    ex.set_balance("XRP", 2_000.0)
    report = engine.run_once()

    assert report.halted is False and report.orders == []
    assert order_calls(ex) == []
    assert not any("Daily loss limit" in m for m in notifier.errors)


def test_cash_moved_in_from_another_coin_does_not_hide_a_real_daily_loss(tmp_path):
    ex = FakeExchange()
    ex.set_balance("USDT", 4_000.0)
    ex.set_balance("BTC", 0.3)  # the bot's, 6,000 USDT
    ex.candles["ETH/USDT"] = hourly_rows(10, price=1_000.0)
    broker = make_broker(ex)
    engine, notifier = ccxt_engine(tmp_path, broker, _PriceTagStrategy(buy_above=500.0),
                                   owned={"BTC/USDT": {"qty": 0.3, "avg_entry_price": 20_000.0}},
                                   max_daily_loss_pct=5.0, stop_loss_pct=None, max_open_positions=1)
    assert engine.run_once().halted is False  # day start: 10,000 (ETH not bought: one position max)

    engine.risk.config.max_open_positions = 5
    ex.candles["ETH/USDT"] = hourly_rows(11, price=1_000.0)  # a new ETH bar with a BUY signal
    ex.tickers["BTC/USDT"] = {"last": 18_000.0}  # the bot loses 600 (-6%) ...
    ex.set_balance("USDT", 4_700.0)  # ... while the user sells 700 USDT of another coin
    report = engine.run_once()

    assert report.halted is True
    assert "daily loss limit" in report.signals["ETH/USDT"]
    assert order_calls(ex) == []


# ---- regression: how much of one of the bot's orders filled -------------------------------
def test_order_filled_qty_reads_a_finished_order():
    ex = FakeExchange()
    ex.fetched_order = {"id": "o-1", "status": "canceled", "amount": 0.5, "filled": 0.2}
    broker = make_broker(ex)
    assert broker.order_filled_qty("BTC/USDT", "bot-x", "o-1") == 0.2
    assert ("fetch_order", "o-1", "BTC/USDT") in ex.calls


def test_order_filled_qty_of_a_closed_order_without_fill_details_is_its_amount():
    ex = FakeExchange()
    ex.fetched_order = {"id": "o-1", "status": "closed", "amount": 0.5, "filled": None}
    assert make_broker(ex).order_filled_qty("BTC/USDT", "bot-x", "o-1") == 0.5


def test_order_filled_qty_of_an_order_still_open_is_not_settled_yet():
    ex = FakeExchange()
    ex.fetched_order = {"id": "o-1", "status": "open", "amount": 0.5, "filled": 0.1}
    with pytest.raises(BrokerError, match="still"):
        make_broker(ex).order_filled_qty("BTC/USDT", "bot-x", "o-1")


def test_order_filled_qty_is_unknown_without_an_order_id_or_when_the_lookup_fails():
    ex = FakeExchange()
    broker = make_broker(ex)
    assert broker.order_filled_qty("BTC/USDT", "bot-x", "") is None  # no clientOrderId is sent to exchanges
    ex.fetch_order_error = ccxt.RequestTimeout("timeout")
    assert broker.order_filled_qty("BTC/USDT", "bot-x", "o-1") is None
