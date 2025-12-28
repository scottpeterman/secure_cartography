"""
SecureCartography NG - SNMP OID Constants.

Centralized OID definitions for network discovery.
Extracted from production VelocityMaps code.

Organization:
- SNMPv2-MIB: System group (sysDescr, sysName, etc.)
- IF-MIB: Interface table (ifName, ifDescr, ifAlias, ifOperStatus)
- CISCO-CDP-MIB: Cisco Discovery Protocol
- LLDP-MIB: Link Layer Discovery Protocol
- IP-MIB: ARP table (ipNetToMedia)

Usage:
    from sc2.scng.discovery.oids import SYSTEM, INTERFACES, CDP, LLDP
    
    # Walk CDP neighbors
    results = await walker.walk(device_ip, CDP.CACHE_ENTRY)
    
    # Get sysDescr
    result = await walker.get(device_ip, SYSTEM.SYS_DESCR)

Notes:
- Numeric OIDs are preferred for performance (skip MIB resolution)
- Named OIDs provided for documentation clarity
- Some devices only respond to numeric OIDs
"""

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class OIDGroup:
    """Base class for OID groups with helper methods."""
    
    @classmethod
    def all_oids(cls) -> Dict[str, str]:
        """Return all OIDs in this group as name->oid dict."""
        return {
            name: value 
            for name, value in vars(cls).items() 
            if isinstance(value, str) and not name.startswith('_')
        }


# =============================================================================
# SNMPv2-MIB - System Group
# =============================================================================

class SYSTEM:
    """
    SNMPv2-MIB System Group OIDs.
    
    Base: 1.3.6.1.2.1.1 (iso.org.dod.internet.mgmt.mib-2.system)
    """
    # Base OID
    BASE = "1.3.6.1.2.1.1"
    
    # Scalar objects (append .0 for GET)
    SYS_DESCR = "1.3.6.1.2.1.1.1.0"           # System description string
    SYS_OBJECT_ID = "1.3.6.1.2.1.1.2.0"       # Vendor's authoritative ID
    SYS_UPTIME = "1.3.6.1.2.1.1.3.0"          # Time since re-init (hundredths)
    SYS_CONTACT = "1.3.6.1.2.1.1.4.0"         # Contact person
    SYS_NAME = "1.3.6.1.2.1.1.5.0"            # Administratively assigned name
    SYS_LOCATION = "1.3.6.1.2.1.1.6.0"        # Physical location
    SYS_SERVICES = "1.3.6.1.2.1.1.7.0"        # Set of services (bitmap)
    
    # For MIB-based queries
    MIB_NAME = "SNMPv2-MIB"


# =============================================================================
# IF-MIB - Interface Table
# =============================================================================

class INTERFACES:
    """
    IF-MIB Interface Table OIDs.
    
    Base: 1.3.6.1.2.1.2.2.1 (ifEntry) and 1.3.6.1.2.1.31.1.1.1 (ifXEntry)
    
    Index: ifIndex (integer)
    
    Walk these tables and extract ifIndex from final OID component.
    """
    # ifTable (RFC 1213, 2863)
    IF_TABLE = "1.3.6.1.2.1.2.2"              # ifTable
    IF_ENTRY = "1.3.6.1.2.1.2.2.1"            # ifEntry
    
    # ifTable columns
    IF_INDEX = "1.3.6.1.2.1.2.2.1.1"          # ifIndex (integer)
    IF_DESCR = "1.3.6.1.2.1.2.2.1.2"          # ifDescr (DisplayString)
    IF_TYPE = "1.3.6.1.2.1.2.2.1.3"           # ifType (IANAifType)
    IF_MTU = "1.3.6.1.2.1.2.2.1.4"            # ifMtu (integer)
    IF_SPEED = "1.3.6.1.2.1.2.2.1.5"          # ifSpeed (Gauge32, bps)
    IF_PHYS_ADDRESS = "1.3.6.1.2.1.2.2.1.6"   # ifPhysAddress (MAC)
    IF_ADMIN_STATUS = "1.3.6.1.2.1.2.2.1.7"   # ifAdminStatus (1=up,2=down,3=testing)
    IF_OPER_STATUS = "1.3.6.1.2.1.2.2.1.8"    # ifOperStatus (1=up,2=down,etc.)
    
    # ifXTable (RFC 2863) - Extended interface info
    IF_X_TABLE = "1.3.6.1.2.1.31.1.1"         # ifXTable
    IF_X_ENTRY = "1.3.6.1.2.1.31.1.1.1"       # ifXEntry
    
    # ifXTable columns (more useful than ifTable)
    IF_NAME = "1.3.6.1.2.1.31.1.1.1.1"        # ifName (short name like "Gi0/1")
    IF_HIGH_SPEED = "1.3.6.1.2.1.31.1.1.1.15" # ifHighSpeed (Mbps, for >4Gbps)
    IF_ALIAS = "1.3.6.1.2.1.31.1.1.1.18"      # ifAlias (user description)
    
    # For MIB-based queries
    MIB_NAME = "IF-MIB"
    
    # Status value mappings
    ADMIN_STATUS_UP = 1
    ADMIN_STATUS_DOWN = 2
    ADMIN_STATUS_TESTING = 3
    
    OPER_STATUS_UP = 1
    OPER_STATUS_DOWN = 2
    OPER_STATUS_TESTING = 3
    OPER_STATUS_UNKNOWN = 4
    OPER_STATUS_DORMANT = 5
    OPER_STATUS_NOT_PRESENT = 6
    OPER_STATUS_LOWER_LAYER_DOWN = 7


# =============================================================================
# CISCO-CDP-MIB - Cisco Discovery Protocol
# =============================================================================

class CDP:
    """
    CISCO-CDP-MIB OIDs for CDP neighbor discovery.
    
    Base: 1.3.6.1.4.1.9.9.23 (enterprises.cisco.ciscoMgmt.ciscoCdpMIB)
    
    Cache Table Index: cdpCacheIfIndex.cdpCacheDeviceIndex
    - cdpCacheIfIndex: Local interface ifIndex
    - cdpCacheDeviceIndex: Arbitrary index for multiple neighbors per interface
    
    To get local port name: Use ifTable with cdpCacheIfIndex
    """
    # Base OID
    BASE = "1.3.6.1.4.1.9.9.23"
    
    # CDP Global settings
    CDP_GLOBAL = "1.3.6.1.4.1.9.9.23.1.3"
    CDP_GLOBAL_RUN = "1.3.6.1.4.1.9.9.23.1.3.1.0"      # CDP enabled (1=true)
    CDP_GLOBAL_MESSAGE_INTERVAL = "1.3.6.1.4.1.9.9.23.1.3.2.0"  # Interval in seconds
    CDP_GLOBAL_HOLDTIME = "1.3.6.1.4.1.9.9.23.1.3.3.0"  # Hold time in seconds
    
    # CDP Cache Table (neighbor information)
    CACHE_TABLE = "1.3.6.1.4.1.9.9.23.1.2.1"
    CACHE_ENTRY = "1.3.6.1.4.1.9.9.23.1.2.1.1"
    
    # CDP Cache Entry columns
    # Index: cdpCacheIfIndex.cdpCacheDeviceIndex
    CACHE_ADDRESS_TYPE = "1.3.6.1.4.1.9.9.23.1.2.1.1.1"   # Address type (1=IP)
    CACHE_ADDRESS = "1.3.6.1.4.1.9.9.23.1.2.1.1.4"        # IP address (binary)
    CACHE_VERSION = "1.3.6.1.4.1.9.9.23.1.2.1.1.5"        # Version string
    CACHE_DEVICE_ID = "1.3.6.1.4.1.9.9.23.1.2.1.1.6"      # Device hostname
    CACHE_DEVICE_PORT = "1.3.6.1.4.1.9.9.23.1.2.1.1.7"    # Remote port name
    CACHE_PLATFORM = "1.3.6.1.4.1.9.9.23.1.2.1.1.8"       # Platform (e.g., "cisco WS-C3750")
    CACHE_CAPABILITIES = "1.3.6.1.4.1.9.9.23.1.2.1.1.9"   # Capabilities (bitmap)
    CACHE_VTP_MGMT_DOMAIN = "1.3.6.1.4.1.9.9.23.1.2.1.1.10"  # VTP domain
    CACHE_NATIVE_VLAN = "1.3.6.1.4.1.9.9.23.1.2.1.1.11"   # Native VLAN
    CACHE_DUPLEX = "1.3.6.1.4.1.9.9.23.1.2.1.1.12"        # Duplex (1=unknown,2=half,3=full)
    CACHE_PRIMARY_MGMT_ADDR_TYPE = "1.3.6.1.4.1.9.9.23.1.2.1.1.15"
    CACHE_PRIMARY_MGMT_ADDR = "1.3.6.1.4.1.9.9.23.1.2.1.1.16"
    CACHE_SECONDARY_MGMT_ADDR_TYPE = "1.3.6.1.4.1.9.9.23.1.2.1.1.17"
    CACHE_SECONDARY_MGMT_ADDR = "1.3.6.1.4.1.9.9.23.1.2.1.1.18"
    
    # For MIB-based queries
    MIB_NAME = "CISCO-CDP-MIB"
    
    # Capabilities bitmap values
    CAP_ROUTER = 0x01
    CAP_TRANSPARENT_BRIDGE = 0x02
    CAP_SOURCE_ROUTE_BRIDGE = 0x04
    CAP_SWITCH = 0x08
    CAP_HOST = 0x10
    CAP_IGMP = 0x20
    CAP_REPEATER = 0x40


# =============================================================================
# LLDP-MIB - Link Layer Discovery Protocol
# =============================================================================

class LLDP:
    """
    LLDP-MIB OIDs for LLDP neighbor discovery.
    
    Base: 1.0.8802.1.1.2 (iso.std.iso8802.ieee802dot1.ieee802dot1mibs.lldpMIB)
    
    Remote Table Index: lldpRemTimeMark.lldpRemLocalPortNum.lldpRemIndex
    - lldpRemTimeMark: TimeFilter (usually 0)
    - lldpRemLocalPortNum: Local port number
    - lldpRemIndex: Arbitrary index for multiple neighbors per port
    
    Subtype decoding required for chassis_id and port_id.
    """
    # Base OID
    BASE = "1.0.8802.1.1.2"
    
    # LLDP Configuration
    LLDP_CONFIG = "1.0.8802.1.1.2.1.1"
    
    # LLDP Local System Data
    LOCAL_SYSTEM = "1.0.8802.1.1.2.1.3"
    LOCAL_CHASSIS_ID_SUBTYPE = "1.0.8802.1.1.2.1.3.1.0"
    LOCAL_CHASSIS_ID = "1.0.8802.1.1.2.1.3.2.0"
    LOCAL_SYS_NAME = "1.0.8802.1.1.2.1.3.3.0"
    LOCAL_SYS_DESC = "1.0.8802.1.1.2.1.3.4.0"
    LOCAL_SYS_CAP_SUPPORTED = "1.0.8802.1.1.2.1.3.5.0"
    LOCAL_SYS_CAP_ENABLED = "1.0.8802.1.1.2.1.3.6.0"
    
    # LLDP Remote Systems Data (Neighbor Table)
    REMOTE_TABLE = "1.0.8802.1.1.2.1.4.1"
    REMOTE_ENTRY = "1.0.8802.1.1.2.1.4.1.1"
    
    # lldpRemTable columns
    # Index: timeMark.localPortNum.remIndex (3-part index)
    # Base for columns: 1.0.8802.1.1.2.1.4.1.1.<column>
    REM_CHASSIS_ID_SUBTYPE = "1.0.8802.1.1.2.1.4.1.1.4"   # LldpChassisIdSubtype
    REM_CHASSIS_ID = "1.0.8802.1.1.2.1.4.1.1.5"           # Chassis ID (binary, decode by subtype)
    REM_PORT_ID_SUBTYPE = "1.0.8802.1.1.2.1.4.1.1.6"      # LldpPortIdSubtype
    REM_PORT_ID = "1.0.8802.1.1.2.1.4.1.1.7"              # Port ID (binary, decode by subtype)
    REM_PORT_DESC = "1.0.8802.1.1.2.1.4.1.1.8"            # Port description
    REM_SYS_NAME = "1.0.8802.1.1.2.1.4.1.1.9"             # System name
    REM_SYS_DESC = "1.0.8802.1.1.2.1.4.1.1.10"            # System description
    REM_SYS_CAP_SUPPORTED = "1.0.8802.1.1.2.1.4.1.1.11"   # Supported capabilities
    REM_SYS_CAP_ENABLED = "1.0.8802.1.1.2.1.4.1.1.12"     # Enabled capabilities
    
    # LLDP Remote Management Address Table
    REM_MAN_ADDR_TABLE = "1.0.8802.1.1.2.1.4.2"
    REM_MAN_ADDR_ENTRY = "1.0.8802.1.1.2.1.4.2.1"
    REM_MAN_ADDR_IF_SUBTYPE = "1.0.8802.1.1.2.1.4.2.1.3"
    REM_MAN_ADDR_IF_ID = "1.0.8802.1.1.2.1.4.2.1.4"
    REM_MAN_ADDR_OID = "1.0.8802.1.1.2.1.4.2.1.5"
    
    # For MIB-based queries
    MIB_NAME = "LLDP-MIB"
    
    # Column numbers within lldpRemEntry (for parsing walk results)
    # OID format: 1.0.8802.1.1.2.1.4.1.1.<column>.<timeMark>.<localPort>.<remIndex>
    COLUMN_CHASSIS_ID_SUBTYPE = 4
    COLUMN_CHASSIS_ID = 5
    COLUMN_PORT_ID_SUBTYPE = 6
    COLUMN_PORT_ID = 7
    COLUMN_PORT_DESC = 8
    COLUMN_SYS_NAME = 9
    COLUMN_SYS_DESC = 10
    COLUMN_CAP_SUPPORTED = 11
    COLUMN_CAP_ENABLED = 12
    
    # Chassis ID Subtypes (LldpChassisIdSubtype)
    CHASSIS_SUBTYPE_COMPONENT = 1     # entPhysicalAlias
    CHASSIS_SUBTYPE_IF_ALIAS = 2      # ifAlias
    CHASSIS_SUBTYPE_PORT = 3          # entPhysicalAlias of port
    CHASSIS_SUBTYPE_MAC = 4           # MAC address (most common)
    CHASSIS_SUBTYPE_NETWORK = 5       # Network address
    CHASSIS_SUBTYPE_IF_NAME = 6       # ifName
    CHASSIS_SUBTYPE_LOCAL = 7         # Locally assigned
    
    # Port ID Subtypes (LldpPortIdSubtype)
    PORT_SUBTYPE_IF_ALIAS = 1         # ifAlias
    PORT_SUBTYPE_PORT = 2             # entPhysicalAlias
    PORT_SUBTYPE_MAC = 3              # MAC address
    PORT_SUBTYPE_NETWORK = 4          # Network address
    PORT_SUBTYPE_IF_NAME = 5          # ifName (most common)
    PORT_SUBTYPE_AGENT = 6            # Agent circuit ID
    PORT_SUBTYPE_LOCAL = 7            # Locally assigned
    
    # Capabilities (bitmap) - same as CDP
    CAP_OTHER = 0x01
    CAP_REPEATER = 0x02
    CAP_BRIDGE = 0x04
    CAP_WLAN_AP = 0x08
    CAP_ROUTER = 0x10
    CAP_TELEPHONE = 0x20
    CAP_DOCSIS = 0x40
    CAP_STATION = 0x80


# =============================================================================
# IP-MIB - ARP Table
# =============================================================================

class ARP:
    """
    IP-MIB OIDs for ARP table (MAC to IP mapping).
    
    Used as fallback for LLDP neighbors that don't provide management address.
    
    Table Index: ipNetToMediaIfIndex.ipNetToMediaNetAddress
    - ipNetToMediaIfIndex: Interface ifIndex
    - ipNetToMediaNetAddress: IP address (4 octets in OID)
    """
    # ipNetToMedia (deprecated in favor of ipNetToPhysical, but widely supported)
    NET_TO_MEDIA_TABLE = "1.3.6.1.2.1.4.22"
    NET_TO_MEDIA_ENTRY = "1.3.6.1.2.1.4.22.1"
    NET_TO_MEDIA_IF_INDEX = "1.3.6.1.2.1.4.22.1.1"       # Interface ifIndex
    NET_TO_MEDIA_PHYS_ADDRESS = "1.3.6.1.2.1.4.22.1.2"   # MAC address (binary)
    NET_TO_MEDIA_NET_ADDRESS = "1.3.6.1.2.1.4.22.1.3"    # IP address
    NET_TO_MEDIA_TYPE = "1.3.6.1.2.1.4.22.1.4"           # Entry type
    
    # ipNetToPhysical (RFC 4293, preferred for IPv6 support)
    NET_TO_PHYSICAL_TABLE = "1.3.6.1.2.1.4.35"
    
    # Entry types
    TYPE_OTHER = 1
    TYPE_INVALID = 2
    TYPE_DYNAMIC = 3
    TYPE_STATIC = 4


# =============================================================================
# Entity-MIB - Physical Entity Table (for serial/model)
# =============================================================================

class ENTITY:
    """
    ENTITY-MIB OIDs for physical entity information.
    
    Used to get serial number, model, and hardware inventory.
    Not all devices support this MIB.
    """
    # entPhysical Table
    PHYSICAL_TABLE = "1.3.6.1.2.1.47.1.1.1"
    PHYSICAL_ENTRY = "1.3.6.1.2.1.47.1.1.1.1"
    
    # Columns
    PHYS_DESCR = "1.3.6.1.2.1.47.1.1.1.1.2"           # Physical description
    PHYS_VENDOR_TYPE = "1.3.6.1.2.1.47.1.1.1.1.3"     # Vendor type OID
    PHYS_CONTAINED_IN = "1.3.6.1.2.1.47.1.1.1.1.4"    # Container entity index
    PHYS_CLASS = "1.3.6.1.2.1.47.1.1.1.1.5"           # Physical class
    PHYS_PARENT_REL_POS = "1.3.6.1.2.1.47.1.1.1.1.6"  # Relative position
    PHYS_NAME = "1.3.6.1.2.1.47.1.1.1.1.7"            # Physical name
    PHYS_HARDWARE_REV = "1.3.6.1.2.1.47.1.1.1.1.8"    # Hardware revision
    PHYS_FIRMWARE_REV = "1.3.6.1.2.1.47.1.1.1.1.9"    # Firmware revision
    PHYS_SOFTWARE_REV = "1.3.6.1.2.1.47.1.1.1.1.10"   # Software revision
    PHYS_SERIAL_NUM = "1.3.6.1.2.1.47.1.1.1.1.11"     # Serial number
    PHYS_MFG_NAME = "1.3.6.1.2.1.47.1.1.1.1.12"       # Manufacturer name
    PHYS_MODEL_NAME = "1.3.6.1.2.1.47.1.1.1.1.13"     # Model name
    PHYS_ALIAS = "1.3.6.1.2.1.47.1.1.1.1.14"          # Alias
    PHYS_ASSET_ID = "1.3.6.1.2.1.47.1.1.1.1.15"       # Asset ID
    PHYS_IS_FRU = "1.3.6.1.2.1.47.1.1.1.1.16"         # Is field-replaceable (1=true)
    
    # Physical class values
    CLASS_OTHER = 1
    CLASS_UNKNOWN = 2
    CLASS_CHASSIS = 3
    CLASS_BACKPLANE = 4
    CLASS_CONTAINER = 5
    CLASS_POWER_SUPPLY = 6
    CLASS_FAN = 7
    CLASS_SENSOR = 8
    CLASS_MODULE = 9
    CLASS_PORT = 10
    CLASS_STACK = 11
    CLASS_CPU = 12


# =============================================================================
# Vendor-specific OIDs
# =============================================================================

class CISCO_ENVMON:
    """Cisco Environmental Monitoring MIB."""
    BASE = "1.3.6.1.4.1.9.9.13"
    
    # Temperature sensors
    TEMP_TABLE = "1.3.6.1.4.1.9.9.13.1.3"
    TEMP_DESCR = "1.3.6.1.4.1.9.9.13.1.3.1.2"
    TEMP_VALUE = "1.3.6.1.4.1.9.9.13.1.3.1.3"
    TEMP_STATE = "1.3.6.1.4.1.9.9.13.1.3.1.6"


class JUNIPER:
    """Juniper-specific OIDs."""
    BASE = "1.3.6.1.4.1.2636"
    
    # Juniper chassis info
    CHASSIS_SERIAL = "1.3.6.1.4.1.2636.3.1.3.0"


class ARISTA:
    """Arista-specific OIDs."""
    BASE = "1.3.6.1.4.1.30065"


# =============================================================================
# Helper Functions
# =============================================================================

def extract_index_from_oid(oid: str, base_oid: str) -> str:
    """
    Extract index portion from an OID.
    
    Example:
        oid = "1.3.6.1.4.1.9.9.23.1.2.1.1.6.10.1"
        base = "1.3.6.1.4.1.9.9.23.1.2.1.1.6"
        returns "10.1"
    """
    if oid.startswith(base_oid + "."):
        return oid[len(base_oid) + 1:]
    return oid


def parse_cdp_index(oid: str) -> tuple[int, int]:
    """
    Parse CDP cache index from OID.
    
    CDP index format: ifIndex.deviceIndex
    Returns (if_index, device_index)
    """
    parts = oid.split(".")
    if len(parts) >= 2:
        return int(parts[-2]), int(parts[-1])
    return 0, 0


def parse_lldp_index(oid: str) -> tuple[int, int, int]:
    """
    Parse LLDP remote table index from OID.
    
    LLDP index format: timeMark.localPortNum.remIndex
    Returns (time_mark, local_port, rem_index)
    """
    parts = oid.split(".")
    if len(parts) >= 3:
        return int(parts[-3]), int(parts[-2]), int(parts[-1])
    return 0, 0, 0


def ip_from_oid_suffix(oid: str, count: int = 4) -> str:
    """
    Extract IP address from the last N octets of an OID.
    
    Used for ARP table where IP is encoded in OID index.
    """
    parts = oid.split(".")
    if len(parts) >= count:
        return ".".join(parts[-count:])
    return ""
