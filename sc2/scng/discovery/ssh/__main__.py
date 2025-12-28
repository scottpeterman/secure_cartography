"""
SCNG SSH Discovery CLI.

Path: scng/discovery/ssh/__main__.py

Usage:
    python -m sc2.scng.discovery.ssh test <host> -u <user> -p <pass>
    python -m sc2.scng.discovery.ssh templates [--filter <str>]
"""

import argparse
import getpass
import json
import logging
import sys
from typing import Optional


def cmd_test(args):
    """Test SSH neighbor collection against a device."""
    from .collector import SSHCollector
    from ..models import DeviceVendor

    # Get password if not provided and no key
    password = args.password
    if not password and not args.key:
        password = getpass.getpass("SSH Password: ")

    # Verify key file exists if provided
    key_file = None
    if args.key:
        import os
        if not os.path.exists(args.key):
            print(f"Key file not found: {args.key}", file=sys.stderr)
            return 1
        key_file = args.key

    # Parse vendor hint
    vendor_hint = None
    if args.vendor:
        try:
            vendor_hint = DeviceVendor(args.vendor.lower())
        except ValueError:
            print(f"Unknown vendor: {args.vendor}", file=sys.stderr)
            print(f"Valid vendors: {[v.value for v in DeviceVendor]}")
            return 1

    # Configure logging
    if args.verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        )
    else:
        logging.basicConfig(level=logging.WARNING)

    # Create collector and run
    collector = SSHCollector(
        username=args.username,
        password=password,
        key_file=key_file,
        legacy_mode=args.legacy,
        template_db_path=args.template_db,
    )

    print(f"Connecting to {args.host}...")
    result = collector.collect(
        args.host,
        vendor_hint=vendor_hint,
        collect_cdp=not args.lldp_only,
        collect_lldp=not args.cdp_only,
    )

    # Output results
    print(f"\nVendor: {result.vendor.value}")
    print(f"Duration: {result.duration_ms:.0f}ms")
    print(f"Success: {result.success}")

    if result.errors:
        print(f"\nErrors:")
        for err in result.errors:
            print(f"  - {err}")

    print(f"\nNeighbors ({len(result.neighbors)}):")
    for n in result.neighbors:
        print(f"  [{n.protocol.value.upper()}] {n.local_interface} -> {n.remote_device}:{n.remote_interface}")
        try:
            if n.remote_ip:
                print(f"         IP: {n.remote_ip}")
        except Exception as e:
            n.remote_ip = "unknown"
            print(f"         Error: {e}")
        try:
            if n.platform:
                print(f"         Platform: {n.platform}")
        except Exception as e:
            n.platform = "unknown"


    # JSON output
    if args.output:
        output_data = {
            'host': args.host,
            'vendor': result.vendor.value,
            'success': result.success,
            'duration_ms': result.duration_ms,
            'neighbors': [n.to_dict() for n in result.neighbors],
            'errors': result.errors,
        }
        if args.include_raw:
            output_data['raw_output'] = result.raw_output

        with open(args.output, 'w') as f:
            json.dump(output_data, f, indent=2)
        print(f"\nSaved to: {args.output}")

    return 0 if result.success else 1


def cmd_templates(args):
    """List available TextFSM templates."""
    from .parsers import TextFSMParser

    parser = TextFSMParser(db_path=args.template_db)
    templates = parser.list_templates(args.filter)

    print(f"Available templates ({len(templates)}):")
    for name in templates:
        print(f"  {name}")

    return 0


def cmd_parse(args):
    """Parse raw CLI output from file."""
    from .parsers import TextFSMParser

    # Read input file
    try:
        with open(args.input, 'r') as f:
            output = f.read()
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        return 1

    parser = TextFSMParser(db_path=args.template_db)
    result = parser.parse(output, args.template)

    if result.success:
        print(f"Template: {result.template_name}")
        print(f"Score: {result.score:.1f}")
        print(f"Records: {result.record_count}")
        print()
        for i, record in enumerate(result.records, 1):
            print(f"Record {i}:")
            for key, value in record.items():
                if value:
                    print(f"  {key}: {value}")
            print()
    else:
        print(f"Parse failed: {result.error}")
        return 1

    return 0


def main():
    parser = argparse.ArgumentParser(
        prog='python -m sc2.scng.discovery.ssh',
        description='SSH-based network neighbor discovery',
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    # test command
    test_parser = subparsers.add_parser('test', help='Test SSH collection against device')
    test_parser.add_argument('host', help='Device IP or hostname')
    test_parser.add_argument('-u', '--username', required=True, help='SSH username')
    test_parser.add_argument('-p', '--password', help='SSH password')
    test_parser.add_argument('-k', '--key', help='SSH private key file')
    test_parser.add_argument('--vendor', help='Vendor hint (cisco, arista, juniper, etc.)')
    test_parser.add_argument('--legacy', action='store_true', help='Enable legacy SSH algorithms')
    test_parser.add_argument('--cdp-only', action='store_true', help='Collect CDP only')
    test_parser.add_argument('--lldp-only', action='store_true', help='Collect LLDP only')
    test_parser.add_argument('--template-db', help='Path to TextFSM templates database')
    test_parser.add_argument('-o', '--output', help='Save results to JSON file')
    test_parser.add_argument('--include-raw', action='store_true', help='Include raw output in JSON')
    test_parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    test_parser.set_defaults(func=cmd_test)

    # templates command
    templates_parser = subparsers.add_parser('templates', help='List available templates')
    templates_parser.add_argument('--filter', help='Filter templates by name')
    templates_parser.add_argument('--template-db', help='Path to TextFSM templates database')
    templates_parser.set_defaults(func=cmd_templates)

    # parse command
    parse_parser = subparsers.add_parser('parse', help='Parse CLI output from file')
    parse_parser.add_argument('input', help='Input file with CLI output')
    parse_parser.add_argument('template', help='Template filter string')
    parse_parser.add_argument('--template-db', help='Path to TextFSM templates database')
    parse_parser.set_defaults(func=cmd_parse)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == '__main__':
    main()