"""Broker adapters and the ``make_broker`` factory.

Vendor SDKs (alpaca-py, ccxt) are imported lazily inside the factory branches
so the ``sim`` broker works without them installed.
"""
from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

from .base import Broker, BrokerError

if TYPE_CHECKING:
    from ..config import BotConfig

logger = logging.getLogger(__name__)

PAPER_ACCOUNT_FILE = "paper_account.json"
CCXT_ENTRIES_FILE = "ccxt_entries.json"


def make_broker(cfg: BotConfig, env: Mapping[str, str] | None = None) -> Broker:
    """Build the broker described by ``cfg``.

    Paper unless ``cfg.mode == "live"`` AND the live confirmation env var is
    set. Credentials come from ``env`` (default ``os.environ``), never from
    the YAML file. Raises ``ConfigError`` for missing keys or bad settings.
    """
    from ..config import ConfigError, assert_live_allowed

    env = os.environ if env is None else env
    live = cfg.is_live
    if live:
        assert_live_allowed(cfg, env)   # defense in depth: the CLI checks too
    b = cfg.broker
    state_dir = Path(cfg.state_dir)
    paper_kwargs = dict(starting_cash=b.starting_cash, fee_pct=b.fee_pct, slippage_pct=b.slippage_pct,
                        state_path=state_dir / PAPER_ACCOUNT_FILE)

    if b.type == "sim":
        if live:
            raise ConfigError("broker type 'sim' uses made-up prices and cannot trade live; use mode: paper")
        from ..data import SyntheticFeed
        from .paper import PaperBroker
        logger.info("Broker: local paper account on synthetic prices (no network, no keys)")
        return _construct(PaperBroker, "sim", SyntheticFeed(seed=b.sim_seed), **paper_kwargs)

    if b.type == "alpaca":
        key, secret = _env(env, "ALPACA_API_KEY"), _env(env, "ALPACA_SECRET_KEY")
        if not key or not secret:
            kind = "LIVE" if live else "PAPER"
            raise ConfigError(
                f"Alpaca needs ALPACA_API_KEY and ALPACA_SECRET_KEY in your environment or .env file "
                f"({kind} trading keys). Get free paper-trading keys at https://app.alpaca.markets "
                "(switch to the Paper account, then 'API Keys' > Generate). See .env.example.")
        try:
            from .alpaca_broker import AlpacaBroker
        except ModuleNotFoundError as exc:
            _raise_if_sdk_missing(exc, "alpaca-py")
            raise
        logger.info("Broker: Alpaca %s account", "LIVE" if live else "paper")
        return _construct(AlpacaBroker, "alpaca", key, secret, paper=not live, data_feed=b.data_feed)

    if b.type == "ccxt":
        if not b.exchange:
            raise ConfigError("broker type ccxt needs broker.exchange (e.g. upbit, binance)")
        symbols = list(cfg.symbols)
        try:
            from .ccxt_broker import CCXTBroker
        except ModuleNotFoundError as exc:
            _raise_if_sdk_missing(exc, "ccxt")
            raise
        if not live and not b.use_sandbox:
            # Local simulated fills on the exchange's real PUBLIC prices. No keys are
            # passed on purpose: this broker cannot place a real order.
            from .paper import PaperBroker
            quote = _quote_currency(symbols)
            logger.info("Broker: local paper account on %s public prices (%s)", b.exchange, quote)
            feed = _construct(CCXTBroker, f"ccxt:{b.exchange}", b.exchange, symbols)
            return _construct(PaperBroker, "paper", feed, currency=quote, **paper_kwargs)
        key, secret = _env(env, "CCXT_API_KEY"), _env(env, "CCXT_SECRET")
        if not key or not secret:
            where = "testnet (sandbox)" if b.use_sandbox else "LIVE"
            raise ConfigError(
                f"{b.exchange} {where} trading needs CCXT_API_KEY and CCXT_SECRET (and CCXT_PASSWORD if "
                "the exchange uses an API passphrase) in your environment or .env file. See .env.example.")
        logger.info("Broker: %s %s account", b.exchange, "TESTNET" if b.use_sandbox else "LIVE")
        return _construct(CCXTBroker, f"ccxt:{b.exchange}", b.exchange, symbols,
                          api_key=key, secret=secret, password=_env(env, "CCXT_PASSWORD"),
                          sandbox=b.use_sandbox, entries_path=state_dir / CCXT_ENTRIES_FILE)

    raise ConfigError(f"unknown broker type {b.type!r}; use sim, alpaca or ccxt")


def _construct(cls, label: str, *args, **kwargs):
    """Instantiate an adapter, turning its setting errors into ConfigError."""
    from ..config import ConfigError

    try:
        return cls(*args, **kwargs)
    except ValueError as exc:
        raise ConfigError(f"{label} broker setup failed: {exc}") from exc


def _raise_if_sdk_missing(exc: ModuleNotFoundError, package: str) -> None:
    """Friendly ConfigError when a vendor SDK is not installed. Any other
    import error (a bug) is left for the caller to re-raise unchanged."""
    from ..config import ConfigError

    if (exc.name or "").split(".")[0] in ("alpaca", "ccxt"):
        raise ConfigError(f"the {package} package is not installed; run: pip install -r requirements.txt") from exc


def _env(env: Mapping[str, str], name: str) -> str | None:
    value = env.get(name)
    return (str(value).strip() or None) if value is not None else None


def _quote_currency(symbols: list[str]) -> str:
    """'BTC/KRW' -> 'KRW' (config validation guarantees one shared quote)."""
    return symbols[0].partition("/")[2].split(":")[0] if symbols else "USD"


__all__ = ["Broker", "BrokerError", "make_broker"]
