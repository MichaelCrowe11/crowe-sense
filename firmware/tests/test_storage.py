from __future__ import annotations

from pathlib import Path

from crowe.storage import status


def test_missing_path_reports_unmounted(tmp_path: Path):
    s = status(tmp_path / "does-not-exist")
    assert s.mounted is False
    assert s.free_bytes == 0


def test_same_device_as_root_reports_unmounted(tmp_path: Path):
    # tmp_path is on the same filesystem as / in CI, which exercises
    # the "configured mount but drive missing" failure mode.
    s = status(tmp_path)
    assert s.mounted is False
