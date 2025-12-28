"""
SecureCartography NG - SNMP Collectors.

Individual collectors for different MIB data:
- system: SNMPv2-MIB system group
- interfaces: IF-MIB interface table
- cdp: CISCO-CDP-MIB neighbors
- lldp: LLDP-MIB neighbors
- arp: IP-MIB ARP table
"""

from .system import (
    get_system_info,
    get_sys_name,
    get_sys_descr,
    detect_device_vendor,
)

from .interfaces import (
    get_interface_table,
    get_interface_table_extended,
    build_interface_lookup,
    resolve_interface_name,
)

from .cdp import (
    get_cdp_neighbors,
    get_cdp_neighbors_raw,
)

from .lldp import (
    get_lldp_neighbors,
    get_lldp_neighbors_raw,
)

from .arp import (
    get_arp_table,
    lookup_ip_by_mac,
)


__all__ = [
    # System
    'get_system_info',
    'get_sys_name',
    'get_sys_descr',
    'detect_device_vendor',
    # Interfaces
    'get_interface_table',
    'get_interface_table_extended',
    'build_interface_lookup',
    'resolve_interface_name',
    # CDP
    'get_cdp_neighbors',
    'get_cdp_neighbors_raw',
    # LLDP
    'get_lldp_neighbors',
    'get_lldp_neighbors_raw',
    # ARP
    'get_arp_table',
    'lookup_ip_by_mac',
]
