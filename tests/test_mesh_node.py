# SPDX-License-Identifier: MIT
# OffGrid Mesh — BLE Transport (discovery) with rotating ephemeral IDs (v2)
"""
Tests for mesh node functionality.
"""

import asyncio
import sys
import os
import unittest
from unittest.mock import MagicMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from offgrid_mesh.mesh_node import MeshNode, MeshMessage
from offgrid_mesh.ephemeral_ids import generate_shared_secret


class TestMeshMessage(unittest.TestCase):
    """Test MeshMessage dataclass."""
    
    def test_message_creation(self):
        """Test creating a mesh message."""
        source_id = b"0123456789abcdef" * 2
        destination_id = b"fedcba9876543210" * 2
        
        message = MeshMessage(
            source_id=source_id,
            destination_id=destination_id,
            message_type="test",
            payload=b"hello",
            timestamp=1234567890.0,
            ttl=5
        )
        
        self.assertEqual(message.source_id, source_id)
        self.assertEqual(message.destination_id, destination_id)
        self.assertEqual(message.message_type, "test")
        self.assertEqual(message.payload, b"hello")
        self.assertEqual(message.timestamp, 1234567890.0)
        self.assertEqual(message.ttl, 5)


class TestMeshNode(unittest.TestCase):
    """Test MeshNode functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.shared_secret = generate_shared_secret()
        
        self.node1 = MeshNode(
            shared_secret=self.shared_secret,
            device_name="TestNode1",
            rotation_interval=60,
            scan_interval=1.0
        )
        
        self.node2 = MeshNode(
            shared_secret=self.shared_secret,
            device_name="TestNode2", 
            rotation_interval=60,
            scan_interval=1.0
        )
    
    def test_node_initialization(self):
        """Test node initialization."""
        self.assertEqual(len(self.node1.device_id), 32)
        self.assertEqual(len(self.node2.device_id), 32)
        self.assertNotEqual(self.node1.device_id, self.node2.device_id)
        
        # Should have ephemeral IDs
        eid1 = self.node1.get_current_ephemeral_id()
        eid2 = self.node2.get_current_ephemeral_id()
        self.assertEqual(len(eid1), 8)
        self.assertEqual(len(eid2), 8)
        self.assertNotEqual(eid1, eid2)
    
    def test_message_handler_registration(self):
        """Test registering message handlers."""
        handler = MagicMock()
        self.node1.register_message_handler("test", handler)
        
        self.assertIn("test", self.node1._message_handlers)
        self.assertEqual(self.node1._message_handlers["test"], handler)
    
    def test_message_serialization(self):
        """Test message serialization and parsing."""
        message = MeshMessage(
            source_id=self.node1.device_id,
            destination_id=self.node2.device_id,
            message_type="test",
            payload=b"hello world",
            timestamp=1234567890.0,
            ttl=7
        )
        
        # Serialize
        serialized = self.node1._serialize_message(message)
        self.assertIsInstance(serialized, bytes)
        
        # Parse back
        parsed = self.node1._parse_message(serialized)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.source_id, message.source_id)
        self.assertEqual(parsed.destination_id, message.destination_id)
        self.assertEqual(parsed.message_type, message.message_type)
        self.assertEqual(parsed.payload, message.payload)
        self.assertEqual(parsed.timestamp, message.timestamp)
        self.assertEqual(parsed.ttl, message.ttl)
    
    def test_message_id_generation(self):
        """Test unique message ID generation."""
        message1 = MeshMessage(
            source_id=self.node1.device_id,
            destination_id=None,
            message_type="test",
            payload=b"hello",
            timestamp=1234567890.0,
            ttl=10
        )
        
        message2 = MeshMessage(
            source_id=self.node1.device_id,
            destination_id=None,
            message_type="test", 
            payload=b"world",
            timestamp=1234567890.0,
            ttl=10
        )
        
        id1 = self.node1._get_message_id(message1)
        id2 = self.node1._get_message_id(message2)
        
        self.assertNotEqual(id1, id2)  # Different payloads should have different IDs
    
    def test_stats_tracking(self):
        """Test statistics tracking."""
        initial_stats = self.node1.get_stats()
        
        expected_keys = [
            "messages_sent", "messages_received", "peers_discovered", 
            "id_rotations", "current_ephemeral_id", "known_peers", "connected_peers"
        ]
        
        for key in expected_keys:
            self.assertIn(key, initial_stats)
        
        self.assertEqual(initial_stats["messages_sent"], 0)
        self.assertEqual(initial_stats["messages_received"], 0)
        self.assertEqual(initial_stats["peers_discovered"], 0)


if __name__ == '__main__':
    # Run async tests
    if len(sys.argv) > 1 and sys.argv[1] == 'async':
        async def run_async_tests():
            # Here you would run async test methods
            pass
        asyncio.run(run_async_tests())
    else:
        unittest.main()