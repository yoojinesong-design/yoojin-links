"""Risk management: position sizing, protective exits, daily loss limit.

Shared by the live engine and the backtester.
"""
from __future__ import annotations

import logging
import math
import numbers
from dataclasses import dataclass

from .models import Account, Action, Position, Signal

logger = logging.getLogger(__name__)

# Relative tolerance for price/percentage boundary checks, so that e.g. a price
# exactly 5% below entry triggers a 5% stop despite binary float rounding.
# Errs on the side of exiting / halting (the conservative direction).
_REL_EPS = 1e-9
# Largest accepted take-profit target (+1000% = 11x the entry price); anything
# above is almost certainly a typo.
MAX_TAKE_PROFIT_PCT = 1000.0


@dataclass
class RiskConfig:
    # % of equity you are willing to lose if a trade hits its stop-loss.
    # Only used when stop_loss_pct is set.
    risk_per_trade_pct: float = 1.0
    # Largest single position, as % of equity.
    max_position_pct: float = 20.0
    # Sum of all open positions' market value, as % of equity.
    max_total_exposure_pct: float = 80.0
    max_open_positions: int = 5
    # Stop opening new positions once equity is down this much vs the day's
    # starting equity. 0 or None disables it.
    max_daily_loss_pct: float | None = 3.0
    # Also sell everything when the daily loss limit is hit.
    flatten_on_daily_loss: bool = False
    # Protective exits relative to average entry price. None disables.
    # take_profit_pct may exceed 100 (up to MAX_TAKE_PROFIT_PCT).
    stop_loss_pct: float | None = 5.0
    take_profit_pct: float | None = None
    # New entries allowed per day (exits are always allowed).
    max_trades_per_day: int = 10
    # Never send an order smaller than this (quote currency). The broker's
    # own minimum is also enforced; the larger of the two wins.
    min_order_notional: float = 1.0
    # Keep this % of buying power unused as a buffer for fees/slippage.
    cash_buffer_pct: float = 1.0

    def validate(self) -> None:
        """Raise ValueError on nonsensical values."""
        errors: list[str] = []

        for name in ("risk_per_trade_pct", "max_position_pct", "max_total_exposure_pct"):
            value = getattr(self, name)
            if not _is_number(value):
                errors.append(f"{name} must be a number, got {value!r}")
            elif not 0 < value <= 100:
                errors.append(f"{name} must be > 0 and <= 100, got {value}")

        # Optional limits: None or 0 means "disabled". A loss can never exceed
        # 100%, but a profit target can (150 = sell at 2.5x the entry price).
        for name, upper in (("max_daily_loss_pct", 100.0), ("stop_loss_pct", 100.0),
                            ("take_profit_pct", MAX_TAKE_PROFIT_PCT)):
            value = getattr(self, name)
            if value is None:
                continue
            if not _is_number(value):
                errors.append(f"{name} must be a number or null, got {value!r}")
            elif not (value == 0 or 0 < value <= upper):
                errors.append(f"{name} must be between 0 and {upper:g} (0 or null disables it), got {value}")

        for name in ("max_open_positions", "max_trades_per_day"):
            value = getattr(self, name)
            if not isinstance(value, numbers.Integral) or isinstance(value, bool):
                errors.append(f"{name} must be a whole number, got {value!r}")
            elif value < 1:
                errors.append(f"{name} must be >= 1, got {value}")

        if not _is_number(self.min_order_notional):
            errors.append(f"min_order_notional must be a number, got {self.min_order_notional!r}")
        elif not 0 <= self.min_order_notional < math.inf:
            errors.append(f"min_order_notional must be >= 0, got {self.min_order_notional}")

        if not _is_number(self.cash_buffer_pct):
            errors.append(f"cash_buffer_pct must be a number, got {self.cash_buffer_pct!r}")
        elif not 0 <= self.cash_buffer_pct <= 50:
            errors.append(f"cash_buffer_pct must be between 0 and 50, got {self.cash_buffer_pct}")

        if not isinstance(self.flatten_on_daily_loss, bool):
            errors.append(f"flatten_on_daily_loss must be true or false, got {self.flatten_on_daily_loss!r}")

        if errors:
            raise ValueError("invalid risk settings: " + "; ".join(errors))


class RiskManager:
    def __init__(self, config: RiskConfig) -> None:
        # Fail fast: a bad limit must never reach the order path.
        config.validate()
        self.config = config

    def daily_loss_breached(self, equity: float, day_start_equity: float) -> bool:
        """True when (equity / day_start_equity - 1) * 100 <= -max_daily_loss_pct.
        Always False when the limit is disabled or day_start_equity <= 0."""
        limit = _enabled(self.config.max_daily_loss_pct)
        if limit is None or not _positive(day_start_equity) or not _is_number(equity):
            return False
        change_pct = (equity / day_start_equity - 1.0) * 100.0
        return change_pct <= -limit + _REL_EPS * limit

    def entry_qty(
        self,
        symbol: str,
        price: float,
        signal: Signal,
        account: Account,
        positions: dict[str, Position],
        broker_min_notional: float = 0.0,
    ) -> tuple[float, str]:
        """Quantity (base units) to buy for a new long entry, plus a short
        human-readable explanation. Returns (0.0, reason) when the entry must
        be skipped (max positions reached, exposure cap, not enough cash,
        below minimum notional, ...).

        Sizing:
          risk notional = equity * risk_per_trade_pct / stop_loss_pct
                          (so a stop-out loses ~risk_per_trade_pct of equity;
                          unbounded when stop_loss_pct is None)
          notional = min(risk notional,
                         equity * max_position_pct/100,
                         equity * max_total_exposure_pct/100 - current exposure,
                         buying_power * (1 - cash_buffer_pct/100))
          qty = notional / price   (the caller rounds with broker.normalize_qty)
        Reject if notional < max(min_order_notional, broker_min_notional).

        Never uses leverage: the spendable amount is min(buying_power, cash),
        so margin buying power is ignored.
        """
        cfg = self.config
        if signal.action is not Action.BUY:
            return 0.0, f"signal is {signal.action.value}, not buy"
        if not _positive(price):
            return 0.0, f"invalid price {price!r}"
        equity = account.equity
        if not _positive(equity):
            return 0.0, f"equity is not positive ({equity!r})"

        existing = positions.get(symbol)
        if existing is not None and existing.qty > 0:
            return 0.0, f"already holding {symbol}"
        open_positions = [p for p in positions.values() if p.qty > 0]
        if len(open_positions) >= cfg.max_open_positions:
            return 0.0, f"max open positions reached ({len(open_positions)}/{cfg.max_open_positions})"

        exposure = sum(p.market_value for p in open_positions)
        broker_min = 0.0 if broker_min_notional is None else broker_min_notional
        if any(math.isnan(v) for v in (account.buying_power, account.cash, exposure, broker_min)):
            logger.warning("entry_qty %s: NaN in account/positions/broker minimum; skipping entry", symbol)
            return 0.0, "cannot size: account, position or minimum values are not numbers"
        spendable = min(account.buying_power, account.cash)
        stop = _enabled(cfg.stop_loss_pct)
        caps = {
            "risk_per_trade": equity * cfg.risk_per_trade_pct / stop if stop else math.inf,
            "max_position": equity * cfg.max_position_pct / 100.0,
            "exposure_cap": equity * cfg.max_total_exposure_pct / 100.0 - exposure,
            "buying_power": spendable * (1.0 - cfg.cash_buffer_pct / 100.0),
        }
        binding = min(caps, key=caps.__getitem__)
        notional = caps[binding]

        if binding == "exposure_cap" and notional <= 0:
            return 0.0, f"exposure cap reached ({exposure:.2f} of {cfg.max_total_exposure_pct:g}% of equity)"
        if binding == "buying_power" and notional <= 0:
            return 0.0, f"no buying power ({spendable:.2f} available)"
        minimum = max(cfg.min_order_notional, broker_min)
        if not math.isfinite(notional) or notional <= 0 or notional < minimum:
            return 0.0, f"order value {notional:.2f} below minimum {minimum:.2f}, limited by {binding}"

        qty = notional / price
        return qty, f"buy {qty:.6g} @ {price:.6g} = {notional:.2f}, limited by {binding}"

    def exit_reason(self, position: Position, price: float) -> str | None:
        """'stop_loss' / 'take_profit' when ``price`` crosses the configured
        level relative to ``position.avg_entry_price``, else None."""
        if not _positive(price) or position.qty <= 0:
            return None
        stop = self.stop_price(position)
        if stop is not None and price <= stop * (1.0 + _REL_EPS):
            return "stop_loss"
        target = self.take_profit_price(position)
        if target is not None and price >= target * (1.0 - _REL_EPS):
            return "take_profit"
        return None

    def stop_price(self, position: Position) -> float | None:
        """Absolute stop-loss price for an open position, or None."""
        pct = _enabled(self.config.stop_loss_pct)
        if pct is None or not _positive(position.avg_entry_price):
            return None
        return position.avg_entry_price * (1.0 - pct / 100.0)

    def take_profit_price(self, position: Position) -> float | None:
        """Absolute take-profit price for an open position, or None."""
        pct = _enabled(self.config.take_profit_pct)
        if pct is None or not _positive(position.avg_entry_price):
            return None
        return position.avg_entry_price * (1.0 + pct / 100.0)


def _is_number(value: object) -> bool:
    """A finite real number, numpy scalars included (bools, NaN and inf are not)."""
    return isinstance(value, numbers.Real) and not isinstance(value, bool) and math.isfinite(value)


def _positive(value: object) -> bool:
    return _is_number(value) and value > 0  # type: ignore[operator]


def _enabled(pct: float | None) -> float | None:
    """An optional percentage limit, or None when it is disabled (None/0)."""
    return float(pct) if pct and pct > 0 else None


__all__ = ["MAX_TAKE_PROFIT_PCT", "RiskConfig", "RiskManager"]
