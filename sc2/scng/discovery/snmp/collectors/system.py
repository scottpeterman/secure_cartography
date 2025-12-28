"""
SecureCartography NG - System Info Collector.

Collects system MIB information (sysDescr, sysName, etc.).
"""

from typing import Optional, Dict, Any

from pysnmp.hlapi.v3arch.asyncio import SnmpEngine

from ...oids import SYSTEM
from ...models import DeviceVendor
from ..walker import SNMPWalker, AuthData
from ..parsers import decode_string, decode_int, detect_vendor


async def get_system_info(
    target: str,
    auth: AuthData,
    engine: Optional[SnmpEngine] = None,
    timeout: float = 5.0,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Get system MIB information from device.
    
    Queries SNMPv2-MIB system group for basic device information.
    
    Args:
        target: Device IP address
        auth: SNMP authentication data
        engine: Optional shared SnmpEngine
        timeout: Request timeout
        verbose: Enable debug output
    
    Returns:
        Dictionary with keys:
            - sys_descr: System description
            - sys_name: System name
            - sys_location: Physical location
            - sys_contact: Contact person
            - sys_object_id: Vendor OID
            - uptime_ticks: Uptime in hundredths of seconds
            - vendor: Detected DeviceVendor enum
    
    Example:
        info = await get_system_info("192.168.1.1", CommunityData("public"))
        print(f"Device: {info['sys_name']} ({info['vendor']})")
    """
    walker = SNMPWalker(
        engine=engine,
        auth=auth,
        default_timeout=timeout,
        verbose=verbose
    )
    
    # Get all system scalars in one request
    oids = [
        SYSTEM.SYS_DESCR,
        SYSTEM.SYS_NAME,
        SYSTEM.SYS_LOCATION,
        SYSTEM.SYS_CONTACT,
        SYSTEM.SYS_OBJECT_ID,
        SYSTEM.SYS_UPTIME,
    ]
    
    values = await walker.get_multiple(target, oids, auth)
    
    result = {
        'sys_descr': None,
        'sys_name': None,
        'sys_location': None,
        'sys_contact': None,
        'sys_object_id': None,
        'uptime_ticks': None,
        'vendor': DeviceVendor.UNKNOWN,
    }
    
    if values[0]:
        result['sys_descr'] = decode_string(values[0])
        result['vendor'] = detect_vendor(result['sys_descr'])
    
    if values[1]:
        result['sys_name'] = decode_string(values[1])
    
    if values[2]:
        result['sys_location'] = decode_string(values[2])
    
    if values[3]:
        result['sys_contact'] = decode_string(values[3])
    
    if values[4]:
        result['sys_object_id'] = decode_string(values[4])
    
    if values[5]:
        result['uptime_ticks'] = decode_int(values[5])
    
    return result


async def get_sys_name(
    target: str,
    auth: AuthData,
    engine: Optional[SnmpEngine] = None,
    timeout: float = 3.0,
) -> Optional[str]:
    """
    Quick sysName lookup.
    
    Used for resolving IP addresses to hostnames during discovery.
    """
    walker = SNMPWalker(engine=engine, auth=auth, default_timeout=timeout)
    value = await walker.get(target, SYSTEM.SYS_NAME, auth)
    
    if value:
        return decode_string(value)
    return None


async def get_sys_descr(
    target: str,
    auth: AuthData,
    engine: Optional[SnmpEngine] = None,
    timeout: float = 3.0,
) -> Optional[str]:
    """
    Quick sysDescr lookup.
    
    Used for vendor detection during discovery.
    """
    walker = SNMPWalker(engine=engine, auth=auth, default_timeout=timeout)
    value = await walker.get(target, SYSTEM.SYS_DESCR, auth)
    
    if value:
        return decode_string(value)
    return None


async def detect_device_vendor(
    target: str,
    auth: AuthData,
    engine: Optional[SnmpEngine] = None,
    timeout: float = 3.0,
) -> tuple[DeviceVendor, Optional[str]]:
    """
    Detect device vendor from sysDescr.
    
    Returns:
        Tuple of (DeviceVendor, sysDescr string or None)
    """
    sys_descr = await get_sys_descr(target, auth, engine, timeout)
    vendor = detect_vendor(sys_descr)
    return vendor, sys_descr
