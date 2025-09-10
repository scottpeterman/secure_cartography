# Network Discovery Logic Flow

## Overview
Secure Cartography performs automated network discovery using SSH connections to network devices, leveraging CDP/LLDP protocols to map network topologies. This document outlines the complete flow from initial configuration to final diagram generation.

## CLI Entry Point (`sc.py`)

### Configuration Processing
The CLI tool processes configuration from multiple sources with the following precedence:
1. **Defaults** - Base configuration values
2. **YAML Config** - Configuration file (if provided)
3. **CLI Arguments** - Command-line parameters
4. **Environment Variables** - Highest precedence (SC_USERNAME, SC_PASSWORD, etc.)

```bash
# Example CLI usage
sc --config network.yaml --seed-ip 192.168.1.1 --verbose
```

### Configuration Validation
Before discovery begins, the system validates required parameters:
- `seed_ip` - Starting device IP address
- `username` - Primary authentication credentials
- `password` - Primary authentication credentials

## Discovery Process (`NetworkDiscovery` class)

### Phase 1: Initialization
```python
# Create discovery configuration
config = DiscoveryConfig(**filtered_config)
discovery = NetworkDiscovery(config)
```

Key components initialized:
- **Queue System** - Device processing queue
- **Tracking Sets** - Visited IPs, failed devices, unreachable hosts
- **Logger** - Progress and debug logging
- **Driver Discovery** - Multi-vendor device support

### Phase 2: Seed Device Processing
```python
# Initialize with seed device
seed_device = DeviceInfo(
    hostname=config.seed_ip,
    ip=config.seed_ip,
    username=config.username,
    password=config.password,
    timeout=config.timeout
)
queue.put(seed_device)
```

### Phase 3: Discovery Loop
The main discovery loop processes devices from the queue until completion:

#### 3.1 Device Dequeue and Validation
```python
while not queue.empty() and devices_discovered < max_devices:
    current_device = queue.get()
    
    # Skip if already processed
    if _is_visited(current_device):
        continue
        
    # Apply exclusion patterns
    if matches_exclude_pattern(current_device.hostname):
        continue
```

#### 3.2 Reachability Check
```python
# Port 22 (SSH) connectivity test
if not _check_port_open(current_device.hostname):
    failed_devices.add(current_device.hostname)
    continue
```

#### 3.3 Device Capabilities Discovery
```python
# Get device information using appropriate driver
capabilities = driver_discovery.get_device_capabilities(
    current_device, 
    config=config
)
```

The system supports multiple vendor platforms:
- **Cisco IOS** - Uses CDP primarily, LLDP as fallback
- **Cisco NX-OS** - LLDP-based discovery
- **Arista EOS** - LLDP-based discovery
- **HP/Aruba ProCurve** - LLDP-based discovery

#### 3.4 Enhanced CDP Processing (IOS-specific)
For Cisco IOS devices, the system performs enhanced CDP parsing:
```python
if capabilities['platform'] == "ios":
    get_ios_cdp(current_device, capabilities)
```

This uses TextFSM templates to parse `show cdp neighbors detail` output for more accurate neighbor information than NAPALM provides.

#### 3.5 Device Processing and Neighbor Discovery
```python
# Create NetworkDevice object
device = _process_device(current_device, capabilities)

# Process discovered neighbors
neighbors = capabilities.get('neighbors', {})
_process_neighbors(device, neighbors)

# Add to network map
network_map[device.hostname] = device
```

### Phase 4: Neighbor Processing

#### 4.1 Protocol Processing
For each discovered neighbor, the system processes both CDP and LLDP data:
```python
for protocol in ['cdp', 'lldp']:
    protocol_neighbors = neighbors.get(protocol, {})
    for neighbor_id, data in protocol_neighbors.items():
        # Normalize hostname
        normalized_neighbor_id = _normalize_hostname(neighbor_id)
        
        # Process connections
        for connection in data.get('connections', []):
            local_port = InterfaceNormalizer.normalize(connection[0])
            remote_port = InterfaceNormalizer.normalize(connection[1])
```

#### 4.2 Connection Mapping
Each connection is stored with:
- **Local Port** - Normalized interface name (e.g., "Gi0/1")
- **Remote Port** - Normalized interface name on neighbor
- **Neighbor IP** - Management IP address
- **Platform** - Device platform type
- **Protocol** - Discovery protocol (CDP/LLDP)

#### 4.3 Queue Management
New devices are queued for discovery if:
- Device has a valid IP address
- Device hasn't been visited or queued
- Device doesn't match exclusion patterns
- Maximum device limit hasn't been reached

```python
if neighbor_ip and not _is_known_device(neighbor_ip):
    neighbor_device = DeviceInfo(
        hostname=neighbor_ip,
        ip=neighbor_ip,
        username=config.username,
        password=config.password,
        timeout=config.timeout
    )
    queue.put(neighbor_device)
```

### Phase 5: Data Transformation

#### 5.1 NetworkDevice to Map Format
Raw device objects are transformed into the standard mapping format:
```python
transformed_map = transform_map(network_map)
# Result format:
{
    "device_hostname": {
        "node_details": {
            "ip": "192.168.1.1",
            "platform": "ios"
        },
        "peers": {
            "neighbor_hostname": {
                "ip": "192.168.1.2",
                "platform": "eos",
                "connections": [["Gi0/1", "Eth1"]]
            }
        }
    }
}
```

#### 5.2 Data Enrichment
The system enriches peer data by cross-referencing discovered devices:
```python
enriched_map = enrich_peer_data(transformed_map)
```

This updates peer platform information using actual discovered device data when available.

#### 5.3 Hostname Normalization
Final hostname normalization ensures consistency:
- Removes domain suffixes (e.g., "router.domain.com" → "router")
- Handles special cases (Nexus devices reporting "Kernel" hostname)
- Merges duplicate entries

## Diagram Generation

### Phase 6: File Output Generation

#### 6.1 JSON Map Export
```python
# Save primary network map
map_path = output_dir / f"{map_name}.json"
with open(map_path, "w") as fh:
    json.dump(normalized_map, indent=2, fp=fh)
```

#### 6.2 Multiple Format Generation
The system generates multiple output formats:

**GraphML (.graphml)**
- Compatible with yEd Graph Editor
- Supports advanced layout algorithms
- Professional network diagram capabilities

**Draw.io (.drawio)**
- Web-based collaborative editing
- Multiple export formats
- Custom network device stencils

**SVG (.svg)**
- Scalable vector graphics
- Direct preview in applications
- Supports both light and dark themes

```python
create_network_diagrams(normalized_map, output_dir, map_name, layout_algo)
```

#### 6.3 Layout Algorithms
Multiple layout options are supported:
- **Kamada-Kawai (kk)** - Force-directed layout for general topologies
- **Spring (rt)** - Real-time spring layout
- **Circular** - Circular arrangement for ring topologies

### Phase 7: Visualization Generation

#### 7.1 NetworkX Graph Creation
```python
# Create graph from network map
G = nx.Graph()
for node, data in map_data.items():
    G.add_node(node, ip=data['node_details']['ip'])
    for peer, peer_data in data['peers'].items():
        if peer in map_data:
            G.add_edge(node, peer, connection=connection_label)
```

#### 7.2 SVG Rendering
The system creates publication-quality SVG diagrams with:
- **Balloon Layout** - Hierarchical positioning with core devices centered
- **Interface Labels** - Connection information on edges
- **Theme Support** - Dark/light mode compatibility
- **Device Icons** - Vendor-specific visual representations

## Error Handling and Recovery

### Timeout Management
- **Connection Timeouts** - Individual device connection limits
- **Global Timeouts** - Overall discovery process limits
- **Retry Logic** - Platform detection fallbacks (e.g., IOS → NX-OS)

### Platform Detection Fallbacks
```python
# Handle Nexus devices misidentified as IOS
if discovered_hostname in ['Kernel', 'Unknown']:
    # Retry with nxos_ssh platform
    alternate_capabilities = get_device_capabilities(
        alternate_device_with_nxos_platform
    )
```

### Progress Tracking
Real-time statistics are maintained:
- **Devices Discovered** - Successfully processed devices
- **Devices Failed** - Connection or processing failures
- **Devices Queued** - Pending discovery queue size
- **Unreachable Hosts** - Network connectivity failures

## Output Structure

### File Organization
```
output_directory/
├── map_name.json         # Primary network map data
├── map_name.graphml      # yEd-compatible format
├── map_name.drawio       # Draw.io format
└── map_name.svg          # SVG visualization
```

### Data Persistence
- **Credentials** - Securely encrypted and stored
- **Discovery State** - Progress and statistics tracking
- **Debug Information** - Detailed logs for troubleshooting (optional)

## Configuration Examples

### YAML Configuration
```yaml
seed_ip: 192.168.1.1
max_devices: 500
output_dir: "./network_maps"
verbose: true
map_name: production_network
layout: "kk"
domain: 'company.local'
exclude: 'test-,dev-,phone'
timeout: 60
```

### Environment Variables
```bash
export SC_USERNAME=netadmin
export SC_PASSWORD=secure_password
export SC_ALT_USERNAME=readonly
export SC_ALT_PASSWORD=readonly_pass
```

### CLI Execution
```bash
# Full CLI specification
sc --config network.yaml \
   --seed-ip 10.1.1.1 \
   --max-devices 100 \
   --exclude-string "sep,phone" \
   --output-dir /tmp/maps \
   --verbose

# Environment variable approach
SC_USERNAME=admin SC_PASSWORD=pass sc --config base.yaml
```

This comprehensive discovery process enables automated mapping of complex multi-vendor network environments while maintaining security through encrypted credential storage and providing multiple output formats for different use cases.