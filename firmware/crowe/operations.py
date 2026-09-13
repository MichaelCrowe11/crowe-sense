"""Operations: the writable half of the node, and the only door to it.

A Crowe Sense node is a reader. The two things it can *do* to the world are blink
its own status LEDs and power-cycle its own hotspot, and both were private to the
watchdog until now. This module makes them requestable, on purpose, with the rules
in code rather than in a prompt:

  * a closed registry of semantic operations (no pin numbers, no raw GPIO);
  * validation with hard bounds before anything is queued;
  * a queue in SQLite that the API writes and the watchdog drains, because the
    watchdog is the one process that owns the pins and two owners would fight;
  * cooldowns enforced by the executor at run time, not only at request time;
  * honest states: queued, running, done, rejected, expired, and unknown for a
    request the executor was running when it died.

Authorization is the API's job (crowe/api.py, an operator bearer on the direct
path). This module never sees a token. Reachability is not authorization: a client
on the LAN still has to present the token.

Shape informed by the public description of Anthropic's Model Hardware Standard
(read/write primitives, limits enforced at the driver). Not a claim of conformance;
the specification is not public as of 2026-09.
"""

from __future__ import annotations

import json
import secrets
import sqlite3
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

IDENTIFY_MIN_S = 1.0
IDENTIFY_MAX_S = 30.0
IDENTIFY_DEFAULT_S = 10.0
IDENTIFY_MIN_GAP_S = 5.0
UPLINK_RESET_COOLDOWN_S = 600.0
UPLINK_RESET_HOLD_S = 3.0          # mirrors watchdog.HOTSPOT_RESET_HOLD_S; asserted by a test
QUEUE_TTL_S = 60.0                  # a request nobody claimed within a minute expires

STATUSES = ("queued", "running", "done", "rejected", "expired", "unknown")

# The registry is data. Each entry is what the descriptor publishes and what
# validate() and the executor enforce, so the three cannot drift apart.
REGISTRY: dict[str, dict[str, Any]] = {
    "indicator.identify": {
        "title": "Identify this node",
        "effect": (
            "Blinks the three status LEDs together for a few seconds so a person can find "
            "the node in a rack or a room. Visual only: sampling and uploads continue."
        ),
        "args": {
            "seconds": {"type": "number", "minimum": IDENTIFY_MIN_S, "maximum": IDENTIFY_MAX_S,
                        "default": IDENTIFY_DEFAULT_S, "description": "how long to blink"},
        },
        "constraints": [
            {"kind": "bound", "arg": "seconds", "min": IDENTIFY_MIN_S, "max": IDENTIFY_MAX_S,
             "enforced_by": "operations.validate"},
            {"kind": "min_gap_s", "value": IDENTIFY_MIN_GAP_S, "enforced_by": "operations.Executor"},
        ],
        "repeat_safe": True,
        "interrupts": [],
    },
    "uplink.reset": {
        "title": "Power-cycle the cellular hotspot",
        "effect": (
            "Holds the hotspot power line for 3 s. The node's backhaul drops for up to a few "
            "minutes, and a request that arrived over that backhaul may lose its own reply. "
            "Sampling and local storage continue; nothing is lost on the node."
        ),
        "args": {},
        "constraints": [
            {"kind": "cooldown_s", "value": UPLINK_RESET_COOLDOWN_S, "enforced_by": "operations.Executor"},
            {"kind": "hold_s", "value": UPLINK_RESET_HOLD_S, "enforced_by": "watchdog._Pins.pulse_reset"},
        ],
        "repeat_safe": False,
        "interrupts": ["backhaul"],
    },
}


class OperationError(Exception):
    """A request the node refuses. `code` is the error slug the API answers with."""

    def __init__(self, code: str, detail: str, status: int = 400):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status = status


def public_registry() -> list[dict[str, Any]]:
    """The registry as the descriptor and /v1/operations publish it."""
    return [{"id": op_id, **spec} for op_id, spec in REGISTRY.items()]


def validate(op_id: str, args: dict | None) -> dict[str, Any]:
    """Return the normalised arguments for `op_id`, or raise OperationError.

    Unknown operations and unknown argument names are refused rather than ignored:
    a dropped argument is a request that succeeds while doing something other than
    what was asked.
    """
    spec = REGISTRY.get(str(op_id or ""))
    if spec is None:
        raise OperationError("unknown_operation", f"No such operation. Operations: {', '.join(REGISTRY)}.", 404)
    if args is None:
        args = {}
    if not isinstance(args, dict):
        raise OperationError("bad_args", "args must be an object of argument names to values.")
    allowed = spec["args"]
    out: dict[str, Any] = {}
    for k in args:
        if k not in allowed:
            raise OperationError("bad_args", f"'{k}' is not an argument of {op_id}. Arguments: {', '.join(allowed) or 'none'}.")
    for k, a in allowed.items():
        v = args.get(k, a.get("default"))
        if a["type"] == "number":
            try:
                v = float(v)
            except (TypeError, ValueError):
                raise OperationError("bad_args", f"{k} must be a number.") from None
            if v != v or v in (float("inf"), float("-inf")):
                raise OperationError("bad_args", f"{k} must be a finite number.")
            if v < a["minimum"] or v > a["maximum"]:
                raise OperationError("bad_args", f"{k} must be between {a['minimum']:g} and {a['maximum']:g}, got {v:g}.")
        out[k] = v
    return out


def gap_for(op_id: str) -> float:
    """The minimum spacing between two completed runs of `op_id`, in seconds."""
    for c in REGISTRY[op_id]["constraints"]:
        if c["kind"] in ("min_gap_s", "cooldown_s"):
            return float(c["value"])
    return 0.0


# ── the queue ──────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS operations (
    id            TEXT PRIMARY KEY,
    op            TEXT NOT NULL,
    args          TEXT NOT NULL,
    requested_by  TEXT NOT NULL,
    ts_requested  REAL NOT NULL,
    ts_started    REAL,
    ts_finished   REAL,
    status        TEXT NOT NULL,
    result        TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_operations_status_ts ON operations(status, ts_requested);
"""


def open_queue(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False, timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(SCHEMA)
    return conn


def _row(r: tuple | None) -> dict | None:
    if r is None:
        return None
    id_, op, args, who, ts_r, ts_s, ts_f, status, result = r
    return {"id": id_, "op": op, "args": json.loads(args), "requested_by": who,
            "ts_requested": ts_r, "ts_started": ts_s, "ts_finished": ts_f,
            "status": status, "result": json.loads(result)}


_COLS = "id, op, args, requested_by, ts_requested, ts_started, ts_finished, status, result"


def enqueue(conn: sqlite3.Connection, op_id: str, args: dict, requested_by: str, now: float) -> dict:
    op_args = validate(op_id, args)
    id_ = "op-" + secrets.token_hex(4)
    conn.execute(
        "INSERT INTO operations (id, op, args, requested_by, ts_requested, status) VALUES (?, ?, ?, ?, ?, 'queued')",
        (id_, op_id, json.dumps(op_args, sort_keys=True), requested_by[:64], now),
    )
    return get(conn, id_)


def get(conn: sqlite3.Connection, id_: str) -> dict | None:
    return _row(conn.execute(f"SELECT {_COLS} FROM operations WHERE id = ?", (id_,)).fetchone())


def recent(conn: sqlite3.Connection, n: int = 20) -> list[dict]:
    rows = conn.execute(f"SELECT {_COLS} FROM operations ORDER BY ts_requested DESC LIMIT ?", (n,)).fetchall()
    return [_row(r) for r in rows]


def last_finished(conn: sqlite3.Connection, op_id: str) -> float | None:
    r = conn.execute(
        "SELECT MAX(ts_finished) FROM operations WHERE op = ? AND status = 'done'", (op_id,)
    ).fetchone()
    return float(r[0]) if r and r[0] is not None else None


def cooldown_remaining(conn: sqlite3.Connection, op_id: str, now: float) -> float:
    """Seconds until `op_id` may run again, 0 when it may run now."""
    last = last_finished(conn, op_id)
    if last is None:
        return 0.0
    return max(0.0, gap_for(op_id) - (now - last))


def expire_stale(conn: sqlite3.Connection, now: float) -> int:
    cur = conn.execute(
        "UPDATE operations SET status = 'expired', ts_finished = ?, result = ? "
        "WHERE status = 'queued' AND ts_requested < ?",
        (now, json.dumps({"error": "expired", "detail": f"not claimed within {QUEUE_TTL_S:g} s"}), now - QUEUE_TTL_S),
    )
    return cur.rowcount


def claim(conn: sqlite3.Connection, now: float) -> dict | None:
    """Take the oldest live request and mark it running. One at a time, by design."""
    expire_stale(conn, now)
    r = conn.execute(
        "SELECT id FROM operations WHERE status = 'queued' ORDER BY ts_requested LIMIT 1"
    ).fetchone()
    if r is None:
        return None
    conn.execute("UPDATE operations SET status = 'running', ts_started = ? WHERE id = ? AND status = 'queued'", (now, r[0]))
    return get(conn, r[0])


def finish(conn: sqlite3.Connection, id_: str, status: str, result: dict, now: float) -> None:
    if status not in ("done", "rejected", "unknown"):
        raise ValueError(status)
    conn.execute("UPDATE operations SET status = ?, ts_finished = ?, result = ? WHERE id = ?",
                 (status, now, json.dumps(result, sort_keys=True), id_))


def recover(conn: sqlite3.Connection, now: float) -> int:
    """Anything still 'running' when an executor starts was interrupted. It may or
    may not have happened; the only honest status is unknown."""
    cur = conn.execute(
        "UPDATE operations SET status = 'unknown', ts_finished = ?, result = ? WHERE status = 'running'",
        (now, json.dumps({"error": "unknown", "detail": "the executor restarted while this was running"})),
    )
    return cur.rowcount


# ── the executor (runs inside the watchdog) ────────────────────────────────────

class Executor:
    """Drains the queue from inside the watchdog loop.

    `pins` is the watchdog's _Pins (set(color, on), pulse_reset()). `gpio_available`
    is whether those pins are real. With no GPIO and `simulate` off, every write is
    rejected as unavailable rather than reported as done: a stub that says "done" is
    a lie the next reader acts on. With `simulate` on (a bench, a test) results carry
    `simulated: true` so nobody mistakes them for the world.
    """

    def __init__(self, conn: sqlite3.Connection, pins: Any, *, gpio_available: bool,
                 simulate: bool = False, now: Callable[[], float] = time.time):
        self.conn = conn
        self.pins = pins
        self.gpio_available = bool(gpio_available)
        self.simulate = bool(simulate)
        self._now = now
        self.identify_until = 0.0
        self.last_reset_ts: float | None = None
        recover(conn, now())

    @property
    def identifying(self) -> bool:
        return self._now() < self.identify_until

    def tick(self) -> dict | None:
        """Run at most one queued request. Returns the finished row, or None."""
        now = self._now()
        row = claim(self.conn, now)
        if row is None:
            return None
        return self._run(row, now)

    def _run(self, row: dict, now: float) -> dict:
        op_id, args, id_ = row["op"], row["args"], row["id"]
        # Re-checked here, not only at request time: two requests can be queued
        # within one cooldown, and the second must still wait.
        remaining = cooldown_remaining(self.conn, op_id, now)
        if remaining > 0:
            finish(self.conn, id_, "rejected",
                   {"error": "cooldown", "detail": f"{op_id} ran recently", "retry_after_s": round(remaining, 1)}, now)
            return get(self.conn, id_)
        if not self.gpio_available and not self.simulate:
            finish(self.conn, id_, "rejected",
                   {"error": "unavailable", "detail": "this host has no GPIO; nothing was changed"}, now)
            return get(self.conn, id_)
        simulated = not self.gpio_available
        if op_id == "indicator.identify":
            self.identify_until = now + float(args["seconds"])
            finish(self.conn, id_, "done", {"simulated": simulated, "blinking_until": self.identify_until}, now)
        elif op_id == "uplink.reset":
            if not simulated:
                self.pins.pulse_reset()
            self.last_reset_ts = self._now()
            finish(self.conn, id_, "done", {"simulated": simulated, "held_s": UPLINK_RESET_HOLD_S}, self._now())
        else:  # registry and executor disagree: refuse loudly rather than guess
            finish(self.conn, id_, "rejected", {"error": "unimplemented", "detail": f"no executor for {op_id}"}, now)
        return get(self.conn, id_)


# ── operator token ─────────────────────────────────────────────────────────────

def read_token(path: Path) -> str | None:
    try:
        t = path.read_text().strip()
    except OSError:
        return None
    return t or None


def token_matches(presented: str | None, path: Path) -> bool:
    import hmac
    expected = read_token(path)
    if not expected or not presented:
        return False
    return hmac.compare_digest(presented.strip(), expected)


def make_token() -> str:
    return "cso-" + secrets.token_urlsafe(24)
