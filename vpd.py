#!/usr/bin/env python3
"""Vapour pressure deficit, derived from what the grower already said.

The corpus grounds relative humidity well and VPD not at all: zero mentions of
VPD or vapour pressure across 69 transcripts, zero of 642 constants. The rig
computes vpd_kpa anyway, and VPD is the variable that actually describes what
the mushroom experiences, because RH moves with temperature. Over 23 days of
real readings the tents held 78-92% RH while VPD swung 0.17 to 0.65 kPa, almost
fourfold. Judging RH alone treats those as the same room.

VPD is a deterministic function of temperature and RH, so deriving it from
documented practice is a change of units and not a new claim. The formula here
was checked against the rig's own vpd_kpa over all 469 published hours: mean
error -0.0001 kPa, worst 0.0007, which is rounding in the stored means. Same
quantity, air VPD rather than leaf VPD.

What must NOT happen is laundering. A derived band is exactly as trustworthy as
the two bands behind it, so if sense_check.py refuses to judge a temperature
band resting on one video, that band must not come back in wearing VPD units.
derive() therefore returns None unless both parents are judgeable, and says
which parent was missing.
"""
from __future__ import annotations

import math

# Tetens/Magnus over water. Matches the rig.
def svp_kpa(temp_c: float) -> float:
    """Saturation vapour pressure at a given air temperature."""
    return 0.6108 * math.exp(17.27 * temp_c / (temp_c + 237.3))


def vpd_kpa(temp_c: float, rh_pct: float) -> float:
    return svp_kpa(temp_c) * (1.0 - rh_pct / 100.0)


def rh_for_vpd(temp_c: float, target_vpd: float) -> float:
    """The RH that produces a given VPD at a given temperature."""
    return 100.0 * (1.0 - target_vpd / svp_kpa(temp_c))


def derive(temp_low: float | None, temp_high: float | None,
           rh_low: float | None, rh_high: float | None) -> tuple | None:
    """The VPD band implied by a temperature band and a humidity band.

    VPD rises with temperature and falls with humidity, so the corners are the
    extremes: the driest corner is the hottest temperature against the lowest
    humidity, and the wettest is the coolest against the highest.

    Returns None if either side is missing, because a VPD band needs both and
    half of one is not a band."""
    if temp_low is None or temp_high is None:
        return None
    if rh_low is None and rh_high is None:
        return None
    lo = vpd_kpa(temp_low, rh_high) if rh_high is not None else None
    hi = vpd_kpa(temp_high, rh_low) if rh_low is not None else None
    if lo is not None and hi is not None and lo > hi:
        lo, hi = hi, lo
    return (round(lo, 3) if lo is not None else None,
            round(hi, 3) if hi is not None else None)


def implied_ceiling(rh_floor: float, temps: list[float]) -> tuple[float, float]:
    """What a fixed RH floor actually demands of VPD, across real temperatures.

    This is the number worth saying out loud. A floor of "keep it at 80 percent"
    is not one VPD target, it is a moving one: at 18C it permits 0.41 kPa and at
    24C it permits 0.65, so the same rule means different things at either end
    of a night. That drift is precisely why RH is the misleading variable to
    document, and quantifying it is what turns 'I hold 80 percent' into a VPD
    figure that can be stated and then judged."""
    vs = [vpd_kpa(t, rh_floor) for t in temps]
    return min(vs), max(vs)
