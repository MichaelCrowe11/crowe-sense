"""Watchdog — liveness LEDs, hotspot reset, mount-state checks, and the executor
for requested operations.

GPIO map is fixed in docs/03-electronics-integration.md:
  17 green  heartbeat
  27 amber  sync activity (driven by the uploader via Unix socket)
  22 red    fault (drive missing or backhaul down)
  23 out    hotspot power-cycle (opto-FET)

This process is the only owner of those pins. The API never touches them: it queues
a request (crowe/operations.py) and the loop here runs it, so a requested identify
blink or hotspot reset goes through the same hands, the same cooldown and the same
status file as the watchdog's own behaviour.
"""

from __future__ import annotations

import argparse
import logging
import signal
import time
from pathlib import Path

from crowe import config, operations
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
    """Tiny GPIO wrapper. Uses gpiozero on hardware, no-ops otherwise.

    `actuators` (name -> ActuatorConfig) become OutputDevices that start low and are
    driven only through set_actuator(). gpiozero returns every pin to its idle state
    when the process exits normally; a hard kill relies on the wiring (a normally-open
    relay is off without a driven line) and on the next start turning everything off."""

    def __init__(self, actuators: dict | None = None):
        self.actuators: dict[str, object] = {}
        try:
            from gpiozero import LED, OutputDevice
            self.green = LED(PIN_LED_GREEN)
            self.amber = LED(PIN_LED_AMBER)
            self.red = LED(PIN_LED_RED)
            self.reset_line = OutputDevice(PIN_HOTSPOT_RESET, initial_value=False)
            for name, a in (actuators or {}).items():
                self.actuators[name] = OutputDevice(int(a.pin), initial_value=False)
            self._real = True
        except Exception:
            log.warning("gpiozero unavailable; running with stub pins")
            self._real = False

    def set_actuator(self, name: str, on: bool) -> None:
        if not self._real:
            return
        dev = self.actuators[name]
        dev.on() if on else dev.off()

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


def build_executor(cfg: config.NodeConfig, pins: _Pins) -> operations.Executor | None:
    """The queue drainer, only when node.toml turns operations on. A read-only node
    never opens the queue and never pretends it could act."""
    if not cfg.operations_enabled:
        return None
    return operations.Executor(operations.open_queue(cfg.operations_db_path), pins,
                               gpio_available=pins._real, simulate=cfg.operations_simulate,
                               actuators=cfg.actuators,
                               reading=operations.reading_from_db(cfg.db_path) if cfg.actuators else None)


def run(cfg: config.NodeConfig, pins: _Pins, status_path: Path,
        executor: operations.Executor | None = None, *, max_ticks: int | None = None,
        sleep=time.sleep, install_signals: bool = True) -> None:
    heartbeat = True
    consecutive_backhaul_fails = 0
    last_reset_ts = 0.0
    stop = False
    was_identifying = False
    ticks = 0

    def _stop(*_):
        nonlocal stop
        stop = True

    if install_signals:
        signal.signal(signal.SIGTERM, _stop)
        signal.signal(signal.SIGINT, _stop)

    try:
        while not stop and (max_ticks is None or ticks < max_ticks):
            ticks += 1
            ms = storage_status(cfg.storage_mount)
            uplink = current_uplink()

            if executor is not None:
                executor.tick()
                if executor.last_reset_ts:
                    # A requested reset counts toward the automatic one's cooldown too.
                    last_reset_ts = max(last_reset_ts, executor.last_reset_ts)

            fault = not ms.mounted or uplink is None or uplink.kind == "unknown"

            if executor is not None and executor.identifying:
                # indicator.identify: all three together, on the heartbeat's own rhythm,
                # so a person can pick this node out of a rack. The fault light is not
                # lost, only paused; it resumes the tick the blink ends.
                for color in ("green", "amber", "red"):
                    pins.set(color, heartbeat)
                was_identifying = True
            else:
                if was_identifying:
                    pins.set("amber", False)
                    was_identifying = False
                pins.set("green", heartbeat)
                pins.set("red", fault)
            heartbeat = not heartbeat

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

            _write_status(status_path, ms, uplink, fault, gpio=pins._real,
                          operations=executor is not None, identifying=executor is not None and executor.identifying)
            sleep(1.0)

    finally:
        # Whatever ended the loop, no actuator outlives the process that was
        # counting its seconds.
        if executor is not None:
            executor.stop()


def _write_status(path: Path, ms, uplink, fault, *, gpio: bool = False,
                  operations: bool = False, identifying: bool = False) -> None:
    import json
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "ts": time.time(),
        "mounted": ms.mounted,
        "free_gb": ms.free_gb,
        "uplink": uplink.interface if uplink else None,
        "uplink_kind": uplink.kind if uplink else None,
        "fault": fault,
        # Read by crowe.descriptor so the API can say whether the pin owner is real,
        # rather than guessing from a process that cannot see the pins.
        "gpio": bool(gpio),
        "operations": bool(operations),
        "identifying": bool(identifying),
    }))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--status-path", type=Path, default=Path("/run/crowe/status.json"))
    args = p.parse_args()

    cfg = config.load()
    pins = _Pins(cfg.actuators)
    executor = build_executor(cfg, pins)
    log.info("watchdog started (gpio=%s, operations=%s)", pins._real, executor is not None)
    run(cfg, pins, args.status_path, executor)


if __name__ == "__main__":
    main()
