import re
from typing import Optional, Tuple


class InterfaceNormalizer:
    STANDARD_INTERFACES = {
        'Gi': 'GigabitEthernet',
        'Te': 'TenGigabitEthernet',
        'Eth': 'Ethernet',
        'Fa': 'FastEthernet',
        'Po': 'Port-channel',
        'Vl': 'Vlan',
        'Lo': 'Loopback',
        'Mg': 'Management',
        'Hu': 'HundredGigE'
    }

    INTERFACE_PATTERNS = {
        'ios': [
            (r'^(?:Gi|GigabitEthernet)(\d+/?\d*/?(?:\d+)?)', 'GigabitEthernet\\1'),
            (r'^(?:Te|TenGigabitEthernet)(\d+/?\d*/?(?:\d+)?)', 'TenGigabitEthernet\\1'),
            (r'^(?:Fa|FastEthernet)(\d+/?\d*/?(?:\d+)?)', 'FastEthernet\\1'),
            (r'^(?:Po|Port-channel)(\d+)', 'Port-channel\\1'),
            (r'^(?:Vl|Vlan)(\d+)', 'Vlan\\1'),
            (r'^(?:Lo|Loopback)(\d+)', 'Loopback\\1'),
            (r'^(?:Hu|HundredGigE)(\d+/?\d*/?(?:\d+)?)', 'HundredGigE\\1')
        ],
        'nxos': [
            (r'^(?:Eth|Ethernet)(\d+/\d+)', 'Ethernet\\1'),
            (r'^(?:Po|port-channel)(\d+)', 'port-channel\\1'),
            (r'^(?:Vlan)(\d+)', 'Vlan\\1'),
            (r'^(?:Lo|loopback)(\d+)', 'loopback\\1'),
            (r'^(?:mgmt)(\d+)', 'mgmt\\1')
        ],
        'arista': [
            (r'^(?:Et|Ethernet)(\d+(/\d+)?)', 'Ethernet\\1'),
            (r'^(?:Po|Port-Channel)(\d+)', 'Port-Channel\\1'),
            (r'^(?:Vl|Vlan)(\d+)', 'Vlan\\1'),
            (r'^(?:Lo|Loopback)(\d+)', 'Loopback\\1'),
            (r'^(?:Ma|Management)(\d+)', 'Management\\1')
        ]
    }

    @classmethod
    def normalize(cls, interface: str, vendor: Optional[str] = None) -> str:
        if not interface or interface == "unknown":
            return "unknown"

        interface = interface.strip()

        # Return if already in full format
        if any(interface.startswith(full) for full in cls.STANDARD_INTERFACES.values()):
            return interface

        if vendor:
            vendor = vendor.lower()
            if vendor in cls.INTERFACE_PATTERNS:
                for pattern, replacement in cls.INTERFACE_PATTERNS[vendor]:
                    if re.match(pattern, interface, re.IGNORECASE):
                        return re.sub(pattern, replacement, interface, flags=re.IGNORECASE)

        # Try generic normalization if no vendor match
        for patterns in cls.INTERFACE_PATTERNS.values():
            for pattern, replacement in patterns:
                if re.match(pattern, interface, re.IGNORECASE):
                    return re.sub(pattern, replacement, interface, flags=re.IGNORECASE)

        return interface

    @classmethod
    def normalize_pair(cls, local_int: str, remote_int: str,
                       local_vendor: Optional[str] = None,
                       remote_vendor: Optional[str] = None) -> Tuple[str, str]:
        return (
            cls.normalize(local_int, local_vendor),
            cls.normalize(remote_int, remote_vendor)
        )