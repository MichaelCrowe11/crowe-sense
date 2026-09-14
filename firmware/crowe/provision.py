"""crowe-provision — one-shot first-boot setup.

Generates an ed25519 keypair, writes /etc/crowe/node.toml, and prints
the public key so the operator can register it with the fleet service.
"""

from __future__ import annotations

import argparse
import base64
import json
import secrets
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

CONFIG_DIR = Path("/etc/crowe")
NODE_CONFIG = CONFIG_DIR / "node.toml"
PRIVATE_KEY = CONFIG_DIR / "node.key"
PUBLIC_KEY = CONFIG_DIR / "node.pub"

DEFAULT_RELAY = "https://sense.crowelogic.com"


def make_node_id() -> str:
    """cs- plus six lowercase hex characters, the shape the relay accepts."""
    return "cs-" + secrets.token_hex(3)


def public_key_b64(pub_pem: str) -> str:
    """The raw 32-byte Ed25519 public key, base64, which is what `crowe sense pair` sends."""
    pub = serialization.load_pem_public_key(pub_pem.encode())
    raw = pub.public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
    return base64.b64encode(raw).decode()


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


def write_operator_token(path: Path) -> str:
    """Mint the bearer that authorizes a write. Written 0600 next to node.toml and
    never printed by this tool: the operator copies the file, not a screen."""
    from crowe.operations import make_token
    token = make_token()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token + "\n")
    path.chmod(0o600)
    return token


def write_config(
    path: Path,
    node_id: str,
    site: str,
    s3_bucket: str,
    storage_mount: Path,
    private_key_path: Path,
    zone: str | None = None,
    relay_url: str = DEFAULT_RELAY,
    sensors: tuple[str, ...] = ("scd41", "sht45", "bme688", "veml7700", "pi"),
    operations: bool = False,
    operator_token_path: Path | None = None,
    tags: tuple[str, ...] = (),
) -> None:
    s3_block = f'''
[s3]
bucket = "{s3_bucket}"
prefix = ""
region = "us-east-1"
''' if s3_bucket else ""
    enabled = ", ".join(f'"{s}"' for s in sensors)
    tag_list = ", ".join(json.dumps(t) for t in tags)
    token_path = operator_token_path or (path.parent / "operator.token")
    contents = f'''# Crowe Sense node configuration
# Provisioned: do not edit by hand.

node_id = "{node_id}"
site = "{site}"
zone = "{zone or node_id}"
storage_mount = "{storage_mount}"
manifest_url = ""
private_key_path = "{private_key_path}"

[relay]
url = "{relay_url}"

[api]
port = 8078

[sensors]
enabled = [{enabled}]
{s3_block}
[sampler.periods]
# Override per-sensor cadences (seconds) here, e.g.:
# scd41 = 10.0

[device]
# What a person knows about this installation that the code does not: where the
# head sits, what the room is for. Read into GET /v1/describe. Descriptive only;
# nothing here changes what the node enforces.
tags = [{tag_list}]

[operations]
# The writable half (crowe/operations.py): indicator.identify and uplink.reset.
# Off by default. On, every request needs the bearer in token_path, and only on
# the direct path; the relay never carries a write.
enabled = {"true" if operations else "false"}
token_path = "{token_path}"

# An actuator appears in the descriptor, and its operation exists, only when it is
# declared here. Declare it only once the relay board is wired. The first kind:
# [actuators.exhaust_fan]
# kind = "exhaust_fan"
# pin = 24            # BCM; drives a normally-open relay so loss of power is off
# max_on_s = 900      # auto-off; the kind's ceiling is 1800
# min_off_s = 120     # spacing between runs, counted from the relay going off
# min_co2_ppm = 0     # >0 refuses "on" while the room is already below this
'''
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--node-id", default=None)
    p.add_argument("--site", required=True)
    p.add_argument("--zone", default=None, help="where the sensor head sits: tent-1, hood-1, incubation")
    p.add_argument("--relay", default=DEFAULT_RELAY, help="relay base URL; empty string disables the cloud push")
    p.add_argument("--sensors", default="scd41,sht45,bme688,veml7700,pi", help="comma list; a hood node uses sdp810,sht45,pi")
    p.add_argument("--s3-bucket", default="", help="optional S3 target instead of the relay")
    p.add_argument("--storage-mount", default="/mnt/crowe", type=Path)
    p.add_argument("--config-dir", default=CONFIG_DIR, type=Path)
    p.add_argument("--operations", action="store_true",
                   help="enable the writable operations and mint an operator token next to node.toml")
    p.add_argument("--tag", action="append", default=[], help="a descriptive note for the descriptor; repeatable")
    args = p.parse_args()

    node_id = args.node_id or make_node_id()
    private_key = args.config_dir / "node.key"
    public_key = args.config_dir / "node.pub"
    config_path = args.config_dir / "node.toml"

    pub_pem = write_keypair(private_key, public_key)
    token_path = args.config_dir / "operator.token"
    write_config(
        config_path, node_id, args.site, args.s3_bucket, args.storage_mount, private_key,
        zone=args.zone, relay_url=args.relay.rstrip("/"),
        sensors=tuple(s.strip() for s in args.sensors.split(",") if s.strip()),
        operations=args.operations, operator_token_path=token_path, tags=tuple(args.tag),
    )
    if args.operations:
        write_operator_token(token_path)
    b64 = public_key_b64(pub_pem)
    print(f"provisioned node {node_id} (zone {args.zone or node_id})")
    print(f"config: {config_path}")
    print(f"public key (base64 raw): {b64}")
    print("pair it from any machine signed in to Crowe ID:")
    print(f"  crowe sense pair {node_id} {b64} --zone {args.zone or node_id}")
    print("then reboot; the uploader starts pushing signed batches to the relay.")
    if args.operations:
        print(f"operations enabled; operator token in {token_path} (mode 600). Copy it to the machines that")
        print("may operate this node. It is shown nowhere else and never leaves the node by itself.")


if __name__ == "__main__":
    main()
