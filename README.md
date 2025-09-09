# CroweSense OffGrid Mesh

**BLE Transport with Rotating Ephemeral IDs (v2)**

A privacy-preserving Bluetooth Low Energy mesh networking system that uses rotating ephemeral identifiers to prevent device tracking while maintaining network connectivity.

## Features

- **Privacy-Preserving Discovery**: Rotating ephemeral IDs prevent long-term device tracking
- **BLE Mesh Transport**: Uses Bluetooth Low Energy for device-to-device communication  
- **Cryptographic Security**: HKDF-based ID derivation with shared secrets
- **Automatic Routing**: Multi-hop message forwarding with TTL-based loop prevention
- **Configurable Rotation**: Adjustable ID rotation intervals (default 5 minutes)
- **Peer Management**: Automatic discovery and connection management

## Architecture

The system consists of three main components:

1. **EphemeralIDManager**: Handles rotating ID generation and verification using HKDF
2. **BLETransport**: Manages BLE advertising, scanning, and GATT communication
3. **MeshNode**: Combines the above into a complete mesh networking node

## Quick Start

### Installation

```bash
# Install dependencies
pip install -r requirements.txt
```

### Basic Usage

```python
import asyncio
from offgrid_mesh import MeshNode
from offgrid_mesh.ephemeral_ids import generate_shared_secret

async def main():
    # Generate shared secret (distribute to all nodes)
    shared_secret = generate_shared_secret()
    
    # Create mesh node
    node = MeshNode(shared_secret=shared_secret)
    
    # Register message handler
    def handle_message(msg):
        print(f"Received: {msg.payload.decode()}")
    
    node.register_message_handler("chat", handle_message)
    
    # Start the node
    await node.start()
    
    # Send a message
    await node.send_message(
        destination_id=None,  # Broadcast
        message_type="chat",
        payload=b"Hello mesh!"
    )
    
    # Keep running
    await asyncio.sleep(3600)
    await node.stop()

asyncio.run(main())
```

### Running the Example

```bash
python examples/basic_mesh_node.py
```

## Privacy & Security

### Ephemeral ID Rotation

- IDs rotate every 5 minutes by default (configurable)
- Uses HKDF with SHA-256 for cryptographically secure derivation
- Each epoch generates a unique ID per device
- Clock skew tolerance (±2 epochs) for verification

### Mesh Security

- Shared secret required for all mesh participants
- Message integrity through ephemeral ID verification
- TTL-based loop prevention in routing
- No long-term identifying information in advertisements

## Protocol Details

### BLE Advertisement Format

```
Service UUID: 6ba7b810-9dad-11d1-80b4-00c04fd430c8
Service Data: [ephemeral_id(8)] [version(1)] [timestamp(4)]
```

### GATT Service

- **Service**: `6ba7b810-9dad-11d1-80b4-00c04fd430c8`
- **Ephemeral ID Characteristic**: `6ba7b811-9dad-11d1-80b4-00c04fd430c8` (Read)
- **Message Characteristic**: `6ba7b812-9dad-11d1-80b4-00c04fd430c8` (Write/Notify)
- **Status Characteristic**: `6ba7b813-9dad-11d1-80b4-00c04fd430c8` (Read)

### Message Format

Messages are JSON-encoded with the following structure:

```json
{
  "source_id": "hex_device_id", 
  "destination_id": "hex_device_id_or_null",
  "message_type": "string",
  "payload": "hex_encoded_payload",
  "timestamp": 1234567890.0,
  "ttl": 10
}
```

## Configuration

Key configuration parameters:

- `rotation_interval`: How often to rotate ephemeral IDs (seconds, default: 300)
- `scan_interval`: BLE scan frequency (seconds, default: 1.0)
- `id_length`: Length of ephemeral IDs (bytes, default: 8)

## Testing

Run the test suite:

```bash
python -m pytest tests/
# or
python -m unittest discover tests/
```

## Dependencies

- `bleak>=0.21.0` - Bluetooth Low Energy library
- `cryptography>=41.0.0` - Cryptographic functions
- `pycryptodome>=3.19.0` - Additional crypto support

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions welcome! Please ensure all code includes the SPDX license header:

```python
# SPDX-License-Identifier: MIT
# OffGrid Mesh — BLE Transport (discovery) with rotating ephemeral IDs (v2)
```