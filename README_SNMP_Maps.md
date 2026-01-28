# Device Poll Dialog

PyQt6 GUI for SNMP device fingerprinting with vendor identification. Poll network devices to identify vendor, model, OS version, and enumerate interfaces and ARP tables.

Part of the [Secure Cartography](https://github.com/scottpeterman/secure_cartography) network discovery toolkit.

![Device Poll Dialog](docs/device_poll_dialog.png)

## Features

- **Device Fingerprinting**: Identify vendor, model, OS via Rapid7 Recog patterns
- **OUI Lookups**: MAC address vendor identification using Wireshark's manuf database
- **Interface Enumeration**: List all interfaces with MAC addresses
- **ARP Table Collection**: Gather neighbor/ARP table entries
- **Proxy Support**: Poll via remote SNMP proxy for isolated networks
- **Excel Export**: Export results to formatted spreadsheet
- **Themeable**: Follows application theme (dark/light)

## Requirements

```
PyQt6
openpyxl (optional, for Excel export)
```

For direct SNMP polling (no proxy):
```
net-snmp tools (snmpget, snmpwalk) in PATH
```

## Usage

### Standalone

```python
from device_poll_dialog import DevicePollDialog
from PyQt6.QtWidgets import QApplication

app = QApplication([])
dialog = DevicePollDialog(
    ip="192.168.1.1",
    hostname="core-switch-01",
    theme_manager=my_theme_manager  # Optional
)
dialog.exec()
```

### From Map Viewer (Secure Cartography)

Right-click a node → "Poll Device" opens the dialog pre-filled with the node's IP and hostname.

## Interface

### Settings Panel

| Field | Description |
|-------|-------------|
| **Community** | SNMP community string (masked input) |
| **Version** | v1 or v2c (v3 via proxy only) |
| **Use SNMP Proxy** | Enable remote proxy mode |
| **Proxy URL** | Proxy address (e.g., `http://jumphost:8899`) |
| **API Key** | Proxy authentication key |

### Results Tabs

| Tab | Content |
|-----|---------|
| **Summary** | System info, fingerprint matches, timing |
| **Interfaces** | Interface names, MACs, vendors |
| **ARP Table** | IP addresses, MACs, vendors |
| **Raw Data** | JSON dump of all collected data |

### Buttons

| Button | Action |
|--------|--------|
| **Poll Device** | Start SNMP collection |
| **Cancel** | Abort running poll |
| **Update Node** | Push fingerprint data back to map |
| **Export Excel** | Save results to .xlsx file |

## Proxy Mode

For networks where your desktop can't reach devices directly, use the SNMP proxy:

1. Deploy `snmp_proxy` on a jump host with SNMP access
2. Note the API key from proxy startup
3. Enable "Use SNMP Proxy" in dialog
4. Enter proxy URL and API key
5. Settings persist to `~/.scng/proxy_settings.json`

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│  Desktop    │  HTTP   │  Jump Host  │  SNMP   │   Network   │
│  (Dialog)   │───────►│   (Proxy)   │───────►│   Device    │
└─────────────┘         └─────────────┘         └─────────────┘
```

### Proxy Features

- **Ticket-based async**: No HTTP timeouts on long walks
- **Progress tracking**: See interface/ARP counts in real-time
- **Cancellation**: Stop mid-poll cleanly

## Fingerprinting

### Recog Pattern Matching

Uses [Rapid7 Recog](https://github.com/rapid7/recog) XML fingerprint files to identify devices:

- `snmp_sysdescr.xml` - Matches sysDescr strings
- `snmp_sysobjid.xml` - Matches sysObjectID OIDs

**Example output:**
```
Arista Network Switch
  os.vendor: Arista
  os.family: EOS
  hw.device: Switch
  os.product: EOS
  os.certainty: 0.9
  os.version: 4.33.1F
  hw.model: vEOS-lab
```

### OUI Lookup

MAC vendor identification using Wireshark's manufacturer database (`manuf.txt`).

**Example:**
```
MAC: 00:05:86:71:AE:00 → Lucent Technologies (Juniper)
MAC: 0C:DE:AD:58:AB:E2 → (Unknown)
```

## Data Files

Fingerprint data is stored in `~/.scng/fingerprint_data/`:

```
fingerprint_data/
├── recog/
│   ├── snmp_sysdescr.xml
│   └── snmp_sysobjid.xml
└── manuf.txt
```

Click **"Download Data Files"** to fetch the latest versions from:
- https://github.com/rapid7/recog (Recog patterns)
- https://www.wireshark.org/download/automated/data/manuf (OUI database)

## SNMP OIDs Collected

### System Info (GET)

| OID | Name |
|-----|------|
| 1.3.6.1.2.1.1.1.0 | sysDescr |
| 1.3.6.1.2.1.1.2.0 | sysObjectID |
| 1.3.6.1.2.1.1.3.0 | sysUpTime |
| 1.3.6.1.2.1.1.4.0 | sysContact |
| 1.3.6.1.2.1.1.5.0 | sysName |
| 1.3.6.1.2.1.1.6.0 | sysLocation |

### Interface Table (WALK)

| OID | Name |
|-----|------|
| 1.3.6.1.2.1.2.2.1.2 | ifDescr |
| 1.3.6.1.2.1.2.2.1.6 | ifPhysAddress |

### ARP Table (WALK)

| OID | Name |
|-----|------|
| 1.3.6.1.2.1.4.22.1.2 | ipNetToMediaPhysAddress |
| 1.3.6.1.2.1.4.22.1.3 | ipNetToMediaNetAddress |

## Excel Export

Exports to a formatted .xlsx with three sheets:

1. **Summary**: System info and fingerprint matches
2. **Interfaces**: Interface, MAC, Vendor columns
3. **ARP Table**: IP, MAC, Vendor columns

Includes formatting: headers, borders, column widths.

## Node Update

The "Update Node" button emits a signal with extracted data:

```python
{
    'id': 'core-switch-01',
    'ip': '192.168.1.1',
    'vendor': 'Arista',
    'platform': 'EOS',
    'version': '4.33.1F',
    'device_type': 'Switch'
}
```

Connect to `node_update_available` signal to update your map/inventory:

```python
dialog.node_update_available.connect(my_update_handler)
```

## Configuration Persistence

Proxy settings saved to `~/.scng/proxy_settings.json`:

```json
{
  "enabled": true,
  "url": "http://jumphost:8899",
  "api_key": "d0f0d9e6-36ae-489d-ba96-29da77e529cc"
}
```

## Theming

Pass a `ThemeManager` instance for consistent styling:

```python
dialog = DevicePollDialog(
    ip="192.168.1.1",
    hostname="switch-01",
    theme_manager=app.theme_manager
)
```

Supports dark and light themes via `ThemeColors` dataclass.

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "snmpget not found" | net-snmp not installed | Install net-snmp or use proxy |
| "No SNMP response" | Device unreachable / wrong community | Verify IP, community, network path |
| "Cannot connect to proxy" | Proxy not running | Start snmp_proxy on jump host |
| "Invalid API key" | Wrong proxy key | Copy key from proxy startup output |

## Class Reference

### DevicePollDialog

Main dialog class.

```python
DevicePollDialog(
    ip: str,                           # Target IP address
    hostname: str = "",                # Display name
    theme_manager: ThemeManager = None,# Optional theming
    parent: QWidget = None
)
```

**Signals:**
- `node_update_available(dict)` - Emitted when user clicks "Update Node"

### PollWorker

Background thread for SNMP operations.

```python
PollWorker(
    ip: str,
    community: str,
    data_dir: Path,
    collect_interfaces: bool = True,
    collect_arp: bool = True,
    use_proxy: bool = False,
    proxy_url: str = "",
    proxy_api_key: str = "",
    snmp_version: str = "2c"
)
```

**Signals:**
- `progress(str)` - Status updates
- `finished(PollResult)` - Completion with results

**Methods:**
- `cancel()` - Request cancellation

### PollResult

Dataclass holding poll results.

```python
@dataclass
class PollResult:
    ip: str
    success: bool = False
    error: str = ""
    snmp_data: Dict[str, str]           # System OIDs
    recog_matches: List[FingerprintMatch]  # Fingerprint results
    oui_lookups: Dict[str, Dict]        # MAC → vendor mappings
    interfaces: List[Dict]              # Interface list
    arp_table: List[Dict]               # ARP entries
    timing: Dict[str, float]            # Phase timings
```

## License

MIT License - See LICENSE file

## Author

Scott Peterman