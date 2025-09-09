# SPDX-License-Identifier: MIT
# OffGrid Mesh — BLE Transport (discovery) with rotating ephemeral IDs (v2)
"""
Command-line interface for OffGrid Mesh Network

Provides a simple CLI to run mesh nodes, generate keys, and manage the network.
"""

import argparse
import asyncio
import sys
import os
import json
from pathlib import Path

from .mesh_node import MeshNode
from .ephemeral_ids import generate_device_id, generate_shared_secret


DEFAULT_CONFIG_PATH = Path.home() / ".config" / "offgrid-mesh" / "config.json"


def load_config(config_path: Path = DEFAULT_CONFIG_PATH) -> dict:
    """Load configuration from file."""
    if not config_path.exists():
        return {}
    
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config from {config_path}: {e}")
        return {}


def save_config(config: dict, config_path: Path = DEFAULT_CONFIG_PATH) -> None:
    """Save configuration to file."""
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"Error saving config to {config_path}: {e}")


def cmd_generate_keys(args):
    """Generate a new device ID and shared secret."""
    device_id = generate_device_id()
    shared_secret = generate_shared_secret()
    
    print("Generated new mesh network keys:")
    print(f"Device ID: {device_id.hex()}")
    print(f"Shared Secret: {shared_secret.hex()}")
    print()
    print("Save the shared secret securely and distribute it to all mesh nodes.")
    print("Each node should have a unique device ID but the same shared secret.")
    
    if args.save:
        config = load_config(args.config)
        config['device_id'] = device_id.hex()
        config['shared_secret'] = shared_secret.hex()
        save_config(config, args.config)
        print(f"Configuration saved to: {args.config}")


async def cmd_run_node(args):
    """Run a mesh node."""
    config = load_config(args.config)
    
    # Get device ID
    device_id = None
    if args.device_id:
        device_id = bytes.fromhex(args.device_id)
    elif 'device_id' in config:
        device_id = bytes.fromhex(config['device_id'])
    
    # Get shared secret
    shared_secret = None
    if args.shared_secret:
        shared_secret = bytes.fromhex(args.shared_secret)
    elif 'shared_secret' in config:
        shared_secret = bytes.fromhex(config['shared_secret'])
    else:
        print("Error: Shared secret required. Use --shared-secret or generate keys first.")
        return 1
    
    # Create node
    node = MeshNode(
        device_id=device_id,
        shared_secret=shared_secret,
        device_name=args.name,
        rotation_interval=args.rotation_interval,
        scan_interval=args.scan_interval
    )
    
    # Register message handlers
    def handle_chat(message):
        print(f"[CHAT] {message.source_id.hex()[:8]}: {message.payload.decode('utf-8', errors='ignore')}")
    
    def handle_ping(message):
        print(f"[PING] from {message.source_id.hex()[:8]}")
        # Send pong response
        asyncio.create_task(node.send_message(
            message.source_id,
            "pong", 
            b"pong response"
        ))
    
    def handle_pong(message):
        print(f"[PONG] from {message.source_id.hex()[:8]}")
    
    node.register_message_handler("chat", handle_chat)
    node.register_message_handler("ping", handle_ping)
    node.register_message_handler("pong", handle_pong)
    
    try:
        await node.start()
        print(f"OffGrid Mesh Node Started")
        print(f"Device ID: {node.device_id.hex()[:16]}...")
        print(f"Device Name: {args.name}")
        print(f"Rotation Interval: {args.rotation_interval}s")
        print("Press Ctrl+C to stop")
        print()
        
        # Main loop with status updates
        while True:
            await asyncio.sleep(30)  # Status every 30 seconds
            
            stats = node.get_stats()
            peers = node.get_connected_peers()
            
            print(f"Status: {len(peers)} peers, "
                  f"sent {stats['messages_sent']}, "
                  f"received {stats['messages_received']}, "
                  f"ID: {stats['current_ephemeral_id'][:8]}...")
                  
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        await node.stop()
    
    return 0


def cmd_send_message(args):
    """Send a message to the mesh network."""
    print("Interactive message sending not yet implemented.")
    print("Use the run-node command and it will handle chat messages automatically.")
    return 1


def create_parser():
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        description="OffGrid Mesh Network CLI",
        epilog="Use 'offgrid-mesh <command> --help' for command-specific help."
    )
    
    parser.add_argument(
        '--config', 
        type=Path, 
        default=DEFAULT_CONFIG_PATH,
        help='Configuration file path'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Generate keys command
    gen_parser = subparsers.add_parser('generate-keys', help='Generate device ID and shared secret')
    gen_parser.add_argument(
        '--save', 
        action='store_true',
        help='Save generated keys to config file'
    )
    
    # Run node command
    run_parser = subparsers.add_parser('run-node', help='Run a mesh node')
    run_parser.add_argument(
        '--device-id',
        type=str,
        help='Device ID (hex string, generated if not provided)'
    )
    run_parser.add_argument(
        '--shared-secret',
        type=str,
        required=False,
        help='Shared secret (hex string)'
    )
    run_parser.add_argument(
        '--name',
        type=str,
        default='OffGridMesh',
        help='BLE device name'
    )
    run_parser.add_argument(
        '--rotation-interval',
        type=int,
        default=300,
        help='Ephemeral ID rotation interval in seconds (default: 300)'
    )
    run_parser.add_argument(
        '--scan-interval',
        type=float,
        default=1.0,
        help='BLE scan interval in seconds (default: 1.0)'
    )
    
    # Send message command (placeholder)
    send_parser = subparsers.add_parser('send', help='Send a message to the mesh')
    send_parser.add_argument('message', help='Message to send')
    send_parser.add_argument('--type', default='chat', help='Message type')
    
    return parser


def main():
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        if args.command == 'generate-keys':
            cmd_generate_keys(args)
            return 0
        elif args.command == 'run-node':
            return asyncio.run(cmd_run_node(args))
        elif args.command == 'send':
            return cmd_send_message(args)
        else:
            print(f"Unknown command: {args.command}")
            return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())