# Quick Start Guide

## Installation

```bash
# Clone the repository
git clone https://github.com/MichaelCrowe11/crowe-sense.git
cd crowe-sense

# Install dependencies  
pip install -r requirements.txt

# Optional: Install in development mode
pip install -e .
```

## Basic Usage

### 1. Generate Keys

First, generate a shared secret for your mesh network:

```bash
python -m src.offgrid_mesh.cli generate-keys --save
```

This creates a device ID and shared secret. **The shared secret must be the same on all nodes in your mesh network.**

### 2. Run a Node

Start a mesh node:

```bash
python -m src.offgrid_mesh.cli run-node --name "MyMeshNode"
```

Or run the example directly:

```bash
python examples/basic_mesh_node.py  
```

### 3. Multiple Nodes

To create a mesh network, run multiple nodes with the **same shared secret** but **different device IDs**:

```bash
# Terminal 1
python -m src.offgrid_mesh.cli run-node --name "Node1" --shared-secret YOUR_HEX_SECRET

# Terminal 2  
python -m src.offgrid_mesh.cli run-node --name "Node2" --shared-secret YOUR_HEX_SECRET
```

## Programming Interface

### Simple Example

```python
import asyncio
from offgrid_mesh import MeshNode
from offgrid_mesh.ephemeral_ids import generate_shared_secret

async def main():
    # Create shared secret (same for all nodes)
    shared_secret = generate_shared_secret()
    
    # Create node
    node = MeshNode(shared_secret=shared_secret)
    
    # Handle incoming messages
    def on_message(msg):
        print(f"Got message: {msg.payload.decode()}")
    
    node.register_message_handler("chat", on_message)
    
    # Start the node
    await node.start()
    
    # Send a broadcast message
    await node.send_message(
        destination_id=None,  # None = broadcast
        message_type="chat", 
        payload=b"Hello mesh!"
    )
    
    # Keep running
    await asyncio.sleep(3600)
    await node.stop()

asyncio.run(main())
```

### Advanced Configuration

```python
node = MeshNode(
    shared_secret=shared_secret,
    device_name="CustomNode",
    rotation_interval=120,  # 2 minute ID rotation
    scan_interval=0.5       # Scan twice per second
)
```

## Configuration File

Create `~/.config/offgrid-mesh/config.json`:

```json
{
  "shared_secret": "your_hex_secret_here",
  "device_id": "your_device_id_here", 
  "mesh_settings": {
    "rotation_interval": 300,
    "device_name": "MyNode"
  }
}
```

## Message Types

The system supports different message types:

- **chat**: Text messages between users
- **ping**: Network connectivity testing
- **pong**: Response to ping messages  
- **custom**: Your own message types

```python
# Register handler for custom messages
def handle_sensor_data(msg):
    data = json.loads(msg.payload)
    print(f"Sensor reading: {data}")

node.register_message_handler("sensor", handle_sensor_data)

# Send sensor data
sensor_data = {"temperature": 22.5, "humidity": 60}
await node.send_message(
    destination_id=None,
    message_type="sensor",
    payload=json.dumps(sensor_data).encode()
)
```

## Privacy Features

### Ephemeral ID Rotation

- IDs change every 5 minutes by default
- External observers cannot track devices over time
- Mesh participants can still route messages correctly

### Clock Synchronization

For best privacy, ensure system clocks are synchronized:

```bash
# Ubuntu/Debian
sudo systemctl enable systemd-timesyncd
sudo systemctl start systemd-timesyncd

# Or use NTP
sudo apt install ntp
```

## Troubleshooting

### Bluetooth Issues

```bash
# Check Bluetooth status
sudo systemctl status bluetooth

# Reset Bluetooth adapter
sudo hciconfig hci0 down && sudo hciconfig hci0 up
```

### No Peers Found

1. Verify same shared secret on all nodes
2. Check Bluetooth Low Energy support
3. Ensure nodes are within BLE range (~10-30 meters)
4. Check for firewall/permission issues

### Permission Errors

```bash
# Add user to bluetooth group
sudo usermod -a -G bluetooth $USER

# Set capabilities for Python (alternative to running as root)
sudo setcap 'cap_net_raw,cap_net_admin+eip' $(which python3)
```

## Performance Tips

- **Scan Interval**: Lower values find peers faster but use more battery
- **Rotation Interval**: Shorter intervals provide better privacy but more overhead
- **Message TTL**: Adjust based on network size (larger networks need higher TTL)

## Development

### Running Tests

```bash
python -m unittest discover tests/
```

### Code Style

```bash
pip install black flake8
black src/ tests/
flake8 src/ tests/
```