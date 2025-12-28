"""
SecureCartography NG - CDP Neighbor Collector.

Collects CDP (Cisco Discovery Protocol) neighbor information.
CDP is Cisco-proprietary but widely supported.
"""

from typing import Optional, Dict, List

from pysnmp.hlapi.v3arch.asyncio import SnmpEngine

from ...oids import CDP
from ...models import Interface, Neighbor, NeighborProtocol
from ..walker import SNMPWalker, AuthData
from ..parsers import decode_string, decode_ip
from .interfaces import resolve_interface_name


async def get_cdp_neighbors(
    target: str,
    auth: AuthData,
    interface_table: Optional[Dict[int, Interface]] = None,
    engine: Optional[SnmpEngine] = None,
    timeout: float = 5.0,
    verbose: bool = False,
) -> List[Neighbor]:
    """
    Get CDP neighbors from device.
    
    Queries CISCO-CDP-MIB for neighbor information. Uses the interface
    table to resolve local ifIndex to interface names.
    
    Args:
        target: Device IP address
        auth: SNMP authentication data
        interface_table: Pre-fetched interface table for name resolution
        engine: Optional shared SnmpEngine
        timeout: Request timeout per table
        verbose: Enable debug output
    
    Returns:
        List of Neighbor dataclasses
    
    Example:
        neighbors = await get_cdp_neighbors("192.168.1.1", auth, interfaces)
        for n in neighbors:
            print(f"{n.local_interface} -> {n.remote_device} ({n.remote_interface})")
    """
    walker = SNMPWalker(
        engine=engine,
        auth=auth,
        default_timeout=timeout,
        verbose=verbose
    )
    
    def _vprint(msg: str):
        if verbose:
            print(f"  [cdp] {msg}")
    
    # Temporary storage keyed by CDP index (ifIndex.deviceIndex)
    neighbors_raw: Dict[str, Dict] = {}
    
    # Query cdpCacheDeviceId first to establish entries
    _vprint("Querying cdpCacheDeviceId...")
    results = await walker.walk(target, CDP.CACHE_DEVICE_ID, auth)
    
    if not results:
        _vprint("No CDP data available")
        return []
    
    for oid, value in results:
        device_id = decode_string(value)
        
        # Skip empty or invalid entries
        if not device_id or device_id in ['', '(', '(\x00', 'CW_']:
            continue
        
        # Extract index from OID: base.ifIndex.deviceIndex
        parts = oid.split('.')
        if len(parts) >= 2:
            if_index = int(parts[-2])
            index = f"{parts[-2]}.{parts[-1]}"
            
            neighbors_raw[index] = {
                'index': index,
                'if_index': if_index,
                'device_id': device_id,
            }
    
    _vprint(f"Found {len(neighbors_raw)} CDP entries")
    
    if not neighbors_raw:
        return []
    
    # Query cdpCacheDevicePort (remote port)
    _vprint("Querying cdpCacheDevicePort...")
    results = await walker.walk(target, CDP.CACHE_DEVICE_PORT, auth)
    
    for oid, value in results:
        parts = oid.split('.')
        if len(parts) >= 2:
            index = f"{parts[-2]}.{parts[-1]}"
            if index in neighbors_raw:
                neighbors_raw[index]['remote_port'] = decode_string(value)
    
    # Query cdpCacheAddress (IP address - binary encoded)
    _vprint("Querying cdpCacheAddress...")
    results = await walker.walk(target, CDP.CACHE_ADDRESS, auth)
    
    for oid, value in results:
        parts = oid.split('.')
        if len(parts) >= 2:
            index = f"{parts[-2]}.{parts[-1]}"
            if index in neighbors_raw:
                ip_addr = decode_ip(value)
                # Validate it looks like an IP
                if ip_addr and '.' in ip_addr:
                    ip_parts = ip_addr.split('.')
                    if len(ip_parts) == 4:
                        try:
                            if all(0 <= int(p) <= 255 for p in ip_parts):
                                neighbors_raw[index]['ip_address'] = ip_addr
                        except ValueError:
                            pass
    
    # Query cdpCachePlatform
    _vprint("Querying cdpCachePlatform...")
    results = await walker.walk(target, CDP.CACHE_PLATFORM, auth)
    
    for oid, value in results:
        parts = oid.split('.')
        if len(parts) >= 2:
            index = f"{parts[-2]}.{parts[-1]}"
            if index in neighbors_raw:
                neighbors_raw[index]['platform'] = decode_string(value)
    
    # Query cdpCacheVersion (software version string)
    _vprint("Querying cdpCacheVersion...")
    results = await walker.walk(target, CDP.CACHE_VERSION, auth)
    
    for oid, value in results:
        parts = oid.split('.')
        if len(parts) >= 2:
            index = f"{parts[-2]}.{parts[-1]}"
            if index in neighbors_raw:
                neighbors_raw[index]['version'] = decode_string(value)
    
    # Convert to Neighbor objects
    neighbors: List[Neighbor] = []
    
    for index, data in neighbors_raw.items():
        device_id = data.get('device_id', '')
        
        # Skip entries with no meaningful device ID
        if not device_id or device_id in ['', 'N/A', 'n/a']:
            # But keep if we have an IP address
            if 'ip_address' not in data:
                continue
            device_id = data.get('ip_address', '')
        
        # Resolve local interface name
        if_index = data.get('if_index', 0)
        if interface_table:
            local_interface = resolve_interface_name(if_index, interface_table)
        else:
            local_interface = f"ifIndex_{if_index}"
        
        neighbor = Neighbor.from_cdp(
            local_interface=local_interface,
            device_id=device_id,
            remote_port=data.get('remote_port', ''),
            ip_address=data.get('ip_address'),
            platform=data.get('platform'),
            local_if_index=if_index,
            raw_index=index,
        )
        
        # Add version to description if present
        if data.get('version'):
            neighbor.remote_description = data['version']
        
        neighbors.append(neighbor)
    
    _vprint(f"Returning {len(neighbors)} valid CDP neighbors")
    return neighbors


async def get_cdp_neighbors_raw(
    target: str,
    auth: AuthData,
    engine: Optional[SnmpEngine] = None,
    timeout: float = 5.0,
    verbose: bool = False,
) -> Dict[str, Dict]:
    """
    Get raw CDP neighbor data as dictionaries.
    
    Returns dict keyed by CDP index with all collected fields.
    Useful for debugging or custom processing.
    """
    walker = SNMPWalker(
        engine=engine,
        auth=auth,
        default_timeout=timeout,
        verbose=verbose
    )
    
    neighbors: Dict[str, Dict] = {}
    
    # CDP cache columns to query
    columns = [
        (CDP.CACHE_DEVICE_ID, 'device_id'),
        (CDP.CACHE_DEVICE_PORT, 'remote_port'),
        (CDP.CACHE_ADDRESS, 'ip_address'),
        (CDP.CACHE_PLATFORM, 'platform'),
        (CDP.CACHE_VERSION, 'version'),
        (CDP.CACHE_CAPABILITIES, 'capabilities'),
        (CDP.CACHE_NATIVE_VLAN, 'native_vlan'),
    ]
    
    for oid_base, field_name in columns:
        results = await walker.walk(target, oid_base, auth)
        
        for oid, value in results:
            parts = oid.split('.')
            if len(parts) >= 2:
                index = f"{parts[-2]}.{parts[-1]}"
                
                if index not in neighbors:
                    neighbors[index] = {
                        'index': index,
                        'if_index': int(parts[-2]),
                    }
                
                # Special handling for IP address
                if field_name == 'ip_address':
                    neighbors[index][field_name] = decode_ip(value)
                else:
                    neighbors[index][field_name] = decode_string(value)
    
    return neighbors
