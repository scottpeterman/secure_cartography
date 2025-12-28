"""
SecureCartography NG - LLDP Neighbor Collector.

Collects LLDP (Link Layer Discovery Protocol) neighbor information.
LLDP is vendor-neutral and widely supported.

LLDP is more complex than CDP due to:
- Subtype-based encoding for chassis_id and port_id
- Separate management address table
- Three-part table index (timeMark.localPort.remIndex)
- Local port numbering may differ from ifIndex (requires lldpLocPortTable)
"""

from typing import Optional, Dict, List

from pysnmp.hlapi.v3arch.asyncio import SnmpEngine

from ...oids import LLDP
from ...models import Interface, Neighbor, NeighborProtocol
from ..walker import SNMPWalker, AuthData
from ..parsers import (
    decode_string, decode_int, decode_chassis_id, decode_port_id,
    is_valid_ipv4,
)
from .interfaces import resolve_interface_name


# LLDP Local Port Table OIDs (missing from oids.py)
LLDP_LOC_PORT_TABLE = "1.0.8802.1.1.2.1.3.7"
LLDP_LOC_PORT_ENTRY = "1.0.8802.1.1.2.1.3.7.1"
LLDP_LOC_PORT_ID_SUBTYPE = "1.0.8802.1.1.2.1.3.7.1.2"  # Column 2
LLDP_LOC_PORT_ID = "1.0.8802.1.1.2.1.3.7.1.3"          # Column 3 - The interface name/ID
LLDP_LOC_PORT_DESC = "1.0.8802.1.1.2.1.3.7.1.4"        # Column 4 - Port description


async def get_lldp_local_port_map(
    target: str,
    auth: AuthData,
    walker: SNMPWalker,
    timeout: float = 10.0,
    verbose: bool = False,
) -> Dict[int, str]:
    """
    Build mapping of lldpLocPortNum -> interface name.

    This is CRITICAL because lldpLocPortNum in the remote table
    is NOT necessarily the same as ifIndex!

    Returns:
        Dict mapping lldpLocPortNum (int) -> interface name (str)
    """
    def _vprint(msg: str):
        if verbose:
            print(f"  [lldp-local] {msg}")

    port_map: Dict[int, str] = {}

    # Walk lldpLocPortId (column 3) - this contains the port identifier
    # OID format: 1.0.8802.1.1.2.1.3.7.1.3.<lldpLocPortNum>
    _vprint(f"Walking lldpLocPortTable: {LLDP_LOC_PORT_ID}")

    try:
        results = await walker.walk(target, LLDP_LOC_PORT_ID, auth, timeout=timeout)

        if results:
            _vprint(f"Got {len(results)} local port entries")

            # Base OID length: 1.0.8802.1.1.2.1.3.7.1.3 = 11 parts
            BASE_LEN = 11

            for oid, value in results:
                parts = oid.split('.')
                if len(parts) > BASE_LEN:
                    try:
                        local_port_num = int(parts[BASE_LEN])
                        port_id = decode_string(value)
                        if port_id:
                            port_map[local_port_num] = port_id
                            _vprint(f"  lldpLocPortNum {local_port_num} -> {port_id}")
                    except (ValueError, IndexError):
                        continue
        else:
            _vprint("No lldpLocPortTable data - will fall back to ifIndex")

    except Exception as e:
        _vprint(f"Failed to get local port table: {e}")

    return port_map


async def get_lldp_neighbors(
    target: str,
    auth: AuthData,
    interface_table: Optional[Dict[int, Interface]] = None,
    engine: Optional[SnmpEngine] = None,
    timeout: float = 10.0,
    verbose: bool = False,
) -> List[Neighbor]:
    """
    Get LLDP neighbors from device.

    Queries LLDP-MIB lldpRemTable for neighbor information. Uses single-table
    walk approach which works better on devices where column-by-column walks
    timeout (e.g., older Juniper).

    Args:
        target: Device IP address
        auth: SNMP authentication data
        interface_table: Pre-fetched interface table for name resolution
        engine: Optional shared SnmpEngine
        timeout: Request timeout (LLDP walks can be slow)
        verbose: Enable debug output

    Returns:
        List of Neighbor dataclasses

    Example:
        neighbors = await get_lldp_neighbors("192.168.1.1", auth, interfaces)
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
            print(f"  [lldp] {msg}")

    # FIRST: Get the local port mapping (lldpLocPortNum -> interface name)
    # This is critical for correct local interface resolution
    lldp_port_map = await get_lldp_local_port_map(
        target, auth, walker, timeout, verbose
    )

    if lldp_port_map:
        _vprint(f"Got {len(lldp_port_map)} local port mappings from lldpLocPortTable")
    else:
        _vprint("No lldpLocPortTable - falling back to ifIndex resolution")

    # Column definitions within lldpRemEntry
    # OID format: 1.0.8802.1.1.2.1.4.1.1.<column>.<timeMark>.<localPort>.<remIndex>
    COLUMN_MAP = {
        '4': ('chassis_id_subtype', True),   # Subtype (integer)
        '5': ('chassis_id', False),          # Needs subtype decoding
        '6': ('port_id_subtype', True),      # Subtype (integer)
        '7': ('port_id', False),             # Needs subtype decoding
        '8': ('port_description', False),
        '9': ('system_name', False),
        '10': ('system_description', False),
        '11': ('capabilities_supported', False),
        '12': ('capabilities_enabled', False),
    }

    BASE_LEN = 10  # Length of base OID: 1.0.8802.1.1.2.1.4.1.1

    # Storage for raw data
    neighbors_raw: Dict[str, Dict] = {}
    subtypes: Dict[str, Dict] = {}  # Store subtypes for decoding

    # Walk entire lldpRemTable in one shot
    _vprint(f"Walking lldpRemTable: {LLDP.REMOTE_TABLE}")
    results = await walker.walk(target, LLDP.REMOTE_TABLE, auth, timeout=timeout)

    if not results:
        _vprint("No LLDP data available")
        return []

    _vprint(f"Got {len(results)} raw LLDP results")

    # Parse results
    for oid, value in results:
        parts = oid.split('.')

        if len(parts) < BASE_LEN + 4:  # Need column + 3-part index
            continue

        column = parts[BASE_LEN]  # Column number
        idx = '.'.join(parts[BASE_LEN + 1:])  # timeMark.localPort.remIndex

        if column not in COLUMN_MAP:
            continue

        field_name, is_subtype = COLUMN_MAP[column]

        # Initialize entry
        if idx not in neighbors_raw:
            neighbors_raw[idx] = {'index': idx}
            subtypes[idx] = {}

            # Extract local port number from the index tuple
            # Index is: timeMark.localPortNum.remIndex
            if len(parts) >= BASE_LEN + 3:
                try:
                    local_port_num = int(parts[BASE_LEN + 2])
                    neighbors_raw[idx]['local_port_num'] = local_port_num
                except ValueError:
                    pass

        # Store subtypes for later decoding
        if is_subtype:
            try:
                subtypes[idx][field_name] = int(value)
            except (ValueError, TypeError):
                subtypes[idx][field_name] = 0
            continue

        # Decode value based on field type
        if field_name == 'chassis_id':
            subtype = subtypes.get(idx, {}).get('chassis_id_subtype', LLDP.CHASSIS_SUBTYPE_MAC)
            decoded = decode_chassis_id(subtype, value)
            neighbors_raw[idx][field_name] = decoded
            neighbors_raw[idx]['chassis_id_subtype'] = subtype

        elif field_name == 'port_id':
            subtype = subtypes.get(idx, {}).get('port_id_subtype', LLDP.PORT_SUBTYPE_IF_NAME)
            decoded = decode_port_id(subtype, value)
            neighbors_raw[idx][field_name] = decoded
            neighbors_raw[idx]['port_id_subtype'] = subtype

        else:
            neighbors_raw[idx][field_name] = decode_string(value)

    _vprint(f"Parsed {len(neighbors_raw)} LLDP neighbor entries")

    # Also query management address table
    await _fetch_management_addresses(
        walker, target, auth, neighbors_raw, timeout, _vprint
    )

    # Convert to Neighbor objects
    neighbors: List[Neighbor] = []

    for idx, data in neighbors_raw.items():
        # Must have at least one identifying field
        system_name = data.get('system_name', '')
        chassis_id = data.get('chassis_id', '')
        mgmt_addr = data.get('management_address')

        # Skip entries with no meaningful data
        if not system_name and not chassis_id and not mgmt_addr:
            continue

        # Clean up empty strings
        if system_name in ['', '(', '(\x00']:
            system_name = None
        if chassis_id in ['', '(', '(\x00']:
            chassis_id = None

        if not system_name and not chassis_id and not mgmt_addr:
            continue

        # Resolve local interface name
        # Priority: lldpLocPortTable > ifIndex lookup
        local_port_num = data.get('local_port_num', 0)
        local_interface = None

        # Try lldpLocPortTable first (correct way)
        if local_port_num in lldp_port_map:
            local_interface = lldp_port_map[local_port_num]
            _vprint(f"Resolved port {local_port_num} via lldpLocPortTable -> {local_interface}")

        # Fall back to ifIndex (may not always match!)
        elif interface_table:
            local_interface = resolve_interface_name(local_port_num, interface_table)
            _vprint(f"Resolved port {local_port_num} via ifIndex (fallback) -> {local_interface}")

        # Last resort
        if not local_interface:
            local_interface = f"ifIndex_{local_port_num}"

        neighbor = Neighbor.from_lldp(
            local_interface=local_interface,
            system_name=system_name,
            port_id=data.get('port_id'),
            management_address=mgmt_addr,
            chassis_id=chassis_id,
            port_description=data.get('port_description'),
            system_description=data.get('system_description'),
            capabilities=data.get('capabilities_enabled'),
            chassis_id_subtype=data.get('chassis_id_subtype'),
            port_id_subtype=data.get('port_id_subtype'),
            local_if_index=local_port_num,
            raw_index=idx,
        )

        neighbors.append(neighbor)

    _vprint(f"Returning {len(neighbors)} valid LLDP neighbors")
    return neighbors


async def _fetch_management_addresses(
    walker: SNMPWalker,
    target: str,
    auth: AuthData,
    neighbors_raw: Dict[str, Dict],
    timeout: float,
    _vprint,
) -> None:
    """
    Fetch management addresses from lldpRemManAddrTable.

    Updates neighbors_raw dict in place with 'management_address' field.
    """
    # lldpRemManAddrTable base
    # OID format: base.timeMark.localPort.remIndex.addrSubtype.addrLen.addr1.addr2.addr3.addr4
    MGMT_BASE_LEN = 11  # 1.0.8802.1.1.2.1.4.2.1.4

    _vprint(f"Querying management address table: {LLDP.REM_MAN_ADDR_TABLE}")

    try:
        results = await walker.walk(target, LLDP.REM_MAN_ADDR_TABLE, auth, timeout=timeout)

        if not results:
            _vprint("No management address data")
            return

        _vprint(f"Got {len(results)} management address entries")

        for oid, value in results:
            parts = oid.split('.')

            # Need at least base + index + address
            if len(parts) < MGMT_BASE_LEN + 7:
                continue

            # Extract neighbor index (timeMark.localPortNum.remIndex)
            try:
                idx = '.'.join(parts[MGMT_BASE_LEN:MGMT_BASE_LEN + 3])

                # Extract IP address (last 4 octets for IPv4)
                # Address type is at position MGMT_BASE_LEN + 3
                addr_type = int(parts[MGMT_BASE_LEN + 3]) if len(parts) > MGMT_BASE_LEN + 3 else 0

                # IPv4 (addr_type 1) has 4 octets at the end
                if addr_type == 1 and len(parts) >= MGMT_BASE_LEN + 8:
                    addr_parts = parts[-4:]
                    if all(0 <= int(p) <= 255 for p in addr_parts):
                        ip_addr = '.'.join(addr_parts)

                        if idx in neighbors_raw:
                            neighbors_raw[idx]['management_address'] = ip_addr
                        else:
                            # Create entry from management address alone
                            try:
                                local_port = int(parts[MGMT_BASE_LEN + 1])
                            except (ValueError, IndexError):
                                local_port = 0

                            neighbors_raw[idx] = {
                                'index': idx,
                                'local_port_num': local_port,
                                'management_address': ip_addr,
                            }

            except (ValueError, IndexError):
                continue

    except Exception as e:
        _vprint(f"Management address query failed: {e}")


async def get_lldp_neighbors_raw(
    target: str,
    auth: AuthData,
    engine: Optional[SnmpEngine] = None,
    timeout: float = 10.0,
    verbose: bool = False,
) -> Dict[str, Dict]:
    """
    Get raw LLDP neighbor data as dictionaries.

    Returns dict keyed by LLDP index with all collected fields.
    Useful for debugging or custom processing.
    """
    walker = SNMPWalker(
        engine=engine,
        auth=auth,
        default_timeout=timeout,
        verbose=verbose
    )

    neighbors: Dict[str, Dict] = {}
    subtypes: Dict[str, Dict] = {}

    # Walk lldpRemTable
    results = await walker.walk(target, LLDP.REMOTE_TABLE, auth)

    BASE_LEN = 10

    for oid, value in results:
        parts = oid.split('.')

        if len(parts) < BASE_LEN + 4:
            continue

        column = parts[BASE_LEN]
        idx = '.'.join(parts[BASE_LEN + 1:])

        if idx not in neighbors:
            neighbors[idx] = {'index': idx}
            subtypes[idx] = {}
            if len(parts) >= BASE_LEN + 3:
                try:
                    neighbors[idx]['local_port_num'] = int(parts[BASE_LEN + 2])
                except ValueError:
                    pass

        # Column mapping
        if column == '4':
            subtypes[idx]['chassis_id_subtype'] = decode_int(value)
        elif column == '5':
            subtype = subtypes.get(idx, {}).get('chassis_id_subtype', 4)
            neighbors[idx]['chassis_id'] = decode_chassis_id(subtype, value)
            neighbors[idx]['chassis_id_subtype'] = subtype
        elif column == '6':
            subtypes[idx]['port_id_subtype'] = decode_int(value)
        elif column == '7':
            subtype = subtypes.get(idx, {}).get('port_id_subtype', 5)
            neighbors[idx]['port_id'] = decode_port_id(subtype, value)
            neighbors[idx]['port_id_subtype'] = subtype
        elif column == '8':
            neighbors[idx]['port_description'] = decode_string(value)
        elif column == '9':
            neighbors[idx]['system_name'] = decode_string(value)
        elif column == '10':
            neighbors[idx]['system_description'] = decode_string(value)
        elif column == '11':
            neighbors[idx]['capabilities_supported'] = decode_string(value)
        elif column == '12':
            neighbors[idx]['capabilities_enabled'] = decode_string(value)

    # Also fetch management addresses
    await _fetch_management_addresses(
        walker, target, auth, neighbors, timeout,
        lambda msg: print(f"[lldp] {msg}") if verbose else None
    )

    return neighbors