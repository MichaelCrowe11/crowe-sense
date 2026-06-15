from __future__ import annotations

from crowe.routing import current_uplink

WIFI_ONLY = """\
Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\tMask
wlan0\t00000000\t0102A8C0\t0003\t0\t0\t600\t00000000
wlan0\t0002A8C0\t00000000\t0001\t0\t0\t600\t00FFFFFF
"""

CELLULAR_AND_WIFI = """\
Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\tMask
wwan0\t00000000\t01010A0A\t0003\t0\t0\t100\t00000000
wlan0\t00000000\t0102A8C0\t0003\t0\t0\t600\t00000000
"""

NO_DEFAULT = """\
Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\tMask
wlan0\t0002A8C0\t00000000\t0001\t0\t0\t600\t00FFFFFF
"""


def test_no_default_route_returns_none():
    assert current_uplink(NO_DEFAULT) is None


def test_wifi_only_picks_wifi():
    u = current_uplink(WIFI_ONLY)
    assert u is not None
    assert u.interface == "wlan0"
    assert u.kind == "wifi"


def test_cellular_preferred_over_wifi():
    u = current_uplink(CELLULAR_AND_WIFI)
    assert u is not None
    assert u.interface == "wwan0"
    assert u.kind == "cellular"
