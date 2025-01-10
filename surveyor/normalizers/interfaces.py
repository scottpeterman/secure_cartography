# normalizers/interfaces.py
from pprint import pprint
from typing import Dict, List, Any, Optional, Union
from datetime import datetime


class InterfaceNormalizer:
    def __init__(self):
        self.normalizers = {
            'arista_eos_show_interfaces': self._normalize_arista,
            'cisco_ios_show_interfaces': self._normalize_ios,
            'cisco_nxos_show_interface': self._normalize_nxos
        }

    @staticmethod
    def safe_int(value: Any, default: int = 0) -> int:
        """Safely convert value to integer."""
        if value is None:
            return default
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return default
            try:
                # Try to handle values with commas and other formatting
                clean_value = value.replace(',', '').replace(' ', '')
                return int(clean_value)
            except ValueError:
                return default
        return default

    @staticmethod
    def safe_str(value: Any, default: str = '') -> str:
        """Safely convert value to string."""
        if value is None:
            return default
        if isinstance(value, str):
            return value.strip()
        return str(value)

    @staticmethod
    def format_ip(address: Optional[str], prefix: Optional[str]) -> str:
        """Safely format IP address with prefix."""
        if not address:
            return ''
        address = address.strip()
        if not address:
            return ''
        if not prefix:
            return address
        prefix = prefix.strip()
        if not prefix:
            return address
        return f"{address}/{prefix}"

    def normalize(self, parsed_data: List[Dict], template_name: str) -> Dict[str, Any]:
        if not parsed_data:
            raise ValueError("Empty parsed data")

        normalizer = self.normalizers.get(template_name)
        if not normalizer:
            raise ValueError(f"Unsupported template: {template_name}")

        interfaces = {}
        for interface_data in parsed_data:
            try:
                normalized = normalizer(interface_data)
                if normalized and normalized.get('name'):
                    interfaces[normalized['name']] = normalized
            except Exception as e:
                print(f"Error normalizing interface: {e}")
                print(f"Problem data: {interface_data}")
                continue

        return {
            'interfaces': interfaces,
            '_metadata': {
                'normalized_timestamp': datetime.utcnow().isoformat(),
                'source_template': template_name,
                'schema_version': '1.0',
                'raw_data': parsed_data
            }
        }

    def _normalize_arista(self, data: Dict) -> Dict:
        return {
            'name': self.safe_str(data.get('INTERFACE')),
            'status': {
                'link': self.safe_str(data.get('LINK_STATUS')),
                'protocol': self.safe_str(data.get('PROTOCOL_STATUS'))
            },
            'hardware': {
                'type': self.safe_str(data.get('HARDWARE_TYPE')),
                'mac_address': self.safe_str(data.get('MAC_ADDRESS')),
                'bia': self.safe_str(data.get('BIA')),
                'mtu': self.safe_int(data.get('MTU')),
                'bandwidth': self.safe_str(data.get('BANDWIDTH'))
            },
            'description': self.safe_str(data.get('DESCRIPTION')),
            'ip': self.safe_str(data.get('IP_ADDRESS')),
            'counters': {
                'uptime': self.safe_str(data.get('INTERFACE_UP_TIME')),
                'status_changes': self.safe_int(data.get('LINK_STATUS_CHANGE'))
            }
        }

    def _normalize_ios(self, data: Dict) -> Dict:
        return {
            'name': self.safe_str(data.get('INTERFACE')),
            'status': {
                'link': self.safe_str(data.get('LINK_STATUS')),
                'protocol': self.safe_str(data.get('PROTOCOL_STATUS'))
            },
            'hardware': {
                'type': self.safe_str(data.get('HARDWARE_TYPE')),
                'mac_address': self.safe_str(data.get('MAC_ADDRESS')),
                'bia': self.safe_str(data.get('BIA')),
                'mtu': self.safe_int(data.get('MTU')),
                'bandwidth': self.safe_str(data.get('BANDWIDTH')),
                'duplex': self.safe_str(data.get('DUPLEX')),
                'speed': self.safe_str(data.get('SPEED')),
                'media_type': self.safe_str(data.get('MEDIA_TYPE'))
            },
            'description': self.safe_str(data.get('DESCRIPTION')),
            'ip': self.format_ip(data.get('IP_ADDRESS'), data.get('PREFIX_LENGTH')),
            'counters': {
                'input_packets': self.safe_int(data.get('INPUT_PACKETS')),
                'output_packets': self.safe_int(data.get('OUTPUT_PACKETS')),
                'input_errors': self.safe_int(data.get('INPUT_ERRORS')),
                'output_errors': self.safe_int(data.get('OUTPUT_ERRORS'))
            }
        }

    def _normalize_nxos(self, data: Dict) -> Dict:
        return {
            'name': self.safe_str(data.get('INTERFACE')),
            'status': {
                'link': self.safe_str(data.get('LINK_STATUS')),
                'protocol': self.safe_str(data.get('ADMIN_STATE'))
            },
            'hardware': {
                'type': self.safe_str(data.get('HARDWARE_TYPE')),
                'mac_address': self.safe_str(data.get('MAC_ADDRESS')),
                'bia': self.safe_str(data.get('BIA')),
                'mtu': self.safe_int(data.get('MTU')),
                'bandwidth': self.safe_str(data.get('BANDWIDTH')),
                'duplex': self.safe_str(data.get('DUPLEX')),
                'speed': self.safe_str(data.get('SPEED'))
            },
            'description': self.safe_str(data.get('DESCRIPTION')),
            'ip': self.format_ip(data.get('IP_ADDRESS'), data.get('PREFIX_LENGTH')),
            'counters': {
                'input_packets': self.safe_int(data.get('INPUT_PACKETS')),
                'output_packets': self.safe_int(data.get('OUTPUT_PACKETS')),
                'input_errors': self.safe_int(data.get('INPUT_ERRORS')),
                'output_errors': self.safe_int(data.get('OUTPUT_ERRORS')),
                'last_flap': self.safe_str(data.get('LAST_LINK_FLAPPED'))
            }
        }