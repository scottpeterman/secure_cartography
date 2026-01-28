"""
Local SNMP Operations - Pure Python async implementation

Windows-native, cross-platform SNMP using pysnmp-lextudio.
Replaces subprocess calls to net-snmp tools.

Usage:
    This module provides async SNMP operations that can be run
    from a QThread using asyncio.run() or a dedicated event loop.
"""

import asyncio
import logging
import warnings
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple, Callable
from dataclasses import dataclass, field

# Suppress pysnmp deprecation warnings
warnings.filterwarnings("ignore", message=".*pysnmp.*deprecated.*")

try:
    from pysnmp.hlapi.asyncio import (
        SnmpEngine,
        CommunityData,
        UsmUserData,
        UdpTransportTarget,
        ContextData,
        ObjectType,
        ObjectIdentity,
        get_cmd,
        walk_cmd,
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
    PYSNMP_AVAILABLE = True
except ImportError:
    PYSNMP_AVAILABLE = False


log = logging.getLogger("local_snmp")


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class SNMPv3Auth:
    """SNMPv3 authentication parameters"""
    username: str
    auth_protocol: str = "SHA"  # MD5, SHA, SHA224, SHA256, SHA384, SHA512, NONE
    auth_password: Optional[str] = None
    priv_protocol: str = "AES"  # DES, 3DES, AES, AES128, AES192, AES256, NONE
    priv_password: Optional[str] = None


@dataclass
class SNMPConfig:
    """SNMP connection configuration"""
    target: str
    community: str = "public"
    version: str = "2c"  # 1, 2c, or 3
    port: int = 161
    v3_auth: Optional[SNMPv3Auth] = None
    get_timeout: int = 10
    walk_timeout: int = 120
    retries: int = 1


@dataclass
class LocalPollResult:
    """Results from local SNMP poll operations"""
    success: bool = False
    error: str = ""
    snmp_data: Dict[str, str] = field(default_factory=dict)
    interfaces: List[Dict] = field(default_factory=list)
    arp_table: List[Dict] = field(default_factory=list)
    timing: Dict[str, float] = field(default_factory=dict)


# =============================================================================
# Protocol Mappings (for SNMPv3)
# =============================================================================

if PYSNMP_AVAILABLE:
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
else:
    AUTH_PROTOCOLS = {}
    PRIV_PROTOCOLS = {}


# =============================================================================
# OID Constants
# =============================================================================

SYSTEM_OIDS = {
    'sysDescr': '1.3.6.1.2.1.1.1.0',
    'sysObjectID': '1.3.6.1.2.1.1.2.0',
    'sysName': '1.3.6.1.2.1.1.5.0',
    'sysContact': '1.3.6.1.2.1.1.4.0',
    'sysLocation': '1.3.6.1.2.1.1.6.0',
    'sysUpTime': '1.3.6.1.2.1.1.3.0',
}

INTERFACE_OIDS = {
    'ifDescr': '1.3.6.1.2.1.2.2.1.2',
    'ifPhysAddress': '1.3.6.1.2.1.2.2.1.6',
}

ARP_OIDS = {
    'ipNetToMediaPhysAddress': '1.3.6.1.2.1.4.22.1.2',
    'ipNetToMediaNetAddress': '1.3.6.1.2.1.4.22.1.3',
}


# =============================================================================
# Credential Builder
# =============================================================================

def build_credentials(config: SNMPConfig):
    """Build pysnmp credentials based on SNMP version"""
    if not PYSNMP_AVAILABLE:
        raise RuntimeError("pysnmp-lextudio is not installed")

    if config.version == "3" and config.v3_auth:
        auth = config.v3_auth
        auth_proto = AUTH_PROTOCOLS.get(
            auth.auth_protocol.upper(), usmHMACSHAAuthProtocol
        )
        priv_proto = PRIV_PROTOCOLS.get(
            auth.priv_protocol.upper(), usmAesCfb128Protocol
        )

        return UsmUserData(
            auth.username,
            authKey=auth.auth_password,
            privKey=auth.priv_password,
            authProtocol=auth_proto,
            privProtocol=priv_proto,
        )
    else:
        # v1 or v2c
        mp_model = 1 if config.version == "2c" else 0
        return CommunityData(config.community, mpModel=mp_model)


# =============================================================================
# MAC Address Normalization
# =============================================================================

def mac_to_string(mac_value: Any) -> str:
    """
    Normalize MAC address to AA:BB:CC:DD:EE:FF format.

    Handles various pysnmp output formats:
    - Raw bytes via asNumbers()
    - Hex string (0x...)
    - Space-separated hex
    - Colon-separated (possibly abbreviated)
    - Dash-separated
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
    config: SNMPConfig,
    oid: str,
) -> Tuple[bool, str, float]:
    """
    Async SNMP GET operation.

    Returns:
        (success, value_or_error, duration_seconds)
    """
    if not PYSNMP_AVAILABLE:
        return False, "pysnmp-lextudio not installed", 0.0

    start = datetime.now()

    try:
        credentials = build_credentials(config)

        # Create transport with async factory (required for newer pysnmp)
        transport = await UdpTransportTarget.create(
            (config.target, config.port),
            timeout=config.get_timeout,
            retries=config.retries
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
            log.debug(f"GET {config.target} {oid}: error_indication={error_indication}")
            return False, str(error_indication), duration

        if error_status:
            log.debug(f"GET {config.target} {oid}: error_status={error_status}")
            return False, f"{error_status.prettyPrint()} at {error_index}", duration

        for var_bind in var_binds:
            value = var_bind[1].prettyPrint()
            # Check for "no such" responses
            if value and "No Such" not in value:
                log.debug(f"GET {config.target} {oid}: value={value[:80]}")
                return True, value, duration

        return False, "No such object", duration

    except asyncio.TimeoutError:
        duration = (datetime.now() - start).total_seconds()
        return False, f"Timeout after {config.get_timeout}s", duration
    except asyncio.CancelledError:
        duration = (datetime.now() - start).total_seconds()
        return False, "Cancelled", duration
    except Exception as e:
        duration = (datetime.now() - start).total_seconds()
        log.exception(f"GET {config.target} {oid}: exception")
        return False, str(e), duration


async def snmp_walk(
    config: SNMPConfig,
    oid: str,
    cancel_event: Optional[asyncio.Event] = None,
    progress_callback: Optional[Callable[[int], Any]] = None,
) -> Tuple[bool, Any, float]:
    """
    Async SNMP WALK operation with cancellation and progress support.

    Returns:
        (success, results_list_or_error_string, duration_seconds)
    """
    if not PYSNMP_AVAILABLE:
        return False, "pysnmp-lextudio not installed", 0.0

    start = datetime.now()
    results = []

    try:
        credentials = build_credentials(config)

        # Create transport with async factory
        transport = await UdpTransportTarget.create(
            (config.target, config.port),
            timeout=config.walk_timeout,
            retries=config.retries
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
                log.info(f"WALK {config.target} {oid}: cancelled after {len(results)} entries")
                return False, "Cancelled", duration

            if error_indication:
                log.warning(f"WALK {config.target} {oid}: error_indication={error_indication}")
                break

            if error_status:
                log.warning(f"WALK {config.target} {oid}: error_status={error_status}")
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
        log.debug(f"WALK {config.target} {oid}: {len(results)} entries in {duration:.1f}s")
        return True, results, duration

    except asyncio.TimeoutError:
        duration = (datetime.now() - start).total_seconds()
        return False, f"Timeout after {config.walk_timeout}s", duration
    except asyncio.CancelledError:
        duration = (datetime.now() - start).total_seconds()
        return False, "Cancelled", duration
    except Exception as e:
        duration = (datetime.now() - start).total_seconds()
        log.exception(f"WALK {config.target} {oid}: exception")
        return False, str(e), duration


# =============================================================================
# High-Level Poll Operations
# =============================================================================

async def poll_system_info(
    config: SNMPConfig,
    cancel_event: Optional[asyncio.Event] = None,
    progress_callback: Optional[Callable[[str], Any]] = None,
) -> Tuple[bool, Dict[str, str], Dict[str, float]]:
    """
    Poll system OIDs (sysDescr, sysName, etc.)

    Returns:
        (success, snmp_data_dict, timing_dict)
    """
    snmp_data = {}
    timing = {}

    def emit_progress(msg: str):
        if progress_callback:
            try:
                result = progress_callback(msg)
                if asyncio.iscoroutine(result):
                    asyncio.create_task(result)
            except Exception:
                pass

    # First, check connectivity with sysName
    emit_progress(f"Checking SNMP connectivity to {config.target}...")

    success, value, duration = await snmp_get(config, SYSTEM_OIDS['sysName'])
    timing['sysName'] = duration

    if not success:
        return False, {}, timing

    snmp_data['sysName'] = value

    # Collect remaining system OIDs
    emit_progress("Collecting system information...")

    for name, oid in SYSTEM_OIDS.items():
        if cancel_event and cancel_event.is_set():
            return False, snmp_data, timing

        if name == 'sysName':  # Already got this one
            continue

        success, value, duration = await snmp_get(config, oid)
        timing[name] = duration

        if success:
            snmp_data[name] = value

    return True, snmp_data, timing


async def poll_interfaces(
    config: SNMPConfig,
    cancel_event: Optional[asyncio.Event] = None,
    progress_callback: Optional[Callable[[str], Any]] = None,
) -> Tuple[bool, List[Dict], float]:
    """
    Poll interface table (descriptions and MAC addresses)

    Returns:
        (success, interfaces_list, total_duration)
    """
    interfaces = []

    def emit_progress(msg: str):
        if progress_callback:
            try:
                result = progress_callback(msg)
                if asyncio.iscoroutine(result):
                    asyncio.create_task(result)
            except Exception:
                pass

    emit_progress("Collecting interface descriptions...")

    # Get interface descriptions
    success, if_descrs, descr_time = await snmp_walk(
        config, INTERFACE_OIDS['ifDescr'],
        cancel_event=cancel_event,
    )

    if not success or isinstance(if_descrs, str):
        return False, [], descr_time

    emit_progress(f"Found {len(if_descrs)} interfaces, collecting MAC addresses...")

    # Get interface MACs
    success, if_macs, mac_time = await snmp_walk(
        config, INTERFACE_OIDS['ifPhysAddress'],
        cancel_event=cancel_event,
    )

    total_time = descr_time + mac_time

    if not success or isinstance(if_macs, str):
        # Still return descriptions even if MACs failed
        for entry in if_descrs:
            interfaces.append({'description': entry['value_str']})
        return True, interfaces, total_time

    # Build interface list by matching indices
    # Extract index from OID: 1.3.6.1.2.1.2.2.1.2.X -> X
    descr_by_index = {}
    for entry in if_descrs:
        oid_parts = entry['oid'].split('.')
        if oid_parts:
            idx = oid_parts[-1]
            descr_by_index[idx] = entry['value_str']

    mac_by_index = {}
    for entry in if_macs:
        oid_parts = entry['oid'].split('.')
        if oid_parts:
            idx = oid_parts[-1]
            # Use raw value for MAC conversion (handles bytes properly)
            mac_by_index[idx] = mac_to_string(entry['value'])

    # Merge by index
    all_indices = sorted(set(descr_by_index.keys()) | set(mac_by_index.keys()), key=int)

    for idx in all_indices:
        iface = {}
        if idx in descr_by_index:
            iface['description'] = descr_by_index[idx]
        if idx in mac_by_index:
            mac = mac_by_index[idx]
            if mac and mac != '00:00:00:00:00:00' and len(mac) >= 12:
                iface['mac'] = mac
        if iface:  # Only add if we have some data
            interfaces.append(iface)

    return True, interfaces, total_time


async def poll_arp_table(
    config: SNMPConfig,
    cancel_event: Optional[asyncio.Event] = None,
    progress_callback: Optional[Callable[[str], Any]] = None,
) -> Tuple[bool, List[Dict], float]:
    """
    Poll ARP/neighbor table

    Returns:
        (success, arp_table_list, total_duration)
    """
    arp_table = []

    def emit_progress(msg: str):
        if progress_callback:
            try:
                result = progress_callback(msg)
                if asyncio.iscoroutine(result):
                    asyncio.create_task(result)
            except Exception:
                pass

    emit_progress("Collecting ARP table MAC addresses...")

    # Get ARP MACs
    success, arp_macs, mac_time = await snmp_walk(
        config, ARP_OIDS['ipNetToMediaPhysAddress'],
        cancel_event=cancel_event,
    )

    if not success or isinstance(arp_macs, str):
        return False, [], mac_time

    emit_progress(f"Found {len(arp_macs)} ARP entries, collecting IP addresses...")

    # Get ARP IPs
    success, arp_ips, ip_time = await snmp_walk(
        config, ARP_OIDS['ipNetToMediaNetAddress'],
        cancel_event=cancel_event,
    )

    total_time = mac_time + ip_time

    # Build lookup by OID suffix (ifIndex.ipAddr)
    # OID format: 1.3.6.1.2.1.4.22.1.2.<ifIndex>.<ipAddr>
    mac_by_suffix = {}
    for entry in arp_macs:
        # Get suffix after base OID
        base = ARP_OIDS['ipNetToMediaPhysAddress']
        if entry['oid'].startswith(base):
            suffix = entry['oid'][len(base):]
            mac_by_suffix[suffix] = mac_to_string(entry['value'])

    ip_by_suffix = {}
    if success and not isinstance(arp_ips, str):
        for entry in arp_ips:
            base = ARP_OIDS['ipNetToMediaNetAddress']
            if entry['oid'].startswith(base):
                suffix = entry['oid'][len(base):]
                ip_by_suffix[suffix] = entry['value_str']

    # Merge by OID suffix
    for suffix in mac_by_suffix:
        entry = {'mac': mac_by_suffix[suffix]}
        if suffix in ip_by_suffix:
            entry['ip'] = ip_by_suffix[suffix]
        arp_table.append(entry)

    return True, arp_table, total_time


async def full_device_poll(
    config: SNMPConfig,
    collect_interfaces: bool = True,
    collect_arp: bool = True,
    cancel_event: Optional[asyncio.Event] = None,
    progress_callback: Optional[Callable[[str], Any]] = None,
) -> LocalPollResult:
    """
    Perform a complete device poll - system info, interfaces, ARP table.

    This is the main entry point for local polling.

    Args:
        config: SNMP configuration
        collect_interfaces: Whether to collect interface table
        collect_arp: Whether to collect ARP table
        cancel_event: asyncio.Event to signal cancellation
        progress_callback: Callback for progress messages

    Returns:
        LocalPollResult with all collected data
    """
    result = LocalPollResult()

    def emit_progress(msg: str):
        if progress_callback:
            try:
                cb_result = progress_callback(msg)
                if asyncio.iscoroutine(cb_result):
                    asyncio.create_task(cb_result)
            except Exception:
                pass

    # Check if pysnmp is available
    if not PYSNMP_AVAILABLE:
        result.error = "pysnmp-lextudio not installed. Install with: pip install pysnmp-lextudio"
        return result

    # === System Info ===
    success, snmp_data, timing = await poll_system_info(
        config, cancel_event, progress_callback
    )

    result.timing.update(timing)

    if not success:
        if cancel_event and cancel_event.is_set():
            result.error = "Poll cancelled by user"
        else:
            result.error = f"No SNMP response from {config.target}\nCheck IP and community string."
        return result

    result.snmp_data = snmp_data
    result.success = True

    # === Interfaces ===
    if collect_interfaces and not (cancel_event and cancel_event.is_set()):
        emit_progress("Collecting interface data...")
        success, interfaces, duration = await poll_interfaces(
            config, cancel_event, progress_callback
        )
        result.interfaces = interfaces if success else []
        result.timing['interfaces'] = duration

    # === ARP Table ===
    if collect_arp and not (cancel_event and cancel_event.is_set()):
        emit_progress("Collecting ARP table...")
        success, arp_table, duration = await poll_arp_table(
            config, cancel_event, progress_callback
        )
        result.arp_table = arp_table if success else []
        result.timing['arp'] = duration

    # Final check for cancellation
    if cancel_event and cancel_event.is_set():
        result.error = "Poll cancelled by user"
        result.success = False
    else:
        emit_progress("Done!")

    # Calculate total time
    total_time = sum(result.timing.values())
    result.timing['total'] = total_time

    return result


# =============================================================================
# Synchronous Wrapper for QThread Usage
# =============================================================================

def run_poll_sync(
    config: SNMPConfig,
    collect_interfaces: bool = True,
    collect_arp: bool = True,
    cancel_flag: Optional[List[bool]] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> LocalPollResult:
    """
    Synchronous wrapper for full_device_poll.

    Runs the async poll in a new event loop. Designed for use in QThread.

    Args:
        config: SNMP configuration
        collect_interfaces: Whether to collect interface table
        collect_arp: Whether to collect ARP table
        cancel_flag: Mutable list [bool] for cancellation (thread-safe)
        progress_callback: Callback for progress messages (must be thread-safe)

    Returns:
        LocalPollResult with all collected data
    """
    # Create a cancel event that we'll set from the cancel_flag
    cancel_event = asyncio.Event()

    async def poll_with_cancel_check():
        """Wrapper that checks cancel_flag and sets cancel_event"""
        # Start a background task to monitor cancellation
        async def cancel_monitor():
            while True:
                if cancel_flag and cancel_flag[0]:
                    cancel_event.set()
                    break
                await asyncio.sleep(0.1)  # Check every 100ms

        monitor_task = asyncio.create_task(cancel_monitor())

        try:
            result = await full_device_poll(
                config=config,
                collect_interfaces=collect_interfaces,
                collect_arp=collect_arp,
                cancel_event=cancel_event,
                progress_callback=progress_callback,
            )
            return result
        finally:
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

    # Run in new event loop with proper cleanup
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        result = loop.run_until_complete(poll_with_cancel_check())
        return result
    except Exception as e:
        result = LocalPollResult()
        result.error = f"Poll failed: {e}"
        return result
    finally:
        # Clean up any pending tasks (pysnmp leaves timeout handlers)
        try:
            # Cancel all pending tasks
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()

            # Allow cancelled tasks to complete
            if pending:
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
        except Exception:
            pass  # Ignore cleanup errors

        # Shutdown async generators
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:
            pass

        # Close the loop
        try:
            loop.close()
        except Exception:
            pass


# =============================================================================
# Availability Check
# =============================================================================

def check_snmp_available() -> Tuple[bool, str]:
    """
    Check if SNMP operations are available.

    Returns:
        (available, message)
    """
    if PYSNMP_AVAILABLE:
        return True, "pysnmp-lextudio ready"
    else:
        return False, "pysnmp-lextudio not installed. Install with: pip install pysnmp-lextudio"


# =============================================================================
# Test / Example Usage
# =============================================================================

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s'
    )

    if len(sys.argv) < 2:
        print("Usage: python local_snmp_ops.py <target_ip> [community]")
        print("\nChecking SNMP availability...")
        available, msg = check_snmp_available()
        print(f"  {msg}")
        sys.exit(1)

    target = sys.argv[1]
    community = sys.argv[2] if len(sys.argv) > 2 else "public"

    config = SNMPConfig(
        target=target,
        community=community,
        version="2c",
        get_timeout=10,
        walk_timeout=60,
    )

    def progress(msg):
        print(f"  [{msg}]")

    print(f"Polling {target}...")
    result = run_poll_sync(
        config=config,
        collect_interfaces=True,
        collect_arp=True,
        progress_callback=progress,
    )

    if result.success:
        print(f"\n=== System Info ===")
        for k, v in result.snmp_data.items():
            print(f"  {k}: {v[:80]}{'...' if len(v) > 80 else ''}")

        print(f"\n=== Interfaces ({len(result.interfaces)}) ===")
        for iface in result.interfaces[:10]:
            print(f"  {iface}")
        if len(result.interfaces) > 10:
            print(f"  ... and {len(result.interfaces) - 10} more")

        print(f"\n=== ARP Table ({len(result.arp_table)}) ===")
        for entry in result.arp_table[:10]:
            print(f"  {entry}")
        if len(result.arp_table) > 10:
            print(f"  ... and {len(result.arp_table) - 10} more")

        print(f"\n=== Timing ===")
        for k, v in result.timing.items():
            print(f"  {k}: {v:.2f}s")
    else:
        print(f"FAILED: {result.error}")