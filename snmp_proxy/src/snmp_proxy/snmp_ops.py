"""
Async SNMP operations using pysnmp-lextudio

Pure Python implementation - works on Windows, Linux, Mac without external tools.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable, Tuple

import warnings

# Suppress pysnmp deprecation warnings
warnings.filterwarnings("ignore", message=".*pysnmp.*deprecated.*")

from pysnmp.hlapi.asyncio import (
    SnmpEngine,
    CommunityData,
    UsmUserData,
    UdpTransportTarget,
    ContextData,
    ObjectType,
    ObjectIdentity,
    get_cmd,      # snake_case in newer pysnmp
    walk_cmd,     # snake_case in newer pysnmp
    # Auth protocols
    usmHMACMD5AuthProtocol,
    usmHMACSHAAuthProtocol,
    usmHMAC128SHA224AuthProtocol,
    usmHMAC192SHA256AuthProtocol,
    usmHMAC256SHA384AuthProtocol,
    usmHMAC384SHA512AuthProtocol,
    usmNoAuthProtocol,
    # Priv protocols
    usmDESPrivProtocol,
    usm3DESEDEPrivProtocol,
    usmAesCfb128Protocol,
    usmAesCfb192Protocol,
    usmAesCfb256Protocol,
    usmNoPrivProtocol,
)

from .models import SNMPv3Auth


log = logging.getLogger("snmp_proxy.snmp")


# =============================================================================
# SNMPv3 Protocol Mappings
# =============================================================================

AUTH_PROTOCOLS = {
    "MD5": usmHMACMD5AuthProtocol,
    "SHA": usmHMACSHAAuthProtocol,
    "SHA224": usmHMAC128SHA224AuthProtocol,
    "SHA256": usmHMAC192SHA256AuthProtocol,
    "SHA384": usmHMAC256SHA384AuthProtocol,
    "SHA512": usmHMAC384SHA512AuthProtocol,
    "NONE": usmNoAuthProtocol,
}

PRIV_PROTOCOLS = {
    "DES": usmDESPrivProtocol,
    "3DES": usm3DESEDEPrivProtocol,
    "AES": usmAesCfb128Protocol,
    "AES128": usmAesCfb128Protocol,
    "AES192": usmAesCfb192Protocol,
    "AES256": usmAesCfb256Protocol,
    "NONE": usmNoPrivProtocol,
}


# =============================================================================
# Credential Builders
# =============================================================================

def build_credentials(version: str, community: str, v3_auth: Optional[SNMPv3Auth] = None):
    """Build pysnmp credentials based on SNMP version"""

    if version == "3" and v3_auth:
        auth_proto = AUTH_PROTOCOLS.get(v3_auth.auth_protocol.upper(), usmHMACSHAAuthProtocol)
        priv_proto = PRIV_PROTOCOLS.get(v3_auth.priv_protocol.upper(), usmAesCfb128Protocol)

        return UsmUserData(
            v3_auth.username,
            authKey=v3_auth.auth_password,
            privKey=v3_auth.priv_password,
            authProtocol=auth_proto,
            privProtocol=priv_proto,
        )
    else:
        # v1 or v2c
        mp_model = 1 if version == "2c" else 0
        return CommunityData(community, mpModel=mp_model)


# =============================================================================
# MAC Address Normalization
# =============================================================================

def mac_to_string(mac_value: Any) -> str:
    """
    Normalize MAC address to AA:BB:CC:DD:EE:FF format.

    Handles various pysnmp output formats:
    - Raw bytes
    - Hex string (0x...)
    - Space-separated hex
    - Colon-separated (possibly abbreviated)
    """
    if mac_value is None:
        return ""

    # Handle pysnmp OctetString - get raw bytes
    if hasattr(mac_value, 'asNumbers'):
        octets = mac_value.asNumbers()
        if len(octets) == 6:
            return ':'.join(f'{b:02X}' for b in octets)
        return ""

    # String representation
    clean = str(mac_value).strip()

    # Empty or placeholder
    if not clean or clean in ('', '""', "''"):
        return ""

    # Hex prefix: 0x001122334455
    if clean.startswith('0x'):
        hex_str = clean[2:].replace(' ', '')
        if len(hex_str) >= 12:
            return ':'.join([hex_str[i:i+2].upper() for i in range(0, 12, 2)])

    # Space-separated: "00 11 22 33 44 55"
    if ' ' in clean and ':' not in clean:
        parts = clean.split()
        if len(parts) == 6:
            return ':'.join(p.upper().zfill(2) for p in parts)

    # Colon-separated (may be abbreviated): "0:11:22:33:44:55"
    if ':' in clean:
        parts = clean.split(':')
        if len(parts) == 6:
            return ':'.join(p.upper().zfill(2) for p in parts)

    # Dash-separated: "00-11-22-33-44-55"
    if '-' in clean and len(clean) == 17:
        return clean.upper().replace('-', ':')

    # Raw 6-byte string (binary)
    if len(clean) == 6 and not clean.isalnum():
        try:
            return ':'.join(f'{ord(c):02X}' for c in clean)
        except (TypeError, ValueError):
            pass

    return clean


# =============================================================================
# Async SNMP Operations
# =============================================================================

async def snmp_get(
    target: str,
    oid: str,
    community: str = "public",
    version: str = "2c",
    port: int = 161,
    timeout: int = 10,
    v3_auth: Optional[SNMPv3Auth] = None,
) -> Tuple[bool, str, float]:
    """
    Async SNMP GET operation.

    Returns:
        (success, value_or_error, duration_seconds)
    """
    start = datetime.now()

    try:
        credentials = build_credentials(version, community, v3_auth)

        # Newer pysnmp requires async .create() for transport
        transport = await UdpTransportTarget.create(
            (target, port),
            timeout=timeout,
            retries=1
        )

        error_indication, error_status, error_index, var_binds = await get_cmd(
            SnmpEngine(),
            credentials,
            transport,
            ContextData(),
            ObjectType(ObjectIdentity(oid))
        )

        duration = (datetime.now() - start).total_seconds()

        if error_indication:
            log.debug(f"GET {target} {oid}: error_indication={error_indication}")
            return False, str(error_indication), duration

        if error_status:
            log.debug(f"GET {target} {oid}: error_status={error_status}")
            return False, f"{error_status.prettyPrint()} at {error_index}", duration

        for var_bind in var_binds:
            value = var_bind[1].prettyPrint()
            # Check for "no such" responses
            if value and "No Such" not in value:
                log.debug(f"GET {target} {oid}: value={value[:80]}")
                return True, value, duration

        return False, "No such object", duration

    except asyncio.TimeoutError:
        duration = (datetime.now() - start).total_seconds()
        return False, f"Timeout after {timeout}s", duration
    except Exception as e:
        duration = (datetime.now() - start).total_seconds()
        log.exception(f"GET {target} {oid}: exception")
        return False, str(e), duration


async def snmp_walk(
    target: str,
    oid: str,
    community: str = "public",
    version: str = "2c",
    port: int = 161,
    timeout: int = 120,
    v3_auth: Optional[SNMPv3Auth] = None,
    cancel_event: Optional[asyncio.Event] = None,
    progress_callback: Optional[Callable[[int], Any]] = None,
) -> Tuple[bool, List[Dict[str, Any]], float]:
    """
    Async SNMP WALK operation with cancellation and progress support.

    Returns:
        (success, results_list_or_error, duration_seconds)
    """
    start = datetime.now()
    results = []

    try:
        credentials = build_credentials(version, community, v3_auth)

        # Newer pysnmp requires async .create() for transport
        transport = await UdpTransportTarget.create(
            (target, port),
            timeout=timeout,
            retries=1
        )

        async for error_indication, error_status, error_index, var_binds in walk_cmd(
            SnmpEngine(),
            credentials,
            transport,
            ContextData(),
            ObjectType(ObjectIdentity(oid)),
            lexicographicMode=False,  # Stop at end of subtree
        ):
            # Check cancellation
            if cancel_event and cancel_event.is_set():
                duration = (datetime.now() - start).total_seconds()
                log.info(f"WALK {target} {oid}: cancelled after {len(results)} entries")
                return False, [], duration

            if error_indication:
                log.warning(f"WALK {target} {oid}: error_indication={error_indication}")
                break

            if error_status:
                log.warning(f"WALK {target} {oid}: error_status={error_status}")
                break

            for var_bind in var_binds:
                results.append({
                    'oid': str(var_bind[0]),
                    'value': var_bind[1],  # Keep raw for MAC processing
                    'value_str': var_bind[1].prettyPrint(),
                })

            # Progress callback every 50 entries
            if progress_callback and len(results) % 50 == 0:
                try:
                    result = progress_callback(len(results))
                    if asyncio.iscoroutine(result):
                        await result
                except Exception:
                    pass

        duration = (datetime.now() - start).total_seconds()
        log.debug(f"WALK {target} {oid}: {len(results)} entries in {duration:.1f}s")
        return True, results, duration

    except asyncio.TimeoutError:
        duration = (datetime.now() - start).total_seconds()
        return False, f"Timeout after {timeout}s", duration
    except Exception as e:
        duration = (datetime.now() - start).total_seconds()
        log.exception(f"WALK {target} {oid}: exception")
        return False, str(e), duration


# =============================================================================
# System OIDs
# =============================================================================

SYSTEM_OIDS = {
    'sysDescr': '1.3.6.1.2.1.1.1.0',
    'sysObjectID': '1.3.6.1.2.1.1.2.0',
    'sysName': '1.3.6.1.2.1.1.5.0',
    'sysContact': '1.3.6.1.2.1.1.4.0',
    'sysLocation': '1.3.6.1.2.1.1.6.0',
    'sysUpTime': '1.3.6.1.2.1.1.3.0',
}

# Interface table OIDs
IF_DESCR_OID = '1.3.6.1.2.1.2.2.1.2'       # ifDescr
IF_PHYS_ADDR_OID = '1.3.6.1.2.1.2.2.1.6'   # ifPhysAddress

# ARP/Neighbor table OIDs
ARP_PHYS_ADDR_OID = '1.3.6.1.2.1.4.22.1.2'  # ipNetToMediaPhysAddress
ARP_NET_ADDR_OID = '1.3.6.1.2.1.4.22.1.3'   # ipNetToMediaNetAddress