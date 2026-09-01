from __future__ import annotations

import tomllib
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from crowe.provision import make_node_id, write_config, write_keypair


def test_make_node_id_format():
    nid = make_node_id()
    assert nid.startswith("cs-")
    assert len(nid) == len("cs-") + 6
    assert nid[3:].isalnum()


def test_write_keypair_produces_loadable_ed25519(tmp_path: Path):
    priv = tmp_path / "node.key"
    pub = tmp_path / "node.pub"
    write_keypair(priv, pub)

    loaded = serialization.load_pem_private_key(priv.read_bytes(), password=None)
    assert isinstance(loaded, Ed25519PrivateKey)
    assert oct(priv.stat().st_mode)[-3:] == "600"


def test_write_config_is_valid_toml(tmp_path: Path):
    cfg = tmp_path / "node.toml"
    write_config(cfg, "cs-ABC123", "site-1", "bucket-x", tmp_path, tmp_path / "node.key")
    data = tomllib.loads(cfg.read_text())
    assert data["node_id"] == "cs-ABC123"
    assert data["site"] == "site-1"
    assert data["s3"]["bucket"] == "bucket-x"


def test_node_id_is_lowercase_hex_the_relay_accepts():
    import re
    assert re.fullmatch(r"cs-[0-9a-f]{6}", make_node_id())


def test_public_key_b64_is_the_raw_32_bytes(tmp_path: Path):
    import base64

    from crowe.provision import public_key_b64
    pub_pem = write_keypair(tmp_path / "k", tmp_path / "k.pub")
    raw = base64.b64decode(public_key_b64(pub_pem))
    assert len(raw) == 32


def test_write_config_defaults_to_the_relay_and_no_s3(tmp_path: Path):
    cfg = tmp_path / "node.toml"
    write_config(cfg, "cs-a1b2c3", "site-1", "", tmp_path, tmp_path / "node.key", zone="tent-1")
    data = tomllib.loads(cfg.read_text())
    assert data["zone"] == "tent-1"
    assert data["relay"]["url"] == "https://sense.crowelogic.com"
    assert "s3" not in data
    assert data["sensors"]["enabled"][0] == "scd41"
