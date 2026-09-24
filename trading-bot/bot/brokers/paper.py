"""Local simulated broker: instant market fills on a data feed's prices.

Used by the ``sim`` broker (synthetic prices) and by crypto ``paper`` mode
(real public exchange prices, simulated account). Long-only and unleveraged:
cash can never go negative and a position can never go short.
"""
from __future__ import annotations

import contextlib
import json
import logging
import math
import numbers
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

import pandas as pd

from ..models import Account, OrderRequest, OrderResult, Position, Side
from ..state import give_default_permissions
from ..utils import floor_to_step, utcnow
from .base import Broker, BrokerError

if TYPE_CHECKING:
    from ..data import DataFeed

logger = logging.getLogger(__name__)

MAX_FILLS = 500      # fill history kept in memory and on disk
QTY_STEP = 1e-6      # default quantity precision when the feed has no rules
_STATE_VERSION = 1

T = TypeVar("T")


@dataclass(frozen=True)
class _Holding:
    qty: float
    avg_entry_price: float


class PaperBroker(Broker):
    """Simulated account on top of a :class:`~bot.data.DataFeed`.

    Market orders fill immediately at ``feed.get_latest_price(symbol)`` moved
    against us by ``slippage_pct`` (buys pay more, sells receive less), and
    ``fee_pct`` of the notional is taken from cash. A buy that would cost more
    than the cash available, or is below the minimum order value, is rejected;
    a sell of more than is held sells only what is held (as does a sell that
    would leave an unsellable dust remainder); selling with no position is
    rejected. Quantities are rounded DOWN to the venue's precision.

    With ``state_path`` the account (cash, positions, last ``MAX_FILLS``
    fills, order counter) is saved atomically after every fill and reloaded on
    start. A fill is applied only once it has been saved, so memory and disk
    never disagree. An unreadable state file raises ``BrokerError`` rather than
    silently starting a fresh account.
    """

    name = "paper"
    # A local simulated account: only this bot ever buys in it.
    bot_owned_account = True

    def __init__(self, feed: DataFeed, starting_cash: float = 10_000.0, fee_pct: float = 0.1,
                 slippage_pct: float = 0.05, state_path: Path | None = None,
                 currency: str = "USD", min_notional: float = 1.0,
                 clock: Callable[[], datetime] = utcnow) -> None:
        if not _finite(starting_cash) or starting_cash <= 0:
            raise ValueError(f"starting_cash must be > 0, got {starting_cash!r}")
        for label, pct in (("fee_pct", fee_pct), ("slippage_pct", slippage_pct)):
            if not _finite(pct) or not 0 <= pct < 100:
                raise ValueError(f"{label} must be >= 0 and < 100, got {pct!r}")
        if not _finite(min_notional) or min_notional < 0:
            raise ValueError(f"min_notional must be >= 0, got {min_notional!r}")
        self.feed = feed
        self.starting_cash = float(starting_cash)
        self.fee_pct = float(fee_pct)
        self.slippage_pct = float(slippage_pct)
        self.state_path = Path(state_path) if state_path is not None else None
        self.currency = currency
        self.min_notional = float(min_notional)
        self.clock = clock
        self._cash = self.starting_cash
        self._holdings: dict[str, _Holding] = {}
        self._fills: list[dict[str, Any]] = []
        self._next_id = 1
        self._last_price: dict[str, float] = {}   # last good price per symbol
        if self.state_path is not None and self.state_path.exists():
            self._load(self.state_path)

    # ---- market data (delegated to the feed) --------------------------------
    def get_bars(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        return self._feed_call(f"bars for {symbol}", self.feed.get_bars, symbol, timeframe, limit)

    def get_latest_price(self, symbol: str) -> float:
        price = self._feed_call(f"price for {symbol}", self.feed.get_latest_price, symbol)
        try:
            price = float(price)
        except (TypeError, ValueError):
            price = math.nan
        if not math.isfinite(price) or price <= 0:
            raise BrokerError(f"paper broker: feed returned an invalid price for {symbol}: {price!r}")
        self._last_price[symbol] = price
        return price

    # ---- account --------------------------------------------------------------
    @property
    def cash(self) -> float:
        return self._cash

    @property
    def fills(self) -> list[dict[str, Any]]:
        """Most recent fills, oldest first (copies)."""
        return [dict(fill) for fill in self._fills]

    def get_account(self) -> Account:
        positions, unpriced = self._marked_positions()
        positions_value = sum(p.market_value for p in positions.values())
        return Account(equity=self._cash + positions_value, cash=self._cash, buying_power=self._cash,
                       currency=self.currency, day_start_equity=None, unpriced=unpriced)

    def get_positions(self) -> dict[str, Position]:
        """Open positions marked to the feed's latest price (see ``get_account``
        for a holding whose price cannot be read)."""
        return self._marked_positions()[0]

    def _marked_positions(self) -> tuple[dict[str, Position], tuple[str, ...]]:
        """Holdings marked to market. One symbol whose price cannot be read
        must not break the whole account: it is valued at its last known price
        (else its entry price) and listed as unpriced."""
        positions: dict[str, Position] = {}
        unpriced: list[str] = []
        for symbol, h in self._holdings.items():
            try:
                price = self.get_latest_price(symbol)
            except BrokerError as exc:
                price = self._last_price.get(symbol, h.avg_entry_price)
                unpriced.append(symbol)
                logger.warning("paper broker: cannot price %s (%s); valuing it at %g for now", symbol, exc, price)
            positions[symbol] = Position(symbol, h.qty, h.avg_entry_price, price)
        return positions, tuple(unpriced)

    # ---- market rules (the feed's when it has them, e.g. a CCXTBroker) -------
    def is_market_open(self) -> bool:
        check = getattr(self.feed, "is_market_open", None)
        return bool(self._feed_call("market clock", check)) if callable(check) else True

    def min_order_notional(self, symbol: str) -> float:
        rule = getattr(self.feed, "min_order_notional", None)
        if not callable(rule):
            return self.min_notional
        value = self._feed_call(f"minimum order value for {symbol}", rule, symbol)
        if not _finite(value) or value < 0:
            raise BrokerError(f"paper broker: feed returned an invalid minimum order value for {symbol}: {value!r}")
        return float(value)

    def normalize_qty(self, symbol: str, qty: float) -> float:
        rule = getattr(self.feed, "normalize_qty", None)
        if not callable(rule):
            return floor_to_step(qty, QTY_STEP)
        value = self._feed_call(f"quantity rules for {symbol}", rule, symbol, qty)
        if not _finite(value) or value < 0:
            raise BrokerError(f"paper broker: feed returned an invalid quantity for {symbol}: {value!r}")
        return float(value)

    # ---- orders ---------------------------------------------------------------
    def submit_order(self, order: OrderRequest) -> OrderResult:
        side = Side(order.side)
        order_id = f"paper-{self._next_id}"
        self._next_id += 1
        if not _finite(order.qty) or order.qty <= 0:
            return self._reject(order_id, order, side, f"quantity must be > 0, got {order.qty!r}")
        if side is Side.SELL and order.symbol not in self._holdings:
            return self._reject(order_id, order, side, f"no {order.symbol} position to sell (long-only)")
        price = self.get_latest_price(order.symbol)
        if side is Side.BUY:
            return self._buy(order_id, order, price)
        return self._sell(order_id, order, price)

    def cancel_all_orders(self) -> None:
        """Paper orders fill instantly, so there is never anything working."""

    def reset(self) -> None:
        """Back to ``starting_cash`` with no positions and no fill history.
        Order ids keep counting up so they stay unique."""
        self._save(self.starting_cash, {}, [])
        self._cash, self._holdings, self._fills = self.starting_cash, {}, []
        logger.warning("Paper account reset to %.2f %s", self.starting_cash, self.currency)

    # ---- internals ------------------------------------------------------------
    def _buy(self, order_id: str, order: OrderRequest, price: float) -> OrderResult:
        symbol = order.symbol
        qty = min(self.normalize_qty(symbol, order.qty), order.qty)  # never more than asked
        if qty <= 0:
            return self._reject(order_id, order, Side.BUY, f"quantity {order.qty:g} rounds down to 0")
        fill_price = price * (1.0 + self.slippage_pct / 100.0)
        notional = qty * fill_price
        fee = notional * self.fee_pct / 100.0
        cost = notional + fee
        minimum = self.min_order_notional(symbol)
        if notional < minimum:
            return self._reject(order_id, order, Side.BUY,
                                f"order value {notional:.2f} below minimum {minimum:.2f} {self.currency}")
        if cost > self._cash:
            return self._reject(order_id, order, Side.BUY, f"insufficient cash: need {cost:.2f} {self.currency} "
                                                           f"incl. fee, have {self._cash:.2f}")
        held = self._holdings.get(symbol)
        held_qty, held_cost = (held.qty, held.qty * held.avg_entry_price) if held else (0.0, 0.0)
        new_qty = held_qty + qty
        holdings = {**self._holdings, symbol: _Holding(new_qty, (held_cost + notional) / new_qty)}
        return self._fill(order_id, order, Side.BUY, qty, fill_price, fee, self._cash - cost, holdings)

    def _sell(self, order_id: str, order: OrderRequest, price: float) -> OrderResult:
        symbol = order.symbol
        held = self._holdings[symbol]
        if order.qty > held.qty:
            logger.warning("Paper sell of %g %s exceeds the %g held; selling only what is held",
                           order.qty, symbol, held.qty)
        closing = order.qty >= held.qty
        qty = held.qty if closing else min(self.normalize_qty(symbol, order.qty), order.qty)
        if qty <= 0:
            return self._reject(order_id, order, Side.SELL, f"quantity {order.qty:g} rounds down to 0")
        remaining = held.qty - qty
        if not closing and (remaining <= held.qty * 1e-9 or self.normalize_qty(symbol, remaining) <= 0):
            # The remainder would be unsellable dust (float rounding or below the
            # venue's step) that blocks re-entry forever: close the whole position.
            closing, qty = True, held.qty
        fill_price = price * (1.0 - self.slippage_pct / 100.0)
        notional = qty * fill_price
        fee = notional * self.fee_pct / 100.0
        minimum = self.min_order_notional(symbol)
        if not closing and notional < minimum:  # a whole position may always be closed
            return self._reject(order_id, order, Side.SELL,
                                f"order value {notional:.2f} below minimum {minimum:.2f} {self.currency}")
        holdings = dict(self._holdings)
        if closing:
            del holdings[symbol]
        else:
            holdings[symbol] = _Holding(remaining, held.avg_entry_price)
        realized = (fill_price - held.avg_entry_price) * qty - fee
        return self._fill(order_id, order, Side.SELL, qty, fill_price, fee, self._cash + notional - fee,
                          holdings, realized)

    def _fill(self, order_id: str, order: OrderRequest, side: Side, qty: float, price: float, fee: float,
              cash: float, holdings: dict[str, _Holding], realized_pnl: float | None = None) -> OrderResult:
        if cash < 0 or not math.isfinite(cash):  # cannot happen given the checks above; never allow it
            return self._reject(order_id, order, side, f"would leave cash at {cash!r}")
        fill: dict[str, Any] = {
            "id": order_id, "time": self.clock().isoformat(), "symbol": order.symbol, "side": side.value,
            "qty": qty, "price": price, "notional": qty * price, "fee": fee, "cash_after": cash,
            "reason": order.reason, "client_order_id": order.client_order_id,
        }
        if realized_pnl is not None:
            fill["realized_pnl"] = realized_pnl
        fills = (self._fills + [fill])[-MAX_FILLS:]
        self._save(cash, holdings, fills)  # raises BrokerError -> nothing changed
        self._cash, self._holdings, self._fills = cash, holdings, fills
        logger.info("Paper %s %.8g %s @ %.8g (fee %.4f %s); cash now %.2f",
                    side.value.upper(), qty, order.symbol, price, fee, self.currency, cash)
        reason = order.reason
        if qty < order.qty:
            reason = f"{reason} (filled {qty:g} of {order.qty:g} requested)".strip()
        return OrderResult(id=order_id, symbol=order.symbol, side=side, qty=order.qty, status="filled",
                           filled_qty=qty, filled_avg_price=price, reason=reason, raw=dict(fill))

    def _reject(self, order_id: str, order: OrderRequest, side: Side, reason: str) -> OrderResult:
        logger.warning("Paper %s %s %s rejected: %s", side.value, order.qty, order.symbol, reason)
        return OrderResult(id=order_id, symbol=order.symbol, side=side, qty=order.qty,
                           status="rejected", reason=reason)

    def _feed_call(self, what: str, fn: Callable[..., T], *args: Any) -> T:
        try:
            return fn(*args)
        except BrokerError:
            raise
        except Exception as exc:
            raise BrokerError(f"paper broker: could not get {what} from the data feed: {exc}") from exc

    # ---- persistence ----------------------------------------------------------
    def _save(self, cash: float, holdings: dict[str, _Holding], fills: list[dict[str, Any]]) -> None:
        if self.state_path is None:
            return
        data = {
            "version": _STATE_VERSION,
            "currency": self.currency,
            "starting_cash": self.starting_cash,
            "cash": cash,
            "next_order_id": self._next_id,
            "positions": {s: {"qty": h.qty, "avg_entry_price": h.avg_entry_price} for s, h in holdings.items()},
            "fills": fills,
        }
        try:
            _atomic_write_json(self.state_path, data)
        except (OSError, TypeError, ValueError) as exc:
            raise BrokerError(f"could not save paper account to {self.state_path} ({exc}); "
                              "the order was NOT executed") from exc

    def _load(self, path: Path) -> None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("expected a JSON object")
            cash = data["cash"]
            if not _finite(cash) or cash < 0:
                raise ValueError(f"invalid cash {cash!r}")
            holdings = {}
            for symbol, pos in (data.get("positions") or {}).items():
                qty, avg = pos["qty"], pos["avg_entry_price"]
                if not (_finite(qty) and qty > 0 and _finite(avg) and avg > 0):
                    raise ValueError(f"invalid position {symbol!r}: {pos!r}")
                holdings[str(symbol)] = _Holding(float(qty), float(avg))
            fills = data.get("fills") or []
            if not isinstance(fills, list) or not all(isinstance(f, dict) for f in fills):
                raise ValueError("fills must be a list of objects")
            next_id = data.get("next_order_id", len(fills) + 1)
            if isinstance(next_id, bool) or not isinstance(next_id, int) or next_id < 1:
                raise ValueError(f"invalid next_order_id {next_id!r}")
            currency = data.get("currency", self.currency)
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            raise BrokerError(f"paper account file {path} is unreadable or corrupt ({exc}); fix it, or move it "
                              "aside to start a fresh paper account") from exc
        if currency != self.currency:
            raise BrokerError(f"paper account file {path} is in {currency}, not {self.currency}; use another "
                              "state_dir or move the file aside to start a fresh paper account")
        if data.get("starting_cash") not in (None, self.starting_cash):
            logger.info("Paper account %s was started with %s %s; keeping its balance (reset() applies %.2f)",
                        path, data.get("starting_cash"), currency, self.starting_cash)
        self._cash, self._holdings, self._fills = float(cash), holdings, fills[-MAX_FILLS:]
        self._next_id = next_id
        logger.info("Loaded paper account %s: cash %.2f %s, %d position(s)", path, self._cash, currency, len(holdings))


def _finite(value: object) -> bool:
    """A finite real number, numpy scalars included (bools, NaN and inf are not)."""
    return isinstance(value, numbers.Real) and not isinstance(value, bool) and math.isfinite(value)


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """Write JSON via a temp file in the same directory + fsync + os.replace."""
    text = json.dumps(data, indent=2, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        give_default_permissions(fd)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise


__all__ = ["MAX_FILLS", "PaperBroker"]
