"""Watchdog — liveness LEDs, hotspot reset, mount-state checks.

GPIO map is fixed in docs/03-electronics-integration.md:
  17 green  heartbeat
  27 amber  sync activity (driven by the uploader via Unix socket)
  22 red    fault (drive missing or backhaul down)
  23 out    hotspot power-cycle (opto-FET)
"""

from __future__ import annotations

import argparse
import logging
import signal
import time
from pathlib import Path

from crowe import config
from crowe.routing import current_uplink
from crowe.storage import status as storage_status

log = logging.getLogger("crowe.watchdog")

PIN_LED_GREEN = 17
PIN_LED_AMBER = 27
PIN_LED_RED = 22
PIN_HOTSPOT_RESET = 23

HOTSPOT_RESET_HOLD_S = 3.0
BACKHAUL_FAIL_THRESHOLD = 3
BACKHAUL_RESET_COOLDOWN_S = 3600


class _Pins:
    """Tiny GPIO wrapper. Uses gpiozero on hardware, no-ops otherwise."""

    def __init__(self):
        try:
            from gpiozero import LED, OutputDevice
            self.green = LED(PIN_LED_GREEN)
            self.amber = LED(PIN_LED_AMBER)
            self.red = LED(PIN_LED_RED)
            self.reset_line = OutputDevice(PIN_HOTSPOT_RESET, initial_value=False)
            self._real = True
        except Exception:
            log.warning("gpiozero unavailable; running with stub pins")
            self._real = False

    def set(self, color: str, on: bool) -> None:
        if not self._real:
            return
        led = getattr(self, color)
        led.on() if on else led.off()

    def pulse_reset(self) -> None:
        if not self._real:
            log.info("[stub] pulse hotspot reset")
            return
        self.reset_line.on()
        time.sleep(HOTSPOT_RESET_HOLD_S)
        self.reset_line.off()


def run(cfg: config.NodeConfig, pins: _Pins, status_path: Path) -> None:
    heartbeat = True
    consecutive_backhaul_fails = 0
    last_reset_ts = 0.0
    stop = False

    def _stop(*_):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    while not stop:
        ms = storage_status(cfg.storage_mount)
        uplink = current_uplink()

        pins.set("green", heartbeat)
        heartbeat = not heartbeat

        fault = not ms.mounted or uplink is None or uplink.kind == "unknown"
        pins.set("red", fault)

        if uplink is None:
            consecutive_backhaul_fails += 1
        else:
            consecutive_backhaul_fails = 0

        now = time.time()
        if (
            consecutive_backhaul_fails >= BACKHAUL_FAIL_THRESHOLD
            and now - last_reset_ts > BACKHAUL_RESET_COOLDOWN_S
        ):
            log.warning("backhaul down for %d ticks; resetting hotspot", consecutive_backhaul_fails)
            pins.pulse_reset()
            last_reset_ts = now
            consecutive_backhaul_fails = 0

        _write_status(status_path, ms, uplink, fault)
        time.sleep(1.0)


def _write_status(path: Path, ms, uplink, fault) -> None:
    import json
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "ts": time.time(),
        "mounted": ms.mounted,
        "free_gb": ms.free_gb,
        "uplink": uplink.interface if uplink else None,
        "uplink_kind": uplink.kind if uplink else None,
        "fault": fault,
    }))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--status-path", type=Path, default=Path("/run/crowe/status.json"))
    args = p.parse_args()

    cfg = config.load()
    pins = _Pins()
    log.info("watchdog started")
    run(cfg, pins, args.status_path)


if __name__ == "__main__":
    main()
