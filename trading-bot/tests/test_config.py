"""Tests for bot.config (loading/validation, live-trading gate) and the
bot.brokers.make_broker factory. Fully offline: broker adapters are stubbed."""
from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any

import pytest
import yaml

import bot.config as config_mod
from bot.config import (
    LIVE_CONFIRM_ENV,
    LIVE_CONFIRM_VALUE,
    BotConfig,
    BrokerConfig,
    ConfigError,
    NotifyConfig,
    StrategyConfig,
    assert_live_allowed,
    load_config,
)
from bot.risk import RiskConfig

ROOT = Path(__file__).resolve().parents[1]
LIVE_ENV = {LIVE_CONFIRM_ENV: LIVE_CONFIRM_VALUE}


def base_config(**overrides: Any) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "mode": "paper",
        "broker": {"type": "sim"},
        "symbols": ["AAA", "BBB"],
        "timeframe": "1d",
        "bars_lookback": 100,
        "timezone": "UTC",
        "poll_interval_seconds": 60,
        "strategy": {"name": "sma_crossover", "params": {"fast": 5, "slow": 20}},
    }
    cfg.update(overrides)
    return cfg


def write(tmp_path: Path, data: dict[str, Any] | str, name: str = "config.yaml") -> Path:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def load(tmp_path: Path, env: dict[str, str] | None = None, **overrides: Any) -> BotConfig:
    return load_config(write(tmp_path, base_config(**overrides)), env={} if env is None else env)


def with_broker(**broker: Any) -> dict[str, Any]:
    return {"broker": broker}


# ---------------------------------------------------------------------------
# happy path, defaults, normalisation
# ---------------------------------------------------------------------------
def test_minimal_config_loads_with_defaults(tmp_path):
    cfg = load(tmp_path)
    assert cfg.mode == "paper" and not cfg.is_live
    assert cfg.broker == BrokerConfig(type="sim")
    assert cfg.symbols == ["AAA", "BBB"]
    assert cfg.timeframe == "1d" and cfg.bars_lookback == 100 and cfg.poll_interval_seconds == 60
    assert cfg.strategy == StrategyConfig("sma_crossover", {"fast": 5, "slow": 20})
    assert cfg.risk == RiskConfig()
    assert cfg.notify == NotifyConfig()
    assert cfg.config_path == (tmp_path / "config.yaml").resolve()


def test_omitted_optional_sections_use_dataclass_defaults(tmp_path):
    cfg = load_config(write(tmp_path, {"symbols": ["X"], "bars_lookback": 60}), env={})
    assert cfg.broker.type == "sim" and cfg.mode == "paper"
    assert cfg.timeframe == "1d" and cfg.timezone == "America/New_York" and cfg.poll_interval_seconds == 300
    assert cfg.strategy.name == "sma_crossover" and cfg.strategy.params == {}


def test_risk_section_maps_onto_risk_config(tmp_path):
    risk = {"risk_per_trade_pct": 0.5, "stop_loss_pct": None, "take_profit_pct": 12,
            "max_open_positions": 3, "flatten_on_daily_loss": True, "max_daily_loss_pct": 0}
    cfg = load(tmp_path, risk=risk)
    assert cfg.risk.risk_per_trade_pct == 0.5 and cfg.risk.stop_loss_pct is None
    assert cfg.risk.take_profit_pct == 12 and cfg.risk.max_open_positions == 3
    assert cfg.risk.flatten_on_daily_loss is True and cfg.risk.max_daily_loss_pct == 0


def test_broker_values_are_parsed_and_normalised(tmp_path):
    cfg = load(tmp_path, broker={"type": " CCXT ", "exchange": " Upbit ", "use_sandbox": True,
                                 "starting_cash": 1_000_000, "fee_pct": 0, "slippage_pct": 5, "sim_seed": 7},
               symbols=["BTC/KRW", "ETH/KRW"])
    assert cfg.broker == BrokerConfig(type="ccxt", exchange="upbit", use_sandbox=True,
                                      starting_cash=1_000_000.0, fee_pct=0.0, slippage_pct=5.0, sim_seed=7)
    assert isinstance(cfg.broker.starting_cash, float)


def test_mode_is_case_insensitive_and_live_sets_is_live(tmp_path):
    cfg = load(tmp_path, mode="Live", broker={"type": "alpaca"}, symbols=["SPY"])
    assert cfg.mode == "live" and cfg.is_live


def test_alpaca_symbols_are_uppercased(tmp_path):
    cfg = load(tmp_path, broker={"type": "alpaca", "data_feed": "SIP"}, symbols=["spy", " qqq "])
    assert cfg.symbols == ["SPY", "QQQ"] and cfg.broker.data_feed == "sip"


def test_ccxt_and_sim_symbols_keep_their_case(tmp_path):
    assert load(tmp_path, broker={"type": "ccxt", "exchange": "binance"},
                symbols=["BTC/USDT", "1000SHIB/USDT"]).symbols == ["BTC/USDT", "1000SHIB/USDT"]
    assert load(tmp_path, symbols=["demo1"]).symbols == ["demo1"]


def test_timeframe_and_timezone_whitespace_is_stripped(tmp_path):
    cfg = load(tmp_path, timeframe=" 4h ", timezone=" Asia/Seoul ")
    assert cfg.timeframe == "4h" and cfg.timezone == "Asia/Seoul"


def test_strategy_params_may_be_omitted_or_null(tmp_path):
    assert load(tmp_path, strategy={"name": "sma_crossover"}).strategy.params == {}
    assert load(tmp_path, strategy={"name": "sma_crossover", "params": None}).strategy.params == {}


def test_empty_sections_are_treated_as_defaults(tmp_path):
    text = "symbols: [X]\nbars_lookback: 60\nbroker:\nrisk:\nnotify:\nstrategy:\n"
    cfg = load_config(write(tmp_path, text), env={})
    assert cfg.broker == BrokerConfig() and cfg.risk == RiskConfig() and cfg.notify == NotifyConfig()


# ---------------------------------------------------------------------------
# paths
# ---------------------------------------------------------------------------
def test_default_state_and_log_dirs_are_next_to_the_config_file(tmp_path, monkeypatch):
    elsewhere = tmp_path / "cwd"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    path = write(tmp_path, base_config(), name="sub/dir/bot.yaml")
    cfg = load_config(path, env={})
    assert cfg.state_dir == (tmp_path / "sub/dir/state").resolve()
    assert cfg.log_dir == (tmp_path / "sub/dir/logs").resolve()


def test_relative_paths_resolve_against_config_dir_not_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = write(tmp_path, base_config(state_dir="../st", log_dir="out/logs"), name="conf/c.yaml")
    cfg = load_config("conf/c.yaml", env={})   # relative config path, too
    assert cfg.config_path == path.resolve()
    assert cfg.state_dir == (tmp_path / "st").resolve()
    assert cfg.log_dir == (tmp_path / "conf/out/logs").resolve()


def test_absolute_and_home_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    cfg = load(tmp_path, state_dir=str(tmp_path / "abs_state"), log_dir="~/botlogs")
    assert cfg.state_dir == (tmp_path / "abs_state").resolve()
    assert cfg.log_dir == (tmp_path / "home/botlogs").resolve()


@pytest.mark.parametrize("value", ["", "   ", 5, ["a"]])
def test_bad_path_values_are_rejected(tmp_path, value):
    with pytest.raises(ConfigError, match="state_dir"):
        load(tmp_path, state_dir=value)


# ---------------------------------------------------------------------------
# notify: secrets come from the environment
# ---------------------------------------------------------------------------
def test_notify_secrets_come_from_env(tmp_path):
    env = {"NOTIFY_WEBHOOK_URL": " https://discord.com/api/webhooks/1/abc \n",
           "TELEGRAM_BOT_TOKEN": "123:XYZ", "TELEGRAM_CHAT_ID": "42"}
    cfg = load(tmp_path, env=env, notify={"on_trade": False, "on_error": True})
    assert cfg.notify.webhook_url == "https://discord.com/api/webhooks/1/abc"
    assert cfg.notify.telegram_bot_token == "123:XYZ" and cfg.notify.telegram_chat_id == "42"
    assert cfg.notify.on_trade is False and cfg.notify.on_error is True


def test_blank_notify_env_values_mean_disabled(tmp_path):
    cfg = load(tmp_path, env={"NOTIFY_WEBHOOK_URL": "", "TELEGRAM_BOT_TOKEN": "   "})
    assert cfg.notify.webhook_url is None and cfg.notify.telegram_bot_token is None


def test_env_defaults_to_os_environ(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "777")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.delenv("NOTIFY_WEBHOOK_URL", raising=False)
    cfg = load_config(write(tmp_path, base_config()))
    assert cfg.notify.telegram_chat_id == "777" and cfg.notify.webhook_url is None


@pytest.mark.parametrize("env, missing", [
    ({"TELEGRAM_BOT_TOKEN": "123:abc"}, "TELEGRAM_CHAT_ID"),
    ({"TELEGRAM_BOT_TOKEN": "123:abc", "TELEGRAM_CHAT_ID": "  "}, "TELEGRAM_CHAT_ID"),
    ({"TELEGRAM_CHAT_ID": "42"}, "TELEGRAM_BOT_TOKEN"),
])
def test_telegram_with_only_one_of_token_and_chat_id_is_a_config_error(tmp_path, env, missing):
    # Only one of the two would silently drop every alert.
    with pytest.raises(ConfigError, match=f"{missing} is not"):
        load(tmp_path, env=env)


def test_notify_secrets_are_hidden_from_repr(tmp_path):
    cfg = load(tmp_path, env={"NOTIFY_WEBHOOK_URL": "https://hooks.slack.com/services/SECRETPART",
                              "TELEGRAM_BOT_TOKEN": "123:TOKENPART", "TELEGRAM_CHAT_ID": "99"})
    text = repr(cfg)
    assert "SECRETPART" not in text and "TOKENPART" not in text


@pytest.mark.parametrize("key", ["telegram_chat_id"])
def test_notify_env_only_settings_in_yaml_point_to_env(tmp_path, key):
    with pytest.raises(ConfigError, match="TELEGRAM_CHAT_ID"):
        load(tmp_path, notify={key: "123"})


@pytest.mark.parametrize("value", ["yes", 1, None])
def test_notify_flags_must_be_booleans(tmp_path, value):
    with pytest.raises(ConfigError, match="notify.on_trade"):
        load(tmp_path, notify={"on_trade": value})


# ---------------------------------------------------------------------------
# unknown keys / secrets / file-level errors
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("overrides, fragment", [
    ({"symbol": ["X"]}, "Did you mean symbols"),
    ({"broker": {"type": "sim", "startng_cash": 5}}, "broker.startng_cash"),
    ({"strategy": {"name": "sma_crossover", "parms": {}}}, "Did you mean strategy.params"),
    ({"risk": {"stop_los_pct": 5}}, "Did you mean risk.stop_loss_pct"),
    ({"notify": {"on_trades": True}}, "Did you mean notify.on_trade"),
    ({"config_path": "/tmp/x"}, "unknown setting config_path"),
])
def test_unknown_keys_are_rejected_with_a_suggestion(tmp_path, overrides, fragment):
    with pytest.raises(ConfigError, match="unknown setting") as info:
        load(tmp_path, **overrides)
    assert fragment in str(info.value)


def test_non_string_keys_are_rejected(tmp_path):
    with pytest.raises(ConfigError, match="unknown setting"):
        load_config(write(tmp_path, "symbols: [X]\n1: 2\n"), env={})


def test_unknown_strategy_param_is_rejected(tmp_path):
    with pytest.raises(ConfigError, match="strategy"):
        load(tmp_path, strategy={"name": "sma_crossover", "params": {"fast": 5, "slow": 20, "fsat": 3}})


@pytest.mark.parametrize("overrides", [
    {"api_key": "PKXXXX"},
    {"apiKey": "PKXXXX"},
    {"broker": {"type": "alpaca", "api_key": "PKXXXX"}},
    {"broker": {"type": "alpaca", "secret_key": "PKXXXX"}},
    {"broker": {"type": "ccxt", "exchange": "upbit", "secret": "PKXXXX"}},
    {"broker": {"type": "ccxt", "exchange": "okx", "password": "PKXXXX"}},
    {"broker": {"type": "ccxt", "exchange": "okx", "API-KEY": "PKXXXX"}},
    {"notify": {"telegram_bot_token": "PKXXXX"}},
    {"notify": {"webhook_url": "https://discord.com/api/webhooks/PKXXXX"}},
    {"notify": {"token": "PKXXXX"}},
    {"strategy": {"name": "sma_crossover", "params": {"secret": "PKXXXX"}}},
    {"extras": [{"nested": {"Password": "PKXXXX"}}]},
])
def test_secrets_anywhere_in_yaml_are_refused_without_echoing_them(tmp_path, overrides):
    with pytest.raises(ConfigError, match=r"\.env") as info:
        load(tmp_path, **overrides)
    message = str(info.value)
    assert "looks like a secret" in message
    assert "PKXXXX" not in message


def test_missing_file_is_a_config_error(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.yaml", env={})


def test_directory_instead_of_file_is_a_config_error(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path, env={})


def test_invalid_yaml_is_a_config_error(tmp_path):
    with pytest.raises(ConfigError, match="not valid YAML"):
        load_config(write(tmp_path, "symbols: [AAA\nmode: paper\n"), env={})


def test_duplicate_keys_are_rejected(tmp_path):
    text = "symbols: [X]\nbars_lookback: 60\nrisk:\n  stop_loss_pct: 5\nrisk:\n  max_open_positions: 2\n"
    with pytest.raises(ConfigError, match="duplicate key 'risk'"):
        load_config(write(tmp_path, text), env={})


def test_duplicate_nested_keys_are_rejected(tmp_path):
    text = "symbols: [X]\nbars_lookback: 60\nbroker:\n  type: sim\n  type: alpaca\n"
    with pytest.raises(ConfigError, match="duplicate key 'type'"):
        load_config(write(tmp_path, text), env={})


def test_yaml_merge_keys_still_work(tmp_path):
    text = ("symbols: [X]\nbars_lookback: 60\n"
            "strategy:\n  name: sma_crossover\n  params:\n    <<: {fast: 3, slow: 10}\n    fast: 4\n")
    cfg = load_config(write(tmp_path, text), env={})
    assert cfg.strategy.params == {"fast": 4, "slow": 10}


@pytest.mark.parametrize("text", ["- a\n- b\n", "just a string\n", "42\n"])
def test_top_level_must_be_a_mapping(tmp_path, text):
    with pytest.raises(ConfigError, match="top level must be a mapping"):
        load_config(write(tmp_path, text), env={})


def test_empty_file_asks_for_symbols(tmp_path):
    with pytest.raises(ConfigError, match="symbols is required"):
        load_config(write(tmp_path, ""), env={})


def test_error_message_names_the_file(tmp_path):
    path = write(tmp_path, base_config(mode="yolo"))
    with pytest.raises(ConfigError) as info:
        load_config(path, env={})
    assert str(path.resolve()) in str(info.value)


# ---------------------------------------------------------------------------
# field validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("mode", ["demo", "LIVEE", "", 1, True, None, ["paper"]])
def test_bad_mode(tmp_path, mode):
    with pytest.raises(ConfigError, match="mode must be one of paper, live"):
        load(tmp_path, mode=mode)


@pytest.mark.parametrize("kind", ["binance", "paper", "", None, 3])
def test_bad_broker_type(tmp_path, kind):
    with pytest.raises(ConfigError, match="broker.type must be one of sim, alpaca, ccxt"):
        load(tmp_path, broker={"type": kind})


@pytest.mark.parametrize("value", ["sim", ["sim"], 5])
def test_broker_section_must_be_a_mapping(tmp_path, value):
    with pytest.raises(ConfigError, match="broker must be a mapping"):
        load(tmp_path, broker=value)


def test_sim_broker_cannot_be_live(tmp_path):
    with pytest.raises(ConfigError, match="cannot trade live"):
        load(tmp_path, env=LIVE_ENV, mode="live")


def test_ccxt_requires_exchange(tmp_path):
    with pytest.raises(ConfigError, match="broker.exchange"):
        load(tmp_path, broker={"type": "ccxt"}, symbols=["BTC/USDT"])


@pytest.mark.parametrize("exchange", ["", "  ", 5])
def test_ccxt_exchange_must_be_text(tmp_path, exchange):
    with pytest.raises(ConfigError, match="broker.exchange"):
        load(tmp_path, broker={"type": "ccxt", "exchange": exchange}, symbols=["BTC/USDT"])


@pytest.mark.parametrize("feed", ["otc", "", 1])
def test_bad_alpaca_data_feed(tmp_path, feed):
    with pytest.raises(ConfigError, match="broker.data_feed"):
        load(tmp_path, broker={"type": "alpaca", "data_feed": feed}, symbols=["SPY"])


@pytest.mark.parametrize("field_name, value", [
    ("fee_pct", -0.01), ("fee_pct", 5.01), ("slippage_pct", -1), ("slippage_pct", 50),
    ("fee_pct", "0.1"), ("slippage_pct", True), ("fee_pct", float("nan")), ("fee_pct", None),
])
def test_fee_and_slippage_must_be_in_0_to_5(tmp_path, field_name, value):
    with pytest.raises(ConfigError, match=f"broker.{field_name}"):
        load(tmp_path, broker={"type": "sim", field_name: value})


@pytest.mark.parametrize("value", [0, 0.0, -100, "10000", float("inf"), float("nan"), True])
def test_starting_cash_must_be_positive_number(tmp_path, value):
    with pytest.raises(ConfigError, match="broker.starting_cash"):
        load(tmp_path, broker={"type": "sim", "starting_cash": value})


@pytest.mark.parametrize("field_name, value", [("use_sandbox", "yes"), ("use_sandbox", 1),
                                               ("sim_seed", 1.5), ("sim_seed", "42"), ("sim_seed", True),
                                               ("sim_seed", -1)])
def test_broker_field_types(tmp_path, field_name, value):
    with pytest.raises(ConfigError, match=f"broker.{field_name}"):
        load(tmp_path, broker={"type": "sim", field_name: value})


# ---- symbols ----------------------------------------------------------------
@pytest.mark.parametrize("value, fragment", [
    (None, "symbols is required"),
    ([], "non-empty list"),
    ("SPY", "non-empty list"),
    ({"SPY": 1}, "non-empty list"),
    (["AAA", "AAA"], "listed twice"),
    ([5], "must be text"),
    ([None], "must be text"),
    (["  "], "must be text"),
    ([True], "in quotes"),
    (["BRK B"], "whitespace"),
])
def test_bad_symbols(tmp_path, value, fragment):
    overrides = {"symbols": value} if value is not None else {}
    data = base_config(**overrides)
    if value is None:
        del data["symbols"]
    with pytest.raises(ConfigError, match="symbols") as info:
        load_config(write(tmp_path, data), env={})
    assert fragment in str(info.value)


def test_yaml_boolean_ticker_gets_a_quoting_hint(tmp_path):
    text = "symbols: [ON]\nbars_lookback: 60\n"
    with pytest.raises(ConfigError, match='"ON"'):
        load_config(write(tmp_path, text), env={})


def test_alpaca_duplicates_detected_after_uppercasing(tmp_path):
    with pytest.raises(ConfigError, match="SPY is listed twice"):
        load(tmp_path, broker={"type": "alpaca"}, symbols=["SPY", "spy"])


@pytest.mark.parametrize("symbol", ["BTC/USD", "btc/usd"])
def test_alpaca_rejects_crypto_pairs(tmp_path, symbol):
    with pytest.raises(ConfigError, match="stocks/ETFs only"):
        load(tmp_path, broker={"type": "alpaca"}, symbols=[symbol])


@pytest.mark.parametrize("symbol", ["BTCUSDT", "BTC/", "/USDT", "BTC/USDT/X"])
def test_ccxt_symbols_need_base_slash_quote(tmp_path, symbol):
    with pytest.raises(ConfigError, match="BASE/QUOTE"):
        load(tmp_path, broker={"type": "ccxt", "exchange": "binance"}, symbols=[symbol])


def test_ccxt_rejects_derivative_contracts(tmp_path):
    with pytest.raises(ConfigError, match="leverage"):
        load(tmp_path, broker={"type": "ccxt", "exchange": "binance"}, symbols=["BTC/USDT:USDT"])


def test_ccxt_symbols_must_share_one_quote_currency(tmp_path):
    with pytest.raises(ConfigError, match="one quote currency"):
        load(tmp_path, broker={"type": "ccxt", "exchange": "binance"}, symbols=["BTC/USDT", "ETH/BTC"])


# ---- timeframe / timezone / numbers --------------------------------------------
@pytest.mark.parametrize("timeframe", ["2h", "1M", "1D", "1w", "", 60, None, "daily"])
def test_bad_timeframe(tmp_path, timeframe):
    with pytest.raises(ConfigError, match="timeframe"):
        load(tmp_path, timeframe=timeframe)


@pytest.mark.parametrize("timeframe", ["1m", "5m", "15m", "30m", "1h", "4h", "1d"])
def test_every_supported_timeframe_is_accepted(tmp_path, timeframe):
    assert load(tmp_path, timeframe=timeframe).timeframe == timeframe


@pytest.mark.parametrize("tz", ["Mars/Olympus", "utc", "America", "", "/etc/passwd", "../x", 5, None])
def test_bad_timezone(tmp_path, tz):
    with pytest.raises(ConfigError, match="timezone"):
        load(tmp_path, timezone=tz)


def test_lookback_must_cover_strategy_warmup_plus_one(tmp_path):
    # sma_crossover(slow=20) needs min_bars = 21, so bars_lookback >= 22.
    assert load(tmp_path, bars_lookback=22).bars_lookback == 22
    with pytest.raises(ConfigError, match="at least 22"):
        load(tmp_path, bars_lookback=21)


def test_lookback_uses_strategy_defaults_when_params_are_omitted(tmp_path):
    # rsi_reversion default trend_sma=200 -> min_bars 201 -> need 202
    with pytest.raises(ConfigError, match="at least 202"):
        load(tmp_path, strategy={"name": "rsi_reversion"}, bars_lookback=201)
    assert load(tmp_path, strategy={"name": "rsi_reversion"}, bars_lookback=202).bars_lookback == 202


def test_lookback_check_uses_the_strategy_factory(tmp_path, monkeypatch):
    class FakeStrategy:
        min_bars = 9
        params: dict = {}

    calls = []

    def fake_create(name, params=None):
        calls.append((name, params))
        return FakeStrategy()

    monkeypatch.setattr(config_mod, "create_strategy", fake_create)
    cfg = load(tmp_path, strategy={"name": "anything", "params": {"k": 1}}, bars_lookback=10)
    assert calls == [("anything", {"k": 1})] and cfg.strategy.name == "anything"
    with pytest.raises(ConfigError, match="at least 10"):
        load(tmp_path, strategy={"name": "anything"}, bars_lookback=9)


@pytest.mark.parametrize("value", [0, -5, 1.5, "300", True, None])
def test_bad_bars_lookback(tmp_path, value):
    with pytest.raises(ConfigError, match="bars_lookback"):
        load(tmp_path, bars_lookback=value)


@pytest.mark.parametrize("value", [4, 0, -1, 30.0, "60", False, None])
def test_bad_poll_interval(tmp_path, value):
    with pytest.raises(ConfigError, match="poll_interval_seconds"):
        load(tmp_path, poll_interval_seconds=value)


def test_poll_interval_minimum_is_five_seconds(tmp_path):
    assert load(tmp_path, poll_interval_seconds=5).poll_interval_seconds == 5


# ---- strategy / risk -------------------------------------------------------------
def test_unknown_strategy_lists_valid_names(tmp_path):
    with pytest.raises(ConfigError, match="sma_crossover"):
        load(tmp_path, strategy={"name": "moon_shot"})


def test_invalid_strategy_params_become_config_errors(tmp_path):
    with pytest.raises(ConfigError, match="strategy"):
        load(tmp_path, strategy={"name": "sma_crossover", "params": {"fast": 30, "slow": 10}})


@pytest.mark.parametrize("params", [[1, 2], "fast=5", 5])
def test_strategy_params_must_be_a_mapping(tmp_path, params):
    with pytest.raises(ConfigError, match="strategy.params"):
        load(tmp_path, strategy={"name": "sma_crossover", "params": params})


@pytest.mark.parametrize("name", [None, "", 3])
def test_strategy_name_must_be_text(tmp_path, name):
    with pytest.raises(ConfigError, match="strategy.name"):
        load(tmp_path, strategy={"name": name})


@pytest.mark.parametrize("risk, fragment", [
    ({"max_open_positions": 0}, "max_open_positions"),
    ({"max_trades_per_day": 0}, "max_trades_per_day"),
    ({"risk_per_trade_pct": 0}, "risk_per_trade_pct"),
    ({"max_position_pct": 150}, "max_position_pct"),
    ({"stop_loss_pct": -5}, "stop_loss_pct"),
    ({"min_order_notional": -1}, "min_order_notional"),
    ({"cash_buffer_pct": 60}, "cash_buffer_pct"),
    ({"flatten_on_daily_loss": "yes"}, "flatten_on_daily_loss"),
    ({"max_position_pct": "20"}, "max_position_pct"),
])
def test_invalid_risk_values_become_config_errors(tmp_path, risk, fragment):
    with pytest.raises(ConfigError, match="risk") as info:
        load(tmp_path, risk=risk)
    assert fragment in str(info.value)


def test_risk_section_must_be_a_mapping(tmp_path):
    with pytest.raises(ConfigError, match="risk must be a mapping"):
        load(tmp_path, risk=[1, 2])


# ---------------------------------------------------------------------------
# assert_live_allowed
# ---------------------------------------------------------------------------
def test_paper_mode_never_needs_confirmation():
    assert_live_allowed(BotConfig(mode="paper"), env={})
    assert_live_allowed(BotConfig(mode="paper"), env={LIVE_CONFIRM_ENV: "nonsense"})


def test_live_mode_with_exact_confirmation_is_allowed():
    assert_live_allowed(BotConfig(mode="live"), env={LIVE_CONFIRM_ENV: "I_ACCEPT_THE_RISK"})


def test_live_mode_without_confirmation_explains_how():
    with pytest.raises(ConfigError) as info:
        assert_live_allowed(BotConfig(mode="live"), env={})
    message = str(info.value)
    assert LIVE_CONFIRM_ENV in message and LIVE_CONFIRM_VALUE in message and "not set" in message


@pytest.mark.parametrize("value", ["", "yes", "true", "1", "i_accept_the_risk", " I_ACCEPT_THE_RISK",
                                   "I_ACCEPT_THE_RISK ", "I_ACCEPT_THE_RISK\n", "I ACCEPT THE RISK",
                                   "I_ACCEPT_THE_RISK!"])
def test_live_confirmation_must_match_exactly(value):
    with pytest.raises(ConfigError, match="exact"):
        assert_live_allowed(BotConfig(mode="live"), env={LIVE_CONFIRM_ENV: value})


def test_assert_live_allowed_defaults_to_os_environ(monkeypatch):
    monkeypatch.delenv(LIVE_CONFIRM_ENV, raising=False)
    with pytest.raises(ConfigError):
        assert_live_allowed(BotConfig(mode="live"))
    monkeypatch.setenv(LIVE_CONFIRM_ENV, LIVE_CONFIRM_VALUE)
    assert_live_allowed(BotConfig(mode="live"))


def test_loading_a_live_config_does_not_by_itself_grant_live_trading(tmp_path, caplog):
    with caplog.at_level("WARNING", logger="bot.config"):
        cfg = load(tmp_path, mode="live", broker={"type": "alpaca"}, symbols=["SPY"])
    assert "LIVE" in caplog.text
    with pytest.raises(ConfigError):
        assert_live_allowed(cfg, env={})


# ---------------------------------------------------------------------------
# shipped example configs and .env.example
# ---------------------------------------------------------------------------
def test_demo_config_loads():
    cfg = load_config(ROOT / "configs/demo.yaml", env={})
    assert cfg.mode == "paper" and cfg.broker.type == "sim"
    assert cfg.symbols == ["DEMO1", "DEMO2"] and cfg.timeframe == "1m"
    assert cfg.bars_lookback == 300 and cfg.timezone == "UTC" and cfg.poll_interval_seconds == 30
    assert cfg.strategy == StrategyConfig("sma_crossover", {"fast": 10, "slow": 30})


def test_stocks_config_loads():
    cfg = load_config(ROOT / "configs/stocks.yaml", env={})
    assert cfg.mode == "paper" and cfg.broker.type == "alpaca" and cfg.broker.data_feed == "iex"
    assert cfg.symbols == ["SPY", "QQQ"] and cfg.timeframe == "1d" and cfg.bars_lookback == 300
    assert cfg.timezone == "America/New_York" and cfg.poll_interval_seconds == 300
    assert cfg.strategy.name == "rsi_reversion"
    r = cfg.risk
    assert (r.max_position_pct, r.max_total_exposure_pct, r.max_open_positions) == (45, 90, 2)
    assert (r.max_daily_loss_pct, r.stop_loss_pct, r.take_profit_pct) == (3, 8, None)
    assert (r.max_trades_per_day, r.min_order_notional) == (2, 1)
    assert cfg.broker.fee_pct == 0 and cfg.broker.slippage_pct == 0.05
    # position size from risk sizing stays under the per-position cap
    assert r.risk_per_trade_pct / r.stop_loss_pct * 100 <= r.max_position_pct


def test_crypto_config_loads():
    cfg = load_config(ROOT / "configs/crypto.yaml", env={})
    assert cfg.mode == "paper" and cfg.broker.type == "ccxt" and cfg.broker.exchange == "upbit"
    assert not cfg.broker.use_sandbox
    assert cfg.symbols == ["BTC/KRW", "ETH/KRW"] and cfg.timeframe == "4h"
    assert cfg.timezone == "Asia/Seoul" and cfg.poll_interval_seconds == 60
    assert cfg.strategy == StrategyConfig("donchian_breakout",
                                          {"entry_period": 20, "exit_period": 10, "trend_sma": 50})
    assert cfg.broker.starting_cash == 1_000_000 and cfg.broker.fee_pct == 0.05
    assert cfg.broker.slippage_pct == 0.1
    assert cfg.risk.min_order_notional == 5000 and cfg.risk.stop_loss_pct == 10
    assert cfg.bars_lookback + 1 <= 200   # Upbit serves at most 200 candles per request


@pytest.mark.parametrize("name", ["demo", "stocks", "crypto"])
def test_shipped_configs_use_separate_state_dirs_inside_the_project(name):
    cfg = load_config(ROOT / f"configs/{name}.yaml", env={})
    assert cfg.state_dir == ROOT / "state" / name and cfg.log_dir == ROOT / "logs" / name


def test_existing_holdings_are_not_adopted_unless_opted_in(tmp_path):
    assert load(tmp_path).adopt_existing_positions is False
    assert load(tmp_path, adopt_existing_positions=True).adopt_existing_positions is True
    with pytest.raises(ConfigError, match="adopt_existing_positions"):
        load(tmp_path, adopt_existing_positions="yes")


def test_state_dir_only_resolves_like_load_config_without_validating_the_rest(tmp_path):
    from bot.config import state_dir_only
    good = write(tmp_path / "configs", base_config(state_dir="../state/x"))
    assert state_dir_only(good) == load_config(good, env={}).state_dir == (tmp_path / "state" / "x").resolve()
    # An invalid edit elsewhere in the file does not hide where the state lives.
    broken = write(tmp_path / "configs", base_config(state_dir="../state/x", bars_lookback=3, typo=1), "b.yaml")
    with pytest.raises(ConfigError):
        load_config(broken, env={})
    assert state_dir_only(broken) == (tmp_path / "state" / "x").resolve()
    default = write(tmp_path / "configs", base_config(), "d.yaml")
    assert state_dir_only(default) == load_config(default, env={}).state_dir


def test_env_example_lists_every_variable_and_keeps_live_switch_off():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    active = {line.split("=", 1)[0]: line.split("=", 1)[1] for line in text.splitlines()
              if line.strip() and not line.lstrip().startswith("#")}
    for name in ("ALPACA_API_KEY", "ALPACA_SECRET_KEY", "CCXT_API_KEY", "CCXT_SECRET", "CCXT_PASSWORD",
                 "NOTIFY_WEBHOOK_URL", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        assert active.get(name) == "", f"{name} should be present and empty"
    assert LIVE_CONFIRM_ENV not in active
    assert f"# {LIVE_CONFIRM_ENV}={LIVE_CONFIRM_VALUE}" in text


# ---------------------------------------------------------------------------
# make_broker (adapters stubbed via sys.modules so no SDK / network is touched)
# ---------------------------------------------------------------------------
class _Fake:
    instances: list

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs
        type(self).instances.append(self)


@pytest.fixture
def fakes(monkeypatch):
    def install(module_name: str, class_name: str) -> type:
        cls = type(class_name, (_Fake,), {"instances": []})
        module = types.ModuleType(module_name)
        setattr(module, class_name, cls)
        monkeypatch.setitem(sys.modules, module_name, module)
        return cls

    return types.SimpleNamespace(
        PaperBroker=install("bot.brokers.paper", "PaperBroker"),
        SyntheticFeed=install("bot.data", "SyntheticFeed"),
        AlpacaBroker=install("bot.brokers.alpaca_broker", "AlpacaBroker"),
        CCXTBroker=install("bot.brokers.ccxt_broker", "CCXTBroker"),
    )


def make_cfg(tmp_path: Path, mode: str = "paper", symbols: list[str] | None = None, **broker: Any) -> BotConfig:
    return BotConfig(mode=mode, broker=BrokerConfig(**broker), symbols=symbols or ["SPY"],
                     state_dir=tmp_path / "state")


ALPACA_KEYS = {"ALPACA_API_KEY": "PKTEST", "ALPACA_SECRET_KEY": "SKTEST"}
CCXT_KEYS = {"CCXT_API_KEY": "ck", "CCXT_SECRET": "cs"}


def test_brokers_package_exports_base_types():
    from bot.brokers import Broker, BrokerError, make_broker
    from bot.brokers.base import Broker as BaseBroker
    from bot.brokers.base import BrokerError as BaseError
    assert Broker is BaseBroker and BrokerError is BaseError and callable(make_broker)


def test_sim_builds_paper_broker_on_synthetic_feed(tmp_path, fakes):
    from bot.brokers import make_broker
    cfg = make_cfg(tmp_path, type="sim", sim_seed=7, starting_cash=5000.0, fee_pct=0.2, slippage_pct=0.3)
    broker = make_broker(cfg, env={})
    assert isinstance(broker, fakes.PaperBroker)
    feed = broker.args[0]
    assert isinstance(feed, fakes.SyntheticFeed) and feed.kwargs == {"seed": 7}
    assert broker.kwargs == {"starting_cash": 5000.0, "fee_pct": 0.2, "slippage_pct": 0.3,
                             "state_path": tmp_path / "state" / "paper_account.json"}
    assert not fakes.AlpacaBroker.instances and not fakes.CCXTBroker.instances


def test_sim_refuses_live_even_when_confirmed(tmp_path, fakes):
    from bot.brokers import make_broker
    with pytest.raises(ConfigError, match="cannot trade live"):
        make_broker(make_cfg(tmp_path, mode="live", type="sim"), env=LIVE_ENV)
    assert not fakes.PaperBroker.instances


def test_alpaca_paper_uses_env_keys_and_paper_endpoint(tmp_path, fakes):
    from bot.brokers import make_broker
    env = {"ALPACA_API_KEY": " PKTEST ", "ALPACA_SECRET_KEY": "SKTEST\n"}
    broker = make_broker(make_cfg(tmp_path, type="alpaca", data_feed="sip"), env=env)
    assert isinstance(broker, fakes.AlpacaBroker)
    assert broker.args == ("PKTEST", "SKTEST")
    assert broker.kwargs == {"paper": True, "data_feed": "sip"}


@pytest.mark.parametrize("env", [{}, {"ALPACA_API_KEY": "PK"}, {"ALPACA_SECRET_KEY": "SK"},
                                 {"ALPACA_API_KEY": "", "ALPACA_SECRET_KEY": "SK"},
                                 {"ALPACA_API_KEY": "PK", "ALPACA_SECRET_KEY": "   "}])
def test_alpaca_missing_keys_explain_where_to_get_them(tmp_path, fakes, env):
    from bot.brokers import make_broker
    with pytest.raises(ConfigError, match="ALPACA_API_KEY") as info:
        make_broker(make_cfg(tmp_path, type="alpaca"), env=env)
    assert "paper" in str(info.value).lower() and "alpaca.markets" in str(info.value)
    assert not fakes.AlpacaBroker.instances


def test_alpaca_live_requires_confirmation_before_anything_is_built(tmp_path, fakes):
    from bot.brokers import make_broker
    with pytest.raises(ConfigError, match=LIVE_CONFIRM_ENV):
        make_broker(make_cfg(tmp_path, mode="live", type="alpaca"), env=dict(ALPACA_KEYS))
    with pytest.raises(ConfigError, match=LIVE_CONFIRM_ENV):
        make_broker(make_cfg(tmp_path, mode="live", type="alpaca"),
                    env={**ALPACA_KEYS, LIVE_CONFIRM_ENV: "yes"})
    assert not fakes.AlpacaBroker.instances


def test_alpaca_live_with_confirmation_uses_live_endpoint(tmp_path, fakes):
    from bot.brokers import make_broker
    broker = make_broker(make_cfg(tmp_path, mode="live", type="alpaca"), env={**ALPACA_KEYS, **LIVE_ENV})
    assert broker.kwargs["paper"] is False


def test_unrecognised_mode_is_treated_as_paper_by_the_factory(tmp_path, fakes):
    """A hand-built config with an odd mode string must never reach a live endpoint."""
    from bot.brokers import make_broker
    broker = make_broker(make_cfg(tmp_path, mode="LIVE", type="alpaca"), env=dict(ALPACA_KEYS))
    assert broker.kwargs["paper"] is True


def test_ccxt_paper_is_local_paper_on_public_data_without_keys(tmp_path, fakes):
    from bot.brokers import make_broker
    cfg = make_cfg(tmp_path, type="ccxt", exchange="upbit", starting_cash=1_000_000.0, fee_pct=0.05,
                   slippage_pct=0.1, symbols=["BTC/KRW", "ETH/KRW"])
    # keys in the environment must NOT be handed to a paper broker
    broker = make_broker(cfg, env={**CCXT_KEYS, "CCXT_PASSWORD": "pw"})
    assert isinstance(broker, fakes.PaperBroker)
    feed = broker.args[0]
    assert isinstance(feed, fakes.CCXTBroker)
    assert feed.args == ("upbit", ["BTC/KRW", "ETH/KRW"]) and feed.kwargs == {}
    assert broker.kwargs == {"starting_cash": 1_000_000.0, "fee_pct": 0.05, "slippage_pct": 0.1,
                             "state_path": tmp_path / "state" / "paper_account.json", "currency": "KRW"}
    assert len(fakes.CCXTBroker.instances) == 1


def test_ccxt_sandbox_uses_testnet_keys(tmp_path, fakes):
    from bot.brokers import make_broker
    cfg = make_cfg(tmp_path, type="ccxt", exchange="binance", use_sandbox=True, symbols=["BTC/USDT"])
    broker = make_broker(cfg, env=dict(CCXT_KEYS))
    assert isinstance(broker, fakes.CCXTBroker) and not fakes.PaperBroker.instances
    assert broker.args == ("binance", ["BTC/USDT"])
    assert broker.kwargs == {"api_key": "ck", "secret": "cs", "password": None, "sandbox": True,
                             "entries_path": tmp_path / "state" / "ccxt_entries.binance.sandbox.json"}


def test_ccxt_testnet_and_live_keep_entry_prices_in_separate_files(tmp_path, fakes):
    # A testnet's average prices must never become the stop reference for live coins.
    from bot.brokers import make_broker
    sandbox = make_broker(make_cfg(tmp_path, type="ccxt", exchange="binance", use_sandbox=True,
                                   symbols=["BTC/USDT"]), env=dict(CCXT_KEYS))
    live = make_broker(make_cfg(tmp_path, mode="live", type="ccxt", exchange="binance", symbols=["BTC/USDT"]),
                       env={**CCXT_KEYS, **LIVE_ENV})
    assert live.kwargs["entries_path"] == tmp_path / "state" / "ccxt_entries.binance.json"
    assert live.kwargs["entries_path"] != sandbox.kwargs["entries_path"]


def test_ccxt_live_with_confirmation_passes_optional_password(tmp_path, fakes):
    from bot.brokers import make_broker
    cfg = make_cfg(tmp_path, mode="live", type="ccxt", exchange="okx", symbols=["BTC/USDT"])
    broker = make_broker(cfg, env={**CCXT_KEYS, "CCXT_PASSWORD": "pass", **LIVE_ENV})
    assert isinstance(broker, fakes.CCXTBroker)
    assert broker.kwargs["password"] == "pass" and broker.kwargs["sandbox"] is False


def test_ccxt_live_without_confirmation_is_refused(tmp_path, fakes):
    from bot.brokers import make_broker
    cfg = make_cfg(tmp_path, mode="live", type="ccxt", exchange="okx", symbols=["BTC/USDT"])
    with pytest.raises(ConfigError, match=LIVE_CONFIRM_ENV):
        make_broker(cfg, env=dict(CCXT_KEYS))
    assert not fakes.CCXTBroker.instances


@pytest.mark.parametrize("mode, sandbox, env", [
    ("paper", True, {}),
    ("paper", True, {"CCXT_API_KEY": "ck"}),
    ("live", False, {"CCXT_SECRET": "cs", **LIVE_ENV}),
    ("live", False, {"CCXT_API_KEY": " ", "CCXT_SECRET": "cs", **LIVE_ENV}),
])
def test_ccxt_authenticated_modes_require_keys(tmp_path, fakes, mode, sandbox, env):
    from bot.brokers import make_broker
    cfg = make_cfg(tmp_path, mode=mode, type="ccxt", exchange="binance", use_sandbox=sandbox,
                   symbols=["BTC/USDT"])
    with pytest.raises(ConfigError, match="CCXT_API_KEY and CCXT_SECRET"):
        make_broker(cfg, env=env)
    assert not fakes.CCXTBroker.instances


def test_ccxt_without_exchange_is_a_config_error(tmp_path, fakes):
    from bot.brokers import make_broker
    with pytest.raises(ConfigError, match="exchange"):
        make_broker(make_cfg(tmp_path, type="ccxt", symbols=["BTC/USDT"]), env={})


def test_unknown_broker_type_is_a_config_error(tmp_path, fakes):
    from bot.brokers import make_broker
    with pytest.raises(ConfigError, match="unknown broker type"):
        make_broker(make_cfg(tmp_path, type="ibkr"), env={})


def test_adapter_value_errors_become_config_errors(tmp_path, fakes, monkeypatch):
    from bot.brokers import make_broker

    def boom(*args, **kwargs):
        raise ValueError("'nosuchex' is not a ccxt exchange")

    monkeypatch.setattr(fakes.CCXTBroker, "__init__", boom)
    cfg = make_cfg(tmp_path, type="ccxt", exchange="nosuchex", symbols=["BTC/USDT"])
    with pytest.raises(ConfigError, match="nosuchex"):
        make_broker(cfg, env={})


def _fail_import(monkeypatch, module: str, missing: str) -> None:
    """Make ``from .<module> import ...`` raise ModuleNotFoundError(name=missing)."""
    import builtins
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == module and level == 1:
            raise ModuleNotFoundError(f"No module named {missing!r}", name=missing)
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)


@pytest.mark.parametrize("module, missing, cfg_kwargs", [
    ("alpaca_broker", "alpaca", {"type": "alpaca"}),
    ("ccxt_broker", "ccxt", {"type": "ccxt", "exchange": "upbit", "symbols": ["BTC/KRW"]}),
])
def test_missing_vendor_sdk_gives_install_hint(tmp_path, monkeypatch, module, missing, cfg_kwargs):
    from bot.brokers import make_broker
    _fail_import(monkeypatch, module, missing)
    with pytest.raises(ConfigError, match="pip install"):
        make_broker(make_cfg(tmp_path, **cfg_kwargs), env={**ALPACA_KEYS, **CCXT_KEYS})


def test_other_import_errors_are_not_disguised(tmp_path, monkeypatch):
    from bot.brokers import make_broker
    _fail_import(monkeypatch, "alpaca_broker", "bot.some_internal_module")
    with pytest.raises(ModuleNotFoundError):
        make_broker(make_cfg(tmp_path, type="alpaca"), env=dict(ALPACA_KEYS))


def test_make_broker_env_defaults_to_os_environ(tmp_path, fakes, monkeypatch):
    from bot.brokers import make_broker
    monkeypatch.setenv("ALPACA_API_KEY", "PKENV")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "SKENV")
    broker = make_broker(make_cfg(tmp_path, type="alpaca"))
    assert broker.args == ("PKENV", "SKENV")


def test_sim_broker_end_to_end_with_real_adapters(tmp_path):
    from bot.brokers import Broker, make_broker
    cfg = make_cfg(tmp_path, type="sim", starting_cash=2500.0, symbols=["DEMO1"])
    broker = make_broker(cfg, env={})
    assert isinstance(broker, Broker) and broker.name == "paper"
    account = broker.get_account()
    assert account.cash == pytest.approx(2500.0) and account.equity == pytest.approx(2500.0)
    assert broker.get_latest_price("DEMO1") > 0


# --------------------------------------------------------------------------- deployment files


def test_docker_compose_mounts_the_configs_so_edits_apply_without_a_rebuild():
    root = Path(__file__).resolve().parents[1]
    compose = yaml.safe_load((root / "docker-compose.yml").read_text(encoding="utf-8"))
    volumes = compose["services"]["trading-bot"]["volumes"]
    assert "./configs:/app/configs:ro" in volumes
    assert "./state:/app/state" in volumes and "./logs:/app/logs" in volumes
