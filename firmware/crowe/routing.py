"""Cellular vs Wi-Fi uplink selection.

The Pi sees two routes to the internet: the AT&T Nighthawk tether on
wwan0/usb0, and (when available) site Wi-Fi on wlan0. We always prefer
the cellular link because it's the deployment guarantee — site Wi-Fi
comes and goes.

We read /proc/net/route directly rather than fighting NetworkManager:
it's stable, kernel-blessed, and doesn't require dbus.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

CELLULAR_INTERFACES = ("wwan0", "usb0", "rmnet0", "enx", "eth1")
WIFI_INTERFACES = ("wlan0", "wlan1")

ROUTE_FILE = Path("/proc/net/route")


@dataclass(frozen=True, slots=True)
class Uplink:
    interface: str
    kind: str   # "cellular", "wifi", "unknown"


def _default_routes(text: str) -> list[str]:
    interfaces: list[str] = []
    for i, line in enumerate(text.splitlines()):
        if i == 0:
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        iface, destination, _gateway = parts[0], parts[1], parts[2]
        if destination == "00000000":
            interfaces.append(iface)
    return interfaces


def _classify(iface: str) -> str:
    if any(iface.startswith(p) for p in CELLULAR_INTERFACES):
        return "cellular"
    if any(iface.startswith(p) for p in WIFI_INTERFACES):
        return "wifi"
    return "unknown"


def current_uplink(route_text: str | None = None) -> Uplink | None:
    if route_text is None:
        try:
            route_text = ROUTE_FILE.read_text()
        except FileNotFoundError:
            return None

    routes = _default_routes(route_text)
    if not routes:
        return None

    classified = [(iface, _classify(iface)) for iface in routes]
    for iface, kind in classified:
        if kind == "cellular":
            return Uplink(iface, kind)
    for iface, kind in classified:
        if kind == "wifi":
            return Uplink(iface, kind)
    iface, kind = classified[0]
    return Uplink(iface, kind)
