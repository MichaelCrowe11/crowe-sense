from __future__ import annotations

from crowe import config


def test_load_parses_node_toml(tmp_config):
    cfg = config.load()
    assert cfg.node_id == "cs-TEST00"
    assert cfg.site == "test-site"
    assert cfg.s3.bucket == "test-bucket"
    assert cfg.s3.endpoint_url == "http://localhost:9000"
    assert cfg.db_path.name == "samples.sqlite"
