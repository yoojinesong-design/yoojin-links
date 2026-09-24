"""Strategy registry: look strategies up by the name used in config files."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .base import Strategy
from .donchian_breakout import DonchianBreakout
from .rsi_reversion import RSIReversion
from .sma_crossover import SMACrossover

STRATEGIES: dict[str, type[Strategy]] = {
    cls.name: cls for cls in (SMACrossover, RSIReversion, DonchianBreakout)
}


def create_strategy(name: str, params: dict[str, Any] | None = None) -> Strategy:
    """Build a strategy by name. Raises ValueError for an unknown name or bad
    params (unknown keys, wrong types, nonsensical values)."""
    cls = STRATEGIES.get(name) if isinstance(name, str) else None
    if cls is None:
        raise ValueError(f"Unknown strategy {name!r}; valid: {', '.join(sorted(STRATEGIES))}")
    if params is None:
        params = {}
    if not isinstance(params, Mapping) or not all(isinstance(k, str) for k in params):
        raise ValueError(f"{name}: params must be a mapping of name -> value, got {params!r}")
    return cls(**params)


__all__ = ["STRATEGIES", "Strategy", "create_strategy",
           "SMACrossover", "RSIReversion", "DonchianBreakout"]
