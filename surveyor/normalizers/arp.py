# normalizers/arp.py
from typing import Dict, List, Any
from datetime import datetime
from ttp import ttp

# arp_templates.py

IOS_TEMPLATE = """
<group name="arp_entries">
Protocol  Address          Age (min)  Hardware Addr   Type   Interface
Internet {{ ip | IP }} {{ age }} {{ mac }} {{ type }} {{ interface }}
</group>
"""

NXOS_TEMPLATE = """
<group name="arp_entries">
Address         Age       MAC Address     Interface       Flags
{{ ip | IP }}  {{ age }} {{ mac }} {{ interface }} {{ flags | ORPHRASE }}
</group>"""

ARISTA_TEMPLATE = """
<group name="arp_entries">
Address         Age         Hardware Addr   Interface
{{ ip | IP }}  {{ age }}  {{ mac }}  {{ interface | PHRASE | re(".+") }}
</group>
"""
ARISTA_TEMPLATE2 = '''
<group name="arp_entries">
Address         Age       MAC Address     Interface       Flags
{{ ip | IP }}  {{ age }} {{ mac }} {{ interface }} {{ flags | ORPHRASE }}
</group>'''

TEMPLATES = {
    'cisco_ios_show_ip_arp': IOS_TEMPLATE,
    'cisco_ios_show_arp': IOS_TEMPLATE,
    'cisco_nxos_show_ip_arp': NXOS_TEMPLATE,
    'arista_eos_show_ip_arp': ARISTA_TEMPLATE
}
class ARPNormalizer:
    def __init__(self):
        self.templates = TEMPLATES

    @staticmethod
    def normalize_mac(mac: str) -> str:
        """Normalize MAC address format."""
        if not mac:
            return ''
        clean_mac = ''.join(c for c in mac if c.isalnum()).lower()
        if len(clean_mac) == 12:
            return ':'.join(clean_mac[i:i + 2] for i in range(0, 12, 2))
        return mac.lower()

    @staticmethod
    def normalize_age(age: str) -> str:
        """Normalize age value."""
        if not age or age == '-':
            return 'permanent'
        return age.strip()

    def normalize(self, raw_data: str, template_name: str) -> Dict[str, Any]:
        """Normalize ARP data using TTP templates."""
        if not raw_data:
            raise ValueError("Empty raw data")

        template = self.templates.get(template_name)
        if not template:
            supported = list(self.templates.keys())
            raise ValueError(f"Unsupported template: {template_name}. Supported: {supported}")

        parser = ttp(data=raw_data, template=template)
        parser.parse()
        results = parser.result(format='dict')[0]

        if not results or 'arp_entries' not in results[0]:
            raise ValueError(f"Failed to parse ARP data using template {template_name}")

        arp_entries = {}
        for entry in results[0]['arp_entries']:
            try:
                normalized = {
                    'ip_address': entry['ip'],
                    'mac_address': self.normalize_mac(entry['mac']),
                    'age': self.normalize_age(entry.get('age')),
                    'interface': entry.get('interface', '').strip(),
                    'type': entry.get('type', 'ARPA'),
                    'vrf': 'default'
                }
                arp_entries[entry['ip']] = normalized
            except Exception as e:
                print(f"Error normalizing entry {entry}: {e}")
                continue

        return {
            'arp_table': arp_entries,
            '_metadata': {
                'normalized_timestamp': datetime.utcnow().isoformat(),
                'source_template': template_name,
                'schema_version': '1.0',
                'raw_data': raw_data
            }
        }