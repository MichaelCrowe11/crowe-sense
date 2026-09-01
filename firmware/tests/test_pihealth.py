from crowe.sensors.pihealth import PiHealth


def test_reads_sysfs_and_skips_vcgencmd_when_absent(tmp_path):
    (tmp_path / "temp").write_text("48250\n")
    (tmp_path / "freq").write_text("1500000\n")
    s = PiHealth(thermal=tmp_path / "temp", clock=tmp_path / "freq", vcgencmd="")
    got = {r.channel: (r.value, r.unit) for r in s.sample()}
    assert got == {"soc_temp_c": (48.25, "C"), "arm_clock_mhz": (1500.0, "MHz")}


def test_reports_nothing_rather_than_a_guess(tmp_path):
    s = PiHealth(thermal=tmp_path / "missing", clock=tmp_path / "missing", vcgencmd="")
    assert s.sample() == []


def test_parses_throttled_flags_and_volts(tmp_path):
    fake = tmp_path / "vcgencmd"
    fake.write_text('#!/bin/sh\ncase "$1" in get_throttled) echo "throttled=0x50005";; measure_volts) echo "volt=0.8500V";; esac\n')
    fake.chmod(0o755)
    (tmp_path / "temp").write_text("50000\n")
    s = PiHealth(thermal=tmp_path / "temp", clock=tmp_path / "nofreq", vcgencmd=str(fake))
    got = {r.channel: r.value for r in s.sample()}
    assert got["undervoltage_now"] == 1.0
    assert got["throttled_now"] == 1.0
    assert got["core_volts"] == 0.85
