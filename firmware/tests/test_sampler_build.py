from crowe.sampler import _build_sensors


def test_build_sensors_follows_the_enabled_list(fake_bus):
    names = [s.name for s in _build_sensors(fake_bus, {}, ("sdp810", "sht45", "pi"))]
    assert names == ["sdp810", "sht45", "pi"]


def test_unknown_driver_is_skipped_not_fatal(fake_bus):
    names = [s.name for s in _build_sensors(fake_bus, {"sht45": 9.0}, ("sht45", "nope"))]
    assert names == ["sht45"]
