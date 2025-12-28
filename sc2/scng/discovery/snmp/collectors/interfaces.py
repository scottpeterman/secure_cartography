"""
SecureCartography NG - Interface Table Collector.

Collects interface information from IF-MIB (ifName, ifDescr, ifAlias).
Used for resolving ifIndex references in CDP/LLDP tables.
"""

from typing import Optional, Dict, List

from pysnmp.hlapi.v3arch.asyncio import SnmpEngine

from ...oids import INTERFACES
from ...models import Interface, InterfaceStatus
from ..walker import SNMPWalker, AuthData
from ..parsers import decode_string, decode_int, decode_mac


async def get_interface_table(
    target: str,
    auth: AuthData,
    engine: Optional[SnmpEngine] = None,
    timeout: float = 5.0,
    verbose: bool = False,
) -> Dict[int, Interface]:
    """
    Get interface table from device.
    
    Queries IF-MIB for interface information, returning a dict
    keyed by ifIndex for fast lookups during neighbor processing.
    
    Args:
        target: Device IP address
        auth: SNMP authentication data
        engine: Optional shared SnmpEngine
        timeout: Request timeout per table
        verbose: Enable debug output
    
    Returns:
        Dict mapping ifIndex (int) to Interface dataclass
    
    Example:
        interfaces = await get_interface_table("192.168.1.1", auth)
        for if_index, iface in interfaces.items():
            print(f"{if_index}: {iface.name} - {iface.alias}")
    """
    walker = SNMPWalker(
        engine=engine,
        auth=auth,
        default_timeout=timeout,
        verbose=verbose
    )
    
    interfaces: Dict[int, Interface] = {}
    
    def _vprint(msg: str):
        if verbose:
            print(f"  [interfaces] {msg}")
    
    # Query ifName (preferred short name like "Gi0/1")
    _vprint("Querying ifName...")
    results = await walker.walk(target, INTERFACES.IF_NAME, auth)
    
    for oid, value in results:
        try:
            if_index = int(oid.split('.')[-1])
            name = decode_string(value)
            if if_index not in interfaces:
                interfaces[if_index] = Interface(name=name, if_index=if_index)
            else:
                interfaces[if_index].name = name
        except (ValueError, IndexError):
            continue
    
    _vprint(f"  Got {len(results)} ifName entries")
    
    # Query ifDescr (often same as ifName, but sometimes more descriptive)
    _vprint("Querying ifDescr...")
    results = await walker.walk(target, INTERFACES.IF_DESCR, auth)
    
    for oid, value in results:
        try:
            if_index = int(oid.split('.')[-1])
            descr = decode_string(value)
            if if_index not in interfaces:
                # Use ifDescr as name if ifName wasn't present
                interfaces[if_index] = Interface(name=descr, if_index=if_index, description=descr)
            else:
                interfaces[if_index].description = descr
        except (ValueError, IndexError):
            continue
    
    _vprint(f"  Got {len(results)} ifDescr entries")
    
    # Query ifAlias (user-configured description)
    _vprint("Querying ifAlias...")
    results = await walker.walk(target, INTERFACES.IF_ALIAS, auth)
    
    for oid, value in results:
        try:
            if_index = int(oid.split('.')[-1])
            alias = decode_string(value)
            if alias and if_index in interfaces:
                interfaces[if_index].alias = alias
        except (ValueError, IndexError):
            continue
    
    _vprint(f"  Got {len(results)} ifAlias entries")
    
    _vprint(f"Total interfaces: {len(interfaces)}")
    return interfaces


async def get_interface_table_extended(
    target: str,
    auth: AuthData,
    engine: Optional[SnmpEngine] = None,
    timeout: float = 5.0,
    verbose: bool = False,
) -> Dict[int, Interface]:
    """
    Get extended interface table including status and MAC.
    
    Includes additional fields beyond basic get_interface_table:
    - ifOperStatus (up/down/admin-down)
    - ifPhysAddress (MAC)
    - ifHighSpeed (Mbps)
    - ifMtu
    
    Slower than get_interface_table due to additional walks.
    Use when full interface details are needed.
    """
    # Start with basic interface table
    interfaces = await get_interface_table(target, auth, engine, timeout, verbose)
    
    if not interfaces:
        return interfaces
    
    walker = SNMPWalker(
        engine=engine,
        auth=auth,
        default_timeout=timeout,
        verbose=verbose
    )
    
    def _vprint(msg: str):
        if verbose:
            print(f"  [interfaces] {msg}")
    
    # Query ifOperStatus
    _vprint("Querying ifOperStatus...")
    results = await walker.walk(target, INTERFACES.IF_OPER_STATUS, auth)
    
    for oid, value in results:
        try:
            if_index = int(oid.split('.')[-1])
            status_int = decode_int(value)
            
            if if_index in interfaces and status_int is not None:
                if status_int == INTERFACES.OPER_STATUS_UP:
                    interfaces[if_index].status = InterfaceStatus.UP
                elif status_int == INTERFACES.OPER_STATUS_DOWN:
                    interfaces[if_index].status = InterfaceStatus.DOWN
                elif status_int == INTERFACES.OPER_STATUS_LOWER_LAYER_DOWN:
                    interfaces[if_index].status = InterfaceStatus.ADMIN_DOWN
                else:
                    interfaces[if_index].status = InterfaceStatus.UNKNOWN
        except (ValueError, IndexError):
            continue
    
    # Query ifPhysAddress (MAC)
    _vprint("Querying ifPhysAddress...")
    results = await walker.walk(target, INTERFACES.IF_PHYS_ADDRESS, auth)
    
    for oid, value in results:
        try:
            if_index = int(oid.split('.')[-1])
            mac = decode_mac(value)
            
            if if_index in interfaces and mac and ':' in mac:
                interfaces[if_index].mac_address = mac
        except (ValueError, IndexError):
            continue
    
    # Query ifHighSpeed (Mbps)
    _vprint("Querying ifHighSpeed...")
    results = await walker.walk(target, INTERFACES.IF_HIGH_SPEED, auth)
    
    for oid, value in results:
        try:
            if_index = int(oid.split('.')[-1])
            speed = decode_int(value)
            
            if if_index in interfaces and speed is not None:
                interfaces[if_index].speed_mbps = speed
        except (ValueError, IndexError):
            continue
    
    # Query ifMtu
    _vprint("Querying ifMtu...")
    results = await walker.walk(target, INTERFACES.IF_MTU, auth)
    
    for oid, value in results:
        try:
            if_index = int(oid.split('.')[-1])
            mtu = decode_int(value)
            
            if if_index in interfaces and mtu is not None:
                interfaces[if_index].mtu = mtu
        except (ValueError, IndexError):
            continue
    
    return interfaces


def build_interface_lookup(interfaces: Dict[int, Interface]) -> Dict[int, str]:
    """
    Build simple ifIndex -> name lookup from interface table.
    
    Prefers ifName, falls back to ifDescr, then to "ifIndex_N".
    """
    lookup: Dict[int, str] = {}
    
    for if_index, iface in interfaces.items():
        lookup[if_index] = iface.name or iface.description or f"ifIndex_{if_index}"
    
    return lookup


def resolve_interface_name(
    if_index: int,
    interfaces: Dict[int, Interface],
) -> str:
    """
    Resolve ifIndex to interface name.
    
    Falls back to "ifIndex_N" if not found.
    """
    if if_index in interfaces:
        iface = interfaces[if_index]
        return iface.name or iface.description or f"ifIndex_{if_index}"
    return f"ifIndex_{if_index}"
