"""Mount detection for the 1 TB drive.

The sampler degrades to an in-memory ring buffer if the drive is missing.
This module reports whether the configured mount point is actually
backed by a different filesystem than the root (i.e. the drive is
mounted), and exposes free-space stats for the health snapshot.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class MountStatus:
    path: Path
    mounted: bool
    total_bytes: int
    free_bytes: int

    @property
    def free_gb(self) -> int:
        return self.free_bytes // (1024**3)


def status(mount: Path) -> MountStatus:
    if not mount.exists():
        return MountStatus(mount, False, 0, 0)

    root_dev = os.stat("/").st_dev
    try:
        mount_dev = os.stat(mount).st_dev
    except FileNotFoundError:
        return MountStatus(mount, False, 0, 0)

    mounted = mount_dev != root_dev
    if not mounted:
        return MountStatus(mount, False, 0, 0)

    usage = shutil.disk_usage(mount)
    return MountStatus(mount, True, usage.total, usage.free)
