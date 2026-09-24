"""Crypto exchange broker built on ccxt (spot only, long only, market orders).

Safety rules enforced here, on top of the engine's own checks:

* Spot markets only: a symbol whose ccxt market is a swap/future/option, or
  that is written in derivative form (``BTC/USDT:USDT``), is refused. There is
  no margin and no leverage anywhere in this adapter.
* No shorting: before every SELL the free base-currency balance is re-read and
  the quantity is capped at it; nothing to sell -> "rejected".
* Quantities are only ever rounded DOWN (``amount_to_precision`` truncates),
  and orders outside the market's amount/cost limits are rejected locally,
  before anything is sent.
* Vendor exceptions never leak: reads raise ``BrokerError``; order submission
  returns status "rejected" when the exchange refuses the order
  (``InsufficientFunds``, ``InvalidOrder``, ``BadRequest``, ``OperationRejected``)
  and raises ``BrokerError`` for network/auth/unknown failures, so the engine
  retries on the next tick.
* Without API keys only public market data works (so this class can be the
  price feed of a local ``PaperBroker``); every account/order method raises.

Exchanges do not report entry prices for spot holdings, so the average entry
price of each position is kept in a small JSON file (``entries_path``) updated
on our own fills. Holdings the bot did not buy itself are anchored at the price
first seen, so stop-losses still have a fixed reference.
"""
from __future__ import annotations

import contextlib
import difflib
import json
import logging
import math
import numbers
import os
import tempfile
import time
from collections.abc import Iterator, Mapping
from datetime import timedelta
from pathlib import Path
from typing import Any

import ccxt
import pandas as pd

from ..models import BAR_COLUMNS, Account, OrderRequest, OrderResult, Position, Side
from ..utils import timeframe_to_timedelta, validate_bars
from .base import Broker, BrokerError

logger = logging.getLogger(__name__)

DEFAULT_MIN_ORDER_COST = 1.0
# Minimum order value for venues whose ccxt markets do not report
# ``limits.cost.min`` (exchange id -> quote currency -> minimum).
KNOWN_MIN_ORDER_COST: dict[str, dict[str, float]] = {"upbit": {"KRW": 5000.0}}

# Exchange verdicts on an order: report "rejected", do not retry.
ORDER_REJECTIONS: tuple[type[Exception], ...] = (
    ccxt.InsufficientFunds, ccxt.InvalidOrder, ccxt.BadRequest, ccxt.OperationRejected)

_DEAD_STATUSES = frozenset({"canceled", "cancelled", "rejected", "expired"})
_MAX_OHLCV_PAGES = 50


def map_order_status(status: str | None, filled: float | None = None) -> str:
    """ccxt order status -> ``OrderResult.status``.

    "closed" -> "filled"; "canceled"/"rejected"/"expired" -> "rejected" unless
    part of it executed (Upbit reports a fully spent market buy as "cancel"),
    in which case "filled" so the bought coins are not reported as nothing;
    "open" or unknown -> "accepted".
    """
    value = (status or "").lower()
    if value == "closed":
        return "filled"
    if value in _DEAD_STATUSES:
        return "filled" if filled is not None and filled > 0 else "rejected"
    return "accepted"


def ohlcv_to_bars(rows: list[list[Any]]) -> pd.DataFrame:
    """ccxt OHLCV rows ``[ms, open, high, low, close, volume]`` -> canonical bars.

    Candles with a missing price are dropped (logged); a missing volume is 0.
    """
    if not rows:
        return pd.DataFrame(columns=BAR_COLUMNS, index=pd.DatetimeIndex([], tz="UTC"), dtype=float)
    padded = [(list(row) + [None] * 6)[:6] for row in rows]
    df = pd.DataFrame(padded, columns=["timestamp", *BAR_COLUMNS]).apply(pd.to_numeric, errors="coerce")
    bad = df[["timestamp", "open", "high", "low", "close"]].isna().any(axis=1)
    if bad.any():
        logger.warning("dropping %d malformed candle(s) with missing prices", int(bad.sum()))
        df = df[~bad]
    df["volume"] = df["volume"].fillna(0.0)
    df.index = pd.to_datetime(df["timestamp"].astype("int64"), unit="ms", utc=True)
    return validate_bars(df[BAR_COLUMNS])


class CCXTBroker(Broker):
    """Spot crypto trading on any ccxt exchange (e.g. ``upbit``, ``binance``).

    ``exchange`` injects a ready-made ccxt exchange object (tests); its
    credentials must already be set, and ``api_key``/``secret`` still decide
    whether private (account/order) methods may be used.
    """

    # Seconds to wait before re-reading an order the exchange has not reported
    # as finished yet (market orders fill almost instantly). Tests set 0.
    fill_poll_delay: float = 1.0

    def __init__(self, exchange_id: str, symbols: list[str], api_key: str | None = None,
                 secret: str | None = None, password: str | None = None, sandbox: bool = False,
                 entries_path: Path | None = None, exchange=None) -> None:
        if bool(api_key) != bool(secret):
            raise ValueError("CCXTBroker needs both api_key and secret to trade "
                             "(or neither, for public market data only)")
        self.exchange_id = exchange_id
        self.name = f"ccxt:{exchange_id}"
        self.symbols = list(dict.fromkeys(_check_symbol_list(symbols)))
        self._base = {symbol: symbol.split("/")[0] for symbol in self.symbols}
        quotes = sorted({symbol.split("/")[1] for symbol in self.symbols})
        if len(quotes) != 1:
            raise ValueError(f"all symbols must share one quote currency (the account currency), "
                             f"got {quotes} from {self.symbols}")
        self.quote_currency = quotes[0]
        self.has_credentials = bool(api_key and secret)
        self.exchange = exchange if exchange is not None else _build_exchange(exchange_id, api_key, secret, password)
        self.sandbox = bool(sandbox)
        if self.sandbox:
            _enable_sandbox(self.exchange, exchange_id)
        self.entries_path = Path(entries_path) if entries_path is not None else None
        self._entries: dict[str, dict[str, float]] = self._load_entries()
        self._markets: Mapping[str, Any] | None = None
        self._warned_unknown_entry: set[str] = set()

    @property
    def currency(self) -> str:
        """The account currency: the quote currency shared by all symbols."""
        return self.quote_currency

    @property
    def entries(self) -> dict[str, dict[str, float]]:
        """Copy of the stored entries ``{symbol: {"qty", "avg_entry_price"}}``."""
        return {symbol: dict(entry) for symbol, entry in self._entries.items()}

    # ---- market data (public, no keys needed) ---------------------------------
    def get_bars(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        if not isinstance(limit, numbers.Integral) or limit < 1:
            raise ValueError(f"limit must be a positive integer, got {limit!r}")
        self._market(symbol)
        if not self.exchange.has.get("fetchOHLCV"):
            raise BrokerError(f"{self.exchange_id} does not provide candle (OHLCV) data")
        timeframes = getattr(self.exchange, "timeframes", None) or {}
        if timeframe not in timeframes:
            raise BrokerError(f"{self.exchange_id} does not offer {timeframe!r} candles; "
                              f"supported: {', '.join(timeframes) or 'none'}")
        bars = ohlcv_to_bars(self._fetch_ohlcv(symbol, timeframe, int(limit)))
        if bars.empty:
            raise BrokerError(f"{self.exchange_id} returned no {timeframe} candles for {symbol}")
        return bars.tail(int(limit))

    def get_latest_price(self, symbol: str) -> float:
        """Last trade price; falls back to the bid/ask mid, then the close."""
        self._market(symbol)
        with self._api(f"fetch_ticker({symbol})"):
            ticker = self.exchange.fetch_ticker(symbol) or {}
        last = _positive(ticker.get("last"))
        if last is not None:
            return last
        bid, ask = _positive(ticker.get("bid")), _positive(ticker.get("ask"))
        if bid is not None and ask is not None:
            return (bid + ask) / 2.0
        close = _positive(ticker.get("close"))
        if close is not None:
            return close
        raise BrokerError(f"{self.exchange_id} ticker for {symbol} has no usable price: "
                          f"last={ticker.get('last')!r} bid={ticker.get('bid')!r} ask={ticker.get('ask')!r}")

    # ---- account (keys required) --------------------------------------------
    def get_account(self) -> Account:
        self._require_keys("reading the account balance")
        balance = self._fetch_balance()
        quote = self.quote_currency
        cash = _balance(balance, quote, "total")
        equity = cash
        for symbol in self.symbols:
            qty = _balance(balance, self._base[symbol], "total")
            if qty > 0:
                equity += qty * self.get_latest_price(symbol)
        return Account(equity=equity, cash=cash, buying_power=_balance(balance, quote, "free"),
                       currency=quote, day_start_equity=None)

    def get_positions(self) -> dict[str, Position]:
        """Configured symbols whose base-currency balance is worth at least the
        minimum order value (smaller leftovers are unsellable dust)."""
        self._require_keys("reading positions")
        balance = self._fetch_balance()
        positions: dict[str, Position] = {}
        anchored = False
        for symbol in self.symbols:
            qty = _balance(balance, self._base[symbol], "total")
            if qty <= 0:
                continue
            price = self.get_latest_price(symbol)
            if qty * price < self.min_order_notional(symbol):
                logger.debug("%s: ignoring dust %g %s", self.name, qty, self._base[symbol])
                continue
            entry = self._entries.get(symbol)
            if entry is None:
                if symbol not in self._warned_unknown_entry:
                    self._warned_unknown_entry.add(symbol)
                    logger.warning("%s: entry price of %g %s is unknown (not bought by this bot); "
                                   "using the current price %g as the entry for stop-loss/take-profit",
                                   self.name, qty, symbol, price)
                entry = {"qty": qty, "avg_entry_price": price}
                self._entries[symbol] = entry
                anchored = True
            positions[symbol] = Position(symbol, qty, entry["avg_entry_price"], price)
        if anchored:
            self._save_entries()
        return positions

    # ---- orders (keys required) ----------------------------------------------
    def submit_order(self, order: OrderRequest) -> OrderResult:
        self._require_keys("placing orders")
        symbol = order.symbol
        side = Side(order.side)
        if symbol not in self._base:
            return _rejected(order, f"{symbol} is not one of the configured symbols {self.symbols}")
        if not _finite(order.qty) or order.qty <= 0:
            return _rejected(order, f"invalid quantity {order.qty!r}")
        market = self._market(symbol)
        if market.get("active") is False:
            return _rejected(order, f"{symbol} market is not active on {self.exchange_id}")
        base = self._base[symbol]
        price = self.get_latest_price(symbol)
        balance = self._fetch_balance()
        min_cost = self.min_order_notional(symbol)

        qty, note = float(order.qty), ""
        if side is Side.SELL:
            available = _balance(balance, base, "free")
            if available <= 0:
                return _rejected(order, f"no {base} available to sell")
            if qty > available:
                qty, note = available, f"capped to available {available:g} {base}"
        elif _balance(balance, base, "total") * price < min_cost:
            self._forget_entry(symbol)  # stale entry from a position closed elsewhere

        amount = self._amount_to_precision(symbol, qty)
        if amount <= 0:
            return _rejected(order, f"quantity {qty:g} {base} is below {symbol}'s amount precision", qty)
        by_cost = side is Side.BUY and self._market_buy_by_cost()
        cost = self._cost_to_precision(symbol, amount * price) if by_cost else amount * price
        problem = _limit_problem(market, amount, cost, min_cost, base, self.quote_currency)
        if problem:
            return _rejected(order, problem, amount)
        free_quote = _balance(balance, self.quote_currency, "free")
        if side is Side.BUY and cost > free_quote:
            return _rejected(order, f"insufficient {self.quote_currency}: order value {cost:.8g} exceeds "
                                    f"free balance {free_quote:.8g}", amount)

        what = f"{side.value} {amount:g} {symbol} (~{cost:.8g} {self.quote_currency})"
        try:
            if by_cost and self.exchange.has.get("createMarketBuyOrderWithCost"):
                response = self.exchange.create_market_buy_order_with_cost(symbol, cost)
            elif by_cost:
                response = self.exchange.create_order(symbol, "market", "buy", amount, price)
            else:
                response = self.exchange.create_order(symbol, "market", side.value, amount)
        except ORDER_REJECTIONS as exc:
            logger.warning("%s: %s rejected by the exchange: %s: %s", self.name, what, type(exc).__name__, exc)
            return _rejected(order, f"exchange rejected the order: {type(exc).__name__}: {exc}", amount)
        except ccxt.NetworkError as exc:
            raise BrokerError(f"{self.exchange_id} network error while placing {what}: {exc}. The order may "
                              "or may not have reached the exchange; check open orders and balances") from exc
        except Exception as exc:
            raise BrokerError(f"{self.exchange_id} failed to place {what}: {type(exc).__name__}: {exc}") from exc

        # The order is live from here on: never raise, or the engine could retry it.
        try:
            response = self._refresh_order(response, symbol)
            result = _order_result(response, order, side, amount, note)
            self._record_fill(result, price)
        except Exception:
            logger.exception("%s: order for %s was sent but its response could not be processed", self.name, what)
            raw = response if isinstance(response, dict) else None
            result = OrderResult(id=str((raw or {}).get("id") or ""), symbol=symbol, side=side, qty=amount,
                                 status="accepted", reason=_join(order.reason, "response unreadable"), raw=raw)
        logger.info("%s: %s -> %s (filled %g @ %s)", self.name, what, result.status,
                    result.filled_qty, result.filled_avg_price)
        return result

    def cancel_all_orders(self) -> None:
        self._require_keys("cancelling orders")
        errors: list[str] = []
        for symbol in self.symbols:
            try:
                with self._api(f"fetch_open_orders({symbol})"):
                    orders = self.exchange.fetch_open_orders(symbol) or []
            except BrokerError as exc:
                errors.append(str(exc))
                continue
            for open_order in orders:
                order_id = open_order.get("id")
                try:
                    self.exchange.cancel_order(order_id, symbol)
                    logger.info("%s: cancelled order %s (%s)", self.name, order_id, symbol)
                except ccxt.OrderNotFound:
                    logger.info("%s: order %s (%s) already gone", self.name, order_id, symbol)
                except Exception as exc:
                    errors.append(f"cancel {order_id} ({symbol}): {type(exc).__name__}: {exc}")
        if errors:
            raise BrokerError(f"{self.exchange_id} cancel_all_orders incomplete: " + "; ".join(errors))

    def has_open_orders(self, symbol: str) -> bool:
        self._require_keys("checking open orders")
        self._market(symbol)
        with self._api(f"fetch_open_orders({symbol})"):
            return bool(self.exchange.fetch_open_orders(symbol))

    # ---- market rules ----------------------------------------------------------
    def min_order_notional(self, symbol: str) -> float:
        cost_min = _positive(_limit(self._market(symbol), "cost", "min"))
        if cost_min is not None:
            return cost_min
        return KNOWN_MIN_ORDER_COST.get(self.exchange_id, {}).get(self.quote_currency, DEFAULT_MIN_ORDER_COST)

    def normalize_qty(self, symbol: str, qty: float) -> float:
        """Truncate to the market's amount precision; 0.0 when that leaves
        nothing or less than the market's minimum amount."""
        market = self._market(symbol)
        if not _finite(qty) or qty <= 0:
            return 0.0
        amount = self._amount_to_precision(symbol, qty)
        for key in ("amount", "market"):
            minimum = _positive(_limit(market, key, "min"))
            if minimum is not None and amount < minimum:
                return 0.0
        return amount

    # ---- internals -------------------------------------------------------------
    @contextlib.contextmanager
    def _api(self, what: str) -> Iterator[None]:
        """Translate every vendor exception from a read into ``BrokerError``."""
        try:
            yield
        except BrokerError:
            raise
        except ccxt.NetworkError as exc:
            raise BrokerError(f"{self.exchange_id} {what} failed (network/exchange unavailable): "
                              f"{type(exc).__name__}: {exc}") from exc
        except ccxt.AuthenticationError as exc:
            raise BrokerError(f"{self.exchange_id} {what} failed: API key rejected ({exc}); check "
                              "CCXT_API_KEY / CCXT_SECRET and the key's permissions") from exc
        except Exception as exc:
            raise BrokerError(f"{self.exchange_id} {what} failed: {type(exc).__name__}: {exc}") from exc

    def _require_keys(self, what: str) -> None:
        if not self.has_credentials:
            raise BrokerError(f"API keys required for {what} on {self.exchange_id}: set CCXT_API_KEY and "
                              "CCXT_SECRET in .env (public market data works without keys)")

    def _load_markets(self) -> Mapping[str, Any]:
        if self._markets is None:
            with self._api("load_markets"):
                markets = self.exchange.load_markets()
            if not markets:
                raise BrokerError(f"{self.exchange_id} returned no markets")
            self._markets = markets
        return self._markets

    def _market(self, symbol: str) -> Mapping[str, Any]:
        market = self._load_markets().get(symbol)
        if market is None:
            raise BrokerError(f"{self.exchange_id} has no market {symbol!r}; check `symbols` in your config "
                              "(ccxt format, e.g. 'BTC/KRW' or 'BTC/USDT')")
        if not (market.get("spot") is True or market.get("type") == "spot") or market.get("contract"):
            raise BrokerError(f"{symbol} on {self.exchange_id} is not a spot market; "
                              "this bot only trades spot (no margin, no derivatives)")
        return market

    def _fetch_balance(self) -> Mapping[str, Any]:
        with self._api("fetch_balance"):
            balance = self.exchange.fetch_balance()
        if not isinstance(balance, Mapping):
            raise BrokerError(f"{self.exchange_id} fetch_balance returned {type(balance).__name__}")
        return balance

    def _fetch_ohlcv(self, symbol: str, timeframe: str, limit: int) -> list[list[Any]]:
        """``limit`` most recent candles, paging backwards with ``since`` when the
        exchange caps candles per request below ``limit`` (Upbit: 200)."""
        what = f"fetch_ohlcv({symbol}, {timeframe})"
        per_call = self._ohlcv_page_limit()
        if per_call is None or limit <= per_call:
            with self._api(what):
                return list(self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit) or [])
        try:
            step_ms = int(timeframe_to_timedelta(timeframe) / timedelta(milliseconds=1))
        except ValueError:
            step_ms = 0
        with self._api(what):
            rows = list(self.exchange.fetch_ohlcv(symbol, timeframe, limit=per_call) or [])
            for _ in range(_MAX_OHLCV_PAGES):
                if not rows or len(rows) >= limit or step_ms <= 0:
                    break
                first = min(int(row[0]) for row in rows)
                need = min(per_call, limit - len(rows))
                page = self.exchange.fetch_ohlcv(symbol, timeframe, since=first - need * step_ms, limit=need) or []
                older = [row for row in page if int(row[0]) < first]
                if not older:
                    break
                rows = older + rows
        return rows

    def _ohlcv_page_limit(self) -> int | None:
        try:
            value = self.exchange.features["spot"]["fetchOHLCV"]["limit"]
        except (AttributeError, KeyError, TypeError):
            return None
        return int(value) if _finite(value) and value >= 1 else None

    def _market_buy_by_cost(self) -> bool:
        """True when this exchange takes market buys as a quote amount to spend."""
        options = getattr(self.exchange, "options", None) or {}
        flag = options.get("createMarketBuyOrderRequiresPrice")
        create_order_options = options.get("createOrder")
        if flag is None and isinstance(create_order_options, Mapping):
            flag = create_order_options.get("createMarketBuyOrderRequiresPrice")
        return bool(flag) or "upbit" in (self.exchange_id, getattr(self.exchange, "id", None))

    def _amount_to_precision(self, symbol: str, qty: float) -> float:
        """Truncated amount, or 0.0 when ``qty`` is below the precision step."""
        try:
            amount = float(self.exchange.amount_to_precision(symbol, float(qty)))
        except ccxt.BaseError as exc:
            logger.debug("%s: amount_to_precision(%s, %g): %s", self.name, symbol, qty, exc)
            return 0.0
        return amount if _finite(amount) and amount > 0 else 0.0

    def _cost_to_precision(self, symbol: str, cost: float) -> float:
        """Quote amount truncated to the exchange's precision (as ccxt will do)."""
        try:
            value = float(self.exchange.cost_to_precision(symbol, cost))
        except Exception:
            return cost
        return value if _finite(value) and 0 <= value <= cost else cost

    def _refresh_order(self, response: Any, symbol: str) -> Any:
        """Re-read an order the exchange has not reported as finished, so the
        fill quantity/price (and thus the stored entry price) is accurate."""
        if not isinstance(response, dict) or not response.get("id"):
            return response
        status = (response.get("status") or "").lower()
        finished = status == "closed" or status in _DEAD_STATUSES
        if (finished and response.get("filled") is not None) or not self.exchange.has.get("fetchOrder"):
            return response
        if self.fill_poll_delay > 0:
            time.sleep(self.fill_poll_delay)
        try:
            updated = self.exchange.fetch_order(response["id"], symbol)
        except Exception as exc:
            logger.warning("%s: could not re-read order %s: %s", self.name, response["id"], exc)
            return response
        return updated if isinstance(updated, dict) and updated.get("id") else response

    # ---- entry-price store -----------------------------------------------------
    def _record_fill(self, result: OrderResult, ref_price: float) -> None:
        """Update the stored entry after one of our orders: weighted average on
        buys, reduce/remove on sells. An accepted order with no fill details
        yet is assumed to fill at ``ref_price`` (market order)."""
        if not result.ok:
            return
        qty = result.filled_qty if result.filled_qty > 0 else result.qty
        price = _positive(result.filled_avg_price) or _positive(ref_price)
        if qty <= 0 or price is None:
            return
        entry = self._entries.get(result.symbol)
        if result.side is Side.BUY:
            held = entry["qty"] if entry else 0.0
            avg = entry["avg_entry_price"] if entry else 0.0
            total = held + qty
            self._entries[result.symbol] = {"qty": total, "avg_entry_price": (held * avg + qty * price) / total}
        elif entry is not None:
            remaining = entry["qty"] - qty
            if remaining <= 0 or remaining * price < self.min_order_notional(result.symbol):
                del self._entries[result.symbol]
            else:
                self._entries[result.symbol] = {"qty": remaining, "avg_entry_price": entry["avg_entry_price"]}
        else:
            return
        self._save_entries()

    def _forget_entry(self, symbol: str) -> None:
        if self._entries.pop(symbol, None) is not None:
            logger.info("%s: dropping stale entry for %s (no holding)", self.name, symbol)
            self._save_entries()

    def _load_entries(self) -> dict[str, dict[str, float]]:
        path = self.entries_path
        if path is None or not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError(f"expected a JSON object, got {type(data).__name__}")
        except (ValueError, UnicodeDecodeError) as exc:
            backup = _free_path(path.with_name(path.name + ".corrupt"))
            os.replace(path, backup)
            logger.warning("%s: entries file %s is unreadable (%s); moved it to %s and starting empty",
                           self.name, path, exc, backup)
            return {}
        entries: dict[str, dict[str, float]] = {}
        for symbol, entry in data.items():
            try:
                qty, avg = float(entry["qty"]), float(entry["avg_entry_price"])
            except (KeyError, TypeError, ValueError):
                qty = avg = math.nan
            if _finite(qty) and _finite(avg) and qty > 0 and avg > 0:
                entries[symbol] = {"qty": qty, "avg_entry_price": avg}
            else:
                logger.warning("%s: ignoring invalid stored entry for %s: %r", self.name, symbol, entry)
        return entries

    def _save_entries(self) -> None:
        """Atomic write; a failure is logged, never raised (orders are already live)."""
        path = self.entries_path
        if path is None:
            return
        tmp: str | None = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self._entries, fh, indent=2, sort_keys=True)
            os.replace(tmp, path)
            tmp = None
        except OSError as exc:
            logger.error("%s: could not save entry prices to %s: %s", self.name, path, exc)
        finally:
            if tmp is not None:
                with contextlib.suppress(OSError):
                    os.unlink(tmp)


# ---- helpers -------------------------------------------------------------------
def _check_symbol_list(symbols: Any) -> list[str]:
    if isinstance(symbols, str) or not symbols:
        raise ValueError(f"symbols must be a non-empty list like ['BTC/KRW'], got {symbols!r}")
    for symbol in symbols:
        parts = symbol.split("/") if isinstance(symbol, str) else []
        if len(parts) != 2 or not all(parts) or ":" in symbol:
            raise ValueError(f"{symbol!r} is not a spot symbol in ccxt format BASE/QUOTE (e.g. 'BTC/KRW'); "
                             "derivative symbols like 'BTC/USDT:USDT' are not supported")
    return list(symbols)


def _build_exchange(exchange_id: str, api_key: str | None, secret: str | None, password: str | None) -> Any:
    if exchange_id not in ccxt.exchanges:
        close = difflib.get_close_matches(str(exchange_id), ccxt.exchanges, n=3)
        hint = f" Did you mean {', '.join(close)}?" if close else ""
        raise ValueError(f"unknown exchange {exchange_id!r}: it is not in ccxt.exchanges "
                         f"(e.g. upbit, binance, kraken, coinbase).{hint}")
    config: dict[str, Any] = {"enableRateLimit": True}
    if api_key:
        config["apiKey"] = api_key
    if secret:
        config["secret"] = secret
    if password:
        config["password"] = password
    return getattr(ccxt, exchange_id)(config)


def _enable_sandbox(exchange: Any, exchange_id: str) -> None:
    # ccxt checks ``'test' in urls`` but many exchanges carry ``'test': None``
    # and then crash with a TypeError instead of raising NotSupported.
    urls = getattr(exchange, "urls", None) or {}
    if not urls.get("test"):
        raise ValueError(f"{exchange_id} has no sandbox/testnet in ccxt; set use_sandbox: false "
                         "and use paper mode to practise")
    try:
        exchange.set_sandbox_mode(True)
    except Exception as exc:
        raise ValueError(f"could not enable {exchange_id} sandbox mode: {type(exc).__name__}: {exc}") from exc


def _limit(market: Mapping[str, Any], key: str, bound: str) -> Any:
    limits = market.get("limits") or {}
    return (limits.get(key) or {}).get(bound)


def _limit_problem(market: Mapping[str, Any], amount: float, cost: float, min_cost: float,
                   base: str, quote: str) -> str | None:
    """Why an order of ``amount`` (worth ``cost``) breaks the market's limits, or None."""
    checks = (
        ("amount", amount, f"amount {amount:g} {base}"),
        ("market", amount, f"market-order amount {amount:g} {base}"),
        ("cost", cost, f"order value {cost:.8g} {quote}"),
    )
    for key, value, label in checks:
        low = min_cost if key == "cost" else _positive(_limit(market, key, "min"))
        high = _positive(_limit(market, key, "max"))
        if low is not None and value < low:
            return f"{label} is below the exchange minimum {low:g}"
        if high is not None and value > high:
            return f"{label} is above the exchange maximum {high:g}"
    return None


def _order_result(response: Any, order: OrderRequest, side: Side, amount: float, note: str) -> OrderResult:
    raw = response if isinstance(response, dict) else {}
    filled = _number(raw.get("filled"))
    raw_status = raw.get("status")
    status = map_order_status(raw_status, filled)
    average = _positive(raw.get("average"))
    spent = _positive(raw.get("cost"))
    if average is None and spent is not None and filled:
        average = spent / filled
    if status == "filled" and not filled:
        filled = amount  # "closed" without fill details: fully filled
    reason = _join(order.reason, note)
    if status == "rejected":
        reason = _join(reason, f"exchange reported status {raw_status!r}")
    elif (raw_status or "").lower() in _DEAD_STATUSES:
        reason = _join(reason, f"partially filled {filled:g} of {amount:g} (order {raw_status})")
    return OrderResult(id=str(raw.get("id") or order.client_order_id or ""), symbol=order.symbol, side=side,
                       qty=amount, status=status, filled_qty=filled or 0.0, filled_avg_price=average,
                       reason=reason, raw=raw or None)


def _rejected(order: OrderRequest, reason: str, qty: float | None = None) -> OrderResult:
    logger.warning("%s %s %s rejected: %s", Side(order.side).value, order.qty, order.symbol, reason)
    if qty is None:
        qty = float(order.qty) if _finite(order.qty) else 0.0
    return OrderResult(id="", symbol=order.symbol, side=Side(order.side), qty=qty,
                       status="rejected", reason=_join(order.reason, reason))


def _balance(balance: Mapping[str, Any], code: str, kind: str) -> float:
    """``balance[kind][code]`` (or ``balance[code][kind]``) as a float, 0.0 if missing."""
    value = (balance.get(kind) or {}).get(code)
    if value is None:
        value = (balance.get(code) or {}).get(kind)
    number = _number(value)
    return number if number is not None else 0.0


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _positive(value: Any) -> float | None:
    number = _number(value)
    return number if number is not None and number > 0 else None


def _finite(value: Any) -> bool:
    return isinstance(value, numbers.Real) and not isinstance(value, bool) and math.isfinite(value)


def _join(*parts: str) -> str:
    return "; ".join(part for part in parts if part)


def _free_path(path: Path) -> Path:
    candidate, n = path, 1
    while candidate.exists():
        candidate, n = path.with_name(f"{path.name}-{n}"), n + 1
    return candidate


__all__ = ["CCXTBroker", "map_order_status", "ohlcv_to_bars"]
