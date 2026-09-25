"""Offline tests for AlpacaBroker. Vendor clients are MagicMocks; responses are
real alpaca-py model objects so field names are checked against the installed SDK."""
from __future__ import annotations

import json
import math
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

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
    ("30m", 30, TimeFrameUnit.Minute), ("1d", 1, TimeFrameUnit.Day),
    # Built from 30-minute bars, so that the first bar of a session holds no pre-market trades.
    ("1h", 30, TimeFrameUnit.Minute), ("4h", 30, TimeFrameUnit.Minute),
])
def test_get_bars_builds_exact_request(fixed_now, tf, amount, unit):
    broker, _, data = make_broker(data_feed="sip")
    # Weekdays at 10:00 New York time: inside the regular session for every timeframe.
    data.get_stock_bars.return_value = BarSet({"SPY": raw_bars(5, start="2026-01-05T15:00:00Z")})
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
    rows = [{k: v for k, v in r.items() if k != "v"} for r in raw_bars(3, start="2026-01-05T15:00:00Z")]
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


def test_an_option_position_is_valued_per_contract_not_per_share():
    # 10 contracts bought at $5.00 a share cost 5,000 (x100): valued per share,
    # buying them by hand would look like 4,950 withdrawn from the account.
    broker, trading, _ = make_broker()
    option = position("SPY260320C00600000", qty="10", avg="5", current="4").model_copy(
        update={"asset_class": "us_option", "market_value": "4000", "cost_basis": "5000"})
    trading.get_all_positions.return_value = [option]
    held = broker.get_positions()["SPY260320C00600000"]
    assert (held.avg_entry_price, held.market_price, held.market_value) == (500.0, 400.0, 4_000.0)


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
    with pytest.raises(BrokerError, match="get_orders"):
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


# ---- regression: HTTP timeouts -------------------------------------------------------
import socket  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402


@pytest.fixture
def silent_server():
    """A local TCP server that accepts connections and never answers."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(16)
    held: list[socket.socket] = []
    stop = threading.Event()

    def accept() -> None:
        server.settimeout(0.1)
        while not stop.is_set():
            try:
                conn, _ = server.accept()
            except OSError:
                continue
            held.append(conn)

    thread = threading.Thread(target=accept, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.getsockname()[1]}"
    stop.set()
    thread.join(timeout=2)
    for conn in held:
        conn.close()
    server.close()


def _call_with_deadline(fn, deadline: float) -> tuple[bool, BaseException | None, float]:
    """Run ``fn`` in a daemon thread: (finished in time, exception raised, seconds taken)."""
    outcome: dict[str, BaseException] = {}

    def target() -> None:
        try:
            fn()
        except BaseException as exc:  # noqa: BLE001 - reported to the test
            outcome["error"] = exc

    started = time.monotonic()
    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(deadline)
    return not thread.is_alive(), outcome.get("error"), time.monotonic() - started


def test_stalled_http_connection_times_out_as_broker_error(monkeypatch, silent_server):
    monkeypatch.setattr(mod, "HTTP_TIMEOUT", (1.0, 1.0))
    broker = AlpacaBroker("k", "s", paper=True)  # the real vendor clients, as make_broker builds them
    broker._trading._base_url = silent_server
    broker._data._base_url = silent_server

    for call in (broker.get_account, lambda: broker.get_bars("SPY", "1d", 5)):
        finished, error, took = _call_with_deadline(call, deadline=8.0)
        assert finished, "the call hung on a connection that never answers"
        assert isinstance(error, BrokerError) and "Timeout" in str(error)
        assert took < 5.0


def test_timeout_is_installed_on_both_vendor_sessions():
    broker = AlpacaBroker("k", "s", paper=True)
    for client in (broker._trading, broker._data):
        adapter = client._session.get_adapter("https://paper-api.alpaca.markets")
        assert getattr(adapter, "timeout", None) == mod.HTTP_TIMEOUT


# ---- regression: open orders / per-symbol cancel ----------------------------------------
def _order_with_client_id(client_order_id: str, side: str = "buy") -> Order:
    placed = order("new", side=side)
    return placed.model_copy(update={"client_order_id": client_order_id})


def test_open_orders_tell_the_bots_own_orders_from_manual_ones():
    broker, trading, _ = make_broker()
    trading.get_orders.return_value = [_order_with_client_id("bot-AAPL-buy-202603101300-ab12cd34"),
                                       _order_with_client_id("web-123", side="sell")]
    orders = broker.open_orders("AAPL")
    assert [(o.side, o.placed_by_bot) for o in orders] == [(Side.BUY, True), (Side.SELL, False)]
    (request,), _ = trading.get_orders.call_args
    assert request.status is QueryOrderStatus.OPEN and request.symbols == ["AAPL"]


def test_cancel_orders_cancels_only_the_given_symbols_orders():
    broker, trading, _ = make_broker()
    first, second = order("new", symbol="SPY"), order("new", symbol="QQQ")
    trading.get_orders.return_value = [first, second]
    broker.cancel_orders(["SPY", "QQQ"])
    (request,), _ = trading.get_orders.call_args
    assert request.status is QueryOrderStatus.OPEN and request.symbols == ["SPY", "QQQ"]
    assert [c.args[0] for c in trading.cancel_order_by_id.call_args_list] == [first.id, second.id]
    trading.cancel_orders.assert_not_called()  # never the account-wide cancel


def test_cancel_orders_with_no_symbols_does_nothing():
    broker, trading, _ = make_broker()
    broker.cancel_orders([])
    assert not trading.method_calls


# ---- regression: regular-session intraday bars ------------------------------------------
def test_intraday_bars_keep_only_the_regular_session(fixed_now):
    # 30m IEX/SIP-like bars from 04:00 to 19:30 New York time on two days (EDT, UTC-4).
    rows = raw_bars(32, start="2026-03-09T08:00:00Z", step=timedelta(minutes=30)) + \
        raw_bars(32, start="2026-03-10T08:00:00Z", step=timedelta(minutes=30))
    broker, _, data = make_broker()
    data.get_stock_bars.return_value = {"AAPL": rows}

    bars = broker.get_bars("AAPL", "1h", 100)

    new_york = bars.index.tz_convert("America/New_York")
    assert len(bars) == 14  # 09:00 (only its 09:30-10:00 half) .. 15:00, twice
    assert all(9 <= t.hour <= 15 for t in new_york)
    assert all(t.minute == 0 for t in new_york)


def session_rows(day: str, bars_30m: list[tuple[str, float, float, float, float, float]]) -> list[dict]:
    """Raw 30m bars on ``day``: (New York start time, o, h, l, c, v)."""
    rows = []
    for start, o, h, low, c, v in bars_30m:
        t = pd.Timestamp(f"{day} {start}", tz="America/New_York").tz_convert("UTC")
        rows.append({"t": t.isoformat(), "o": o, "h": h, "l": low, "c": c, "v": v})
    return rows


def test_the_first_hourly_bar_of_a_session_holds_no_pre_market_trades(fixed_now):
    # Pre-market trades at 500 with a dip to 494; the session opens at 503.
    rows = session_rows("2026-03-09", [
        ("09:00", 500, 501, 494, 502, 100),        # pre-market
        ("09:30", 503, 504, 502.5, 503.5, 1000),
        ("10:00", 503.5, 506, 503, 505, 900),
        ("10:30", 505, 505.5, 501, 502, 800),
    ])
    broker, _, data = make_broker()
    data.get_stock_bars.return_value = {"AAPL": rows}

    bars = broker.get_bars("AAPL", "1h", 10)

    assert list(bars.index.tz_convert("America/New_York").strftime("%H:%M")) == ["09:00", "10:00"]
    assert tuple(bars.iloc[0]) == (503, 504, 502.5, 503.5, 1000)  # the 09:30-10:00 half only
    assert tuple(bars.iloc[1]) == (503.5, 506, 501, 502, 1700)


def test_four_hour_bars_are_built_from_the_regular_session_in_new_york_time(fixed_now):
    # Across the DST change (March 8, 2026) the bars still start at 08:00 and
    # 12:00 New York time (09:30-12:00 and 12:00-16:00).
    rows = []
    for day in ("2026-03-06", "2026-03-09"):
        rows += session_rows(day, [(f"{h:02d}:{m:02d}", 100 + h, 101 + h, 99 + h, 100.5 + h, 10)
                                   for h in range(7, 18) for m in (0, 30)])
    broker, _, data = make_broker()
    data.get_stock_bars.return_value = {"AAPL": rows}

    bars = broker.get_bars("AAPL", "4h", 10)

    local = bars.index.tz_convert("America/New_York")
    assert list(local.strftime("%m-%d %H:%M")) == ["03-06 08:00", "03-06 12:00", "03-09 08:00", "03-09 12:00"]
    first = bars.iloc[0]
    assert (first.open, first.high, first.low, first.volume) == (109, 112, 108, 50)  # 09:30 .. 11:30


def test_a_backtest_on_hourly_bars_fills_an_overnight_order_at_the_regular_open(fixed_now):
    from bot.backtest import BacktestConfig, run_backtest
    from bot.models import Action, Signal
    from bot.risk import RiskConfig

    rows = session_rows("2026-03-05", [(f"{h:02d}:{m:02d}", 490, 491, 489, 490, 10)
                                       for h in range(9, 16) for m in (0, 30)])
    rows += session_rows("2026-03-06", [("09:00", 500, 501, 494, 502, 100), ("09:30", 503, 504, 502.5, 503.5, 10),
                                        ("10:00", 503.5, 504, 503, 503.5, 10)])
    broker, _, data = make_broker()
    data.get_stock_bars.return_value = {"AAPL": rows}
    bars = broker.get_bars("AAPL", "1h", 100)

    class BuyAtTheLastBarOfTheDay:
        name, min_bars = "buy_late", 1

        def generate_signal(self, window, position):
            late = window.index[-1].tz_convert("America/New_York").hour == 15
            return Signal(Action.BUY if late and position is None else Action.HOLD, "late")

    cfg = BacktestConfig(fee_pct=0.0, slippage_pct=0.0, timeframe="1h", lookback=50,
                         risk=RiskConfig(stop_loss_pct=1.0, max_daily_loss_pct=None))
    trades = run_backtest(BuyAtTheLastBarOfTheDay(), {"AAPL": bars}, cfg).trades
    (trade,) = trades
    assert trade.entry_price == 503  # the 09:30 open, not the 09:00 pre-market price
    assert trade.exit_reason == "end_of_backtest"  # the pre-market dip to 494 is not a stop-out


def test_daily_bars_are_not_session_filtered(fixed_now):
    broker, _, data = make_broker()
    data.get_stock_bars.return_value = {"AAPL": raw_bars(8)}
    assert len(broker.get_bars("AAPL", "1d", 8)) == 8


# ---- regression: a retried order whose first attempt went through ----------------------
def test_duplicate_client_order_id_after_a_retried_504_returns_the_placed_order(monkeypatch):
    import alpaca.common.rest as rest

    monkeypatch.setattr(rest.time, "sleep", lambda seconds: None)
    broker, http, _ = real_broker()
    placed = order_json("filled")
    http.request.side_effect = [
        http_response(504, {"message": "gateway timeout"}),
        http_response(422, {"code": 40010001, "message": "client_order_id must be unique"}),
        http_response(200, placed),
    ]

    result = broker.submit_order(OrderRequest("AAPL", Side.BUY, 2.5, client_order_id="bot-1"))

    assert (result.status, result.id, result.filled_qty) == ("filled", placed["id"], 2.5)
    method, url = http.request.call_args.args
    assert method == "GET" and url.endswith("/v2/orders:by_client_order_id")
    assert http.request.call_args.kwargs["params"] == {"client_order_id": "bot-1"}


def test_duplicate_client_order_id_that_cannot_be_looked_up_is_a_broker_error(monkeypatch):
    import alpaca.common.rest as rest

    monkeypatch.setattr(rest.time, "sleep", lambda seconds: None)
    broker, http, _ = real_broker()
    http.request.side_effect = [
        http_response(422, {"code": 40010001, "message": "client_order_id must be unique"}),
        http_response(500, {"message": "internal error"}),
    ]
    with pytest.raises(BrokerError, match="may have been placed"):
        broker.submit_order(OrderRequest("AAPL", Side.BUY, 2.5, client_order_id="bot-1"))


# ---- regression: the real adapter under the trading engine --------------------------------
class _Strategy:
    """Minimal strategy: the same scripted action on every bar."""

    name = "scripted"
    min_bars = 2

    def __init__(self, action: str = "hold") -> None:
        from bot.models import Action
        self.action = Action(action)

    def generate_signal(self, bars, position):
        from bot.models import Signal
        return Signal(self.action, f"scripted {self.action.value}")


def alpaca_engine(tmp_path, broker, strategy=None, clock_now: datetime = NOW, symbols=("SPY", "QQQ"), **risk):
    from bot.config import BotConfig, BrokerConfig, NotifyConfig
    from bot.engine import TradingEngine
    from bot.notify import Notifier
    from bot.risk import RiskConfig, RiskManager
    from bot.state import STATE_FILE, StateStore

    class Recorder(Notifier):
        def __init__(self) -> None:
            super().__init__(NotifyConfig(), mode="live")
            self.errors: list[str] = []

        def error(self, text: str) -> None:
            self.errors.append(text)
            super().error(text)

    cfg = BotConfig(mode="live", broker=BrokerConfig(type="alpaca"), symbols=list(symbols), timeframe="1d",
                    bars_lookback=10, timezone="America/New_York", risk=RiskConfig(**risk),
                    state_dir=tmp_path / "state", log_dir=tmp_path / "logs")
    notifier = Recorder()
    engine = TradingEngine(cfg, broker, strategy or _Strategy(), RiskManager(cfg.risk),
                           StateStore(cfg.state_dir / STATE_FILE), notifier, clock=lambda: clock_now)
    return engine, notifier


def open_market(trading, data, positions, spy_price: float = 560.0, **acct):
    trading.get_clock.return_value = SimpleNamespace(is_open=True)
    trading.get_account.return_value = account(**acct)
    trading.get_all_positions.return_value = positions
    trading.get_orders.return_value = []
    trading.get_asset.return_value = asset("SPY")
    data.get_stock_latest_trade.return_value = {"SPY": {"p": spy_price}, "QQQ": {"p": 480.0}}
    data.get_stock_bars.return_value = {"SPY": raw_bars(30, start="2026-02-01T05:00:00Z"),
                                        "QQQ": raw_bars(30, start="2026-02-01T05:00:00Z")}


def test_engine_never_sells_spy_the_account_held_before_the_bot_started(tmp_path):
    # configs/stocks.yaml switched to live on an account that has held 100 SPY
    # (average $250) for years. Strategy SELL: the bot must not sell them.
    broker, trading, data = make_broker(paper=False)
    open_market(trading, data, [position("SPY", qty="100", avg="250", current="560")],
                equity="66000", cash="10000", last_equity="66000")
    engine, notifier = alpaca_engine(tmp_path, broker, _Strategy("sell"), stop_loss_pct=8.0, take_profit_pct=20.0)

    report = engine.run_once()

    trading.submit_order.assert_not_called()
    assert report.orders == [] and report.errors == []
    assert any("SPY" in m and "no record of buying" in m for m in notifier.errors)  # its first run


def test_stop_loss_uses_the_positions_price_when_the_market_data_api_is_down(tmp_path):
    # The trading API still reports SPY at 80 (bought at 100, 8% stop), but
    # Alpaca's market-data service answers 503.
    from bot.state import STATE_FILE, BotState, StateStore
    broker, trading, data = make_broker(paper=False)
    open_market(trading, data, [position("SPY", qty="10", avg="100", current="80")],
                equity="10000", cash="9200", last_equity="10000")
    data.get_stock_latest_trade.side_effect = api_error(503, "service unavailable", code=50300000)
    trading.get_open_position.return_value = position("SPY", qty="10", avg="100", current="80")
    trading.submit_order.return_value = order("accepted", symbol="SPY", side="sell", qty="10", filled_qty="0",
                                              filled_avg_price=None)
    StateStore(tmp_path / "state" / STATE_FILE).save(
        BotState(owned={"SPY": {"qty": 10.0, "avg_entry_price": 100.0}}))
    engine, _ = alpaca_engine(tmp_path, broker, stop_loss_pct=8.0)

    report = engine.run_once()

    (request,), _ = trading.submit_order.call_args
    assert request.symbol == "SPY" and request.side is OrderSide.SELL and request.qty == 10.0
    assert any(e.startswith("SPY:") and "503" in e for e in report.errors)


def test_a_withdrawal_is_not_counted_as_a_daily_loss(tmp_path):
    # $1,000 withdrawn in the middle of the day; the positions are unchanged.
    broker, trading, data = make_broker(paper=False)
    positions = [position("SPY", qty="10", avg="560", current="560")]
    open_market(trading, data, positions, equity="10000", cash="4400", last_equity="10000")
    engine, notifier = alpaca_engine(tmp_path, broker, max_daily_loss_pct=3.0, stop_loss_pct=None)
    assert engine.run_once().halted is False

    trading.get_account.return_value = account(equity="9000", cash="3400", last_equity="10000")
    report = engine.run_once()

    assert report.halted is False
    assert not any("Daily loss limit" in m for m in notifier.errors)

    # A real loss on top of it still counts: SPY -10% is -$560 = -6.2% of the $9,000 left.
    trading.get_account.return_value = account(equity="8440", cash="3400", last_equity="10000")
    trading.get_all_positions.return_value = [position("SPY", qty="10", avg="560", current="504")]
    assert engine.run_once().halted is True


# ---- regression: a stateful Alpaca account behind the real adapter and the engine ---------
class FakeAlpaca:
    """A stateful Alpaca account (trading and market-data client in one)
    behind the REAL adapter. Market orders are acknowledged "accepted" and
    fill only when ``fill()`` runs. Responses are real alpaca-py models."""

    def __init__(self, prices: dict[str, float], cash: float, positions: dict[str, float] | None = None,
                 last_equity: float | None = None) -> None:
        self.prices = dict(prices)
        self.cash = cash
        self.qty = dict(positions or {})  # symbol -> signed quantity (< 0: short)
        self.entry = {symbol: self.prices[symbol] for symbol in self.qty}
        self.orders: list[dict] = []
        self.last_equity = last_equity
        self.cancelled: list[str] = []
        self.after_next_account_read = None  # runs once, right after the next get_account
        self.on_next_order = None            # runs once, right after the next submit_order

    # -- trading API
    def get_account(self) -> TradeAccount:
        held = sum(q * self.prices[s] for s, q in self.qty.items())
        acct = account(equity=str(self.cash + held), cash=str(self.cash), buying_power=str(self.cash),
                       non_marginable_buying_power=str(max(0.0, self.cash)),
                       last_equity=str(self.last_equity if self.last_equity is not None else self.cash + held))
        hook, self.after_next_account_read = self.after_next_account_read, None
        if hook:
            hook()
        return acct

    def get_all_positions(self) -> list[AlpacaPosition]:
        return [self._position(s) for s, q in self.qty.items() if q]

    def get_open_position(self, symbol: str) -> AlpacaPosition:
        if not self.qty.get(symbol):
            raise api_error(404, "position does not exist", code=40410000)
        return self._position(symbol)

    def submit_order(self, request: MarketOrderRequest) -> Order:
        placed = dict(id=str(uuid.uuid4()), symbol=request.symbol, side=request.side.value, qty=float(request.qty),
                      client_order_id=request.client_order_id, status="accepted")
        self.orders.append(placed)
        hook, self.on_next_order = self.on_next_order, None
        if hook:
            hook()
        return self._order({**placed, "status": "accepted"})

    def get_orders(self, request: GetOrdersRequest) -> list[Order]:
        if request.status is QueryOrderStatus.ALL:  # the latest orders of any status, newest first
            return [self._order(o) for o in reversed(self.orders)][:request.limit]
        return [self._order(o) for o in self.working() if not request.symbols or o["symbol"] in request.symbols]

    def get_order_by_id(self, order_id: str) -> Order:
        return self._order(self._find("id", str(order_id)))

    def get_order_by_client_id(self, client_order_id: str) -> Order:
        return self._order(self._find("client_order_id", client_order_id))

    def cancel_order_by_id(self, order_id: str) -> None:
        placed = next(o for o in self.orders if o["id"] == str(order_id))
        if placed["status"] not in ("accepted", "new"):
            raise api_error(422, "order is not cancelable", code=42210000)
        placed["status"] = "canceled"
        self.cancelled.append(str(order_id))

    def get_clock(self) -> SimpleNamespace:
        return SimpleNamespace(is_open=True)

    def get_asset(self, symbol: str) -> Asset:
        return asset(symbol, fractionable=False)

    # -- market-data API
    def get_stock_bars(self, request: StockBarsRequest) -> dict:
        return {request.symbol_or_symbols: raw_bars(30, start="2026-02-01T05:00:00Z")}

    def get_stock_latest_trade(self, request: StockLatestTradeRequest) -> dict:
        return {request.symbol_or_symbols: {"p": self.prices[request.symbol_or_symbols]}}

    # -- test controls
    def place_user_order(self, symbol: str, side: str, qty: float, client_order_id: str) -> str:
        placed = dict(id=str(uuid.uuid4()), symbol=symbol, side=side, qty=qty, client_order_id=client_order_id,
                      status="new")
        self.orders.append(placed)
        return placed["id"]

    def working(self, symbol: str | None = None) -> list[dict]:
        return [o for o in self.orders if o["status"] in ("accepted", "new") and symbol in (None, o["symbol"])]

    def fill(self) -> None:
        """The bot's working orders fill at the current price."""
        for o in self.working():
            if not o["client_order_id"].startswith("bot-"):
                continue
            symbol, qty, price = o["symbol"], o["qty"], self.prices[o["symbol"]]
            held = self.qty.get(symbol, 0.0)
            if o["side"] == "buy":
                self.entry[symbol] = (max(held, 0.0) * self.entry.get(symbol, price) + qty * price) / (
                    max(held, 0.0) + qty)
                self.qty[symbol], self.cash = held + qty, self.cash - qty * price
            else:
                self.qty[symbol], self.cash = held - qty, self.cash + qty * price
            o["status"], o["filled"] = "filled", qty

    def _position(self, symbol: str) -> AlpacaPosition:
        q = self.qty[symbol]
        locked = sum(o["qty"] for o in self.working(symbol) if o["side"] == "sell")
        return position(symbol, qty=str(q), side="long" if q > 0 else "short", avg=str(self.entry[symbol]),
                        current=str(self.prices[symbol]), qty_available=str(q - locked if q > 0 else q))

    def _find(self, key: str, value: str) -> dict:
        placed = next((o for o in self.orders if o[key] == value), None)
        if placed is None:
            raise api_error(404, "order not found", code=40410000)
        return placed

    def _order(self, o: dict) -> Order:
        placed = order(o["status"], symbol=o["symbol"], side=o["side"], qty=str(o["qty"]),
                       filled_qty=str(o.get("filled", 0.0)), filled_avg_price=None)
        return placed.model_copy(update={"id": uuid.UUID(o["id"]), "client_order_id": o["client_order_id"]})


def fake_alpaca_engine(tmp_path, fake: FakeAlpaca, action: str = "hold", symbols=("SPY",),
                       owned: dict[str, float] | None = None, **risk):
    from bot.state import STATE_FILE, BotState, StateStore

    store = StateStore(tmp_path / "state" / STATE_FILE)
    if owned:
        store.save(BotState(owned={s: {"qty": q, "avg_entry_price": 100.0} for s, q in owned.items()}))
    broker = AlpacaBroker("k", "s", trading_client=fake, data_client=fake)
    engine, notifier = alpaca_engine(tmp_path, broker, _Strategy(action), symbols=symbols, **risk)
    return engine, notifier, store


_LOSS_LIMIT = dict(stop_loss_pct=None, max_position_pct=30.0, max_daily_loss_pct=3.0, flatten_on_daily_loss=True)


def test_a_buy_filling_between_the_account_and_positions_reads_is_not_money_moved_in_or_out(tmp_path):
    fake = FakeAlpaca({"SPY": 100.0}, cash=10_000.0, last_equity=10_000.0)
    engine, notifier, store = fake_alpaca_engine(tmp_path, fake, "buy", **_LOSS_LIMIT)
    fake.on_next_order = lambda: setattr(fake, "after_next_account_read", fake.fill)

    first = engine.run_once()  # buys 30 SPY; it fills between the re-read of the account and of the positions
    assert [(o.symbol, o.qty, o.status) for o in first.orders] == [("SPY", 30.0, "accepted")]
    assert fake.qty["SPY"] == 30.0
    for _ in range(2):
        assert engine.run_once().halted is False
    assert store.load().external_flow == 0.0

    fake.prices["SPY"] = 80.0  # -600 = -6% of the account, twice the 3% limit
    assert engine.run_once().halted is True
    assert any("Daily loss limit hit" in m for m in notifier.errors)


def test_a_sell_filling_between_the_account_and_positions_reads_is_not_a_false_daily_loss(tmp_path):
    fake = FakeAlpaca({"SPY": 100.0}, cash=7_000.0, positions={"SPY": 30.0}, last_equity=10_000.0)
    engine, notifier, store = fake_alpaca_engine(tmp_path, fake, "sell", owned={"SPY": 30.0}, **_LOSS_LIMIT)
    fake.on_next_order = lambda: setattr(fake, "after_next_account_read", fake.fill)

    first = engine.run_once()
    assert [(o.symbol, o.side, o.qty) for o in first.orders] == [("SPY", Side.SELL, 30.0)]
    for _ in range(2):
        report = engine.run_once()
        assert report.halted is False and report.orders == []
    assert store.load().external_flow == 0.0
    assert not any("Daily loss limit" in m for m in notifier.errors)


def test_a_failed_positions_read_after_a_buy_is_not_money_moved_in_or_out(tmp_path):
    fake = FakeAlpaca({"SPY": 100.0}, cash=10_000.0, last_equity=10_000.0)
    engine, notifier, store = fake_alpaca_engine(tmp_path, fake, "buy", **_LOSS_LIMIT)
    real_positions = fake.get_all_positions

    def fill_then_fail_positions_read() -> None:
        fake.fill()

        def unavailable():
            fake.get_all_positions = real_positions
            raise api_error(503, "service unavailable", code=50300000)
        fake.get_all_positions = unavailable

    fake.on_next_order = fill_then_fail_positions_read
    first = engine.run_once()
    assert any("could not refresh" in e for e in first.errors)

    for _ in range(2):
        report = engine.run_once()
        assert report.halted is False and report.orders == []  # no false halt, no flatten of the new position
    assert store.load().external_flow == 0.0
    assert fake.qty["SPY"] == 30.0
    assert not any("Daily loss limit" in m for m in notifier.errors)


def test_daily_loss_flatten_cancels_only_the_bots_own_orders(tmp_path):
    # 130 SPY: 30 the bot bought, 100 the user's with their own working stop
    # order. The user also has an order working on QQQ, where the bot has a
    # working BUY of its own.
    fake = FakeAlpaca({"SPY": 100.0, "QQQ": 400.0}, cash=10_000.0, positions={"SPY": 130.0},
                      last_equity=23_000.0)
    user_stop = fake.place_user_order("SPY", "sell", 100.0, "my-own-stop")
    user_qqq = fake.place_user_order("QQQ", "buy", 5.0, "web-qqq-limit")
    bot_qqq = fake.place_user_order("QQQ", "buy", 2.0, "bot-QQQ-buy-202603090500-ab12cd34")
    engine, notifier, _ = fake_alpaca_engine(tmp_path, fake, symbols=("SPY", "QQQ"), owned={"SPY": 30.0},
                                             **_LOSS_LIMIT)
    fake.prices["SPY"] = 90.0  # equity 21,700: -5.7% vs 23,000

    report = engine.run_once()

    assert report.halted is True
    assert fake.cancelled == [bot_qqq]
    assert [o["id"] for o in fake.working() if not o["client_order_id"].startswith("bot-")] == [user_stop, user_qqq]
    assert [(o.symbol, o.side, o.qty) for o in report.orders] == [("SPY", Side.SELL, 30.0)]


def test_the_trading_day_is_new_yorks_whatever_the_configured_timezone(tmp_path):
    # last_equity is the previous New York close: a Seoul day would roll mid-session.
    fake = FakeAlpaca({"SPY": 100.0}, cash=10_000.0, last_equity=10_000.0)
    engine, _, store = fake_alpaca_engine(tmp_path, fake)
    engine.cfg = replace(engine.cfg, timezone="Asia/Seoul")
    engine.run_once()  # NOW is 11:30 New York on 2026-03-10, already 00:30 on the 11th in Seoul
    assert NOW.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat() == "2026-03-11"
    assert store.load().day == "2026-03-10"


def test_a_sale_the_bot_did_not_make_between_two_ticks_is_a_loss_not_money_taken_out(tmp_path):
    # The user's own 200 SPY are sold by their stop at 95 between two ticks:
    # a real loss of 1,000 (-3.3% of 30,000), past the 3% limit.
    fake = FakeAlpaca({"SPY": 100.0}, cash=10_000.0, positions={"SPY": 200.0}, last_equity=30_000.0)
    engine, notifier, store = fake_alpaca_engine(tmp_path, fake, stop_loss_pct=None, max_daily_loss_pct=3.0)
    assert engine.run_once().halted is False
    fake.prices["SPY"] = 95.0
    fake.qty["SPY"], fake.cash = 0.0, fake.cash + 200 * 95.0

    report = engine.run_once()

    assert report.halted is True
    assert store.load().external_flow == pytest.approx(0.0)


def test_the_bot_never_buys_into_a_short_position_it_would_cover(tmp_path):
    # The user is short 60 SPY by hand on a margin account.
    fake = FakeAlpaca({"SPY": 100.0}, cash=20_000.0, positions={"SPY": -60.0}, last_equity=14_000.0)
    engine, notifier, store = fake_alpaca_engine(tmp_path, fake, "buy", stop_loss_pct=None, max_position_pct=20.0,
                                                 max_daily_loss_pct=3.0)
    for _ in range(2):
        report = engine.run_once()
        assert report.orders == [] and fake.orders == []
        assert "short" in report.signals["SPY"]
    assert len([m for m in notifier.errors if "SPY" in m and "short" in m]) == 1

    fake.qty["SPY"], fake.cash = 0.0, fake.cash - 6_000.0  # the user covers the short by hand
    report = engine.run_once()
    assert report.halted is False
    assert store.load().external_flow == 0.0  # a cover is not money taken out of the account


# ---- regression: how much of one of the bot's orders filled -------------------------------
@pytest.mark.parametrize("status, filled, expected", [
    ("filled", "20", 20.0), ("canceled", "5", 5.0), ("expired", "0", 0.0), ("rejected", "0", 0.0)])
def test_order_filled_qty_reads_a_finished_order(status, filled, expected):
    broker, trading, _ = make_broker()
    trading.get_order_by_client_id.return_value = order(status, qty="20", filled_qty=filled)
    assert broker.order_filled_qty("AAPL", "bot-AAPL-buy-1-ab") == expected
    trading.get_order_by_client_id.assert_called_once_with("bot-AAPL-buy-1-ab")


def test_an_order_reported_filled_without_a_fill_quantity_filled_in_full():
    broker, trading, _ = make_broker()
    trading.get_order_by_client_id.return_value = order("filled", qty="20", filled_qty="0")
    assert broker.order_filled_qty("AAPL", "bot-AAPL-buy-1-ab") == 20.0


def test_order_filled_qty_prefers_the_brokers_order_id():
    broker, trading, _ = make_broker()
    trading.get_order_by_id.return_value = order("filled", qty="3", filled_qty="3")
    assert broker.order_filled_qty("AAPL", "bot-AAPL-buy-1-ab", "order-9") == 3.0
    trading.get_order_by_id.assert_called_once_with("order-9")
    trading.get_order_by_client_id.assert_not_called()


def test_an_order_alpaca_never_received_filled_nothing():
    broker, trading, _ = make_broker()
    trading.get_order_by_client_id.side_effect = api_error(404, "order not found", code=40410000)
    assert broker.order_filled_qty("AAPL", "bot-AAPL-buy-1-ab") == 0.0


def test_an_order_still_working_is_not_settled_yet():
    broker, trading, _ = make_broker()
    trading.get_order_by_client_id.return_value = order("accepted", qty="3", filled_qty="0")
    with pytest.raises(BrokerError, match="still"):
        broker.order_filled_qty("AAPL", "bot-AAPL-buy-1-ab")


@pytest.mark.parametrize("exc", [api_error(500, "internal"), api_error(429, "rate limit"),
                                 requests.ConnectionError("reset")])
def test_an_order_lookup_that_fails_is_looked_up_again_later(exc):
    broker, trading, _ = make_broker()
    trading.get_order_by_client_id.side_effect = exc
    with pytest.raises(BrokerError, match="could not look up"):
        broker.order_filled_qty("AAPL", "bot-AAPL-buy-1-ab")


def test_the_newest_order_of_the_bots_comes_from_the_accounts_latest_orders():
    broker, trading, _ = make_broker()
    trading.get_orders.return_value = [order(symbol="SPY").model_copy(update={"client_order_id": cid})
                                       for cid in ("web-order-1", "bot-SPY-sell-202603100930-ab12cd34",
                                                   "bot-SPY-buy-202603090930-00000000")]
    assert broker.latest_bot_order_id() == "bot-SPY-sell-202603100930-ab12cd34"
    (request,), _ = trading.get_orders.call_args
    assert request.status is QueryOrderStatus.ALL and request.direction.value == "desc" and request.limit >= 50
    trading.get_orders.return_value = [order().model_copy(update={"client_order_id": "web-order-1"})]
    assert broker.latest_bot_order_id() is None


def test_a_brief_order_lookup_outage_never_sells_the_users_shares(tmp_path):
    # The bot owns 20 of 120 SPY (the user's 100). Its stop-loss SELL fills, the
    # user buys 30 more, then the next tick's order lookups fail (HTTP 503).
    fake = FakeAlpaca({"SPY": 100.0}, cash=8_000.0, positions={"SPY": 120.0}, last_equity=20_000.0)
    engine, notifier, store = fake_alpaca_engine(tmp_path, fake, owned={"SPY": 20.0}, stop_loss_pct=5.0,
                                                 max_daily_loss_pct=None)
    fake.prices["SPY"] = 94.0
    assert [(o.side, o.qty, o.status) for o in engine.run_once().orders] == [(Side.SELL, 20.0, "accepted")]
    fake.fill()
    fake.qty["SPY"] += 30.0
    real_lookup = fake.get_order_by_id
    fake.get_order_by_id = MagicMock(side_effect=api_error(503, "service unavailable", code=50300000))
    assert engine.run_once().orders == []  # unknown yet: nothing is sold blind
    fake.get_order_by_id = real_lookup

    for _ in range(2):
        assert engine.run_once().orders == []
    assert fake.qty["SPY"] == 130.0 and store.load().owned == {}


def test_a_buy_whose_reply_was_lost_is_looked_up_and_keeps_its_stop_loss(tmp_path):
    fake = FakeAlpaca({"SPY": 100.0}, cash=10_000.0, last_equity=10_000.0)
    engine, notifier, store = fake_alpaca_engine(tmp_path, fake, "buy", stop_loss_pct=5.0, max_position_pct=30.0,
                                                 max_daily_loss_pct=None)
    real_submit = fake.submit_order

    def placed_then_timed_out(request):
        real_submit(request)
        fake.fill()
        raise requests.ReadTimeout("read timed out")

    fake.submit_order = placed_then_timed_out
    assert any("may or may not" in e for e in engine.run_once().errors)
    fake.submit_order = real_submit
    fake.prices["SPY"] = 90.0

    report = engine.run_once()

    assert [(o.symbol, o.side, o.qty) for o in report.orders] == [("SPY", Side.SELL, 20.0)]  # 1% risk / 5% stop
    assert not any("did not buy" in m for m in notifier.errors)


def test_a_buy_alpaca_never_received_is_not_booked_even_when_the_user_buys_the_symbol(tmp_path):
    fake = FakeAlpaca({"SPY": 100.0}, cash=10_000.0, last_equity=10_000.0)
    engine, notifier, store = fake_alpaca_engine(tmp_path, fake, "buy", stop_loss_pct=5.0, max_position_pct=30.0,
                                                 max_daily_loss_pct=None)
    real_submit = fake.submit_order
    fake.submit_order = lambda request: (_ for _ in ()).throw(requests.ConnectionError("connection reset"))
    assert any("may or may not" in e for e in engine.run_once().errors)
    assert store.load().owned["SPY"]["qty"] == 20.0  # booked as sent: its outcome is unknown
    fake.submit_order = real_submit
    fake.qty["SPY"], fake.entry["SPY"], fake.cash = 20.0, 100.0, 8_000.0  # meanwhile the user buys 20 by hand
    fake.prices["SPY"] = 90.0

    for _ in range(2):
        assert engine.run_once().orders == []  # the user's shares are never sold

    assert store.load().owned == {} and store.load().pending_orders == {}
    assert any("SPY" in m and "did not buy" in m for m in notifier.errors)
