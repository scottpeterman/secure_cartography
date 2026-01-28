#!/usr/bin/env python3
"""
Device Fingerprinting Utility
Identifies network devices using SNMP sysDescr/sysObjectID via Recog patterns,
OUI vendor lookup from MAC addresses, and interface/ARP table correlation.
"""

import sys
import os
import re
import json
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
import urllib.request
import subprocess

__version__ = "0.1.0"

# SNMP OIDs
OIDS = {
    'sysDescr': '1.3.6.1.2.1.1.1.0',
    'sysObjectID': '1.3.6.1.2.1.1.2.0',
    'sysName': '1.3.6.1.2.1.1.5.0',
    'sysContact': '1.3.6.1.2.1.1.4.0',
    'sysLocation': '1.3.6.1.2.1.1.6.0',
    'sysUpTime': '1.3.6.1.2.1.1.3.0',
}

WALK_OIDS = {
    'ifDescr': '1.3.6.1.2.1.2.2.1.2',
    'ifPhysAddress': '1.3.6.1.2.1.2.2.1.6',
    'ipNetToMediaPhysAddress': '1.3.6.1.2.1.4.22.1.2',
    'ipNetToMediaNetAddress': '1.3.6.1.2.1.4.22.1.3',
}

DATA_DIR = Path(__file__).parent / 'data'


@dataclass
class FingerprintMatch:
    """Result from Recog pattern matching"""
    matched: str
    params: Dict[str, str] = field(default_factory=dict)
    pattern: str = ""


@dataclass
class DeviceFingerprint:
    """Consolidated device fingerprint"""
    ip: str
    snmp_data: Dict[str, str] = field(default_factory=dict)
    recog_matches: List[FingerprintMatch] = field(default_factory=list)
    oui_lookups: Dict[str, Dict] = field(default_factory=dict)
    interfaces: List[Dict] = field(default_factory=list)
    arp_table: List[Dict] = field(default_factory=list)


class RecogMatcher:
    """Parse and match against Recog XML fingerprint files"""

    def __init__(self, xml_dir: Path, verbose: bool = False):
        self.xml_dir = xml_dir
        self.verbose = verbose
        self.fingerprints = {}
        self._load_fingerprints()

    def _load_fingerprints(self):
        """Load all XML fingerprint files"""
        for xml_file in self.xml_dir.glob('*.xml'):
            try:
                tree = ET.parse(xml_file)
                root = tree.getroot()
                matches_type = root.get('matches', xml_file.stem)

                fps = []
                for fp in root.findall('fingerprint'):
                    pattern = fp.get('pattern')
                    flags = fp.get('flags', '')
                    description = fp.find('description')
                    desc_text = description.text if description is not None else ''

                    params = []
                    for param in fp.findall('param'):
                        params.append({
                            'pos': int(param.get('pos', 0)),
                            'name': param.get('name'),
                            'value': param.get('value')
                        })

                    regex_flags = 0
                    if 'i' in flags:
                        regex_flags |= re.IGNORECASE
                    if 's' in flags:
                        regex_flags |= re.DOTALL
                    if 'm' in flags:
                        regex_flags |= re.MULTILINE

                    try:
                        compiled = re.compile(pattern, regex_flags)
                        fps.append({
                            'pattern': pattern,
                            'regex': compiled,
                            'description': desc_text,
                            'params': params
                        })
                    except re.error:
                        pass

                self.fingerprints[matches_type] = fps
                if self.verbose:
                    print(f"  Loaded {len(fps)} fingerprints from {xml_file.name}")

            except ET.ParseError as e:
                if self.verbose:
                    print(f"  Warning: Could not parse {xml_file.name}: {e}")

    def match(self, data: str, match_type: str) -> List[FingerprintMatch]:
        """Match data against fingerprints of a given type"""
        results = []

        fps = self.fingerprints.get(match_type, [])
        for fp in fps:
            m = fp['regex'].search(data)
            if m:
                params = {}
                for param in fp['params']:
                    pos = param['pos']
                    name = param['name']
                    value = param.get('value')

                    if name.startswith('_tmp.'):
                        continue

                    if pos == 0 and value:
                        params[name] = value
                    elif pos > 0:
                        try:
                            params[name] = m.group(pos)
                        except IndexError:
                            pass

                for key, val in list(params.items()):
                    if val and '{' in val:
                        for pname, pval in params.items():
                            if pval:
                                val = val.replace(f'{{{pname}}}', pval)
                        params[key] = val

                results.append(FingerprintMatch(
                    matched=fp['description'],
                    params=params,
                    pattern=fp['pattern']
                ))

        return results


class OUILookup:
    """MAC address OUI vendor lookup"""

    def __init__(self, oui_file: Path, verbose: bool = False):
        self.oui_db = {}
        self.verbose = verbose

        if oui_file.suffix == '.json' and oui_file.exists():
            self._load_db(oui_file)
        if not self.oui_db:
            manuf_file = oui_file.parent / 'manuf.txt'
            if manuf_file.exists():
                self._load_manuf(manuf_file)

    def _load_db(self, oui_file: Path):
        """Load OUI database (JSON format)"""
        if not oui_file.exists():
            if self.verbose:
                print(f"  Warning: OUI database not found at {oui_file}")
            return

        try:
            with open(oui_file, 'r') as f:
                self.oui_db = json.load(f)
            if self.verbose:
                print(f"  Loaded {len(self.oui_db)} OUI entries")
        except json.JSONDecodeError as e:
            if self.verbose:
                print(f"  Warning: Could not parse OUI database: {e}")

    def _load_manuf(self, manuf_file: Path):
        """Load Wireshark manuf format"""
        if not manuf_file.exists():
            return

        with open(manuf_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    oui = parts[0].upper().replace('-', ':')
                    if '/' in oui:
                        oui = oui.split('/')[0]
                    if len(oui) >= 8:
                        oui = oui[:8]
                    short_name = parts[1] if len(parts) > 1 else ''
                    full_name = ' '.join(parts[2:]) if len(parts) > 2 else short_name
                    self.oui_db[oui] = {
                        'manufacturer': full_name if full_name else short_name,
                        'short': short_name
                    }

        if self.verbose:
            print(f"  Loaded {len(self.oui_db)} OUI entries from manuf")

    def lookup(self, mac: str) -> Optional[Dict]:
        """Look up a MAC address, return vendor info"""
        mac_clean = mac.upper().replace('-', ':').replace('.', '')

        if ':' not in mac_clean and len(mac_clean) >= 6:
            mac_clean = ':'.join([mac_clean[i:i + 2] for i in range(0, len(mac_clean), 2)])

        oui = mac_clean[:8].upper()

        if oui in self.oui_db:
            return self.oui_db[oui]

        oui_nosep = oui.replace(':', '')
        for key in self.oui_db:
            if key.replace(':', '').replace('-', '') == oui_nosep:
                return self.oui_db[key]

        return None


def run_snmpget(ip: str, community: str, oid: str, version: str = '2c',
                timeout: int = 10) -> Optional[str]:
    """Run snmpget and return the value"""
    try:
        result = subprocess.run(
            ['snmpget', f'-v{version}', '-c', community, '-OvQ', ip, oid],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        if result.returncode == 0:
            value = result.stdout.strip().strip('"')
            return value if value and value != 'No Such Object' else None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def run_snmpwalk(ip: str, community: str, oid: str, version: str = '2c',
                 timeout: int = 30) -> List[tuple]:
    """Run snmpwalk and return list of (oid_suffix, value) tuples"""
    results = []
    try:
        result = subprocess.run(
            ['snmpwalk', f'-v{version}', '-c', community, '-OvQ', '-On', ip, oid],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if line and '=' in line:
                    parts = line.split(' = ', 1)
                    if len(parts) == 2:
                        results.append((parts[0].strip(), parts[1].strip().strip('"')))
                elif line:
                    results.append(('', line.strip().strip('"')))
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return results


def mac_bytes_to_string(mac_bytes: str) -> str:
    """Convert SNMP MAC format to readable string"""
    clean = mac_bytes.strip()

    if ':' in clean and not clean.startswith('0x'):
        parts = clean.split(':')
        if len(parts) == 6:
            return ':'.join(p.upper().zfill(2) for p in parts)

    if mac_bytes.startswith('0x') or mac_bytes.startswith('Hex-STRING:'):
        hex_str = mac_bytes.replace('0x', '').replace('Hex-STRING:', '').strip()
        hex_str = hex_str.replace(' ', '')
        if len(hex_str) >= 12:
            return ':'.join([hex_str[i:i + 2].upper() for i in range(0, 12, 2)])

    if len(clean) == 17 and (':' in clean or '-' in clean):
        return clean.upper().replace('-', ':')

    return mac_bytes


def download_data_files(verbose: bool = False):
    """Download Recog XML and OUI database if not present"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    recog_dir = DATA_DIR / 'recog'
    recog_dir.mkdir(exist_ok=True)

    recog_files = [
        'snmp_sysdescr.xml',
        'snmp_sysobjid.xml',
        'ssh_banners.xml',
        'http_servers.xml',
    ]

    if verbose:
        print("Checking/downloading data files...")

    for fname in recog_files:
        fpath = recog_dir / fname
        if not fpath.exists():
            url = f'https://raw.githubusercontent.com/rapid7/recog/main/xml/{fname}'
            if verbose:
                print(f"  Downloading {fname}...")
            try:
                urllib.request.urlretrieve(url, fpath)
            except Exception as e:
                if verbose:
                    print(f"  Warning: Could not download {fname}: {e}")

    oui_file = DATA_DIR / 'oui.json'
    if not oui_file.exists():
        if verbose:
            print("  Downloading OUI database...")
        url = 'https://raw.githubusercontent.com/Ringmast4r/OUI-Master-Database/main/LISTS/master_oui.min.json'
        try:
            urllib.request.urlretrieve(url, oui_file)
        except Exception as e:
            if verbose:
                print(f"  Warning: Could not download OUI database: {e}")

    return recog_dir, oui_file


def fingerprint_device(ip: str, community: str = 'public', version: str = '2c',
                       timeout: int = 10, verbose: bool = False,
                       skip_arp: bool = False, skip_interfaces: bool = False) -> DeviceFingerprint:
    """Main fingerprinting function"""

    if verbose:
        print(f"\n{'=' * 60}")
        print(f"DEVICE FINGERPRINTING: {ip}")
        print(f"{'=' * 60}")
        print(f"\nChecking SNMP connectivity...")

    # Precheck
    sysname = run_snmpget(ip, community, OIDS['sysName'], version, timeout)
    if not sysname:
        if verbose:
            print(f"  ✗ No SNMP response from {ip}")
        return DeviceFingerprint(ip=ip)

    if verbose:
        print(f"  ✓ {sysname}")

    recog_dir, oui_file = download_data_files(verbose)

    if verbose:
        print("\nLoading fingerprint databases...")

    recog = RecogMatcher(recog_dir, verbose)
    oui = OUILookup(oui_file, verbose)

    result = DeviceFingerprint(ip=ip)

    # Collect SNMP data
    if verbose:
        print(f"\nQuerying SNMP data from {ip}...")

    for name, oid in OIDS.items():
        value = run_snmpget(ip, community, oid, version, timeout)
        if value:
            result.snmp_data[name] = value
            if verbose:
                print(f"  {name}: {value[:80]}{'...' if len(value) > 80 else ''}")

    if not result.snmp_data:
        return result

    # Interfaces
    if not skip_interfaces:
        if verbose:
            print("\nCollecting interface data...")

        if_descrs = run_snmpwalk(ip, community, WALK_OIDS['ifDescr'], version, timeout * 3)
        if_macs = run_snmpwalk(ip, community, WALK_OIDS['ifPhysAddress'], version, timeout * 3)

        for i, (oid, descr) in enumerate(if_descrs):
            iface = {'description': descr}
            if i < len(if_macs):
                mac = mac_bytes_to_string(if_macs[i][1])
                if mac and len(mac) >= 12 and mac != '00:00:00:00:00:00':
                    iface['mac'] = mac
            result.interfaces.append(iface)

        if verbose:
            print(f"  Found {len(result.interfaces)} interfaces")

    # ARP table
    if not skip_arp:
        if verbose:
            print("\nCollecting ARP table...")

        arp_macs = run_snmpwalk(ip, community, WALK_OIDS['ipNetToMediaPhysAddress'], version, timeout * 3)
        arp_ips = run_snmpwalk(ip, community, WALK_OIDS['ipNetToMediaNetAddress'], version, timeout * 3)

        for i, (oid, mac_raw) in enumerate(arp_macs):
            mac = mac_bytes_to_string(mac_raw)
            entry = {'mac': mac}
            if i < len(arp_ips):
                entry['ip'] = arp_ips[i][1]
            result.arp_table.append(entry)

        if verbose:
            print(f"  Found {len(result.arp_table)} ARP entries")

    # Recog matching
    if verbose:
        print("\n" + "-" * 60)
        print("RECOG FINGERPRINT MATCHING")
        print("-" * 60)

    if 'sysDescr' in result.snmp_data:
        if verbose:
            print(f"\nMatching sysDescr: {result.snmp_data['sysDescr'][:60]}...")

        matches = recog.match(result.snmp_data['sysDescr'], 'snmp.sys_description')
        if not matches:
            matches = recog.match(result.snmp_data['sysDescr'], 'snmp_sysdescr')

        for m in matches:
            result.recog_matches.append(m)
            if verbose:
                print(f"\n  MATCH: {m.matched}")
                for k, v in m.params.items():
                    print(f"    {k}: {v}")

    if 'sysObjectID' in result.snmp_data:
        if verbose:
            print(f"\nMatching sysObjectID: {result.snmp_data['sysObjectID']}")

        matches = recog.match(result.snmp_data['sysObjectID'], 'snmp.sys_object_id')
        if not matches:
            matches = recog.match(result.snmp_data['sysObjectID'], 'snmp_sysobjid')

        for m in matches:
            result.recog_matches.append(m)
            if verbose:
                print(f"\n  MATCH: {m.matched}")
                for k, v in m.params.items():
                    print(f"    {k}: {v}")

    # OUI lookups
    if verbose:
        print("\n" + "-" * 60)
        print("OUI VENDOR LOOKUPS")
        print("-" * 60)

    all_macs = set()
    for iface in result.interfaces:
        if 'mac' in iface:
            all_macs.add(iface['mac'])
    for arp in result.arp_table:
        if 'mac' in arp:
            all_macs.add(arp['mac'])

    for mac in sorted(all_macs):
        vendor_info = oui.lookup(mac)
        if vendor_info:
            result.oui_lookups[mac] = vendor_info
            if verbose:
                manufacturer = vendor_info.get('manufacturer', 'Unknown')
                device_type = vendor_info.get('device_type', '')
                print(f"\n  {mac}")
                print(f"    Manufacturer: {manufacturer}")
                if device_type:
                    print(f"    Device Type: {device_type}")
        elif verbose:
            print(f"\n  {mac}")
            print(f"    Manufacturer: Unknown")

    return result


def format_summary(fp: DeviceFingerprint) -> str:
    """Format fingerprint as human-readable summary"""
    lines = []
    lines.append(f"Target: {fp.ip}")

    if fp.snmp_data.get('sysName'):
        lines.append(f"Hostname: {fp.snmp_data['sysName']}")

    if fp.snmp_data.get('sysDescr'):
        lines.append(f"Description: {fp.snmp_data['sysDescr'][:100]}")

    os_info = {}
    hw_info = {}
    for match in fp.recog_matches:
        for k, v in match.params.items():
            if k.startswith('os.'):
                os_info[k] = v
            elif k.startswith('hw.'):
                hw_info[k] = v

    if os_info:
        lines.append("\nOperating System:")
        for k, v in os_info.items():
            lines.append(f"  {k}: {v}")

    if hw_info:
        lines.append("\nHardware:")
        for k, v in hw_info.items():
            lines.append(f"  {k}: {v}")

    vendors = set()
    for mac, info in fp.oui_lookups.items():
        if info.get('manufacturer'):
            vendors.add(info['manufacturer'])

    if vendors:
        lines.append(f"\nConnected Vendors ({len(vendors)}):")
        for v in sorted(vendors)[:10]:
            lines.append(f"  - {v}")
        if len(vendors) > 10:
            lines.append(f"  ... and {len(vendors) - 10} more")

    lines.append(f"\nStatistics:")
    lines.append(f"  Interfaces: {len(fp.interfaces)}")
    lines.append(f"  ARP entries: {len(fp.arp_table)}")
    lines.append(f"  Recog matches: {len(fp.recog_matches)}")
    lines.append(f"  OUI lookups: {len(fp.oui_lookups)}")

    return '\n'.join(lines)


def format_json(fp: DeviceFingerprint) -> str:
    """Format fingerprint as JSON"""
    output_data = {
        'ip': fp.ip,
        'snmp_data': fp.snmp_data,
        'recog_matches': [
            {'matched': m.matched, 'params': m.params, 'pattern': m.pattern}
            for m in fp.recog_matches
        ],
        'oui_lookups': fp.oui_lookups,
        'interfaces': fp.interfaces,
        'arp_table': fp.arp_table,
    }
    return json.dumps(output_data, indent=2)


def check_snmp_tools():
    """Verify net-snmp tools are available"""
    try:
        subprocess.run(['snmpget', '--version'], capture_output=True)
        return True
    except FileNotFoundError:
        return False


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser"""
    parser = argparse.ArgumentParser(
        description='Device fingerprinting via SNMP, Recog patterns, and OUI lookup',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s 192.168.1.1
  %(prog)s 192.168.1.1 -c private -V 2c
  %(prog)s 192.168.1.1 --json -o device.json
  %(prog)s 192.168.1.1 --skip-arp --timeout 5

Requires net-snmp tools (snmpget, snmpwalk):
  Ubuntu/Debian: sudo apt install snmp
  RHEL/CentOS:   sudo yum install net-snmp-utils
  macOS:         brew install net-snmp
"""
    )

    parser.add_argument('target', metavar='IP',
                        help='Target IP address')

    parser.add_argument('-c', '--community', default='public',
                        help='SNMP community string (default: public)')

    parser.add_argument('-V', '--snmp-version', choices=['1', '2c'], default='2c',
                        dest='snmp_version', help='SNMP version (default: 2c)')

    parser.add_argument('-t', '--timeout', type=int, default=10,
                        help='SNMP timeout in seconds (default: 10)')

    parser.add_argument('--json', action='store_true',
                        help='Output as JSON')

    parser.add_argument('-o', '--output', metavar='FILE',
                        help='Write output to file')

    parser.add_argument('--skip-arp', action='store_true',
                        help='Skip ARP table collection')

    parser.add_argument('--skip-interfaces', action='store_true',
                        help='Skip interface collection')

    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Verbose output with progress details')

    parser.add_argument('-q', '--quiet', action='store_true',
                        help='Suppress all output except results')

    parser.add_argument('--version', action='version',
                        version=f'%(prog)s {__version__}')

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not check_snmp_tools():
        sys.stderr.write("Error: net-snmp tools not found (snmpget, snmpwalk)\n")
        sys.stderr.write("Install with:\n")
        sys.stderr.write("  Ubuntu/Debian: sudo apt install snmp\n")
        sys.stderr.write("  RHEL/CentOS:   sudo yum install net-snmp-utils\n")
        sys.stderr.write("  macOS:         brew install net-snmp\n")
        sys.exit(1)

    # Determine verbosity
    verbose = args.verbose and not args.quiet

    result = fingerprint_device(
        ip=args.target,
        community=args.community,
        version=args.snmp_version,
        timeout=args.timeout,
        verbose=verbose,
        skip_arp=args.skip_arp,
        skip_interfaces=args.skip_interfaces,
    )

    # Format output
    if args.json:
        output = format_json(result)
    else:
        output = format_summary(result)

    # Write output
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        if not args.quiet:
            print(f"Results written to {args.output}")
    else:
        if not args.quiet or not verbose:
            print(output)


if __name__ == '__main__':
    main()