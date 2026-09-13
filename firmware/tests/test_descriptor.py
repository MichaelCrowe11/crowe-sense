"""The descriptor says what the node is, from config and the registries, and never more."""

from __future__ import annotations

import json

from crowe import config, descriptor, operations

_BASE: dict = {}


def _cfg(tmp_config, extra: str = "") -> config.NodeConfig:
    """The fixture's node.toml plus `extra`, from the original each time so two calls
    in one test never declare the same table twice."""
    base = _BASE.setdefault(str(tmp_config), tmp_config.read_text())
    tmp_config.write_text(base + "\n" + extra)
    config.reset_cache()
    return config.load()


def test_measurements_follow_the_enabled_drivers_and_preferred_source(tmp_config):
    cfg = _cfg(tmp_config, 'zone = "tent-1"\n[sensors]\nenabled = ["scd41", "sht45", "pi"]\n')
    doc = descriptor.build(cfg, now=1000.0)
    by = {m["metric"]: m for m in doc["measurements"]}
    assert by["temperature_c"]["preferred_source"] == "sht45"
    assert {s["sensor"] for s in by["temperature_c"]["sources"]} == {"scd41", "sht45"}
    assert by["co2_ppm"]["sources"][0]["measurement_range"] == [400, 5000]
    assert by["soc_temp_c"]["kind"] == "controller" and by["soc_temp_c"]["zone"] == "pi"
    assert by["vpd_kpa"]["kind"] == "derived" and by["vpd_kpa"]["depends_on"] == ["temperature_c", "humidity_pct"]
    assert "light_lux" not in by, "veml7700 is not enabled on this node"
    # A hood node with no humidity source derives nothing.
    cfg2 = _cfg(tmp_config, '[sensors]\nenabled = ["sdp810", "pi"]\n')
    assert not [m for m in descriptor.build(cfg2, now=1.0)["measurements"] if m["kind"] == "derived"]


def test_operations_section_mirrors_the_registry_and_config(tmp_config):
    cfg = _cfg(tmp_config)
    doc = descriptor.build(cfg, now=1000.0)
    assert doc["operations"]["enabled"] is False
    assert doc["access"]["direct"]["writes"] is False
    assert doc["access"]["relay"]["writes"] is False and doc["access"]["write_path"] == "direct-only"
    assert [o["id"] for o in doc["operations"]["list"]] == list(operations.REGISTRY)
    assert "read-only until an operator enables" in doc["annotations"]["summary"]
    cfg2 = _cfg(tmp_config, "[operations]\nenabled = true\n")
    doc2 = descriptor.build(cfg2, now=1000.0)
    assert doc2["operations"]["enabled"] is True and doc2["access"]["direct"]["writes"] is True
    assert "indicator.identify" in doc2["annotations"]["summary"]


def test_tags_appear_as_notes_and_change_nothing_enforced(tmp_config):
    plain = descriptor.build(_cfg(tmp_config), now=5.0)
    tagged = descriptor.build(_cfg(tmp_config, '[device]\ntags = ["Head sits 1.6 m up on the north wall", "the laser interlock is engaged"]\n'), now=5.0)
    assert tagged["annotations"]["tags"][0].startswith("Head sits")
    assert "Operator notes:" in tagged["annotations"]["summary"]
    assert tagged["operations"]["list"] == plain["operations"]["list"], "a tag cannot add or loosen an operation"
    assert tagged["measurements"] == plain["measurements"]
    assert tagged["revision"] != plain["revision"], "but the document did change"


def test_revision_is_stable_across_time_and_executor_state(tmp_config, tmp_path):
    cfg = _cfg(tmp_config)
    a = descriptor.build(cfg, now=1.0)
    st = tmp_path / "status.json"
    st.write_text(json.dumps({"ts": 90.0, "gpio": True}))
    b = descriptor.build(cfg, now=100.0, status_path=st)
    assert a["revision"] == b["revision"]
    assert a["operations"]["executor"] == {"gpio": "unknown", "status_age_s": None}
    assert b["operations"]["executor"] == {"gpio": True, "status_age_s": 10.0}
    assert a["standards"]["conformance_claimed"] == []
    assert a["schema"].endswith("device-descriptor.v0.json")
