"""Tests for the command-line interface (``python -m bot``).

Everything runs offline: configs are temp copies of ``configs/demo.yaml``
(the built-in ``sim`` broker, no keys, no network) with state and logs in
``tmp_path``; brokers that would need a network are replaced with fakes.
"""
from __future__ import annotations

import argparse
import json
import logging
import logging.handlers
import os
import signal
import subprocess
import sys
import threading
from pathlib import Path

import pytest
import yaml

from bot import cli
from bot.brokers.base import Broker, BrokerError
from bot.brokers.paper import PaperBroker
from bot.config import LIVE_CONFIRM_ENV, LIVE_CONFIRM_VALUE, load_config
from bot.data import SyntheticFeed, generate_synthetic_bars
from bot.models import Account, OrderRequest, OrderResult, Position, Side
from bot.risk import RiskConfig
from bot.state import KILL_FILE, BotState, StateStore
from bot.strategies import STRATEGIES

ROOT = Path(__file__).resolve().parents[1]

SECRET_ENV = ("NOTIFY_WEBHOOK_URL", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", LIVE_CONFIRM_ENV,
              "ALPACA_API_KEY", "ALPACA_SECRET_KEY", "CCXT_API_KEY", "CCXT_SECRET", "CCXT_PASSWORD")


# --------------------------------------------------------------------------- helpers


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Run every test in tmp_path with no secrets in the environment, so no
    .env from the repo is read, nothing is written into the repo and no real
    notification or broker could ever be reached."""
    monkeypatch.chdir(tmp_path)
    for name in SECRET_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(cli, "LIVE_START_DELAY_SECONDS", 0)


def _merge(base: dict, extra: dict) -> dict:
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value
    return base


def write_config(tmp_path: Path, name: str = "config.yaml", **overrides) -> Path:
    """A copy of configs/demo.yaml with state/logs inside tmp_path."""
    raw = yaml.safe_load((ROOT / "configs" / "demo.yaml").read_text(encoding="utf-8"))
    raw["state_dir"] = str(tmp_path / "state")
    raw["log_dir"] = str(tmp_path / "logs")
    _merge(raw, overrides)
    path = tmp_path / name
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return path


def live_alpaca_config(tmp_path: Path) -> Path:
    return write_config(tmp_path, name="live.yaml", mode="live", symbols=["SPY", "QQQ"],
                        broker={"type": "alpaca", "data_feed": "iex", "sim_seed": 42})


def run(capsys, *argv: str) -> tuple[int, str, str]:
    code = cli.main(list(argv))
    out, err = capsys.readouterr()
    return code, out, err


def paper_broker(tmp_path: Path) -> PaperBroker:
    """The same paper account the sim broker of ``write_config`` uses."""
    return PaperBroker(SyntheticFeed(seed=42), state_path=tmp_path / "state" / "paper_account.json")


def forbid_make_broker(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise AssertionError("make_broker must not be called")

    monkeypatch.setattr("bot.brokers.make_broker", fail)


class FakeBroker(Broker):
    """Minimal scripted broker for failure paths."""

    name = "fake"

    def __init__(self, *, fail_account: bool = False, positions: dict[str, Position] | None = None,
                 reject_sells: bool = False, bars=None) -> None:
        self.fail_account = fail_account
        self.positions = positions or {}
        self.reject_sells = reject_sells
        self.bars = bars
        self.bar_requests: list[tuple[str, str, int]] = []
        self.orders: list[OrderRequest] = []
        self.cancelled = 0

    def get_bars(self, symbol, timeframe, limit):
        self.bar_requests.append((symbol, timeframe, limit))
        if self.bars is None:
            raise BrokerError("no data")
        return self.bars.tail(limit)

    def get_latest_price(self, symbol):
        return 100.0

    def get_account(self):
        if self.fail_account:
            raise BrokerError("connection refused")
        return Account(equity=1000.0, cash=1000.0, buying_power=1000.0)

    def get_positions(self):
        return dict(self.positions)

    def submit_order(self, order):
        self.orders.append(order)
        status = "rejected" if self.reject_sells and order.side is Side.SELL else "filled"
        return OrderResult(id=f"f-{len(self.orders)}", symbol=order.symbol, side=order.side, qty=order.qty,
                           status=status, filled_qty=order.qty if status == "filled" else 0.0,
                           filled_avg_price=100.0 if status == "filled" else None,
                           reason="insufficient qty" if status == "rejected" else "")

    def cancel_all_orders(self):
        self.cancelled += 1


# --------------------------------------------------------------------------- parser / basics


def test_strategies_lists_every_strategy_with_defaults_and_warmup(capsys):
    code, out, _ = run(capsys, "strategies")
    assert code == 0
    for name in STRATEGIES:
        assert name in out
    assert "fast=20, slow=50" in out
    assert "needs 201 bars" in out  # rsi_reversion warm-up
    assert "Trend following" in out
    hint = next(line for line in out.splitlines() if "test it before trading" in line)
    assert "-c configs/" in hint  # without a config the command fails (no ./config.yaml)


def test_no_command_prints_help_and_usage_exit_code(capsys):
    code, out, _ = run(capsys)
    assert code == 2
    assert "usage:" in out and "demo" in out


def test_help_exits_zero(capsys):
    code, out, _ = run(capsys, "--help")
    assert code == 0
    assert "flatten" in out


def test_unknown_command_is_a_usage_error(capsys):
    code, _, err = run(capsys, "moon")
    assert code == 2
    assert "invalid choice" in err


@pytest.mark.parametrize("value", ["0", "-5", "ten"])
def test_bars_must_be_a_positive_whole_number(capsys, value):
    code, _, err = run(capsys, "backtest", "--synthetic", "--bars", value)
    assert code == 2
    assert "--bars" in err


def test_synthetic_and_csv_are_mutually_exclusive(capsys, tmp_path):
    cfg = write_config(tmp_path)
    code, _, err = run(capsys, "-c", str(cfg), "backtest", "--synthetic", "--csv", "X=a.csv")
    assert code == 2
    assert "not allowed with" in err


@pytest.mark.parametrize("position", ["before", "after"])
def test_config_and_verbose_flags_work_before_or_after_the_command(capsys, tmp_path, position):
    cfg = write_config(tmp_path)
    argv = ["-c", str(cfg), "-v", "kill"] if position == "before" else ["kill", "-c", str(cfg), "-v"]
    code, _, _ = run(capsys, *argv)
    assert code == 0
    assert (tmp_path / "state" / KILL_FILE).exists()


def test_config_after_the_command_overrides_the_global_one(capsys, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    cfg_a = write_config(tmp_path)
    cfg_b = write_config(other, name="b.yaml")
    code, _, _ = run(capsys, "-c", str(cfg_a), "kill", "-c", str(cfg_b))
    assert code == 0
    assert (other / "state" / KILL_FILE).exists()
    assert not (tmp_path / "state" / KILL_FILE).exists()


def test_main_module_runs_via_python_dash_m(tmp_path):
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    proc = subprocess.run([sys.executable, "-m", "bot", "strategies"], cwd=tmp_path, env=env,
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert "sma_crossover" in proc.stdout


# --------------------------------------------------------------------------- config errors


def test_config_error_exits_2_with_a_friendly_message(capsys, tmp_path):
    cfg = write_config(tmp_path, risk={"stop_los_pct": 5})
    code, out, err = run(capsys, "-c", str(cfg), "status")
    assert code == 2
    assert "Configuration problem" in err
    assert "stop_loss_pct" in err  # "did you mean" hint from config validation
    assert "Traceback" not in err + out


def test_config_error_from_the_real_entry_point_has_no_traceback(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("mode: paper\nbroker: {type: sim}\nsymbols: [A]\napi_key: oops\n", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in SECRET_ENV}
    env["PYTHONPATH"] = str(ROOT)
    proc = subprocess.run([sys.executable, "-m", "bot", "-c", str(bad), "once"], cwd=tmp_path, env=env,
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 2
    assert "Traceback" not in proc.stderr
    assert ".env" in proc.stderr  # the secret-in-YAML message tells where keys belong


def test_missing_default_config_explains_how_to_get_started(capsys):
    code, _, err = run(capsys, "status")
    assert code == 2
    assert "config.yaml" in err and "python -m bot demo" in err


def test_default_config_yaml_in_the_working_directory_is_used(capsys, tmp_path):
    write_config(tmp_path, name="config.yaml")
    code, _, _ = run(capsys, "kill")
    assert code == 0
    assert (tmp_path / "state" / KILL_FILE).exists()


def test_invalid_yaml_is_a_config_error(capsys, tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("mode: [paper\n", encoding="utf-8")
    code, _, err = run(capsys, "-c", str(bad), "once")
    assert code == 2
    assert "YAML" in err
    code, _, err = run(capsys, "-c", str(bad), "kill")  # the emergency stop still works (default state_dir)
    assert code == 0 and "YAML" in err and (tmp_path / "state" / KILL_FILE).exists()


# --------------------------------------------------------------------------- kill / resume


def test_kill_then_resume_toggles_the_kill_switch(capsys, tmp_path):
    cfg = write_config(tmp_path)
    kill_file = tmp_path / "state" / KILL_FILE

    code, out, _ = run(capsys, "-c", str(cfg), "kill", "--reason", "going on vacation")
    assert code == 0
    assert kill_file.read_text(encoding="utf-8") == "going on vacation"
    assert "Kill switch is ON" in out and "resume" in out and "NOT sold" in out

    code, out, _ = run(capsys, "-c", str(cfg), "resume")
    assert code == 0
    assert not kill_file.exists()
    assert "OFF" in out and "going on vacation" in out


def test_kill_without_reason_writes_a_default_note(capsys, tmp_path):
    cfg = write_config(tmp_path)
    assert run(capsys, "-c", str(cfg), "kill")[0] == 0
    assert "manual kill switch" in (tmp_path / "state" / KILL_FILE).read_text(encoding="utf-8")


def test_kill_again_keeps_the_original_reason_unless_a_new_one_is_given(capsys, tmp_path):
    cfg = write_config(tmp_path)
    kill_file = tmp_path / "state" / KILL_FILE
    run(capsys, "-c", str(cfg), "kill", "--reason", "first")
    code, out, _ = run(capsys, "-c", str(cfg), "kill")
    assert code == 0
    assert "already ON (first)" in out
    assert kill_file.read_text(encoding="utf-8") == "first"
    run(capsys, "-c", str(cfg), "kill", "--reason", "second")
    assert kill_file.read_text(encoding="utf-8") == "second"


def test_resume_when_not_killed_is_a_harmless_no_op(capsys, tmp_path):
    cfg = write_config(tmp_path)
    code, out, _ = run(capsys, "-c", str(cfg), "resume")
    assert code == 0
    assert "already OFF" in out
    assert not (tmp_path / "state" / KILL_FILE).exists()


def test_kill_hints_repeat_the_config_path(capsys, tmp_path):
    cfg = write_config(tmp_path, name="my bot.yaml")
    _, out, _ = run(capsys, "-c", str(cfg), "kill")
    assert f"python -m bot resume -c '{cfg}'" in out  # quoted: the path has a space


# --------------------------------------------------------------------------- flatten


def test_flatten_refuses_without_yes_and_touches_nothing(capsys, tmp_path, monkeypatch):
    cfg = write_config(tmp_path)
    forbid_make_broker(monkeypatch)
    code, out, err = run(capsys, "-c", str(cfg), "flatten")
    assert code == 2
    assert "--yes" in err and "Nothing was done" in err
    assert not (tmp_path / "state").exists()


def test_flatten_with_yes_sells_every_paper_position(capsys, tmp_path):
    cfg = write_config(tmp_path)
    broker = paper_broker(tmp_path)
    for symbol in ("DEMO1", "DEMO2"):
        assert broker.submit_order(OrderRequest(symbol, Side.BUY, 5.0)).status == "filled"

    code, out, _ = run(capsys, "-c", str(cfg), "flatten", "--yes")
    assert code == 0
    assert "SELL 5 DEMO1: filled" in out and "SELL 5 DEMO2: filled" in out
    assert "2 of 2 close order(s) sent" in out
    assert "kill" in out  # hint: the bot may buy again
    assert paper_broker(tmp_path).get_positions() == {}


def test_flatten_with_no_positions_says_so(capsys, tmp_path):
    cfg = write_config(tmp_path)
    code, out, _ = run(capsys, "-c", str(cfg), "flatten", "--yes")
    assert code == 0
    assert "No open positions" in out


def test_flatten_reports_rejections_with_exit_code_1(capsys, tmp_path, monkeypatch):
    cfg = write_config(tmp_path)
    fake = FakeBroker(positions={"DEMO1": Position("DEMO1", 2.0, 90.0, 100.0)}, reject_sells=True)
    monkeypatch.setattr("bot.brokers.make_broker", lambda cfg, env=None: fake)
    code, out, _ = run(capsys, "-c", str(cfg), "flatten", "--yes")
    assert code == 1
    assert "REJECTED" in out
    assert fake.cancelled == 1  # working orders cancelled first
    assert [(o.symbol, o.side, o.qty) for o in fake.orders] == [("DEMO1", Side.SELL, 2.0)]


def test_flatten_broker_error_exits_1_without_traceback(capsys, tmp_path, monkeypatch):
    cfg = write_config(tmp_path)

    class Down(FakeBroker):
        def cancel_all_orders(self):
            raise BrokerError("exchange unreachable")

    monkeypatch.setattr("bot.brokers.make_broker", lambda cfg, env=None: Down())
    code, _, err = run(capsys, "-c", str(cfg), "flatten", "--yes")
    assert code == 1
    assert "Broker error: exchange unreachable" in err
    assert "Traceback" not in err


def test_flatten_of_paper_account_is_refused_while_the_bot_runs(capsys, tmp_path):
    cfg = write_config(tmp_path)
    broker = paper_broker(tmp_path)
    broker.submit_order(OrderRequest("DEMO1", Side.BUY, 5.0))
    lock = cli._InstanceLock(tmp_path / "state")
    if not lock.acquire() or cli.fcntl is None:
        pytest.skip("file locking unavailable")
    try:
        code, _, err = run(capsys, "-c", str(cfg), "flatten", "--yes")
    finally:
        lock.release()
    assert code == 1
    assert "running" in err
    assert "DEMO1" in paper_broker(tmp_path).get_positions()  # nothing sold


def test_flatten_on_a_real_broker_proceeds_while_the_bot_runs(capsys, tmp_path, monkeypatch):
    cfg = write_config(tmp_path)
    fake = FakeBroker(positions={"DEMO1": Position("DEMO1", 1.0, 90.0, 100.0)})
    monkeypatch.setattr("bot.brokers.make_broker", lambda cfg, env=None: fake)
    lock = cli._InstanceLock(tmp_path / "state")
    if not lock.acquire() or cli.fcntl is None:
        pytest.skip("file locking unavailable")
    try:
        code, out, _ = run(capsys, "-c", str(cfg), "flatten", "--yes")
    finally:
        lock.release()
    assert code == 0
    assert "the bot is running" in out
    assert len(fake.orders) == 1


# --------------------------------------------------------------------------- live-mode safety


def test_live_config_without_confirmation_is_refused_before_any_broker(capsys, tmp_path, monkeypatch):
    cfg = live_alpaca_config(tmp_path)
    forbid_make_broker(monkeypatch)
    for command in (["once"], ["run", "--max-ticks", "1"], ["status"], ["flatten", "--yes"]):
        code, _, err = run(capsys, "-c", str(cfg), *command)
        assert code == 2, command
        assert LIVE_CONFIRM_ENV in err and "Traceback" not in err


def test_live_confirmation_must_match_exactly(capsys, tmp_path, monkeypatch):
    cfg = live_alpaca_config(tmp_path)
    forbid_make_broker(monkeypatch)
    monkeypatch.setenv(LIVE_CONFIRM_ENV, LIVE_CONFIRM_VALUE.lower())
    code, _, err = run(capsys, "-c", str(cfg), "once")
    assert code == 2
    assert LIVE_CONFIRM_ENV in err


def test_live_run_prints_a_loud_warning_banner(capsys, tmp_path, monkeypatch):
    cfg = live_alpaca_config(tmp_path)
    monkeypatch.setenv(LIVE_CONFIRM_ENV, LIVE_CONFIRM_VALUE)
    fake = PaperBroker(SyntheticFeed(seed=1))  # stands in for Alpaca: never touches a network
    monkeypatch.setattr("bot.brokers.make_broker", lambda cfg, env=None: fake)
    code, out, _ = run(capsys, "-c", str(cfg), "run", "--max-ticks", "1")
    assert code == 0
    assert "LIVE TRADING" in out and "REAL money" in out
    assert "LIVE (real money)" in out
    assert "flatten --yes" in out


def test_live_run_can_be_aborted_during_the_start_delay(capsys, tmp_path, monkeypatch):
    cfg = live_alpaca_config(tmp_path)
    monkeypatch.setenv(LIVE_CONFIRM_ENV, LIVE_CONFIRM_VALUE)
    fake = FakeBroker()
    monkeypatch.setattr("bot.brokers.make_broker", lambda cfg, env=None: fake)
    monkeypatch.setattr(cli, "LIVE_START_DELAY_SECONDS", 30)
    real_wait = threading.Event.wait

    def instant_abort(self, timeout=None):  # simulate Ctrl-C during the countdown
        self.set()
        return real_wait(self, 0)

    monkeypatch.setattr(threading.Event, "wait", instant_abort)
    code, out, _ = run(capsys, "-c", str(cfg), "run")
    assert code == 0
    assert "Aborted" in out
    assert fake.orders == [] and fake.bar_requests == []


def test_backtest_on_a_live_config_fetches_data_through_a_paper_broker(capsys, tmp_path, monkeypatch):
    cfg = live_alpaca_config(tmp_path)  # no live confirmation set on purpose
    bars = generate_synthetic_bars(400, "1m")
    seen = []

    def factory(cfg, env=None):
        seen.append((cfg.mode, cfg.broker.use_sandbox))
        return FakeBroker(bars=bars)

    monkeypatch.setattr("bot.brokers.make_broker", factory)
    code, out, _ = run(capsys, "-c", str(cfg), "backtest", "--bars", "400", "--out", str(tmp_path / "out"))
    assert code == 0, out
    assert seen == [("paper", False)]


# --------------------------------------------------------------------------- status


def test_status_on_sim_broker_shows_account_state_and_kill_switch(capsys, tmp_path):
    cfg = write_config(tmp_path)
    code, out, _ = run(capsys, "-c", str(cfg), "status")
    assert code == 0
    assert "PAPER" in out
    assert "10,000.00 USD" in out
    assert "Positions (0)" in out
    assert "has not run yet" in out
    assert "Kill switch: OFF" in out


def test_status_shows_positions_bot_state_and_active_kill_switch(capsys, tmp_path):
    cfg = write_config(tmp_path)
    paper_broker(tmp_path).submit_order(OrderRequest("DEMO1", Side.BUY, 3.0))
    StateStore(tmp_path / "state" / cli.STATE_FILE).save(BotState(
        day="2026-09-24", day_start_equity=10_000.0, trades_today=2, halted_today=True,
        last_signal_bar={"DEMO1": "2026-09-24T14:00:00+00:00"}, consecutive_errors=1,
        last_tick_at="2026-09-24T14:01:00+00:00"))
    run(capsys, "-c", str(cfg), "kill", "--reason", "maintenance")

    code, out, _ = run(capsys, "-c", str(cfg), "status")
    assert code == 0
    assert "Positions (1)" in out and "DEMO1" in out and "P&L %" in out
    assert "2 of max 20" in out
    assert "YES" in out  # daily loss halt
    assert "Errors in a row   1" in out
    assert "2026-09-24T14:00:00+00:00" in out
    assert "Kill switch: ON (maintenance)" in out


def test_status_leaves_a_corrupt_state_file_in_place(capsys, tmp_path):
    cfg = write_config(tmp_path)
    state_file = tmp_path / "state" / cli.STATE_FILE
    state_file.parent.mkdir(parents=True)
    state_file.write_text("{not json", encoding="utf-8")
    code, out, _ = run(capsys, "-c", str(cfg), "status")
    assert code == 0
    assert "unreadable" in out
    assert state_file.read_text(encoding="utf-8") == "{not json"


def test_status_broker_failure_still_shows_local_state_and_exits_1(capsys, tmp_path, monkeypatch):
    cfg = write_config(tmp_path)
    monkeypatch.setattr("bot.brokers.make_broker", lambda cfg, env=None: FakeBroker(fail_account=True))
    run(capsys, "-c", str(cfg), "kill")
    code, out, _ = run(capsys, "-c", str(cfg), "status")
    assert code == 1
    assert "connection refused" in out
    assert "Kill switch: ON" in out


# --------------------------------------------------------------------------- once / run


def test_once_on_sim_broker_returns_0_and_saves_state(capsys, tmp_path):
    cfg = write_config(tmp_path)
    code, out, _ = run(capsys, "-c", str(cfg), "once")
    assert code == 0, out
    assert "PAPER" in out and "DEMO1" in out and "DEMO2" in out
    assert "Equity:" in out
    state = json.loads((tmp_path / "state" / cli.STATE_FILE).read_text(encoding="utf-8"))
    assert state["last_tick_at"] and state["consecutive_errors"] == 0
    assert set(state["last_signal_bar"]) == {"DEMO1", "DEMO2"}


def test_once_returns_1_when_the_tick_had_errors(capsys, tmp_path, monkeypatch):
    cfg = write_config(tmp_path)
    monkeypatch.setattr("bot.brokers.make_broker", lambda cfg, env=None: FakeBroker(fail_account=True))
    code, out, _ = run(capsys, "-c", str(cfg), "once")
    assert code == 1
    assert "ERROR: connection refused" in out


def test_once_with_kill_switch_places_no_orders(capsys, tmp_path, monkeypatch):
    cfg = write_config(tmp_path)
    fake = FakeBroker()
    monkeypatch.setattr("bot.brokers.make_broker", lambda cfg, env=None: fake)
    run(capsys, "-c", str(cfg), "kill")
    code, out, _ = run(capsys, "-c", str(cfg), "once")
    assert code == 0
    assert "kill switch is ON" in out
    assert fake.orders == [] and fake.bar_requests == []


def test_once_refuses_while_another_bot_process_holds_the_lock(capsys, tmp_path, monkeypatch):
    if cli.fcntl is None:
        pytest.skip("file locking unavailable")
    cfg = write_config(tmp_path)
    forbid_make_broker(monkeypatch)
    lock = cli._InstanceLock(tmp_path / "state")
    assert lock.acquire()
    try:
        code, _, err = run(capsys, "-c", str(cfg), "once")
    finally:
        lock.release()
    assert code == 1
    assert "already running" in err
    assert run(capsys, "-c", str(cfg), "kill")[0] == 0  # kill still works while locked


def test_lock_is_released_after_once(capsys, tmp_path):
    cfg = write_config(tmp_path)
    assert run(capsys, "-c", str(cfg), "once")[0] == 0
    lock = cli._InstanceLock(tmp_path / "state")
    assert lock.acquire()
    lock.release()


def test_run_prints_a_banner_and_stops_after_max_ticks(capsys, tmp_path):
    cfg = write_config(tmp_path)
    code, out, _ = run(capsys, "-c", str(cfg), "run", "--max-ticks", "1")
    assert code == 0
    for text in ("PAPER (simulated money)", "DEMO1, DEMO2", "sma_crossover (fast=10, slow=30)",
                 "stop-loss 5%", "daily loss limit 3%", "Ctrl-C", "Bot stopped"):
        assert text in out
    assert "LIVE TRADING" not in out
    assert (tmp_path / "state" / cli.STATE_FILE).exists()


def test_signal_handler_sets_the_stop_event_and_is_restored(monkeypatch):
    before = signal.getsignal(signal.SIGINT)
    stop = threading.Event()
    with cli._stop_on_signals(stop):
        os.kill(os.getpid(), signal.SIGINT)  # no KeyboardInterrupt: the handler just sets the event
        assert stop.wait(5)
        with pytest.raises(KeyboardInterrupt):  # a second Ctrl-C forces the exit
            signal.getsignal(signal.SIGINT)(signal.SIGINT, None)
    assert signal.getsignal(signal.SIGINT) is before


# --------------------------------------------------------------------------- backtest


def test_backtest_synthetic_prints_summary_and_saves_results(capsys, tmp_path):
    cfg = write_config(tmp_path)
    out_dir = tmp_path / "out"
    code, out, _ = run(capsys, "-c", str(cfg), "backtest", "--synthetic", "--bars", "300", "--out", str(out_dir))
    assert code == 0, out
    assert "Total return" in out and "synthetic" in out
    assert {p.name for p in out_dir.iterdir()} >= {"equity.csv", "trades.csv", "metrics.json"}


def test_backtest_default_output_folder_is_results_timestamp(capsys, tmp_path):
    cfg = write_config(tmp_path)
    assert run(capsys, "-c", str(cfg), "backtest", "--synthetic", "--bars", "200")[0] == 0
    runs = list((tmp_path / "results").iterdir())
    assert len(runs) == 1 and (runs[0] / "metrics.json").exists()


def test_backtest_from_csv_files(capsys, tmp_path):
    cfg = write_config(tmp_path, timeframe="1d")
    path = tmp_path / "spy.csv"
    generate_synthetic_bars(300, "1d").to_csv(path)
    out_dir = tmp_path / "out"
    code, out, _ = run(capsys, "-c", str(cfg), "backtest", "--csv", f"SPY={path}", "--bars", "250",
                       "--out", str(out_dir))
    assert code == 0, out
    assert "SPY 250 bars" in out
    assert (out_dir / "metrics.json").exists()


@pytest.mark.parametrize("spec", ["SPY", "=a.csv", "SPY="])
def test_backtest_csv_spec_must_be_symbol_equals_path(capsys, tmp_path, spec):
    cfg = write_config(tmp_path)
    code, _, err = run(capsys, "-c", str(cfg), "backtest", "--csv", spec)
    assert code == 2
    assert "SYMBOL=PATH" in err


def test_backtest_missing_csv_is_a_friendly_error(capsys, tmp_path):
    cfg = write_config(tmp_path)
    code, _, err = run(capsys, "-c", str(cfg), "backtest", "--csv", "SPY=nope.csv")
    assert code == 2
    assert "nope.csv" in err and "Traceback" not in err


def test_backtest_duplicate_csv_symbol_is_refused(capsys, tmp_path):
    cfg = write_config(tmp_path)
    path = tmp_path / "a.csv"
    generate_synthetic_bars(100, "1d").to_csv(path)
    code, _, err = run(capsys, "-c", str(cfg), "backtest", "--csv", f"A={path}", "--csv", f"A={path}")
    assert code == 2
    assert "twice" in err


def test_backtest_with_too_little_history_is_refused(capsys, tmp_path):
    cfg = write_config(tmp_path)
    code, _, err = run(capsys, "-c", str(cfg), "backtest", "--synthetic", "--bars", "20")
    assert code == 2
    assert "warm up" in err


def test_backtest_fetches_bars_from_the_broker_by_default(capsys, tmp_path, monkeypatch):
    cfg = write_config(tmp_path)
    fake = FakeBroker(bars=generate_synthetic_bars(500, "1m"))
    monkeypatch.setattr("bot.brokers.make_broker", lambda cfg, env=None: fake)
    code, out, _ = run(capsys, "-c", str(cfg), "backtest", "--out", str(tmp_path / "o"))
    assert code == 0, out
    # One extra bar each: the venue's still-forming bar is dropped.
    assert fake.bar_requests == [("DEMO1", "1m", 1001), ("DEMO2", "1m", 1001)]
    assert "got 500 of the 1,000" in out  # the venue returned less history than asked
    assert fake.orders == []  # a backtest never trades


def test_backtest_broker_data_error_exits_1(capsys, tmp_path, monkeypatch):
    cfg = write_config(tmp_path)
    monkeypatch.setattr("bot.brokers.make_broker", lambda cfg, env=None: FakeBroker(bars=None))
    code, _, err = run(capsys, "-c", str(cfg), "backtest", "--bars", "100")
    assert code == 1
    assert "Broker error: no data" in err


def capture_backtest_config(monkeypatch) -> dict:
    captured: dict = {}
    import bot.backtest as backtest_mod

    real = backtest_mod.run_backtest

    def spy(strategy, data, bt_cfg):
        captured["cfg"] = bt_cfg
        return real(strategy, data, bt_cfg)

    monkeypatch.setattr(backtest_mod, "run_backtest", spy)
    return captured


def alpaca_daily_config(tmp_path: Path) -> Path:
    return write_config(tmp_path, symbols=["SPY"], broker={"type": "alpaca"}, timeframe="1d",
                        strategy={"name": "sma_crossover", "params": {"fast": 5, "slow": 20}})


def weekday_bars(n: int):
    frame = generate_synthetic_bars(n * 7 // 5 + 10, "1d")
    return frame[frame.index.dayofweek < 5].tail(n)


def test_backtest_alpaca_data_annualises_with_252_days(capsys, tmp_path, monkeypatch):
    cfg = alpaca_daily_config(tmp_path)
    captured = capture_backtest_config(monkeypatch)
    monkeypatch.setattr("bot.brokers.make_broker", lambda cfg, env=None: FakeBroker(bars=weekday_bars(300)))
    code, _, _ = run(capsys, "-c", str(cfg), "backtest", "--bars", "250", "--out", str(tmp_path / "o"))
    assert code == 0
    bt = captured["cfg"]
    assert bt.trading_days_per_year == 252
    assert (bt.timeframe, bt.lookback, bt.timezone) == ("1d", 300, "America/New_York")  # Alpaca's trading day
    assert (bt.fee_pct, bt.slippage_pct, bt.starting_cash) == (0.1, 0.05, 10000.0)


def test_backtest_synthetic_data_is_24_7_so_it_annualises_with_365_days_even_for_alpaca(
        capsys, tmp_path, monkeypatch):
    cfg = alpaca_daily_config(tmp_path)
    captured = capture_backtest_config(monkeypatch)
    code, _, _ = run(capsys, "-c", str(cfg), "backtest", "--synthetic", "--bars", "200", "--out", str(tmp_path / "o"))
    assert code == 0
    assert captured["cfg"].trading_days_per_year == 365


def test_backtest_weekday_only_csv_annualises_with_252_days_under_a_crypto_config(capsys, tmp_path, monkeypatch):
    cfg = write_config(tmp_path, timeframe="1d")  # the sim broker (365 by broker type)
    path = tmp_path / "spy.csv"
    weekday_bars(300).to_csv(path)
    captured = capture_backtest_config(monkeypatch)
    code, out, err = run(capsys, "-c", str(cfg), "backtest", "--csv", f"SPY={path}", "--out", str(tmp_path / "o"))
    assert code == 0, err
    assert captured["cfg"].trading_days_per_year == 252
    assert "252" in out


def test_backtest_refuses_csv_bars_that_do_not_match_the_config_timeframe(capsys, tmp_path):
    cfg = write_config(tmp_path, timeframe="4h")
    path = tmp_path / "btc_daily.csv"
    generate_synthetic_bars(400, "1d").to_csv(path)
    code, _, err = run(capsys, "-c", str(cfg), "backtest", "--csv", f"BTC={path}", "--out", str(tmp_path / "o"))
    assert code == 2
    assert "1d" in err and "4h" in err and "timeframe" in err
    assert not (tmp_path / "o").exists()


def test_backtest_from_the_broker_does_not_report_a_false_history_limit(capsys, tmp_path):
    cfg = write_config(tmp_path)  # the sim broker: it has no history limit
    code, out, _ = run(capsys, "-c", str(cfg), "backtest", "--bars", "1000", "--out", str(tmp_path / "o"))
    assert code == 0, out
    assert "Note: got" not in out
    assert "DEMO1 1,000 bars" in out and "DEMO2 1,000 bars" in out


# --------------------------------------------------------------------------- demo


def test_demo_runs_end_to_end_without_touching_the_configs_state(capsys, tmp_path):
    cfg = write_config(tmp_path)
    code, out, _ = run(capsys, "-c", str(cfg), "demo", "--bars", "400")
    assert code == 0, out
    for name in STRATEGIES:
        assert name in out
    assert "Buy & hold" in out and "Max drawdown" in out
    assert "Check 1 of 3" in out and "Check 3 of 3" in out
    assert "Paper account after 3 checks" in out
    assert not (tmp_path / "state").exists()  # the demo trades in a throwaway folder
    assert not (tmp_path / "logs").exists()


def test_demo_uses_configs_demo_yaml_by_default(capsys, monkeypatch):
    seen = []
    real = cli.load_config
    monkeypatch.setattr(cli, "load_config", lambda path, env=None: seen.append(Path(path)) or real(path, env))
    code, _, _ = run(capsys, "demo", "--bars", "250", "--ticks", "1")
    assert code == 0
    assert seen == [ROOT / "configs" / "demo.yaml"]


def test_demo_ignores_notification_secrets_in_the_environment(capsys, tmp_path, monkeypatch):
    cfg = write_config(tmp_path)
    monkeypatch.setenv("NOTIFY_WEBHOOK_URL", "https://example.invalid/hook")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    import bot.notify as notify_mod

    created, posts = [], []
    real_init = notify_mod.Notifier.__init__

    def spy_init(self, *args, **kwargs):
        real_init(self, *args, **kwargs)
        created.append(self)

    monkeypatch.setattr(notify_mod.Notifier, "__init__", spy_init)
    monkeypatch.setattr(notify_mod.Notifier, "_post", lambda self, *args: posts.append(args))
    assert run(capsys, "-c", str(cfg), "demo", "--bars", "250", "--ticks", "2")[0] == 0
    assert created and not any(n.enabled for n in created)
    assert posts == []


def test_demo_refuses_a_non_sim_config(capsys, tmp_path):
    cfg = write_config(tmp_path, symbols=["SPY"], broker={"type": "alpaca"})
    code, _, err = run(capsys, "-c", str(cfg), "demo")
    assert code == 2
    assert "simulator" in err


def test_demo_needs_enough_bars_for_every_strategy(capsys, tmp_path):
    cfg = write_config(tmp_path)
    code, _, err = run(capsys, "-c", str(cfg), "demo", "--bars", "100")
    assert code == 2
    assert "--bars" in err


# --------------------------------------------------------------------------- .env and logging


def test_env_files_are_loaded_without_overriding_real_environment(capsys, tmp_path, monkeypatch):
    for name in ("BOT_CLI_TEST_FROM_FILE", "BOT_CLI_TEST_REAL", "BOT_CLI_TEST_CWD"):
        monkeypatch.setenv(name, "x")  # registered so monkeypatch restores (deletes) them afterwards
        monkeypatch.delenv(name)
    monkeypatch.setenv("BOT_CLI_TEST_REAL", "real")
    conf_dir = tmp_path / "conf"
    conf_dir.mkdir()
    cfg = write_config(conf_dir, name="c.yaml")
    (conf_dir / ".env").write_text("BOT_CLI_TEST_FROM_FILE=file\nBOT_CLI_TEST_REAL=file\n", encoding="utf-8")
    (tmp_path / ".env").write_text("BOT_CLI_TEST_CWD=cwd\n", encoding="utf-8")  # tmp_path is the CWD

    assert run(capsys, "-c", str(cfg), "kill")[0] == 0
    assert os.environ["BOT_CLI_TEST_FROM_FILE"] == "file"
    assert os.environ["BOT_CLI_TEST_CWD"] == "cwd"
    assert os.environ["BOT_CLI_TEST_REAL"] == "real"


def test_commands_log_to_a_rotating_bot_log_in_log_dir(capsys, tmp_path):
    cfg = write_config(tmp_path)
    assert run(capsys, "-c", str(cfg), "kill", "--reason", "audit me")[0] == 0
    text = (tmp_path / "logs" / "bot.log").read_text(encoding="utf-8")
    assert "audit me" in text


def test_logging_handlers_are_removed_after_each_command(capsys, tmp_path):
    root = logging.getLogger()
    before, level = list(root.handlers), root.level
    cfg = write_config(tmp_path)
    run(capsys, "-c", str(cfg), "kill")
    run(capsys, "-c", str(tmp_path / "missing.yaml"), "kill")
    assert root.handlers == before
    assert root.level == level


def test_log_setup_attaches_a_rotating_file_handler(tmp_path):
    setup = cli._LogSetup(logging.ERROR)
    try:
        setup.add_file(tmp_path / "logs")
        handler = next(h for h in setup.handlers if isinstance(h, logging.handlers.RotatingFileHandler))
        assert handler.maxBytes == 5 * 1024 * 1024 and handler.backupCount == 5
        assert Path(handler.baseFilename) == tmp_path / "logs" / "bot.log"
    finally:
        setup.close()


def test_unwritable_log_dir_falls_back_to_console_logging(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("not a folder", encoding="utf-8")
    setup = cli._LogSetup(logging.ERROR)
    try:
        setup.add_file(blocker / "logs")  # mkdir fails: must not raise
        assert len(setup.handlers) == 1
    finally:
        setup.close()


# --------------------------------------------------------------------------- regression: review findings


def test_live_banner_emergency_commands_use_the_same_config(tmp_path):
    cfg = load_config(live_alpaca_config(tmp_path), env={})
    banner = cli._banner(cfg, argparse.Namespace(config="x/live.yaml"))
    assert "python -m bot kill -c x/live.yaml" in banner
    assert "python -m bot flatten --yes -c x/live.yaml" in banner
    for line in banner.splitlines():
        if "python -m bot" in line:
            assert "-c x/live.yaml" in line, line


def test_risk_line_without_a_stop_loss_does_not_claim_a_risk_per_trade():
    lines = cli._risk_lines(RiskConfig(stop_loss_pct=None, risk_per_trade_pct=2.0, max_position_pct=45.0))
    assert "at risk per trade" not in lines[0]
    assert "no stop-loss" in lines[0] and "45%" in lines[0]
    with_stop = cli._risk_lines(RiskConfig(stop_loss_pct=5.0, risk_per_trade_pct=2.0))
    assert "2% of equity at risk per trade" in with_stop[0] and "stop-loss 5%" in with_stop[0]


def test_missing_config_hint_keeps_state_inside_the_project(capsys):
    code, _, err = run(capsys, "status")
    assert code == 2
    assert "to config.yaml" not in err  # the examples' ../state paths would escape the project
    assert "configs/my.yaml" in err


@pytest.mark.parametrize("name", ["demo.yaml", "stocks.yaml", "crypto.yaml"])
def test_example_configs_keep_state_and_logs_inside_the_project(name):
    cfg = load_config(ROOT / "configs" / name, env={})
    assert Path(cfg.state_dir).resolve().is_relative_to(ROOT / "state")
    assert Path(cfg.log_dir).resolve().is_relative_to(ROOT / "logs")


def test_kill_resume_and_status_show_where_the_kill_file_is(capsys, tmp_path):
    cfg = write_config(tmp_path)
    kill_file = str((tmp_path / "state" / KILL_FILE).resolve())
    _, out, _ = run(capsys, "-c", str(cfg), "kill")
    assert kill_file in out
    _, out, _ = run(capsys, "-c", str(cfg), "status")
    assert kill_file in out
    _, out, _ = run(capsys, "-c", str(cfg), "resume")
    assert kill_file in out


def test_status_flags_positions_the_bot_does_not_manage(capsys, tmp_path):
    cfg = write_config(tmp_path)  # symbols: DEMO1, DEMO2
    paper_broker(tmp_path).submit_order(OrderRequest("DEMO3", Side.BUY, 2.0))
    code, out, _ = run(capsys, "-c", str(cfg), "status")
    assert code == 0
    assert "DEMO3" in out and "not managed" in out


def test_flatten_help_says_it_is_account_wide_on_alpaca(capsys):
    code, out, _ = run(capsys, "flatten", "-h")
    assert code == 0
    assert "Alpaca" in out and "account" in out
    assert "short" in " ".join(out.split())  # Alpaca also buys back a short position


def test_flatten_warns_that_it_also_sells_what_the_bot_did_not_buy_on_an_exchange(capsys, tmp_path):
    code, _, err = run(capsys, "-c", str(write_config(tmp_path)), "flatten")
    assert code == 2
    assert "exchange" in err and "coins" in err and "did not buy" in err
    _, out, _ = run(capsys, "flatten", "-h")
    assert "exchange" in out


class _FakeMsvcrt:
    """msvcrt.locking emulated with flock, so the Windows branch runs on Linux."""

    LK_UNLCK, LK_NBLCK = 0, 2

    def __init__(self, real_fcntl) -> None:
        self.fcntl = real_fcntl
        self.calls: list[int] = []

    def locking(self, fd: int, mode: int, nbytes: int) -> None:
        self.calls.append(mode)
        if mode == self.LK_NBLCK:
            self.fcntl.flock(fd, self.fcntl.LOCK_EX | self.fcntl.LOCK_NB)
        else:
            self.fcntl.flock(fd, self.fcntl.LOCK_UN)


def test_instance_lock_works_without_fcntl_through_msvcrt(tmp_path, monkeypatch):
    real_fcntl = cli.fcntl
    if real_fcntl is None:
        pytest.skip("needs fcntl to emulate msvcrt")
    fake = _FakeMsvcrt(real_fcntl)
    monkeypatch.setattr(cli, "fcntl", None)  # as on Windows
    monkeypatch.setattr(cli, "msvcrt", fake, raising=False)
    first, second = cli._InstanceLock(tmp_path), cli._InstanceLock(tmp_path)

    assert first.acquire() is True
    assert second.acquire() is False  # a second bot on the same state folder is refused
    first.release()
    assert second.acquire() is True
    second.release()
    assert fake.LK_UNLCK in fake.calls


def test_instance_lock_without_any_locking_warns_loudly(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(cli, "fcntl", None)
    monkeypatch.setattr(cli, "msvcrt", None, raising=False)
    with caplog.at_level(logging.WARNING):
        assert cli._InstanceLock(tmp_path).acquire() is True
    assert any("lock" in r.getMessage().lower() for r in caplog.records)


# --------------------------------------------------------------------------- regression: emergency commands


def invalid_config(tmp_path: Path) -> Path:
    """Edited while the bot runs: the strategy now needs 201 bars, lookback is only 100."""
    return write_config(tmp_path, name="edited.yaml", bars_lookback=100, strategy={"params": {"slow": 200}})


def test_kill_and_resume_still_work_when_the_config_no_longer_validates(capsys, tmp_path):
    cfg = invalid_config(tmp_path)
    kill_file = tmp_path / "state" / KILL_FILE

    code, out, err = run(capsys, "-c", str(cfg), "kill", "--reason", "market crash")
    assert code == 0
    assert kill_file.read_text(encoding="utf-8") == "market crash"
    assert "bars_lookback" in err  # the config problem is still shown
    assert str(kill_file.resolve()) in out

    code, out, _ = run(capsys, "-c", str(cfg), "resume")
    assert code == 0 and not kill_file.exists()


def test_kill_still_works_after_a_yaml_indentation_mistake(capsys, tmp_path):
    # The most common editing slip: one risk key indented by one space.
    path = tmp_path / "configs" / "my.yaml"
    path.parent.mkdir()
    text = (ROOT / "configs" / "demo.yaml").read_text(encoding="utf-8")
    assert "\n  max_open_positions:" in text
    path.write_text(text.replace("\n  max_open_positions:", "\n max_open_positions:"), encoding="utf-8")
    kill_file = tmp_path / "state" / "demo" / KILL_FILE  # demo.yaml: state_dir: ../state/demo

    code, out, err = run(capsys, "-c", str(path), "kill")
    assert code == 0 and kill_file.exists()
    assert "not valid YAML" in err and str(kill_file.resolve()) in out
    _, _, err = run(capsys, "-c", str(path), "status")
    assert str(kill_file.resolve()) in err
    assert run(capsys, "-c", str(path), "resume")[0] == 0 and not kill_file.exists()


@pytest.mark.parametrize("command", [["flatten", "--yes"], ["status"]])
def test_other_commands_with_an_invalid_config_say_where_the_kill_file_is(capsys, tmp_path, command):
    cfg = invalid_config(tmp_path)
    code, _, err = run(capsys, "-c", str(cfg), *command)
    assert code == 2
    assert "bars_lookback" in err
    assert str((tmp_path / "state" / KILL_FILE).resolve()) in err and "kill" in err


def test_kill_says_plainly_that_stop_losses_stop_too(capsys, tmp_path):
    cfg = write_config(tmp_path)
    _, out, _ = run(capsys, "-c", str(cfg), "kill", "--reason", "vacation")
    assert "stop-loss" in out.lower() and "unprotected" in out
    _, out, _ = run(capsys, "-c", str(cfg), "status")
    assert "not even stop-loss" in out


def test_readme_does_not_describe_the_kill_switch_as_stopping_only_new_orders():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    (line,) = [line for line in readme.splitlines() if " kill --reason" in line]
    assert "손절" in line  # says that stop-loss sells stop as well


def test_run_banner_says_where_alerts_go_or_that_none_will_be_sent(tmp_path):
    args = cli.build_parser().parse_args(["run"])
    cfg = load_config(write_config(tmp_path), env={})
    assert "none" in cli._banner(cfg, args).split("Notify", 1)[1].splitlines()[0]
    cfg = load_config(write_config(tmp_path), env={"TELEGRAM_BOT_TOKEN": "1:a", "TELEGRAM_CHAT_ID": "2"})
    assert "Telegram" in cli._banner(cfg, args).split("Notify", 1)[1].splitlines()[0]


# --------------------------------------------------------------------------- regression: status, flatten, CI


def test_status_warns_about_holdings_it_could_not_price_and_exits_1(capsys, tmp_path, monkeypatch):
    cfg = write_config(tmp_path)

    class Unpriced(FakeBroker):
        def get_account(self):
            return Account(equity=1000.0, cash=800.0, buying_power=800.0, unpriced=("DEMO1", "DEMO2"))

    fake = Unpriced(positions={"DEMO1": Position("DEMO1", 2.0, 100.0, 100.0)})
    monkeypatch.setattr("bot.brokers.make_broker", lambda cfg, env=None: fake)
    code, out, _ = run(capsys, "-c", str(cfg), "status")
    assert code == 1
    assert "WARNING" in out and "DEMO1" in out and "may be wrong" in out
    demo1_row = next(line for line in out.splitlines() if line.strip().startswith("DEMO1"))
    assert "+0.00%" not in demo1_row and "unknown" in demo1_row
    assert "DEMO2" in out and "cannot be priced" in out  # held, but missing from the positions list


def test_status_names_a_crypto_holding_whose_price_cannot_be_read(capsys, tmp_path, monkeypatch):
    import ccxt

    from bot.brokers.ccxt_broker import CCXTBroker
    from tests.test_ccxt_broker import FakeExchange
    cfg = write_config(tmp_path, symbols=["BTC/USDT", "ETH/USDT"], broker={"type": "ccxt", "exchange": "fakex"})
    ex = FakeExchange()
    ex.set_balance("BTC", 0.5)
    ex.tickers["BTC/USDT"] = ccxt.NetworkError("ticker down")
    broker = CCXTBroker("fakex", ["BTC/USDT", "ETH/USDT"], api_key="k", secret="s", exchange=ex)
    monkeypatch.setattr("bot.brokers.make_broker", lambda cfg, env=None: broker)
    code, out, _ = run(capsys, "-c", str(cfg), "status")
    assert code == 1
    assert "BTC/USDT" in out and "cannot be priced" in out


def test_flatten_records_its_sells_in_trades_csv(capsys, tmp_path):
    cfg = write_config(tmp_path)
    paper_broker(tmp_path).submit_order(OrderRequest("DEMO1", Side.BUY, 4.0))
    assert run(capsys, "-c", str(cfg), "flatten", "--yes")[0] == 0
    import csv
    with (tmp_path / "logs" / "trades.csv").open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert [(r["symbol"], r["side"], r["status"]) for r in rows] == [("DEMO1", "sell", "filled")]
    assert "flatten" in rows[0]["reason"] and rows[0]["mode"] == "paper"


def test_flatten_still_reports_the_sells_it_made_when_a_later_one_fails(capsys, tmp_path, monkeypatch):
    cfg = write_config(tmp_path)

    class Flaky(FakeBroker):
        def submit_order(self, order):
            if order.symbol == "DEMO2":
                raise BrokerError("timeout while selling DEMO2")
            return super().submit_order(order)

    fake = Flaky(positions={"DEMO1": Position("DEMO1", 2.0, 90.0, 100.0),
                            "DEMO2": Position("DEMO2", 3.0, 90.0, 100.0)})
    monkeypatch.setattr("bot.brokers.make_broker", lambda cfg, env=None: fake)
    code, out, err = run(capsys, "-c", str(cfg), "flatten", "--yes")
    assert code == 1
    assert "SELL 2 DEMO1: filled" in out
    assert "timeout while selling DEMO2" in out + err
    assert "DEMO1" in (tmp_path / "logs" / "trades.csv").read_text(encoding="utf-8")


def test_once_on_github_actions_refuses_a_state_dir_the_workflow_does_not_keep(capsys, tmp_path, monkeypatch):
    # A config in a configs/ folder without state_dir: its state would land in
    # configs/state, which the workflow never caches, so every run forgets it.
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    configs = tmp_path / "configs"
    configs.mkdir()
    raw = yaml.safe_load((ROOT / "configs" / "demo.yaml").read_text(encoding="utf-8"))
    del raw["state_dir"]
    (configs / "x.yaml").write_text(yaml.safe_dump(raw), encoding="utf-8")
    forbid_make_broker(monkeypatch)
    code, _, err = run(capsys, "-c", str(configs / "x.yaml"), "once")
    assert code == 2
    assert "GitHub Actions" in err and "state_dir" in err


def test_the_actions_workflow_never_trades_or_saves_from_a_lost_state():
    # GitHub deletes a cache unused for 7 days: a blank state would forget what
    # the bot bought (no stop-loss) and, once saved, shadow the good cache.
    path = ROOT.parent / ".github" / "workflows" / "trading-bot.yml"
    if not path.exists():
        pytest.skip("the workflow lives outside this folder")
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    steps = {step.get("name"): step for step in workflow["jobs"]["tick"]["steps"]}
    restore = steps["Restore bot state"]
    assert restore["if"] == "${{ !inputs.fresh_state }}" and restore["with"]["fail-on-cache-miss"] is True
    assert "steps.restore.outputs.cache-matched-key != ''" in steps["Save bot state"]["if"]


def test_the_actions_workflow_fails_when_the_state_was_not_saved_and_runs_on_one_branch_only():
    # A failed cache save only warns; the next run would restore an older state.
    path = ROOT.parent / ".github" / "workflows" / "trading-bot.yml"
    if not path.exists():
        pytest.skip("the workflow lives outside this folder")
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    job = workflow["jobs"]["tick"]
    names = [step.get("name") for step in job["steps"]]
    check = job["steps"][names.index("Check the bot state was saved")]
    assert names.index("Check the bot state was saved") > names.index("Save bot state")
    assert check["with"]["key"] == job["steps"][names.index("Save bot state")]["with"]["key"]
    assert check["with"]["lookup-only"] is True and check["with"]["fail-on-cache-miss"] is True
    assert "github.event.repository.default_branch" in job["if"]


@pytest.mark.parametrize("name", ["demo.yaml", "stocks.yaml", "crypto.yaml"])
def test_shipped_configs_pass_the_github_actions_state_dir_check(name, monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    cli._check_ci_state_dir(load_config(ROOT / "configs" / name, env={}))


def test_status_lists_holdings_the_bot_did_not_buy(capsys, tmp_path, monkeypatch):
    cfg = write_config(tmp_path)  # symbols DEMO1, DEMO2 on a (fake) real account
    fake = FakeBroker(positions={"DEMO1": Position("DEMO1", 7.0, 90.0, 100.0),
                                 "DEMO2": Position("DEMO2", 3.0, 90.0, 100.0)})
    monkeypatch.setattr("bot.brokers.make_broker", lambda cfg, env=None: fake)
    store = StateStore(tmp_path / "state" / cli.STATE_FILE)
    store.save(BotState(account_key="paper:sim::USD", owned={"DEMO2": {"qty": 3.0, "avg_entry_price": 90.0}},
                        holdings_checked=True))
    code, out, _ = run(capsys, "-c", str(cfg), "status")
    assert code == 0
    line = next(line for line in out.splitlines() if "Not bought by this bot" in line)
    assert "DEMO1 7" in line and "DEMO2" not in line
    store.save(BotState(account_key="paper:sim::USD", last_tick_at="2026-09-24T14:00:00+00:00"))  # a lost state
    _, out, _ = run(capsys, "-c", str(cfg), "status")  # that has only seen a closed market since
    assert "No record of the bot buying these" in out and "Not bought by this bot" not in out


def test_status_counts_what_the_bot_bought_in_this_account_after_it_ran_on_another(capsys, tmp_path, monkeypatch):
    cfg = write_config(tmp_path)  # paper; the bot last ran with a live config on the same state folder
    fake = FakeBroker(positions={"DEMO1": Position("DEMO1", 7.0, 90.0, 100.0),
                                 "DEMO2": Position("DEMO2", 3.0, 90.0, 100.0)})
    monkeypatch.setattr("bot.brokers.make_broker", lambda cfg, env=None: fake)
    StateStore(tmp_path / "state" / cli.STATE_FILE).save(BotState(account_key="live:sim::USD", other_ledgers={
        "paper:sim::USD": {"owned": {"DEMO2": {"qty": 3.0, "avg_entry_price": 90.0}}}}, holdings_checked=True))
    _, out, _ = run(capsys, "-c", str(cfg), "status")
    line = next(line for line in out.splitlines() if "Not bought by this bot" in line)
    assert "DEMO1 7" in line and "DEMO2" not in line


# ---------------------------------------------------------------- regression: secrets in verbose logs, kill on Actions


def test_verbose_logs_never_show_the_webhook_url_or_the_telegram_token(capsys, tmp_path, monkeypatch):
    # With -v every library logs at DEBUG: urllib3 logs each request line, and
    # a webhook's (or the Telegram API's) path IS the secret.
    monkeypatch.setenv("NOTIFY_WEBHOOK_URL", "https://discord.com/api/webhooks/123/SUPERSECRETTOKEN")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABCSECRETTOKEN")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    real = cli.set_kill_switch

    def kill_while_libraries_log(*args, **kwargs):
        wire = logging.getLogger("urllib3.connectionpool")
        wire.debug('%s "POST %s HTTP/1.1" 204 0', "https://discord.com:443", "/api/webhooks/123/SUPERSECRETTOKEN")
        wire.debug('%s "POST %s HTTP/1.1" 200 0', "https://api.telegram.org:443",
                   "/bot123456:ABCSECRETTOKEN/sendMessage")
        logging.getLogger("some.library").debug("posting to %s",
                                                "https://discord.com/api/webhooks/123/SUPERSECRETTOKEN")
        try:
            raise ConnectionError("POST /bot123456:ABCSECRETTOKEN/sendMessage failed")
        except ConnectionError:
            logging.getLogger("some.library").exception("request failed")
        return real(*args, **kwargs)

    monkeypatch.setattr(cli, "set_kill_switch", kill_while_libraries_log)
    cfg = write_config(tmp_path)
    code, out, err = run(capsys, "-v", "-c", str(cfg), "kill")

    log = (tmp_path / "logs" / "bot.log").read_text(encoding="utf-8")
    assert code == 0
    assert "some.library" in log and "request failed" in log  # debug logs are still written ...
    for text in (out, err, log):
        assert "SECRETTOKEN" not in text  # ... with the secrets masked


def test_kill_and_flatten_say_a_github_actions_deployment_keeps_trading(capsys, tmp_path, monkeypatch):
    # The KILL file is written on this machine; the Actions runner restores its
    # state from the Actions cache and never sees it.
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    cfg = write_config(tmp_path)
    _, out, _ = run(capsys, "-c", str(cfg), "kill", "--reason", "vacation")
    assert "GitHub Actions" in out and "TRADING_BOT_ENABLED" in out
    run(capsys, "-c", str(cfg), "resume")
    _, out, _ = run(capsys, "-c", str(cfg), "flatten", "--yes")
    assert "GitHub Actions" in out and "TRADING_BOT_ENABLED" in out


def test_kill_on_the_actions_runner_itself_does_not_add_the_note(capsys, tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setattr(cli, "_check_ci_state_dir", lambda cfg: None)
    cfg = write_config(tmp_path)
    _, out, _ = run(capsys, "-c", str(cfg), "kill")
    assert "TRADING_BOT_ENABLED" not in out


def test_readme_says_kill_does_not_pause_a_github_actions_deployment():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    section = readme[readme.index("## 7."):readme.index("### Live")]
    assert "TRADING_BOT_ENABLED" in section and "GitHub Actions" in section


# --------------------------------------------------------------------------- regression: review round 2


def test_an_alpaca_backtest_counts_new_york_days_whatever_the_configured_timezone(capsys, tmp_path, monkeypatch):
    # The live bot on Alpaca counts New York days: a Seoul midnight falls mid-session.
    cfg = write_config(tmp_path, symbols=["SPY"], broker={"type": "alpaca"}, timeframe="1d", timezone="Asia/Seoul",
                       strategy={"name": "sma_crossover", "params": {"fast": 5, "slow": 20}})
    captured = capture_backtest_config(monkeypatch)
    code, out, _ = run(capsys, "-c", str(cfg), "backtest", "--synthetic", "--bars", "200", "--out", str(tmp_path / "o"))
    assert code == 0
    assert captured["cfg"].timezone == "America/New_York" and "America/New_York days" in out


def test_the_run_banner_shows_the_trading_day_the_daily_limits_really_use(tmp_path):
    args = argparse.Namespace(config="x.yaml")
    alpaca = write_config(tmp_path, name="a.yaml", symbols=["SPY"], broker={"type": "alpaca"}, timezone="Asia/Seoul")
    (row,) = [line for line in cli._banner(load_config(alpaca, env={}), args).splitlines() if "Trading day" in line]
    assert "America/New_York" in row and "Seoul" not in row
    sim = write_config(tmp_path, name="s.yaml", timezone="Asia/Seoul")
    assert "Asia/Seoul" in cli._banner(load_config(sim, env={}), args)
