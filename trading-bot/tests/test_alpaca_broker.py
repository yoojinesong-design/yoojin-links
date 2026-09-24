"""Offline tests for AlpacaBroker. Vendor clients are MagicMocks; responses are
real alpaca-py model objects so field names are checked against the installed SDK."""
from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest
import requests
from alpaca.common.enums import BaseURL
from alpaca.common.exceptions import APIError
from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.models import BarSet, Trade
from alpaca.data.requests import StockBarsRequest, StockLatestTradeRequest
from alpaca.data.timeframe import TimeFrameUnit
from alpaca.trading.enums import OrderSide, OrderStatus, OrderType, QueryOrderStatus, TimeInForce
from alpaca.trading.models import Asset, Clock, ClosePositionResponse, Order, TradeAccount
from alpaca.trading.models import Position as AlpacaPosition
from alpaca.trading.requests import GetOrdersRequest, MarketOrderRequest

import bot.brokers.alpaca_broker as mod
from bot.brokers.alpaca_broker import AlpacaBroker, lookback_start, map_order_status
from bot.brokers.base import BrokerError
from bot.models import BAR_COLUMNS, OrderRequest, Side

NOW = datetime(2026, 3, 10, 15, 30, tzinfo=timezone.utc)
TS = NOW.isoformat()


# ---- helpers ---------------------------------------------------------------
def make_broker(**kwargs) -> tuple[AlpacaBroker, MagicMock, MagicMock]:
    trading, data = MagicMock(name="trading"), MagicMock(name="data")
    broker = AlpacaBroker("key", "secret", trading_client=trading, data_client=data, **kwargs)
    return broker, trading, data


@pytest.fixture
def fixed_now(monkeypatch):
    monkeypatch.setattr(mod, "utcnow", lambda: NOW)
    return NOW


def api_error(status: int | None, message: str = "boom", code: int = 40010000, body: str | None = None) -> APIError:
    text = body if body is not None else json.dumps({"code": code, "message": message})
    if status is None:
        return APIError(text)
    response = requests.Response()
    response.status_code = status
    return APIError(text, requests.HTTPError(response=response))


def order(status: str = "filled", symbol: str = "AAPL", side: str = "buy", qty: str = "2",
          filled_qty: str = "2", filled_avg_price: str | None = "150.5") -> Order:
    return Order(id=str(uuid.uuid4()), client_order_id="cid", created_at=TS, updated_at=TS,
                 submitted_at=TS, order_class="simple", time_in_force="day", status=status,
                 extended_hours=False, symbol=symbol, qty=qty, filled_qty=filled_qty,
                 filled_avg_price=filled_avg_price, side=side, type="market")


def account(**overrides) -> TradeAccount:
    fields = dict(id=str(uuid.uuid4()), account_number="PA123", status="ACTIVE", currency="USD",
                  equity="10500.25", cash="4000", buying_power="21000", non_marginable_buying_power="3900.5",
                  last_equity="10400", trading_blocked=False, account_blocked=False,
                  trade_suspended_by_user=False)
    fields.update(overrides)
    return TradeAccount(**fields)


def position(symbol: str = "AAPL", qty: str = "3", side: str = "long", avg: str = "100",
             current: str | None = "110", qty_available: str | None = None,
             market_value: str | None = None) -> AlpacaPosition:
    return AlpacaPosition(asset_id=str(uuid.uuid4()), symbol=symbol, exchange="NASDAQ",
                          asset_class="us_equity", avg_entry_price=avg, qty=qty, side=side,
                          cost_basis="300", current_price=current, market_value=market_value,
                          qty_available=qty_available if qty_available is not None else qty)


def asset(symbol: str = "AAPL", fractionable: bool = True) -> Asset:
    return Asset(**{"id": str(uuid.uuid4()), "class": "us_equity", "exchange": "NASDAQ", "symbol": symbol,
                    "status": "active", "tradable": True, "marginable": True, "shortable": True,
                    "easy_to_borrow": True, "fractionable": fractionable})


def raw_bars(n: int, start: str = "2026-01-02T05:00:00Z", step: timedelta = timedelta(days=1)) -> list[dict]:
    t0 = pd.Timestamp(start)
    return [{"t": (t0 + i * step).isoformat(), "o": 10 + i, "h": 11 + i, "l": 9 + i, "c": 10.5 + i,
             "v": 1000 + i, "n": 5, "vw": 10.2 + i} for i in range(n)]


# ---- construction ------------------------------------------------------------
def test_defaults_to_paper_and_iex_feed():
    broker, _, _ = make_broker()
    assert broker.name == "alpaca"
    assert broker.paper is True
    assert broker.data_feed is DataFeed.IEX


@pytest.mark.parametrize("feed, expected", [("sip", DataFeed.SIP), (" IEX ", DataFeed.IEX)])
def test_data_feed_is_case_insensitive(feed, expected):
    broker, _, _ = make_broker(data_feed=feed)
    assert broker.data_feed is expected


def test_unknown_data_feed_raises():
    with pytest.raises(ValueError, match="data feed"):
        make_broker(data_feed="otc")


@pytest.mark.parametrize("key, secret", [("", "s"), ("k", ""), (None, None)])
def test_missing_keys_without_injected_clients_raise(key, secret):
    with pytest.raises(ValueError, match="ALPACA_API_KEY"):
        AlpacaBroker(key, secret)


def test_builds_vendor_clients_with_paper_flag(monkeypatch):
    calls = {}
    monkeypatch.setattr(mod, "TradingClient", lambda *a, **kw: calls.setdefault("trading", (a, kw)))
    monkeypatch.setattr(mod, "StockHistoricalDataClient", lambda *a, **kw: calls.setdefault("data", (a, kw)))
    AlpacaBroker("k", "s", paper=False)
    assert calls["trading"] == (("k", "s"), {"paper": False})
    assert calls["data"] == (("k", "s"), {})


@pytest.mark.parametrize("paper, url", [(True, BaseURL.TRADING_PAPER), (False, BaseURL.TRADING_LIVE)])
def test_real_trading_client_targets_paper_or_live_endpoint(paper, url):
    broker = AlpacaBroker("k", "s", paper=paper)  # constructing a client makes no network calls
    assert broker._trading._base_url == url


# ---- lookback window ---------------------------------------------------------
@pytest.mark.parametrize("limit", [1, 20, 251, 301, 1000, 2500])
def test_daily_lookback_covers_limit_trading_days(limit):
    start = lookback_start("1d", limit, NOW)
    weekdays = len(pd.bdate_range(start.date(), NOW.date()))
    holidays = math.ceil((NOW - start).days / 365 * 10)  # NYSE has ~9-10 holidays a year
    assert weekdays - holidays >= limit


@pytest.mark.parametrize("tf, per_session", [("1m", 390), ("5m", 78), ("15m", 26), ("30m", 13),
                                              ("1h", 6), ("4h", 1)])
@pytest.mark.parametrize("limit", [1, 301, 5000])
def test_intraday_lookback_covers_enough_regular_sessions(tf, per_session, limit):
    start = lookback_start(tf, limit, NOW)
    sessions_needed = math.ceil(limit / per_session)
    weekdays = len(pd.bdate_range(start.date(), NOW.date())) - 1  # today's session may not have started
    holidays = math.ceil((NOW - start).days / 365 * 10) + 1
    assert weekdays - holidays >= sessions_needed


def test_lookback_is_tz_aware_and_before_now():
    start = lookback_start("1h", 10, NOW)
    assert start.tzinfo is not None and start < NOW


def test_lookback_rejects_non_positive_limit():
    with pytest.raises(ValueError):
        lookback_start("1d", 0, NOW)


def test_lookback_caps_absurd_limits_without_overflow():
    start = lookback_start("1d", 10**9, NOW)
    assert start.year >= NOW.year - 51


# ---- get_bars ----------------------------------------------------------------
@pytest.mark.parametrize("tf, amount, unit", [
    ("1m", 1, TimeFrameUnit.Minute), ("5m", 5, TimeFrameUnit.Minute), ("15m", 15, TimeFrameUnit.Minute),
    ("30m", 30, TimeFrameUnit.Minute), ("1h", 1, TimeFrameUnit.Hour), ("4h", 4, TimeFrameUnit.Hour),
    ("1d", 1, TimeFrameUnit.Day),
])
def test_get_bars_builds_exact_request(fixed_now, tf, amount, unit):
    broker, _, data = make_broker(data_feed="sip")
    data.get_stock_bars.return_value = BarSet({"SPY": raw_bars(5)})
    broker.get_bars("SPY", tf, 3)

    (request,), _ = data.get_stock_bars.call_args
    assert type(request) is StockBarsRequest
    assert request.symbol_or_symbols == "SPY"
    assert request.timeframe.amount == amount and request.timeframe.unit == unit
    assert request.feed is DataFeed.SIP
    assert request.adjustment is Adjustment.ALL
    assert request.limit is None and request.end is None  # window + tail, not Alpaca's head-limit
    # alpaca-py stores start as naive UTC
    expected = lookback_start(tf, 3, NOW).replace(tzinfo=None)
    assert request.start == expected


def test_get_bars_converts_barset_to_canonical_tail(fixed_now):
    broker, _, data = make_broker()
    data.get_stock_bars.return_value = BarSet({"AAPL": raw_bars(10)})
    bars = broker.get_bars("AAPL", "1d", 4)

    assert list(bars.columns) == BAR_COLUMNS
    assert all(bars[c].dtype == float for c in BAR_COLUMNS)
    assert isinstance(bars.index, pd.DatetimeIndex) and str(bars.index.tz) == "UTC"
    assert bars.index.is_monotonic_increasing and len(bars) == 4
    assert bars.index[-1] == pd.Timestamp("2026-01-11T05:00:00Z")
    assert bars.iloc[-1].tolist() == [19.0, 20.0, 18.0, 19.5, 1009.0]


def test_get_bars_returns_all_when_fewer_than_limit(fixed_now):
    broker, _, data = make_broker()
    data.get_stock_bars.return_value = BarSet({"AAPL": raw_bars(3)})
    assert len(broker.get_bars("AAPL", "1d", 300)) == 3


def test_get_bars_sorts_and_dedupes(fixed_now):
    broker, _, data = make_broker()
    rows = raw_bars(3)
    data.get_stock_bars.return_value = BarSet({"AAPL": [rows[2], rows[0], rows[1], rows[1]]})
    bars = broker.get_bars("AAPL", "1d", 10)
    assert bars.index.is_monotonic_increasing and bars.index.is_unique and len(bars) == 3


def test_get_bars_accepts_df_only_response_with_multiindex(fixed_now):
    broker, _, data = make_broker()
    df = BarSet({"AAPL": raw_bars(6), "MSFT": raw_bars(2)}).df
    data.get_stock_bars.return_value = SimpleNamespace(df=df)
    bars = broker.get_bars("AAPL", "1d", 5)
    assert list(bars.columns) == BAR_COLUMNS and len(bars) == 5
    assert str(bars.index.tz) == "UTC"
    assert bars["close"].iloc[-1] == 15.5


def test_get_bars_df_without_symbol_raises(fixed_now):
    broker, _, data = make_broker()
    data.get_stock_bars.return_value = SimpleNamespace(df=BarSet({"MSFT": raw_bars(2)}).df)
    with pytest.raises(BrokerError, match="no 1d bars for AAPL"):
        broker.get_bars("AAPL", "1d", 5)


def test_get_bars_accepts_raw_dict_response_and_missing_volume(fixed_now):
    broker, _, data = make_broker()
    rows = [{k: v for k, v in r.items() if k != "v"} for r in raw_bars(3)]
    data.get_stock_bars.return_value = {"AAPL": rows}
    bars = broker.get_bars("AAPL", "1h", 3)
    assert (bars["volume"] == 0.0).all() and len(bars) == 3


@pytest.mark.parametrize("response", [BarSet({}), BarSet({"MSFT": raw_bars(3)}), BarSet({"AAPL": []})])
def test_get_bars_empty_raises_broker_error(fixed_now, response):
    broker, _, data = make_broker()
    data.get_stock_bars.return_value = response
    with pytest.raises(BrokerError, match="no 1d bars"):
        broker.get_bars("AAPL", "1d", 5)


def test_get_bars_nan_price_raises_broker_error(fixed_now):
    broker, _, data = make_broker()
    rows = raw_bars(3)
    rows[1]["c"] = None
    data.get_stock_bars.return_value = {"AAPL": rows}
    with pytest.raises(BrokerError, match="NaN"):
        broker.get_bars("AAPL", "1d", 5)


@pytest.mark.parametrize("exc", [api_error(403, "subscription does not permit querying recent SIP data"),
                                 requests.ConnectionError("dns"), ValueError("bad payload")])
def test_get_bars_wraps_vendor_errors(fixed_now, exc):
    broker, _, data = make_broker()
    data.get_stock_bars.side_effect = exc
    with pytest.raises(BrokerError, match=r"get_bars\(AAPL, 1d\)") as info:
        broker.get_bars("AAPL", "1d", 5)
    assert info.value.__cause__ is exc


def test_get_bars_rejects_crypto_symbol_without_calling_api():
    broker, _, data = make_broker()
    with pytest.raises(BrokerError, match="stocks/ETFs only"):
        broker.get_bars("BTC/USD", "1d", 5)
    data.get_stock_bars.assert_not_called()


def test_get_bars_unsupported_timeframe():
    broker, _, _ = make_broker()
    with pytest.raises(ValueError, match="timeframe"):
        broker.get_bars("AAPL", "2h", 5)


# ---- get_latest_price ----------------------------------------------------------
def test_get_latest_price_request_and_value():
    broker, _, data = make_broker()
    data.get_stock_latest_trade.return_value = {"AAPL": Trade("AAPL", {"t": TS, "p": 187.25, "s": 10})}
    assert broker.get_latest_price("AAPL") == 187.25
    (request,), _ = data.get_stock_latest_trade.call_args
    assert type(request) is StockLatestTradeRequest
    assert request.symbol_or_symbols == "AAPL" and request.feed is DataFeed.IEX


@pytest.mark.parametrize("response", [{}, {"MSFT": Trade("MSFT", {"t": TS, "p": 1.0, "s": 1})},
                                      {"AAPL": Trade("AAPL", {"t": TS, "p": 0.0, "s": 1})},
                                      {"AAPL": {"p": float("nan")}}, None])
def test_get_latest_price_invalid_raises(response):
    broker, _, data = make_broker()
    data.get_stock_latest_trade.return_value = response
    with pytest.raises(BrokerError, match="latest trade price for AAPL"):
        broker.get_latest_price("AAPL")


def test_get_latest_price_wraps_api_error():
    broker, _, data = make_broker()
    data.get_stock_latest_trade.side_effect = api_error(500, "internal")
    with pytest.raises(BrokerError, match="HTTP 500: internal"):
        broker.get_latest_price("AAPL")


# ---- get_account ---------------------------------------------------------------
def test_get_account_uses_non_marginable_buying_power():
    broker, trading, _ = make_broker()
    trading.get_account.return_value = account()
    acct = broker.get_account()
    assert acct.equity == 10500.25 and acct.cash == 4000.0
    assert acct.buying_power == 3900.5  # never the 2x margin buying_power (21000)
    assert acct.day_start_equity == 10400.0
    assert acct.currency == "USD" and acct.trading_blocked is False


def test_get_account_without_last_equity():
    broker, trading, _ = make_broker()
    trading.get_account.return_value = account(last_equity=None, currency=None)
    acct = broker.get_account()
    assert acct.day_start_equity is None and acct.currency == "USD"


@pytest.mark.parametrize("flag", ["trading_blocked", "account_blocked", "trade_suspended_by_user"])
def test_get_account_any_block_flag_blocks_trading(flag):
    broker, trading, _ = make_broker()
    trading.get_account.return_value = account(**{flag: True})
    assert broker.get_account().trading_blocked is True


def test_get_account_missing_block_flags_means_not_blocked():
    broker, trading, _ = make_broker()
    trading.get_account.return_value = account(trading_blocked=None, account_blocked=None,
                                               trade_suspended_by_user=None)
    assert broker.get_account().trading_blocked is False


def test_get_account_without_non_marginable_bp_falls_back_to_cash_not_margin():
    broker, trading, _ = make_broker()
    trading.get_account.return_value = account(non_marginable_buying_power=None)
    assert broker.get_account().buying_power == 4000.0


def test_get_account_negative_buying_power_clamped_to_zero():
    broker, trading, _ = make_broker()
    trading.get_account.return_value = account(non_marginable_buying_power="-12.5")
    assert broker.get_account().buying_power == 0.0


def test_get_account_missing_equity_raises_broker_error():
    broker, trading, _ = make_broker()
    trading.get_account.return_value = account(equity=None)
    with pytest.raises(BrokerError, match="get_account"):
        broker.get_account()


def test_get_account_api_error_with_non_json_body():
    broker, trading, _ = make_broker()
    trading.get_account.side_effect = api_error(401, body="<html>unauthorized</html>")
    with pytest.raises(BrokerError, match="HTTP 401: <html>unauthorized</html>"):
        broker.get_account()


# ---- get_positions ---------------------------------------------------------------
def test_get_positions_maps_long_positions_only():
    broker, trading, _ = make_broker()
    trading.get_all_positions.return_value = [
        position("AAPL", qty="3", avg="100", current="110"),
        position("TSLA", qty="-5", side="short"),
        position("MSFT", qty="0"),
        position("SPY", qty="0.5", avg="400", current=None, market_value="210"),
    ]
    positions = broker.get_positions()
    assert set(positions) == {"AAPL", "SPY"}
    aapl = positions["AAPL"]
    assert (aapl.symbol, aapl.qty, aapl.avg_entry_price, aapl.market_price) == ("AAPL", 3.0, 100.0, 110.0)
    assert positions["SPY"].market_price == 420.0  # market_value / qty when current_price missing


def test_get_positions_empty():
    broker, trading, _ = make_broker()
    trading.get_all_positions.return_value = []
    assert broker.get_positions() == {}


def test_get_positions_wraps_errors():
    broker, trading, _ = make_broker()
    trading.get_all_positions.side_effect = requests.Timeout("slow")
    with pytest.raises(BrokerError, match="get_positions"):
        broker.get_positions()


# ---- submit_order ------------------------------------------------------------------
def test_buy_builds_exact_market_order_request():
    broker, trading, _ = make_broker()
    trading.submit_order.return_value = order("accepted", filled_qty="0", filled_avg_price=None)
    result = broker.submit_order(OrderRequest("AAPL", Side.BUY, 2.5, reason="sma cross", client_order_id="bot-1"))

    (request,), _ = trading.submit_order.call_args
    assert type(request) is MarketOrderRequest
    assert request.symbol == "AAPL" and request.qty == 2.5
    assert request.side is OrderSide.BUY and request.time_in_force is TimeInForce.DAY
    assert request.type is OrderType.MARKET and request.notional is None
    assert request.client_order_id == "bot-1"
    assert not request.extended_hours
    trading.get_open_position.assert_not_called()  # buys don't need a position check
    assert result.status == "accepted" and result.ok and result.side is Side.BUY
    assert result.reason == "sma cross" and result.filled_avg_price is None


def test_buy_filled_result_fields():
    broker, trading, _ = make_broker()
    placed = order("filled", qty="2", filled_qty="2", filled_avg_price="150.5")
    trading.submit_order.return_value = placed
    result = broker.submit_order(OrderRequest("AAPL", Side.BUY, 2))
    assert result.status == "filled" and result.id == str(placed.id)
    assert result.filled_qty == 2.0 and result.filled_avg_price == 150.5 and result.qty == 2.0
    assert result.raw["client_order_id"] == "cid"
    json.dumps(result.raw)  # raw must be JSON-serialisable for logs


@pytest.mark.parametrize("status, expected", [
    ("filled", "filled"), ("rejected", "rejected"), ("canceled", "rejected"), ("expired", "rejected"),
    ("new", "accepted"), ("accepted", "accepted"), ("pending_new", "accepted"),
    ("partially_filled", "accepted"), ("held", "accepted"),
])
def test_order_status_mapping(status, expected):
    broker, trading, _ = make_broker()
    trading.submit_order.return_value = order(status, filled_qty="0", filled_avg_price="0")
    result = broker.submit_order(OrderRequest("AAPL", Side.BUY, 1, reason="r"))
    assert result.status == expected
    assert result.filled_avg_price is None  # Alpaca reports 0 until processed
    if expected == "rejected":
        assert status in result.reason


def test_map_order_status_accepts_enums_and_strings():
    assert map_order_status(OrderStatus.FILLED) == "filled"
    assert map_order_status(OrderStatus.CANCELED) == "rejected"
    assert map_order_status("EXPIRED") == "rejected"
    assert map_order_status(OrderStatus.PARTIALLY_FILLED) == "accepted"
    assert map_order_status(None) == "accepted"


def test_sell_checks_position_and_builds_sell_request():
    broker, trading, _ = make_broker()
    trading.get_open_position.return_value = position("AAPL", qty="3")
    trading.submit_order.return_value = order("filled", side="sell", qty="3", filled_qty="3")
    result = broker.submit_order(OrderRequest("AAPL", Side.SELL, 3, reason="stop_loss"))
    trading.get_open_position.assert_called_once_with("AAPL")
    (request,), _ = trading.submit_order.call_args
    assert request.side is OrderSide.SELL and request.qty == 3.0 and request.time_in_force is TimeInForce.DAY
    assert result.status == "filled" and result.side is Side.SELL


def test_sell_more_than_available_is_capped_never_shorts():
    broker, trading, _ = make_broker()
    trading.get_open_position.return_value = position("AAPL", qty="3", qty_available="1.5")
    trading.submit_order.return_value = order("accepted", side="sell", qty="1.5", filled_qty="0")
    result = broker.submit_order(OrderRequest("AAPL", Side.SELL, 10))
    (request,), _ = trading.submit_order.call_args
    assert request.qty == 1.5 and result.qty == 1.5


def test_selling_a_position_rounded_down_to_1e6_sells_all_of_it():
    """A holding with more than 6 decimals (e.g. bought manually by dollar amount)
    must not leave an unsellable sub-1e-6 remainder behind after a full exit."""
    broker, trading, _ = make_broker()
    trading.get_open_position.return_value = position("AAPL", qty="2.123456789")
    trading.get_asset.return_value = asset("AAPL", fractionable=True)
    trading.submit_order.return_value = order("filled", side="sell", qty="2.123456789", filled_qty="2.123456789")
    qty = broker.normalize_qty("AAPL", 2.123456789)
    assert qty == 2.123456
    broker.submit_order(OrderRequest("AAPL", Side.SELL, qty))
    (request,), _ = trading.submit_order.call_args
    assert request.qty == 2.123456789


def test_partial_sell_is_not_rounded_up_to_the_whole_position():
    broker, trading, _ = make_broker()
    trading.get_open_position.return_value = position("AAPL", qty="3")
    trading.submit_order.return_value = order("filled", side="sell", qty="2.999998", filled_qty="2.999998")
    broker.submit_order(OrderRequest("AAPL", Side.SELL, 2.999998))
    (request,), _ = trading.submit_order.call_args
    assert request.qty == 2.999998


def test_sell_without_position_is_rejected_and_not_sent():
    broker, trading, _ = make_broker()
    trading.get_open_position.side_effect = api_error(404, "position does not exist", code=40410000)
    result = broker.submit_order(OrderRequest("AAPL", Side.SELL, 1))
    assert result.status == "rejected" and "short" in result.reason
    trading.submit_order.assert_not_called()


@pytest.mark.parametrize("pos", [position("AAPL", qty="-2", side="short"),
                                 position("AAPL", qty="2", qty_available="0")])
def test_sell_when_short_or_all_shares_held_is_rejected(pos):
    broker, trading, _ = make_broker()
    trading.get_open_position.return_value = pos
    result = broker.submit_order(OrderRequest("AAPL", Side.SELL, 1))
    assert result.status == "rejected"
    trading.submit_order.assert_not_called()


@pytest.mark.parametrize("exc", [api_error(500, "internal"), requests.ConnectionError("down")])
def test_sell_position_check_failure_raises_and_does_not_send(exc):
    broker, trading, _ = make_broker()
    trading.get_open_position.side_effect = exc
    with pytest.raises(BrokerError, match="get_open_position"):
        broker.submit_order(OrderRequest("AAPL", Side.SELL, 1))
    trading.submit_order.assert_not_called()


@pytest.mark.parametrize("status, message", [(403, "insufficient buying power"),
                                             (422, "qty must be > 0"), (404, "asset not found")])
def test_api_4xx_is_a_rejection_not_an_exception(status, message):
    broker, trading, _ = make_broker()
    trading.submit_order.side_effect = api_error(status, message, code=40310000)
    result = broker.submit_order(OrderRequest("AAPL", Side.BUY, 1))
    assert result.status == "rejected" and not result.ok
    assert message in result.reason and f"HTTP {status}" in result.reason and "40310000" in result.reason
    assert result.id == "" and result.qty == 1.0


def test_api_4xx_with_non_json_body_is_still_a_rejection():
    broker, trading, _ = make_broker()
    trading.submit_order.side_effect = api_error(403, body="forbidden")
    result = broker.submit_order(OrderRequest("AAPL", Side.BUY, 1))
    assert result.status == "rejected" and "forbidden" in result.reason


@pytest.mark.parametrize("exc", [
    api_error(500, "internal"), api_error(503, "unavailable"), api_error(429, "rate limit"),
    api_error(401, "unauthorized"), api_error(None, "no http info"),
    requests.ConnectionError("reset"), requests.Timeout("read timeout"),
])
def test_server_and_transport_errors_raise_broker_error(exc):
    broker, trading, _ = make_broker()
    trading.submit_order.side_effect = exc
    with pytest.raises(BrokerError, match=r"submit_order\(AAPL\)") as info:
        broker.submit_order(OrderRequest("AAPL", Side.BUY, 1))
    assert info.value.__cause__ is exc


@pytest.mark.parametrize("qty", [0, -1, float("nan"), float("inf"), None, 1e-12])
def test_invalid_qty_rejected_without_api_calls(qty):
    broker, trading, _ = make_broker()
    result = broker.submit_order(OrderRequest("AAPL", Side.SELL, qty))
    assert result.status == "rejected"
    trading.submit_order.assert_not_called()
    trading.get_open_position.assert_not_called()


def test_crypto_symbol_order_rejected_without_api_calls():
    broker, trading, _ = make_broker()
    result = broker.submit_order(OrderRequest("BTC/USD", Side.BUY, 1))
    assert result.status == "rejected" and "ccxt" in result.reason
    trading.submit_order.assert_not_called()


def test_invalid_side_rejected():
    broker, trading, _ = make_broker()
    result = broker.submit_order(OrderRequest("AAPL", "short", 1))  # type: ignore[arg-type]
    assert result.status == "rejected"
    trading.submit_order.assert_not_called()


def test_string_side_is_accepted():
    broker, trading, _ = make_broker()
    trading.submit_order.return_value = order("new", filled_qty="0")
    result = broker.submit_order(OrderRequest("AAPL", "buy", 1))  # type: ignore[arg-type]
    assert result.side is Side.BUY and result.status == "accepted"


def test_qty_float_noise_is_rounded_down_not_up():
    broker, trading, _ = make_broker()
    trading.submit_order.return_value = order("new", filled_qty="0")
    broker.submit_order(OrderRequest("AAPL", Side.BUY, 0.1 + 0.2))  # 0.30000000000000004
    broker.submit_order(OrderRequest("AAPL", Side.BUY, 1.0000000019))
    first, second = (c.args[0].qty for c in trading.submit_order.call_args_list)
    assert first == 0.3 and second == 1.000000001


def test_unparseable_order_response_raises_broker_error():
    broker, trading, _ = make_broker()
    trading.submit_order.side_effect = ValueError("validation error for Order")
    with pytest.raises(BrokerError, match="may or may not"):
        broker.submit_order(OrderRequest("AAPL", Side.BUY, 1))


# ---- orders housekeeping -------------------------------------------------------------
def test_cancel_all_orders_calls_cancel_orders():
    broker, trading, _ = make_broker()
    trading.cancel_orders.return_value = []
    broker.cancel_all_orders()
    trading.cancel_orders.assert_called_once_with()


def test_cancel_all_orders_wraps_errors():
    broker, trading, _ = make_broker()
    trading.cancel_orders.side_effect = api_error(500)
    with pytest.raises(BrokerError, match="cancel_all_orders"):
        broker.cancel_all_orders()


@pytest.mark.parametrize("orders, expected", [([], False), (None, False), ([order("new")], True)])
def test_has_open_orders(orders, expected):
    broker, trading, _ = make_broker()
    trading.get_orders.return_value = orders
    assert broker.has_open_orders("AAPL") is expected
    (request,), _ = trading.get_orders.call_args
    assert type(request) is GetOrdersRequest
    assert request.status is QueryOrderStatus.OPEN and request.symbols == ["AAPL"]


def test_has_open_orders_wraps_errors():
    broker, trading, _ = make_broker()
    trading.get_orders.side_effect = requests.ConnectionError("x")
    with pytest.raises(BrokerError, match="has_open_orders"):
        broker.has_open_orders("AAPL")


@pytest.mark.parametrize("is_open", [True, False])
def test_is_market_open_uses_clock(is_open):
    broker, trading, _ = make_broker()
    trading.get_clock.return_value = Clock(timestamp=TS, is_open=is_open, next_open=TS, next_close=TS)
    assert broker.is_market_open() is is_open


def test_is_market_open_wraps_errors():
    broker, trading, _ = make_broker()
    trading.get_clock.side_effect = api_error(502)
    with pytest.raises(BrokerError, match="get_clock"):
        broker.is_market_open()


# ---- market rules ------------------------------------------------------------------
def test_min_order_notional_is_one_dollar():
    broker, _, _ = make_broker()
    assert broker.min_order_notional("AAPL") == 1.0


@pytest.mark.parametrize("qty, expected", [(1.2345679, 1.234567), (0.0000019, 0.000001), (5.0, 5.0),
                                           (0.1 + 0.2, 0.3), (0.0000009, 0.0)])
def test_normalize_qty_fractionable_floors_to_micro_shares(qty, expected):
    broker, trading, _ = make_broker()
    trading.get_asset.return_value = asset(fractionable=True)
    assert broker.normalize_qty("AAPL", qty) == expected


@pytest.mark.parametrize("qty, expected", [(2.99, 2.0), (3.0, 3.0), (0.999, 0.0)])
def test_normalize_qty_non_fractionable_floors_to_whole_shares(qty, expected):
    broker, trading, _ = make_broker()
    trading.get_asset.return_value = asset(fractionable=False)
    assert broker.normalize_qty("BRK.A", qty) == expected


def test_normalize_qty_caches_fractionable_per_symbol():
    broker, trading, _ = make_broker()
    trading.get_asset.side_effect = lambda s: asset(s, fractionable=(s == "AAPL"))
    for _ in range(3):
        assert broker.normalize_qty("AAPL", 1.5) == 1.5
        assert broker.normalize_qty("XYZ", 1.5) == 1.0
    assert [c.args[0] for c in trading.get_asset.call_args_list] == ["AAPL", "XYZ"]


@pytest.mark.parametrize("qty", [0, -3, float("nan"), float("inf"), None])
def test_normalize_qty_invalid_is_zero_without_lookup(qty):
    broker, trading, _ = make_broker()
    assert broker.normalize_qty("AAPL", qty) == 0.0
    trading.get_asset.assert_not_called()


def test_normalize_qty_asset_lookup_failure_raises_and_is_not_cached():
    broker, trading, _ = make_broker()
    trading.get_asset.side_effect = [api_error(503), asset(fractionable=True)]
    with pytest.raises(BrokerError, match=r"get_asset\(AAPL\)"):
        broker.normalize_qty("AAPL", 1.5)
    assert broker.normalize_qty("AAPL", 1.5) == 1.5


# ---- close_all_positions ----------------------------------------------------------------
def test_close_all_positions_maps_responses():
    broker, trading, _ = make_broker()
    ok = order("accepted", symbol="AAPL", side="sell", qty="3", filled_qty="0", filled_avg_price=None)
    trading.close_all_positions.return_value = [
        ClosePositionResponse(order_id=ok.id, status=200, symbol="AAPL", body=ok.model_dump()),
        ClosePositionResponse(status=403, symbol="MSFT",
                              body={"code": 40310000, "message": "insufficient qty available",
                                    "existing_qty": 5, "held_for_orders": 5}),
    ]
    results = broker.close_all_positions()
    trading.close_all_positions.assert_called_once_with(cancel_orders=True)
    first, second = results
    assert (first.symbol, first.side, first.qty, first.status, first.id) == ("AAPL", Side.SELL, 3.0,
                                                                            "accepted", str(ok.id))
    assert first.reason == "flatten"
    assert (second.symbol, second.status, second.qty) == ("MSFT", "rejected", 5.0)
    assert "insufficient qty available" in second.reason


def test_close_all_positions_nothing_to_close():
    broker, trading, _ = make_broker()
    trading.close_all_positions.return_value = []
    assert broker.close_all_positions() == []


def test_close_all_positions_wraps_errors():
    broker, trading, _ = make_broker()
    trading.close_all_positions.side_effect = api_error(500)
    with pytest.raises(BrokerError, match="close_all_positions"):
        broker.close_all_positions()


# ---- symbol guard ------------------------------------------------------------------------
@pytest.mark.parametrize("call", [
    lambda b: b.get_latest_price("ETH/USD"),
    lambda b: b.has_open_orders("ETH/USD"),
    lambda b: b.normalize_qty("ETH/USD", 1.0),
    lambda b: b.get_bars("", "1d", 5),
])
def test_non_stock_symbols_raise_clear_error(call):
    broker, trading, data = make_broker()
    with pytest.raises(BrokerError, match="stocks/ETFs only"):
        call(broker)
    assert not trading.method_calls and not data.method_calls


# ---- wire level: real alpaca-py clients, HTTP session faked ---------------------------
def http_response(status: int, payload: object) -> requests.Response:
    response = requests.Response()
    response.status_code = status
    response._content = json.dumps(payload).encode()
    response.url = "https://example.invalid"
    return response


def order_json(status: str = "filled") -> dict:
    return {"id": str(uuid.uuid4()), "client_order_id": "bot-1", "created_at": TS, "updated_at": TS,
            "submitted_at": TS, "order_class": "simple", "time_in_force": "day", "status": status,
            "extended_hours": False, "symbol": "AAPL", "qty": "2.5", "filled_qty": "2.5",
            "filled_avg_price": "101.25", "side": "buy", "type": "market"}


def real_broker() -> tuple[AlpacaBroker, MagicMock, MagicMock]:
    from alpaca.data.historical.stock import StockHistoricalDataClient
    from alpaca.trading.client import TradingClient

    trading, data = TradingClient("k", "s", paper=True), StockHistoricalDataClient("k", "s")
    trading._session, data._session = MagicMock(name="trading_http"), MagicMock(name="data_http")
    return AlpacaBroker("k", "s", trading_client=trading, data_client=data), trading._session, data._session


def test_wire_market_order_payload_and_parsed_fill():
    broker, http, _ = real_broker()
    http.request.return_value = http_response(200, order_json("filled"))
    result = broker.submit_order(OrderRequest("AAPL", Side.BUY, 2.5, client_order_id="bot-1"))
    method, url = http.request.call_args.args
    assert method == "POST" and url.endswith("/v2/orders") and "paper-api" in url
    assert http.request.call_args.kwargs["json"] == {
        "symbol": "AAPL", "qty": 2.5, "side": "buy", "type": "market",
        "time_in_force": "day", "client_order_id": "bot-1"}
    assert (result.status, result.filled_qty, result.filled_avg_price) == ("filled", 2.5, 101.25)


def test_wire_http_403_is_rejection_and_500_is_broker_error():
    broker, http, _ = real_broker()
    http.request.return_value = http_response(403, {"code": 40310000, "message": "insufficient buying power"})
    result = broker.submit_order(OrderRequest("AAPL", Side.BUY, 1))
    assert result.status == "rejected" and "HTTP 403: insufficient buying power" in result.reason

    http.request.return_value = http_response(500, {"code": 50010000, "message": "internal server error"})
    with pytest.raises(BrokerError, match="HTTP 500"):
        broker.submit_order(OrderRequest("AAPL", Side.BUY, 1))


def test_wire_sell_without_position_never_posts_an_order():
    broker, http, _ = real_broker()
    http.request.return_value = http_response(404, {"code": 40410000, "message": "position does not exist"})
    result = broker.submit_order(OrderRequest("AAPL", Side.SELL, 1))
    assert result.status == "rejected"
    assert [c.args[0] for c in http.request.call_args_list] == ["GET"]


def test_wire_open_orders_query_params():
    broker, http, _ = real_broker()
    http.request.return_value = http_response(200, [])
    assert broker.has_open_orders("AAPL") is False
    method, url = http.request.call_args.args
    assert method == "GET" and url.endswith("/v2/orders")
    assert http.request.call_args.kwargs["params"] == {"status": "open", "symbols": "AAPL"}


def test_wire_close_all_positions_cancels_orders_first():
    broker, http, _ = real_broker()
    http.request.return_value = http_response(207, [])
    assert broker.close_all_positions() == []
    method, url = http.request.call_args.args
    assert method == "DELETE" and url.endswith("/v2/positions")
    assert http.request.call_args.kwargs["params"] == {"cancel_orders": True}


def test_wire_bars_query_and_conversion(fixed_now):
    broker, _, http = real_broker()
    http.request.return_value = http_response(200, {"bars": {"AAPL": raw_bars(8)}, "next_page_token": None})
    bars = broker.get_bars("AAPL", "1d", 5)
    method, url = http.request.call_args.args
    params = http.request.call_args.kwargs["params"]
    assert method == "GET" and url.endswith("/v2/stocks/bars")
    assert params["symbols"] == "AAPL" and str(params["timeframe"]) == "1Day"
    assert params["feed"] == "iex" and params["adjustment"] == "all"
    assert params["start"] == lookback_start("1d", 5, NOW).isoformat()
    assert len(bars) == 5 and str(bars.index.tz) == "UTC" and list(bars.columns) == BAR_COLUMNS


def test_wire_latest_trade(fixed_now):
    broker, _, http = real_broker()
    http.request.return_value = http_response(200, {"trades": {"AAPL": {"t": TS, "p": 99.5, "s": 3}}})
    assert broker.get_latest_price("AAPL") == 99.5
    assert http.request.call_args.kwargs["params"]["feed"] == "iex"
