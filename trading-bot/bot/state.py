"""Persistent bot state (daily counters, last evaluated bars) and the kill switch.

State lives in one small JSON file written atomically, so a crash mid-write can
never leave a half-written file behind. The kill switch is just a file named
``KILL`` in the state directory: while it exists the engine does nothing.
"""
from __future__ import annotations

import json
import logging
import math
import numbers
import os
import tempfile
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

KILL_FILE = "KILL"
# The bot's state file inside ``state_dir`` (shared by the CLI, deploy scripts and docs).
STATE_FILE = "bot_state.json"


@dataclass
class BotState:
    day: str | None = None                 # ISO date (YYYY-MM-DD) in the bot's timezone
    day_start_equity: float | None = None
    trades_today: int = 0                  # new entries placed today
    halted_today: bool = False             # daily loss limit hit today
    last_signal_bar: dict[str, str] = field(default_factory=dict)  # symbol -> ISO ts of last bar evaluated
    consecutive_errors: int = 0
    last_tick_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> BotState:
        """Build a state from saved JSON. Unknown keys are ignored (forward
        compatibility), missing keys take defaults, wrong types raise ValueError."""
        if not isinstance(data, Mapping):
            raise ValueError(f"state must be a JSON object, got {type(data).__name__}")
        known = {f.name for f in fields(cls)}
        values = {k: v for k, v in data.items() if k in known}
        state = cls(**values)
        _check_types(state)
        if state.day_start_equity is not None:
            state.day_start_equity = float(state.day_start_equity)
        state.last_signal_bar = dict(state.last_signal_bar)
        return state


def _check_types(state: BotState) -> None:
    def fail(name: str, value: Any) -> None:
        raise ValueError(f"state field {name!r} has invalid value {value!r}")

    for name in ("day", "last_tick_at"):
        value = getattr(state, name)
        if value is not None and not isinstance(value, str):
            fail(name, value)
    equity = state.day_start_equity
    if equity is not None and (
        not isinstance(equity, numbers.Real) or isinstance(equity, bool) or not math.isfinite(equity)
    ):
        fail("day_start_equity", equity)
    for name in ("trades_today", "consecutive_errors"):
        value = getattr(state, name)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            fail(name, value)
    if not isinstance(state.halted_today, bool):
        fail("halted_today", state.halted_today)
    bars = state.last_signal_bar
    if not isinstance(bars, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in bars.items()):
        fail("last_signal_bar", bars)


class StateStore:
    """Loads and atomically saves a :class:`BotState` as JSON at ``path``."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def load(self) -> BotState:
        """Missing file -> fresh state. Unreadable/corrupt content -> the file
        is moved aside to ``<name>.corrupt-<n>``, a warning is logged and a
        fresh state is returned. Other I/O errors (e.g. permissions) raise."""
        try:
            raw = self.path.read_bytes()
        except FileNotFoundError:
            return BotState()
        try:
            return BotState.from_dict(json.loads(raw.decode("utf-8")))
        except (ValueError, TypeError) as exc:  # incl. JSONDecodeError, UnicodeDecodeError
            backup = self._quarantine()
            logger.warning("State file %s is corrupt (%s); moved to %s and starting fresh",
                           self.path, exc, backup or "<could not move>")
            return BotState()

    def save(self, state: BotState) -> None:
        """Write atomically: temp file in the same directory, fsync, os.replace.
        Parent directories are created. NaN/inf values raise ValueError rather
        than being persisted as invalid JSON."""
        payload = json.dumps(state.to_dict(), indent=2, sort_keys=True, allow_nan=False)
        _atomic_write_text(self.path, payload + "\n")

    def _quarantine(self) -> Path | None:
        n = 1
        while (backup := self.path.with_name(f"{self.path.name}.corrupt-{n}")).exists():
            n += 1
        try:
            os.replace(self.path, backup)
        except OSError as exc:
            logger.error("Could not move corrupt state file %s aside: %s", self.path, exc)
            return None
        return backup


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    _fsync_dir(path.parent)


def _fsync_dir(directory: Path) -> None:
    """Persist the rename itself across power loss (best effort; POSIX only)."""
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def kill_switch_active(state_dir: Path) -> bool:
    """True while ``state_dir/KILL`` exists (the engine then places no orders)."""
    return (Path(state_dir) / KILL_FILE).exists()


def set_kill_switch(state_dir: Path, on: bool, reason: str = "") -> None:
    """Create (``on=True``, with ``reason`` written inside) or remove the kill file."""
    kill_path = Path(state_dir) / KILL_FILE
    if on:
        kill_path.parent.mkdir(parents=True, exist_ok=True)
        kill_path.write_text(reason, encoding="utf-8")
        logger.warning("Kill switch ON (%s)%s", kill_path, f": {reason}" if reason else "")
    else:
        kill_path.unlink(missing_ok=True)
        logger.info("Kill switch OFF (%s)", kill_path)


def kill_switch_reason(state_dir: Path) -> str | None:
    """Text written into the kill file, or None when the switch is off."""
    try:
        return (Path(state_dir) / KILL_FILE).read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError):
        return ""  # present but unreadable (e.g. a directory named KILL): still active


__all__ = [
    "KILL_FILE",
    "STATE_FILE",
    "BotState",
    "StateStore",
    "kill_switch_active",
    "kill_switch_reason",
    "set_kill_switch",
]
