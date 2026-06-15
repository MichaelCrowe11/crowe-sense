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
