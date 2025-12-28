# SecureCartography NG: Discovery Engine Architecture

## Technical Design Document

**Author:** Scott Peterman  
**Version:** 1.0  
**Date:** December 2025

---

## Executive Summary

SecureCartography NG (SCNG) implements a hybrid network discovery engine that combines SNMP-based collection with SSH CLI fallback to produce accurate, vendor-agnostic network topology maps. The system's key innovation is its **two-pass interface resolution** for LLDP data, which correctly handles the distinction between LLDP port numbering and SNMP ifIndex values—a subtle but critical difference that causes topology inaccuracies in naive implementations.

The architecture prioritizes:
- **SNMP-first discovery** for complete device metadata (sysDescr, interfaces, ARP)
- **SSH fallback** using TextFSM template matching for devices without SNMP access
- **Bidirectional validation** to ensure only confirmed links appear in the final topology
- **Unified data models** that normalize CDP and LLDP into a common Neighbor format

---

## 1. Architecture Overview

### 1.1 Component Hierarchy

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DiscoveryEngine                               │
│  (engine.py - Orchestration, credential management, crawl logic)    │
└────────────────────────────┬────────────────────────────────────────┘
                             │
           ┌─────────────────┴─────────────────┐
           ▼                                   ▼
┌─────────────────────┐              ┌─────────────────────┐
│   SNMP Collection   │              │    SSH Fallback     │
│                     │              │                     │
│  • walker.py        │              │  • SSHCollector     │
│  • lldp.py          │              │  • parsers.py       │
│  • cdp.py           │              │  • tfsm_fire        │
│  • interfaces.py    │              │                     │
└─────────┬───────────┘              └─────────┬───────────┘
          │                                    │
          └─────────────┬──────────────────────┘
                        ▼
              ┌─────────────────────┐
              │    Data Models      │
              │    (models.py)      │
              │                     │
              │  • Device           │
              │  • Neighbor         │
              │  • Interface        │
              └─────────┬───────────┘
                        │
                        ▼
              ┌─────────────────────┐
              │  Topology Builder   │
              │  (engine.py)        │
              │                     │
              │  • Bidirectional    │
              │    Validation       │
              │  • Interface        │
              │    Normalization    │
              └─────────────────────┘
```

### 1.2 Discovery Flow

```
1. Seed device(s) provided
         │
         ▼
2. Credential discovery
   ├── Try SNMP credentials (v2c/v3)
   │   └── Test with sysName.0 query
   └── Fall back to SSH if SNMP fails
         │
         ▼
3. Device collection
   ├── SNMP Path:
   │   ├── System info (sysDescr, sysName, etc.)
   │   ├── Interface table (ifName, ifIndex mapping)
   │   ├── ARP table (MAC → IP resolution)
   │   ├── CDP neighbors (Cisco only)
   │   └── LLDP neighbors (all vendors)
   │
   └── SSH Path:
       ├── Vendor detection via pagination probes
       ├── CLI command execution
       └── TextFSM parsing for neighbor extraction
         │
         ▼
4. Neighbor queuing
   └── Queue discovered neighbors for next depth
         │
         ▼
5. Repeat until max_depth reached
         │
         ▼
6. Topology generation with bidirectional validation
```

---

## 2. SNMP Collection Layer

### 2.1 The SNMPWalker (walker.py)

The SNMPWalker provides efficient async GETBULK operations for table walks:

```python
class SNMPWalker:
    """
    Async SNMP table walker using pysnmp.hlapi.v3arch.asyncio.
    
    Key features:
    - Automatic table boundary detection (OID prefix matching)
    - Configurable bulk_size (default 25 OIDs per request)
    - Iteration limits to prevent infinite loops
    - Support for both numeric OIDs and MIB-resolved ObjectIdentity
    """
```

**Algorithm: Table Walk**

```
Input: base_oid, target_ip, auth
Output: List[(oid_string, value)]

1. Initialize results = [], last_oid = base_oid
2. For iteration in range(max_iterations):
   a. Execute GETBULK(last_oid, max_repetitions=bulk_size)
   b. For each var_bind in response:
      - If oid.startswith(base_oid): 
        - Append to results
        - Update last_oid
      - Else: table boundary reached, break
   c. If var_binds < bulk_size: end of data, break
3. Return results
```

### 2.2 LLDP Collection: The Two-Pass Solution (lldp.py)

**The Problem:**

LLDP uses its own port numbering scheme (`lldpLocPortNum`) which is *not* necessarily the same as SNMP's `ifIndex`. A naive implementation that assumes `lldpRemLocalPortNum == ifIndex` produces incorrect local interface names:

```
Device A reports: lldpRemLocalPortNum=50 → neighbor on "port 50"
Naive lookup:     ifIndex 50 = Gi1/50
Actual interface: LLDP port 50 = Te1/49 (different!)
```

This causes bidirectional validation to fail because Device A claims `Te1/49 → peer` but Device B claims `peer → Gi1/50`. The connection appears unconfirmed and gets dropped.

**The Solution: Two-Pass Interface Resolution**

```
PASS 1: Build lldpLocPortTable mapping
        lldpLocPortNum → interface name
        
        Walk OID 1.0.8802.1.1.2.1.3.7.1.3 (lldpLocPortId)
        Extract: port_num from index, interface_name from value
        Result: {50: "Te1/49", 51: "Te1/50", ...}

PASS 2: Query lldpRemTable for neighbors
        Use lldpLocPortTable to resolve local interfaces
        Fall back to ifIndex only if lldpLocPortTable empty
```

**Implementation (lldp.py lines 36-88, 133-143):**

```python
async def get_lldp_local_port_map(target, auth, walker, ...):
    """
    Build mapping of lldpLocPortNum -> interface name.
    
    This is CRITICAL because lldpLocPortNum in the remote table
    is NOT necessarily the same as ifIndex!
    """
    port_map: Dict[int, str] = {}
    
    # Walk lldpLocPortId (column 3)
    # OID: 1.0.8802.1.1.2.1.3.7.1.3.<lldpLocPortNum>
    results = await walker.walk(target, LLDP_LOC_PORT_ID, auth)
    
    for oid, value in results:
        parts = oid.split('.')
        local_port_num = int(parts[11])  # Index position
        port_id = decode_string(value)
        port_map[local_port_num] = port_id
    
    return port_map


async def get_lldp_neighbors(target, auth, interface_table, ...):
    # FIRST: Get the local port mapping
    lldp_port_map = await get_lldp_local_port_map(target, auth, walker)
    
    # ... walk lldpRemTable ...
    
    # Resolve local interface name
    local_port_num = data.get('local_port_num', 0)
    
    # Try lldpLocPortTable first (correct way)
    if local_port_num in lldp_port_map:
        local_interface = lldp_port_map[local_port_num]
    # Fall back to ifIndex (may not always match!)
    elif interface_table:
        local_interface = resolve_interface_name(local_port_num, interface_table)
```

### 2.3 LLDP Data Structures

LLDP uses a three-part table index: `timeMark.localPortNum.remIndex`

```
OID Structure:
1.0.8802.1.1.2.1.4.1.1.<column>.<timeMark>.<localPortNum>.<remIndex>
     │         │   │      │         │           │            │
     │         │   │      │         │           │            └── Remote entry index
     │         │   │      │         │           └── Local port number (NOT ifIndex!)
     │         │   │      │         └── Time mark (usually 0)
     │         │   │      └── Column number (4-12)
     │         │   └── lldpRemEntry
     │         └── lldpRemTable
     └── LLDP-MIB base
```

**Column Mapping:**

| Column | Field | Notes |
|--------|-------|-------|
| 4 | chassis_id_subtype | Integer (1-7) |
| 5 | chassis_id | Decoded based on subtype |
| 6 | port_id_subtype | Integer (1-7) |
| 7 | port_id | Decoded based on subtype |
| 8 | port_description | String |
| 9 | system_name | String - primary device identifier |
| 10 | system_description | Platform info |
| 11 | capabilities_supported | Bitmap |
| 12 | capabilities_enabled | Bitmap |

### 2.4 Subtype Decoding

LLDP chassis_id and port_id require subtype-aware decoding:

```python
# Chassis ID Subtypes
1 = Component (string)
2 = Interface Alias (string)
3 = Port Component (string)
4 = MAC Address (hex → XX:XX:XX:XX:XX:XX)
5 = Network Address (typically IPv4)
6 = Interface Name (string)
7 = Locally Assigned (string)

# Port ID Subtypes
1 = Interface Alias
2 = Port Component
3 = MAC Address
4 = Network Address
5 = Interface Name (most common)
6 = Agent Circuit ID
7 = Locally Assigned
```

---

## 3. SSH Fallback Layer

### 3.1 When SSH Fallback Triggers

```python
# engine.py credential selection logic
async def _get_working_credential(self, target):
    # Try SNMP first (preferred - full discovery capability)
    for snmp_cred in snmp_credentials:
        auth = self._build_auth(snmp_cred)
        sys_name = await get_sys_name(target, auth)
        if sys_name:  # SNMP works
            return (auth, cred_name, 'snmp')
    
    # Fallback to SSH
    for ssh_cred in ssh_credentials:
        if await self._test_ssh_credential(target, ssh_cred):
            return (ssh_cred, cred_name, 'ssh')
    
    return None
```

### 3.2 SSHCollector Architecture

The SSHCollector handles:
1. **Vendor detection** via pagination command probing
2. **CLI command execution** with vendor-specific commands
3. **TextFSM parsing** for structured data extraction

```python
class SSHCollector:
    """
    SSH-based neighbor collection when SNMP unavailable.
    
    Vendor Detection Strategy:
    1. Connect and find prompt
    2. Try vendor-specific pagination disable commands
    3. First command that succeeds identifies vendor
    4. For Cisco success, further refine via "show version"
       (Arista returns EOS version, true Cisco returns IOS)
    """
```

**Vendor Probe Commands:**

| Vendor | Pagination Disable Command |
|--------|---------------------------|
| Cisco/Arista | `terminal length 0` |
| Juniper | `set cli screen-length 0` |
| Palo Alto | `set cli pager off` |

### 3.3 TextFSM Integration (parsers.py)

The TextFSMParser uses `tfsm_fire.TextFSMAutoEngine` for automatic template selection:

```python
class TextFSMParser:
    """
    Uses tfsm_fire for template-based CLI output parsing.
    
    Workflow:
    1. Clean raw output (remove preamble, command echo, trailing prompts)
    2. Query template database with filter string
    3. Auto-select best matching template based on parse score
    4. Return structured records
    """
    
    def parse(self, output, filter_string):
        # Clean the output
        cleaned = OutputCleaner.clean(output)
        
        # Find best matching template
        template, parsed_data, score = self._engine.find_best_template(
            cleaned, filter_string
        )
        
        return ParseResult(
            success=bool(parsed_data and score > 0),
            template_name=template,
            records=parsed_data,
            score=score
        )
```

**Output Cleaning (OutputCleaner):**

```python
# Patterns removed from raw CLI output:
PREAMBLE_PATTERNS = [
    r'^terminal\s+(length|width)',      # Cisco/Arista
    r'^pagination\s+disabled',          # Various
    r'^screen-length\s+disable',        # Huawei
    r'^set cli screen-length',          # Juniper
]

COMMAND_ECHO_PATTERN = r'^[\w\-\.@]+[\#\>\$\)]\s*(show|display|get)\s+'
TRAILING_PROMPT_PATTERN = r'^[\w\-\.@]+[\#\>\$\)]\s*$'
```

### 3.4 Template Selection via tfsm_fire

The `tfsm_fire` engine provides automatic template matching:

```
Input:  CLI output + filter string (e.g., "juniper_junos_lldp_neighbors")
Process:
  1. Query tfsm_templates.db for templates matching filter
  2. Parse output against each candidate template
  3. Score based on field population and record count
  4. Return highest-scoring result

Output: (template_name, parsed_records, score)
```

---

## 4. Data Model Layer (models.py)

### 4.1 Neighbor Normalization

The `Neighbor` dataclass normalizes CDP and LLDP into a unified format:

```python
@dataclass
class Neighbor:
    # Local side
    local_interface: str
    local_interface_index: Optional[int] = None
    
    # Remote side (normalized from CDP or LLDP)
    remote_device: str       # CDP: device_id | LLDP: system_name or chassis_id
    remote_interface: str    # CDP: device_port | LLDP: port_id
    remote_ip: Optional[str] # CDP: ip_address | LLDP: management_address
    
    # Protocol tracking
    protocol: NeighborProtocol  # CDP or LLDP
    chassis_id: Optional[str]   # LLDP-specific

    @classmethod
    def from_cdp(cls, local_interface, device_id, remote_port, ip_address, ...):
        """Factory for CDP data."""
        
    @classmethod
    def from_lldp(cls, local_interface, system_name, port_id, management_address, ...):
        """Factory for LLDP data - uses system_name or chassis_id for remote_device."""
```

### 4.2 Device Aggregation

```python
@dataclass
class Device:
    hostname: str
    ip_address: str
    
    # SNMP system info
    sys_name: Optional[str]
    sys_descr: Optional[str]
    vendor: DeviceVendor
    
    # Collections
    interfaces: List[Interface]
    neighbors: List[Neighbor]      # Combined CDP + LLDP
    arp_table: Dict[str, str]      # MAC → IP for LLDP resolution
    
    # Discovery metadata
    discovered_via: DiscoveryProtocol  # SNMP or SSH
    depth: int                          # Crawl depth from seed
    
    @property
    def cdp_neighbors(self) -> List[Neighbor]:
        return [n for n in self.neighbors if n.protocol == NeighborProtocol.CDP]
    
    @property
    def lldp_neighbors(self) -> List[Neighbor]:
        return [n for n in self.neighbors if n.protocol == NeighborProtocol.LLDP]
```

---

## 5. Topology Generation

### 5.1 Bidirectional Validation Algorithm

The topology builder only includes connections that pass validation:

```python
def _generate_topology_map(self, devices):
    """
    Validation Rules:
    1. If both devices discovered: require bidirectional confirmation
    2. If only one device discovered (leaf/edge): trust unidirectional claim
    
    This eliminates:
    - Spurious connections from stale LLDP data
    - Misconfigured or one-way links
    - Interface mapping errors (fixed by two-pass LLDP)
    """
```

**Algorithm:**

```
PASS 1: Collect all neighbor claims
        Key: (canonical_device, normalized_local_interface)
        Value: [(canonical_peer, normalized_remote_interface, neighbor_obj), ...]

PASS 2: Validate and build topology
        For each device:
          For each neighbor claim:
            peer_discovered = check if peer in discovered_devices
            
            If peer_discovered:
              # Require reverse claim
              reverse_key = (peer, remote_interface)
              if reverse_key claims (device, local_interface):
                INCLUDE connection
              else:
                DROP as unconfirmed
            Else:
              # Leaf node - trust unidirectional
              INCLUDE connection
```

### 5.2 Interface Normalization

Consistent interface naming is critical for bidirectional matching:

```python
def _normalize_interface(self, interface: str) -> str:
    """
    Normalizations applied:
    
    Cisco Long → Short:
      GigabitEthernet0/1     → Gi0/1
      TenGigabitEthernet1/1  → Te1/1
      HundredGigE0/0/0       → Hu0/0/0
      Port-channel1          → Po1
      
    Arista:
      Et1/1                  → Eth1/1
      
    Juniper:
      xe-0/0/0.0             → xe-0/0/0  (strip default .0 unit)
      
    Case normalization:
      port-channel1          → Po1
      VLAN666                → Vl666
    """
```

### 5.3 Output Format

```json
{
  "device_name": {
    "node_details": {
      "ip": "10.1.1.1",
      "platform": "Arista vEOS-lab EOS 4.33.1F"
    },
    "peers": {
      "peer_device": {
        "ip": "10.1.1.2",
        "platform": "Cisco IOSv IOS 15.6(2)T",
        "connections": [
          ["Eth1/1", "Gi0/1"],
          ["Eth1/2", "Gi0/2"]
        ]
      }
    }
  }
}
```

---

## 6. Crawl Engine

### 6.1 Breadth-First Discovery

```python
async def crawl(self, seeds, max_depth, domains, ...):
    """
    Breadth-first network discovery from seed devices.
    
    Depth 0: Seed devices
    Depth 1: Neighbors of seeds
    Depth 2: Neighbors of depth 1
    ...
    Depth N: Stop when max_depth reached
    """
    
    current_batch = [{'target': s, 'depth': 0} for s in seeds]
    processed = set()
    
    while current_batch:
        next_batch = []
        depth = current_batch[0]['depth']
        
        for item in current_batch:
            target = item['target']
            
            if target in processed:
                continue
                
            device = await self.discover_device(target, depth=depth, ...)
            processed.add(target)
            processed.add(device.ip_address)
            processed.add(device.hostname)
            
            if device.discovery_success and depth < max_depth:
                for neighbor in device.neighbors:
                    next_target = neighbor.remote_device or neighbor.remote_ip
                    
                    # Filter MAC addresses
                    if is_mac_address(next_target):
                        continue
                    
                    # Skip already processed
                    if next_target in processed:
                        continue
                    
                    next_batch.append({
                        'target': next_target,
                        'depth': depth + 1
                    })
        
        current_batch = next_batch
```

### 6.2 MAC Address Filtering

Prevents chassis_id (MAC) from leaking through as discovery targets:

```python
MAC_PATTERN = re.compile(
    r'^([0-9a-fA-F]{2}[:\-.]?){5}[0-9a-fA-F]{2}$|'  # Standard: 00:11:22:33:44:55
    r'^([0-9a-fA-F]{4}\.){2}[0-9a-fA-F]{4}$'         # Cisco: 0011.2233.4455
)

def is_mac_address(value: str) -> bool:
    return bool(MAC_PATTERN.match(value))
```

---

## 7. Key Design Decisions

### 7.1 Why SNMP First?

| Capability | SNMP | SSH |
|------------|------|-----|
| System info (sysDescr, sysName) | ✓ | Limited |
| Interface table with ifIndex | ✓ | ✗ |
| ARP table for IP resolution | ✓ | Vendor-specific |
| CDP neighbors | ✓ | ✓ |
| LLDP neighbors | ✓ | ✓ |
| Vendor-agnostic | ✓ | Requires templates |
| Speed | Fast (bulk) | Slower (sequential) |

SNMP provides richer metadata and is vendor-agnostic. SSH is reserved for devices where SNMP is unavailable or blocked.

### 7.2 Why Two-Pass LLDP?

The `lldpLocPortNum` vs `ifIndex` distinction is subtle but critical:

- **lldpLocPortNum**: LLDP's internal port numbering, determined by the LLDP agent
- **ifIndex**: SNMP's interface index, determined by the IF-MIB implementation

These *often* match but are not guaranteed to:
- Virtual ports may have different numbering
- Port-channels may be numbered differently
- Some vendors intentionally use different schemes

The two-pass approach queries `lldpLocPortTable` first to get authoritative port→interface mappings, eliminating this class of errors entirely.

### 7.3 Why Bidirectional Validation?

Unidirectional links can appear in discovery data due to:
- Stale LLDP cache (neighbor removed but data persists)
- Misconfigured LLDP (one direction disabled)
- Transient network states during discovery

Requiring both sides to confirm the connection ensures the topology reflects actual, current connectivity.

---

## 8. Performance Characteristics

| Operation | Typical Duration | Notes |
|-----------|------------------|-------|
| Single device (SNMP) | 2-5 seconds | System info + interfaces + neighbors |
| Single device (SSH) | 5-15 seconds | Connection + vendor detect + commands |
| LLDP table walk | 1-3 seconds | Depends on neighbor count |
| 100-device crawl | 3-8 minutes | Parallel within depth, sequential across depths |

---

## 9. Error Handling

### 9.1 Graceful Degradation

```python
# Collection errors don't stop discovery
try:
    interface_dict = await get_interface_table(...)
except Exception as e:
    device.discovery_errors.append(f"Interface collection failed: {e}")
    interface_dict = {}  # Continue with empty

try:
    cdp_neighbors = await get_cdp_neighbors(...)
except Exception as e:
    device.discovery_errors.append(f"CDP collection failed: {e}")
    # Continue to LLDP
```

### 9.2 DNS Handling

```python
# --no-dns mode for environments without name resolution
if self.no_dns:
    if not is_ip_address(target):
        return Device(
            discovery_success=False,
            discovery_errors=[f"DNS disabled, cannot resolve: {target}"]
        )
```

---

## 10. Future Enhancements

1. **Parallel device discovery** within each depth level
2. **Incremental discovery** - only rediscover changed portions
3. **SNMP traps** for real-time topology updates
4. **Additional protocols** - IS-IS, OSPF neighbor tables
5. **Credential learning** - remember which credential works per subnet

---

## Appendix A: OID Reference

```
System MIB:
  sysDescr.0      = 1.3.6.1.2.1.1.1.0
  sysObjectID.0   = 1.3.6.1.2.1.1.2.0
  sysUpTime.0     = 1.3.6.1.2.1.1.3.0
  sysName.0       = 1.3.6.1.2.1.1.5.0

IF-MIB:
  ifName          = 1.3.6.1.2.1.31.1.1.1.1
  ifAlias         = 1.3.6.1.2.1.31.1.1.1.18

LLDP-MIB:
  lldpLocPortTable = 1.0.8802.1.1.2.1.3.7
  lldpLocPortId    = 1.0.8802.1.1.2.1.3.7.1.3
  lldpRemTable     = 1.0.8802.1.1.2.1.4.1
  lldpRemManAddr   = 1.0.8802.1.1.2.1.4.2

CDP-MIB (Cisco):
  cdpCacheTable    = 1.3.6.1.4.1.9.9.23.1.2.1
```

---

## Appendix B: File Structure

```
scng/
├── discovery/
│   ├── __init__.py
│   ├── engine.py          # Main orchestration
│   ├── models.py          # Data classes
│   │
│   ├── snmp/
│   │   ├── walker.py      # SNMP GETBULK implementation
│   │   ├── lldp.py        # LLDP collection (two-pass)
│   │   ├── cdp.py         # CDP collection
│   │   ├── interfaces.py  # ifTable resolution
│   │   └── parsers.py     # SNMP value decoders
│   │
│   └── ssh/
│       ├── client.py      # SSH client wrapper
│       ├── collector.py   # SSHCollector
│       └── parsers.py     # TextFSM integration
│
├── creds/
│   └── vault.py           # Credential management
│
└── utils/
    └── tfsm_fire.py       # TextFSM auto-engine
```