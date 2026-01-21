"""
SCNG Audit Collector - Config and inventory collection from discovery output.

Path: scng/audit/collector.py

Second-pass collector that reads discovery output folders and collects:
- Running configuration
- Hardware inventory

Uses vendor field from device.json to select appropriate commands.
Reuses existing SSH client and credential vault infrastructure.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from ..discovery.ssh.client import SSHClient, SSHClientConfig
from ..discovery.models import DeviceVendor

# Import vault - try multiple paths for different package structures
HAS_VAULT = False
try:
    from scng.creds import CredentialVault, CredentialType
    HAS_VAULT = True
except ImportError:
    pass

if not HAS_VAULT:
    try:
        from sc2.scng.creds import CredentialVault, CredentialType
        HAS_VAULT = True
    except ImportError:
        pass

if not HAS_VAULT:
    try:
        from ..creds import CredentialVault, CredentialType
        HAS_VAULT = True
    except ImportError:
        pass

logger = logging.getLogger(__name__)


# =============================================================================
# Vendor-specific audit commands
# =============================================================================

@dataclass
class AuditCommands:
    """Commands for audit collection per vendor."""
    config_command: str
    inventory_command: str
    pager_suffix: Optional[str] = None  # Appended to commands (e.g., "| no-more")


AUDIT_COMMANDS: Dict[str, AuditCommands] = {
    "cisco": AuditCommands(
        config_command="show running-config",
        inventory_command="show inventory",
        pager_suffix=None,  # Handled by terminal length 0
    ),
    "arista": AuditCommands(
        config_command="show running-config",
        inventory_command="show inventory",
        pager_suffix=None,
    ),
    "juniper": AuditCommands(
        config_command="show configuration",
        inventory_command="show chassis hardware",
        pager_suffix=" | no-more",
    ),
    "paloalto": AuditCommands(
        config_command="show config running",
        inventory_command="show system info",
        pager_suffix=None,  # set cli pager off handled in pagination
    ),
    "fortinet": AuditCommands(
        config_command="show full-configuration",
        inventory_command="get system status",
        pager_suffix=None,
    ),
    "huawei": AuditCommands(
        config_command="display current-configuration",
        inventory_command="display device",
        pager_suffix=None,  # screen-length 0 temporary handled in pagination
    ),
    "hp": AuditCommands(
        config_command="show running-config",
        inventory_command="show system information",
        pager_suffix=None,
    ),
    "linux": AuditCommands(
        config_command="cat /etc/network/interfaces 2>/dev/null || ip addr show",
        inventory_command="cat /proc/cpuinfo | head -30; free -h; df -h",
        pager_suffix=None,
    ),
}

# Fallback for unknown vendors
DEFAULT_AUDIT_COMMANDS = AuditCommands(
    config_command="show running-config",
    inventory_command="show inventory",
    pager_suffix=None,
)


# =============================================================================
# Result models
# =============================================================================

@dataclass
class DeviceAuditResult:
    """Result of auditing a single device."""
    hostname: str
    ip_address: str
    vendor: str
    success: bool
    config_collected: bool = False
    inventory_collected: bool = False
    config_size: int = 0
    inventory_size: int = 0
    errors: List[str] = field(default_factory=list)
    duration_ms: float = 0.0


@dataclass
class AuditResult:
    """Result of full audit run."""
    discovery_path: str
    devices_total: int
    devices_audited: int
    devices_failed: int
    device_results: List[DeviceAuditResult] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0


# =============================================================================
# Audit Collector
# =============================================================================

class AuditCollector:
    """
    Collect configurations and inventory from previously discovered devices.

    Reads discovery output folder, iterates device.json files, connects
    via SSH using vault credentials, and writes config.txt + inventory.txt.

    Example:
        from sc2.scng.creds import CredentialVault

        vault = CredentialVault()
        vault.unlock("password")

        collector = AuditCollector(vault)
        result = collector.collect("./network_maps_ktest/")

        for device in result.device_results:
            print(f"{device.hostname}: config={device.config_collected}")
    """

    def __init__(
        self,
        vault,  # CredentialVault instance
        timeout: int = 30,
        legacy_mode: bool = True,
    ):
        """
        Initialize audit collector.

        Args:
            vault: Unlocked CredentialVault instance.
            timeout: SSH connection timeout in seconds.
            legacy_mode: Enable legacy SSH algorithms (recommended).
        """
        self.vault = vault
        self.timeout = timeout
        self.legacy_mode = legacy_mode

    def collect(
        self,
        discovery_path: str,
        devices: Optional[List[str]] = None,
        vendor_filter: Optional[str] = None,
        credential_name: Optional[str] = None,
        debug: bool = False,
        progress_callback: Optional[callable] = None,
    ) -> AuditResult:
        """
        Collect configs and inventory from discovery output.

        Args:
            discovery_path: Path to discovery output folder.
            devices: Optional list of device hostnames to audit (default: all).
            vendor_filter: Optional vendor filter (e.g., "juniper").
            credential_name: Specific credential to use (default: try all SSH creds).
            debug: Enable debug output.
            progress_callback: Optional callback(completed, total, device_result).

        Returns:
            AuditResult with per-device results.
        """
        start_time = time.time()
        started_at = datetime.now()

        discovery_path = Path(discovery_path)
        if not discovery_path.exists():
            raise ValueError(f"Discovery path not found: {discovery_path}")

        # Find all device.json files
        device_folders = self._find_device_folders(discovery_path)

        if debug:
            print(f"[AUDIT] Found {len(device_folders)} device folders in {discovery_path}")

        # Filter devices if specified
        if devices:
            device_folders = {k: v for k, v in device_folders.items() if k in devices}
            if debug:
                print(f"[AUDIT] Filtered to {len(device_folders)} devices")

        device_results: List[DeviceAuditResult] = []
        devices_audited = 0
        devices_failed = 0

        total = len(device_folders)

        for idx, (hostname, folder_path) in enumerate(device_folders.items()):
            if debug:
                print(f"\n[AUDIT] === Processing {hostname} ({idx + 1}/{total}) ===")

            # Load device.json
            device_json_path = folder_path / "device.json"
            try:
                with open(device_json_path) as f:
                    device_data = json.load(f)
            except Exception as e:
                if debug:
                    print(f"[AUDIT] Failed to load device.json: {e}")
                device_results.append(DeviceAuditResult(
                    hostname=hostname,
                    ip_address="unknown",
                    vendor="unknown",
                    success=False,
                    errors=[f"Failed to load device.json: {e}"],
                ))
                devices_failed += 1
                continue

            vendor = device_data.get("vendor", "unknown")
            ip_address = device_data.get("ip_address")

            if not ip_address:
                if debug:
                    print(f"[AUDIT] No IP address in device.json, skipping")
                device_results.append(DeviceAuditResult(
                    hostname=hostname,
                    ip_address="unknown",
                    vendor=vendor,
                    success=False,
                    errors=["No IP address in device.json"],
                ))
                devices_failed += 1
                continue

            # Apply vendor filter
            if vendor_filter and vendor.lower() != vendor_filter.lower():
                if debug:
                    print(f"[AUDIT] Skipping {hostname} (vendor={vendor}, filter={vendor_filter})")
                continue

            # Audit the device
            result = self._audit_device(
                hostname=hostname,
                ip_address=ip_address,
                vendor=vendor,
                output_folder=folder_path,
                credential_name=credential_name,
                debug=debug,
            )

            device_results.append(result)

            if result.success:
                devices_audited += 1
            else:
                devices_failed += 1

            # Progress callback
            if progress_callback:
                progress_callback(idx + 1, total, result)

        completed_at = datetime.now()
        duration_seconds = time.time() - start_time

        return AuditResult(
            discovery_path=str(discovery_path),
            devices_total=total,
            devices_audited=devices_audited,
            devices_failed=devices_failed,
            device_results=device_results,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration_seconds,
        )

    def _find_device_folders(self, discovery_path: Path) -> Dict[str, Path]:
        """Find all device folders containing device.json."""
        device_folders = {}

        for item in discovery_path.iterdir():
            if item.is_dir():
                device_json = item / "device.json"
                if device_json.exists():
                    device_folders[item.name] = item

        return device_folders

    def _audit_device(
        self,
        hostname: str,
        ip_address: str,
        vendor: str,
        output_folder: Path,
        credential_name: Optional[str] = None,
        debug: bool = False,
    ) -> DeviceAuditResult:
        """Audit a single device."""
        start_time = time.time()
        errors: List[str] = []

        # Get audit commands for vendor
        commands = AUDIT_COMMANDS.get(vendor.lower(), DEFAULT_AUDIT_COMMANDS)

        if debug:
            print(f"[AUDIT] Vendor: {vendor}")
            print(f"[AUDIT] Config command: {commands.config_command}")
            print(f"[AUDIT] Inventory command: {commands.inventory_command}")

        # Get credentials
        ssh_cred = self._get_ssh_credential(credential_name)
        if not ssh_cred:
            return DeviceAuditResult(
                hostname=hostname,
                ip_address=ip_address,
                vendor=vendor,
                success=False,
                errors=["No SSH credentials available in vault"],
                duration_ms=(time.time() - start_time) * 1000,
            )

        # Build SSH config
        config = SSHClientConfig(
            host=ip_address,
            username=ssh_cred.username,
            password=ssh_cred.password,
            key_content=getattr(ssh_cred, 'private_key', None),
            timeout=self.timeout,
            legacy_mode=self.legacy_mode,
        )

        config_collected = False
        inventory_collected = False
        config_size = 0
        inventory_size = 0

        try:
            with SSHClient(config) as client:
                # Detect prompt
                prompt = client.find_prompt()
                client.set_expect_prompt(prompt)

                if debug:
                    print(f"[AUDIT] Connected, prompt: {prompt!r}")

                # Disable pagination
                client.disable_pagination()

                # Collect configuration
                config_output = self._collect_config(client, commands, debug)
                if config_output:
                    config_path = output_folder / "config.txt"
                    with open(config_path, 'w') as f:
                        f.write(config_output)
                    config_collected = True
                    config_size = len(config_output)
                    if debug:
                        print(f"[AUDIT] Config written: {config_size} bytes")

                # Collect inventory
                inventory_output = self._collect_inventory(client, commands, debug)
                if inventory_output:
                    inventory_path = output_folder / "inventory.txt"
                    with open(inventory_path, 'w') as f:
                        f.write(inventory_output)
                    inventory_collected = True
                    inventory_size = len(inventory_output)
                    if debug:
                        print(f"[AUDIT] Inventory written: {inventory_size} bytes")

        except Exception as e:
            if debug:
                print(f"[AUDIT] SSH Exception: {e}")
            errors.append(f"SSH connection failed: {e}")

        duration_ms = (time.time() - start_time) * 1000

        return DeviceAuditResult(
            hostname=hostname,
            ip_address=ip_address,
            vendor=vendor,
            success=config_collected or inventory_collected,
            config_collected=config_collected,
            inventory_collected=inventory_collected,
            config_size=config_size,
            inventory_size=inventory_size,
            errors=errors,
            duration_ms=duration_ms,
        )

    def _get_ssh_credential(self, credential_name: Optional[str] = None):
        """Get SSH credential from vault."""
        if credential_name:
            return self.vault.get_ssh_credential(name=credential_name)

        # Get default or first available SSH credential
        creds = self.vault.list_credentials()

        # First pass: look for default SSH credential
        for cred in creds:
            cred_type = cred.credential_type
            # Handle both enum and string types
            type_value = cred_type.value if hasattr(cred_type, 'value') else str(cred_type)
            if type_value.lower() == "ssh" and cred.is_default:
                return self.vault.get_ssh_credential(name=cred.name)

        # Second pass: get first SSH credential
        for cred in creds:
            cred_type = cred.credential_type
            type_value = cred_type.value if hasattr(cred_type, 'value') else str(cred_type)
            if type_value.lower() == "ssh":
                return self.vault.get_ssh_credential(name=cred.name)

        return None

    def _collect_config(
        self,
        client: SSHClient,
        commands: AuditCommands,
        debug: bool = False,
    ) -> Optional[str]:
        """Collect running configuration."""
        try:
            cmd = commands.config_command
            if commands.pager_suffix:
                cmd += commands.pager_suffix

            if debug:
                print(f"[AUDIT] Sending: {cmd}")

            output = client.execute_command(cmd)

            if debug:
                print(f"[AUDIT] Config returned {len(output)} bytes")

            return output if output and len(output) > 100 else None

        except Exception as e:
            if debug:
                print(f"[AUDIT] Config collection failed: {e}")
            return None

    def _collect_inventory(
        self,
        client: SSHClient,
        commands: AuditCommands,
        debug: bool = False,
    ) -> Optional[str]:
        """Collect hardware inventory."""
        try:
            cmd = commands.inventory_command
            if commands.pager_suffix:
                cmd += commands.pager_suffix

            if debug:
                print(f"[AUDIT] Sending: {cmd}")

            output = client.execute_command(cmd)

            if debug:
                print(f"[AUDIT] Inventory returned {len(output)} bytes")

            return output if output and len(output) > 50 else None

        except Exception as e:
            if debug:
                print(f"[AUDIT] Inventory collection failed: {e}")
            return None


# =============================================================================
# Convenience function
# =============================================================================

def audit_discovery(
    discovery_path: str,
    vault,  # CredentialVault instance
    devices: Optional[List[str]] = None,
    vendor_filter: Optional[str] = None,
    debug: bool = False,
) -> AuditResult:
    """
    Convenience function for audit collection.

    Args:
        discovery_path: Path to discovery output folder.
        vault: Unlocked CredentialVault.
        devices: Optional list of device hostnames.
        vendor_filter: Optional vendor filter.
        debug: Enable debug output.

    Returns:
        AuditResult with per-device results.
    """
    collector = AuditCollector(vault)
    return collector.collect(
        discovery_path=discovery_path,
        devices=devices,
        vendor_filter=vendor_filter,
        debug=debug,
    )