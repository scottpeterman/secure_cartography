# Secure Cartography v2

**SSH & SNMP-Based Network Discovery and Topology Mapping**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![PyQt6](https://img.shields.io/badge/GUI-PyQt6-green.svg)](https://www.riverbankcomputing.com/software/pyqt/)

Secure Cartography is a network discovery tool that crawls your infrastructure via SNMP and SSH, collecting CDP/LLDP neighbor information to automatically generate topology maps. Built by a network engineer, for network engineers.

<p align="center">
  <img src="https://raw.githubusercontent.com/scottpeterman/secure_cartography/main/screenshots/main_cyber.png" alt="Secure Cartography - Cyber Theme" width="800">
</p>

---

## What's New in v2

Version 2 is a complete rewrite with a modernized architecture:

| Feature | v1 | v2 |
|---------|----|----|
| Discovery Engine | Synchronous, single-threaded | **Async with configurable concurrency** |
| Credential Storage | YAML + keyring | **SQLite vault with AES-256 encryption** |
| CLI | Basic | **Full-featured with test/discover/crawl commands** |
| Progress Reporting | Callbacks | **Structured events for GUI integration** |
| SSH Support | Primary | **Fallback when SNMP unavailable** |
| SNMP Support | v2c only | **v2c and v3 (authPriv)** |
| GUI | PyQt5 | **PyQt6 with theme support (Cyber/Dark/Light)** |
| Topology Viewer | External | **Embedded Cytoscape.js with live preview** |

---

## Features

### Discovery Engine
- **SNMP-first discovery** with automatic SSH fallback
- **CDP and LLDP** neighbor detection across vendors
- **Two-pass LLDP resolution** - correctly handles lldpLocPortNum vs ifIndex
- **Bidirectional link validation** - only confirmed connections appear in topology
- **Concurrent crawling** - discover 20+ devices simultaneously
- **Depth-limited recursion** - control how far the crawler goes
- **Exclusion patterns** - skip devices by hostname, sys_name, or sysDescr
- **No-DNS mode** - use IPs directly from neighbor tables (home lab friendly)

### Credential Management
- **Encrypted SQLite vault** - AES-256-GCM encryption at rest
- **Multiple credential types** - SSH (password + key), SNMPv2c, SNMPv3
- **Priority ordering** - try credentials in sequence until one works
- **Credential discovery** - auto-detect which credentials work on which devices

### Live Topology Preview
- **Embedded Cytoscape.js viewer** - interactive network visualization
- **Real-time rendering** - topology displayed immediately after discovery
- **Vendor-specific icons** - Cisco, Arista, Juniper with distinct styling
- **Undiscovered peer nodes** - referenced but unreachable devices shown with warning markers
- **Theme-aware** - visualization adapts to Cyber/Dark/Light themes
- **Interactive controls** - fit view, auto-layout, node selection with details popup

### Themed GUI
- **Three themes** - Cyber (cyan), Dark (gold), Light (blue)
- **Real-time progress** - live counters, depth tracking, log output
- **Responsive design** - UI remains interactive during discovery
- **Click-to-inspect** - node details (hostname, IP, platform) on selection

### Supported Platforms
| Vendor | SNMP | SSH | Notes |
|--------|------|-----|-------|
| Cisco IOS/IOS-XE | ✓ | ✓ | CDP + LLDP |
| Cisco NX-OS | ✓ | ✓ | CDP + LLDP |
| Arista EOS | ✓ | ✓ | LLDP primary |
| Juniper JUNOS | ✓ | ✓ | LLDP primary |

---

## Screenshots

<table>
<tr>
<td><img src="https://raw.githubusercontent.com/scottpeterman/secure_cartography/main/screenshots/main_cyber.png" alt="Cyber Theme" width="280"></td>
<td><img src="https://raw.githubusercontent.com/scottpeterman/secure_cartography/main/screenshots/main_dark.png" alt="Dark Theme" width="280"></td>
<td><img src="https://raw.githubusercontent.com/scottpeterman/secure_cartography/main/screenshots/main_light.png" alt="Light Theme" width="280"></td>
</tr>
<tr>
<td align="center"><b>Cyber</b> - Teal accents</td>
<td align="center"><b>Dark</b> - Gold accents</td>
<td align="center"><b>Light</b> - Blue accents</td>
</tr>
</table>

<table>
<tr>
<td><img src="https://raw.githubusercontent.com/scottpeterman/secure_cartography/main/screenshots/full_run_preview_cyber.png" alt="Topology - Cyber" width="280"></td>
<td><img src="https://raw.githubusercontent.com/scottpeterman/secure_cartography/main/screenshots/run_complete_dark.png" alt="Topology - Dark" width="280"></td>
<td><img src="https://raw.githubusercontent.com/scottpeterman/secure_cartography/main/screenshots/full_run_preview_light.png" alt="Topology - Light" width="280"></td>
</tr>
<tr>
<td align="center">Topology Preview - Cyber</td>
<td align="center">Topology Preview - Dark</td>
<td align="center">Topology Preview - Light</td>
</tr>
</table>

<table>
<tr>
<td><img src="https://raw.githubusercontent.com/scottpeterman/secure_cartography/main/screenshots/login_cyan.png" alt="Login - Cyber" width="280"></td>
<td><img src="https://raw.githubusercontent.com/scottpeterman/secure_cartography/main/screenshots/login_amber.png" alt="Login - Dark" width="280"></td>
<td><img src="https://raw.githubusercontent.com/scottpeterman/secure_cartography/main/screenshots/login_light.png" alt="Login - Light" width="280"></td>
</tr>
<tr>
<td align="center">Login - Cyber</td>
<td align="center">Login - Dark</td>
<td align="center">Login - Light</td>
</tr>
</table>

---

## Installation

### Prerequisites
- Python 3.10 or higher
- pip

### From Source
```bash
git clone https://github.com/scottpeterman/secure_cartography.git
cd secure_cartography
pip install -e .
```

### Dependencies
```bash
# Core
pip install pysnmp-lextudio paramiko cryptography textfsm aiofiles

# GUI
pip install PyQt6 PyQt6-WebEngine
```

---

## Quick Start

### 1. Initialize the Credential Vault
```bash
# Create vault and set master password
python -m sc2.scng.creds init

# Add SNMP credential
python -m sc2.scng.creds add snmpv2c snmp-readonly --community public

# Add SSH credential  
python -m sc2.scng.creds add ssh network-admin --username admin

# List credentials
python -m sc2.scng.creds list
```

### 2. Test Connectivity
```bash
# Quick SNMP test (no vault needed)
python -m sc2.scng.discovery test 192.168.1.1 --community public

# Test with vault credentials
python -m sc2.scng.discovery device 192.168.1.1
```

### 3. Run Discovery
```bash
# Basic crawl
python -m sc2.scng.discovery crawl 192.168.1.1 -d 3

# With options
python -m sc2.scng.discovery crawl 192.168.1.1 10.0.0.1 \
    -d 5 \
    --domain corp.example.com \
    --exclude "phone,wireless,linux" \
    --output ./network_maps
```

### 4. Launch GUI
```bash
python -m sc2.ui
```

---

## Architecture

```
sc2/
├── scng/                      # Discovery engine
│   ├── creds/                 # Credential vault
│   │   ├── vault.py           # Encrypted SQLite storage
│   │   ├── models.py          # SSH, SNMPv2c, SNMPv3 dataclasses
│   │   ├── resolver.py        # Credential testing & discovery
│   │   └── cli.py             # Credential management CLI
│   │
│   ├── discovery/             # Discovery engine
│   │   ├── engine.py          # Async orchestration, crawl logic
│   │   ├── models.py          # Device, Neighbor, Interface
│   │   ├── cli.py             # Discovery CLI
│   │   │
│   │   ├── snmp/              # SNMP collection
│   │   │   ├── walker.py      # Async GETBULK table walks
│   │   │   └── collectors/    # system, interfaces, lldp, cdp, arp
│   │   │
│   │   └── ssh/               # SSH fallback
│   │       ├── client.py      # Paramiko wrapper
│   │       ├── collector.py   # Vendor detection, command execution
│   │       └── parsers.py     # TextFSM integration
│   │
│   └── utils/
│       └── tfsm_fire.py       # TextFSM auto-template selection
│
└── ui/                        # PyQt6 GUI
    ├── themes.py              # Theme system (Cyber/Dark/Light)
    ├── login.py               # Vault unlock dialog
    ├── main_window.py         # Main application window
    │
    └── widgets/               # Custom themed widgets
        ├── panel.py               # Base panel with title bar
        ├── connection_panel.py    # Seeds, domains, excludes
        ├── credentials_panel.py   # Credential management UI
        ├── discovery_options.py   # Depth, concurrency, toggles
        ├── output_panel.py        # Output directory config
        ├── progress_panel.py      # Stats, progress bar
        ├── discovery_log.py       # Styled log output
        ├── discovery_controller.py # Discovery↔UI bridge with throttled events
        ├── topology_preview_panel.py  # Preview container (singleton)
        ├── topology_viewer.py     # QWebEngineView + Cytoscape.js bridge
        ├── topology_viewer.html   # Cytoscape.js visualization
        ├── tag_input.py           # Tag/chip input widget
        ├── toggle_switch.py       # iOS-style toggle
        └── stat_box.py            # Counter display boxes
```

---

## Topology Viewer

The embedded topology viewer uses [Cytoscape.js](https://js.cytoscape.org/) for interactive network visualization.

### Features
- **Automatic layout** - COSE algorithm for organic network arrangement
- **Vendor icons** - Platform-specific SVG icons (Cisco, Arista, Juniper)
- **Undiscovered nodes** - Peers referenced but not crawled shown with dashed borders and ⚠ markers
- **Edge labels** - Interface pairs displayed on connections
- **Click inspection** - Select nodes to view device details
- **Theme integration** - Colors adapt to current UI theme

### Data Flow
```
Discovery Engine → map.json → Base64 encode → QWebChannel → JavaScript → Cytoscape.js
```

The viewer uses base64 encoding for reliable Python→JavaScript data transfer, avoiding escaping issues with complex JSON payloads.

---

## CLI Reference

Secure Cartography provides two CLI modules that can be used independently of the GUI:

- `sc2.scng.creds` - Credential vault management
- `sc2.scng.discovery` - Network discovery engine

Both CLIs support `--help` on all commands and subcommands.

---

### Credential Management (`sc2.scng.creds`)

```
usage: scng-creds [-h] [--vault-path VAULT_PATH] [--password PASSWORD]
                  {init,unlock,add,list,show,remove,set-default,test,discover,change-password,deps} ...
```

#### Global Options

| Option | Description |
|--------|-------------|
| `-v, --vault-path` | Path to vault database (default: `~/.scng/credentials.db`) |
| `-p, --password` | Vault password (or set `SCNG_VAULT_PASSWORD` env var) |

#### Commands

##### `init` - Initialize a new vault
```bash
python -m sc2.scng.creds init
python -m sc2.scng.creds init --vault-path /path/to/custom.db
```

##### `add` - Add credentials
```bash
# SSH with password (prompts for password)
python -m sc2.scng.creds add ssh admin-cred --username admin --password

# SSH with key file
python -m sc2.scng.creds add ssh key-cred --username automation --key-file ~/.ssh/id_rsa

# SNMPv2c
python -m sc2.scng.creds add snmpv2c readonly --community public

# SNMPv3 (authPriv)
python -m sc2.scng.creds add snmpv3 snmpv3-cred \
    --username snmpuser \
    --auth-protocol sha256 \
    --auth-password authpass123 \
    --priv-protocol aes128 \
    --priv-password privpass123
```

##### `list` - List all credentials
```bash
python -m sc2.scng.creds list
```
Output shows credential name, type, priority, and default status.

##### `show` - Show credential details
```bash
python -m sc2.scng.creds show admin-cred
python -m sc2.scng.creds show admin-cred --reveal  # Show passwords/communities
```

##### `remove` - Delete a credential
```bash
python -m sc2.scng.creds remove old-credential
```

##### `set-default` - Set credential as default for its type
```bash
python -m sc2.scng.creds set-default admin-cred
```

##### `test` - Test credential against a host
```bash
python -m sc2.scng.creds test admin-cred 192.168.1.1
python -m sc2.scng.creds test readonly 10.0.0.1
```

##### `discover` - Find which credentials work on a host
```bash
python -m sc2.scng.creds discover 192.168.1.1
```
Tests all credentials and reports which ones succeed.

##### `change-password` - Change vault master password
```bash
python -m sc2.scng.creds change-password
```

##### `deps` - Check required dependencies
```bash
python -m sc2.scng.creds deps
```

---

### Network Discovery (`sc2.scng.discovery`)

```
usage: scng.discovery [-h] {test,device,crawl} ...
```

#### Commands

##### `test` - Quick SNMP connectivity test (no vault required)
```bash
python -m sc2.scng.discovery test 192.168.1.1 --community public
python -m sc2.scng.discovery test 192.168.1.1 --community public --verbose
```

##### `device` - Discover a single device
```bash
python -m sc2.scng.discovery device 192.168.1.1
python -m sc2.scng.discovery device core-switch.example.com --output ./results
```

##### `crawl` - Recursive network discovery
```
usage: scng.discovery crawl [-h] [-d DEPTH] [--domain DOMAINS] [--exclude EXCLUDE_PATTERNS]
                            [-o OUTPUT] [-v] [--no-dns] [-c CONCURRENCY] [-t TIMEOUT]
                            [--no-color] [--timestamps] [--json-events]
                            seeds [seeds ...]
```

| Option | Description |
|--------|-------------|
| `seeds` | One or more seed IP addresses or hostnames |
| `-d, --depth` | Maximum discovery depth (default: 3) |
| `--domain` | Domain suffix for hostname resolution (repeatable) |
| `--exclude` | Exclusion patterns for devices to skip (repeatable, comma-separated) |
| `-o, --output` | Output directory for results |
| `-v, --verbose` | Enable debug output |
| `--no-dns` | Disable DNS lookups; use IPs from LLDP/CDP directly |
| `-c, --concurrency` | Maximum parallel discoveries (default: 20) |
| `-t, --timeout` | SNMP timeout in seconds (default: 5) |
| `--no-color` | Disable colored terminal output |
| `--timestamps` | Show timestamps in log output |
| `--json-events` | Output events as JSON lines (for GUI/automation integration) |

#### Crawl Examples

```bash
# Basic crawl from single seed
python -m sc2.scng.discovery crawl 192.168.1.1

# Multiple seeds with depth limit
python -m sc2.scng.discovery crawl 10.1.1.1 10.2.1.1 --depth 5

# With domain suffix for DNS resolution
python -m sc2.scng.discovery crawl core-sw01 --domain corp.example.com --domain example.com

# Exclude devices by pattern (matches hostname, sys_name, or sysDescr)
python -m sc2.scng.discovery crawl 192.168.1.1 --exclude "linux,vmware,phone"

# Multiple exclude flags also work
python -m sc2.scng.discovery crawl 192.168.1.1 \
    --exclude "linux" \
    --exclude "phone" \
    --exclude "wireless"

# Home lab mode (no DNS, faster)
python -m sc2.scng.discovery crawl 192.168.1.1 --no-dns

# High concurrency for large networks
python -m sc2.scng.discovery crawl 10.0.0.1 -c 50 -d 10 -o ./enterprise_map

# Full production example
python -m sc2.scng.discovery crawl \
    core-rtr-01.dc1.example.com \
    core-rtr-01.dc2.example.com \
    --depth 8 \
    --domain dc1.example.com \
    --domain dc2.example.com \
    --exclude "linux,esxi,vcenter,phone,wireless,ups" \
    --concurrency 30 \
    --timeout 10 \
    --output ./network_discovery_$(date +%Y%m%d) \
    --verbose
```

#### Exclusion Patterns

The `--exclude` option filters devices from propagating the crawl. Patterns are:

- **Case-insensitive** substring matches
- **Comma-separated** for multiple patterns in one flag
- Matched against **three fields**: `sysDescr`, `hostname`, and `sys_name`

This means exclusions work for both SNMP-discovered devices (via sysDescr) and SSH-discovered devices (via hostname).

| Pattern | Matches |
|---------|---------|
| `linux` | Any device with "linux" in sysDescr, hostname, or sys_name |
| `rtr-lab,sw-test` | Devices with "rtr-lab" OR "sw-test" in any field |
| `phone,wireless,ap-` | Common patterns to skip IP phones and APs |

**Note:** Excluded devices are still discovered (credentials tested, data collected), but their neighbors are not queued for further discovery. This prevents the crawl from expanding through non-network infrastructure.

---

## Output Format

Discovery creates per-device folders with JSON data:

```
discovery_output/
├── core-switch-01/
│   ├── device.json      # System info, interfaces
│   ├── cdp.json         # CDP neighbors
│   └── lldp.json        # LLDP neighbors
├── dist-switch-01/
│   └── ...
├── discovery_summary.json
└── map.json             # Topology with bidirectional validation
```

### map.json (Topology)
```json
{
  "core-switch-01": {
    "node_details": {
      "ip": "10.1.1.1",
      "platform": "Arista vEOS-lab EOS 4.33.1F"
    },
    "peers": {
      "dist-switch-01": {
        "ip": "10.1.1.2",
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

## GUI Theme System

The GUI uses a comprehensive theme system with three built-in themes:

| Theme | Primary | Accent | Use Case |
|-------|---------|--------|----------|
| **Cyber** | `#0a0a0f` | `#00ffff` (cyan) | SOC/NOC aesthetic |
| **Dark** | `#000000` | `#d4af37` (gold) | Professional elegance |
| **Light** | `#ffffff` | `#2563eb` (blue) | Bright environments |

See [README_Style_Guide.md](README_Style_Guide.md) for widget styling details.

---

## Documentation

| Document | Description |
|----------|-------------|
| [README_Creds.md](README_Creds.md) | Credential vault API and CLI |
| [README_scng.md](README_scng.md) | Discovery engine architecture |
| [README_SNMP_Discovery.md](README_SNMP_Discovery.md) | SNMP collection details |
| [README_SSH_Discovery.md](README_SSH_Discovery.md) | SSH fallback module |
| [README_Progress_events.md](README_Progress_events.md) | GUI progress event reference |
| [README_Style_Guide.md](README_Style_Guide.md) | PyQt6 widget theming guide |

---

## Development Status

### ✅ Complete
- Credential vault with encryption
- SNMP discovery (v2c, v3)
- SSH fallback discovery
- Async crawl engine with progress events
- CLI for creds and discovery
- Theme system (Cyber/Dark/Light)
- Login dialog with vault unlock
- Main window layout with all panels
- Custom themed widgets
- Discovery↔UI integration with throttled events
- Live topology preview with Cytoscape.js
- Undiscovered peer node visualization

### 📋 Planned
- Map enhancement tools (manual node positioning, annotations)
- Credential auto-discovery integration
- Settings persistence
- Export topology as PNG/SVG
- Full-screen topology viewer
- Topology diff (compare discoveries)

---

## Technical Notes

### Threading Architecture
The GUI uses a careful threading model to prevent UI lockups:

- **Discovery runs in QThread** - async engine wrapped in worker thread
- **Events throttled at source** - high-frequency events (stats, topology) rate-limited before emission
- **QueuedConnection for all signals** - ensures slots execute on main thread
- **WebView isolation** - no webview updates during active discovery; topology loads once at completion

### Topology Data Transfer
Python→JavaScript communication uses base64 encoding:
```python
# Python side
b64_data = base64.b64encode(json.dumps(topology).encode()).decode()
self._run_js(f"TopologyViewer.loadTopologyB64('{b64_data}')")
```
```javascript
// JavaScript side  
loadTopologyB64(b64String) {
    const jsonString = atob(b64String);
    this.loadTopology(jsonString);
}
```
This avoids JSON escaping issues with complex network data containing special characters.

---

## Security Considerations

- **Master password** is never stored; derived key is held in memory only while vault is unlocked
- **Credentials are encrypted** with AES-256-GCM before storage
- **Salt** is randomly generated per installation
- **No credentials in logs** - discovery output never includes passwords/communities
- **Vault auto-locks** when application exits

---

## Performance

Typical discovery rates:
- Single device (SNMP): 2-5 seconds
- Single device (SSH fallback): 5-15 seconds
- 100 devices: 3-8 minutes with 20 concurrent workers
- 750+ devices: ~4-5 hours (production tested, 88%+ success rate)

GUI remains responsive during discovery due to throttled event architecture.

---

## License

This project is licensed under the **GNU General Public License v3.0** - see [LICENSE](LICENSE) for details.

GPL v3 is required due to the use of PyQt6.

---

## Author

**Scott Peterman** - Principal Infrastructure Engineer

- GitHub: [@scottpeterman](https://github.com/scottpeterman)
- LinkedIn: [scottpeterman](https://www.linkedin.com/in/scottpeterman/)

*Built by a network engineer who got tired of manually drawing topology diagrams.*

---

## Acknowledgments

- Network visualization powered by [Cytoscape.js](https://js.cytoscape.org/)
- SNMP operations via [pysnmp-lextudio](https://github.com/lextudio/pysnmp)
- SSH via [Paramiko](https://www.paramiko.org/)
- CLI parsing with [TextFSM](https://github.com/google/textfsm)
- GUI powered by [PyQt6](https://www.riverbankcomputing.com/software/pyqt/)
- Encryption via [cryptography](https://cryptography.io/)