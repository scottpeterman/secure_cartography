# normalizers/inventory.py
from typing import Dict, List, Any, Optional
from datetime import datetime


class InventoryNormalizer:
    def __init__(self):
        self.normalizers = {
            'arista_eos_show_inventory': self._normalize_arista,
            'cisco_ios_show_inventory': self._normalize_cisco,
            'cisco_nxos_show_inventory': self._normalize_cisco  # Same format as IOS
        }

    @staticmethod
    def safe_str(value: Any, default: str = '') -> str:
        """Safely convert value to string."""
        if value is None:
            return default
        if isinstance(value, str):
            return value.strip()
        return str(value)

    def normalize(self, parsed_data: List[Dict], template_name: str) -> Dict[str, Any]:
        """Normalize parsed inventory data into a standard format."""
        if not parsed_data:
            raise ValueError("Empty parsed data")

        normalizer = self.normalizers.get(template_name)
        if not normalizer:
            raise ValueError(f"Unsupported template: {template_name}")

        components = []
        for component_data in parsed_data:
            try:
                normalized = normalizer(component_data)
                if normalized:
                    components.append(normalized)
            except Exception as e:
                print(f"Error normalizing component: {e}")
                print(f"Problem data: {component_data}")
                continue

        return {
            'components': components,
            '_metadata': {
                'normalized_timestamp': datetime.utcnow().isoformat(),
                'source_template': template_name,
                'schema_version': '1.0',
                'raw_data': parsed_data
            }
        }

    def _normalize_arista(self, data: Dict) -> Dict:
        """Normalize Arista EOS inventory data.
        Headers: ['PORT', 'NAME', 'SN', 'DESCR', 'VID']
        """
        return {
            'name': self.safe_str(data.get('NAME')),
            'description': self.safe_str(data.get('DESCR')),
            'serial_number': self.safe_str(data.get('SN')),
            'version_id': self.safe_str(data.get('VID')),
            'product_id': '',  # Not available in Arista output
            'port': self.safe_str(data.get('PORT')),  # Arista-specific field
            '_vendor': 'arista'
        }

    def _normalize_cisco(self, data: Dict) -> Dict:
        """Normalize Cisco IOS/NXOS inventory data.
        Headers: ['NAME', 'DESCR', 'PID', 'VID', 'SN']
        """
        return {
            'name': self.safe_str(data.get('NAME')),
            'description': self.safe_str(data.get('DESCR')),
            'serial_number': self.safe_str(data.get('SN')),
            'version_id': self.safe_str(data.get('VID')),
            'product_id': self.safe_str(data.get('PID')),
            'port': '',  # Not available in Cisco output
            '_vendor': 'cisco'
        }