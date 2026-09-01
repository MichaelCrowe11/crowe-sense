from __future__ import annotations

from crowe import config


def test_load_parses_node_toml(tmp_config):
    cfg = config.load()
    assert cfg.node_id == "cs-TEST00"
    assert cfg.site == "test-site"
    assert cfg.s3.bucket == "test-bucket"
    assert cfg.s3.endpoint_url == "http://localhost:9000"
    assert cfg.db_path.name == "samples.sqlite"


def test_relay_and_sensors_defaults(tmp_config):
    cfg = config.load()
    assert cfg.zone == "cs-TEST00"            # defaults to the node id
    assert cfg.relay_url == ""                # the fixture has no [relay]
    assert cfg.sensors_enabled == config.DEFAULT_SENSORS
    assert cfg.api_port == 8078


def test_relay_zone_and_sensor_list_parse(tmp_config):
    tmp_config.write_text(tmp_config.read_text().replace(
        'site = "test-site"', 'site = "test-site"\nzone = "hood-1"\n[relay]\nurl = "https://relay.test/"\n[sensors]\nenabled = ["sdp810", "sht45"]\n[api]\nport = 8099\n'))
    config.reset_cache()
    cfg = config.load()
    assert cfg.zone == "hood-1"
    assert cfg.relay_url == "https://relay.test"
    assert cfg.sensors_enabled == ("sdp810", "sht45")
    assert cfg.api_port == 8099
