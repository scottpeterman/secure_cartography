# SCNG SSH Discovery Module

SSH-based fallback for neighbor discovery when SNMP fails or lacks neighbor data.

## Overview

The SSH module provides CDP/LLDP neighbor collection via CLI commands, using TextFSM templates for multi-vendor parsing. It integrates with `scng.creds` for credential management.

## Architecture

```
scng/discovery/ssh/
├── __init__.py       # Public API exports
├── __main__.py       # CLI entry point
├── client.py         # Paramiko SSH wrapper
├── collector.py      # Discovery orchestration
├── parsers.py        # TextFSM template matching
└── templates/        # (Optional) Additional templates
```

## Components

### SSHClient (`client.py`)

Paramiko wrapper with:
- Legacy algorithm support (DH group1, 3DES, etc.)
- ANSI sequence filtering
- Prompt detection and counting
- Key or password authentication

```python
from sc2.scng.discovery.ssh import SSHClient, SSHClientConfig

config = SSHClientConfig(
    host="192.168.1.1",
    username="admin",
    password="secret",
    legacy_mode=True,  # Enable old ciphers
)

with SSHClient(config) as client:
    client.find_prompt()
    output = client.execute_command("show cdp neighbors detail")
```

### TextFSMParser (`parsers.py`)

Template-based CLI parsing with:
- 7 embedded templates (no external DB required)
- Optional `tfsm_templates.db` integration
- Auto-scoring for best template match
- Output cleaning (removes prompts, command echoes)

```python
from sc2.scng.discovery.ssh import TextFSMParser

parser = TextFSMParser()
result = parser.parse(output, "cisco_ios_show_cdp_neighbors_detail")

if result.success:
    for record in result.records:
        print(record)
```

**Embedded Templates:**
- `cisco_ios_show_cdp_neighbors_detail`
- `cisco_ios_show_lldp_neighbors_detail`
- `cisco_nxos_show_cdp_neighbors_detail`
- `cisco_nxos_show_lldp_neighbors_detail`
- `arista_eos_show_lldp_neighbors`
- `arista_eos_show_lldp_neighbors_detail`
- `juniper_junos_show_lldp_neighbors`

### SSHCollector (`collector.py`)

High-level discovery interface:
- Vendor auto-detection
- Vendor-specific command selection
- CDP + LLDP collection
- Returns `Neighbor` model objects

```python
from sc2.scng.discovery.ssh import SSHCollector

collector = SSHCollector(
    username="admin",
    password="secret",
    legacy_mode=True,
)

result = collector.collect("192.168.1.1")

print(f"Vendor: {result.vendor.value}")
for neighbor in result.neighbors:
    print(f"  [{neighbor.protocol.value}] {neighbor.local_interface} -> {neighbor.remote_device}")
```

## CLI Usage

```bash
# List available templates
python -m sc2.scng.discovery.ssh templates

# Test against device
python -m sc2.scng.discovery.ssh test 192.168.1.1 -u admin -p secret -v

# With legacy mode
python -m sc2.scng.discovery.ssh test 192.168.1.1 -u admin --legacy

# Save results to JSON
python -m sc2.scng.discovery.ssh test 192.168.1.1 -u admin -o results.json

# Parse output from file
python -m sc2.scng.discovery.ssh parse output.txt cisco_ios_show_cdp
```

## Integration with scng.creds

```python
from scng.creds import CredentialVault
from sc2.scng.discovery.ssh import SSHCollector

# Get credentials from vault
vault = CredentialVault()
vault.unlock("password")
ssh_cred = vault.get_ssh_credential("lab")

# Use in collector
collector = SSHCollector(
    username=ssh_cred.username,
    password=ssh_cred.password,
    key_content=ssh_cred.key_content,
)

result = collector.collect("192.168.1.1")
vault.lock()
```

## Vendor Command Mapping

| Vendor  | CDP Command                    | LLDP Command                |
|---------|-------------------------------|-----------------------------|
| Cisco   | `show cdp neighbors detail`   | `show lldp neighbors detail`|
| Arista  | -                             | `show lldp neighbors detail`|
| Juniper | -                             | `show lldp neighbors`       |
| NX-OS   | `show cdp neighbors detail`   | `show lldp neighbors detail`|

## Data Models

### Neighbor

```python
@dataclass
class Neighbor:
    local_interface: str        # Our port name
    remote_device: str          # Neighbor hostname
    remote_interface: str       # Neighbor port name
    protocol: NeighborProtocol  # CDP or LLDP (required)
    remote_ip: Optional[str]    # Management IP
    chassis_id: Optional[str]   # LLDP chassis ID
    platform: Optional[str]     # CDP platform string
    capabilities: Optional[str]
```

### SSHCollectorResult

```python
@dataclass
class SSHCollectorResult:
    success: bool
    neighbors: List[Neighbor]
    vendor: DeviceVendor
    raw_output: Dict[str, str]  # command -> output
    errors: List[str]
    duration_ms: float
```

## Adding Custom Templates

1. **Embedded**: Add to `EMBEDDED_TEMPLATES` dict in `parsers.py`
2. **Database**: Use `tfsm_templates.db` with `--template-db` option

Template format follows TextFSM specification:
```
Value Required HOSTNAME (\S+)
Value IP_ADDRESS (\d+\.\d+\.\d+\.\d+)

Start
  ^Device ID: ${HOSTNAME}
  ^  IP address: ${IP_ADDRESS} -> Record
```

## Dependencies

```
paramiko>=2.7
textfsm>=1.1
```

## Lineage

Adapted from VCollector's SSH infrastructure:
- `ssh_client.py` → `client.py`
- `executor.py` → `collector.py`
- `tfsm_fire.py` + `tfsm_engine.py` → `parsers.py`

Key improvements:
- Simplified for single-device discovery (no ThreadPoolExecutor needed here)
- Embedded templates (no external DB dependency)
- Returns `sc2.scng.discovery.models` objects for consistency with SNMP
