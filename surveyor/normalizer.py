from typing import Dict, Any, Optional, Union, List
from datetime import datetime, timedelta

from typing import Dict, Any, Optional
from datetime import datetime, timedelta


class DeviceDataNormalizer:
    def __init__(self):
        self.normalizers = {
            'cisco_ios_show_version': self._normalize_ios,
            'cisco_nxos_show_version': self._normalize_nxos,
            'arista_eos_show_version': self._normalize_arista
        }

    def normalize(self, parsed_data: Union[Dict[str, Any], List[Dict[str, Any]]], template_name: str) -> Dict[str, Any]:
        if not parsed_data:
            raise ValueError("Empty parsed data")

        normalizer = self.normalizers.get(template_name)
        if not normalizer:
            raise ValueError(f"Unsupported template: {template_name}")

        try:
            # Handle list of dictionaries by taking first item
            data_to_normalize = parsed_data[0] if isinstance(parsed_data, list) else parsed_data
            normalized = normalizer(data_to_normalize)
            return self._add_metadata(normalized, data_to_normalize, template_name)
        except Exception as e:
            raise ValueError(f"Normalization failed: {str(e)}")

    def _add_metadata(self, data: Dict[str, Any], original_tfsm_data, template_name: str) -> Dict[str, Any]:
        data['_metadata'] = {
            'normalized_timestamp': datetime.utcnow().isoformat(),
            'source_template': template_name,
            'schema_version': '1.0',
            'tfsm_data': original_tfsm_data
        }
        return data

    def _parse_uptime(self, uptime_str: str) -> Dict[str, int]:
        components = {
            'years': 0,
            'weeks': 0,
            'days': 0,
            'hours': 0,
            'minutes': 0
        }

        if not uptime_str:
            return components

        mappings = {
            'year': 'years',
            'week': 'weeks',
            'day': 'days',
            'hour': 'hours',
            'minute': 'minutes'
        }

        for part in uptime_str.lower().split(','):
            for key, value in mappings.items():
                if key in part:
                    try:
                        components[value] = int(part.split()[0])
                    except (ValueError, IndexError):
                        pass

        return components

    def _normalize_ios(self, data: Dict[str, Any]) -> Dict[str, Any]:
        uptime = self._parse_uptime(data.get('UPTIME', ''))

        return {
            'system': {
                'hostname': data.get('HOSTNAME', ''),
                'image': data.get('RUNNING_IMAGE', ''),
                'version': data.get('VERSION', ''),
                'platform': data.get('HARDWARE', [''])[0] if data.get('HARDWARE') else '',
                'uptime': uptime,
                'boot_reason': data.get('RELOAD_REASON', '')
            },
            'hardware': {
                'serial_numbers': data.get('SERIAL', []),
                'mac_addresses': data.get('MAC_ADDRESS', []),
                'model': data.get('HARDWARE', [''])[0] if data.get('HARDWARE') else '',
                'memory': {
                    'total': None,  # Not available in IOS output
                    'free': None
                }
            },
            'software': {
                'version': data.get('VERSION', ''),
                'image': data.get('SOFTWARE_IMAGE', ''),
                'rommon': data.get('ROMMON', '')
            }
        }

    def _normalize_nxos(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'system': {
                'hostname': data.get('HOSTNAME', ''),
                'image': data.get('BOOT_IMAGE', ''),
                'version': data.get('OS', ''),
                'platform': data.get('PLATFORM', ''),
                'uptime': self._parse_uptime(data.get('UPTIME', '')),
                'boot_reason': data.get('LAST_REBOOT_REASON', '')
            },
            'hardware': {
                'serial_numbers': [data.get('SERIAL', '')] if data.get('SERIAL') else [],
                'mac_addresses': [],  # Not available in NXOS output
                'model': data.get('PLATFORM', ''),
                'memory': {
                    'total': None,  # Not available in NXOS output
                    'free': None
                }
            },
            'software': {
                'version': data.get('OS', ''),
                'image': data.get('BOOT_IMAGE', ''),
                'rommon': None  # Not available in NXOS output
            }
        }

    def _normalize_arista(self, data: Dict[str, Any]) -> Dict[str, Any]:
        version = data.get('VERSION', '') or data.get('HW_VERSION', '')
        mac = data.get('SYS_MAC', '')
        model = data.get('MODEL', '')
        image = data.get('IMAGE', '')

        def safe_int(value, default=0):
            try:
                return int(value) if value else default
            except (ValueError, TypeError):
                return default

        uptime = {
            'years': 0,
            'weeks': safe_int(data.get('UPTIME_WEEKS')),
            'days': safe_int(data.get('UPTIME_DAYS')),
            'hours': safe_int(data.get('UPTIME_HOURS')),
            'minutes': safe_int(data.get('UPTIME_MINUTES'))
        }

        return {
            'system': {
                'hostname': '',
                'image': image,
                'version': version,
                'platform': model,
                'uptime': uptime,
                'boot_reason': ''
            },
            'hardware': {
                'serial_numbers': [data.get('SERIAL_NUMBER', '')] if data.get('SERIAL_NUMBER') else [],
                'mac_addresses': [mac] if mac else [],
                'model': model,
                'memory': {
                    'total': safe_int(data.get('TOTAL_MEMORY')),
                    'free': safe_int(data.get('FREE_MEMORY'))
                }
            },
            'software': {
                'version': version,
                'image': image,
                'rommon': None
            }
        }


def process_version_data(template_name: str, parsed_data: Dict) -> Dict:
    normalizer = DeviceDataNormalizer()
    try:
        return normalizer.normalize(parsed_data, template_name)
    except Exception as e:
        return {"error": f"Normalization failed: {str(e)}"}

