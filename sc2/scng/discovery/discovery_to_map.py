#!/usr/bin/env python3
"""
Convert discovery_summary.json to map.json topology format.

Usage:
    python discovery_to_map.py discovery_summary.json
    python discovery_to_map.py discovery_summary.json -o custom_map.json
    python discovery_to_map.py /path/to/discovery_*/discovery_summary.json
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Set


def extract_platform(sys_descr: str, vendor: str = None) -> str:
    """
    Extract a concise platform string from sysDescr.

    Examples:
        "Arista Networks EOS version 4.33.1F running on an Arista vEOS-lab"
        -> "Arista vEOS-lab EOS 4.33.1F"

        "Cisco IOS Software, IOSv Software (VIOS-ADVENTERPRISEK9-M), Version 15.6(2)T..."
        -> "Cisco IOSv IOS 15.6(2)T"
    """
    if not sys_descr:
        return "Unknown"

    # Arista pattern
    if 'Arista' in sys_descr:
        model = "Arista"
        version = ""
        if 'vEOS-lab' in sys_descr:
            model = "Arista vEOS-lab"
        elif 'vEOS' in sys_descr:
            model = "Arista vEOS"
        eos_match = re.search(r'EOS version (\S+)', sys_descr)
        if eos_match:
            version = f"EOS {eos_match.group(1)}"
        return f"{model} {version}".strip()

    # Cisco IOS pattern
    if 'Cisco IOS' in sys_descr or 'Cisco' in sys_descr:
        model = "Cisco"

        if 'IOSv' in sys_descr or 'VIOS' in sys_descr:
            model = "Cisco IOSv"
        elif 'vios_l2' in sys_descr:
            model = "Cisco IOS"
        elif '7206VXR' in sys_descr:
            model = "Cisco 7206VXR"
        elif '7200' in sys_descr:
            model = "Cisco 7200"

        version_match = re.search(r'Version (\S+),', sys_descr)
        if version_match:
            return f"{model} IOS {version_match.group(1)}"

        return model

    # Juniper pattern
    if 'Juniper' in sys_descr or 'JUNOS' in sys_descr:
        version_match = re.search(r'JUNOS (\S+)', sys_descr)
        if version_match:
            return f"Juniper JUNOS {version_match.group(1)}"
        return "Juniper"

    # Default: return first 50 chars
    return sys_descr[:50].strip()


def normalize_interface(interface: str) -> str:
    """Normalize interface name for consistent display and deduplication."""
    if not interface:
        return ""

    result = interface.strip()

    # Common long-form abbreviations
    replacements = [
        ("GigabitEthernet", "Gi"),
        ("TenGigabitEthernet", "Te"),
        ("FortyGigabitEthernet", "Fo"),
        ("HundredGigE", "Hu"),
        ("FastEthernet", "Fa"),
        ("Ethernet", "Eth"),
    ]

    for long, short in replacements:
        if result.startswith(long):
            result = short + result[len(long):]
            break

    # Normalize short forms: Et1/1 -> Eth1/1
    result = re.sub(r'^Et(\d)', r'Eth\1', result)

    return result


def connections_equal(conn1: List[str], conn2: List[str]) -> bool:
    """Check if two connections are equivalent (same interfaces, normalized)."""
    if len(conn1) != 2 or len(conn2) != 2:
        return False

    local1, remote1 = normalize_interface(conn1[0]), normalize_interface(conn1[1])
    local2, remote2 = normalize_interface(conn2[0]), normalize_interface(conn2[1])

    return local1 == local2 and remote1 == remote2


def generate_topology_map(devices: List[Dict], verbose: bool = False) -> Dict[str, Any]:
    """
    Generate topology map from discovered devices with bidirectional validation.

    Connections are only included if:
    1. Both sides confirm the link (bidirectional), OR
    2. The peer wasn't discovered (leaf/edge case - trust unidirectional)

    Args:
        devices: List of device dicts from discovery_summary.json
        verbose: Print debug info about dropped connections

    Returns:
        Topology map dict suitable for visualization
    """
    # Build lookup for device info by various identifiers
    device_info: Dict[str, Dict] = {}
    for device in devices:
        hostname = device.get('hostname', '')
        sys_name = device.get('sys_name', '')
        ip_address = device.get('ip_address', '')

        if hostname:
            device_info[hostname] = device
        if sys_name and sys_name != hostname:
            device_info[sys_name] = device
        if ip_address:
            device_info[ip_address] = device

    # Get canonical name for a device
    def get_canonical_name(device: Dict) -> str:
        return device.get('sys_name') or device.get('hostname') or device.get('ip_address', '')

    # Build set of discovered device canonical names
    discovered_devices: Set[str] = set()
    for device in devices:
        canonical = get_canonical_name(device)
        if canonical:
            discovered_devices.add(canonical)
            if device.get('sys_name'):
                discovered_devices.add(device['sys_name'])
            if device.get('hostname'):
                discovered_devices.add(device['hostname'])

    # First pass: collect all neighbor claims
    # Key: (canonical_device, normalized_local_if) -> list of (canonical_peer, normalized_remote_if, neighbor)
    all_claims: Dict[tuple, List[tuple]] = {}

    for device in devices:
        device_canonical = get_canonical_name(device)
        if not device_canonical:
            continue

        for neighbor in device.get('neighbors', []):
            if not neighbor.get('remote_device'):
                continue

            local_if = normalize_interface(neighbor.get('local_interface', ''))
            remote_if = normalize_interface(neighbor.get('remote_interface', ''))

            if not local_if or not remote_if:
                continue

            # Get canonical peer name
            peer_name = neighbor['remote_device']
            canonical_peer = peer_name
            if peer_name in device_info:
                peer_dev = device_info[peer_name]
                canonical_peer = get_canonical_name(peer_dev)

            key = (device_canonical, local_if)
            if key not in all_claims:
                all_claims[key] = []
            all_claims[key].append((canonical_peer, remote_if, neighbor))

    # Helper to check if reverse claim exists
    def has_reverse_claim(device_canonical: str, local_if: str,
                          peer_canonical: str, remote_if: str) -> bool:
        """Check if peer claims the reverse connection."""
        reverse_key = (peer_canonical, remote_if)
        if reverse_key not in all_claims:
            return False

        for (claimed_peer, claimed_remote, _) in all_claims[reverse_key]:
            # Peer should claim connection back to us on our local interface
            if claimed_peer == device_canonical and claimed_remote == local_if:
                return True
            # Also check if claimed_peer matches any of our identifiers
            if device_canonical in device_info:
                dev = device_info[device_canonical]
                if claimed_peer in [dev.get('hostname'), dev.get('sys_name'), dev.get('ip_address')]:
                    if claimed_remote == local_if:
                        return True
        return False

    # Helper to check if peer was discovered
    def peer_was_discovered(peer_canonical: str, peer_name_original: str) -> bool:
        """Check if we discovered this peer."""
        if peer_canonical in discovered_devices:
            return True
        if peer_name_original in discovered_devices:
            return True
        if peer_name_original in device_info:
            return True
        return False

    # Second pass: build topology with validated connections
    topology: Dict[str, Any] = {}
    seen_devices: Set[str] = set()
    dropped_count = 0

    for device in devices:
        canonical_name = get_canonical_name(device)
        if not canonical_name or canonical_name in seen_devices:
            continue
        seen_devices.add(canonical_name)

        vendor = device.get('vendor', '')
        sys_descr = device.get('sys_descr', '')

        node = {
            "node_details": {
                "ip": device.get('ip_address', ''),
                "platform": extract_platform(sys_descr, vendor)
            },
            "peers": {}
        }

        # Group validated connections by peer
        peer_connections: Dict[str, Dict] = {}
        used_local_interfaces: Set[str] = set()

        for neighbor in device.get('neighbors', []):
            if not neighbor.get('remote_device'):
                continue

            local_if = normalize_interface(neighbor.get('local_interface', ''))
            remote_if = normalize_interface(neighbor.get('remote_interface', ''))

            if not local_if or not remote_if:
                continue

            # Skip if we've already used this local interface
            if local_if in used_local_interfaces:
                continue

            # Get canonical peer name
            peer_name = neighbor['remote_device']
            canonical_peer = peer_name
            if peer_name in device_info:
                peer_dev = device_info[peer_name]
                canonical_peer = get_canonical_name(peer_dev)

            # Validate connection
            peer_discovered = peer_was_discovered(canonical_peer, peer_name)

            if peer_discovered:
                # Peer was discovered - require bidirectional confirmation
                if not has_reverse_claim(canonical_name, local_if, canonical_peer, remote_if):
                    if verbose:
                        print(f"  Dropping unconfirmed: {canonical_name}:{local_if} -> {canonical_peer}:{remote_if}")
                    dropped_count += 1
                    continue
            # else: peer not discovered (leaf/edge) - trust unidirectional claim

            # Get peer platform
            remote_desc = neighbor.get('remote_description', '')
            peer_platform = extract_platform(remote_desc) if remote_desc else None
            if peer_name in device_info:
                peer_dev = device_info[peer_name]
                peer_platform = extract_platform(
                    peer_dev.get('sys_descr', ''),
                    peer_dev.get('vendor', '')
                )

            if canonical_peer not in peer_connections:
                peer_connections[canonical_peer] = {
                    "ip": neighbor.get('remote_ip', ''),
                    "platform": peer_platform or "Unknown",
                    "connections": []
                }

            # Add validated connection
            conn = [local_if, remote_if]
            peer_connections[canonical_peer]["connections"].append(conn)
            used_local_interfaces.add(local_if)

        node["peers"] = peer_connections
        topology[canonical_name] = node

    if verbose and dropped_count > 0:
        print(f"  Dropped {dropped_count} unconfirmed connections")

    return topology


def main():
    parser = argparse.ArgumentParser(
        description='Convert discovery_summary.json to map.json topology format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python discovery_to_map.py discovery_summary.json
  python discovery_to_map.py discovery_summary.json -o network_map.json
  python discovery_to_map.py ./discovery_20251223_200000/discovery_summary.json
        """
    )
    parser.add_argument(
        'input',
        type=Path,
        help='Path to discovery_summary.json file'
    )
    parser.add_argument(
        '-o', '--output',
        type=Path,
        help='Output file path (default: map.json in same directory as input)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show processing details'
    )

    args = parser.parse_args()

    # Validate input
    if not args.input.exists():
        print(f"ERROR: Input file not found: {args.input}", file=sys.stderr)
        return 1

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        output_path = args.input.parent / 'map.json'

    # Load discovery summary
    if args.verbose:
        print(f"Loading: {args.input}")

    try:
        with open(args.input, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in {args.input}: {e}", file=sys.stderr)
        return 1

    # Extract devices list
    if 'devices' in data:
        devices = data['devices']
    elif isinstance(data, list):
        devices = data
    else:
        print("ERROR: Could not find devices list in input file", file=sys.stderr)
        return 1

    if args.verbose:
        print(f"Found {len(devices)} devices")

    # Generate topology map
    topology = generate_topology_map(devices, verbose=args.verbose)

    if args.verbose:
        print(f"Generated topology with {len(topology)} nodes")

    # Write output
    with open(output_path, 'w') as f:
        json.dump(topology, f, indent=2)

    print(f"Topology map saved to: {output_path}")

    # Print summary
    total_connections = sum(
        sum(len(peer['connections']) for peer in node['peers'].values())
        for node in topology.values()
    )
    print(f"  Nodes: {len(topology)}")
    print(f"  Connections: {total_connections}")

    return 0


if __name__ == '__main__':
    sys.exit(main())