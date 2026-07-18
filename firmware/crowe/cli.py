"""Unified `crowe` command — the operator's front door to a node.

The firmware ships one systemd service per job (sampler, uploader, health,
watchdog). Those are great for the machine but awkward for a human standing
in front of a node with a laptop. This module is the single command you
reach for in that moment:

    crowe status              # is this node healthy right now?
    crowe read --last 20      # what has it measured recently?
    crowe read --sensor scd41 # ...for one sensor
    crowe storage             # is the 1 TB drive mounted, how full?
    crowe uplink              # cellular or site Wi-Fi right now?
    crowe queue               # how many samples are waiting to ship?

Everything here is read-only and hardware-free: it reads the local SQLite
DB, the mount table, and /proc/net/route. It never touches the I2C bus, so
it is safe to run alongside the live sampler.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections.abc import Sequence

from crowe import __version__, config
from crowe.routing import current_uplink
from crowe.storage import status as storage_status


def _open_readonly(cfg: config.NodeConfig) -> sqlite3.Connection | None:
    """Open the samples DB read-only. Returns None if it does not exist yet."""
    if not cfg.db_path.exists():
        return None
    uri = f"file:{cfg.db_path}?mode=ro"
    return sqlite3.connect(uri, uri=True, check_same_thread=False)


def _queue_depth(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM raw_samples WHERE sent = 0").fetchone()[0]


def _last_sample_ts(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT ts FROM raw_samples ORDER BY id DESC LIMIT 1").fetchone()
    return row[0] if row else None


# ---- commands ---------------------------------------------------------------


def cmd_status(cfg: config.NodeConfig, args: argparse.Namespace) -> int:
    """One-shot health readout. `--json` emits the machine snapshot verbatim."""
    from crowe.health import snapshot  # lazy: pulls in psutil/httpx

    snap = snapshot(cfg)
    if args.json:
        print(json.dumps(snap, indent=2))
        return 0

    drive = snap["drive"]
    uplink = snap["uplink"]
    drive_line = (
        f"mounted, {drive['free_gb']} GB free" if drive["mounted"] else "NOT MOUNTED"
    )
    uplink_line = (
        f"{uplink['interface']} ({uplink['kind']})" if uplink["interface"] else "offline"
    )
    print(f"node      {snap['node_id']}  @ {snap['site']}")
    print(f"uptime    {snap['uptime_s']} s")
    print(f"drive     {drive_line}")
    print(f"uplink    {uplink_line}")
    print(f"queue     {snap['queue_depth']} samples pending upload")
    print(f"last read {snap['last_sample_ts'] or 'none yet'}")
    if snap["cpu_temp_c"] is not None:
        print(f"cpu temp  {snap['cpu_temp_c']:.1f} C")
    return 0


def cmd_read(cfg: config.NodeConfig, args: argparse.Namespace) -> int:
    """Print the most recent samples, newest first."""
    conn = _open_readonly(cfg)
    if conn is None:
        print("no samples database yet — has the sampler run?", file=sys.stderr)
        return 1

    sql = "SELECT ts, sensor, channel, value, unit FROM raw_samples"
    params: list[object] = []
    if args.sensor:
        sql += " WHERE sensor = ?"
        params.append(args.sensor)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(args.last)

    rows = list(conn.execute(sql, params))
    if not rows:
        where = f" for sensor {args.sensor!r}" if args.sensor else ""
        print(f"no samples found{where}", file=sys.stderr)
        return 1

    if args.json:
        out = [
            {"ts": ts, "sensor": s, "channel": c, "value": v, "unit": u}
            for ts, s, c, v, u in rows
        ]
        print(json.dumps(out, indent=2))
        return 0

    for ts, sensor, channel, value, unit in rows:
        print(f"{ts}  {sensor:<9} {channel:<14} {value:>10.3f} {unit}")
    return 0


def cmd_storage(cfg: config.NodeConfig, args: argparse.Namespace) -> int:
    ms = storage_status(cfg.storage_mount)
    rc = 0 if ms.mounted else 1
    if args.json:
        print(json.dumps(
            {
                "path": str(ms.path),
                "mounted": ms.mounted,
                "total_bytes": ms.total_bytes,
                "free_bytes": ms.free_bytes,
                "free_gb": ms.free_gb,
            },
            indent=2,
        ))
        return rc

    if not ms.mounted:
        print(f"{ms.path}: NOT MOUNTED (sampler is on the in-memory ring buffer)")
        return rc
    total_gb = ms.total_bytes // (1024**3)
    used_gb = total_gb - ms.free_gb
    print(f"{ms.path}: mounted  {used_gb} GB used / {total_gb} GB  ({ms.free_gb} GB free)")
    return rc


def cmd_uplink(cfg: config.NodeConfig, args: argparse.Namespace) -> int:
    up = current_uplink()
    rc = 0 if up is not None else 1
    if args.json:
        payload = None if up is None else {"interface": up.interface, "kind": up.kind}
        print(json.dumps(payload, indent=2))
        return rc
    if up is None:
        print("offline — no default route")
        return rc
    print(f"{up.interface} ({up.kind})")
    return rc


def cmd_queue(cfg: config.NodeConfig, args: argparse.Namespace) -> int:
    conn = _open_readonly(cfg)
    if conn is None:
        print("no samples database yet — has the sampler run?", file=sys.stderr)
        return 1
    depth = _queue_depth(conn)
    last = _last_sample_ts(conn)
    if args.json:
        print(json.dumps({"queue_depth": depth, "last_sample_ts": last}, indent=2))
        return 0
    print(f"{depth} samples pending upload (last read {last or 'none yet'})")
    return 0


# ---- argument parsing -------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="crowe",
        description="Operator CLI for a Crowe Sensor node (read-only).",
    )
    p.add_argument("--version", action="version", version=f"crowe {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    def _add(name: str, func, help_: str) -> argparse.ArgumentParser:
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("--json", action="store_true", help="emit JSON instead of text")
        sp.set_defaults(func=func)
        return sp

    _add("status", cmd_status, "node health at a glance")

    read = _add("read", cmd_read, "recent samples, newest first")
    read.add_argument("--sensor", help="filter to one sensor (e.g. scd41)")
    read.add_argument("--last", type=int, default=10, help="how many samples (default 10)")

    _add("storage", cmd_storage, "1 TB drive mount + free space")
    _add("uplink", cmd_uplink, "current internet uplink")
    _add("queue", cmd_queue, "upload backlog depth")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        cfg = config.load()
    except FileNotFoundError:
        print(
            "no node config found — set CROWE_CONFIG or provision the node first",
            file=sys.stderr,
        )
        return 2
    return args.func(cfg, args)


if __name__ == "__main__":
    raise SystemExit(main())
