"""crowe-provision — one-shot first-boot setup.

Generates an ed25519 keypair, writes /etc/crowe/node.toml, and prints
the public key so the operator can register it with the fleet service.
"""

from __future__ import annotations

import argparse
import secrets
import string
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

CONFIG_DIR = Path("/etc/crowe")
NODE_CONFIG = CONFIG_DIR / "node.toml"
PRIVATE_KEY = CONFIG_DIR / "node.key"
PUBLIC_KEY = CONFIG_DIR / "node.pub"

ALPHABET = string.digits + "ABCDEFGHJKLMNPQRSTUVWXYZ"


def make_node_id() -> str:
    return "cs-" + "".join(secrets.choice(ALPHABET) for _ in range(6))


def write_keypair(priv_path: Path, pub_path: Path) -> str:
    priv = Ed25519PrivateKey.generate()
    priv_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_pem = priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    priv_path.parent.mkdir(parents=True, exist_ok=True)
    priv_path.write_bytes(priv_pem)
    priv_path.chmod(0o600)
    pub_path.write_bytes(pub_pem)
    return pub_pem.decode()


def write_config(
    path: Path,
    node_id: str,
    site: str,
    s3_bucket: str,
    storage_mount: Path,
    private_key_path: Path,
) -> None:
    contents = f'''# Crowe Sensor node configuration
# Provisioned: do not edit by hand.

node_id = "{node_id}"
site = "{site}"
storage_mount = "{storage_mount}"
manifest_url = ""
private_key_path = "{private_key_path}"

[s3]
bucket = "{s3_bucket}"
prefix = ""
region = "us-east-1"

[sampler.periods]
# Override per-sensor cadences (seconds) here, e.g.:
# scd41 = 10.0
'''
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--node-id", default=None)
    p.add_argument("--site", required=True)
    p.add_argument("--s3-bucket", required=True)
    p.add_argument("--storage-mount", default="/mnt/crowe", type=Path)
    p.add_argument("--config-dir", default=CONFIG_DIR, type=Path)
    args = p.parse_args()

    node_id = args.node_id or make_node_id()
    private_key = args.config_dir / "node.key"
    public_key = args.config_dir / "node.pub"
    config_path = args.config_dir / "node.toml"

    pub_pem = write_keypair(private_key, public_key)
    write_config(config_path, node_id, args.site, args.s3_bucket, args.storage_mount, private_key)

    print(f"provisioned node {node_id}")
    print(f"config: {config_path}")
    print(f"public key:\n{pub_pem}")
    print("register this key with the fleet service, then reboot.")


if __name__ == "__main__":
    main()
