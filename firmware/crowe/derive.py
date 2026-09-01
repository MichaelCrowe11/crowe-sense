"""Derived metrics. VPD and dew point are deterministic functions of temperature and
humidity (Tetens/Magnus, air VPD not leaf), verified against the 2026 rig's own vpd_kpa
channel to 0.0007 kPa. Nothing here is a claim about growing; it is a change of units."""

from __future__ import annotations

import math


def svp_kpa(t_c: float) -> float:
    return 0.6108 * math.exp(17.27 * t_c / (t_c + 237.3))


def vpd_kpa(t_c: float, rh_pct: float) -> float:
    return round(svp_kpa(t_c) * (1.0 - rh_pct / 100.0), 4)


def dew_point_c(t_c: float, rh_pct: float) -> float:
    rh = max(min(rh_pct, 100.0), 0.1)
    a, b = 17.27, 237.3
    gamma = a * t_c / (b + t_c) + math.log(rh / 100.0)
    return round(b * gamma / (a - gamma), 3)
