# Network Discovery System - Complete Workflow (With Junos Support)

## **Platform Support Matrix**

| Platform | Driver | CDP | LLDP | SSH Required | Status |
|----------|--------|-----|------|--------------|--------|
| Cisco IOS | `ios` | ✓ | ✓ | Yes | ✓ Supported |
| Cisco NX-OS | `nxos_ssh` | ✓ | ✓ | Yes | ✓ Supported |
| Arista EOS | `eos` | ✗ | ✓ | Yes | ✓ Supported |
| HP/Aruba ProCurve | `procurve` | ✗ | ✓ | Yes | ✓ Supported |
| **Juniper Junos** | **`junos`** | **✗** | **✓** | **Yes** | **✓ Supported** |

---

## **Phase 5: Neighbor Discovery (Updated with Junos)**

### **A. Platform-Specific Command Execution**

```python
# CDP Processing (Cisco only)
if platform not in ['eos', 'junos']:  # ← Junos excluded from CDP
    cdp_output = ssh_client(
        host=hostname,
        cmds="show cdp neighbor detail",
        prompt="#",
        ...
    )
    parsed_cdp = parser.find_best_template(cdp_output, 'show_cdp_neighbor')

# LLDP Processing (All platforms)
if platform == 'junos':
    # Junos-specific LLDP handling
    lldp_command = "show lldp neighbors detail"  # Note: "neighbors" not "neighbor"
    prompt = ">"  # Operational mode prompt
    prompt_count = 1
else:
    # Cisco/Arista/HP LLDP handling
    lldp_command = "show lldp neighbor detail"
    prompt = "#"
    prompt_count = 3

lldp_output = ssh_client(
    host=hostname,
    cmds=lldp_command,
    prompt=prompt,
    prompt_count=prompt_count,
    ...
)
```

### **B. Template Selection by Platform**

```python
# Select appropriate TextFSM template
if platform == 'eos':
    show_command = 'arista_eos_show_lldp_neighbors_detail'
elif platform == 'ios':
    show_command = 'cisco_ios_show_lldp_neighbors_detail'
elif platform == 'nxos_ssh':
    show_command = 'cisco_nxos_show_lldp_neighbors_detail'
elif platform == 'junos':
    show_command = 'juniper_junos_show_lldp_neighbors_detail'  # ← NEW
else:
    show_command = 'show_lldp_neighbor'

best_template, parsed_lldp, score = parser.find_best_template(
    lldp_output,
    show_command
)
```

### **C. Junos LLDP Output Example**

```
LLDP Neighbor Information:

Local Interface    Parent Interface    Chassis Id          Port info          System Name
ge-0/0/0           -                   00:1a:2b:3c:4d:5e   Gi0/1              CORE-SW-01
ae0                -                   00:1a:2b:3c:4d:5f   ae0                RTR-EDGE-02

Interface: ge-0/0/0
  Chassis ID: 00:1a:2b:3c:4d:5e
  Port ID: Gi0/1
  System name: CORE-SW-01.example.com
  System description: Cisco IOS Software, Version 15.2
  Management address: 192.168.1.10
```

### **D. Field Mapping Enhancement**

```python
def _map_neighbor_fields(self, entry: Dict, protocol: str) -> Dict:
    mapped = {
        'ip': '',
        'platform': 'unknown',
        'connections': []
    }

    # IP address extraction (enhanced for Junos)
    if 'MGMT_ADDRESS' in entry:
        mapped['ip'] = entry['MGMT_ADDRESS']
    elif 'INTERFACE_IP' in entry:  # ← Junos alternative
        mapped['ip'] = entry['INTERFACE_IP']

    # Platform detection
    if protocol == 'lldp':
        if 'NEIGHBOR_DESCRIPTION' in entry:
            mapped['platform'] = self._detect_platform_from_desc(
                entry['NEIGHBOR_DESCRIPTION']
            )
        elif 'CAPABILITIES' in entry:  # ← Junos uses capabilities
            mapped['platform'] = self._detect_platform_from_capabilities(
                entry['CAPABILITIES']
            )

        # Interface pairs (enhanced for Junos)
        local_port = entry.get('LOCAL_INTERFACE', '')
        remote_port = (entry.get('NEIGHBOR_INTERFACE', '') or
                      entry.get('NEIGHBOR_PORT_ID', '') or
                      entry.get('PORT_ID', ''))  # ← Junos variant

    return mapped
```

### **E. Platform Detection from Capabilities (New)**

```python
def _detect_platform_from_capabilities(self, capabilities: str) -> str:
    """Detect platform from LLDP capabilities string."""
    if not capabilities:
        return 'unknown'

    capabilities = capabilities.lower()

    # Juniper detection
    if any(term in capabilities for term in ['juniper', 'junos', 'jnpr']):
        return 'junos'

    # Generic detection
    if 'router' in capabilities and 'bridge' in capabilities:
        return 'junos'  # Likely Juniper

    return 'unknown'
```

---

## **Interface Normalization (Updated)**

### **Multi-Platform Support**

```python
class Platform(Enum):
    CISCO_IOS = auto()
    CISCO_NXOS = auto()
    ARISTA = auto()
    JUNIPER = auto()  # ← NEW
    UNKNOWN = auto()

# Junos Interface Patterns (added to INTERFACE_SPECS)
INTERFACE_SPECS = [
    # Juniper Gigabit Ethernet
    InterfaceSpec(r"^(?:ge[-_])(\d+/\d+/\d+(?:\.\d+)?)",
                  "ge-\\1", "ge-\\1",
                  [Platform.JUNIPER]),

    # Juniper 10GE
    InterfaceSpec(r"^(?:xe[-_])(\d+/\d+/\d+(?:\.\d+)?)",
                  "xe-\\1", "xe-\\1",
                  [Platform.JUNIPER]),

    # Juniper 25/40/100GE
    InterfaceSpec(r"^(?:et[-_])(\d+/\d+/\d+(?:\.\d+)?)",
                  "et-\\1", "et-\\1",
                  [Platform.JUNIPER]),

    # Juniper Aggregated Ethernet
    InterfaceSpec(r"^(?:ae)(\d+(?:\.\d+)?)",
                  "ae\\1", "ae\\1",
                  [Platform.JUNIPER]),

    # Juniper Management
    InterfaceSpec(r"^(?:fxp|em|me)(\d+)",
                  "fxp\\1", "fxp\\1",
                  [Platform.JUNIPER]),

    # ... Cisco/Arista patterns follow ...
]
```

### **Interface Normalization Examples**

| Platform | Raw Interface | Normalized | Type |
|----------|--------------|------------|------|
| Cisco IOS | GigabitEthernet1/0/1 | Gi1/0/1 | Gigabit |
| Cisco NX-OS | Ethernet1/1 | Eth1/1 | Ethernet |
| Arista EOS | Ethernet1 | Eth1 | Ethernet |
| **Juniper** | **ge-0/0/1** | **ge-0/0/1** | **Gigabit** |
| **Juniper** | **xe-1/2/3** | **xe-1/2/3** | **10 Gigabit** |
| **Juniper** | **ae0** | **ae0** | **Link Aggregation** |
| **Juniper** | **fxp0** | **fxp0** | **Management** |

---

## **Complete Discovery Example (Multi-Vendor)**

### **Scenario: Mixed Cisco/Juniper/Arista Network**

```
Topology:
  CORE-MX480 (Juniper)
    ├─ ge-0/0/1 → Gi0/48 (CORE-SW-3850, Cisco)
    ├─ ae0 → ae0 (EDGE-MX240, Juniper)
    └─ xe-0/0/5 → Eth1 (SPINE-7050, Arista)
```

### **Discovery Flow**

```python
# Step 1: Start with Juniper seed device
seed_device = DeviceInfo(
    hostname="192.168.1.100",  # CORE-MX480
    ip="192.168.1.100",
    username="admin",
    password="juniper123"
)

# Step 2: Platform Detection
platform = detect_platform(seed_device)
# Result: 'junos'

# Step 3: Get Device Capabilities
capabilities = get_device_capabilities(seed_device)
# {
#   'facts': {
#     'hostname': 'CORE-MX480',
#     'vendor': 'Juniper',
#     'model': 'mx480',
#     'os_version': 'JUNOS 20.4R1.12'
#   },
#   'neighbors': {
#     'lldp': {
#       'CORE-SW-3850': {
#         'ip': '192.168.1.50',
#         'platform': 'ios',
#         'connections': [['ge-0/0/1', 'Gi0/48']]
#       },
#       'EDGE-MX240': {
#         'ip': '192.168.1.101',
#         'platform': 'junos',
#         'connections': [['ae0', 'ae0']]
#       },
#       'SPINE-7050': {
#         'ip': '192.168.1.200',
#         'platform': 'eos',
#         'connections': [['xe-0/0/5', 'Eth1']]
#       }
#     }
#   }
# }

# Step 4: Queue Neighbors
for neighbor in neighbors:
    if not is_known(neighbor['ip']):
        queue.put(DeviceInfo(
            hostname=neighbor['ip'],
            ip=neighbor['ip'],
            platform=neighbor['platform']
        ))

# Step 5: Process Next Device (CORE-SW-3850, Cisco)
device = queue.get()
platform = detect_platform(device)  # 'ios'
# Now uses CDP + LLDP for this device

# Step 6: Continue until all devices discovered
```

### **Output JSON**

```json
{
  "CORE-MX480": {
    "node_details": {
      "ip": "192.168.1.100",
      "platform": "mx480"
    },
    "peers": {
      "CORE-SW-3850": {
        "ip": "192.168.1.50",
        "platform": "",
        "connections": [["ge-0/0/1", "Gi0/48"]]
      },
      "EDGE-MX240": {
        "ip": "192.168.1.101",
        "platform": "",
        "connections": [["ae0", "ae0"]]
      },
      "SPINE-7050": {
        "ip": "192.168.1.200",
        "platform": "",
        "connections": [["xe-0/0/5", "Eth1"]]
      }
    }
  },
  "CORE-SW-3850": {
    "node_details": {
      "ip": "192.168.1.50",
      "platform": "WS-C3850-48T"
    },
    "peers": {
      "CORE-MX480": {
        "ip": "192.168.1.100",
        "platform": "",
        "connections": [["Gi0/48", "ge-0/0/1"]]
      }
    }
  }
}
```

---

## **Platform-Specific Considerations**

### **Juniper Junos**

**Commands Used**:
- `show lldp neighbors detail` (not "neighbor")
- `show version`
- `show interfaces`

**Prompt Detection**:
- Operational mode: `user@hostname>`
- Configuration mode: `user@hostname#`
- Discovery uses: `>` prompt

**LLDP Requirements**:
```bash
# Check LLDP status
show lldp

# Enable LLDP on all interfaces
set protocols lldp interface all
commit

# Verify
show lldp neighbors
```

**Interface Naming**:
- Physical: `ge-0/0/0` (FPC/PIC/Port)
- 10GE: `xe-0/0/0`
- 25/40/100GE: `et-0/0/0`
- Link Aggregation: `ae0`, `ae1`
- Management: `fxp0` (M/MX), `em0` (EX)
- VLAN: `irb.100`, `vlan.200`

**Platform Detection**:
- Vendor: `'Juniper'`
- OS Version contains: `'JUNOS'`
- Model examples: `mx480`, `ex4300-48t`, `qfx5100-48s`

---

## **Complete Workflow Summary**

```
┌─────────────────────────────────────────────────────────┐
│             NETWORK DISCOVERY WORKFLOW                  │
└─────────────────────────────────────────────────────────┘

1. INITIALIZATION
   ├─ Create DiscoveryConfig
   ├─ Initialize NetworkDiscovery
   ├─ Create DriverDiscovery
   └─ Load TextFSM templates

2. SEED DEVICE
   └─ Add to queue

3. MAIN LOOP (for each device in queue)
   ├─ Check if visited → skip
   ├─ Check port 22 reachability
   │
   ├─ PLATFORM DETECTION
   │  ├─ Try: ios, junos, eos, procurve, nxos_ssh
   │  ├─ Validate facts:
   │  │  • Cisco IOS: 'Cisco' vendor, 'Version' in os
   │  │  • Juniper: 'Juniper' vendor, 'JUNOS' in os
   │  │  • Arista: 'Arista' vendor, 'EOS' in os
   │  └─ Cache result
   │
   ├─ GET CAPABILITIES
   │  ├─ Connect via NAPALM
   │  ├─ Get facts (hostname, model, version)
   │  ├─ Get interfaces
   │  └─ Get neighbors:
   │     ├─ CDP (if ios/nxos only)
   │     └─ LLDP (all platforms)
   │
   ├─ NEIGHBOR PROCESSING
   │  ├─ For each protocol (CDP/LLDP):
   │  │  ├─ Parse with TextFSM
   │  │  ├─ Extract fields
   │  │  ├─ Map to schema
   │  │  └─ Normalize interfaces
   │  │
   │  └─ Queue new devices
   │
   └─ Add to network_map

4. DATA TRANSFORMATION
   ├─ Transform to JSON schema
   ├─ Enrich peer data
   └─ Normalize hostnames

5. OUTPUT GENERATION
   ├─ JSON (.json)
   ├─ GraphML (.graphml)
   ├─ Draw.io (.drawio)
   └─ SVG (.svg)

END
```

---

## **Quick Reference: Platform Differences**

| Feature | Cisco IOS | Juniper Junos | Arista EOS |
|---------|-----------|---------------|------------|
| **CDP** | ✓ Yes | ✗ No | ✗ No |
| **LLDP** | ✓ Yes | ✓ Yes | ✓ Yes |
| **LLDP Command** | `show lldp neighbor detail` | `show lldp neighbors detail` | `show lldp neighbor detail` |
| **Prompt** | `#` | `>` | `#` |
| **Interface Format** | `Gi1/0/1` | `ge-0/0/1` | `Eth1` |
| **Vendor** | Cisco | Juniper | Arista |
| **OS Identifier** | Version | JUNOS | EOS |

---

## **Testing Multi-Vendor Networks**

```python
# Test configuration for mixed environment
config = DiscoveryConfig(
    seed_ip="192.168.1.1",  # Any platform
    username="netadmin",
    password="secret",
    max_devices=100,
    exclude_string="phone,sep,ap",  # Exclude non-network devices
    output_dir=Path("./multi_vendor_map"),
    map_name="production_network"
)

discovery = NetworkDiscovery(config)

# Enable detailed logging
def log_callback(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}")

discovery.set_log_callback(log_callback)

# Run discovery
network_map = discovery.crawl()

# Results will include all supported platforms:
# - Cisco IOS/NX-OS devices
# - Juniper Junos devices
# - Arista EOS devices
# - HP/Aruba ProCurve devices
```

---

This workflow now fully supports **Juniper Junos** devices alongside Cisco, Arista, and HP platforms, providing comprehensive multi-vendor network discovery capabilities.
