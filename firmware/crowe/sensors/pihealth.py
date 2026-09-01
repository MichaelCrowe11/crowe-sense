"""Controller health as a sensor: SoC temperature, ARM clock, core voltage, and the
undervoltage/throttle flags from the firmware. Reads sysfs and `vcgencmd` when present,
and reports nothing (rather than a guess) when neither is available."""

from __future__ import annotations

import asyncio
import contextlib
import shutil
import subprocess
from pathlib import Path

from crowe.sensors.base import Reading, now_iso

THERMAL = Path("/sys/class/thermal/thermal_zone0/temp")
CLOCK = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq")


class PiHealth:
    name = "pi"
    period_s = 30.0

    def __init__(self, thermal: Path = THERMAL, clock: Path = CLOCK, vcgencmd: str | None = None):
        self._thermal = thermal
        self._clock = clock
        self._vcgencmd = vcgencmd if vcgencmd is not None else shutil.which("vcgencmd")

    def _throttled(self) -> int | None:
        if not self._vcgencmd:
            return None
        try:
            out = subprocess.run([self._vcgencmd, "get_throttled"], capture_output=True, text=True, timeout=2).stdout
            return int(out.strip().split("=")[1], 16)
        except (OSError, ValueError, IndexError, subprocess.SubprocessError):
            return None

    def _volts(self) -> float | None:
        if not self._vcgencmd:
            return None
        try:
            out = subprocess.run([self._vcgencmd, "measure_volts", "core"], capture_output=True, text=True, timeout=2).stdout
            return float(out.strip().split("=")[1].rstrip("V"))
        except (OSError, ValueError, IndexError, subprocess.SubprocessError):
            return None

    def sample(self) -> list[Reading]:
        ts = now_iso()
        out: list[Reading] = []
        with contextlib.suppress(OSError, ValueError):
            out.append(Reading(ts, self.name, "soc_temp_c", int(self._thermal.read_text().strip()) / 1000.0, "C"))
        with contextlib.suppress(OSError, ValueError):
            out.append(Reading(ts, self.name, "arm_clock_mhz", int(self._clock.read_text().strip()) / 1000.0, "MHz"))
        flags = self._throttled()
        if flags is not None:
            out.append(Reading(ts, self.name, "undervoltage_now", float(bool(flags & 0x1)), "bool"))
            out.append(Reading(ts, self.name, "throttled_now", float(bool(flags & 0x4)), "bool"))
        volts = self._volts()
        if volts is not None:
            out.append(Reading(ts, self.name, "core_volts", volts, "V"))
        return out

    async def read(self) -> list[Reading]:
        return await asyncio.to_thread(self.sample)
