"""
SecureCartography NG - Network Discovery Module.

SNMP-first network discovery with SSH fallback, integrated with
scng.creds vault for credential management.

Architecture:
    discovery/
    ├── models.py      # Device, Interface, Neighbor dataclasses
    ├── oids.py        # SNMP OID constants
    ├── engine.py      # High-level discovery orchestration
    ├── cli.py         # CLI interface
    └── snmp/          # SNMP-based discovery
        ├── walker.py  # Async SNMP GETBULK
        ├── parsers.py # Value decoding
        └── collectors/
            ├── system.py     # sysDescr, sysName
            ├── interfaces.py # IF-MIB
            ├── cdp.py        # CISCO-CDP-MIB
            ├── lldp.py       # LLDP-MIB
            └── arp.py        # ARP table

Usage:
    from sc2.scng.discovery import Device, Neighbor, DiscoveryResult
    from sc2.scng.discovery.snmp import (
        get_system_info,
        get_interface_table,
        get_cdp_neighbors,
        get_lldp_neighbors,
    )

Quick Start:
    # With vault integration
    from scng.creds import CredentialVault
    from sc2.scng.discovery import discover_device
    
    vault = CredentialVault()
    vault.unlock("password")
    
    device = await discover_device("192.168.1.1", vault)
    print(f"Found {len(device.neighbors)} neighbors")
"""

from .models import (
    Device,
    Interface,
    Neighbor,
    DiscoveryResult,
    DiscoveryProtocol,
    NeighborProtocol,
    InterfaceStatus,
    DeviceVendor,
)

from .oids import (
    SYSTEM,
    INTERFACES,
    CDP,
    LLDP,
    ARP,
    ENTITY,
)

from .engine import (
    DiscoveryEngine,
    discover_device,
)


__all__ = [
    # Engine
    'DiscoveryEngine',
    'discover_device',
    # Models
    'Device',
    'Interface',
    'Neighbor',
    'DiscoveryResult',
    'DiscoveryProtocol',
    'NeighborProtocol',
    'InterfaceStatus',
    'DeviceVendor',
    # OID groups
    'SYSTEM',
    'INTERFACES',
    'CDP',
    'LLDP',
    'ARP',
    'ENTITY',
]
