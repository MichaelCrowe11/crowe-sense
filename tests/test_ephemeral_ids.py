# SPDX-License-Identifier: MIT
# OffGrid Mesh — BLE Transport (discovery) with rotating ephemeral IDs (v2)
"""
Tests for ephemeral ID management system.
"""

import asyncio
import sys
import os
import time
import unittest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from offgrid_mesh.ephemeral_ids import EphemeralIDManager, generate_device_id, generate_shared_secret


class TestEphemeralIDManager(unittest.TestCase):
    """Test cases for EphemeralIDManager."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.device_id1 = generate_device_id()
        self.device_id2 = generate_device_id()
        self.shared_secret = generate_shared_secret()
        
        self.manager1 = EphemeralIDManager(
            device_id=self.device_id1,
            shared_secret=self.shared_secret,
            rotation_interval=10,  # 10 seconds for testing
            id_length=8
        )
        
        self.manager2 = EphemeralIDManager(
            device_id=self.device_id2,
            shared_secret=self.shared_secret,
            rotation_interval=10,
            id_length=8
        )
    
    def test_ephemeral_id_generation(self):
        """Test that ephemeral IDs are generated correctly."""
        id1 = self.manager1.get_current_ephemeral_id()
        id2 = self.manager2.get_current_ephemeral_id()
        
        # IDs should be 8 bytes
        self.assertEqual(len(id1), 8)
        self.assertEqual(len(id2), 8)
        
        # Different devices should have different IDs
        self.assertNotEqual(id1, id2)
    
    def test_ephemeral_id_consistency(self):
        """Test that the same device generates the same ID in the same epoch."""
        id1 = self.manager1.get_current_ephemeral_id()
        id2 = self.manager1.get_current_ephemeral_id()
        
        # Should be the same ID
        self.assertEqual(id1, id2)
    
    def test_verification(self):
        """Test ephemeral ID verification."""
        ephemeral_id = self.manager1.get_current_ephemeral_id()
        
        # Manager2 should be able to verify manager1's ID
        self.assertTrue(self.manager2.verify_ephemeral_id(ephemeral_id, self.device_id1))
        
        # But not with a wrong device ID
        wrong_device_id = generate_device_id()
        self.assertFalse(self.manager2.verify_ephemeral_id(ephemeral_id, wrong_device_id))
    
    def test_lookup(self):
        """Test device ID lookup from ephemeral ID."""
        ephemeral_id = self.manager1.get_current_ephemeral_id()
        
        # Verify first to cache the mapping
        self.manager2.verify_ephemeral_id(ephemeral_id, self.device_id1)
        
        # Should be able to look up
        looked_up_id = self.manager2.lookup_device_id(ephemeral_id)
        self.assertEqual(looked_up_id, self.device_id1)
    
    def test_advertisement_data(self):
        """Test advertisement data generation."""
        ad_data = self.manager1.get_advertisement_data()
        
        self.assertIn("ephemeral_id", ad_data)
        self.assertIn("version", ad_data)
        self.assertIn("timestamp", ad_data)
        
        self.assertEqual(len(ad_data["ephemeral_id"]), 8)
        self.assertEqual(ad_data["version"], b"\x02")
    
    async def test_rotation_task(self):
        """Test automatic ID rotation."""
        # Start rotation
        await self.manager1.start_rotation()
        
        try:
            id1 = self.manager1.get_current_ephemeral_id()
            
            # Wait briefly (should be same ID)
            await asyncio.sleep(1)
            id2 = self.manager1.get_current_ephemeral_id()
            self.assertEqual(id1, id2)
            
        finally:
            await self.manager1.stop_rotation()


class TestHelperFunctions(unittest.TestCase):
    """Test helper functions."""
    
    def test_generate_device_id(self):
        """Test device ID generation."""
        id1 = generate_device_id()
        id2 = generate_device_id()
        
        self.assertEqual(len(id1), 32)
        self.assertEqual(len(id2), 32)
        self.assertNotEqual(id1, id2)
    
    def test_generate_shared_secret(self):
        """Test shared secret generation."""
        secret1 = generate_shared_secret()
        secret2 = generate_shared_secret()
        
        self.assertEqual(len(secret1), 32)
        self.assertEqual(len(secret2), 32)
        self.assertNotEqual(secret1, secret2)


if __name__ == '__main__':
    unittest.main()