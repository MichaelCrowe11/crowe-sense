# SPDX-License-Identifier: MIT
# OffGrid Mesh — BLE Transport (discovery) with rotating ephemeral IDs (v2)
"""
BLE Transport Layer for OffGrid Mesh Network

This module implements the Bluetooth Low Energy transport layer for device discovery
and communication in the mesh network using rotating ephemeral IDs.
"""

import asyncio
import struct
from typing import Dict, List, Optional, Callable, Set
from bleak import BleakScanner, BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.descriptor import BleakGATTDescriptor
from bleak.backends.service import BleakGATTService

from .ephemeral_ids import EphemeralIDManager


class BLETransport:
    """
    BLE Transport implementation for mesh networking with ephemeral IDs.
    
    Handles BLE advertising, scanning, and GATT service management for
    mesh network communication while maintaining privacy through rotating IDs.
    """
    
    # Custom GATT Service and Characteristic UUIDs for mesh communication
    MESH_SERVICE_UUID = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
    EPHEMERAL_ID_CHAR_UUID = "6ba7b811-9dad-11d1-80b4-00c04fd430c8"  
    MESSAGE_CHAR_UUID = "6ba7b812-9dad-11d1-80b4-00c04fd430c8"
    STATUS_CHAR_UUID = "6ba7b813-9dad-11d1-80b4-00c04fd430c8"
    
    def __init__(
        self,
        ephemeral_manager: EphemeralIDManager,
        device_name: str = "OffGridMesh",
        scan_interval: float = 1.0
    ):
        """
        Initialize the BLE transport.
        
        Args:
            ephemeral_manager: Manager for ephemeral IDs
            device_name: BLE device name to advertise
            scan_interval: How often to perform discovery scans
        """
        self.ephemeral_manager = ephemeral_manager
        self.device_name = device_name
        self.scan_interval = scan_interval
        
        self._scanner: Optional[BleakScanner] = None
        self._discovered_peers: Dict[str, Dict] = {}  # address -> peer_info
        self._connected_clients: Dict[str, BleakClient] = {}
        self._scan_task: Optional[asyncio.Task] = None
        self._advertise_task: Optional[asyncio.Task] = None
        
        # Callbacks
        self._peer_discovered_callback: Optional[Callable] = None
        self._message_received_callback: Optional[Callable] = None
        
    def set_peer_discovered_callback(self, callback: Callable[[str, Dict], None]) -> None:
        """Set callback for when a new peer is discovered."""
        self._peer_discovered_callback = callback
        
    def set_message_received_callback(self, callback: Callable[[str, bytes], None]) -> None:
        """Set callback for when a message is received."""
        self._message_received_callback = callback
    
    async def start(self) -> None:
        """Start the BLE transport (scanning and advertising)."""
        await self._start_scanning()
        await self._start_advertising()
        
    async def stop(self) -> None:
        """Stop the BLE transport."""
        await self._stop_scanning()
        await self._stop_advertising()
        await self._disconnect_all_clients()
        
    async def _start_scanning(self) -> None:
        """Start BLE scanning for mesh peers."""
        if self._scan_task is not None:
            return
            
        self._scanner = BleakScanner(detection_callback=self._on_device_discovered)
        self._scan_task = asyncio.create_task(self._scan_loop())
        
    async def _stop_scanning(self) -> None:
        """Stop BLE scanning."""
        if self._scan_task is not None:
            self._scan_task.cancel()
            try:
                await self._scan_task
            except asyncio.CancelledError:
                pass
            self._scan_task = None
            
        if self._scanner is not None:
            await self._scanner.stop()
            self._scanner = None
    
    async def _scan_loop(self) -> None:
        """Main scanning loop."""
        while True:
            try:
                if self._scanner is not None:
                    await self._scanner.start()
                    await asyncio.sleep(self.scan_interval)
                    await self._scanner.stop()
                    
                # Brief pause between scans
                await asyncio.sleep(0.1)
                
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"Error in scan loop: {e}")
                await asyncio.sleep(1)
    
    def _on_device_discovered(self, device, advertisement_data) -> None:
        """Handle discovered BLE device."""
        # Look for our mesh service in the advertisement
        if self.MESH_SERVICE_UUID.lower() in [uuid.lower() for uuid in advertisement_data.service_uuids]:
            asyncio.create_task(self._process_discovered_device(device, advertisement_data))
    
    async def _process_discovered_device(self, device, advertisement_data) -> None:
        """Process a discovered mesh device."""
        try:
            address = device.address
            
            # Skip if we already know about this device recently
            if address in self._discovered_peers:
                last_seen = self._discovered_peers[address].get("last_seen", 0)
                if asyncio.get_event_loop().time() - last_seen < 30:  # 30 second cooldown
                    return
            
            # Extract ephemeral ID from manufacturer data or service data
            ephemeral_id = None
            if advertisement_data.manufacturer_data:
                for company_id, data in advertisement_data.manufacturer_data.items():
                    if len(data) >= 8:  # Expected ephemeral ID length
                        ephemeral_id = data[:8]
                        break
            
            if ephemeral_id is None and advertisement_data.service_data:
                for service_uuid, data in advertisement_data.service_data.items():
                    if service_uuid.lower() == self.MESH_SERVICE_UUID.lower() and len(data) >= 8:
                        ephemeral_id = data[:8]
                        break
            
            if ephemeral_id is not None:
                # Try to connect and verify the ephemeral ID
                peer_info = await self._verify_and_connect_peer(device, ephemeral_id)
                if peer_info:
                    self._discovered_peers[address] = {
                        **peer_info,
                        "last_seen": asyncio.get_event_loop().time(),
                        "address": address
                    }
                    
                    if self._peer_discovered_callback:
                        self._peer_discovered_callback(address, peer_info)
                        
        except Exception as e:
            print(f"Error processing discovered device {device.address}: {e}")
    
    async def _verify_and_connect_peer(self, device, ephemeral_id: bytes) -> Optional[Dict]:
        """Verify a peer's ephemeral ID and establish connection."""
        try:
            # Don't connect if already connected
            if device.address in self._connected_clients:
                return None
                
            client = BleakClient(device.address)
            await client.connect(timeout=10.0)
            
            # Look for our mesh service
            services = client.services
            mesh_service = services.get_service(self.MESH_SERVICE_UUID)
            if not mesh_service:
                await client.disconnect()
                return None
            
            # Read the ephemeral ID characteristic to verify
            ephemeral_char = mesh_service.get_characteristic(self.EPHEMERAL_ID_CHAR_UUID)
            if ephemeral_char:
                advertised_id = await client.read_gatt_char(ephemeral_char)
                
                # Verify this is a valid mesh peer by checking known device IDs
                device_id = self.ephemeral_manager.lookup_device_id(advertised_id)
                
                if device_id or self._is_valid_mesh_peer(advertised_id):
                    self._connected_clients[device.address] = client
                    
                    # Set up notifications for incoming messages
                    message_char = mesh_service.get_characteristic(self.MESSAGE_CHAR_UUID)
                    if message_char:
                        await client.start_notify(message_char, self._on_message_received)
                    
                    return {
                        "ephemeral_id": advertised_id,
                        "device_id": device_id,
                        "client": client,
                        "verified": True
                    }
            
            await client.disconnect()
            return None
            
        except Exception as e:
            print(f"Error verifying peer {device.address}: {e}")
            try:
                if 'client' in locals():
                    await client.disconnect()
            except:
                pass
            return None
    
    def _is_valid_mesh_peer(self, ephemeral_id: bytes) -> bool:
        """
        Check if an ephemeral ID represents a valid mesh peer.
        
        This could be extended to verify against a list of known device IDs
        or use other cryptographic verification methods.
        """
        # For now, we'll accept any ephemeral ID that follows our format
        return len(ephemeral_id) == 8
    
    def _on_message_received(self, sender_char: BleakGATTCharacteristic, data: bytes) -> None:
        """Handle received message from a peer."""
        try:
            # Find which client this came from
            sender_address = None
            for address, client in self._connected_clients.items():
                if sender_char in client.services.characteristics:
                    sender_address = address
                    break
            
            if sender_address and self._message_received_callback:
                self._message_received_callback(sender_address, data)
                
        except Exception as e:
            print(f"Error handling received message: {e}")
    
    async def _start_advertising(self) -> None:
        """Start BLE advertising with current ephemeral ID."""
        if self._advertise_task is not None:
            return
            
        self._advertise_task = asyncio.create_task(self._advertise_loop())
    
    async def _stop_advertising(self) -> None:
        """Stop BLE advertising."""
        if self._advertise_task is not None:
            self._advertise_task.cancel()
            try:
                await self._advertise_task
            except asyncio.CancelledError:
                pass
            self._advertise_task = None
    
    async def _advertise_loop(self) -> None:
        """Main advertising loop."""
        while True:
            try:
                # Set up GATT server with current ephemeral ID
                await self._setup_gatt_server()
                
                # Advertise for 30 seconds, then refresh
                await asyncio.sleep(30)
                    
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"Error in advertise loop: {e}")
                await asyncio.sleep(5)
    
    async def _setup_gatt_server(self) -> None:
        """Set up the GATT server with mesh service."""
        # Note: BleakServer is not available in current bleak version
        # This is a placeholder for future implementation when peripheral mode is available
        print("GATT server setup - not implemented in current bleak version")
        
        # In a real implementation, this would:
        # 1. Create a GATT server
        # 2. Add the mesh service with characteristics
        # 3. Set the ephemeral ID in the characteristic
        # 4. Start advertising with the service UUID
        
        await asyncio.sleep(0.1)  # Placeholder
    
    async def send_message(self, peer_address: str, message: bytes) -> bool:
        """
        Send a message to a connected peer.
        
        Args:
            peer_address: BLE address of the peer
            message: Message data to send
            
        Returns:
            True if message was sent successfully
        """
        try:
            client = self._connected_clients.get(peer_address)
            if not client or not client.is_connected:
                return False
            
            # Find the message characteristic
            services = client.services
            mesh_service = services.get_service(self.MESH_SERVICE_UUID)
            if not mesh_service:
                return False
                
            message_char = mesh_service.get_characteristic(self.MESSAGE_CHAR_UUID)
            if not message_char:
                return False
            
            await client.write_gatt_char(message_char, message)
            return True
            
        except Exception as e:
            print(f"Error sending message to {peer_address}: {e}")
            return False
    
    async def _disconnect_all_clients(self) -> None:
        """Disconnect from all connected clients."""
        for address, client in list(self._connected_clients.items()):
            try:
                if client.is_connected:
                    await client.disconnect()
            except Exception as e:
                print(f"Error disconnecting from {address}: {e}")
            
        self._connected_clients.clear()
    
    def get_discovered_peers(self) -> Dict[str, Dict]:
        """Get the list of discovered mesh peers."""
        return self._discovered_peers.copy()
    
    def get_connected_peers(self) -> List[str]:
        """Get the list of currently connected peer addresses."""
        return [addr for addr, client in self._connected_clients.items() if client.is_connected]