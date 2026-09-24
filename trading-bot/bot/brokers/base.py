"""Broker interface. Every broker (Alpaca, CCXT exchange, local paper sim)
implements this so the engine and CLI never touch vendor SDKs directly."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass

import pandas as pd

from ..models import Account, OrderRequest, OrderResult, Position, Side
from ..utils import floor_to_step

# Every client order id the engine sends starts with this, so the bot can tell
# its own working orders from ones a person placed on the same account.
BOT_ORDER_PREFIX = "bot-"


class BrokerError(Exception):
    """A broker/API call failed. The engine logs it and retries next tick."""


class FlattenIncomplete(BrokerError):
    """``close_all_positions`` could not send every sell. ``results`` holds the
    orders that were sent (so they are still reported), ``errors`` the rest."""

    def __init__(self, results: list[OrderResult], errors: list[str]) -> None:
        super().__init__("could not send every sell: " + "; ".join(errors))
        self.results = results
        self.errors = errors


@dataclass(frozen=True)
class OpenOrder:
    """A working (not yet filled, cancelled or expired) order on the venue."""
    id: str
    symbol: str
    side: Side | None = None
    # True when this bot placed it (its client order id starts with
    # BOT_ORDER_PREFIX, or the adapter remembers sending it).
    placed_by_bot: bool = False


class Broker(ABC):
    name: str = "broker"
    # True when every holding in this account was bought through this bot (a
    # local simulated account), so nothing in it can be someone else's. For a
    # real brokerage/exchange account (False) the engine manages and sells
    # only what it bought itself; see BotState.owned.
    bot_owned_account: bool = False

    # ---- market data -------------------------------------------------------
    @abstractmethod
    def get_bars(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        """Most recent ``limit`` bars in canonical form (see ``utils.validate_bars``).

        May include the still-forming last bar; callers drop it with
        ``utils.drop_incomplete_bars``.
        """

    @abstractmethod
    def get_latest_price(self, symbol: str) -> float:
        """Last traded (or mid) price."""

    # ---- account -----------------------------------------------------------
    @abstractmethod
    def get_account(self) -> Account: ...

    @abstractmethod
    def get_positions(self) -> dict[str, Position]:
        """Open long positions keyed by the SAME symbol string used in config."""

    def short_positions(self) -> dict[str, Position]:
        """Short positions (``qty`` < 0) as of the most recent
        :meth:`get_positions` call. The bot never opens one, but a margin
        account can hold a short a person opened, which a BUY would cover.
        Brokers that cannot be short (spot crypto, the paper account) have none."""
        return {}

    # ---- orders ------------------------------------------------------------
    @abstractmethod
    def submit_order(self, order: OrderRequest) -> OrderResult:
        """Submit a market order. Must not raise for business rejections
        (insufficient funds, below minimum size): return status="rejected"
        with a reason. Raise BrokerError only for transport/API failures."""

    @abstractmethod
    def cancel_all_orders(self) -> None: ...

    def open_orders(self, symbol: str) -> list[OpenOrder]:
        """Working orders for ``symbol``: the bot's own AND any other order on
        the account (e.g. one placed by hand). Brokers whose orders fill
        instantly have none. An adapter that only overrides ``has_open_orders``
        gets one unidentified order, treated as the bot's own (so it still
        blocks duplicate orders)."""
        if type(self).has_open_orders is not Broker.has_open_orders and self.has_open_orders(symbol):
            return [OpenOrder(id="", symbol=symbol, placed_by_bot=True)]
        return []

    def has_open_orders(self, symbol: str) -> bool:
        """True if any unfilled order for ``symbol`` is working."""
        return bool(self.open_orders(symbol))

    def order_filled_qty(self, symbol: str, client_order_id: str, order_id: str = "") -> float | None:
        """How much of one of the bot's orders filled, once it is no longer
        working, looked up by the broker's order id (else by the client order
        id the bot sent): 0.0 for an order the broker never received. None when
        the broker cannot tell (the engine then goes by how the holding
        changed). Raises BrokerError while the order is still working."""
        return None

    def cancel_order(self, symbol: str, order_id: str) -> None:
        """Cancel one working order of ``symbol`` by its id (one that has
        already filled or gone is not an error). Brokers that can have working
        orders override this; the default refuses rather than cancelling
        anything else."""
        raise BrokerError(f"{self.name} cannot cancel order {order_id or '?'} ({symbol})")

    def cancel_orders(self, symbols: Sequence[str]) -> None:
        """Cancel the working orders of ``symbols`` only (never other symbols'
        orders). Brokers that can have working orders override this; the
        default refuses rather than silently leaving an order in place."""
        for symbol in symbols:
            if self.open_orders(symbol):
                raise BrokerError(f"{self.name} cannot cancel the working orders for {symbol}")

    # ---- market rules ------------------------------------------------------
    def is_market_open(self) -> bool:
        """Crypto trades 24/7; stock brokers override with the exchange clock."""
        return True

    def min_order_notional(self, symbol: str) -> float:
        """Smallest order value (quote currency) the venue accepts."""
        return 1.0

    def normalize_qty(self, symbol: str, qty: float) -> float:
        """Round an order quantity DOWN to what the venue accepts."""
        return floor_to_step(qty, 1e-6)

    # ---- convenience -------------------------------------------------------
    def close_all_positions(self) -> list[OrderResult]:
        """Emergency flatten (the ``flatten`` command): cancel working orders,
        then sell every position this broker reports. Alpaca reports (and
        closes) every position in the account; the engine's own daily-loss
        flatten sells only the bot's positions instead. One sell that fails
        does not stop the others: :class:`FlattenIncomplete` is raised at the
        end, carrying the results of those that were sent."""
        self.cancel_all_orders()
        results: list[OrderResult] = []
        errors: list[str] = []
        for symbol, pos in self.get_positions().items():
            if pos.qty > 0:
                try:
                    results.append(self.submit_order(
                        OrderRequest(symbol=symbol, side=Side.SELL, qty=pos.qty, reason="flatten")))
                except BrokerError as exc:
                    errors.append(f"{symbol}: {exc}")
        if errors:
            raise FlattenIncomplete(results, errors)
        return results
