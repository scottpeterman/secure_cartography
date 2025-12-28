"""
SecureCartography NG - Concurrent Discovery Engine.

High-level discovery orchestration with vault integration.
Combines SNMP collectors with credential management from scng.creds.

Features:
- Single device discovery
- Recursive crawl with depth limits
- SNMP-first with SSH fallback
- CONCURRENT discovery within each depth level (configurable parallelism)
- Credential preference caching by subnet
- Atomic deduplication to prevent duplicate discovery
- Structured event emission for GUI integration
- Cancellation support
- Async file I/O for non-blocking output
"""

import asyncio
import re
import socket
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Callable, Any, Set, Union, Tuple
import json

# Async file I/O - optional, falls back to executor if not available
try:
    import aiofiles
    HAS_AIOFILES = True
except ImportError:
    HAS_AIOFILES = False

# Try new pysnmp first, fall back to older v3arch path
try:
    from pysnmp.hlapi.asyncio import (
        SnmpEngine, CommunityData, UsmUserData,
        usmHMACMD5AuthProtocol, usmHMACSHAAuthProtocol,
        usmHMAC128SHA224AuthProtocol, usmHMAC192SHA256AuthProtocol,
        usmHMAC256SHA384AuthProtocol, usmHMAC384SHA512AuthProtocol,
        usmDESPrivProtocol, usmAesCfb128Protocol,
        usmAesCfb192Protocol, usmAesCfb256Protocol,
        usmNoAuthProtocol, usmNoPrivProtocol,
    )
except ImportError:
    from pysnmp.hlapi.v3arch.asyncio import (
        SnmpEngine, CommunityData, UsmUserData,
        usmHMACMD5AuthProtocol, usmHMACSHAAuthProtocol,
        usmHMAC128SHA224AuthProtocol, usmHMAC192SHA256AuthProtocol,
        usmHMAC256SHA384AuthProtocol, usmHMAC384SHA512AuthProtocol,
        usmDESPrivProtocol, usmAesCfb128Protocol,
        usmAesCfb192Protocol, usmAesCfb256Protocol,
        usmNoAuthProtocol, usmNoPrivProtocol,
    )

from .models import (
    Device, Interface, Neighbor, DiscoveryResult,
    DeviceVendor, DiscoveryProtocol, NeighborProtocol,
)
from .snmp import (
    get_system_info,
    get_interface_table,
    get_cdp_neighbors,
    get_lldp_neighbors,
    get_arp_table,
    lookup_ip_by_mac,
    get_sys_name,
    should_exclude,
    detect_vendor,
    extract_hostname,
    build_fqdn,
    is_ip_address,
)

# Import SSH collector
from .ssh import SSHCollector

# Import event system
from .events import (
    EventEmitter, EventCallback, EventType, LogLevel,
    ConsoleEventPrinter, DiscoveryEvent,
)

# Import from scng.creds for vault integration
# Try multiple import paths to handle different package structures
HAS_VAULT = False
try:
    from scng.creds import (
        CredentialVault,
        CredentialType,
        SSHCredential,
        SNMPv2cCredential,
        SNMPv3Credential,
        SNMPv3AuthProtocol,
        SNMPv3PrivProtocol,
    )
    HAS_VAULT = True
except ImportError:
    pass

if not HAS_VAULT:
    try:
        from sc2.scng.creds import (
            CredentialVault,
            CredentialType,
            SSHCredential,
            SNMPv2cCredential,
            SNMPv3Credential,
            SNMPv3AuthProtocol,
            SNMPv3PrivProtocol,
        )
        HAS_VAULT = True
    except ImportError:
        pass

if not HAS_VAULT:
    # Try relative import as last resort
    try:
        from ..creds import (
            CredentialVault,
            CredentialType,
            SSHCredential,
            SNMPv2cCredential,
            SNMPv3Credential,
            SNMPv3AuthProtocol,
            SNMPv3PrivProtocol,
        )
        HAS_VAULT = True
    except ImportError:
        pass


# Legacy type alias for backward compatibility
ProgressCallback = Callable[[str, int, int], None]  # (message, current, total)

# MAC address patterns to filter out
MAC_PATTERN = re.compile(r'^([0-9a-fA-F]{2}[:\-.]?){5}[0-9a-fA-F]{2}$|^([0-9a-fA-F]{4}\.){2}[0-9a-fA-F]{4}$')


def is_mac_address(value: str) -> bool:
    """Check if string looks like a MAC address."""
    if not value:
        return False
    # Cisco format: 00cc.344b.b47e
    # Standard formats: 00:cc:34:4b:b4:7e or 00-cc-34-4b-b4-7e
    return bool(MAC_PATTERN.match(value))


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
        # Extract model and version
        model = "Arista"
        version = ""
        if 'vEOS-lab' in sys_descr:
            model = "Arista vEOS-lab"
        elif 'vEOS' in sys_descr:
            model = "Arista vEOS"
        # Extract EOS version
        eos_match = re.search(r'EOS version (\S+)', sys_descr)
        if eos_match:
            version = f"EOS {eos_match.group(1)}"
        return f"{model} {version}".strip()

    # Cisco IOS pattern
    if 'Cisco IOS' in sys_descr or 'Cisco' in sys_descr:
        # Try to extract model info
        model = "Cisco"

        # Check for specific platforms
        if 'IOSv' in sys_descr or 'VIOS' in sys_descr:
            model = "Cisco IOSv"
        elif 'vios_l2' in sys_descr:
            model = "Cisco IOS"  # L2 switch
        elif '7200' in sys_descr:
            model = "Cisco 7200"
        elif '7206VXR' in sys_descr:
            model = "Cisco 7206VXR"

        # Extract IOS version
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


class DiscoveryEngine:
    """
    Concurrent network discovery engine with vault integration.

    Combines SNMP-based discovery with credential management
    from scng.creds vault. Falls back to SSH when SNMP fails.

    Features:
    - Parallel discovery within each depth level (breadth-first)
    - Credential preference caching by /24 subnet
    - Atomic deduplication prevents double-discovery
    - Configurable concurrency limits
    - Structured event emission for GUI integration

    Usage:
        from scng.creds import CredentialVault
        from scng.discovery import DiscoveryEngine

        vault = CredentialVault()
        vault.unlock("password")

        engine = DiscoveryEngine(vault, max_concurrent=20)

        # Subscribe to events (for GUI)
        engine.events.subscribe(my_gui_handler)

        # Or use console printer for CLI
        printer = ConsoleEventPrinter(verbose=True)
        engine.events.subscribe(printer.handle_event)

        # Single device
        device = await engine.discover_device("192.168.1.1")

        # Recursive crawl (concurrent within each depth)
        result = await engine.crawl(
            seeds=["192.168.1.1"],
            max_depth=3,
            domains=["example.com"],
        )
    """

    def __init__(
        self,
        vault: Optional['CredentialVault'] = None,
        snmp_engine: Optional[SnmpEngine] = None,
        default_timeout: float = 5.0,
        verbose: bool = False,
        no_dns: bool = False,
        max_concurrent: int = 20,
        event_emitter: Optional[EventEmitter] = None,
    ):
        """
        Initialize discovery engine.

        Args:
            vault: Unlocked CredentialVault for credential retrieval
            snmp_engine: Shared pysnmp engine (created if not provided)
            default_timeout: Default SNMP timeout in seconds
            verbose: Enable debug output
            no_dns: Disable DNS lookups (targets must be IPs)
            max_concurrent: Maximum concurrent device discoveries (default 20)
            event_emitter: Event emitter for GUI integration (created if not provided)
        """
        self.vault = vault
        self.snmp_engine = snmp_engine or SnmpEngine()
        self.default_timeout = default_timeout
        self.verbose = verbose
        self.no_dns = no_dns
        self.max_concurrent = max_concurrent

        # Event system
        self.events = event_emitter or EventEmitter()

        # Concurrency primitives
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._executor = ThreadPoolExecutor(max_workers=max_concurrent)

        # Deduplication: normalized identifiers we've claimed or processed
        # In asyncio single-thread model, no lock needed between awaits
        self._claimed: Set[str] = set()

        # Credential preference cache: /24 subnet -> (cred_name, protocol)
        # When a credential works for an IP, remember it for the subnet
        self._subnet_preferences: Dict[str, Tuple[str, str]] = {}

        # Legacy cache for backward compatibility (IP -> full credential result)
        self._credential_cache: Dict[str, tuple] = {}

    def _vprint(self, msg: str, level: int = 1):
        """Print verbose message if enabled."""
        if self.verbose:
            indent = "  " * level
            print(f"{indent}[discovery] {msg}")

    def _log(self, message: str, level: LogLevel = LogLevel.INFO, device: str = ""):
        """Emit log message event."""
        self.events.log(message, level, device)
        if self.verbose or level in (LogLevel.WARNING, LogLevel.ERROR):
            self._vprint(message, 1)

    # =========================================================================
    # Exclusion
    # =========================================================================

    def _should_exclude_device(self, device: Device, exclude_patterns: List[str]) -> Tuple[bool, str]:
        """
        Check if device should be excluded from crawl propagation.

        Matches against multiple device identifiers:
        - sys_descr (SNMP)
        - hostname
        - sys_name

        Supports comma-separated patterns: "linux,rtr,use-"

        Args:
            device: Discovered device to check
            exclude_patterns: List of patterns (may contain comma-separated values)

        Returns:
            (should_exclude, matching_pattern)
        """
        if not exclude_patterns:
            return False, ""

        # Expand comma-separated patterns
        expanded_patterns = []
        for p in exclude_patterns:
            expanded_patterns.extend(part.strip() for part in p.split(',') if part.strip())

        # Fields to check (lowercased)
        check_fields = [
            (device.sys_descr or "").lower(),
            (device.hostname or "").lower(),
            (device.sys_name or "").lower(),
        ]

        for pattern in expanded_patterns:
            pattern_lower = pattern.lower()
            for field in check_fields:
                if field and pattern_lower in field:
                    return True, pattern

        return False, ""

    # =========================================================================
    # Deduplication
    # =========================================================================

    def _normalize_identifier(self, identifier: str) -> str:
        """
        Normalize an identifier for deduplication.

        - Lowercase
        - Strip trailing dots (FQDN normalization)
        - For hostnames, also store the short name
        """
        if not identifier:
            return ""
        return identifier.lower().rstrip('.')

    def _try_claim(self, target: str) -> bool:
        """
        Atomically claim a target for discovery.

        Returns True if we got it, False if already claimed.
        Thread-safe in asyncio single-thread model (no lock needed).
        """
        normalized = self._normalize_identifier(target)
        if not normalized:
            return False
        if normalized in self._claimed:
            return False
        self._claimed.add(normalized)
        return True

    def _register_device(self, device: Device) -> None:
        """
        Register all known identifiers for a discovered device.

        Called after discovery completes to prevent rediscovery
        via alternate identifiers (IP vs hostname vs sysName).
        """
        identifiers = [
            device.ip_address,
            device.hostname,
            device.sys_name,
            device.fqdn,
        ]
        for ident in identifiers:
            if ident:
                self._claimed.add(self._normalize_identifier(ident))

    def _is_claimed(self, target: str) -> bool:
        """Check if a target has been claimed."""
        return self._normalize_identifier(target) in self._claimed

    def reset_state(self) -> None:
        """Reset discovery state for a new crawl."""
        self._claimed.clear()
        self._subnet_preferences.clear()
        self._credential_cache.clear()
        self.events.reset_stats()

    # =========================================================================
    # Credential Management
    # =========================================================================

    def _get_subnet(self, ip: str) -> str:
        """Extract /24 subnet from IP address."""
        if not ip or not is_ip_address(ip):
            return ""
        parts = ip.split('.')
        if len(parts) == 4:
            return '.'.join(parts[:3])
        return ip

    def _build_auth(self, credential) -> Optional[Any]:
        """
        Build pysnmp auth data from vault credential.

        Returns CommunityData for SNMPv2c or UsmUserData for SNMPv3.
        """
        if not HAS_VAULT:
            return None

        if isinstance(credential, SNMPv2cCredential):
            return CommunityData(credential.community, mpModel=1)

        elif isinstance(credential, SNMPv3Credential):
            # Map auth protocols
            auth_map = {
                SNMPv3AuthProtocol.NONE: usmNoAuthProtocol,
                SNMPv3AuthProtocol.MD5: usmHMACMD5AuthProtocol,
                SNMPv3AuthProtocol.SHA: usmHMACSHAAuthProtocol,
                SNMPv3AuthProtocol.SHA224: usmHMAC128SHA224AuthProtocol,
                SNMPv3AuthProtocol.SHA256: usmHMAC192SHA256AuthProtocol,
                SNMPv3AuthProtocol.SHA384: usmHMAC256SHA384AuthProtocol,
                SNMPv3AuthProtocol.SHA512: usmHMAC384SHA512AuthProtocol,
            }

            # Map priv protocols
            priv_map = {
                SNMPv3PrivProtocol.NONE: usmNoPrivProtocol,
                SNMPv3PrivProtocol.DES: usmDESPrivProtocol,
                SNMPv3PrivProtocol.AES: usmAesCfb128Protocol,
                SNMPv3PrivProtocol.AES192: usmAesCfb192Protocol,
                SNMPv3PrivProtocol.AES256: usmAesCfb256Protocol,
            }

            usm_kwargs = {}

            if credential.auth_protocol != SNMPv3AuthProtocol.NONE:
                usm_kwargs['authKey'] = credential.auth_password
                usm_kwargs['authProtocol'] = auth_map.get(
                    credential.auth_protocol, usmNoAuthProtocol
                )

            if credential.priv_protocol != SNMPv3PrivProtocol.NONE:
                usm_kwargs['privKey'] = credential.priv_password
                usm_kwargs['privProtocol'] = priv_map.get(
                    credential.priv_protocol, usmNoPrivProtocol
                )

            return UsmUserData(credential.username, **usm_kwargs)

        return None

    def _test_ssh_credential_sync(self, target: str, cred) -> bool:
        """
        Synchronous SSH credential test for use in executor.

        Args:
            target: IP address or hostname
            cred: SSHCredential from vault

        Returns:
            True if connection successful
        """
        from .ssh.client import SSHClient, SSHClientConfig

        config = SSHClientConfig(
            host=target,
            username=cred.username,
            password=cred.password,
            key_content=cred.key_content,
            key_passphrase=cred.key_passphrase,
            timeout=min(cred.timeout_seconds, 10),  # Cap at 10s for testing
        )

        try:
            with SSHClient(config) as client:
                client.find_prompt()
                return True
        except Exception as e:
            return False

    async def _test_ssh_credential(self, target: str, cred) -> bool:
        """
        Test if SSH credential works for target (async wrapper).

        Runs the blocking SSH test in a thread pool executor.
        """
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(
                self._executor,
                self._test_ssh_credential_sync,
                target,
                cred
            )
        except Exception as e:
            self._vprint(f"SSH test failed: {e}", 3)
            return False

    async def _test_snmp_credential(
        self,
        target: str,
        cred_name: str,
        auth: Any,
    ) -> bool:
        """Test if SNMP credential works for target."""
        try:
            sys_name = await asyncio.wait_for(
                get_sys_name(target, auth, self.snmp_engine, timeout=3.0),
                timeout=5.0
            )
            return bool(sys_name)
        except asyncio.TimeoutError:
            self._vprint(f"SNMP credential '{cred_name}' timed out for {target}", 3)
            return False
        except Exception as e:
            self._vprint(f"SNMP credential '{cred_name}' failed for {target}: {e}", 3)
            return False

    async def _get_working_credential(
        self,
        target: str,
        credential_names: Optional[List[str]] = None,
    ) -> Optional[tuple]:
        """
        Find a working credential for target.

        Tries credentials in order:
        1. Check if we have a preference for this subnet (from previous success)
        2. Try SNMP credentials
        3. Fall back to SSH credentials

        Returns:
            Tuple of (credential, credential_name, protocol) or None.
            - For SNMP: credential is CommunityData or UsmUserData
            - For SSH: credential is SSHCredential
            - protocol is 'snmp' or 'ssh'
        """
        # Check legacy cache first (exact IP match)
        if target in self._credential_cache:
            return self._credential_cache[target]

        if not self.vault:
            return None

        # Check subnet preference
        subnet = self._get_subnet(target)
        if subnet in self._subnet_preferences:
            pref_name, pref_proto = self._subnet_preferences[subnet]
            self._vprint(f"Using subnet preference: {pref_name} ({pref_proto})", 3)

            # Get the preferred credential
            info = self.vault.get_credential_info(name=pref_name)
            if info:
                if pref_proto == 'snmp':
                    if info.credential_type == CredentialType.SNMP_V2C:
                        cred = self.vault.get_snmpv2c_credential(name=pref_name)
                        if cred:
                            auth = self._build_auth(cred)
                            if auth:
                                result = (auth, pref_name, 'snmp')
                                self._credential_cache[target] = result
                                return result
                    elif info.credential_type == CredentialType.SNMP_V3:
                        cred = self.vault.get_snmpv3_credential(name=pref_name)
                        if cred:
                            auth = self._build_auth(cred)
                            if auth:
                                result = (auth, pref_name, 'snmp')
                                self._credential_cache[target] = result
                                return result
                elif pref_proto == 'ssh':
                    cred = self.vault.get_ssh_credential(name=pref_name)
                    if cred:
                        result = (cred, pref_name, 'ssh')
                        self._credential_cache[target] = result
                        return result

        # Get credential list
        if credential_names:
            cred_list = credential_names
        else:
            cred_list = [c.name for c in self.vault.list_credentials()]

        # Try SNMP credentials first
        for cred_name in cred_list:
            info = self.vault.get_credential_info(name=cred_name)
            if not info:
                continue

            if info.credential_type == CredentialType.SNMP_V2C:
                cred = self.vault.get_snmpv2c_credential(name=cred_name)
                if cred:
                    auth = self._build_auth(cred)
                    if auth and await self._test_snmp_credential(target, cred_name, auth):
                        self._vprint(f"SNMP credential '{cred_name}' works for {target}", 2)
                        # Save preference
                        if subnet:
                            self._subnet_preferences[subnet] = (cred_name, 'snmp')
                        result = (auth, cred_name, 'snmp')
                        self._credential_cache[target] = result
                        return result

            elif info.credential_type == CredentialType.SNMP_V3:
                cred = self.vault.get_snmpv3_credential(name=cred_name)
                if cred:
                    auth = self._build_auth(cred)
                    if auth and await self._test_snmp_credential(target, cred_name, auth):
                        self._vprint(f"SNMPv3 credential '{cred_name}' works for {target}", 2)
                        if subnet:
                            self._subnet_preferences[subnet] = (cred_name, 'snmp')
                        result = (auth, cred_name, 'snmp')
                        self._credential_cache[target] = result
                        return result

        # Fall back to SSH
        for cred_name in cred_list:
            info = self.vault.get_credential_info(name=cred_name)
            if not info or info.credential_type != CredentialType.SSH:
                continue

            cred = self.vault.get_ssh_credential(name=cred_name)
            if cred and await self._test_ssh_credential(target, cred):
                self._vprint(f"SSH credential '{cred_name}' works for {target}", 2)
                if subnet:
                    self._subnet_preferences[subnet] = (cred_name, 'ssh')
                result = (cred, cred_name, 'ssh')
                self._credential_cache[target] = result
                return result

        return None

    # =========================================================================
    # SSH Fallback Discovery
    # =========================================================================

    async def _discover_via_ssh(
        self,
        device_ip: str,
        ssh_cred,
        credential_name: str,
        hostname: str,
        depth: int,
        domains: List[str],
    ) -> Device:
        """
        Discover device via SSH when SNMP fails.

        Uses SSHCollector to execute commands and parse output.
        Limited to neighbor discovery (CDP/LLDP) without full SNMP data.
        """
        start_time = datetime.now()

        self._vprint(f"SSH fallback for {hostname} ({device_ip})", 1)

        device = Device(
            hostname=hostname,
            ip_address=device_ip,
            credential_used=credential_name,
            depth=depth,
            discovered_via=DiscoveryProtocol.SSH,
        )

        loop = asyncio.get_event_loop()

        try:
            # Create SSH collector (host is passed to collect(), not constructor)
            collector = SSHCollector(
                username=ssh_cred.username,
                password=ssh_cred.password,
                key_content=getattr(ssh_cred, 'key_content', None),
                key_passphrase=getattr(ssh_cred, 'key_passphrase', None),
                timeout=getattr(ssh_cred, 'timeout_seconds', 30),
            )

            # Collect in thread pool - pass host and debug flag
            ssh_result = await loop.run_in_executor(
                self._executor,
                lambda: collector.collect(device_ip, debug=self.verbose)
            )

            # ssh_result is SSHCollectorResult dataclass
            if ssh_result and ssh_result.success:
                # Update device with SSH results
                if ssh_result.vendor:
                    device.vendor = ssh_result.vendor
                if ssh_result.hostname:
                    # Normalize hostname by stripping domain suffix
                    normalized = extract_hostname(ssh_result.hostname, domains)
                    device.hostname = normalized or ssh_result.hostname
                    device.sys_name = ssh_result.hostname  # Keep original as sys_name
                    if normalized != ssh_result.hostname:
                        device.fqdn = ssh_result.hostname

                # Get version info from raw output if available
                if ssh_result.raw_output.get('show_version'):
                    device.sys_descr = ssh_result.raw_output['show_version'][:200]

                # Process neighbors - normalize their hostnames too
                for neighbor in ssh_result.neighbors:
                    # Normalize neighbor hostname (stored in remote_device)
                    if neighbor.remote_device and domains:
                        normalized_neighbor = extract_hostname(neighbor.remote_device, domains)
                        if normalized_neighbor:
                            neighbor.remote_device = normalized_neighbor
                    device.add_neighbor(neighbor)

                device.discovery_success = True
                device.discovery_duration_ms = ssh_result.duration_ms

                self._vprint(f"SSH collected {len(ssh_result.neighbors)} neighbors", 2)
            else:
                # Collection failed or returned no data
                if ssh_result and ssh_result.errors:
                    for err in ssh_result.errors:
                        device.discovery_errors.append(err)
                else:
                    device.discovery_errors.append("SSH collection returned no data")

        except Exception as e:
            device.discovery_errors.append(f"SSH discovery failed: {e}")
            self._vprint(f"SSH exception: {e}", 1)

        if device.discovery_duration_ms == 0:
            device.discovery_duration_ms = (datetime.now() - start_time).total_seconds() * 1000

        return device

    # =========================================================================
    # Hostname Resolution
    # =========================================================================

    def _resolve_hostname(self, hostname: str, domains: List[str]) -> Optional[str]:
        """
        Resolve hostname to IP address, trying domain suffixes.

        Returns IP address or None if resolution fails.
        """
        if self.no_dns:
            return None

        if is_ip_address(hostname):
            return hostname

        # Check if hostname already has a domain suffix
        has_domain = any(hostname.endswith('.' + d) for d in domains)

        if has_domain:
            # Already FQDN, try direct lookup
            try:
                ip = socket.gethostbyname(hostname)
                self._vprint(f"Resolved {hostname} -> {ip}", 3)
                return ip
            except socket.gaierror:
                return None

        # No domain suffix - append each one and try
        for domain in domains:
            fqdn = f"{hostname}.{domain}"
            try:
                ip = socket.gethostbyname(fqdn)
                self._vprint(f"Resolved {hostname} -> {fqdn} -> {ip}", 3)
                return ip
            except socket.gaierror:
                continue

        return None

    # =========================================================================
    # Device Discovery
    # =========================================================================

    async def discover_device(
        self,
        target: str,
        auth: Optional[Any] = None,
        credential_name: Optional[str] = None,
        domains: Optional[List[str]] = None,
        depth: int = 0,
        collect_arp: bool = True,
    ) -> Device:
        """
        Discover a single device.

        Tries SNMP first for full discovery, falls back to SSH
        for neighbor-only discovery if SNMP fails.

        Args:
            target: IP address or hostname
            auth: Pre-built auth data (CommunityData or UsmUserData)
            credential_name: Specific credential to use from vault
            domains: Domain suffixes for hostname resolution
            depth: Discovery depth (for tracking)
            collect_arp: Whether to collect ARP table (SNMP only)

        Returns:
            Device dataclass with collected information
        """
        start_time = datetime.now()
        domains = domains or []

        # Resolve hostname to IP
        if is_ip_address(target):
            device_ip = target
            hostname = target
        else:
            hostname = target
            if self.no_dns:
                # DNS disabled - fail fast for non-IP targets
                return Device(
                    hostname=target,
                    ip_address="",
                    discovery_success=False,
                    discovery_errors=[f"DNS disabled, cannot resolve hostname: {target}"],
                    depth=depth,
                )
            try:
                fqdn = build_fqdn(target, domains)
                device_ip = socket.gethostbyname(fqdn)
            except socket.gaierror:
                # Create failed device
                return Device(
                    hostname=target,
                    ip_address="",
                    discovery_success=False,
                    discovery_errors=[f"DNS resolution failed for {target}"],
                    depth=depth,
                )

        self._vprint(f"Discovering {hostname} ({device_ip})", 1)

        # Get auth if not provided
        protocol = 'snmp'  # Default assumption
        ssh_cred = None

        if not auth:
            if credential_name and self.vault:
                # Try specific credential by name
                info = self.vault.get_credential_info(name=credential_name)
                if info:
                    if info.credential_type == CredentialType.SNMP_V2C:
                        cred = self.vault.get_snmpv2c_credential(name=credential_name)
                        if cred:
                            auth = self._build_auth(cred)
                    elif info.credential_type == CredentialType.SNMP_V3:
                        cred = self.vault.get_snmpv3_credential(name=credential_name)
                        if cred:
                            auth = self._build_auth(cred)
                    elif info.credential_type == CredentialType.SSH:
                        ssh_cred = self.vault.get_ssh_credential(name=credential_name)
                        protocol = 'ssh'
            else:
                # Auto-discover working credential
                result = await self._get_working_credential(device_ip)
                if result:
                    cred, credential_name, protocol = result
                    if protocol == 'ssh':
                        ssh_cred = cred
                    else:
                        auth = cred  # It's already the auth object for SNMP

        # Use SSH fallback if that's what worked
        if protocol == 'ssh' and ssh_cred:
            return await self._discover_via_ssh(
                device_ip, ssh_cred, credential_name, hostname, depth, domains
            )

        # No working credential found
        if not auth:
            return Device(
                hostname=hostname,
                ip_address=device_ip,
                discovery_success=False,
                discovery_errors=["No working SNMP or SSH credential found"],
                depth=depth,
            )

        # Continue with SNMP discovery
        # Collect system info
        self._vprint("Collecting system info...", 2)
        sys_info = await get_system_info(
            device_ip, auth, self.snmp_engine,
            timeout=self.default_timeout, verbose=self.verbose
        )

        # Create device
        device = Device(
            hostname=hostname,
            ip_address=device_ip,
            sys_name=sys_info.get('sys_name'),
            sys_descr=sys_info.get('sys_descr'),
            sys_location=sys_info.get('sys_location'),
            sys_contact=sys_info.get('sys_contact'),
            sys_object_id=sys_info.get('sys_object_id'),
            uptime_ticks=sys_info.get('uptime_ticks'),
            vendor=sys_info.get('vendor', DeviceVendor.UNKNOWN),
            credential_used=credential_name,
            depth=depth,
            discovered_via=DiscoveryProtocol.SNMP,
        )

        # Update hostname if we got sysName and it differs
        if device.sys_name and is_ip_address(hostname):
            resolved_hostname = extract_hostname(device.sys_name, domains)
            if resolved_hostname:
                device.hostname = resolved_hostname
                device.fqdn = device.sys_name

        # Collect interfaces
        self._vprint("Collecting interface table...", 2)
        try:
            interface_dict = await get_interface_table(
                device_ip, auth, self.snmp_engine,
                timeout=self.default_timeout, verbose=self.verbose
            )
            device.interfaces = list(interface_dict.values())
        except Exception as e:
            device.discovery_errors.append(f"Interface collection failed: {e}")
            interface_dict = {}

        # Collect ARP table (for LLDP fallback)
        arp_table = {}
        if collect_arp:
            self._vprint("Collecting ARP table...", 2)
            try:
                arp_table = await get_arp_table(
                    device_ip, auth, self.snmp_engine,
                    timeout=self.default_timeout, verbose=self.verbose
                )
                device.arp_table = arp_table
            except Exception as e:
                device.discovery_errors.append(f"ARP collection failed: {e}")

        # Collect CDP neighbors (Cisco only)
        if device.vendor == DeviceVendor.CISCO:
            self._vprint("Collecting CDP neighbors...", 2)
            try:
                cdp_neighbors = await get_cdp_neighbors(
                    device_ip, auth, interface_dict, self.snmp_engine,
                    timeout=self.default_timeout, verbose=self.verbose
                )
                for n in cdp_neighbors:
                    # Normalize neighbor hostname (stored in remote_device)
                    if n.remote_device and domains:
                        normalized = extract_hostname(n.remote_device, domains)
                        if normalized:
                            n.remote_device = normalized
                    device.add_neighbor(n)
            except Exception as e:
                device.discovery_errors.append(f"CDP collection failed: {e}")

        # Collect LLDP neighbors (all vendors)
        self._vprint("Collecting LLDP neighbors...", 2)
        try:
            lldp_neighbors = await get_lldp_neighbors(
                device_ip, auth, interface_dict, self.snmp_engine,
                timeout=self.default_timeout * 2,  # LLDP can be slow
                verbose=self.verbose
            )

            # Try to resolve missing management addresses via ARP
            for n in lldp_neighbors:
                if not n.remote_ip and n.chassis_id and arp_table:
                    resolved_ip = lookup_ip_by_mac(n.chassis_id, arp_table)
                    if resolved_ip:
                        n.remote_ip = resolved_ip
                        self._vprint(f"Resolved {n.chassis_id} to {resolved_ip} via ARP", 3)

                # Normalize neighbor hostname (stored in remote_device)
                if n.remote_device and domains:
                    normalized = extract_hostname(n.remote_device, domains)
                    if normalized:
                        n.remote_device = normalized

                device.add_neighbor(n)

        except Exception as e:
            device.discovery_errors.append(f"LLDP collection failed: {e}")

        # Calculate duration
        device.discovery_duration_ms = (datetime.now() - start_time).total_seconds() * 1000

        self._vprint(
            f"Discovery complete: {len(device.interfaces)} interfaces, "
            f"{len(device.neighbors)} neighbors in {device.discovery_duration_ms:.0f}ms",
            1
        )

        return device

    # =========================================================================
    # Async File I/O
    # =========================================================================

    async def _write_json_file(self, filepath: Path, data: dict) -> None:
        """Write JSON data to file asynchronously."""
        content = json.dumps(data, indent=2)

        if HAS_AIOFILES:
            async with aiofiles.open(filepath, 'w') as f:
                await f.write(content)
        else:
            # Fallback to executor
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self._executor,
                self._write_json_file_sync,
                filepath,
                content,
            )

    def _write_json_file_sync(self, filepath: Path, content: str) -> None:
        """Synchronous file write for executor fallback."""
        with open(filepath, 'w') as f:
            f.write(content)

    async def _save_device_files(
        self,
        device: Device,
        output_dir: Path,
    ) -> None:
        """Save device data to individual files asynchronously."""
        device_dir = output_dir / device.hostname
        device_dir.mkdir(parents=True, exist_ok=True)

        # Save device JSON
        device_file = device_dir / 'device.json'
        await self._write_json_file(device_file, device.to_dict())

        # Save neighbors
        if device.cdp_neighbors:
            cdp_file = device_dir / 'cdp.json'
            await self._write_json_file(
                cdp_file,
                [n.to_dict() for n in device.cdp_neighbors]
            )

        if device.lldp_neighbors:
            lldp_file = device_dir / 'lldp.json'
            await self._write_json_file(
                lldp_file,
                [n.to_dict() for n in device.lldp_neighbors]
            )

    # =========================================================================
    # Crawl
    # =========================================================================

    async def _discover_with_semaphore(
        self,
        target: str,
        depth: int,
        domains: List[str],
    ) -> Device:
        """
        Rate-limited device discovery.

        Acquires semaphore before discovery to limit concurrency.
        """
        # Emit device started event
        self.events.device_started(target, depth)

        async with self._semaphore:
            return await self.discover_device(
                target=target,
                domains=domains,
                depth=depth,
            )

    async def crawl(
        self,
        seeds: List[str],
        max_depth: int = 3,
        domains: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
        credential_names: Optional[List[str]] = None,
        output_dir: Optional[Path] = None,
        progress_callback: Optional[ProgressCallback] = None,
        cancel_event: Optional[asyncio.Event] = None,
    ) -> DiscoveryResult:
        """
        Recursively discover network from seed devices.

        Discovery is CONCURRENT within each depth level (up to max_concurrent
        devices at once), but proceeds breadth-first across depths.

        Args:
            seeds: Starting IP addresses or hostnames
            max_depth: Maximum recursion depth
            domains: Domain suffixes for hostname resolution
            exclude_patterns: sysDescr patterns to skip
            credential_names: Specific credentials to try
            output_dir: Directory to save per-device JSON
            progress_callback: Legacy callback (message, current, total)
            cancel_event: Set to cancel discovery

        Returns:
            DiscoveryResult with all discovered devices
        """
        domains = domains or []
        exclude_patterns = exclude_patterns or []

        # Reset state for new crawl
        self.reset_state()

        result = DiscoveryResult(
            seed_devices=seeds,
            max_depth=max_depth,
            domains=domains,
            exclude_patterns=exclude_patterns,
            started_at=datetime.now(),
        )

        # Emit crawl started event
        self.events.crawl_started(
            seeds, max_depth, domains, exclude_patterns,
            no_dns=self.no_dns,
            concurrency=self.max_concurrent,
            timeout=self.default_timeout,
        )

        # Claim and queue seeds
        current_batch: List[Tuple[str, int]] = []
        for seed in seeds:
            if self._try_claim(seed):
                current_batch.append((seed, 0))
                self.events.device_queued(seed, 0)

        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)

        while current_batch:
            # Check cancellation
            if cancel_event and cancel_event.is_set():
                self.events.crawl_cancelled()
                result.completed_at = datetime.now()
                return result

            depth = current_batch[0][1]
            batch_size = len(current_batch)

            # Emit depth started event
            self.events.depth_started(depth, batch_size)

            # Legacy progress callback
            if progress_callback:
                progress_callback(
                    f"Depth {depth}: discovering {batch_size} devices",
                    result.total_attempted,
                    result.total_attempted + batch_size
                )

            # Discover all devices at this depth concurrently
            tasks = [
                self._discover_with_semaphore(target, d, domains)
                for target, d in current_batch
            ]

            # Gather with exception handling - don't let one failure stop others
            devices = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results and collect next batch
            next_batch: List[Tuple[str, int]] = []
            depth_discovered = 0
            depth_failed = 0

            for i, device_or_error in enumerate(devices):
                target, _ = current_batch[i]
                result.total_attempted += 1

                # Handle exceptions
                if isinstance(device_or_error, Exception):
                    result.failed += 1
                    depth_failed += 1
                    self.events.device_failed(
                        target=target,
                        error=str(device_or_error),
                        depth=depth,
                    )
                    continue

                device: Device = device_or_error

                # Register all identifiers to prevent rediscovery
                self._register_device(device)

                if device.discovery_success:
                    result.successful += 1
                    depth_discovered += 1
                    result.devices.append(device)

                    # Emit device complete event
                    method = device.discovered_via.value if device.discovered_via else "unknown"
                    self.events.device_complete(
                        target=target,
                        hostname=device.hostname,
                        ip=device.ip_address,
                        vendor=device.vendor.value if device.vendor else "unknown",
                        neighbor_count=len(device.neighbors),
                        duration_ms=device.discovery_duration_ms,
                        method=method,
                        depth=depth,
                    )

                    # Check exclusion (sys_descr, hostname, sys_name)
                    excluded, matching_pattern = self._should_exclude_device(device, exclude_patterns)
                    if excluded:
                        result.excluded += 1
                        self.events.device_excluded(device.hostname, matching_pattern)
                        continue

                    # Save to file asynchronously
                    if output_dir:
                        try:
                            await self._save_device_files(device, output_dir)
                        except Exception as e:
                            self._log(
                                f"Failed to save {device.hostname}: {e}",
                                LogLevel.WARNING,
                                device.hostname
                            )

                    # Queue neighbors for next depth
                    if depth < max_depth:
                        for neighbor in device.neighbors:
                            # Determine next target - prefer hostname, fall back to IP
                            next_target = neighbor.remote_device
                            next_ip = neighbor.remote_ip

                            # Skip MAC addresses (chassis_id leaking through)
                            if next_target and is_mac_address(next_target):
                                self.events.neighbor_skipped(
                                    next_target, "MAC address", device.hostname
                                )
                                continue

                            if next_ip and is_mac_address(next_ip):
                                next_ip = None  # Clear invalid IP

                            # Use IP if no hostname, or if --no-dns and IP available
                            if not next_target or (self.no_dns and next_ip):
                                next_target = next_ip or next_target

                            if not next_target:
                                continue

                            # Atomically claim the target
                            if self._try_claim(next_target):
                                next_batch.append((next_target, depth + 1))

                                # Also claim the IP if we have it (prevent duplicate via IP)
                                if next_ip and next_ip != next_target:
                                    self._try_claim(next_ip)

                                # Emit neighbor queued event
                                self.events.neighbor_queued(
                                    target=next_target,
                                    ip=next_ip if next_ip != next_target else None,
                                    from_device=device.hostname,
                                    depth=depth + 1,
                                )
                            else:
                                self.events.neighbor_skipped(
                                    next_target, "already claimed", device.hostname
                                )

                else:
                    result.failed += 1
                    depth_failed += 1
                    error_msg = "; ".join(device.discovery_errors) if device.discovery_errors else "Unknown error"
                    self.events.device_failed(
                        target=target,
                        error=error_msg,
                        depth=depth,
                    )

            # Emit depth complete event
            self.events.depth_complete(depth, depth_discovered, depth_failed)

            # Move to next depth
            current_batch = next_batch

        result.completed_at = datetime.now()

        # Generate topology map
        topology_map = None
        if output_dir:
            topology_map = self._generate_topology_map(result.devices)
            map_file = output_dir / 'map.json'
            await self._write_json_file(map_file, topology_map)
            self._log(f"Topology map saved to: {map_file}", LogLevel.INFO)

        # Emit topology update
        if topology_map:
            self.events.topology_updated(topology_map)

        # Emit crawl complete event
        self.events.crawl_complete(
            duration_seconds=result.duration_seconds or 0,
            topology=topology_map,
        )

        return result

    # =========================================================================
    # Topology Generation
    # =========================================================================

    def _generate_topology_map(self, devices: List[Device]) -> Dict[str, Any]:
        """
        Generate topology map from discovered devices with bidirectional validation.

        Connections are only included if:
        1. Both sides confirm the link (bidirectional), OR
        2. The peer wasn't discovered (leaf/edge case - trust unidirectional)

        Returns a dict suitable for visualization:
        {
            "device_name": {
                "node_details": {"ip": "...", "platform": "..."},
                "peers": {
                    "peer_name": {
                        "ip": "...",
                        "platform": "...",
                        "connections": [["local_if", "remote_if"], ...]
                    }
                }
            }
        }
        """
        # Build lookup for device info by various identifiers
        device_info: Dict[str, Device] = {}
        for device in devices:
            if device.hostname:
                device_info[device.hostname] = device
            if device.sys_name and device.sys_name != device.hostname:
                device_info[device.sys_name] = device
            if device.ip_address:
                device_info[device.ip_address] = device

        # Get canonical name for a device
        def get_canonical_name(device: Device) -> str:
            return device.sys_name or device.hostname or device.ip_address

        # Build set of discovered device canonical names
        discovered_devices: Set[str] = set()
        for device in devices:
            canonical = get_canonical_name(device)
            if canonical:
                discovered_devices.add(canonical)
                # Also add variations for matching
                if device.sys_name:
                    discovered_devices.add(device.sys_name)
                if device.hostname:
                    discovered_devices.add(device.hostname)

        # First pass: collect all neighbor claims
        # Key: (canonical_device, normalized_local_if) -> list of (canonical_peer, normalized_remote_if, neighbor_obj)
        all_claims: Dict[tuple, List[tuple]] = {}

        for device in devices:
            device_canonical = get_canonical_name(device)
            if not device_canonical:
                continue

            for neighbor in device.neighbors:
                if not neighbor.remote_device:
                    continue

                local_if = self._normalize_interface(neighbor.local_interface)
                remote_if = self._normalize_interface(neighbor.remote_interface)

                if not local_if or not remote_if:
                    continue

                # Get canonical peer name
                peer_name = neighbor.remote_device
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
            return True

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
                    if claimed_peer in [dev.hostname, dev.sys_name, dev.ip_address]:
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

        # Helper to check if peer is a leaf node (discovered but has no neighbors)
        def peer_is_leaf(peer_canonical: str, peer_name_original: str) -> bool:
            """Check if peer is a leaf node (no LLDP/CDP capability)."""
            # Check by canonical name
            if peer_canonical in device_info:
                peer_dev = device_info[peer_canonical]
                if len(peer_dev.neighbors) == 0:
                    return True
            # Check by original name
            if peer_name_original in device_info:
                peer_dev = device_info[peer_name_original]
                if len(peer_dev.neighbors) == 0:
                    return True
            return False

        # Second pass: build topology with validated connections
        topology: Dict[str, Any] = {}
        seen_devices: Set[str] = set()

        for device in devices:
            canonical_name = get_canonical_name(device)
            if not canonical_name or canonical_name in seen_devices:
                continue
            seen_devices.add(canonical_name)

            node = {
                "node_details": {
                    "ip": device.ip_address,
                    "platform": extract_platform(device.sys_descr,
                                                 device.vendor.value if device.vendor else None)
                },
                "peers": {}
            }

            # Group validated connections by peer
            peer_connections: Dict[str, Dict] = {}
            used_local_interfaces: Set[str] = set()  # Track used interfaces globally for this device

            for neighbor in device.neighbors:
                if not neighbor.remote_device:
                    continue

                local_if = self._normalize_interface(neighbor.local_interface)
                remote_if = self._normalize_interface(neighbor.remote_interface)

                if not local_if or not remote_if:
                    continue

                # Skip if we've already used this local interface
                if local_if in used_local_interfaces:
                    continue

                # Get canonical peer name
                peer_name = neighbor.remote_device
                canonical_peer = peer_name
                if peer_name in device_info:
                    peer_dev = device_info[peer_name]
                    canonical_peer = get_canonical_name(peer_dev)

                # Validate connection
                peer_discovered = peer_was_discovered(canonical_peer, peer_name)

                if peer_discovered:
                    # Peer was discovered - check if it's a leaf node
                    is_leaf = peer_is_leaf(canonical_peer, peer_name)

                    if is_leaf:
                        # Leaf node (no neighbors) - trust unidirectional claim
                        pass
                    elif not has_reverse_claim(canonical_name, local_if, canonical_peer, remote_if):
                        # Not a leaf and no reverse claim - drop
                        self._vprint(f"Dropping unconfirmed link: {canonical_name}:{local_if} -> {canonical_peer}:{remote_if}", 2)
                        continue
                # else: peer not discovered (leaf/edge) - trust unidirectional claim

                # Get peer platform
                peer_platform = extract_platform(neighbor.remote_description) if neighbor.remote_description else None
                if peer_name in device_info:
                    peer_dev = device_info[peer_name]
                    peer_platform = extract_platform(peer_dev.sys_descr,
                                                     peer_dev.vendor.value if peer_dev.vendor else None)

                if canonical_peer not in peer_connections:
                    peer_connections[canonical_peer] = {
                        "ip": neighbor.remote_ip,
                        "platform": peer_platform or "Unknown",
                        "connections": []
                    }

                # Add validated connection
                conn = [local_if, remote_if]
                peer_connections[canonical_peer]["connections"].append(conn)
                used_local_interfaces.add(local_if)

            node["peers"] = peer_connections
            topology[canonical_name] = node

        return topology

    def _normalize_interface(self, interface: str) -> str:
        """Normalize interface name for consistent display and deduplication."""
        if not interface:
            return ""

        result = interface.strip()

        # === Cisco long-form to short-form ===
        cisco_replacements = [
            ("GigabitEthernet", "Gi"),
            ("TenGigabitEthernet", "Te"),
            ("TenGigE", "Te"),              # IOS-XR style
            ("FortyGigabitEthernet", "Fo"),
            ("FortyGigE", "Fo"),
            ("HundredGigE", "Hu"),
            ("HundredGigabitEthernet", "Hu"),
            ("TwentyFiveGigE", "Twe"),
            ("FastEthernet", "Fa"),
            ("Ethernet", "Eth"),            # Must come after longer variants
        ]

        for long, short in cisco_replacements:
            if result.startswith(long):
                result = short + result[len(long):]
                break

        # === Port-channel normalization (case-insensitive) ===
        # Port-channel1, Port-Channel1, port-channel1 -> Po1
        port_channel_match = re.match(r'^[Pp]ort-[Cc]hannel(\d+.*)$', result)
        if port_channel_match:
            result = f"Po{port_channel_match.group(1)}"

        # === Vlan normalization ===
        # Vlan666, VLAN-666, vlan666 -> Vl666
        vlan_match = re.match(r'^[Vv][Ll][Aa][Nn]-?(\d+.*)$', result)
        if vlan_match:
            result = f"Vl{vlan_match.group(1)}"

        # === Null interface normalization ===
        # Null0 -> Nu0
        if result.startswith("Null"):
            result = "Nu" + result[4:]

        # === Loopback normalization ===
        # Loopback0 -> Lo0
        if result.startswith("Loopback"):
            result = "Lo" + result[8:]

        # === Short form normalization ===
        # Et1/1 -> Eth1/1 (Arista short form in LLDP)
        result = re.sub(r'^Et(\d)', r'Eth\1', result)

        # === Juniper subinterface normalization ===
        # xe-0/0/0.0 -> xe-0/0/0 (strip default .0 unit for matching)
        # But keep .123 or other non-zero units
        result = re.sub(r'^((?:xe|ge|et|ae|irb|em|me|fxp)-?\d+(?:/\d+)*)\.0$', r'\1', result, flags=re.IGNORECASE)

        return result

    def _connections_equal(self, conn1: List[str], conn2: List[str]) -> bool:
        """Check if two connections are equivalent (same interfaces, normalized)."""
        if len(conn1) != 2 or len(conn2) != 2:
            return False

        local1, remote1 = self._normalize_interface(conn1[0]), self._normalize_interface(conn1[1])
        local2, remote2 = self._normalize_interface(conn2[0]), self._normalize_interface(conn2[1])

        return local1 == local2 and remote1 == remote2


# Convenience function for single device discovery
async def discover_device(
    target: str,
    vault: Optional['CredentialVault'] = None,
    auth: Optional[Any] = None,
    **kwargs
) -> Device:
    """
    Quick single-device discovery.

    Args:
        target: IP address or hostname
        vault: Unlocked CredentialVault
        auth: Pre-built auth data
        **kwargs: Passed to DiscoveryEngine.discover_device()

    Returns:
        Device dataclass
    """
    engine = DiscoveryEngine(vault=vault)
    return await engine.discover_device(target, auth=auth, **kwargs)