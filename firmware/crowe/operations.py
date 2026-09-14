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


# ── actuators: operations that exist only when node.toml declares the hardware ──
#
# The v1 node ships with no actuators. This is the design for the first one, the
# exhaust fan (fresh-air exchange), so that its bounds, its interlocks and its
# fail-safe are in code with tests before a relay board is wired to anything. A
# node whose node.toml has no [actuators] table never lists it.

EXHAUST_FAN_MIN_ON_S = 30.0
EXHAUST_FAN_MAX_ON_CEILING_S = 1800.0      # the kind's own ceiling; an operator may set lower, never higher
FAN_ON_KIND = "exhaust_fan"

_ACTUATORS: dict[str, Any] = {}


def configure_actuators(actuators: dict[str, Any] | None) -> None:
    """Called with cfg.actuators by whoever builds a registry view: the API service,
    the descriptor builder, the watchdog's executor. Idempotent."""
    global _ACTUATORS
    _ACTUATORS = dict(actuators or {})


def actuator_operations() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for name, a in _ACTUATORS.items():
        if a.kind != FAN_ON_KIND:
            continue
        max_on = min(float(a.max_on_s), EXHAUST_FAN_MAX_ON_CEILING_S)
        constraints = [
            {"kind": "enum", "arg": "state", "values": ["on", "off"], "enforced_by": "operations.validate"},
            {"kind": "bound", "arg": "seconds", "min": EXHAUST_FAN_MIN_ON_S, "max": max_on, "enforced_by": "operations.validate"},
            {"kind": "max_on_s", "value": max_on, "enforced_by": "operations.Executor (auto-off checked every tick)"},
            {"kind": "min_off_s", "value": float(a.min_off_s), "enforced_by": "operations.Executor"},
            {"kind": "interlock", "name": "fresh_reading", "value": float(a.max_reading_age_s),
             "detail": f"on requires a co2_ppm reading younger than {a.max_reading_age_s:g} s; no reading, no run",
             "enforced_by": "operations.Executor"},
            {"kind": "fail_safe", "detail": "off at executor start and stop; wire through a normally-open relay so loss of power is off",
             "enforced_by": "watchdog._Pins, wiring"},
        ]
        if a.min_co2_ppm > 0:
            constraints.insert(5, {"kind": "interlock", "name": "co2_floor", "value": float(a.min_co2_ppm),
                                   "detail": f"on refused while co2_ppm is at or below {a.min_co2_ppm:g}",
                                   "enforced_by": "operations.Executor"})
        out[f"ventilation.{name}"] = {
            "title": f"Run the {name.replace('_', ' ')}",
            "effect": (f"Switches the {name.replace('_', ' ')} relay on for a bounded time, then off by itself. "
                       "Fresh-air exchange for the room. 'off' is immediate and never refused. "
                       "The result reports the commanded relay state, not airflow."),
            "args": {
                "state": {"type": "string", "enum": ["on", "off"], "description": "on or off"},
                "seconds": {"type": "number", "minimum": EXHAUST_FAN_MIN_ON_S, "maximum": max_on,
                            "default": min(300.0, max_on), "description": "how long to run before auto-off (state on)"},
            },
            "constraints": constraints,
            "repeat_safe": True,
            "interrupts": [],
            "actuator": {"name": name, "kind": a.kind, "pin": int(a.pin)},
        }
    return out


def active_registry() -> dict[str, dict[str, Any]]:
    return {**REGISTRY, **actuator_operations()}


class OperationError(Exception):
    """A request the node refuses. `code` is the error slug the API answers with."""

    def __init__(self, code: str, detail: str, status: int = 400):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status = status


def public_registry() -> list[dict[str, Any]]:
    """The registry as the descriptor and /v1/operations publish it."""
    return [{"id": op_id, **spec} for op_id, spec in active_registry().items()]


def validate(op_id: str, args: dict | None) -> dict[str, Any]:
    """Return the normalised arguments for `op_id`, or raise OperationError.

    Unknown operations and unknown argument names are refused rather than ignored:
    a dropped argument is a request that succeeds while doing something other than
    what was asked.
    """
    reg = active_registry()
    spec = reg.get(str(op_id or ""))
    if spec is None:
        raise OperationError("unknown_operation", f"No such operation. Operations: {', '.join(reg)}.", 404)
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
        if a["type"] == "string":
            if v is None:
                raise OperationError("bad_args", f"{k} is required ({', '.join(a['enum'])}).")
            v = str(v).strip().lower()
            if v not in a["enum"]:
                raise OperationError("bad_args", f"{k} must be one of {', '.join(a['enum'])}, got {v!r}.")
            out[k] = v
            continue
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
    """The minimum spacing between two completed runs of `op_id`, in seconds, as the
    queue can judge it. Actuator spacing (min_off_s) counts from when the relay
    actually went off, which only the executor knows, so it is 0 here."""
    for c in active_registry()[op_id]["constraints"]:
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
                 simulate: bool = False, now: Callable[[], float] = time.time,
                 actuators: dict[str, Any] | None = None,
                 reading: Callable[[str], tuple[float, float] | None] | None = None):
        self.conn = conn
        self.pins = pins
        self.gpio_available = bool(gpio_available)
        self.simulate = bool(simulate)
        self._now = now
        self.identify_until = 0.0
        self.last_reset_ts: float | None = None
        # Actuators: name -> ActuatorConfig; `reading(metric)` -> (value, age_s) or None,
        # the interlock's only window onto the room. None means "cannot be judged",
        # and an interlock that cannot be judged refuses.
        self.actuators = dict(actuators or {})
        configure_actuators(self.actuators)
        self.reading = reading
        self.actuator_until: dict[str, float] = {}
        self.actuator_off_ts: dict[str, float] = {}
        self.actuator_state: dict[str, bool] = {}
        recover(conn, now())
        # Safe startup: whatever the pins were doing before this process existed,
        # every actuator is off now, and the record says so.
        for name in self.actuators:
            self._set_actuator(name, False, now())

    @property
    def identifying(self) -> bool:
        return self._now() < self.identify_until

    def tick(self) -> dict | None:
        """Auto-off any actuator whose time is up, then run at most one queued
        request. Returns the finished row, or None."""
        now = self._now()
        for name, until in list(self.actuator_until.items()):
            if now >= until:
                self._set_actuator(name, False, now)
        row = claim(self.conn, now)
        if row is None:
            return None
        return self._run(row, now)

    def stop(self) -> None:
        """Called when the watchdog exits: every actuator off, whatever was queued."""
        now = self._now()
        for name in self.actuators:
            self._set_actuator(name, False, now)

    def _set_actuator(self, name: str, on: bool, now: float) -> None:
        if self.gpio_available:
            self.pins.set_actuator(name, on)
        was_on = self.actuator_state.get(name)   # None before the first set
        self.actuator_state[name] = on
        if on:
            return
        self.actuator_until.pop(name, None)
        # The spacing counts from every real off and from the off at start: after a
        # restart the executor cannot know what the relay was doing a moment ago, so
        # it behaves as if the fan had just stopped. An off while already off does
        # not restart the clock.
        if was_on is None or was_on:
            self.actuator_off_ts[name] = now

    def _run_actuator(self, row: dict, spec: dict, now: float) -> dict:
        name = spec["actuator"]["name"]
        a = self.actuators[name]
        args, id_ = row["args"], row["id"]
        simulated = not self.gpio_available
        if args["state"] == "off":
            self._set_actuator(name, False, now)
            finish(self.conn, id_, "done", {"simulated": simulated, "state": "off"}, now)
            return get(self.conn, id_)
        # state on: spacing, then the interlocks, then the relay.
        off_ts = self.actuator_off_ts.get(name)
        if off_ts is not None and not self.actuator_state.get(name) and now - off_ts < a.min_off_s:
            finish(self.conn, id_, "rejected", {"error": "cooldown", "detail": f"{name} went off recently",
                                                "retry_after_s": round(a.min_off_s - (now - off_ts), 1)}, now)
            return get(self.conn, id_)
        if self.reading is None:
            finish(self.conn, id_, "rejected", {"error": "interlock_unverifiable",
                                                "detail": "this executor has no window onto the room's readings; refusing to run blind"}, now)
            return get(self.conn, id_)
        r = self.reading("co2_ppm")
        if r is None or r[1] > a.max_reading_age_s:
            finish(self.conn, id_, "rejected", {"error": "stale_reading", "interlock": "fresh_reading",
                                                "detail": "no co2_ppm reading" if r is None else f"newest co2_ppm reading is {r[1]:.0f} s old"}, now)
            return get(self.conn, id_)
        value = float(r[0])
        if a.min_co2_ppm > 0 and value <= a.min_co2_ppm:
            finish(self.conn, id_, "rejected", {"error": "interlock", "interlock": "co2_floor",
                                                "detail": f"co2_ppm is {value:.0f}, at or below the floor of {a.min_co2_ppm:g}"}, now)
            return get(self.conn, id_)
        seconds = float(args["seconds"])
        self._set_actuator(name, True, now)
        self.actuator_until[name] = now + seconds
        finish(self.conn, id_, "done", {"simulated": simulated, "state": "on", "off_at": now + seconds,
                                        "co2_ppm": value, "reading_age_s": round(r[1], 1)}, now)
        return get(self.conn, id_)

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
        spec = active_registry().get(op_id) or {}
        if spec.get("actuator"):
            return self._run_actuator(row, spec, now)
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


# ── the interlock's window onto the room ───────────────────────────────────────

def reading_from_db(db_path: Path, now: Callable[[], float] = time.time) -> Callable[[str], tuple[float, float] | None]:
    """A `reading(metric)` for the executor, straight from the sampler's SQLite,
    read-only. Returns (value, age_s) for the newest row of that channel, or None.
    Any failure is None: a broken window is a closed window, and the interlock
    refuses."""
    from datetime import datetime

    def reading(metric: str) -> tuple[float, float] | None:
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2)
            try:
                row = conn.execute(
                    "SELECT ts, value FROM raw_samples WHERE channel = ? ORDER BY id DESC LIMIT 1", (metric,)
                ).fetchone()
            finally:
                conn.close()
        except sqlite3.Error:
            return None
        if row is None:
            return None
        ts = datetime.fromisoformat(str(row[0]).replace("Z", "+00:00")).timestamp()
        return float(row[1]), max(0.0, now() - ts)

    return reading


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
