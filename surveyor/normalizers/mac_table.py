from typing import Dict, List, Any, Optional
from datetime import datetime
import re


class MacTableNormalizer:
    def __init__(self):
        self.normalizers = {
            'arista': self._normalize_arista,
            'cisco': self._normalize_cisco,
            'nxos': self._normalize_nxos
        }
        self.mac_pattern = re.compile(r'[0-9a-fA-F]{4}\.[0-9a-fA-F]{4}\.[0-9a-fA-F]{4}|'
                                      r'[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}|'
                                      r'[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}|'
                                      r'[0-9a-fA-F]{12}')

    @staticmethod
    def safe_str(value: Any, default: str = '') -> str:
        """Safely convert value to string."""
        if value is None:
            return default
        if isinstance(value, str):
            return value.strip()
        return str(value)

    def normalize_mac(self, mac: str) -> str:
        """Normalize MAC address format to xx:xx:xx:xx:xx:xx."""
        if not mac:
            return ''

        # Find MAC address in the string
        match = self.mac_pattern.search(mac)
        if not match:
            return mac

        mac = match.group(0)
        # Remove any separators and convert to lowercase
        clean_mac = ''.join(c for c in mac if c.isalnum()).lower()
        if len(clean_mac) != 12:
            return mac
        return ':'.join(clean_mac[i:i + 2] for i in range(0, 12, 2))

    def normalize(self, parsed_data: Dict, vendor: str) -> Dict[str, Any]:
        """Normalize parsed MAC table data into a standard format."""
        if not parsed_data:
            return {
                'entries': [],
                '_metadata': {
                    'normalized_timestamp': datetime.utcnow().isoformat(),
                    'source_vendor': vendor,
                    'schema_version': '1.0',
                    'raw_data': parsed_data
                }
            }

        normalizer = self.normalizers.get(vendor)
        if not normalizer:
            raise ValueError(f"Unsupported vendor: {vendor}")

        normalized_entries = []
        try:
            entries = normalizer(parsed_data)
            for entry in entries:
                if entry and entry.get('mac_address'):  # Only include entries with valid MAC addresses
                    normalized_entries.append(entry)
        except Exception as e:
            print(f"Error normalizing MAC table: {e}")
            print(f"Problem data: {parsed_data}")

        return {
            'entries': normalized_entries,
            '_metadata': {
                'normalized_timestamp': datetime.utcnow().isoformat(),
                'source_vendor': vendor,
                'schema_version': '1.0',
                'raw_data': parsed_data
            }
        }

    def _normalize_arista(self, data: Dict) -> List[Dict]:
        """Normalize Arista JSON MAC table data."""
        entries = []
        unicast_entries = data.get('unicastTable', {}).get('tableEntries', [])

        for entry in unicast_entries:
            if not entry:
                continue

            normalized = {
                'vlan_id': entry.get('vlanId', 0),
                'mac_address': self.normalize_mac(entry.get('macAddress', '')),
                'type': entry.get('entryType', '').lower(),
                'interface': self.safe_str(entry.get('interface')),
                'moves': entry.get('moves', 0),
                'last_move': entry.get('lastMove', 0),
                '_vendor': 'arista'
            }
            entries.append(normalized)

        return entries

    def _normalize_cisco(self, data: List[Dict]) -> List[Dict]:
        """Normalize Cisco IOS TTP-parsed MAC table data.

        TTP parser returns a list of template matches, where each match is a list of dictionaries.
        Format: [[{'mac_addess': '...', 'vlan': '...', ...}], ...]
        """
        entries = []

        try:
            # If TTP returned multiple matches (multiple templates), flatten them
            if isinstance(data, list):
                # Flatten list of lists into single list of dictionaries
                flattened_data = []
                for sublist in data:
                    if isinstance(sublist, list):
                        flattened_data.extend(sublist)
                    elif isinstance(sublist, dict):
                        flattened_data.append(sublist)
                data = flattened_data

            # Handle single dict case
            if isinstance(data, dict):
                data = [data]

            # Process each entry
            for entry in data:
                if not entry:
                    continue

                # Look for MAC address in either mac_address or mac_addess (handle typo in original data)
                mac = entry.get('mac_address') or entry.get('mac_addess', '')
                if not mac:  # Skip entries without MAC addresses
                    continue

                # Handle 'All' VLAN as VLAN 0 (reserved for system VLANs)
                vlan_str = entry.get('vlan', '0')
                try:
                    vlan = 0 if vlan_str.lower() == 'all' else int(vlan_str)
                except ValueError:
                    vlan = 0

                normalized = {
                    'vlan_id': vlan,
                    'mac_address': self.normalize_mac(mac),
                    'type': self.safe_str(entry.get('learned_type', '')).lower(),
                    'interface': self.safe_str(entry.get('ports')),
                    'moves': 0,  # Not available in IOS output
                    'last_move': 0,  # Not available in IOS output
                    '_vendor': 'cisco'
                }
                if normalized['mac_address']:  # Only add entries with valid MAC addresses
                    entries.append(normalized)

        except Exception as e:
            print(f"Error in _normalize_cisco: {str(e)}")
            print(f"Input data: {data}")
            raise

        return entries
    def _normalize_nxos(self, data: List[Dict]) -> List[Dict]:
        """Normalize Cisco NXOS TTP-parsed MAC table data."""
        entries = []
        # Handle both single dict and list of dicts
        if isinstance(data, dict):
            data = [data]

        for entry in data:
            if not entry:
                continue

            normalized = {
                'vlan_id': int(self.safe_str(entry.get('vlan', '0'))),
                'mac_address': self.normalize_mac(entry.get('mac_address', '')),
                'type': self.safe_str(entry.get('learned_type', '')).lower(),
                'interface': self.safe_str(entry.get('ports')),
                'moves': 0,  # Not typically available in NXOS output
                'last_move': 0,  # Could potentially use 'age' field but format varies
                'entry_type': self.safe_str(entry.get('entry_type')),
                'secure': entry.get('secure') == 'T',
                'notify': entry.get('ntfy') == 'T',
                '_vendor': 'nxos'
            }
            if normalized['mac_address']:  # Only add entries with valid MAC addresses
                entries.append(normalized)

        return entries