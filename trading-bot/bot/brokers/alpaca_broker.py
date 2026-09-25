"""Alpaca (US stocks/ETFs) broker adapter built on ``alpaca-py``.

Paper trading by default. Safety rules enforced here, on top of the engine's
own checks:

* No leverage: ``Account.buying_power`` is Alpaca's ``non_marginable_buying_power``
  (cash you actually have), never the margin-inflated ``buying_power``.
* No shorting: before every SELL the live position is re-read and the quantity
  is capped at the shares actually available; no position -> "rejected".
* Quantities are only ever rounded DOWN.
* Vendor exceptions never leak: reads raise ``BrokerError``; order submission
  returns status "rejected" for business rejections (HTTP 4xx such as 403
  insufficient buying power or 422 invalid order) and raises ``BrokerError``
  for transport/server failures (5xx, connection errors, timeouts) and for the
  transient 4xx codes 401/408/429, so the engine retries on the next tick.
* Every HTTP request has a finite timeout (``HTTP_TIMEOUT``): alpaca-py sets
  none, so one connection that is accepted but never answered would otherwise
  block the trading loop, and every stop-loss check, forever.
* Intraday bars are limited to the regular session (see
  ``regular_session_bars``), the only hours the bot trades in; 1h and 4h bars
  are built from 30-minute ones, so that no bar mixes in pre-market trades.
"""
from __future__ import annotations

import logging
import math
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime, timedelta
from decimal import ROUND_DOWN, Context, Decimal
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from alpaca.common.enums import Sort
from alpaca.common.exceptions import APIError
from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestTradeRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce
from alpaca.trading.requests import GetOrdersRequest, MarketOrderRequest

from ..models import BAR_COLUMNS, Account, OrderRequest, OrderResult, Position, Side
from ..utils import timeframe_to_timedelta, utcnow, validate_bars
from .base import ALPACA_TRADING_DAY_TIMEZONE, BOT_ORDER_PREFIX, Broker, BrokerError, OpenOrder

logger = logging.getLogger(__name__)

# Canonical timeframe -> Alpaca TimeFrame.
TIMEFRAMES: dict[str, TimeFrame] = {
    "1m": TimeFrame(1, TimeFrameUnit.Minute),
    "5m": TimeFrame(5, TimeFrameUnit.Minute),
    "15m": TimeFrame(15, TimeFrameUnit.Minute),
    "30m": TimeFrame(30, TimeFrameUnit.Minute),
    "1h": TimeFrame(1, TimeFrameUnit.Hour),
    "4h": TimeFrame(4, TimeFrameUnit.Hour),
    "1d": TimeFrame(1, TimeFrameUnit.Day),
}

DATA_FEEDS: dict[str, DataFeed] = {"iex": DataFeed.IEX, "sip": DataFeed.SIP}

# Timeframes built from finer bars: Alpaca's own are clock-aligned, so its
# 09:00 hourly bar (and a 4h bar) would mix pre-market trades into the first
# bar of the session, which the live bot, trading only from 09:30, never sees.
_BUILT_FROM: dict[str, str] = {"1h": "30m", "4h": "30m"}

# Alpaca order statuses that mean "this order will never fill".
_DEAD_STATUSES = frozenset({"rejected", "canceled", "expired"})
# Order statuses after which an order's filled quantity no longer changes.
_FINISHED_STATUSES = _DEAD_STATUSES | {"filled", "replaced", "done_for_day", "calculated"}

# 4xx codes that are transient/transport problems rather than a verdict on the
# order itself: raise BrokerError so the engine retries next tick instead of
# recording a rejection. (401 bad keys, 408 timeout, 429 rate limit after the
# SDK's own retries.)
_TRANSIENT_4XX = frozenset({401, 408, 429})

# Look-back window sizing for get_bars. Alpaca's bars endpoint returns bars
# from ``start`` forward, so we ask for comfortably more calendar time than
# ``limit`` bars need and keep the tail.
_REGULAR_SESSION = timedelta(hours=6, minutes=30)
_WEEKEND_FACTOR = 7 / 5    # 5 trading days per 7 calendar days
_HOLIDAY_FACTOR = 1.1      # ~9 NYSE holidays a year, plus slack
_PAD_DAYS = 7
_MAX_LOOKBACK_DAYS = 365 * 50

# (connect, read) seconds for every Alpaca REST request.
HTTP_TIMEOUT: tuple[float, float] = (5.0, 20.0)

# The regular session in New York; intraday bars outside it are dropped.
_NEW_YORK = ZoneInfo("America/New_York")
_SESSION_OPEN_MINUTE = 9 * 60 + 30
_SESSION_CLOSE_MINUTE = 16 * 60

FRACTIONAL_DECIMALS = 6    # fractionable assets are traded in 1e-6 share steps
_FRACTIONAL_STEP = 10.0 ** -FRACTIONAL_DECIMALS
_ORDER_DECIMALS = 9        # Alpaca accepts quantities with up to 9 decimals
_RECENT_ORDERS = 100       # latest orders searched for the bot's newest (latest_bot_order_id)


def lookback_start(timeframe: str, limit: int, now: datetime) -> datetime:
    """Earliest bar time to request so that ``limit`` bars are available.

    Assumes only the 6.5h regular session trades (Alpaca also returns extended
    hours bars intraday, which only adds margin) and pads for weekends and
    exchange holidays.
    """
    if limit < 1:
        raise ValueError(f"limit must be >= 1, got {limit}")
    td = timeframe_to_timedelta(timeframe)
    if td >= timedelta(days=1):
        sessions = limit * (td / timedelta(days=1))
    else:
        per_session = max(1, int(_REGULAR_SESSION / td))  # 4h -> 1 (floored)
        sessions = math.ceil(limit / per_session)
    days = math.ceil(sessions * _WEEKEND_FACTOR * _HOLIDAY_FACTOR) + _PAD_DAYS
    return now - timedelta(days=min(days, _MAX_LOOKBACK_DAYS))


def regular_session_bars(bars: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """Keep only intraday bars that overlap the regular session (weekdays,
    09:30-16:00 New York time). Alpaca also returns pre-market and after-hours
    bars, which the live bot never acts on (it trades only while the market is
    open), so live signals and backtests both use this series. Alpaca's bars
    are clock-aligned: a 1h bar opening at 09:00 straddles the 09:30 open, so
    1h and 4h bars are built from 30-minute ones instead (``resample_session_bars``).
    Early-close days keep their after-hours bars up to 16:00."""
    minutes_long = timeframe_to_timedelta(timeframe) / timedelta(minutes=1)
    if bars.empty or minutes_long >= 24 * 60:
        return bars
    local = bars.index.tz_convert(_NEW_YORK)
    start = local.hour.to_numpy() * 60 + local.minute.to_numpy()
    keep = ((local.weekday.to_numpy() < 5) & (start < _SESSION_CLOSE_MINUTE)
            & (start + minutes_long > _SESSION_OPEN_MINUTE))
    return bars[keep]


def resample_session_bars(bars: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """Combine regular-session bars into ``timeframe`` bars aligned to the
    New York clock (1h: 09:00, 10:00, ...; 4h: 08:00 and 12:00), each labelled
    by its start. The 09:00 hourly bar then holds only 09:30-10:00: its open
    is the session's first trade, its low and high are regular-session ones."""
    if bars.empty:
        return bars
    step = timeframe_to_timedelta(timeframe)
    wall = bars.index.tz_convert(_NEW_YORK).tz_localize(None).floor(step)
    grouped = bars.groupby(wall, sort=True).agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
        volume=("volume", "sum"))
    grouped.index = pd.DatetimeIndex(grouped.index).tz_localize(_NEW_YORK).tz_convert("UTC")
    return validate_bars(grouped)


def map_order_status(status: Any) -> str:
    """Alpaca ``OrderStatus`` -> our "filled" | "rejected" | "accepted"."""
    value = _enum_value(status)
    if value == "filled":
        return "filled"
    if value in _DEAD_STATUSES:
        return "rejected"
    return "accepted"


class AlpacaBroker(Broker):
    name = "alpaca"
    trading_day_timezone = ALPACA_TRADING_DAY_TIMEZONE  # last_equity is the previous New York close

    def __init__(self, api_key: str, secret_key: str, paper: bool = True, data_feed: str = "iex",
                 trading_client=None, data_client=None) -> None:
        feed = str(data_feed).strip().lower()
        if feed not in DATA_FEEDS:
            raise ValueError(f"Unknown Alpaca data feed {data_feed!r}; use one of {sorted(DATA_FEEDS)} "
                             "('iex' is free, 'sip' needs a paid market-data plan)")
        if (trading_client is None or data_client is None) and not (api_key and secret_key):
            raise ValueError("Alpaca API key and secret key are required "
                             "(set ALPACA_API_KEY and ALPACA_SECRET_KEY)")
        self.paper = bool(paper)
        self.data_feed = DATA_FEEDS[feed]
        self._trading = trading_client if trading_client is not None else \
            TradingClient(api_key, secret_key, paper=self.paper)
        self._data = data_client if data_client is not None else \
            StockHistoricalDataClient(api_key, secret_key)
        for client in (self._trading, self._data):
            _install_timeout(client)
        self._fractionable: dict[str, bool] = {}
        self._shorts: dict[str, Position] = {}   # short positions seen by the last get_positions()
        logger.info("Alpaca broker ready: %s trading, %s data feed",
                    "PAPER" if self.paper else "LIVE", feed)

    # ---- market data -------------------------------------------------------
    def get_bars(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        _require_stock_symbol(symbol)
        if timeframe not in TIMEFRAMES:
            raise ValueError(f"Unsupported timeframe {timeframe!r} for Alpaca; use one of {list(TIMEFRAMES)}")
        source = _BUILT_FROM.get(timeframe, timeframe)
        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TIMEFRAMES[source],
            start=lookback_start(timeframe, limit, utcnow()),
            feed=self.data_feed,
            adjustment=Adjustment.ALL,
        )
        with _vendor_errors(f"get_bars({symbol}, {timeframe})"):
            response = self._data.get_stock_bars(request)
            bars = regular_session_bars(validate_bars(_bars_frame(response, symbol)), source)
            if source != timeframe:
                bars = resample_session_bars(bars, timeframe)
        if bars.empty:
            raise BrokerError(f"Alpaca returned no {timeframe} bars for {symbol} "
                              f"(feed={self.data_feed.value}); check the symbol is a US stock/ETF")
        return bars.tail(limit)

    def get_latest_price(self, symbol: str) -> float:
        _require_stock_symbol(symbol)
        request = StockLatestTradeRequest(symbol_or_symbols=symbol, feed=self.data_feed)
        with _vendor_errors(f"get_latest_price({symbol})"):
            trades = self._data.get_stock_latest_trade(request)
            trade = trades.get(symbol) if isinstance(trades, Mapping) else None
            price = _to_float(_field(trade, "price", "p"))
        if price is None or not math.isfinite(price) or price <= 0:
            raise BrokerError(f"Alpaca returned no valid latest trade price for {symbol}")
        return price

    # ---- account -----------------------------------------------------------
    def get_account(self) -> Account:
        with _vendor_errors("get_account"):
            acct = self._trading.get_account()
            equity = float(acct.equity)
            cash = float(acct.cash)
            buying_power = _to_float(acct.non_marginable_buying_power)
            if buying_power is None:
                # Never fall back to margin buying power alone: cap at cash.
                fallback = [v for v in (cash, _to_float(acct.buying_power)) if v is not None]
                buying_power = min(fallback)
                logger.warning("Alpaca account has no non_marginable_buying_power; using %.2f", buying_power)
            last_equity = _to_float(getattr(acct, "last_equity", None))
            blocked = any(bool(getattr(acct, flag, False))
                          for flag in ("trading_blocked", "account_blocked", "trade_suspended_by_user"))
            return Account(
                equity=equity,
                cash=cash,
                buying_power=max(0.0, buying_power),
                currency=str(getattr(acct, "currency", None) or "USD"),
                day_start_equity=last_equity,
                trading_blocked=blocked,
            )

    def get_positions(self) -> dict[str, Position]:
        """Long positions. Short ones (a margin account where a person sold
        short) are kept aside for :meth:`short_positions`."""
        with _vendor_errors("get_positions"):
            positions: dict[str, Position] = {}
            shorts: dict[str, Position] = {}
            for p in self._trading.get_all_positions():
                qty = float(p.qty)
                if qty == 0:
                    continue
                short = qty < 0 or _enum_value(getattr(p, "side", "long")) == "short"
                entry = float(p.avg_entry_price)
                price = _to_float(getattr(p, "current_price", None))
                if price is None:
                    value = _to_float(getattr(p, "market_value", None))
                    price = value / qty if value is not None else entry
                if _enum_value(getattr(p, "asset_class", "")) == "us_option":
                    # Quoted per share; market_value and cost_basis carry the x100 contract multiplier.
                    value = _to_float(getattr(p, "market_value", None))
                    cost = _to_float(getattr(p, "cost_basis", None))
                    price, entry = (value / qty if value else price), (cost / qty if cost else entry)
                target = shorts if short else positions
                target[str(p.symbol)] = Position(symbol=str(p.symbol), qty=-abs(qty) if short else qty,
                                                 avg_entry_price=entry, market_price=abs(price))
            for symbol, pos in shorts.items():
                if symbol not in self._shorts:
                    logger.warning("Alpaca account is short %g %s (not the bot's: it is long-only and never "
                                   "covers it)", -pos.qty, symbol)
            self._shorts = shorts
            return positions

    def short_positions(self) -> dict[str, Position]:
        return dict(self._shorts)

    # ---- orders ------------------------------------------------------------
    def submit_order(self, order: OrderRequest) -> OrderResult:
        try:
            side = Side(order.side)
        except ValueError:
            return _rejected(order, f"invalid side {order.side!r}")
        if not _is_stock_symbol(order.symbol):
            return _rejected(order, f"{order.symbol!r} is not a US stock/ETF symbol (crypto pairs "
                                    "with '/' need the ccxt broker)")
        qty = _to_float(order.qty)
        if qty is None or not math.isfinite(qty) or qty <= 0:
            return _rejected(order, f"quantity must be > 0, got {order.qty!r}")
        qty = _round_down(qty)
        if qty <= 0:
            return _rejected(order, "quantity rounds down to 0", qty)

        if side is Side.SELL:
            available = self._sellable_qty(order.symbol)
            if available <= 0:
                return _rejected(order, f"no {order.symbol} shares available to sell "
                                        "(long-only: refusing to open a short)", qty)
            if qty > available:
                logger.warning("SELL %s qty %s exceeds available %s; selling only what is held",
                               order.symbol, qty, available)
                qty = available
            elif available - qty < _FRACTIONAL_STEP:
                # A "sell everything" rounded down to 1e-6 (normalize_qty) would leave a
                # sub-1e-6 remainder of a position holding more decimals (e.g. one bought
                # manually by dollar amount), which the engine would keep treating as a
                # position forever. Sell the whole holding instead (Alpaca takes 9 decimals).
                qty = available

        try:
            request = MarketOrderRequest(
                symbol=order.symbol,
                qty=qty,
                side=OrderSide.BUY if side is Side.BUY else OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
                client_order_id=order.client_order_id,
            )
        except ValueError as exc:  # pydantic validation: nothing was sent
            return _rejected(order, f"invalid order: {exc}", qty)
        try:
            placed = self._trading.submit_order(request)
        except APIError as exc:
            status = _status_code(exc)
            if _is_business_rejection(status) and order.client_order_id and _is_duplicate_client_id(exc):
                return self._already_placed(order, side, qty, exc)
            if _is_business_rejection(status):
                reason = f"rejected by Alpaca: {_api_error_text(exc)}"
                logger.warning("%s %s %s %s", side.value.upper(), qty, order.symbol, reason)
                return _rejected(order, reason, qty)
            raise BrokerError(f"Alpaca submit_order({order.symbol}) failed: {_api_error_text(exc)}") from exc
        except Exception as exc:  # connection errors, timeouts, response parsing
            raise BrokerError(f"Alpaca submit_order({order.symbol}) failed ({type(exc).__name__}: {exc}); "
                              "the order may or may not have reached Alpaca - check open orders") from exc
        return _order_result(placed, symbol=order.symbol, side=side, qty=qty, reason=order.reason)

    def cancel_all_orders(self) -> None:
        with _vendor_errors("cancel_all_orders"):
            responses = self._trading.cancel_orders()
        logger.info("Alpaca: requested cancel of %d open order(s)", len(responses or []))

    def open_orders(self, symbol: str) -> list[OpenOrder]:
        """Working orders on ``symbol``; the bot's own carry a ``bot-`` client order id."""
        _require_stock_symbol(symbol)
        request = GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol])
        with _vendor_errors(f"get_orders({symbol})"):
            return [_open_order(o, symbol) for o in self._trading.get_orders(request) or []]

    def order_filled_qty(self, symbol: str, client_order_id: str, order_id: str = "") -> float | None:
        """A lookup that fails (5xx, 429, a timeout, a dropped connection)
        raises BrokerError like an order still working: the engine keeps it
        pending and looks again next tick, rather than guessing from how the
        holding changed (a trade by hand in the meantime would be counted as
        the bot's). 404: Alpaca never received it, so nothing filled."""
        key = order_id or client_order_id
        if not key:
            return None
        try:
            if order_id:
                placed = self._trading.get_order_by_id(order_id)
            else:
                placed = self._trading.get_order_by_client_id(client_order_id)
        except APIError as exc:
            if _status_code(exc) == 404:  # Alpaca never received it
                return 0.0
            raise BrokerError(f"Alpaca could not look up order {key} ({symbol}): {_api_error_text(exc)}") from exc
        except Exception as exc:
            raise BrokerError(f"Alpaca could not look up order {key} ({symbol}): "
                              f"{type(exc).__name__}: {exc}") from exc
        status = _enum_value(_field(placed, "status"))
        if status not in _FINISHED_STATUSES:
            raise BrokerError(f"Alpaca order {key} ({symbol}) is still {status or 'working'}")
        filled = max(_to_float(_field(placed, "filled_qty")) or 0.0, 0.0)
        if status == "filled" and not filled:  # "filled" without a fill quantity: all of it
            return max(_to_float(_field(placed, "qty")) or 0.0, 0.0)
        return filled

    def latest_bot_order_id(self) -> str | None:
        """From the account's latest orders (newest first, whoever placed them)."""
        request = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=_RECENT_ORDERS, direction=Sort.DESC)
        with _vendor_errors("get_orders(recent)"):
            ids = [str(_field(o, "client_order_id") or "") for o in self._trading.get_orders(request) or []]
        return next((cid for cid in ids if cid.startswith(BOT_ORDER_PREFIX)), None)

    def cancel_order(self, symbol: str, order_id: str) -> None:
        _require_stock_symbol(symbol)
        try:
            self._trading.cancel_order_by_id(order_id)
        except APIError as exc:
            if _status_code(exc) in (404, 422):  # already filled / cancelled
                logger.info("Alpaca: order %s (%s) is no longer working", order_id, symbol)
                return
            raise BrokerError(f"Alpaca cancel_order({order_id}, {symbol}) failed: {_api_error_text(exc)}") from exc
        except Exception as exc:
            raise BrokerError(f"Alpaca cancel_order({order_id}, {symbol}) failed: "
                              f"{type(exc).__name__}: {exc}") from exc
        logger.info("Alpaca: requested cancel of order %s (%s)", order_id, symbol)

    def cancel_orders(self, symbols: Sequence[str]) -> None:
        """Cancel the working orders of ``symbols`` only (``cancel_all_orders``
        would also cancel orders on every other symbol in the account)."""
        wanted = list(dict.fromkeys(symbols))
        if not wanted:
            return
        for symbol in wanted:
            _require_stock_symbol(symbol)
        request = GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=wanted)
        with _vendor_errors(f"get_orders({', '.join(wanted)})"):
            orders = self._trading.get_orders(request) or []
        errors = []
        for working in orders:
            order_id = _field(working, "id")
            try:
                self._trading.cancel_order_by_id(order_id)
            except APIError as exc:
                if _status_code(exc) not in (404, 422):  # already filled / cancelled
                    errors.append(f"{order_id}: {_api_error_text(exc)}")
            except Exception as exc:
                errors.append(f"{order_id}: {type(exc).__name__}: {exc}")
        if errors:
            raise BrokerError("Alpaca could not cancel every order: " + "; ".join(errors))
        logger.info("Alpaca: requested cancel of %d open order(s) for %s", len(orders), ", ".join(wanted))

    # ---- market rules ------------------------------------------------------
    def is_market_open(self) -> bool:
        with _vendor_errors("get_clock"):
            return bool(self._trading.get_clock().is_open)

    def min_order_notional(self, symbol: str) -> float:
        return 1.0

    def normalize_qty(self, symbol: str, qty: float) -> float:
        """Round DOWN: to 1e-6 shares for fractionable assets, else whole shares."""
        _require_stock_symbol(symbol)
        if qty is None or not math.isfinite(qty) or qty <= 0:
            return 0.0
        if self._is_fractionable(symbol):
            return _floor_decimals(qty, FRACTIONAL_DECIMALS)
        return float(math.floor(qty))

    # ---- convenience -------------------------------------------------------
    def close_all_positions(self) -> list[OrderResult]:
        """Cancel all working orders and liquidate every position (Alpaca-side)."""
        with _vendor_errors("close_all_positions"):
            responses = self._trading.close_all_positions(cancel_orders=True)
        results = [_close_result(r) for r in responses or []]
        logger.warning("Alpaca: flatten requested for %d position(s)", len(results))
        return results

    # ---- internals ---------------------------------------------------------
    def _already_placed(self, order: OrderRequest, side: Side, qty: float, exc: APIError) -> OrderResult:
        """Alpaca refused the client order id as a duplicate: an earlier attempt
        of THIS order went through (alpaca-py re-sends a POST after a 504/429),
        so report that order instead of a rejection."""
        client_id = str(order.client_order_id)
        logger.warning("Alpaca: %s (%s) is a duplicate client order id; looking up the order already placed",
                       client_id, _api_error_text(exc))
        try:
            placed = self._trading.get_order_by_client_id(client_id)
            return _order_result(placed, symbol=order.symbol, side=side, qty=qty, reason=order.reason)
        except Exception as lookup_exc:
            raise BrokerError(f"Alpaca refused client order id {client_id} as a duplicate, so the "
                              f"order may have been placed, but looking it up failed ({type(lookup_exc).__name__}: "
                              f"{lookup_exc}); check open orders") from lookup_exc

    def _is_fractionable(self, symbol: str) -> bool:
        if symbol not in self._fractionable:
            with _vendor_errors(f"get_asset({symbol})"):
                self._fractionable[symbol] = bool(self._trading.get_asset(symbol).fractionable)
        return self._fractionable[symbol]

    def _sellable_qty(self, symbol: str) -> float:
        """Shares of ``symbol`` we hold long and that are not tied up in other orders."""
        try:
            pos = self._trading.get_open_position(symbol)
        except APIError as exc:
            if _status_code(exc) == 404:  # Alpaca: "position does not exist"
                return 0.0
            raise BrokerError(f"Alpaca get_open_position({symbol}) failed: {_api_error_text(exc)}") from exc
        except Exception as exc:
            raise BrokerError(f"Alpaca get_open_position({symbol}) failed: "
                              f"{type(exc).__name__}: {exc}") from exc
        with _vendor_errors(f"get_open_position({symbol})"):
            held = float(pos.qty)
            if held <= 0 or _enum_value(getattr(pos, "side", "long")) == "short":
                return 0.0
            available = _to_float(getattr(pos, "qty_available", None))
            return _round_down(min(held, available if available is not None else held))


# ---- helpers ----------------------------------------------------------------
class _TimeoutAdapter(HTTPAdapter):
    """Transport adapter that gives every request without a timeout ``timeout``."""

    def __init__(self, timeout: tuple[float, float], **kwargs: Any) -> None:
        self.timeout = timeout
        super().__init__(**kwargs)

    def send(self, request: requests.PreparedRequest, **kwargs: Any) -> requests.Response:  # type: ignore[override]
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = self.timeout
        return super().send(request, **kwargs)


def _install_timeout(client: Any) -> None:
    """Mount a default-timeout adapter on an alpaca-py client's requests session.
    (A timed-out request raises ``requests.Timeout``, reported as BrokerError.)"""
    session = getattr(client, "_session", None)
    if isinstance(session, requests.Session):
        adapter = _TimeoutAdapter(HTTP_TIMEOUT)
        session.mount("https://", adapter)
        session.mount("http://", adapter)


def _is_duplicate_client_id(exc: APIError) -> bool:
    text = _api_error_text(exc).lower()
    return "client_order_id" in text and any(word in text for word in ("unique", "duplicate", "already"))


def _open_order(order: Any, symbol: str) -> OpenOrder:
    side = _enum_value(_field(order, "side"))
    client_id = str(_field(order, "client_order_id") or "")
    return OpenOrder(id=str(_field(order, "id") or ""), symbol=str(_field(order, "symbol") or symbol),
                     side=Side(side) if side in ("buy", "sell") else None,
                     placed_by_bot=client_id.startswith(BOT_ORDER_PREFIX))


@contextmanager
def _vendor_errors(what: str) -> Iterator[None]:
    """Re-raise any vendor/parsing exception as BrokerError with context."""
    try:
        yield
    except BrokerError:
        raise
    except APIError as exc:
        raise BrokerError(f"Alpaca {what} failed: {_api_error_text(exc)}") from exc
    except Exception as exc:
        raise BrokerError(f"Alpaca {what} failed: {type(exc).__name__}: {exc}") from exc


def _is_stock_symbol(symbol: Any) -> bool:
    return isinstance(symbol, str) and bool(symbol.strip()) and "/" not in symbol


def _require_stock_symbol(symbol: Any) -> None:
    if not _is_stock_symbol(symbol):
        raise BrokerError(f"AlpacaBroker trades US stocks/ETFs only; {symbol!r} is not a stock symbol "
                          "(crypto pairs like 'BTC/USDT' need broker type 'ccxt')")


def _status_code(exc: APIError) -> int | None:
    try:
        code = exc.status_code
    except Exception:  # SDK dereferences http_error.response, which may be None
        return None
    return code if isinstance(code, int) else None


def _is_business_rejection(status: int | None) -> bool:
    return status is not None and 400 <= status < 500 and status not in _TRANSIENT_4XX


def _api_error_text(exc: APIError) -> str:
    """'HTTP 403: insufficient buying power (code 40310000)' without ever raising."""
    try:
        message = str(exc.message)
    except Exception:  # body was not JSON
        message = str(exc) or type(exc).__name__
    try:
        code = f" (code {exc.code})"
    except Exception:
        code = ""
    status = _status_code(exc)
    prefix = f"HTTP {status}: " if status is not None else ""
    return f"{prefix}{message}{code}"[:500]


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "").lower()


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _field(obj: Any, name: str, short: str | None = None) -> Any:
    """Read ``name`` from a model or a raw dict (whose keys may be Alpaca's short names)."""
    if obj is None:
        return None
    if isinstance(obj, Mapping):
        value = obj.get(name)
        return obj.get(short) if value is None and short else value
    return getattr(obj, name, None)


def _floor_decimals(qty: float, decimals: int) -> float:
    """Round ``qty`` DOWN to ``decimals`` places.

    Works on the shortest decimal repr of the float, so a value already on the
    grid (e.g. a held position of 1234.567891 shares) is returned unchanged;
    plain float division (``qty / 1e-6``) can land just below and drop a step.
    """
    step = Decimal(1).scaleb(-decimals)
    return float(Decimal(repr(float(qty))).quantize(step, rounding=ROUND_DOWN, context=Context(prec=64)))


def _round_down(qty: float) -> float:
    """Floor to Alpaca's 9-decimal precision (strips float noise, never rounds up)."""
    return _floor_decimals(qty, _ORDER_DECIMALS)


_BAR_FIELDS = {"timestamp": "t", "open": "o", "high": "h", "low": "l", "close": "c", "volume": "v"}


def _bars_frame(response: Any, symbol: str) -> pd.DataFrame:
    """Alpaca bars (BarSet ``.data`` lists, raw dicts, or ``.df``) -> DataFrame indexed by UTC time."""
    data = response if isinstance(response, Mapping) else getattr(response, "data", None)
    if isinstance(data, Mapping):
        rows = [{name: _field(bar, name, short) for name, short in _BAR_FIELDS.items()}
                for bar in data.get(symbol) or [] if bar is not None]
        frame = pd.DataFrame(rows, columns=list(_BAR_FIELDS)).set_index("timestamp")
    else:
        frame = getattr(response, "df", None)
        if not isinstance(frame, pd.DataFrame):
            raise BrokerError(f"unexpected Alpaca bars response type {type(response).__name__}")
        if isinstance(frame.index, pd.MultiIndex):
            level = "symbol" if "symbol" in frame.index.names else 0
            if symbol not in frame.index.get_level_values(level):
                return pd.DataFrame(columns=BAR_COLUMNS, index=pd.DatetimeIndex([], tz="UTC"))
            frame = frame.xs(symbol, level=level)
        frame = frame.reindex(columns=BAR_COLUMNS)
    frame.index = pd.DatetimeIndex(pd.to_datetime(frame.index, utc=True))
    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce").fillna(0.0)
    return frame


def _rejected(order: OrderRequest, reason: str, qty: float | None = None) -> OrderResult:
    try:
        side = Side(order.side)
    except ValueError:
        side = Side.SELL if str(order.side).lower() == "sell" else Side.BUY
    return OrderResult(id="", symbol=str(order.symbol), side=side,
                       qty=float(qty if qty is not None else (_to_float(order.qty) or 0.0)),
                       status="rejected", reason=reason)


def _order_result(order: Any, symbol: str, side: Side, qty: float, reason: str = "") -> OrderResult:
    raw_status = _enum_value(_field(order, "status"))
    status = map_order_status(raw_status)
    avg = _to_float(_field(order, "filled_avg_price"))
    if status == "rejected":
        reason = f"Alpaca order {raw_status}" + (f" ({reason})" if reason else "")
    return OrderResult(
        id=str(_field(order, "id") or ""),
        symbol=str(_field(order, "symbol") or symbol),
        side=side,
        qty=_to_float(_field(order, "qty")) or qty,
        status=status,
        filled_qty=_to_float(_field(order, "filled_qty")) or 0.0,
        filled_avg_price=avg if avg is not None and avg > 0 else None,  # 0 until processed
        reason=reason,
        raw=_raw(order),
    )


def _close_result(response: Any) -> OrderResult:
    """Map one ``ClosePositionResponse`` (order placed, or failure details) to an OrderResult."""
    body = _field(response, "body")
    symbol = str(_field(response, "symbol") or _field(body, "symbol") or "")
    http_status = _field(response, "status")
    failed = (isinstance(http_status, int) and not 200 <= http_status < 300) or _field(body, "message") is not None
    if failed or body is None:
        message = _field(body, "message") or f"HTTP {http_status}"
        qty = _to_float(_field(body, "existing_qty")) or 0.0
        return OrderResult(id=str(_field(response, "order_id") or ""), symbol=symbol, side=Side.SELL,
                           qty=qty, status="rejected", reason=f"close position failed: {message}",
                           raw=_raw(response))
    side = Side.BUY if _enum_value(_field(body, "side")) == "buy" else Side.SELL
    qty = _to_float(_field(body, "qty")) or 0.0
    return _order_result(body, symbol=symbol, side=side, qty=qty, reason="flatten")


def _raw(obj: Any) -> dict[str, Any] | None:
    if isinstance(obj, Mapping):
        return dict(obj)
    dump = getattr(obj, "model_dump", None)
    if callable(dump):
        try:
            result = dump(mode="json")
        except Exception:
            return None
        return result if isinstance(result, dict) else None
    return None
