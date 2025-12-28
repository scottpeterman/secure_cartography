"""
SecureCartography NG - ARP Table Collector.

Collects ARP table (MAC to IP mapping) from devices.
Used as fallback for LLDP neighbors without management addresses.
"""

from typing import Optional, Dict

from pysnmp.hlapi.v3arch.asyncio import SnmpEngine

from ...oids import ARP
from ..walker import SNMPWalker, AuthData
from ..parsers import decode_mac, is_valid_ipv4


async def get_arp_table(
    target: str,
    auth: AuthData,
    engine: Optional[SnmpEngine] = None,
    timeout: float = 5.0,
    verbose: bool = False,
) -> Dict[str, str]:
    """
    Get ARP table from device.
    
    Queries ipNetToMediaPhysAddress for MAC-to-IP mappings.
    
    Args:
        target: Device IP address
        auth: SNMP authentication data
        engine: Optional shared SnmpEngine
        timeout: Request timeout
        verbose: Enable debug output
    
    Returns:
        Dict mapping MAC addresses (lowercase, colon-separated) to IP addresses
    
    Example:
        arp = await get_arp_table("192.168.1.1", auth)
        ip = arp.get("aa:bb:cc:dd:ee:ff")
    """
    walker = SNMPWalker(
        engine=engine,
        auth=auth,
        default_timeout=timeout,
        verbose=verbose
    )
    
    def _vprint(msg: str):
        if verbose:
            print(f"  [arp] {msg}")
    
    mac_to_ip: Dict[str, str] = {}
    
    # OID: ipNetToMediaPhysAddress
    # Index: ifIndex.ip1.ip2.ip3.ip4
    # Value: MAC address (binary)
    _vprint(f"Querying ARP table: {ARP.NET_TO_MEDIA_PHYS_ADDRESS}")
    
    results = await walker.walk(target, ARP.NET_TO_MEDIA_PHYS_ADDRESS, auth)
    
    for oid, value in results:
        try:
            # Extract IP from OID (last 4 octets)
            parts = oid.split('.')
            if len(parts) >= 4:
                ip_parts = parts[-4:]
                
                # Validate IP octets
                if all(0 <= int(p) <= 255 for p in ip_parts):
                    ip_addr = '.'.join(ip_parts)
                    
                    # Decode MAC address
                    mac = decode_mac(value)
                    
                    if mac and ':' in mac:
                        mac_lower = mac.lower()
                        mac_to_ip[mac_lower] = ip_addr
                        
                        if verbose:
                            _vprint(f"  {mac_lower} -> {ip_addr}")
        
        except (ValueError, IndexError):
            continue
    
    _vprint(f"Found {len(mac_to_ip)} ARP entries")
    return mac_to_ip


def lookup_ip_by_mac(
    mac: str,
    arp_table: Dict[str, str],
) -> Optional[str]:
    """
    Look up IP address by MAC address.
    
    Normalizes MAC format before lookup.
    
    Args:
        mac: MAC address (any format)
        arp_table: Dict from get_arp_table()
    
    Returns:
        IP address or None if not found
    """
    if not mac or not arp_table:
        return None
    
    # Normalize MAC to lowercase colon-separated
    mac_clean = mac.replace('-', ':').replace('.', '').lower()
    
    # If it's in hex-only format, add colons
    if ':' not in mac_clean and len(mac_clean) == 12:
        mac_clean = ':'.join(mac_clean[i:i+2] for i in range(0, 12, 2))
    
    return arp_table.get(mac_clean)
