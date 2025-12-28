"""
SecureCartography NG - SNMP Value Parsers.

Functions for decoding binary SNMP values into usable formats.
Extracted and enhanced from production VelocityMaps code.

Handles:
- MAC address decoding (various pysnmp types)
- IP address decoding (with/without address family byte)
- LLDP chassis/port ID decoding by subtype
- Text value extraction from OctetString
- Vendor detection from sysDescr

All functions are defensive - they return safe fallback values
on decode errors rather than raising exceptions.
"""

import binascii
import re
from typing import Optional, Tuple, Any, Union

from ..oids import LLDP
from ..models import DeviceVendor


# =============================================================================
# MAC Address Decoding
# =============================================================================

def decode_mac(binary_data: Any) -> str:
    """
    Decode binary data as MAC address.
    
    Handles various pysnmp types:
    - OctetString with asOctets()
    - Types with prettyPrint() returning "0x..."
    - Raw bytes
    - String (latin-1 encoded)
    
    Returns:
        Colon-separated MAC (e.g., "aa:bb:cc:dd:ee:ff")
        or error string on failure
    
    Examples:
        >>> decode_mac(b'\\xaa\\xbb\\xcc\\xdd\\xee\\xff')
        'aa:bb:cc:dd:ee:ff'
    """
    try:
        # Handle pysnmp OctetString types
        if hasattr(binary_data, 'asOctets'):
            binary_data = binary_data.asOctets()
        elif hasattr(binary_data, 'prettyPrint'):
            # Some pysnmp types need prettyPrint first
            pretty = binary_data.prettyPrint()
            # Check if it's already formatted as hex (0x...)
            if pretty.startswith('0x'):
                hex_str = pretty[2:]
                if len(hex_str) == 12:  # Valid MAC length
                    return ':'.join(hex_str[i:i + 2] for i in range(0, len(hex_str), 2))
            binary_data = bytes(binary_data)
        elif isinstance(binary_data, str):
            binary_data = binary_data.encode('latin-1')

        # Convert to bytes if needed
        if not isinstance(binary_data, bytes):
            try:
                binary_data = bytes(binary_data)
            except (TypeError, ValueError):
                return repr(binary_data)

        hex_str = binascii.hexlify(binary_data).decode()
        return ':'.join(hex_str[i:i + 2] for i in range(0, len(hex_str), 2))
    
    except Exception as e:
        # Use repr() to safely show binary data without control chars
        return f"<mac_decode_error: {repr(binary_data)[:50]}>"


def normalize_mac(mac: str) -> str:
    """
    Normalize MAC address to lowercase colon-separated format.
    
    Handles various input formats:
    - aa:bb:cc:dd:ee:ff
    - AA:BB:CC:DD:EE:FF
    - aa-bb-cc-dd-ee-ff
    - aabb.ccdd.eeff
    - aabbccddeeff
    
    Returns:
        Lowercase colon-separated MAC or original string if invalid
    """
    # Remove common separators
    clean = mac.replace(':', '').replace('-', '').replace('.', '').lower()
    
    if len(clean) == 12 and all(c in '0123456789abcdef' for c in clean):
        return ':'.join(clean[i:i + 2] for i in range(0, 12, 2))
    
    return mac


# =============================================================================
# IP Address Decoding
# =============================================================================

def decode_ip(binary_data: Any) -> str:
    """
    Decode binary data as IP address.
    
    Handles two common formats:
    - 4 bytes: Direct IPv4 address
    - 5 bytes: Address family byte + IPv4 address (CDP format)
    
    Returns:
        Dotted-decimal IP (e.g., "192.168.1.1")
        or repr() of input on failure
    
    Examples:
        >>> decode_ip(b'\\xc0\\xa8\\x01\\x01')
        '192.168.1.1'
        >>> decode_ip(b'\\x01\\xc0\\xa8\\x01\\x01')  # with family byte
        '192.168.1.1'
    """
    try:
        # Handle pysnmp OctetString types
        if hasattr(binary_data, 'asOctets'):
            binary_data = binary_data.asOctets()
        elif hasattr(binary_data, 'prettyPrint'):
            binary_data = bytes(binary_data)
        elif isinstance(binary_data, str):
            binary_data = binary_data.encode('latin-1')

        # Convert to bytes if needed
        if not isinstance(binary_data, bytes):
            try:
                binary_data = bytes(binary_data)
            except (TypeError, ValueError):
                return str(binary_data)

        # First byte is address family, rest is IP
        if len(binary_data) == 5:  # IPv4 with family byte
            return '.'.join(str(b) for b in binary_data[1:])
        elif len(binary_data) == 4:  # IPv4 without family
            return '.'.join(str(b) for b in binary_data)
        
    except Exception:
        pass
    
    return repr(binary_data)[:50]


def is_valid_ipv4(ip: str) -> bool:
    """Check if string is a valid IPv4 address."""
    if not ip:
        return False
    parts = ip.split('.')
    if len(parts) != 4:
        return False
    try:
        return all(0 <= int(p) <= 255 for p in parts)
    except ValueError:
        return False


def is_ip_address(s: str) -> bool:
    """Check if string looks like an IP address (IPv4)."""
    return is_valid_ipv4(s)


# =============================================================================
# LLDP Subtype Decoding
# =============================================================================

def decode_chassis_id(subtype: int, value: Any) -> str:
    """
    Decode LLDP chassis ID based on subtype.
    
    Subtypes (LldpChassisIdSubtype):
        1 = chassis component (entPhysicalAlias)
        2 = interface alias (ifAlias)
        3 = port component
        4 = MAC address (most common)
        5 = network address
        6 = interface name (ifName)
        7 = locally assigned
    
    Returns:
        Decoded chassis ID string
    """
    try:
        if subtype == LLDP.CHASSIS_SUBTYPE_MAC:  # 4 = MAC address
            return decode_mac(value)
        
        elif subtype == LLDP.CHASSIS_SUBTYPE_NETWORK:  # 5 = Network address
            return decode_ip(value)
        
        elif subtype in (
            LLDP.CHASSIS_SUBTYPE_COMPONENT,   # 1
            LLDP.CHASSIS_SUBTYPE_IF_ALIAS,    # 2
            LLDP.CHASSIS_SUBTYPE_PORT,        # 3
            LLDP.CHASSIS_SUBTYPE_IF_NAME,     # 6
            LLDP.CHASSIS_SUBTYPE_LOCAL,       # 7
        ):
            # Text-based types
            return decode_string(value)
        
        else:
            # Unknown subtype - try string first
            return decode_string(value)
    
    except Exception as e:
        return f"<chassis_decode_error: {repr(value)[:30]}>"


def decode_port_id(subtype: int, value: Any) -> str:
    """
    Decode LLDP port ID based on subtype.
    
    Subtypes (LldpPortIdSubtype):
        1 = interface alias (ifAlias)
        2 = port component
        3 = MAC address
        4 = network address
        5 = interface name (ifName) - most common
        6 = agent circuit ID
        7 = locally assigned
    
    Returns:
        Decoded port ID string
    """
    try:
        if subtype == LLDP.PORT_SUBTYPE_MAC:  # 3 = MAC address
            return decode_mac(value)
        
        elif subtype == LLDP.PORT_SUBTYPE_NETWORK:  # 4 = Network address
            return decode_ip(value)
        
        elif subtype in (
            LLDP.PORT_SUBTYPE_IF_ALIAS,   # 1
            LLDP.PORT_SUBTYPE_PORT,       # 2
            LLDP.PORT_SUBTYPE_IF_NAME,    # 5
            LLDP.PORT_SUBTYPE_AGENT,      # 6
            LLDP.PORT_SUBTYPE_LOCAL,      # 7
        ):
            # Text-based types
            return decode_string(value)
        
        else:
            # Unknown subtype - try string first
            return decode_string(value)
    
    except Exception as e:
        return f"<port_decode_error: {repr(value)[:30]}>"


# =============================================================================
# String Decoding
# =============================================================================

def decode_string(value: Any) -> str:
    """
    Safely convert SNMP value to string.
    
    Handles pysnmp OctetString, DisplayString, and other types.
    Strips null bytes and control characters.
    
    Returns:
        Clean string value
    """
    try:
        if hasattr(value, 'prettyPrint'):
            result = value.prettyPrint()
        elif hasattr(value, 'asOctets'):
            # Try UTF-8 first, fall back to latin-1
            octets = value.asOctets()
            try:
                result = octets.decode('utf-8')
            except UnicodeDecodeError:
                result = octets.decode('latin-1')
        elif isinstance(value, bytes):
            try:
                result = value.decode('utf-8')
            except UnicodeDecodeError:
                result = value.decode('latin-1')
        else:
            result = str(value)
        
        # Clean up the string
        # Remove null bytes and leading/trailing whitespace
        result = result.replace('\x00', '').strip()
        
        # Remove hex prefix if present (from prettyPrint)
        if result.startswith('0x'):
            # Try to decode as hex string
            try:
                hex_bytes = bytes.fromhex(result[2:])
                result = hex_bytes.decode('utf-8', errors='replace')
            except (ValueError, UnicodeDecodeError):
                pass  # Keep original
        
        return result
    
    except Exception:
        return str(value)


def decode_int(value: Any) -> Optional[int]:
    """
    Safely convert SNMP value to integer.
    
    Returns:
        Integer value or None on failure
    """
    try:
        if hasattr(value, 'prettyPrint'):
            return int(value.prettyPrint())
        return int(value)
    except (ValueError, TypeError):
        return None


# =============================================================================
# Vendor Detection
# =============================================================================

# Vendor detection patterns (case-insensitive)
VENDOR_PATTERNS = {
    DeviceVendor.CISCO: [
        r'cisco',
        r'ios',
        r'nx-?os',
        r'asa',
        r'cat\d',  # Catalyst
    ],
    DeviceVendor.ARISTA: [
        r'arista',
        r'eos',
    ],
    DeviceVendor.JUNIPER: [
        r'juniper',
        r'junos',
        r'srx',
        r'mx\d',
        r'qfx',
        r'ex\d',
    ],
    DeviceVendor.PALOALTO: [
        r'palo\s*alto',
        r'pan-?os',
    ],
    DeviceVendor.FORTINET: [
        r'fortinet',
        r'fortigate',
        r'fortios',
    ],
}


def detect_vendor(sys_descr: Optional[str]) -> DeviceVendor:
    """
    Detect device vendor from sysDescr string.
    
    Uses pattern matching against known vendor strings.
    
    Returns:
        DeviceVendor enum value
    
    Examples:
        >>> detect_vendor("Cisco IOS Software, C3750 Software...")
        DeviceVendor.CISCO
        >>> detect_vendor("Arista Networks EOS version 4.27.0F")
        DeviceVendor.ARISTA
        >>> detect_vendor("Juniper Networks, Inc. ex4300-48t...")
        DeviceVendor.JUNIPER
    """
    if not sys_descr:
        return DeviceVendor.UNKNOWN
    
    sys_descr_lower = sys_descr.lower()
    
    for vendor, patterns in VENDOR_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, sys_descr_lower):
                return vendor
    
    return DeviceVendor.UNKNOWN


def is_network_device(sys_descr: Optional[str]) -> bool:
    """
    Check if sysDescr indicates a network device (vs server/host).
    
    Used for filtering during discovery.
    """
    if not sys_descr:
        return False
    
    vendor = detect_vendor(sys_descr)
    return vendor != DeviceVendor.UNKNOWN


# Exclusion patterns for non-network devices
DEFAULT_EXCLUDE_PATTERNS = [
    'linux',
    'windows',
    'vmware',
    'esxi',
    'hypervisor',
    'ucs',
    'server',
    'hp proliant',
    'dell poweredge',
    'ibm system',
]


def should_exclude(sys_descr: Optional[str], exclude_patterns: Optional[list] = None) -> bool:
    """
    Check if device should be excluded from discovery.
    
    Uses case-insensitive substring matching against exclusion patterns.
    Useful for filtering out servers, hosts, and other non-network devices.
    
    Args:
        sys_descr: sysDescr string from SNMP
        exclude_patterns: List of lowercase patterns to match.
                         If None, uses DEFAULT_EXCLUDE_PATTERNS.
    
    Returns:
        True if device should be excluded
    """
    if not sys_descr:
        return False
    
    if exclude_patterns is None:
        exclude_patterns = DEFAULT_EXCLUDE_PATTERNS
    
    sys_descr_lower = sys_descr.lower()
    
    for pattern in exclude_patterns:
        if pattern.lower() in sys_descr_lower:
            return True
    
    return False


# =============================================================================
# Hostname Processing
# =============================================================================

def extract_hostname(system_name: str, domains: Union[str, list]) -> str:
    """
    Extract base hostname by stripping domain suffix.
    
    Args:
        system_name: Full system name (e.g., 'switch01.example.com')
        domains: Domain(s) to strip (str or list)
    
    Returns:
        Hostname without domain (e.g., 'switch01')
    
    Examples:
        >>> extract_hostname('switch01.example.com', 'example.com')
        'switch01'
        >>> extract_hostname('agg01.dc1.example.com', ['example.com', 'local'])
        'agg01.dc1'
    """
    if not system_name:
        return ""
    
    # Ensure domains is a list
    if isinstance(domains, str):
        domains = [domains]
    
    # Try each domain suffix (case-insensitive)
    for domain in domains:
        domain_suffix = f".{domain}"
        if system_name.lower().endswith(domain_suffix.lower()):
            return system_name[:-len(domain_suffix)]
    
    return system_name


def build_fqdn(system_name: str, domains: Union[str, list]) -> Optional[str]:
    """
    Build FQDN from system name and domain(s).
    
    If system_name already ends with a configured domain, returns as-is.
    If system_name looks like an FQDN (2+ dots), returns as-is.
    Otherwise appends the primary (first) domain.
    
    Args:
        system_name: Hostname or partial FQDN
        domains: Domain(s) to use (str or list, first is primary)
    
    Returns:
        FQDN string or None if invalid input
    """
    if not system_name:
        return None
    
    # Ensure domains is a list
    if isinstance(domains, str):
        domains = [domains]
    
    if not domains:
        return system_name
    
    # Check if already ends with any configured domain
    for domain in domains:
        if system_name.lower().endswith(f".{domain.lower()}"):
            return system_name
    
    # Check if it looks like an FQDN already (2+ dots)
    if system_name.count('.') >= 2:
        return system_name
    
    # Append primary domain
    return f"{system_name}.{domains[0]}"


def extract_hostname_from_port_desc(port_desc: str) -> Optional[str]:
    """
    Try to extract hostname from LLDP port_description field.
    
    Fallback for devices that don't advertise lldpRemSysName.
    
    Common patterns:
        'INT::hostname.domain::interface' -> hostname.domain
        'TO::hostname::interface' -> hostname
    
    Returns:
        Extracted hostname or None if no pattern matches
    """
    if not port_desc:
        return None
    
    # Pattern: INT::hostname::interface or TO::hostname::interface
    if '::' in port_desc:
        parts = port_desc.split('::')
        if len(parts) >= 2:
            candidate = parts[1].strip()
            
            # Validate it looks like a hostname (not an interface name)
            interface_prefixes = (
                'et-', 'xe-', 'ge-', 'eth', 'te', 'gi', 'fa', 
                'po', 'vlan', 'lo', 'mgmt'
            )
            
            if candidate and not candidate.lower().startswith(interface_prefixes):
                # Should contain letters
                if any(c.isalpha() for c in candidate):
                    return candidate
    
    return None


# =============================================================================
# Capability Parsing
# =============================================================================

def parse_cdp_capabilities(cap_value: int) -> list:
    """
    Parse CDP capabilities bitmap.
    
    Returns list of capability strings.
    """
    from .oids import CDP
    
    capabilities = []
    if cap_value & CDP.CAP_ROUTER:
        capabilities.append('router')
    if cap_value & CDP.CAP_TRANSPARENT_BRIDGE:
        capabilities.append('bridge')
    if cap_value & CDP.CAP_SOURCE_ROUTE_BRIDGE:
        capabilities.append('source-route-bridge')
    if cap_value & CDP.CAP_SWITCH:
        capabilities.append('switch')
    if cap_value & CDP.CAP_HOST:
        capabilities.append('host')
    if cap_value & CDP.CAP_IGMP:
        capabilities.append('igmp')
    if cap_value & CDP.CAP_REPEATER:
        capabilities.append('repeater')
    
    return capabilities


def parse_lldp_capabilities(cap_value: int) -> list:
    """
    Parse LLDP capabilities bitmap.
    
    Returns list of capability strings.
    """
    capabilities = []
    if cap_value & LLDP.CAP_OTHER:
        capabilities.append('other')
    if cap_value & LLDP.CAP_REPEATER:
        capabilities.append('repeater')
    if cap_value & LLDP.CAP_BRIDGE:
        capabilities.append('bridge')
    if cap_value & LLDP.CAP_WLAN_AP:
        capabilities.append('wlan-ap')
    if cap_value & LLDP.CAP_ROUTER:
        capabilities.append('router')
    if cap_value & LLDP.CAP_TELEPHONE:
        capabilities.append('telephone')
    if cap_value & LLDP.CAP_DOCSIS:
        capabilities.append('docsis')
    if cap_value & LLDP.CAP_STATION:
        capabilities.append('station')
    
    return capabilities
