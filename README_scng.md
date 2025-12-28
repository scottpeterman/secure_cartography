# SecureCartography NG (SCNG)

**Hybrid SNMP/SSH Network Discovery and Topology Mapping**

SCNG is a production-grade network discovery engine that combines SNMP-based collection with SSH CLI fallback to produce accurate, vendor-agnostic topology maps. Designed for real-world enterprise networks where access policies are fragmented and no single protocol reaches every device.

## Key Features

- **SNMP-first discovery** with automatic SSH fallback
- **Two-pass LLDP resolution** - correctly handles lldpLocPortNum vs ifIndex distinction
- **Bidirectional link validation** - only confirmed connections appear in topology
- **Multi-vendor support** - Cisco, Arista, Juniper, Palo Alto, and more
- **Encrypted credential vault** - Fernet/PBKDF2 with SQLite storage
- **CLI-driven** - scriptable, automatable, GUI-optional
- **Production tested** - 750+ device networks, 88%+ discovery success rates

## Why Hybrid Discovery?

Real enterprise networks have fragmented access:
- Device A: SNMP works, SSH blocked by firewall
- Device B: SNMP disabled, SSH with keys only
- Device C: SNMPv3 with different credentials
- Device D: Legacy box with old SNMP community

A pure SNMP tool misses half. A pure SSH tool misses the other half. SCNG gets both.

## Installation

```bash
git clone https://github.com/scottpeterman/scng.git
cd scng
pip install -r requirements.txt
```

**Dependencies:**
- Python 3.10+
- pysnmp (SNMP operations)
- paramiko (SSH connections)
- textfsm (CLI output parsing)
- cryptography (credential encryption)

## Quick Start

### 1. Initialize Credential Vault

```bash
python -m scng.creds init
# Enter master password when prompted
```

### 2. Add Credentials

```bash
# SNMP v2c
python -m scng.creds add snmpv2c prod-snmp --community your_community

# SNMP v3
python -m scng.creds add snmpv3 prod-snmpv3 \
    --username snmpuser \
    --auth-protocol sha256 \
    --auth-password authpass \
    --priv-protocol aes \
    --priv-password privpass

# SSH with password
python -m scng.creds add ssh admin-ssh --username admin

# SSH with key
python -m scng.creds add ssh key-ssh --username admin --key-file ~/.ssh/id_rsa
```

### 3. Discover Network

```bash
# Single device
python -m scng.discovery device 10.1.1.1

# Recursive crawl from seed
python -m scng.discovery crawl 10.1.1.1 \
    --max-depth 5 \
    --domain .example.com \
    --output ./discovery_output

# With verbose logging
python -m scng.discovery crawl 10.1.1.1 --max-depth 3 -v
```

### 4. Output

Discovery creates per-device folders with JSON data:

```
discovery_output/
├── device-hostname/
│   ├── device.json      # System info, interfaces
│   ├── cdp.json         # CDP neighbors (Cisco)
│   └── lldp.json        # LLDP neighbors
├── another-device/
│   └── ...
├── discovery_summary.json
└── map.json             # Topology with bidirectional validation
```

## Architecture

```
scng/
├── creds/                    # Credential management
│   ├── vault.py              # Encrypted SQLite storage
│   ├── models.py             # SSH, SNMPv2c, SNMPv3 dataclasses
│   └── cli.py                # Credential CLI
│
├── discovery/                # Discovery engine
│   ├── engine.py             # Orchestration, crawl logic
│   ├── models.py             # Device, Neighbor, Interface
│   ├── cli.py                # Discovery CLI
│   │
│   ├── snmp/                 # SNMP collection
│   │   ├── walker.py         # Async GETBULK table walks
│   │   ├── collectors/
│   │   │   ├── system.py     # sysDescr, sysName, etc.
│   │   │   ├── interfaces.py # ifTable, ifXTable
│   │   │   ├── lldp.py       # Two-pass LLDP resolution
│   │   │   ├── cdp.py        # CDP neighbor table
│   │   │   └── arp.py        # ARP for MAC→IP resolution
│   │   └── parsers.py        # SNMP value decoders
│   │
│   └── ssh/                  # SSH fallback
│       ├── client.py         # Paramiko wrapper
│       ├── collector.py      # Vendor detection, command execution
│       └── parsers.py        # TextFSM integration
│
└── utils/
    └── tfsm_fire.py          # TextFSM auto-template selection
```

## The Two-Pass LLDP Solution

SCNG correctly handles a subtle but critical issue: **LLDP port numbers are not the same as SNMP ifIndex values**.

Naive implementations assume `lldpRemLocalPortNum == ifIndex`, which causes:
- Device A reports: `Te1/49 → peer`
- Device B reports: `peer → Gi1/50` (wrong interface!)
- Bidirectional validation fails, valid links get dropped

**SCNG's approach:**

```
Pass 1: Query lldpLocPortTable
        Build mapping: lldpLocPortNum → interface name
        
Pass 2: Query lldpRemTable for neighbors
        Use lldpLocPortTable for correct local interface resolution
```

This eliminates an entire class of topology errors.

## Bidirectional Validation

The topology builder only includes connections where both sides agree:

- **Both devices discovered**: Require mutual confirmation
- **Only one device discovered** (leaf node): Trust unidirectional claim

This filters out:
- Stale LLDP cache entries
- Misconfigured one-way links
- Interface mapping errors

## CLI Reference

### Credentials

```bash
# Initialize vault
python -m scng.creds init

# Add credentials
python -m scng.creds add ssh <name> --username <user> [--password] [--key-file <path>]
python -m scng.creds add snmpv2c <name> --community <string>
python -m scng.creds add snmpv3 <name> --username <user> --auth-protocol <proto> ...

# List credentials
python -m scng.creds list

# Test credential against host
python -m scng.creds test <name> <host>

# Auto-discover working credential
python -m scng.creds discover <host>

# Delete credential
python -m scng.creds delete <name>
```

### Discovery

```bash
# Single device discovery
python -m scng.discovery device <ip> [--output <dir>]

# Recursive network crawl
python -m scng.discovery crawl <seed_ip> \
    [--max-depth <n>]           # Default: 3
    [--domain <suffix>]         # e.g., .example.com (can specify multiple)
    [--exclude <pattern>]       # sysDescr patterns to skip
    [--output <dir>]            # Output directory
    [--no-dns]                  # Disable DNS lookups
    [-v, --verbose]             # Debug output
```

## Output Formats

### device.json
```json
{
  "hostname": "switch-01",
  "ip_address": "10.1.1.1",
  "sys_name": "switch-01.example.com",
  "sys_descr": "Arista Networks EOS version 4.33.1F...",
  "vendor": "arista",
  "interfaces": [...],
  "neighbors": [...],
  "discovered_via": "snmp",
  "discovery_duration_ms": 2847
}
```

### map.json (Topology)
```json
{
  "switch-01": {
    "node_details": {
      "ip": "10.1.1.1",
      "platform": "Arista vEOS-lab EOS 4.33.1F"
    },
    "peers": {
      "switch-02": {
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

## Visualization

The `map.json` output is compatible with:

- **yEd** - Import as GraphML after conversion
- **draw.io** - Direct import or via conversion script
- **Cytoscape** - For programmatic visualization
- **D3.js** - Web-based interactive diagrams

Use `folder_to_map.py` to regenerate topology from device folders:

```bash
python folder_to_map.py ./discovery_output --output topology.json
```

## Performance

Typical discovery rates:
- Single device (SNMP): 2-5 seconds
- Single device (SSH fallback): 5-15 seconds  
- 100 devices: 3-8 minutes
- 750+ devices: ~4-5 hours

## Supported Vendors

| Vendor | SNMP | SSH | Notes |
|--------|------|-----|-------|
| Cisco IOS/IOS-XE | ✓ | ✓ | CDP + LLDP |
| Cisco NX-OS | ✓ | ✓ | CDP + LLDP |
| Arista EOS | ✓ | ✓ | LLDP primary |
| Juniper JUNOS | ✓ | ✓ | LLDP primary |
| Palo Alto | ✓ | ✓ | LLDP |

## Project History

SCNG combines learnings from three production tools:

- **VelocityMaps** - SNMP-based CDP/LLDP discovery
- **VCollector** - SSH + TextFSM template parsing  
- **Secure Cartography** - Recursive discovery with credential management

The hybrid approach emerged from real-world necessity: enterprise networks with 10+ years of accumulated configuration debt, where no single access method reaches every device.

## License

GPLv3 License - See LICENSE file

## Author

Scott Peterman - Principal Infrastructure Engineer

## Contributing

Issues and PRs welcome. Please include:
- Device vendor/model affected
- Sanitized debug output (`-v` flag)
- Expected vs actual behavior