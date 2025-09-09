# SPDX-License-Identifier: MIT
# OffGrid Mesh — BLE Transport (discovery) with rotating ephemeral IDs (v2)
"""
Mesh Node Implementation for OffGrid Mesh Network

This module provides the main MeshNode class that combines ephemeral ID management
and BLE transport to create a complete mesh networking node.
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass

from .ephemeral_ids import EphemeralIDManager, generate_device_id
from .ble_transport import BLETransport


@dataclass
class MeshMessage:
    """Represents a message in the mesh network."""
    source_id: bytes
    destination_id: Optional[bytes]  # None for broadcast
    message_type: str
    payload: bytes
    timestamp: float
    ttl: int = 10  # Time to live for routing


class MeshNode:
    """
    Main mesh network node implementation.
    
    Combines ephemeral ID management with BLE transport to provide
    a complete mesh networking solution with privacy protection.
    """
    
    def __init__(
        self,
        device_id: Optional[bytes] = None,
        shared_secret: Optional[bytes] = None,
        device_name: str = "OffGridMesh",
        rotation_interval: int = 300,
        scan_interval: float = 1.0
    ):
        """
        Initialize a mesh node.
        
        Args:
            device_id: Unique device identifier (generated if None)
            shared_secret: Shared secret for the mesh (must be same for all nodes)
            device_name: BLE device name
            rotation_interval: Ephemeral ID rotation interval in seconds
            scan_interval: BLE scan interval in seconds
        """
        if device_id is None:
            device_id = generate_device_id()
        if shared_secret is None:
            raise ValueError("Shared secret must be provided for mesh networking")
            
        self.device_id = device_id
        self.device_name = device_name
        
        # Initialize ephemeral ID manager
        self.ephemeral_manager = EphemeralIDManager(
            device_id=device_id,
            shared_secret=shared_secret,
            rotation_interval=rotation_interval
        )
        
        # Initialize BLE transport
        self.ble_transport = BLETransport(
            ephemeral_manager=self.ephemeral_manager,
            device_name=device_name,
            scan_interval=scan_interval
        )
        
        # Set up transport callbacks
        self.ble_transport.set_peer_discovered_callback(self._on_peer_discovered)
        self.ble_transport.set_message_received_callback(self._on_message_received)
        
        # Internal state
        self._known_peers: Dict[bytes, Dict] = {}  # device_id -> peer_info
        self._message_handlers: Dict[str, Callable] = {}
        self._routing_table: Dict[bytes, str] = {}  # device_id -> ble_address
        self._message_cache: Dict[str, float] = {}  # message_id -> timestamp (for duplicate detection)
        self._running = False
        
        # Statistics
        self.stats = {
            "messages_sent": 0,
            "messages_received": 0,
            "peers_discovered": 0,
            "id_rotations": 0
        }
    
    async def start(self) -> None:
        """Start the mesh node."""
        if self._running:
            return
            
        self._running = True
        
        # Start ephemeral ID rotation
        await self.ephemeral_manager.start_rotation()
        
        # Start BLE transport
        await self.ble_transport.start()
        
        print(f"Mesh node started with device ID: {self.device_id.hex()[:16]}...")
    
    async def stop(self) -> None:
        """Stop the mesh node."""
        if not self._running:
            return
            
        self._running = False
        
        # Stop components
        await self.ble_transport.stop()
        await self.ephemeral_manager.stop_rotation()
        
        print("Mesh node stopped")
    
    def register_message_handler(self, message_type: str, handler: Callable[[MeshMessage], None]) -> None:
        """
        Register a handler for a specific message type.
        
        Args:
            message_type: Type of message to handle
            handler: Function to call when message is received
        """
        self._message_handlers[message_type] = handler
    
    def _on_peer_discovered(self, address: str, peer_info: Dict) -> None:
        """Handle discovery of a new peer."""
        try:
            device_id = peer_info.get("device_id")
            if device_id:
                self._known_peers[device_id] = {
                    "address": address,
                    "ephemeral_id": peer_info["ephemeral_id"],
                    "last_seen": time.time(),
                    "verified": peer_info.get("verified", False)
                }
                self._routing_table[device_id] = address
                self.stats["peers_discovered"] += 1
                
                print(f"Discovered mesh peer: {device_id.hex()[:16]}... at {address}")
        except Exception as e:
            print(f"Error handling peer discovery: {e}")
    
    def _on_message_received(self, sender_address: str, data: bytes) -> None:
        """Handle received message from BLE transport."""
        try:
            # Parse the mesh message
            message = self._parse_message(data)
            if message is None:
                return
            
            # Check for duplicates
            message_id = self._get_message_id(message)
            current_time = time.time()
            
            if message_id in self._message_cache:
                if current_time - self._message_cache[message_id] < 60:  # 1 minute duplicate window
                    return
            
            self._message_cache[message_id] = current_time
            self.stats["messages_received"] += 1
            
            # Handle the message asynchronously
            asyncio.create_task(self._handle_received_message(message, sender_address))
            
        except Exception as e:
            print(f"Error handling received message: {e}")
    
    async def _handle_received_message(self, message: MeshMessage, sender_address: str) -> None:
        """Process a received mesh message."""
        try:
            # Check if message is for us
            if message.destination_id is None or message.destination_id == self.device_id:
                # Message for us - handle it
                handler = self._message_handlers.get(message.message_type)
                if handler:
                    handler(message)
                else:
                    print(f"No handler for message type: {message.message_type}")
            
            # Forward message if TTL allows and we're not the original sender
            if message.ttl > 1 and message.source_id != self.device_id:
                await self._forward_message(message, sender_address)
                
        except Exception as e:
            print(f"Error handling message: {e}")
    
    async def _forward_message(self, message: MeshMessage, received_from: str) -> None:
        """Forward a message to other peers."""
        try:
            # Decrement TTL
            message.ttl -= 1
            
            # Forward to all connected peers except the one we received from
            connected_peers = self.ble_transport.get_connected_peers()
            
            for peer_address in connected_peers:
                if peer_address != received_from:
                    message_data = self._serialize_message(message)
                    await self.ble_transport.send_message(peer_address, message_data)
                    
        except Exception as e:
            print(f"Error forwarding message: {e}")
    
    async def send_message(
        self, 
        destination_id: Optional[bytes], 
        message_type: str, 
        payload: bytes,
        ttl: int = 10
    ) -> bool:
        """
        Send a message to a specific peer or broadcast.
        
        Args:
            destination_id: Target device ID (None for broadcast)
            message_type: Type of message
            payload: Message payload
            ttl: Time to live for routing
            
        Returns:
            True if message was sent to at least one peer
        """
        try:
            message = MeshMessage(
                source_id=self.device_id,
                destination_id=destination_id,
                message_type=message_type,
                payload=payload,
                timestamp=time.time(),
                ttl=ttl
            )
            
            message_data = self._serialize_message(message)
            sent_count = 0
            
            if destination_id is not None and destination_id in self._routing_table:
                # Send directly to specific peer
                peer_address = self._routing_table[destination_id]
                if await self.ble_transport.send_message(peer_address, message_data):
                    sent_count += 1
            else:
                # Broadcast to all connected peers
                connected_peers = self.ble_transport.get_connected_peers()
                for peer_address in connected_peers:
                    if await self.ble_transport.send_message(peer_address, message_data):
                        sent_count += 1
            
            if sent_count > 0:
                self.stats["messages_sent"] += 1
                return True
                
            return False
            
        except Exception as e:
            print(f"Error sending message: {e}")
            return False
    
    def _serialize_message(self, message: MeshMessage) -> bytes:
        """Serialize a mesh message to bytes."""
        try:
            data = {
                "source_id": message.source_id.hex(),
                "destination_id": message.destination_id.hex() if message.destination_id else None,
                "message_type": message.message_type,
                "payload": message.payload.hex(),
                "timestamp": message.timestamp,
                "ttl": message.ttl
            }
            
            return json.dumps(data).encode('utf-8')
            
        except Exception as e:
            print(f"Error serializing message: {e}")
            return b""
    
    def _parse_message(self, data: bytes) -> Optional[MeshMessage]:
        """Parse bytes into a mesh message."""
        try:
            json_data = json.loads(data.decode('utf-8'))
            
            return MeshMessage(
                source_id=bytes.fromhex(json_data["source_id"]),
                destination_id=bytes.fromhex(json_data["destination_id"]) if json_data["destination_id"] else None,
                message_type=json_data["message_type"],
                payload=bytes.fromhex(json_data["payload"]),
                timestamp=json_data["timestamp"],
                ttl=json_data["ttl"]
            )
            
        except Exception as e:
            print(f"Error parsing message: {e}")
            return None
    
    def _get_message_id(self, message: MeshMessage) -> str:
        """Generate a unique ID for a message to detect duplicates."""
        return f"{message.source_id.hex()}:{message.timestamp}:{hash(message.payload)}"
    
    def get_current_ephemeral_id(self) -> bytes:
        """Get the current ephemeral ID for this node."""
        return self.ephemeral_manager.get_current_ephemeral_id()
    
    def get_known_peers(self) -> Dict[bytes, Dict]:
        """Get information about known peers."""
        return self._known_peers.copy()
    
    def get_connected_peers(self) -> List[str]:
        """Get list of currently connected peer addresses."""
        return self.ble_transport.get_connected_peers()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get node statistics."""
        return {
            **self.stats,
            "current_ephemeral_id": self.get_current_ephemeral_id().hex(),
            "known_peers": len(self._known_peers),
            "connected_peers": len(self.get_connected_peers())
        }