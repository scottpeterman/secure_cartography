"""
SecureCartography NG - SNMP Discovery Module.

Async SNMP-based network discovery using pysnmp.

Components:
- walker: Core SNMP GETBULK implementation
- parsers: Value decoding (MAC, IP, LLDP subtypes, etc.)
- collectors: MIB-specific data collection
  - system: sysDescr, sysName, etc.
  - interfaces: ifName, ifDescr, ifAlias
  - cdp: Cisco Discovery Protocol neighbors
  - lldp: Link Layer Discovery Protocol neighbors
  - arp: ARP table for MAC-to-IP resolution

Usage:
    from sc2.scng.discovery.snmp import SNMPWalker
    from sc2.scng.discovery.snmp.collectors import (
        get_system_info,
        get_interface_table,
        get_cdp_neighbors,
        get_lldp_neighbors,
    )
    
    # Create walker with auth
    from pysnmp.hlapi.v3arch.asyncio import CommunityData
    auth = CommunityData("public", mpModel=1)
    
    # Collect device data
    sys_info = await get_system_info("192.168.1.1", auth)
    interfaces = await get_interface_table("192.168.1.1", auth)
    cdp = await get_cdp_neighbors("192.168.1.1", auth, interfaces)
    lldp = await get_lldp_neighbors("192.168.1.1", auth, interfaces)
"""

from .walker import SNMPWalker, snmp_walk, snmp_get, AuthData
from .parsers import (
    decode_mac,
    decode_ip,
    decode_string,
    decode_int,
    decode_chassis_id,
    decode_port_id,
    detect_vendor,
    should_exclude,
    is_valid_ipv4,
    is_ip_address,
    normalize_mac,
    extract_hostname,
    build_fqdn,
)

from .collectors import (
    get_system_info,
    get_sys_name,
    get_sys_descr,
    detect_device_vendor,
    get_interface_table,
    get_interface_table_extended,
    get_cdp_neighbors,
    get_lldp_neighbors,
    get_arp_table,
    lookup_ip_by_mac,
)


__all__ = [
    # Walker
    'SNMPWalker',
    'snmp_walk',
    'snmp_get',
    'AuthData',
    # Parsers
    'decode_mac',
    'decode_ip',
    'decode_string',
    'decode_int',
    'decode_chassis_id',
    'decode_port_id',
    'detect_vendor',
    'should_exclude',
    'is_valid_ipv4',
    'is_ip_address',
    'normalize_mac',
    'extract_hostname',
    'build_fqdn',
    # Collectors
    'get_system_info',
    'get_sys_name',
    'get_sys_descr',
    'detect_device_vendor',
    'get_interface_table',
    'get_interface_table_extended',
    'get_cdp_neighbors',
    'get_lldp_neighbors',
    'get_arp_table',
    'lookup_ip_by_mac',
]
