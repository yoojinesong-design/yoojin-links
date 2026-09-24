"""Broker interface. Every broker (Alpaca, CCXT exchange, local paper sim)
implements this so the engine and CLI never touch vendor SDKs directly."""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from ..models import Account, OrderRequest, OrderResult, Position, Side
from ..utils import floor_to_step


class BrokerError(Exception):
    """A broker/API call failed. The engine logs it and retries next tick."""


class Broker(ABC):
    name: str = "broker"

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

    # ---- orders ------------------------------------------------------------
    @abstractmethod
    def submit_order(self, order: OrderRequest) -> OrderResult:
        """Submit a market order. Must not raise for business rejections
        (insufficient funds, below minimum size): return status="rejected"
        with a reason. Raise BrokerError only for transport/API failures."""

    @abstractmethod
    def cancel_all_orders(self) -> None: ...

    def has_open_orders(self, symbol: str) -> bool:
        """True if an unfilled order for ``symbol`` is working. Used to avoid
        sending duplicate orders while a previous one is still pending."""
        return False

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
        """Emergency flatten: cancel working orders, then sell every position."""
        self.cancel_all_orders()
        results = []
        for symbol, pos in self.get_positions().items():
            if pos.qty > 0:
                results.append(self.submit_order(
                    OrderRequest(symbol=symbol, side=Side.SELL, qty=pos.qty, reason="flatten")))
        return results
