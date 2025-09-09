#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# OffGrid Mesh — BLE Transport (discovery) with rotating ephemeral IDs (v2)
"""
Basic Mesh Node Example

This example demonstrates how to set up and run a basic mesh node
with ephemeral ID rotation for privacy-preserving mesh networking.
"""

import asyncio
import sys
import os

# Add parent directory to path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from offgrid_mesh import MeshNode, EphemeralIDManager
from offgrid_mesh.ephemeral_ids import generate_shared_secret


async def message_handler(message):
    """Handle received messages."""
    print(f"Received message:")
    print(f"  From: {message.source_id.hex()[:16]}...")
    print(f"  Type: {message.message_type}")
    print(f"  Payload: {message.payload.decode('utf-8', errors='ignore')}")
    print(f"  TTL: {message.ttl}")


async def main():
    """Main function to run the mesh node."""
    print("OffGrid Mesh Node Example")
    print("=" * 40)
    
    # Generate a shared secret for this demo
    # In a real deployment, this would be distributed securely to all nodes
    shared_secret = generate_shared_secret()
    print(f"Shared secret: {shared_secret.hex()[:32]}...")
    
    # Create and configure the mesh node
    node = MeshNode(
        shared_secret=shared_secret,
        device_name="ExampleMeshNode",
        rotation_interval=60,  # Rotate every minute for demo
        scan_interval=2.0
    )
    
    # Register message handler
    node.register_message_handler("chat", message_handler)
    node.register_message_handler("ping", message_handler)
    
    try:
        # Start the node
        await node.start()
        
        print(f"Node started with device ID: {node.device_id.hex()[:16]}...")
        print(f"Current ephemeral ID: {node.get_current_ephemeral_id().hex()}")
        print("Scanning for peers...")
        
        # Main loop
        message_count = 0
        while True:
            await asyncio.sleep(10)
            
            # Print status
            stats = node.get_stats()
            peers = node.get_known_peers()
            connected = node.get_connected_peers()
            
            print(f"\nStatus Update:")
            print(f"  Current ephemeral ID: {stats['current_ephemeral_id']}")
            print(f"  Known peers: {len(peers)}")
            print(f"  Connected peers: {len(connected)}")
            print(f"  Messages sent: {stats['messages_sent']}")
            print(f"  Messages received: {stats['messages_received']}")
            
            # Send a test message every minute
            message_count += 1
            if message_count % 6 == 0:  # Every 60 seconds
                test_message = f"Hello from {node.device_id.hex()[:8]} - message #{message_count//6}"
                success = await node.send_message(
                    destination_id=None,  # Broadcast
                    message_type="chat",
                    payload=test_message.encode('utf-8')
                )
                if success:
                    print(f"Sent broadcast message: {test_message}")
                else:
                    print("No peers available to send message")
                    
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        await node.stop()
        print("Node stopped")


if __name__ == "__main__":
    asyncio.run(main())