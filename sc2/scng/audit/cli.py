#!/usr/bin/env python3
"""
SecureCartography NG - Audit CLI.

Command-line interface for config and inventory collection from discovery output.

Usage:
    # Audit all devices in discovery output
    python -m sc2.scng.audit collect ./network_maps/

    # Audit specific devices
    python -m sc2.scng.audit collect ./network_maps/ --devices edge5-01.iad1,edge5-02.iad1

    # Audit only Juniper devices
    python -m sc2.scng.audit collect ./network_maps/ --vendor juniper

    # Use specific credential
    python -m sc2.scng.audit collect ./network_maps/ --credential prod-ssh

    # Generate PDF report from audit data
    python -m sc2.scng.audit report ./network_maps/ -o audit_report.pdf

    # Verbose mode
    python -m sc2.scng.audit collect ./network_maps/ -v
"""

import argparse
import sys
from pathlib import Path

from .collector import AuditCollector, DeviceAuditResult


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        prog='scng.audit',
        description='SCNG Audit Collector - Config and inventory collection',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Audit all devices in discovery output
  python -m sc2.scng.audit collect ./network_maps/

  # Audit specific devices
  python -m sc2.scng.audit collect ./network_maps/ --devices edge5-01.iad1,edge5-02.iad1

  # Audit only Juniper devices  
  python -m sc2.scng.audit collect ./network_maps/ --vendor juniper

  # Use specific credential
  python -m sc2.scng.audit collect ./network_maps/ --credential prod-ssh

  # Generate PDF report from audit data
  python -m sc2.scng.audit report ./network_maps/ -o audit_report.pdf

  # Verbose output
  python -m sc2.scng.audit collect ./network_maps/ -v
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # collect command
    collect_parser = subparsers.add_parser(
        'collect',
        help='Collect configs and inventory from discovery output'
    )
    collect_parser.add_argument(
        'discovery_path',
        help='Path to discovery output folder'
    )
    collect_parser.add_argument(
        '--devices',
        help='Comma-separated list of device hostnames to audit'
    )
    collect_parser.add_argument(
        '--vendor',
        help='Filter by vendor (cisco, juniper, arista, etc.)'
    )
    collect_parser.add_argument(
        '--credential',
        help='Specific credential name to use'
    )
    collect_parser.add_argument(
        '-t', '--timeout',
        type=int,
        default=30,
        help='SSH connection timeout in seconds (default: 30)'
    )
    collect_parser.add_argument(
        '--no-legacy',
        action='store_true',
        dest='no_legacy',
        help='Disable legacy SSH algorithm support'
    )
    collect_parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    collect_parser.add_argument(
        '--no-color',
        action='store_true',
        dest='no_color',
        help='Disable colored output'
    )

    # report command
    report_parser = subparsers.add_parser(
        'report',
        help='Generate PDF report from audit/discovery data'
    )
    report_parser.add_argument(
        'audit_path',
        help='Path to audit/discovery output folder'
    )
    report_parser.add_argument(
        '-o', '--output',
        help='Output PDF file path (default: audit_report_<timestamp>.pdf)'
    )
    report_parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )

    return parser


def print_progress(completed: int, total: int, result: DeviceAuditResult, color: bool = True):
    """Progress callback for audit collection."""
    if result.success:
        status = "\033[32m✓\033[0m" if color else "✓"
    else:
        status = "\033[31m✗\033[0m" if color else "✗"

    config = "config" if result.config_collected else ""
    inventory = "inventory" if result.inventory_collected else ""
    collected = ", ".join(filter(None, [config, inventory])) or "nothing"

    print(f"  [{completed}/{total}] {status} {result.hostname}: {collected}")


def cmd_collect(args) -> int:
    """Handle 'collect' command."""
    # Import vault - try multiple paths for different package structures
    CredentialVault = None
    try:
        from scng.creds import CredentialVault
    except ImportError:
        try:
            from sc2.scng.creds import CredentialVault
        except ImportError:
            try:
                from ..creds import CredentialVault
            except ImportError:
                pass

    if CredentialVault is None:
        print("ERROR: scng.creds module not available")
        print("Make sure the creds module is installed")
        return 1

    # Validate discovery path
    discovery_path = Path(args.discovery_path)
    if not discovery_path.exists():
        print(f"ERROR: Discovery path not found: {discovery_path}")
        return 1

    # Open vault
    vault = CredentialVault()

    if not vault.is_initialized:
        print("ERROR: Vault not initialized")
        print("Run: python -m scng.creds init")
        return 1

    # Prompt for password
    import getpass
    try:
        password = getpass.getpass("Vault password: ")
        vault.unlock(password)
    except Exception as e:
        print(f"ERROR: Failed to unlock vault: {e}")
        return 1

    # Parse device list
    devices = None
    if args.devices:
        devices = [d.strip() for d in args.devices.split(",")]

    # Print configuration
    print(f"\nAudit: {discovery_path}")
    if devices:
        print(f"Devices: {', '.join(devices)}")
    if args.vendor:
        print(f"Vendor: {args.vendor}")
    print()

    # Create collector
    collector = AuditCollector(
        vault=vault,
        timeout=args.timeout,
        legacy_mode=not args.no_legacy,
    )

    # Progress callback with color support
    use_color = not args.no_color
    progress_cb = lambda c, t, r: print_progress(c, t, r, color=use_color)

    # Run audit
    try:
        result = collector.collect(
            discovery_path=str(discovery_path),
            devices=devices,
            vendor_filter=args.vendor,
            credential_name=args.credential,
            debug=args.verbose,
            progress_callback=progress_cb,
        )
    except KeyboardInterrupt:
        print("\nAudit cancelled")
        return 130
    except Exception as e:
        print(f"ERROR: Audit failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1
    finally:
        vault.lock()

    # Print summary
    print(f"\n{'=' * 60}")
    print(f"AUDIT COMPLETE")
    print(f"{'=' * 60}")
    print(f"Devices total:   {result.devices_total}")
    print(f"Devices audited: {result.devices_audited}")
    print(f"Devices failed:  {result.devices_failed}")
    print(f"Duration:        {result.duration_seconds:.1f}s")

    # Show failures if any
    failures = [r for r in result.device_results if not r.success]
    if failures:
        print(f"\nFailed:")
        for r in failures:
            errors = "; ".join(r.errors) if r.errors else "Unknown error"
            # Truncate long errors
            if len(errors) > 60:
                errors = errors[:57] + "..."
            print(f"  {r.hostname}: {errors}")

    return 0 if result.devices_audited > 0 else 1


def cmd_report(args) -> int:
    """Handle 'report' command."""
    from .report import generate_report

    # Validate audit path
    audit_path = Path(args.audit_path)
    if not audit_path.exists():
        print(f"ERROR: Audit path not found: {audit_path}")
        return 1

    print(f"\nGenerating audit report...")
    print(f"Source: {audit_path}")

    try:
        output_path = generate_report(
            audit_path=str(audit_path),
            output_path=args.output,
            verbose=args.verbose,
        )

        print(f"\n{'=' * 60}")
        print(f"REPORT GENERATED")
        print(f"{'=' * 60}")
        print(f"Output: {output_path}")

        return 0

    except ImportError as e:
        print(f"ERROR: Missing dependency: {e}")
        print("Install with: pip install reportlab")
        return 1
    except Exception as e:
        print(f"ERROR: Report generation failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == 'collect':
        return cmd_collect(args)
    elif args.command == 'report':
        return cmd_report(args)
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())