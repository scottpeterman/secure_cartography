"""
SecureCartography NG - Discovery Data Models.

Vendor-agnostic dataclasses for network discovery results.
These models normalize data from CDP, LLDP, and other sources
into a consistent format for topology building and export.

Design Principles:
- All fields optional except identifiers (for partial discovery)
- Source tracking (snmp vs ssh, cdp vs lldp)
- Timestamps for freshness tracking
- Serializable to JSON for caching/export
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
import json


class DiscoveryProtocol(str, Enum):
    """Protocol used to discover information."""
    SNMP = "snmp"
    SSH = "ssh"
    

class NeighborProtocol(str, Enum):
    """Neighbor discovery protocol."""
    CDP = "cdp"
    LLDP = "lldp"
    

class InterfaceStatus(str, Enum):
    """Interface operational status."""
    UP = "up"
    DOWN = "down"
    ADMIN_DOWN = "admin_down"
    UNKNOWN = "unknown"


class DeviceVendor(str, Enum):
    """Known device vendors."""
    CISCO = "cisco"
    ARISTA = "arista"
    JUNIPER = "juniper"
    PALOALTO = "paloalto"
    FORTINET = "fortinet"
    HUAWEI = "huawei"
    HP = "hp"
    LINUX = "linux"
    UNKNOWN = "unknown"


@dataclass
class Interface:
    """
    Network interface on a device.

    Populated from IF-MIB walks (ifName, ifDescr, ifAlias).
    Used for resolving ifIndex references in CDP/LLDP tables.
    """
    name: str                                    # ifName (e.g., "Gi0/1", "et-0/0/0")
    if_index: Optional[int] = None               # SNMP ifIndex
    description: Optional[str] = None            # ifDescr (often same as name)
    alias: Optional[str] = None                  # ifAlias (user-configured description)
    ip_address: Optional[str] = None             # Primary IP if assigned
    mac_address: Optional[str] = None            # Interface MAC
    speed_mbps: Optional[int] = None             # Speed in Mbps
    mtu: Optional[int] = None                    # MTU
    status: InterfaceStatus = InterfaceStatus.UNKNOWN

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        d['status'] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Interface':
        """Create from dictionary."""
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = InterfaceStatus(data['status'])
        return cls(**data)


@dataclass
class Neighbor:
    """
    Discovered neighbor from CDP or LLDP.

    Normalizes the different field names and encodings between
    CDP and LLDP into a common format.

    CDP fields: device_id, platform, device_port, ip_address
    LLDP fields: chassis_id, system_name, port_id, management_address
    """
    # Local side (our interface)
    local_interface: str                         # Our interface name
    local_interface_index: Optional[int] = None  # ifIndex if known

    # Remote side identification
    remote_device: str = ""                      # Hostname/device_id/chassis_id
    remote_interface: str = ""                   # Remote port name
    remote_ip: Optional[str] = None              # Management IP (CDP ip_address / LLDP mgmt_address)

    # Additional remote info
    remote_platform: Optional[str] = None        # Platform/model string
    remote_description: Optional[str] = None     # System description
    remote_capabilities: Optional[str] = None    # LLDP capabilities

    # Discovery metadata
    protocol: NeighborProtocol = NeighborProtocol.CDP
    chassis_id: Optional[str] = None             # LLDP chassis ID (often MAC)
    chassis_id_subtype: Optional[int] = None     # LLDP chassis ID subtype
    port_id_subtype: Optional[int] = None        # LLDP port ID subtype

    # Raw data for debugging
    raw_index: Optional[str] = None              # Original SNMP table index

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        d['protocol'] = self.protocol.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Neighbor':
        """Create from dictionary."""
        if 'protocol' in data and isinstance(data['protocol'], str):
            data['protocol'] = NeighborProtocol(data['protocol'])
        return cls(**data)

    @classmethod
    def from_cdp(
        cls,
        local_interface: str,
        device_id: str,
        remote_port: str,
        ip_address: Optional[str] = None,
        platform: Optional[str] = None,
        local_if_index: Optional[int] = None,
        raw_index: Optional[str] = None,
    ) -> 'Neighbor':
        """Create Neighbor from CDP data."""
        return cls(
            local_interface=local_interface,
            local_interface_index=local_if_index,
            remote_device=device_id,
            remote_interface=remote_port,
            remote_ip=ip_address,
            remote_platform=platform,
            protocol=NeighborProtocol.CDP,
            raw_index=raw_index,
        )

    @classmethod
    def from_lldp(
        cls,
        local_interface: str,
        system_name: Optional[str] = None,
        port_id: Optional[str] = None,
        management_address: Optional[str] = None,
        chassis_id: Optional[str] = None,
        port_description: Optional[str] = None,
        system_description: Optional[str] = None,
        capabilities: Optional[str] = None,
        chassis_id_subtype: Optional[int] = None,
        port_id_subtype: Optional[int] = None,
        local_if_index: Optional[int] = None,
        raw_index: Optional[str] = None,
    ) -> 'Neighbor':
        """Create Neighbor from LLDP data."""
        # Use system_name if available, fall back to chassis_id
        remote_device = system_name or chassis_id or ""

        return cls(
            local_interface=local_interface,
            local_interface_index=local_if_index,
            remote_device=remote_device,
            remote_interface=port_id or "",
            remote_ip=management_address,
            remote_description=system_description,
            remote_capabilities=capabilities,
            protocol=NeighborProtocol.LLDP,
            chassis_id=chassis_id,
            chassis_id_subtype=chassis_id_subtype,
            port_id_subtype=port_id_subtype,
            raw_index=raw_index,
        )


@dataclass
class Device:
    """
    Discovered network device.

    Aggregates all information collected about a device:
    - System info (sysDescr, sysName, etc.)
    - Interfaces
    - Neighbors (CDP/LLDP)
    - Discovery metadata

    This is the primary output of device discovery.
    """
    # Identity
    hostname: str                                # Resolved hostname (folder name)
    ip_address: str                              # IP used for discovery

    # System info from SNMP
    sys_name: Optional[str] = None               # sysName.0
    sys_descr: Optional[str] = None              # sysDescr.0
    sys_location: Optional[str] = None           # sysLocation.0
    sys_contact: Optional[str] = None            # sysContact.0
    sys_object_id: Optional[str] = None          # sysObjectID.0
    uptime_ticks: Optional[int] = None           # sysUpTime.0 (hundredths of seconds)

    # Vendor detection
    vendor: DeviceVendor = DeviceVendor.UNKNOWN
    model: Optional[str] = None
    os_version: Optional[str] = None
    serial: Optional[str] = None

    # Collections
    interfaces: List[Interface] = field(default_factory=list)
    neighbors: List[Neighbor] = field(default_factory=list)
    arp_table: Dict[str, str] = field(default_factory=dict)  # MAC -> IP

    # Discovery metadata
    discovered_via: DiscoveryProtocol = DiscoveryProtocol.SNMP
    discovered_at: Optional[datetime] = None
    discovery_duration_ms: Optional[float] = None
    credential_used: Optional[str] = None        # Credential name from vault
    fqdn: Optional[str] = None                   # Fully qualified domain name
    depth: int = 0                               # Discovery depth from seed

    # Status
    discovery_success: bool = True
    discovery_errors: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.discovered_at is None:
            self.discovered_at = datetime.now()

    @property
    def cdp_neighbors(self) -> List[Neighbor]:
        """Get only CDP neighbors."""
        return [n for n in self.neighbors if n.protocol == NeighborProtocol.CDP]

    @property
    def lldp_neighbors(self) -> List[Neighbor]:
        """Get only LLDP neighbors."""
        return [n for n in self.neighbors if n.protocol == NeighborProtocol.LLDP]

    @property
    def interface_by_index(self) -> Dict[int, Interface]:
        """Get interfaces keyed by ifIndex."""
        return {
            iface.if_index: iface
            for iface in self.interfaces
            if iface.if_index is not None
        }

    @property
    def interface_by_name(self) -> Dict[str, Interface]:
        """Get interfaces keyed by name."""
        return {iface.name: iface for iface in self.interfaces}

    def get_interface_name(self, if_index: int) -> str:
        """
        Resolve ifIndex to interface name.
        Falls back to 'ifIndex_N' if not found.
        """
        iface = self.interface_by_index.get(if_index)
        if iface:
            return iface.name
        return f"ifIndex_{if_index}"

    def add_neighbor(self, neighbor: Neighbor) -> None:
        """Add a neighbor, avoiding duplicates."""
        # Simple dedup by remote_device + local_interface
        for existing in self.neighbors:
            if (existing.remote_device == neighbor.remote_device and
                existing.local_interface == neighbor.local_interface and
                existing.protocol == neighbor.protocol):
                return
        self.neighbors.append(neighbor)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'hostname': self.hostname,
            'ip_address': self.ip_address,
            'sys_name': self.sys_name,
            'sys_descr': self.sys_descr,
            'sys_location': self.sys_location,
            'sys_contact': self.sys_contact,
            'sys_object_id': self.sys_object_id,
            'uptime_ticks': self.uptime_ticks,
            'vendor': self.vendor.value,
            'model': self.model,
            'os_version': self.os_version,
            'serial': self.serial,
            'interfaces': [i.to_dict() for i in self.interfaces],
            'neighbors': [n.to_dict() for n in self.neighbors],
            'arp_table': self.arp_table,
            'discovered_via': self.discovered_via.value,
            'discovered_at': self.discovered_at.isoformat() if self.discovered_at else None,
            'discovery_duration_ms': self.discovery_duration_ms,
            'credential_used': self.credential_used,
            'fqdn': self.fqdn,
            'depth': self.depth,
            'discovery_success': self.discovery_success,
            'discovery_errors': self.discovery_errors,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Device':
        """Create Device from dictionary."""
        # Convert nested objects
        interfaces = [Interface.from_dict(i) for i in data.get('interfaces', [])]
        neighbors = [Neighbor.from_dict(n) for n in data.get('neighbors', [])]

        # Convert enums
        vendor = DeviceVendor(data.get('vendor', 'unknown'))
        discovered_via = DiscoveryProtocol(data.get('discovered_via', 'snmp'))

        # Convert datetime
        discovered_at = None
        if data.get('discovered_at'):
            discovered_at = datetime.fromisoformat(data['discovered_at'])

        return cls(
            hostname=data['hostname'],
            ip_address=data['ip_address'],
            sys_name=data.get('sys_name'),
            sys_descr=data.get('sys_descr'),
            sys_location=data.get('sys_location'),
            sys_contact=data.get('sys_contact'),
            sys_object_id=data.get('sys_object_id'),
            uptime_ticks=data.get('uptime_ticks'),
            vendor=vendor,
            model=data.get('model'),
            os_version=data.get('os_version'),
            serial=data.get('serial'),
            interfaces=interfaces,
            neighbors=neighbors,
            arp_table=data.get('arp_table', {}),
            discovered_via=discovered_via,
            discovered_at=discovered_at,
            discovery_duration_ms=data.get('discovery_duration_ms'),
            credential_used=data.get('credential_used'),
            fqdn=data.get('fqdn'),
            depth=data.get('depth', 0),
            discovery_success=data.get('discovery_success', True),
            discovery_errors=data.get('discovery_errors', []),
        )


@dataclass
class DiscoveryResult:
    """
    Result of a discovery operation (single device or crawl).

    Contains discovered devices and summary statistics.
    """
    devices: List[Device] = field(default_factory=list)

    # Statistics
    total_attempted: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0
    excluded: int = 0

    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Configuration used
    seed_devices: List[str] = field(default_factory=list)
    max_depth: int = 0
    domains: List[str] = field(default_factory=list)
    exclude_patterns: List[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> Optional[float]:
        """Get discovery duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def devices_by_depth(self) -> Dict[int, List[Device]]:
        """Group devices by discovery depth."""
        result: Dict[int, List[Device]] = {}
        for device in self.devices:
            if device.depth not in result:
                result[device.depth] = []
            result[device.depth].append(device)
        return result

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'devices': [d.to_dict() for d in self.devices],
            'total_attempted': self.total_attempted,
            'successful': self.successful,
            'failed': self.failed,
            'skipped': self.skipped,
            'excluded': self.excluded,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration_seconds': self.duration_seconds,
            'seed_devices': self.seed_devices,
            'max_depth': self.max_depth,
            'domains': self.domains,
            'exclude_patterns': self.exclude_patterns,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)