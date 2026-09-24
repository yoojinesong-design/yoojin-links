"""Tests for bot.state: atomic JSON persistence and the kill switch."""
from __future__ import annotations

import json
import logging
import math
import os
from pathlib import Path

import pytest

from bot import state as state_mod
from bot.state import (
    KILL_FILE,
    BotState,
    StateStore,
    kill_switch_active,
    kill_switch_reason,
    set_kill_switch,
)


def full_state() -> BotState:
    return BotState(
        day="2026-09-24",
        day_start_equity=10_234.56,
        trades_today=3,
        halted_today=True,
        last_signal_bar={"AAPL": "2026-09-23T00:00:00+00:00", "BTC/USDT": "2026-09-24T13:00:00+00:00"},
        consecutive_errors=2,
        last_tick_at="2026-09-24T14:05:00+00:00",
    )


def leftovers(directory: Path) -> list[str]:
    return sorted(p.name for p in directory.iterdir() if p.name.endswith(".tmp"))


# --------------------------------------------------------------------------- BotState


def test_fresh_state_defaults():
    s = BotState()
    assert s.day is None and s.day_start_equity is None and s.last_tick_at is None
    assert s.trades_today == 0 and s.consecutive_errors == 0 and s.halted_today is False
    assert s.last_signal_bar == {}


def test_default_dicts_are_not_shared_between_instances():
    a, b = BotState(), BotState()
    a.last_signal_bar["X"] = "t"
    assert b.last_signal_bar == {}


# --------------------------------------------------------------------------- load / save


def test_load_missing_file_returns_fresh_state(tmp_path):
    assert StateStore(tmp_path / "nope" / "state.json").load() == BotState()


def test_save_load_round_trip(tmp_path):
    store = StateStore(tmp_path / "state.json")
    original = full_state()
    store.save(original)
    loaded = store.load()
    assert loaded == original
    assert loaded is not original
    assert isinstance(loaded.day_start_equity, float)


def test_round_trip_through_a_new_store_instance(tmp_path):
    StateStore(tmp_path / "state.json").save(full_state())
    assert StateStore(tmp_path / "state.json").load() == full_state()


def test_default_state_round_trips(tmp_path):
    store = StateStore(tmp_path / "state.json")
    store.save(BotState())
    assert store.load() == BotState()


def test_integer_equity_loads_as_float(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"day_start_equity": 5000}))
    loaded = StateStore(path).load()
    assert loaded.day_start_equity == 5000.0 and isinstance(loaded.day_start_equity, float)


def test_save_creates_parent_directories(tmp_path):
    path = tmp_path / "a" / "b" / "state.json"
    StateStore(path).save(full_state())
    assert path.is_file()


def test_save_accepts_str_path(tmp_path):
    store = StateStore(str(tmp_path / "state.json"))  # type: ignore[arg-type]
    store.save(full_state())
    assert store.load() == full_state()


def test_saved_file_is_plain_json(tmp_path):
    path = tmp_path / "state.json"
    StateStore(path).save(full_state())
    data = json.loads(path.read_text())
    assert data["trades_today"] == 3
    assert data["last_signal_bar"]["BTC/USDT"] == "2026-09-24T13:00:00+00:00"


def test_save_overwrites_previous_state_and_leaves_no_temp_files(tmp_path):
    path = tmp_path / "state.json"
    store = StateStore(path)
    store.save(full_state())
    store.save(BotState(trades_today=7))
    assert store.load() == BotState(trades_today=7)
    assert leftovers(tmp_path) == []
    assert [p.name for p in tmp_path.iterdir()] == ["state.json"]


def test_save_is_atomic_when_replace_fails(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    store = StateStore(path)
    store.save(full_state())
    before = path.read_bytes()

    def boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(state_mod.os, "replace", boom)
    with pytest.raises(OSError, match="disk full"):
        store.save(BotState(trades_today=99))
    assert path.read_bytes() == before  # old state untouched
    assert leftovers(tmp_path) == []     # temp file cleaned up


def test_save_writes_temp_file_in_same_directory_then_replaces(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    calls: list[tuple[Path, Path]] = []
    real_replace = os.replace

    def spy(src, dst):
        calls.append((Path(src), Path(dst)))
        assert Path(src).read_text().startswith("{")  # fully written before the swap
        real_replace(src, dst)

    monkeypatch.setattr(state_mod.os, "replace", spy)
    StateStore(path).save(full_state())
    assert len(calls) == 1
    src, dst = calls[0]
    assert src.parent == tmp_path and dst == path and src != path


def test_save_rejects_nan_instead_of_writing_invalid_json(tmp_path):
    path = tmp_path / "state.json"
    store = StateStore(path)
    store.save(full_state())
    with pytest.raises(ValueError):
        store.save(BotState(day_start_equity=math.nan))
    assert store.load() == full_state()
    assert leftovers(tmp_path) == []


def test_unknown_keys_are_ignored(tmp_path):
    path = tmp_path / "state.json"
    data = {**full_state().to_dict(), "future_field": {"x": 1}, "schema_version": 9}
    path.write_text(json.dumps(data))
    assert StateStore(path).load() == full_state()
    assert path.exists()  # not treated as corrupt


def test_missing_keys_take_defaults(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"day": "2026-01-02", "trades_today": 4}))
    assert StateStore(path).load() == BotState(day="2026-01-02", trades_today=4)


# --------------------------------------------------------------------------- corrupt files


@pytest.mark.parametrize(
    "content",
    [
        "{not json",
        "",
        "[1, 2, 3]",
        "null",
        '"just a string"',
        '{"trades_today": "three"}',
        '{"trades_today": -1}',
        '{"trades_today": 1.5}',
        '{"halted_today": "yes"}',
        '{"day_start_equity": "10000"}',
        '{"day_start_equity": NaN}',
        '{"day_start_equity": Infinity}',
        '{"last_signal_bar": ["AAPL"]}',
        '{"last_signal_bar": {"AAPL": 123}}',
        '{"day": 20260924}',
        '{"consecutive_errors": true}',
    ],
)
def test_corrupt_file_is_moved_aside_and_fresh_state_returned(tmp_path, caplog, content):
    path = tmp_path / "state.json"
    path.write_text(content)
    with caplog.at_level(logging.WARNING, logger="bot.state"):
        loaded = StateStore(path).load()
    assert loaded == BotState()
    assert not path.exists()
    backup = tmp_path / "state.json.corrupt-1"
    assert backup.read_text() == content  # original bytes kept for inspection
    assert any("corrupt" in r.getMessage() for r in caplog.records)


def test_non_utf8_file_is_treated_as_corrupt(tmp_path):
    path = tmp_path / "state.json"
    path.write_bytes(b"\xff\xfe\x00garbage")
    assert StateStore(path).load() == BotState()
    assert (tmp_path / "state.json.corrupt-1").read_bytes() == b"\xff\xfe\x00garbage"


def test_corrupt_backups_are_numbered_and_never_overwritten(tmp_path):
    path = tmp_path / "state.json"
    store = StateStore(path)
    for n, content in enumerate(["bad one", "bad two", "bad three"], start=1):
        path.write_text(content)
        assert store.load() == BotState()
        assert (tmp_path / f"state.json.corrupt-{n}").read_text() == content
    assert (tmp_path / "state.json.corrupt-1").read_text() == "bad one"


def test_store_recovers_after_corruption(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{{{")
    store = StateStore(path)
    assert store.load() == BotState()
    store.save(full_state())
    assert store.load() == full_state()


def test_unreadable_path_is_not_silently_reset(tmp_path):
    path = tmp_path / "state.json"
    path.mkdir()  # a directory where the file should be: an I/O problem, not corruption
    with pytest.raises(OSError):
        StateStore(path).load()
    assert path.is_dir()


# --------------------------------------------------------------------------- kill switch


def test_kill_switch_off_by_default(tmp_path):
    assert kill_switch_active(tmp_path) is False
    assert kill_switch_active(tmp_path / "does-not-exist") is False
    assert kill_switch_reason(tmp_path) is None


def test_kill_switch_on_writes_reason_and_off_removes(tmp_path):
    set_kill_switch(tmp_path, True, reason="manual stop: weird fills")
    kill = tmp_path / KILL_FILE
    assert kill_switch_active(tmp_path) is True
    assert kill.read_text() == "manual stop: weird fills"
    assert kill_switch_reason(tmp_path) == "manual stop: weird fills"

    set_kill_switch(tmp_path, False)
    assert not kill.exists()
    assert kill_switch_active(tmp_path) is False


def test_kill_switch_on_without_reason(tmp_path):
    set_kill_switch(tmp_path, True)
    assert kill_switch_active(tmp_path) is True
    assert kill_switch_reason(tmp_path) == ""


def test_kill_switch_creates_missing_state_dir(tmp_path):
    state_dir = tmp_path / "state" / "nested"
    set_kill_switch(state_dir, True, "x")
    assert kill_switch_active(state_dir)


def test_kill_switch_off_when_already_off_is_a_noop(tmp_path):
    set_kill_switch(tmp_path, False)
    set_kill_switch(tmp_path / "missing-dir", False)
    assert not kill_switch_active(tmp_path)


def test_kill_switch_on_twice_updates_reason(tmp_path):
    set_kill_switch(tmp_path, True, "first")
    set_kill_switch(tmp_path, True, "second")
    assert kill_switch_reason(tmp_path) == "second"


def test_kill_switch_accepts_str_paths(tmp_path):
    set_kill_switch(str(tmp_path), True, "r")  # type: ignore[arg-type]
    assert kill_switch_active(str(tmp_path))  # type: ignore[arg-type]


def test_manually_created_kill_file_is_honoured(tmp_path):
    (tmp_path / "KILL").touch()
    assert kill_switch_active(tmp_path)
    assert KILL_FILE == "KILL"


def test_kill_switch_is_independent_of_state_file(tmp_path):
    store = StateStore(tmp_path / "state.json")
    store.save(full_state())
    set_kill_switch(tmp_path, True, "halt")
    assert store.load() == full_state()
    set_kill_switch(tmp_path, False)
    assert (tmp_path / "state.json").exists()
