"""Load and validate the bot's YAML config.

The YAML file holds *settings only*. Secrets (API keys, webhook URLs, bot
tokens) come from environment variables / ``.env`` so a config file can be
shared or committed without leaking credentials.

Every problem raises :class:`ConfigError` with a message that says what is
wrong and how to fix it, before any broker is contacted.
"""
from __future__ import annotations

import difflib
import logging
import math
import numbers
import os
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from .risk import RiskConfig
from .strategies import create_strategy
from .utils import SUPPORTED_TIMEFRAMES

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """The config (or environment) is invalid; the message explains the fix."""


LIVE_CONFIRM_ENV = "LIVE_TRADING_CONFIRM"
LIVE_CONFIRM_VALUE = "I_ACCEPT_THE_RISK"

MODES = ("paper", "live")
BROKER_TYPES = ("sim", "alpaca", "ccxt")
ALPACA_DATA_FEEDS = ("iex", "sip")
MIN_POLL_INTERVAL_SECONDS = 5
MAX_FEE_OR_SLIPPAGE_PCT = 5.0

# Environment variables holding secrets (documented in .env.example).
ENV_NOTIFY_WEBHOOK_URL = "NOTIFY_WEBHOOK_URL"
ENV_TELEGRAM_BOT_TOKEN = "TELEGRAM_BOT_TOKEN"
ENV_TELEGRAM_CHAT_ID = "TELEGRAM_CHAT_ID"
SECRET_ENV_VARS = ("ALPACA_API_KEY", "ALPACA_SECRET_KEY", "CCXT_API_KEY", "CCXT_SECRET",
                   "CCXT_PASSWORD", ENV_NOTIFY_WEBHOOK_URL, ENV_TELEGRAM_BOT_TOKEN, ENV_TELEGRAM_CHAT_ID)

# A YAML key whose normalised name (lowercase, letters/digits only) contains
# any of these is treated as a credential and refused.
_SECRET_MARKERS = ("apikey", "secret", "password", "passwd", "passphrase", "token",
                   "privatekey", "webhook")
# notify settings that exist but must come from the environment.
_NOTIFY_ENV_KEYS = {"webhook_url": ENV_NOTIFY_WEBHOOK_URL,
                    "telegram_bot_token": ENV_TELEGRAM_BOT_TOKEN,
                    "telegram_chat_id": ENV_TELEGRAM_CHAT_ID}


@dataclass
class BrokerConfig:
    type: str = "sim"                 # sim | alpaca | ccxt
    data_feed: str = "iex"            # alpaca: iex (free) | sip (paid)
    exchange: str | None = None       # ccxt exchange id, e.g. "upbit", "binance"
    use_sandbox: bool = False         # ccxt: exchange testnet with testnet keys
    starting_cash: float = 10_000.0   # sim + local paper + backtest
    fee_pct: float = 0.1              # sim + local paper + backtest
    slippage_pct: float = 0.05        # sim + local paper + backtest
    sim_seed: int = 42


@dataclass
class StrategyConfig:
    name: str = "sma_crossover"
    params: dict = field(default_factory=dict)


@dataclass
class NotifyConfig:
    # Secrets: filled from the environment only, and hidden from repr() so a
    # logged/printed config never leaks them.
    webhook_url: str | None = field(default=None, repr=False)          # env NOTIFY_WEBHOOK_URL (Discord/Slack)
    telegram_bot_token: str | None = field(default=None, repr=False)   # env TELEGRAM_BOT_TOKEN
    telegram_chat_id: str | None = field(default=None, repr=False)     # env TELEGRAM_CHAT_ID
    on_trade: bool = True
    on_error: bool = True


@dataclass
class BotConfig:
    mode: str = "paper"                   # paper | live
    broker: BrokerConfig = field(default_factory=BrokerConfig)
    symbols: list[str] = field(default_factory=list)
    timeframe: str = "1d"
    bars_lookback: int = 300
    timezone: str = "America/New_York"    # defines the trading "day" for daily limits (not on Alpaca: New York)
    poll_interval_seconds: int = 300
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    notify: NotifyConfig = field(default_factory=NotifyConfig)
    state_dir: Path = Path("state")       # relative paths resolved against the config file's directory
    log_dir: Path = Path("logs")
    config_path: Path | None = None
    # By default the bot manages (and sells) only what it bought itself; a
    # holding already in the account in one of `symbols` is left alone. True
    # lets it take over such holdings: stop-loss, strategy exits, flatten.
    adopt_existing_positions: bool = False

    @property
    def is_live(self) -> bool:
        """True only for real-money trading (``mode: live``)."""
        return self.mode == "live"


_TOP_KEYS = ("mode", "broker", "symbols", "timeframe", "bars_lookback", "timezone",
             "poll_interval_seconds", "strategy", "risk", "notify", "state_dir", "log_dir",
             "adopt_existing_positions")
_BROKER_KEYS = tuple(f.name for f in fields(BrokerConfig))
_STRATEGY_KEYS = ("name", "params")
_RISK_KEYS = tuple(f.name for f in fields(RiskConfig))
_NOTIFY_KEYS = ("on_trade", "on_error")


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------
def load_config(path: str | Path, env: Mapping[str, str] | None = None) -> BotConfig:
    """Read, validate and return the config at ``path``.

    ``env`` (default ``os.environ``) supplies the notification secrets.
    Raises :class:`ConfigError` for anything invalid.
    """
    env = os.environ if env is None else env
    config_path = Path(path).expanduser().resolve()
    if not config_path.is_file():
        raise ConfigError(f"Config file not found: {config_path}. "
                          "Copy one of the examples (e.g. configs/demo.yaml) and pass it with -c.")
    try:
        text = config_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigError(f"Cannot read config file {config_path}: {exc}") from exc
    try:
        raw = yaml.load(text, Loader=_StrictLoader)  # noqa: S506 - SafeLoader subclass
    except yaml.YAMLError as exc:
        raise ConfigError(f"{config_path} is not valid YAML (check indentation and colons):\n{exc}") from exc

    try:
        cfg = _build(raw, config_path, env)
    except ConfigError as exc:
        raise ConfigError(f"{config_path}: {exc}") from exc
    logger.debug("Loaded config %s (mode=%s, broker=%s)", config_path, cfg.mode, cfg.broker.type)
    if cfg.is_live:
        logger.warning("Config %s requests LIVE trading with real money", config_path)
    return cfg


def state_dir_only(path: str | Path) -> Path:
    """The state folder a config uses, WITHOUT validating anything else, so
    the emergency commands (``kill``/``resume``) still reach a running bot
    after its config was edited into an invalid state (a YAML syntax error
    included: then the top-level ``state_dir:`` line is read as text).
    Resolved exactly like :func:`load_config` does. Raises ConfigError only
    when the file cannot be read or ``state_dir`` itself is invalid."""
    config_path = Path(path).expanduser().resolve()
    try:
        text = config_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigError(f"Cannot read config file {config_path}: {exc}") from exc
    try:
        raw = yaml.load(text, Loader=_StrictLoader)  # noqa: S506
    except yaml.YAMLError:
        line = re.search(r"^state_dir:[ \t]*(.*?)[ \t]*(?:#.*)?$", text, re.MULTILINE)
        raw = {"state_dir": line.group(1).strip("'\"")} if line and line.group(1) else {}
    value = raw.get("state_dir", "state") if isinstance(raw, Mapping) else "state"
    return _path(value, "state_dir", config_path.parent)


def assert_live_allowed(cfg: BotConfig, env: Mapping[str, str] | None = None) -> None:
    """Refuse to trade real money unless the user opted in twice.

    No-op in paper mode. In live mode, ``LIVE_TRADING_CONFIRM`` must be set to
    exactly ``I_ACCEPT_THE_RISK`` (case-sensitive, no extra spaces).
    """
    if not cfg.is_live:
        return
    env = os.environ if env is None else env
    if env.get(LIVE_CONFIRM_ENV) == LIVE_CONFIRM_VALUE:
        return
    state = "is not set" if env.get(LIVE_CONFIRM_ENV) is None else "is set, but not to the exact required value"
    raise ConfigError(
        f"Live trading refused: the config says mode: live, but {LIVE_CONFIRM_ENV} {state}. "
        "Live mode sends REAL orders with REAL money and you can lose it. "
        "Backtest and paper-trade first. If you really mean it, set "
        f"{LIVE_CONFIRM_ENV}={LIVE_CONFIRM_VALUE} in your environment or .env file "
        "(exact spelling, uppercase). Otherwise change the config to mode: paper."
    )


# ---------------------------------------------------------------------------
# building / validation
# ---------------------------------------------------------------------------
def _build(raw: Any, config_path: Path, env: Mapping[str, str]) -> BotConfig:
    if raw is None:
        raw = {}
    if not isinstance(raw, Mapping):
        raise ConfigError("the top level must be a mapping of settings (key: value lines), "
                          f"got {type(raw).__name__}")
    _reject_secrets(raw)
    top = _section(raw, "top level", _TOP_KEYS)

    mode = _choice(top.get("mode", "paper"), "mode", MODES)
    broker = _broker(top.get("broker"))
    if broker.type == "sim" and mode == "live":
        raise ConfigError("broker type 'sim' is a simulator with made-up prices and cannot trade live. "
                          "Use mode: paper, or broker type alpaca/ccxt for real trading.")
    symbols = _symbols(top.get("symbols"), broker.type)
    timeframe = top.get("timeframe", "1d")
    if not isinstance(timeframe, str) or timeframe.strip() not in SUPPORTED_TIMEFRAMES:
        raise ConfigError(f"timeframe {timeframe!r} is not supported; use one of "
                          f"{', '.join(SUPPORTED_TIMEFRAMES)} (lowercase m = minutes)")
    timeframe = timeframe.strip()

    strategy = _strategy(top.get("strategy"))
    lookback = _integer(top.get("bars_lookback", 300), "bars_lookback", minimum=1)
    built = _create_strategy(strategy)
    needed = built.min_bars + 1
    if lookback < needed:
        raise ConfigError(f"bars_lookback is {lookback}, but strategy {strategy.name} {built.params} "
                          f"needs {built.min_bars} closed bars to warm up; set bars_lookback to at least {needed}")

    poll = _integer(top.get("poll_interval_seconds", 300), "poll_interval_seconds",
                    minimum=MIN_POLL_INTERVAL_SECONDS)
    tz = _timezone(top.get("timezone", "America/New_York"))
    base_dir = config_path.parent
    return BotConfig(
        mode=mode,
        broker=broker,
        symbols=symbols,
        timeframe=timeframe,
        bars_lookback=lookback,
        timezone=tz,
        poll_interval_seconds=poll,
        strategy=strategy,
        risk=_risk(top.get("risk")),
        notify=_notify(top.get("notify"), env),
        state_dir=_path(top.get("state_dir", "state"), "state_dir", base_dir),
        log_dir=_path(top.get("log_dir", "logs"), "log_dir", base_dir),
        config_path=config_path,
        adopt_existing_positions=_boolean(top.get("adopt_existing_positions", False),
                                          "adopt_existing_positions"),
    )


def _broker(raw: Any) -> BrokerConfig:
    sec = _section(raw, "broker", _BROKER_KEYS)
    defaults = BrokerConfig()
    kind = _choice(sec.get("type", defaults.type), "broker.type", BROKER_TYPES)
    data_feed = _choice(sec.get("data_feed", defaults.data_feed), "broker.data_feed", ALPACA_DATA_FEEDS,
                        hint="'iex' is free, 'sip' needs a paid Alpaca market-data plan")
    exchange = sec.get("exchange")
    if exchange is not None:
        exchange = _text(exchange, "broker.exchange").lower()
    if kind == "ccxt" and not exchange:
        raise ConfigError("broker type ccxt needs broker.exchange, the ccxt exchange id "
                          "(e.g. exchange: upbit, binance, kraken, coinbase)")
    fee = _number(sec.get("fee_pct", defaults.fee_pct), "broker.fee_pct")
    slippage = _number(sec.get("slippage_pct", defaults.slippage_pct), "broker.slippage_pct")
    for name, value in (("fee_pct", fee), ("slippage_pct", slippage)):
        if not 0 <= value <= MAX_FEE_OR_SLIPPAGE_PCT:
            raise ConfigError(f"broker.{name} must be between 0 and {MAX_FEE_OR_SLIPPAGE_PCT:g} "
                              f"(a percentage, e.g. 0.1 means 0.1%), got {value:g}")
    cash = _number(sec.get("starting_cash", defaults.starting_cash), "broker.starting_cash")
    if cash <= 0:
        raise ConfigError(f"broker.starting_cash must be > 0, got {cash:g}")
    return BrokerConfig(
        type=kind,
        data_feed=data_feed,
        exchange=exchange,
        use_sandbox=_boolean(sec.get("use_sandbox", defaults.use_sandbox), "broker.use_sandbox"),
        starting_cash=cash,
        fee_pct=fee,
        slippage_pct=slippage,
        sim_seed=_integer(sec.get("sim_seed", defaults.sim_seed), "broker.sim_seed", minimum=0),
    )


def _symbols(raw: Any, broker_type: str) -> list[str]:
    example = {"alpaca": "[SPY, QQQ]", "ccxt": "[BTC/USDT, ETH/USDT]"}.get(broker_type, "[DEMO1, DEMO2]")
    if raw is None:
        raise ConfigError(f"symbols is required: list what to trade, e.g. symbols: {example}")
    if not isinstance(raw, list) or not raw:
        raise ConfigError(f"symbols must be a non-empty list, e.g. symbols: {example}; got {raw!r}")
    out: list[str] = []
    for item in raw:
        if isinstance(item, bool):
            raise ConfigError(f"symbols: YAML read one entry as {item!r} (words like ON/YES/NO/OFF are "
                              'booleans in YAML); put the ticker in quotes, e.g. "ON"')
        if not isinstance(item, str) or not item.strip():
            raise ConfigError(f"symbols: every entry must be text, got {item!r}; "
                              'wrap numeric codes in quotes, e.g. "005930"')
        symbol = item.strip()
        if any(ch.isspace() for ch in symbol):
            raise ConfigError(f"symbols: {symbol!r} contains whitespace")
        if broker_type == "alpaca":
            symbol = symbol.upper()
            if "/" in symbol:
                raise ConfigError(f"symbols: {symbol} looks like a crypto pair, but broker type alpaca trades "
                                  "US stocks/ETFs only (e.g. SPY). Use broker type ccxt for crypto.")
        elif broker_type == "ccxt":
            base, _, quote = symbol.partition("/")
            if not base or not quote or "/" in quote:
                raise ConfigError(f"symbols: {symbol!r} is not a ccxt market symbol; use BASE/QUOTE, "
                                  "e.g. BTC/USDT or BTC/KRW")
            if ":" in quote:
                raise ConfigError(f"symbols: {symbol} is a futures/perpetual contract; only spot markets "
                                  "(e.g. BTC/USDT) are supported: this bot never uses leverage")
        if symbol in out:
            raise ConfigError(f"symbols: {symbol} is listed twice")
        out.append(symbol)
    if broker_type == "ccxt":
        quotes = sorted({s.partition("/")[2] for s in out})
        if len(quotes) > 1:
            raise ConfigError(f"symbols: all ccxt symbols must share one quote currency (the account "
                              f"currency), got {', '.join(quotes)}")
    return out


def _strategy(raw: Any) -> StrategyConfig:
    sec = _section(raw, "strategy", _STRATEGY_KEYS)
    name = _text(sec.get("name", StrategyConfig().name), "strategy.name")
    params = sec.get("params")
    if params is None:
        params = {}
    if not isinstance(params, Mapping):
        raise ConfigError(f"strategy.params must be a mapping (name: value lines), got {params!r}")
    return StrategyConfig(name=name, params=dict(params))


def _create_strategy(cfg: StrategyConfig):
    try:
        return create_strategy(cfg.name, dict(cfg.params))
    except (ValueError, TypeError) as exc:
        raise ConfigError(f"strategy: {exc}") from exc


def _risk(raw: Any) -> RiskConfig:
    sec = _section(raw, "risk", _RISK_KEYS)
    risk = RiskConfig(**sec)
    try:
        risk.validate()
    except ValueError as exc:
        raise ConfigError(f"risk: {exc}") from exc
    return risk


def _notify(raw: Any, env: Mapping[str, str]) -> NotifyConfig:
    if isinstance(raw, Mapping):
        for key in raw:
            if key in _NOTIFY_ENV_KEYS:
                raise ConfigError(f"notify.{key} must not be in the YAML file; set {_NOTIFY_ENV_KEYS[key]} "
                                  "in your .env file instead (see .env.example)")
    sec = _section(raw, "notify", _NOTIFY_KEYS)
    token, chat_id = _env_value(env, ENV_TELEGRAM_BOT_TOKEN), _env_value(env, ENV_TELEGRAM_CHAT_ID)
    if bool(token) != bool(chat_id):
        # Telegram needs both: with only one, every alert would be dropped silently.
        have, missing = ((ENV_TELEGRAM_BOT_TOKEN, ENV_TELEGRAM_CHAT_ID) if token
                         else (ENV_TELEGRAM_CHAT_ID, ENV_TELEGRAM_BOT_TOKEN))
        raise ConfigError(f"{have} is set but {missing} is not, so no Telegram alert could be sent. Set "
                          f"{missing} in your .env file too (see .env.example: the chat id comes from "
                          f"https://api.telegram.org/bot<token>/getUpdates), or remove {have}.")
    return NotifyConfig(
        webhook_url=_env_value(env, ENV_NOTIFY_WEBHOOK_URL),
        telegram_bot_token=token,
        telegram_chat_id=chat_id,
        on_trade=_boolean(sec.get("on_trade", True), "notify.on_trade"),
        on_error=_boolean(sec.get("on_error", True), "notify.on_error"),
    )


def _timezone(raw: Any) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ConfigError(f"timezone must be an IANA time zone name such as UTC, America/New_York "
                          f"or Asia/Seoul, got {raw!r}")
    name = raw.strip()
    try:
        ZoneInfo(name)
    except Exception as exc:  # ZoneInfoNotFoundError, ValueError, OSError
        raise ConfigError(f"timezone {name!r} is not a known time zone; use an IANA name such as UTC, "
                          "America/New_York or Asia/Seoul (case-sensitive)") from exc
    return name


def _path(raw: Any, where: str, base_dir: Path) -> Path:
    path = Path(_text(raw, where)).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


# ---------------------------------------------------------------------------
# small validators
# ---------------------------------------------------------------------------
def _reject_secrets(node: Any, where: str = "") -> None:
    """Refuse any key that looks like a credential, anywhere in the document."""
    if isinstance(node, Mapping):
        for key, value in node.items():
            here = f"{where}.{key}" if where else str(key)
            normalised = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if any(marker in normalised for marker in _SECRET_MARKERS):
                raise ConfigError(
                    f"{here!r} looks like a secret. Never put API keys, passwords, tokens or webhook URLs "
                    "in the YAML config (it is easy to commit or share by accident). Delete it and set it "
                    f"in your .env file instead (see .env.example: {', '.join(SECRET_ENV_VARS)}). "
                    "If this file was already shared or committed, revoke that credential now.")
            _reject_secrets(value, here)
    elif isinstance(node, list):
        for i, value in enumerate(node):
            _reject_secrets(value, f"{where}[{i}]")


def _section(raw: Any, where: str, allowed: Iterable[str]) -> dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise ConfigError(f"{where} must be a mapping (key: value lines), got {raw!r}")
    allowed = tuple(allowed)
    for key in raw:
        if not isinstance(key, str) or key not in allowed:
            prefix = "" if where == "top level" else f"{where}."
            close = difflib.get_close_matches(str(key), allowed, n=1)
            hint = f" Did you mean {prefix}{close[0]}?" if close else ""
            raise ConfigError(f"unknown setting {prefix}{key}.{hint} Valid keys here: {', '.join(allowed)}")
    return dict(raw)


def _choice(value: Any, where: str, options: tuple[str, ...], hint: str = "") -> str:
    if isinstance(value, str) and value.strip().lower() in options:
        return value.strip().lower()
    extra = f" ({hint})" if hint else ""
    raise ConfigError(f"{where} must be one of {', '.join(options)}{extra}, got {value!r}")


def _text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{where} must be non-empty text, got {value!r}")
    return value.strip()


def _number(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, numbers.Real) or not math.isfinite(value):
        raise ConfigError(f"{where} must be a number, got {value!r}")
    return float(value)


def _integer(value: Any, where: str, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, numbers.Integral):
        raise ConfigError(f"{where} must be a whole number, got {value!r}")
    if minimum is not None and value < minimum:
        raise ConfigError(f"{where} must be at least {minimum}, got {value}")
    return int(value)


def _boolean(value: Any, where: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"{where} must be true or false, got {value!r}")
    return value


def _env_value(env: Mapping[str, str], name: str) -> str | None:
    value = env.get(name)
    if value is None:
        return None
    return str(value).strip() or None


class _StrictLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate keys (YAML silently keeps the last one,
    which could quietly replace e.g. a whole ``risk:`` section)."""


def _construct_mapping(loader: _StrictLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
    seen: set[str] = set()
    for key_node, _ in node.value:
        if isinstance(key_node, yaml.ScalarNode) and key_node.tag != "tag:yaml.org,2002:merge":
            if key_node.value in seen:
                raise yaml.constructor.ConstructorError(
                    "while reading a mapping", node.start_mark,
                    f"found duplicate key {key_node.value!r}", key_node.start_mark)
            seen.add(key_node.value)
    return loader.construct_mapping(node, deep=deep)


_StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


__all__ = [
    "ConfigError", "LIVE_CONFIRM_ENV", "LIVE_CONFIRM_VALUE", "BrokerConfig", "StrategyConfig",
    "NotifyConfig", "BotConfig", "load_config", "assert_live_allowed", "state_dir_only",
]
