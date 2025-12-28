"""
SecureCartography NG - CLI Interface.

Command-line interface for credential management.

Commands:
    scng-creds init              Initialize credential vault
    scng-creds unlock            Unlock vault (for scripting)
    scng-creds add ssh           Add SSH credential
    scng-creds add snmpv2c       Add SNMPv2c credential
    scng-creds add snmpv3        Add SNMPv3 credential
    scng-creds list              List credentials
    scng-creds show <name>       Show credential details
    scng-creds remove <name>     Remove credential
    scng-creds test <name> <host> Test credential
    scng-creds discover <host>   Discover working credentials
    scng-creds change-password   Change master password

Environment Variables:
    SCNG_VAULT_PASSWORD    Master password (for scripting)
    SCNG_VAULT_PATH        Path to vault database
"""

import os
import sys
import argparse
import getpass
from pathlib import Path
from typing import Optional, List

from .vault import CredentialVault, VaultNotInitialized, DuplicateCredential
from .resolver import CredentialResolver, check_dependencies
from .models import CredentialType, SNMPv3AuthProtocol, SNMPv3PrivProtocol
from .encryption import InvalidPassword


def get_vault_password(args: argparse.Namespace, prompt: str = "Vault password: ") -> str:
    """Get vault password from args, env, or prompt."""
    if hasattr(args, 'password') and args.password:
        return args.password

    env_pass = os.environ.get('SCNG_VAULT_PASSWORD')
    if env_pass:
        return env_pass

    return getpass.getpass(prompt)


def get_vault_path(args: argparse.Namespace) -> Path:
    """Get vault path from args or env."""
    if hasattr(args, 'vault_path') and args.vault_path:
        return Path(args.vault_path)

    env_path = os.environ.get('SCNG_VAULT_PATH')
    if env_path:
        return Path(env_path)

    return Path.home() / ".scng" / "credentials.db"


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog='scng-creds',
        description='SecureCartography NG Credential Manager',
    )
    parser.add_argument(
        '--vault-path', '-v',
        help='Path to vault database (default: ~/.scng/credentials.db)',
    )
    parser.add_argument(
        '--password', '-p',
        help='Vault password (or set SCNG_VAULT_PASSWORD)',
    )

    subparsers = parser.add_subparsers(dest='command', help='Command')

    # init
    init_parser = subparsers.add_parser('init', help='Initialize vault')

    # unlock (for scripting - validates password)
    unlock_parser = subparsers.add_parser('unlock', help='Validate vault password')

    # add
    add_parser = subparsers.add_parser('add', help='Add credential')
    add_subparsers = add_parser.add_subparsers(dest='cred_type', help='Credential type')

    # add ssh
    add_ssh_parser = add_subparsers.add_parser('ssh', help='Add SSH credential')
    add_ssh_parser.add_argument('name', help='Credential name')
    add_ssh_parser.add_argument('--username', '-u', required=True, help='SSH username')
    add_ssh_parser.add_argument('--password', '-P', help='SSH password (will prompt if not provided)')
    add_ssh_parser.add_argument('--key-file', '-k', help='Path to SSH private key')
    add_ssh_parser.add_argument('--port', type=int, default=22, help='SSH port')
    add_ssh_parser.add_argument('--timeout', type=int, default=30, help='Connection timeout')
    add_ssh_parser.add_argument('--description', '-d', help='Description')
    add_ssh_parser.add_argument('--default', action='store_true', help='Set as default')
    add_ssh_parser.add_argument('--priority', type=int, default=100, help='Priority (lower = higher)')
    add_ssh_parser.add_argument('--tags', help='Comma-separated tags')

    # add snmpv2c
    add_v2c_parser = add_subparsers.add_parser('snmpv2c', help='Add SNMPv2c credential')
    add_v2c_parser.add_argument('name', help='Credential name')
    add_v2c_parser.add_argument('--community', '-c', help='Community string (will prompt if not provided)')
    add_v2c_parser.add_argument('--port', type=int, default=161, help='SNMP port')
    add_v2c_parser.add_argument('--timeout', type=int, default=5, help='Request timeout')
    add_v2c_parser.add_argument('--retries', type=int, default=2, help='Number of retries')
    add_v2c_parser.add_argument('--description', '-d', help='Description')
    add_v2c_parser.add_argument('--default', action='store_true', help='Set as default')
    add_v2c_parser.add_argument('--priority', type=int, default=100, help='Priority')
    add_v2c_parser.add_argument('--tags', help='Comma-separated tags')

    # add snmpv3
    add_v3_parser = add_subparsers.add_parser('snmpv3', help='Add SNMPv3 credential')
    add_v3_parser.add_argument('name', help='Credential name')
    add_v3_parser.add_argument('--username', '-u', required=True, help='Security name')
    add_v3_parser.add_argument('--auth-protocol', '-a',
                               choices=['none', 'md5', 'sha', 'sha224', 'sha256', 'sha384', 'sha512'],
                               default='none', help='Auth protocol')
    add_v3_parser.add_argument('--auth-password', '-A', help='Auth password')
    add_v3_parser.add_argument('--priv-protocol', '-x',
                               choices=['none', 'des', 'aes', 'aes192', 'aes256'],
                               default='none', help='Privacy protocol')
    add_v3_parser.add_argument('--priv-password', '-X', help='Privacy password')
    add_v3_parser.add_argument('--context', help='Context name')
    add_v3_parser.add_argument('--port', type=int, default=161, help='SNMP port')
    add_v3_parser.add_argument('--timeout', type=int, default=5, help='Request timeout')
    add_v3_parser.add_argument('--retries', type=int, default=2, help='Number of retries')
    add_v3_parser.add_argument('--description', '-d', help='Description')
    add_v3_parser.add_argument('--default', action='store_true', help='Set as default')
    add_v3_parser.add_argument('--priority', type=int, default=100, help='Priority')
    add_v3_parser.add_argument('--tags', help='Comma-separated tags')

    # list
    list_parser = subparsers.add_parser('list', help='List credentials')
    list_parser.add_argument('--type', '-t',
                             choices=['ssh', 'snmpv2c', 'snmpv3'],
                             help='Filter by type')
    list_parser.add_argument('--tags', help='Filter by tags (comma-separated)')
    list_parser.add_argument('--defaults', action='store_true', help='Show only defaults')

    # show
    show_parser = subparsers.add_parser('show', help='Show credential details')
    show_parser.add_argument('name', help='Credential name')
    show_parser.add_argument('--reveal', '-r', action='store_true', help='Show secrets')

    # remove
    remove_parser = subparsers.add_parser('remove', help='Remove credential')
    remove_parser.add_argument('name', help='Credential name')
    remove_parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation')

    # set-default
    default_parser = subparsers.add_parser('set-default', help='Set credential as default')
    default_parser.add_argument('name', help='Credential name')

    # test
    test_parser = subparsers.add_parser('test', help='Test credential')
    test_parser.add_argument('name', help='Credential name')
    test_parser.add_argument('host', help='Target host')
    test_parser.add_argument('--port', type=int, help='Override port')
    test_parser.add_argument('--timeout', type=int, help='Override timeout')

    # discover
    discover_parser = subparsers.add_parser('discover', help='Discover working credentials')
    discover_parser.add_argument('host', help='Target host')
    discover_parser.add_argument('--type', '-t',
                                 choices=['ssh', 'snmpv2c', 'snmpv3'],
                                 action='append', dest='types',
                                 help='Credential types to test')
    discover_parser.add_argument('--credentials', '-c',
                                 help='Specific credentials to test (comma-separated)')

    # change-password
    chpass_parser = subparsers.add_parser('change-password', help='Change vault password')

    # deps
    deps_parser = subparsers.add_parser('deps', help='Check dependencies')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Route to handler
    handlers = {
        'init': handle_init,
        'unlock': handle_unlock,
        'add': handle_add,
        'list': handle_list,
        'show': handle_show,
        'remove': handle_remove,
        'set-default': handle_set_default,
        'test': handle_test,
        'discover': handle_discover,
        'change-password': handle_change_password,
        'deps': handle_deps,
    }

    handler = handlers.get(args.command)
    if handler:
        return handler(args)

    parser.print_help()
    return 1


def handle_init(args: argparse.Namespace) -> int:
    """Initialize vault."""
    vault_path = get_vault_path(args)
    vault = CredentialVault(vault_path)

    if vault.is_initialized:
        print(f"Vault already initialized at: {vault_path}")
        return 1

    print(f"Initializing vault at: {vault_path}")
    print()

    password = getpass.getpass("Enter master password: ")
    confirm = getpass.getpass("Confirm master password: ")

    if password != confirm:
        print("Error: Passwords do not match")
        return 1

    if len(password) < 8:
        print("Error: Password must be at least 8 characters")
        return 1

    try:
        vault.initialize(password)
        print()
        print("✓ Vault initialized successfully")
        print()
        print("Next steps:")
        print("  scng-creds add ssh <name> --username <user>")
        print("  scng-creds add snmpv2c <name> --community <string>")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


def handle_unlock(args: argparse.Namespace) -> int:
    """Validate vault password (for scripting)."""
    vault_path = get_vault_path(args)
    vault = CredentialVault(vault_path)

    if not vault.is_initialized:
        print("Error: Vault not initialized")
        return 1

    password = get_vault_password(args)

    try:
        vault.unlock(password)
        print("✓ Vault unlocked successfully")
        vault.lock()
        return 0
    except InvalidPassword:
        print("Error: Invalid password")
        return 1


def handle_add(args: argparse.Namespace) -> int:
    """Add credential."""
    if not args.cred_type:
        print("Usage: scng-creds add {ssh|snmpv2c|snmpv3} ...")
        return 1

    vault_path = get_vault_path(args)
    vault = CredentialVault(vault_path)

    if not vault.is_initialized:
        print("Error: Vault not initialized. Run 'scng-creds init' first.")
        return 1

    password = get_vault_password(args)

    try:
        vault.unlock(password)
    except InvalidPassword:
        print("Error: Invalid vault password")
        return 1

    try:
        tags = args.tags.split(',') if args.tags else []

        if args.cred_type == 'ssh':
            return _add_ssh(vault, args, tags)
        elif args.cred_type == 'snmpv2c':
            return _add_snmpv2c(vault, args, tags)
        elif args.cred_type == 'snmpv3':
            return _add_snmpv3(vault, args, tags)
    except DuplicateCredential as e:
        print(f"Error: {e}")
        return 1
    finally:
        vault.lock()


def _add_ssh(vault: CredentialVault, args: argparse.Namespace, tags: List[str]) -> int:
    """Add SSH credential."""
    # Get password if not provided
    ssh_password = None
    if hasattr(args, 'password') and args.password:
        ssh_password = args.password
    else:
        ssh_password = getpass.getpass(f"SSH password for {args.username} (enter to skip): ")
        if not ssh_password:
            ssh_password = None

    # Get key if specified
    key_content = None
    key_passphrase = None
    if args.key_file:
        key_path = Path(args.key_file).expanduser()
        if not key_path.exists():
            print(f"Error: Key file not found: {key_path}")
            return 1
        key_content = key_path.read_text()
        key_passphrase = getpass.getpass("Key passphrase (enter if none): ")
        if not key_passphrase:
            key_passphrase = None

    if not ssh_password and not key_content:
        print("Error: Must provide password or SSH key")
        return 1

    cred_id = vault.add_ssh_credential(
        name=args.name,
        username=args.username,
        password=ssh_password,
        key_content=key_content,
        key_passphrase=key_passphrase,
        port=args.port,
        timeout_seconds=args.timeout,
        description=args.description,
        priority=args.priority,
        is_default=args.default,
        tags=tags,
    )

    print(f"✓ Added SSH credential '{args.name}' (id={cred_id})")
    if args.default:
        print("  Set as default SSH credential")
    return 0


def _add_snmpv2c(vault: CredentialVault, args: argparse.Namespace, tags: List[str]) -> int:
    """Add SNMPv2c credential."""
    community = args.community
    if not community:
        community = getpass.getpass("Community string: ")

    if not community:
        print("Error: Community string required")
        return 1

    cred_id = vault.add_snmpv2c_credential(
        name=args.name,
        community=community,
        port=args.port,
        timeout_seconds=args.timeout,
        retries=args.retries,
        description=args.description,
        priority=args.priority,
        is_default=args.default,
        tags=tags,
    )

    print(f"✓ Added SNMPv2c credential '{args.name}' (id={cred_id})")
    if args.default:
        print("  Set as default SNMPv2c credential")
    return 0


def _add_snmpv3(vault: CredentialVault, args: argparse.Namespace, tags: List[str]) -> int:
    """Add SNMPv3 credential."""
    auth_protocol = SNMPv3AuthProtocol(args.auth_protocol)
    priv_protocol = SNMPv3PrivProtocol(args.priv_protocol)

    # Get auth password if needed
    auth_password = args.auth_password
    if auth_protocol != SNMPv3AuthProtocol.NONE and not auth_password:
        auth_password = getpass.getpass("Auth password: ")

    # Get priv password if needed
    priv_password = args.priv_password
    if priv_protocol != SNMPv3PrivProtocol.NONE and not priv_password:
        priv_password = getpass.getpass("Privacy password: ")

    cred_id = vault.add_snmpv3_credential(
        name=args.name,
        username=args.username,
        auth_protocol=auth_protocol,
        auth_password=auth_password,
        priv_protocol=priv_protocol,
        priv_password=priv_password,
        context_name=args.context or "",
        port=args.port,
        timeout_seconds=args.timeout,
        retries=args.retries,
        description=args.description,
        priority=args.priority,
        is_default=args.default,
        tags=tags,
    )

    print(f"✓ Added SNMPv3 credential '{args.name}' (id={cred_id})")
    if args.default:
        print("  Set as default SNMPv3 credential")
    return 0


def handle_list(args: argparse.Namespace) -> int:
    """List credentials."""
    vault_path = get_vault_path(args)
    vault = CredentialVault(vault_path)

    if not vault.is_initialized:
        print("Vault not initialized")
        return 1

    # Listing doesn't require unlock
    cred_type = CredentialType(args.type) if args.type else None
    tags = args.tags.split(',') if args.tags else None

    creds = vault.list_credentials(
        credential_type=cred_type,
        tags=tags,
        include_defaults_only=args.defaults,
    )

    if not creds:
        print("No credentials found")
        return 0

    # Group by type
    by_type = {}
    for c in creds:
        by_type.setdefault(c.credential_type, []).append(c)

    for ctype, type_creds in by_type.items():
        print(f"\n{ctype.value.upper()} Credentials:")
        print("-" * 40)

        for c in type_creds:
            default_marker = " (default)" if c.is_default else ""
            print(f"  {c.name}{default_marker}")

            if c.display_username:
                print(f"    Username: {c.display_username}")

            print(f"    Auth: {c.auth_summary}")

            if c.tags:
                print(f"    Tags: {', '.join(c.tags)}")

            if c.last_test_at:
                status = "✓" if c.last_test_success else "✗"
                print(f"    Last test: {status} ({c.last_test_at})")

    print()
    return 0


def handle_show(args: argparse.Namespace) -> int:
    """Show credential details."""
    vault_path = get_vault_path(args)
    vault = CredentialVault(vault_path)

    if not vault.is_initialized:
        print("Vault not initialized")
        return 1

    info = vault.get_credential_info(name=args.name)
    if not info:
        print(f"Credential '{args.name}' not found")
        return 1

    print(f"\nCredential: {info.name}")
    print("=" * 40)
    print(f"Type: {info.type_display}")
    print(f"ID: {info.id}")

    if info.description:
        print(f"Description: {info.description}")

    if info.display_username:
        print(f"Username: {info.display_username}")

    print(f"Priority: {info.priority}")
    print(f"Default: {'Yes' if info.is_default else 'No'}")

    if info.tags:
        print(f"Tags: {', '.join(info.tags)}")

    if info.created_at:
        print(f"Created: {info.created_at}")

    if info.last_used_at:
        print(f"Last used: {info.last_used_at}")

    if info.last_test_at:
        status = "Success" if info.last_test_success else "Failed"
        print(f"Last test: {status} ({info.last_test_at})")

    # Show secrets if requested
    if args.reveal:
        password = get_vault_password(args)
        try:
            vault.unlock(password)
            cred = vault.get_credential(name=args.name)

            print()
            print("Secrets:")
            print("-" * 40)

            if hasattr(cred, 'password') and cred.password:
                print(f"Password: {cred.password}")
            if hasattr(cred, 'key_content') and cred.key_content:
                print(f"SSH Key: (present, {len(cred.key_content)} bytes)")
            if hasattr(cred, 'community'):
                print(f"Community: {cred.community}")
            if hasattr(cred, 'auth_password') and cred.auth_password:
                print(f"Auth password: {cred.auth_password}")
            if hasattr(cred, 'priv_password') and cred.priv_password:
                print(f"Priv password: {cred.priv_password}")

            vault.lock()
        except InvalidPassword:
            print("Error: Invalid vault password")
            return 1

    print()
    return 0


def handle_remove(args: argparse.Namespace) -> int:
    """Remove credential."""
    vault_path = get_vault_path(args)
    vault = CredentialVault(vault_path)

    if not vault.is_initialized:
        print("Vault not initialized")
        return 1

    if not args.yes:
        confirm = input(f"Remove credential '{args.name}'? [y/N]: ")
        if confirm.lower() != 'y':
            print("Aborted")
            return 0

    if vault.remove_credential(name=args.name):
        print(f"✓ Removed credential '{args.name}'")
        return 0
    else:
        print(f"Credential '{args.name}' not found")
        return 1


def handle_set_default(args: argparse.Namespace) -> int:
    """Set credential as default."""
    vault_path = get_vault_path(args)
    vault = CredentialVault(vault_path)

    if not vault.is_initialized:
        print("Vault not initialized")
        return 1

    if vault.set_default(name=args.name):
        print(f"✓ Set '{args.name}' as default")
        return 0
    else:
        print(f"Credential '{args.name}' not found")
        return 1


def handle_test(args: argparse.Namespace) -> int:
    """Test credential."""
    vault_path = get_vault_path(args)
    vault = CredentialVault(vault_path)

    if not vault.is_initialized:
        print("Vault not initialized")
        return 1

    password = get_vault_password(args)

    try:
        vault.unlock(password)
    except InvalidPassword:
        print("Error: Invalid vault password")
        return 1

    try:
        info = vault.get_credential_info(name=args.name)
        if not info:
            print(f"Credential '{args.name}' not found")
            return 1

        print(f"Testing {info.type_display} credential '{args.name}' against {args.host}...")

        resolver = CredentialResolver(vault)

        if info.credential_type == CredentialType.SSH:
            result = resolver.test_ssh_credential(
                args.name, args.host, args.port, args.timeout
            )
        elif info.credential_type == CredentialType.SNMP_V2C:
            result = resolver.test_snmpv2c_credential(
                args.name, args.host, args.port, args.timeout
            )
        elif info.credential_type == CredentialType.SNMP_V3:
            result = resolver.test_snmpv3_credential(
                args.name, args.host, args.port, args.timeout
            )
        else:
            print(f"Unknown credential type: {info.credential_type}")
            return 1

        print()
        if result.success:
            print(f"✓ SUCCESS ({result.duration_ms:.0f}ms)")
            if result.prompt_detected:
                print(f"  Prompt: {result.prompt_detected}")
            if result.system_description:
                desc = result.system_description[:80]
                if len(result.system_description) > 80:
                    desc += "..."
                print(f"  sysDescr: {desc}")
        else:
            print(f"✗ FAILED: {result.status.value}")
            if result.error_message:
                print(f"  Error: {result.error_message}")

        return 0 if result.success else 1

    finally:
        vault.lock()


def handle_discover(args: argparse.Namespace) -> int:
    """Discover working credentials."""
    vault_path = get_vault_path(args)
    vault = CredentialVault(vault_path)

    if not vault.is_initialized:
        print("Vault not initialized")
        return 1

    password = get_vault_password(args)

    try:
        vault.unlock(password)
    except InvalidPassword:
        print("Error: Invalid vault password")
        return 1

    try:
        cred_types = None
        if args.types:
            cred_types = [CredentialType(t) for t in args.types]

        cred_names = None
        if args.credentials:
            cred_names = [n.strip() for n in args.credentials.split(',')]

        print(f"Discovering credentials for {args.host}...")
        print()

        resolver = CredentialResolver(vault)

        def on_progress(result):
            status = "✓" if result.success else "✗"
            print(f"  {status} {result.credential_name}: {result.status.value} ({result.duration_ms:.0f}ms)")

        result = resolver.discover_credentials(
            host=args.host,
            credential_types=cred_types,
            credential_names=cred_names,
            progress_callback=on_progress,
        )

        print()
        if result.success:
            print(f"✓ Found working credential: {result.matched_credential_name}")
            print(f"  Type: {result.matched_credential_type.value}")
        else:
            print("✗ No working credentials found")

        print(f"\nTested {result.attempts} credential(s) in {result.total_duration_ms:.0f}ms")

        return 0 if result.success else 1

    finally:
        vault.lock()


def handle_change_password(args: argparse.Namespace) -> int:
    """Change vault password."""
    vault_path = get_vault_path(args)
    vault = CredentialVault(vault_path)

    if not vault.is_initialized:
        print("Vault not initialized")
        return 1

    current = getpass.getpass("Current password: ")
    new_pass = getpass.getpass("New password: ")
    confirm = getpass.getpass("Confirm new password: ")

    if new_pass != confirm:
        print("Error: Passwords do not match")
        return 1

    if len(new_pass) < 8:
        print("Error: Password must be at least 8 characters")
        return 1

    try:
        vault.change_password(current, new_pass)
        print("✓ Password changed successfully")
        return 0
    except InvalidPassword:
        print("Error: Invalid current password")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def handle_deps(args: argparse.Namespace) -> int:
    """Check dependencies."""
    deps = check_dependencies()

    print("Dependencies:")
    print("-" * 40)

    for name, available in deps.items():
        status = "✓ installed" if available else "✗ not installed"
        print(f"  {name}: {status}")

    print()

    if not deps['paramiko']:
        print("Note: Install paramiko for SSH testing:")
        print("  pip install paramiko")

    if not deps['pysnmp']:
        print("Note: Install pysnmp for SNMP testing:")
        print("  pip install pysnmp")

    return 0


if __name__ == '__main__':
    sys.exit(main())