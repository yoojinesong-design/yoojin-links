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
# The fields that record what the bot bought in one account (see BotState.other_ledgers).
ACCOUNT_LEDGER = ("owned", "unsettled", "pending_orders", "seen_holdings", "recent_order_ids")
# How many of the bot's latest client order ids the state keeps (recent_order_ids).
MAX_RECENT_ORDER_IDS = 100


class CorruptStateError(ValueError):
    """The state file exists but its content cannot be used. It is left in place."""


@dataclass
class BotState:
    day: str | None = None                 # ISO date (YYYY-MM-DD) in the bot's timezone
    day_start_equity: float | None = None
    trades_today: int = 0                  # new entries placed today
    halted_today: bool = False             # daily loss limit hit today
    last_signal_bar: dict[str, str] = field(default_factory=dict)  # symbol -> ISO ts of last bar evaluated
    consecutive_errors: int = 0
    last_tick_at: str | None = None
    # Which account the daily fields belong to (mode, broker, currency). When it
    # changes (e.g. a paper -> live switch on the same state_dir) the daily
    # counters and loss baseline start over, and the record of what the bot
    # bought (ACCOUNT_LEDGER) is swapped for that account's (other_ledgers).
    account_key: str | None = None
    # What the bot itself bought in this account, from its own orders:
    # symbol -> {"qty", "avg_entry_price"}. Only this much of a holding is
    # managed (stop-loss, exits, flatten) and ever sold by the bot.
    owned: dict[str, dict[str, float]] = field(default_factory=dict)
    # Symbols with an order from the bot the broker had not reported filled
    # yet (or whose reply was lost): ``owned`` is not trimmed to the broker's
    # holding until no order of the bot's is working on them.
    unsettled: list[str] = field(default_factory=list)
    # Orders of the bot's not reported filled yet (accepted, or sent and the
    # reply lost), by client order id: {"symbol", "side" ("buy"/"sell"),
    # "qty", "booked": how much of it ``owned`` already counts (a BUY in full,
    # as if it fills; a SELL only as far as it filled), "held": the account's
    # holding when it was sent, "order_id": the broker's id, if known}. When
    # the symbol settles, ``owned`` is corrected to what the broker says
    # filled (else to how the holding changed): a sell that expired, was
    # cancelled or filled in part leaves the rest the bot's, and shares the
    # user holds alongside are never counted as the bot's.
    pending_orders: dict[str, dict[str, Any]] = field(default_factory=dict)
    # The broker's own [qty, avg_entry_price] of each holding the bot owns (a
    # part of), as last seen. A later change of quantity at an unchanged cost
    # (qty x average price) is a stock split: ``owned`` is rescaled with it.
    seen_holdings: dict[str, list[float]] = field(default_factory=dict)
    # The client order ids of the bot's latest orders in this account (oldest
    # first, at most MAX_RECENT_ORDER_IDS), booked before each order goes out.
    # A newer order of the bot's at the broker means this state is older than
    # the account (e.g. a GitHub Actions cache save that failed): not traded on.
    recent_order_ids: list[str] = field(default_factory=list)
    # Holdings the bot does not manage that it already sent a notice about.
    notified_unmanaged: list[str] = field(default_factory=list)
    # Symbols it already warned have too little history to ever trade (kept
    # here so that separate `once` runs do not repeat the notice).
    warned_short_history: list[str] = field(default_factory=list)
    # True once a tick with this state has looked at the account's holdings
    # (not only at a closed market): until then a holding it has no record of
    # is reported as "no record" (a first run, or a lost state), not as "not
    # bought by the bot".
    holdings_checked: bool = False
    # Money that moved in or out of the account today without the bot trading
    # (a deposit, a withdrawal, a trade in an asset the bot does not value),
    # added to day_start_equity so the daily loss limit only sees trading.
    external_flow: float = 0.0
    # Cash and holdings ({symbol: [qty, price]}) at the end of the last tick
    # today: the reference those flows are measured against (None: none yet).
    flow_cash: float | None = None
    flow_holdings: dict[str, list[float]] = field(default_factory=dict)
    # What the bot bought in the other accounts this state was used with, by
    # account_key: {field: value} for the ACCOUNT_LEDGER fields. Switching
    # back (e.g. live -> paper -> live) restores that account's record, so
    # the positions the bot bought there keep their stop-loss.
    other_ledgers: dict[str, dict[str, Any]] = field(default_factory=dict)

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
        if "holdings_checked" not in data:  # a state saved before this field existed
            values["holdings_checked"] = data.get("last_tick_at") is not None
        state = cls(**values)
        _check_types(state)
        if state.day_start_equity is not None:
            state.day_start_equity = float(state.day_start_equity)
        if state.flow_cash is not None:
            state.flow_cash = float(state.flow_cash)
        state.external_flow = float(state.external_flow)
        state.last_signal_bar = dict(state.last_signal_bar)
        state.owned = {s: {"qty": float(e["qty"]), "avg_entry_price": float(e["avg_entry_price"])}
                       for s, e in state.owned.items()}
        state.unsettled = list(state.unsettled)
        state.recent_order_ids = list(state.recent_order_ids)
        state.pending_orders = {cid: {"symbol": e["symbol"], "side": e["side"], "qty": float(e["qty"]),
                                      "booked": float(e["booked"]), "held": float(e["held"]),
                                      "order_id": e["order_id"]}
                                for cid, e in state.pending_orders.items()}
        state.seen_holdings = {s: [float(v) for v in pair] for s, pair in state.seen_holdings.items()}
        state.notified_unmanaged = list(state.notified_unmanaged)
        state.warned_short_history = list(state.warned_short_history)
        state.flow_holdings = {s: [float(v) for v in pair] for s, pair in state.flow_holdings.items()}
        state.other_ledgers = {key: _ledger(value) for key, value in state.other_ledgers.items()}
        return state


def _ledger(data: Mapping[str, Any]) -> dict[str, Any]:
    """One account's record (the ACCOUNT_LEDGER fields), checked like the state's own."""
    part = BotState.from_dict({name: data[name] for name in ACCOUNT_LEDGER if name in data})
    return {name: getattr(part, name) for name in ACCOUNT_LEDGER}


def _check_types(state: BotState) -> None:
    def fail(name: str, value: Any) -> None:
        raise ValueError(f"state field {name!r} has invalid value {value!r}")

    for name in ("day", "last_tick_at", "account_key"):
        value = getattr(state, name)
        if value is not None and not isinstance(value, str):
            fail(name, value)
    for name in ("day_start_equity", "flow_cash", "external_flow"):
        value = getattr(state, name)
        if value is not None and not _finite(value):
            fail(name, value)
    for name in ("trades_today", "consecutive_errors"):
        value = getattr(state, name)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            fail(name, value)
    for name in ("halted_today", "holdings_checked"):
        if not isinstance(getattr(state, name), bool):
            fail(name, getattr(state, name))
    bars = state.last_signal_bar
    if not isinstance(bars, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in bars.items()):
        fail("last_signal_bar", bars)
    owned = state.owned
    if not isinstance(owned, dict) or not all(
            isinstance(k, str) and isinstance(v, dict) and set(v) == {"qty", "avg_entry_price"}
            and all(_finite(x) and x > 0 for x in v.values()) for k, v in owned.items()):
        fail("owned", owned)
    for name in ("unsettled", "recent_order_ids", "notified_unmanaged", "warned_short_history"):
        value = getattr(state, name)
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            fail(name, value)
    orders = state.pending_orders
    if not isinstance(orders, dict) or not all(
            isinstance(k, str) and isinstance(v, dict) and set(v) == _PENDING_KEYS
            and isinstance(v["symbol"], str) and v["side"] in ("buy", "sell") and isinstance(v["order_id"], str)
            and all(_finite(v[x]) and v[x] >= 0 for x in ("qty", "booked", "held")) for k, v in orders.items()):
        fail("pending_orders", orders)
    seen = state.seen_holdings
    if not isinstance(seen, dict) or not all(
            isinstance(k, str) and isinstance(v, list) and len(v) == 2 and all(_finite(x) and x > 0 for x in v)
            for k, v in seen.items()):
        fail("seen_holdings", seen)
    held = state.flow_holdings
    if not isinstance(held, dict) or not all(
            isinstance(k, str) and isinstance(v, list) and len(v) == 2 and all(_finite(x) for x in v)
            for k, v in held.items()):
        fail("flow_holdings", held)
    ledgers = state.other_ledgers
    if not isinstance(ledgers, dict) or not all(
            isinstance(k, str) and isinstance(v, dict) and set(v) <= set(ACCOUNT_LEDGER) for k, v in ledgers.items()):
        fail("other_ledgers", ledgers)


_PENDING_KEYS = {"symbol", "side", "qty", "booked", "held", "order_id"}


def _finite(value: Any) -> bool:
    return isinstance(value, numbers.Real) and not isinstance(value, bool) and math.isfinite(value)


class StateStore:
    """Loads and atomically saves a :class:`BotState` as JSON at ``path``."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def load(self) -> BotState:
        """Missing file -> fresh state. Content that cannot be used raises
        :class:`CorruptStateError` and the file is left in place (a fresh state
        would forget what the bot bought: its positions would lose their
        stop-loss). Other I/O errors (e.g. permissions) raise as they are."""
        try:
            raw = self.path.read_bytes()
        except FileNotFoundError:
            return BotState()
        try:
            return BotState.from_dict(json.loads(raw.decode("utf-8")))
        except (ValueError, TypeError) as exc:  # incl. JSONDecodeError, UnicodeDecodeError
            raise CorruptStateError(
                f"state file {self.path} is corrupt ({exc}); fix it, or delete it to start over (the bot then "
                "forgets what it bought, so those positions get no stop-loss)") from exc

    def save(self, state: BotState) -> None:
        """Write atomically: temp file in the same directory, fsync, os.replace.
        Parent directories are created. NaN/inf values raise ValueError rather
        than being persisted as invalid JSON."""
        payload = json.dumps(state.to_dict(), indent=2, sort_keys=True, allow_nan=False)
        _atomic_write_text(self.path, payload + "\n")


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        give_default_permissions(fd)
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


def give_default_permissions(fd: int) -> None:
    """Give a ``mkstemp`` file (always 0600) the mode a normally created file
    gets (0666 minus the umask, e.g. 0644), so a file rewritten by another
    user (say, one ``sudo`` run) stays readable by the bot's own user. Best
    effort: a no-op where ``os.fchmod`` does not exist (Windows)."""
    fchmod = getattr(os, "fchmod", None)
    if fchmod is None:
        return
    umask = os.umask(0)
    os.umask(umask)
    try:
        fchmod(fd, 0o666 & ~umask)
    except OSError:
        pass


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


def loss_baseline(state: BotState) -> float | None:
    """The daily loss limit's reference: the day's starting equity plus money
    moved in (or minus money moved out) today without the bot trading. None
    when there is no usable baseline."""
    start = state.day_start_equity
    if start is None or not _finite(start) or start <= 0:
        return None
    baseline = start + state.external_flow
    return baseline if _finite(baseline) and baseline > 0 else None


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
    "ACCOUNT_LEDGER",
    "KILL_FILE",
    "MAX_RECENT_ORDER_IDS",
    "STATE_FILE",
    "BotState",
    "CorruptStateError",
    "StateStore",
    "give_default_permissions",
    "kill_switch_active",
    "kill_switch_reason",
    "loss_baseline",
    "set_kill_switch",
]
