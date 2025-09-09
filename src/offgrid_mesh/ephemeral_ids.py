# SPDX-License-Identifier: MIT
# OffGrid Mesh — BLE Transport (discovery) with rotating ephemeral IDs (v2)
"""
Ephemeral ID Manager for Privacy-Preserving Device Discovery

This module implements rotating ephemeral identifiers that change periodically
to prevent tracking while allowing mesh network participants to recognize each other.
"""

import asyncio
import hashlib
import secrets
import struct
import time
from typing import Optional, Dict, List, Tuple
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend


class EphemeralIDManager:
    """
    Manages rotating ephemeral IDs for privacy-preserving mesh discovery.
    
    Each device has a long-term identity key and generates ephemeral IDs that rotate
    at configurable intervals. Other mesh participants can verify these IDs using
    shared cryptographic material while external observers cannot track devices.
    """
    
    def __init__(
        self, 
        device_id: bytes, 
        shared_secret: bytes,
        rotation_interval: int = 300,  # 5 minutes default
        id_length: int = 8
    ):
        """
        Initialize the ephemeral ID manager.
        
        Args:
            device_id: Unique device identifier (32 bytes)
            shared_secret: Shared secret for the mesh network (32 bytes)
            rotation_interval: How often to rotate IDs in seconds
            id_length: Length of ephemeral IDs in bytes
        """
        if len(device_id) != 32:
            raise ValueError("Device ID must be 32 bytes")
        if len(shared_secret) != 32:
            raise ValueError("Shared secret must be 32 bytes")
            
        self.device_id = device_id
        self.shared_secret = shared_secret
        self.rotation_interval = rotation_interval
        self.id_length = id_length
        
        self._current_ephemeral_id: Optional[bytes] = None
        self._current_epoch: Optional[int] = None
        self._rotation_task: Optional[asyncio.Task] = None
        self._peer_ids: Dict[bytes, Tuple[bytes, int]] = {}  # ephemeral_id -> (device_id, epoch)
        
    def _get_epoch(self, timestamp: Optional[float] = None) -> int:
        """Get the current epoch based on timestamp and rotation interval."""
        if timestamp is None:
            timestamp = time.time()
        return int(timestamp // self.rotation_interval)
    
    def _derive_ephemeral_id(self, device_id: bytes, epoch: int) -> bytes:
        """
        Derive an ephemeral ID for a given device and epoch.
        
        Uses HKDF to derive a deterministic but unpredictable ephemeral ID
        from the device ID, shared secret, and current epoch.
        """
        # Create info parameter with epoch
        info = b"ephemeral_id_v2" + struct.pack(">Q", epoch)
        
        # Use HKDF to derive the ephemeral ID
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=self.id_length,
            salt=self.shared_secret,
            info=info,
            backend=default_backend()
        )
        
        return hkdf.derive(device_id)
    
    def get_current_ephemeral_id(self) -> bytes:
        """Get the current ephemeral ID for this device."""
        current_epoch = self._get_epoch()
        
        if self._current_epoch != current_epoch:
            self._current_ephemeral_id = self._derive_ephemeral_id(self.device_id, current_epoch)
            self._current_epoch = current_epoch
            
        return self._current_ephemeral_id
    
    def verify_ephemeral_id(self, ephemeral_id: bytes, suspected_device_id: bytes) -> bool:
        """
        Verify if an ephemeral ID could belong to a suspected device.
        
        Checks current and recent epochs to account for clock skew.
        """
        current_epoch = self._get_epoch()
        
        # Check current and previous epochs to handle clock skew
        for epoch_offset in range(-2, 3):  # Check 5 epochs total
            test_epoch = current_epoch + epoch_offset
            expected_id = self._derive_ephemeral_id(suspected_device_id, test_epoch)
            
            if expected_id == ephemeral_id:
                # Cache the mapping for fast lookup
                self._peer_ids[ephemeral_id] = (suspected_device_id, test_epoch)
                return True
                
        return False
    
    def lookup_device_id(self, ephemeral_id: bytes) -> Optional[bytes]:
        """
        Look up the device ID for a given ephemeral ID.
        
        Returns the cached device ID if available and still valid.
        """
        if ephemeral_id in self._peer_ids:
            device_id, epoch = self._peer_ids[ephemeral_id]
            current_epoch = self._get_epoch()
            
            # Check if the cached mapping is still valid (within 5 epochs)
            if abs(current_epoch - epoch) <= 2:
                return device_id
            else:
                # Remove stale mapping
                del self._peer_ids[ephemeral_id]
                
        return None
    
    def get_advertisement_data(self) -> Dict[str, bytes]:
        """
        Get the data to include in BLE advertisements.
        
        Returns a dictionary with the ephemeral ID and metadata.
        """
        ephemeral_id = self.get_current_ephemeral_id()
        
        return {
            "ephemeral_id": ephemeral_id,
            "version": b"\x02",  # Version 2
            "timestamp": struct.pack(">I", int(time.time()))
        }
    
    async def start_rotation(self) -> None:
        """Start the automatic ID rotation task."""
        if self._rotation_task is not None:
            return
            
        self._rotation_task = asyncio.create_task(self._rotation_loop())
    
    async def stop_rotation(self) -> None:
        """Stop the automatic ID rotation task."""
        if self._rotation_task is not None:
            self._rotation_task.cancel()
            try:
                await self._rotation_task
            except asyncio.CancelledError:
                pass
            self._rotation_task = None
    
    async def _rotation_loop(self) -> None:
        """Background task that handles ID rotation."""
        while True:
            try:
                # Calculate time until next rotation
                current_time = time.time()
                current_epoch = self._get_epoch(current_time)
                next_rotation_time = (current_epoch + 1) * self.rotation_interval
                sleep_time = next_rotation_time - current_time
                
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                
                # Force regeneration of ephemeral ID
                self._current_epoch = None
                
                # Clean up old peer ID mappings
                self._cleanup_peer_ids()
                
            except asyncio.CancelledError:
                raise
            except Exception as e:
                # Log error and continue
                print(f"Error in rotation loop: {e}")
                await asyncio.sleep(60)  # Wait a minute before retrying
    
    def _cleanup_peer_ids(self) -> None:
        """Remove stale peer ID mappings."""
        current_epoch = self._get_epoch()
        stale_ids = []
        
        for ephemeral_id, (device_id, epoch) in self._peer_ids.items():
            if abs(current_epoch - epoch) > 5:  # More than 5 epochs old
                stale_ids.append(ephemeral_id)
        
        for ephemeral_id in stale_ids:
            del self._peer_ids[ephemeral_id]


def generate_device_id() -> bytes:
    """Generate a random 32-byte device ID."""
    return secrets.token_bytes(32)


def generate_shared_secret() -> bytes:
    """Generate a random 32-byte shared secret for a mesh network."""
    return secrets.token_bytes(32)