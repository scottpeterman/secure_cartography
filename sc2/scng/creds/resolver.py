"""
SecureCartography NG - Credential Resolver.

High-level credential retrieval with connection testing.

This module provides:
- Credential discovery (find working credentials for a device)
- Connection testing (SSH, SNMPv2c, SNMPv3)
- Fallback logic for trying multiple credentials
- Async operations for bulk testing

Design for PyQt6 Integration:
- All blocking operations support timeout
- Progress callbacks for UI updates
- Cancellation support via threading.Event
- Signal-friendly result objects
"""

import socket
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Callable, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from .models import (
    CredentialType, CredentialInfo,
    SSHCredential, SNMPv2cCredential, SNMPv3Credential,
    CredentialTestResult, DeviceCredentialTestResult,
    TestResultStatus,
)
from .vault import CredentialVault, AnyCredential

# Optional imports for actual testing
try:
    import paramiko

    HAS_PARAMIKO = True
except ImportError:
    HAS_PARAMIKO = False

try:
    from pysnmp.hlapi import (
        getCmd, SnmpEngine, CommunityData, UsmUserData,
        UdpTransportTarget, ContextData, ObjectType, ObjectIdentity,
    )

    HAS_PYSNMP = True
except ImportError:
    HAS_PYSNMP = False


class ResolverError(Exception):
    """Base exception for resolver operations."""
    pass


class CredentialResolver:
    """
    High-level credential operations.

    Wraps CredentialVault with connection testing and discovery.

    Usage:
        resolver = CredentialResolver(vault)

        # Test specific credential
        result = resolver.test_ssh_credential("lab", "192.168.1.1")

        # Discover working credentials for a device
        result = resolver.discover_credentials(
            host="192.168.1.1",
            credential_types=[CredentialType.SSH, CredentialType.SNMP_V2C],
            progress_callback=lambda r: print(f"Tested: {r.credential_name}")
        )

        # Bulk discovery
        results = resolver.discover_bulk(
            hosts=["192.168.1.1", "192.168.1.2"],
            max_workers=4,
            progress_callback=lambda completed, total, r: update_progress(completed, total)
        )

    PyQt6 Integration:
        # In your worker thread
        def run_discovery(self):
            resolver = CredentialResolver(self.vault)

            def on_progress(completed, total, result):
                self.progress.emit(completed, total)
                if result.success:
                    self.credential_found.emit(result.device_name, result.matched_credential_name)

            results = resolver.discover_bulk(
                hosts=self.hosts,
                cancel_event=self.cancel_event,
                progress_callback=on_progress
            )

            self.finished.emit(results)
    """

    def __init__(self, vault: CredentialVault):
        """
        Initialize resolver.

        Args:
            vault: Unlocked CredentialVault instance.
        """
        self.vault = vault

    # =========================================================================
    # Single Credential Testing
    # =========================================================================

    def test_ssh_credential(
            self,
            credential_name: str,
            host: str,
            port: Optional[int] = None,
            timeout: Optional[int] = None,
    ) -> CredentialTestResult:
        """
        Test SSH credential against a host.

        Args:
            credential_name: Name of SSH credential.
            host: Target hostname or IP.
            port: Override port (default from credential).
            timeout: Override timeout (default from credential).

        Returns:
            CredentialTestResult with success/failure details.
        """
        cred = self.vault.get_ssh_credential(name=credential_name)
        if not cred:
            return CredentialTestResult(
                credential_id=0,
                credential_name=credential_name,
                credential_type=CredentialType.SSH,
                target_host=host,
                target_port=port or 22,
                success=False,
                status=TestResultStatus.UNKNOWN_ERROR,
                error_message=f"Credential '{credential_name}' not found",
            )

        info = self.vault.get_credential_info(name=credential_name)

        return self._test_ssh(
            credential=cred,
            credential_id=info.id if info else 0,
            credential_name=credential_name,
            host=host,
            port=port,
            timeout=timeout,
        )

    def test_snmpv2c_credential(
            self,
            credential_name: str,
            host: str,
            port: Optional[int] = None,
            timeout: Optional[int] = None,
    ) -> CredentialTestResult:
        """Test SNMPv2c credential against a host."""
        cred = self.vault.get_snmpv2c_credential(name=credential_name)
        if not cred:
            return CredentialTestResult(
                credential_id=0,
                credential_name=credential_name,
                credential_type=CredentialType.SNMP_V2C,
                target_host=host,
                target_port=port or 161,
                success=False,
                status=TestResultStatus.UNKNOWN_ERROR,
                error_message=f"Credential '{credential_name}' not found",
            )

        info = self.vault.get_credential_info(name=credential_name)

        return self._test_snmpv2c(
            credential=cred,
            credential_id=info.id if info else 0,
            credential_name=credential_name,
            host=host,
            port=port,
            timeout=timeout,
        )

    def test_snmpv3_credential(
            self,
            credential_name: str,
            host: str,
            port: Optional[int] = None,
            timeout: Optional[int] = None,
    ) -> CredentialTestResult:
        """Test SNMPv3 credential against a host."""
        cred = self.vault.get_snmpv3_credential(name=credential_name)
        if not cred:
            return CredentialTestResult(
                credential_id=0,
                credential_name=credential_name,
                credential_type=CredentialType.SNMP_V3,
                target_host=host,
                target_port=port or 161,
                success=False,
                status=TestResultStatus.UNKNOWN_ERROR,
                error_message=f"Credential '{credential_name}' not found",
            )

        info = self.vault.get_credential_info(name=credential_name)

        return self._test_snmpv3(
            credential=cred,
            credential_id=info.id if info else 0,
            credential_name=credential_name,
            host=host,
            port=port,
            timeout=timeout,
        )

    # =========================================================================
    # Credential Discovery
    # =========================================================================

    def discover_credentials(
            self,
            host: str,
            device_name: Optional[str] = None,
            credential_types: Optional[List[CredentialType]] = None,
            credential_names: Optional[List[str]] = None,
            stop_on_first: bool = True,
            progress_callback: Optional[Callable[[CredentialTestResult], None]] = None,
            cancel_event: Optional[threading.Event] = None,
    ) -> DeviceCredentialTestResult:
        """
        Discover working credentials for a device.

        Tries credentials in priority order until one succeeds.

        Args:
            host: Target hostname or IP.
            device_name: Device name for result (default: host).
            credential_types: Types to test (default: all).
            credential_names: Specific credentials to test (default: all).
            stop_on_first: Stop after first success per type.
            progress_callback: Called after each test.
            cancel_event: Set to cancel discovery.

        Returns:
            DeviceCredentialTestResult with all test results.
        """
        device_name = device_name or host
        start_time = time.time()

        result = DeviceCredentialTestResult(
            device_name=device_name,
            target_host=host,
        )

        # Get credentials to test
        if credential_names:
            creds_to_test = [
                self.vault.get_credential_info(name=name)
                for name in credential_names
            ]
            creds_to_test = [c for c in creds_to_test if c is not None]
        else:
            creds_to_test = self.vault.list_credentials(
                credential_type=credential_types[0] if credential_types and len(credential_types) == 1 else None
            )

        # Filter by type if specified
        if credential_types:
            creds_to_test = [
                c for c in creds_to_test
                if c.credential_type in credential_types
            ]

        # Sort by priority
        creds_to_test.sort(key=lambda c: c.priority)

        # Track which types have succeeded
        succeeded_types: set = set()

        for cred_info in creds_to_test:
            # Check cancellation
            if cancel_event and cancel_event.is_set():
                break

            # Skip if we already found a working credential of this type
            if stop_on_first and cred_info.credential_type in succeeded_types:
                continue

            # Test based on type
            test_result = self._test_credential(cred_info, host)
            result.test_results.append(test_result)

            # Update result if success
            if test_result.success:
                succeeded_types.add(cred_info.credential_type)

                if not result.success:  # First success
                    result.success = True
                    result.matched_credential_id = test_result.credential_id
                    result.matched_credential_name = test_result.credential_name
                    result.matched_credential_type = test_result.credential_type

                # Update vault test result
                self.vault.update_test_result(
                    cred_info.id,
                    success=True
                )
            else:
                self.vault.update_test_result(
                    cred_info.id,
                    success=False,
                    error=test_result.error_message
                )

            # Progress callback
            if progress_callback:
                progress_callback(test_result)

        result.total_duration_ms = (time.time() - start_time) * 1000
        return result

    def discover_bulk(
            self,
            hosts: List[str],
            device_names: Optional[Dict[str, str]] = None,
            credential_types: Optional[List[CredentialType]] = None,
            max_workers: int = 8,
            progress_callback: Optional[Callable[[int, int, DeviceCredentialTestResult], None]] = None,
            cancel_event: Optional[threading.Event] = None,
    ) -> List[DeviceCredentialTestResult]:
        """
        Discover credentials for multiple hosts in parallel.

        Args:
            hosts: List of hostnames/IPs.
            device_names: Map of host -> device_name.
            credential_types: Types to test.
            max_workers: Maximum parallel connections.
            progress_callback: Called with (completed, total, result).
            cancel_event: Set to cancel discovery.

        Returns:
            List of DeviceCredentialTestResult.
        """
        device_names = device_names or {}
        total = len(hosts)
        completed = 0
        results: List[DeviceCredentialTestResult] = []
        results_lock = threading.Lock()

        def test_host(host: str) -> DeviceCredentialTestResult:
            return self.discover_credentials(
                host=host,
                device_name=device_names.get(host),
                credential_types=credential_types,
                cancel_event=cancel_event,
            )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(test_host, host): host
                for host in hosts
            }

            for future in as_completed(futures):
                if cancel_event and cancel_event.is_set():
                    # Cancel remaining futures
                    for f in futures:
                        f.cancel()
                    break

                host = futures[future]
                try:
                    result = future.result()
                except Exception as e:
                    result = DeviceCredentialTestResult(
                        device_name=device_names.get(host, host),
                        target_host=host,
                        success=False,
                    )
                    result.test_results.append(CredentialTestResult(
                        credential_id=0,
                        credential_name="",
                        credential_type=CredentialType.SSH,
                        target_host=host,
                        target_port=0,
                        success=False,
                        status=TestResultStatus.UNKNOWN_ERROR,
                        error_message=str(e),
                    ))

                with results_lock:
                    results.append(result)
                    completed += 1

                if progress_callback:
                    progress_callback(completed, total, result)

        return results

    # =========================================================================
    # Protocol-Specific Testing
    # =========================================================================

    def _test_credential(
            self,
            cred_info: CredentialInfo,
            host: str,
    ) -> CredentialTestResult:
        """Test a credential based on its type."""
        if cred_info.credential_type == CredentialType.SSH:
            cred = self.vault.get_ssh_credential(credential_id=cred_info.id)
            if cred:
                return self._test_ssh(
                    credential=cred,
                    credential_id=cred_info.id,
                    credential_name=cred_info.name,
                    host=host,
                )

        elif cred_info.credential_type == CredentialType.SNMP_V2C:
            cred = self.vault.get_snmpv2c_credential(credential_id=cred_info.id)
            if cred:
                return self._test_snmpv2c(
                    credential=cred,
                    credential_id=cred_info.id,
                    credential_name=cred_info.name,
                    host=host,
                )

        elif cred_info.credential_type == CredentialType.SNMP_V3:
            cred = self.vault.get_snmpv3_credential(credential_id=cred_info.id)
            if cred:
                return self._test_snmpv3(
                    credential=cred,
                    credential_id=cred_info.id,
                    credential_name=cred_info.name,
                    host=host,
                )

        return CredentialTestResult(
            credential_id=cred_info.id,
            credential_name=cred_info.name,
            credential_type=cred_info.credential_type,
            target_host=host,
            target_port=0,
            success=False,
            status=TestResultStatus.UNKNOWN_ERROR,
            error_message="Failed to retrieve credential",
        )

    def _test_ssh(
            self,
            credential: SSHCredential,
            credential_id: int,
            credential_name: str,
            host: str,
            port: Optional[int] = None,
            timeout: Optional[int] = None,
    ) -> CredentialTestResult:
        """Test SSH connection."""
        actual_port = port or credential.port
        actual_timeout = timeout or credential.timeout_seconds

        start_time = time.time()

        if not HAS_PARAMIKO:
            return CredentialTestResult(
                credential_id=credential_id,
                credential_name=credential_name,
                credential_type=CredentialType.SSH,
                target_host=host,
                target_port=actual_port,
                success=False,
                status=TestResultStatus.UNKNOWN_ERROR,
                error_message="paramiko not installed",
                started_at=datetime.now(),
                duration_ms=(time.time() - start_time) * 1000,
            )

        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            connect_kwargs = {
                "hostname": host,
                "port": actual_port,
                "username": credential.username,
                "timeout": actual_timeout,
                "allow_agent": False,
                "look_for_keys": False,
                "banner_timeout": actual_timeout,
                "auth_timeout": actual_timeout,
            }

            # Key authentication
            if credential.key_content:
                # Parse key from string
                import io
                key_file = io.StringIO(credential.key_content)

                try:
                    pkey = paramiko.RSAKey.from_private_key(
                        key_file,
                        password=credential.key_passphrase
                    )
                except paramiko.SSHException:
                    key_file.seek(0)
                    try:
                        pkey = paramiko.Ed25519Key.from_private_key(
                            key_file,
                            password=credential.key_passphrase
                        )
                    except paramiko.SSHException:
                        key_file.seek(0)
                        pkey = paramiko.ECDSAKey.from_private_key(
                            key_file,
                            password=credential.key_passphrase
                        )

                connect_kwargs["pkey"] = pkey

            # Password authentication
            if credential.password:
                connect_kwargs["password"] = credential.password

            client.connect(**connect_kwargs)

            # Get prompt to verify we're really connected
            prompt_detected = None
            try:
                channel = client.invoke_shell()
                channel.settimeout(3)
                time.sleep(0.5)
                if channel.recv_ready():
                    output = channel.recv(4096).decode('utf-8', errors='replace')
                    # Extract last line as prompt
                    lines = output.strip().split('\n')
                    if lines:
                        prompt_detected = lines[-1].strip()
                channel.close()
            except Exception:
                pass

            client.close()

            return CredentialTestResult(
                credential_id=credential_id,
                credential_name=credential_name,
                credential_type=CredentialType.SSH,
                target_host=host,
                target_port=actual_port,
                success=True,
                status=TestResultStatus.SUCCESS,
                prompt_detected=prompt_detected,
                started_at=datetime.now(),
                duration_ms=(time.time() - start_time) * 1000,
            )

        except paramiko.AuthenticationException as e:
            return CredentialTestResult(
                credential_id=credential_id,
                credential_name=credential_name,
                credential_type=CredentialType.SSH,
                target_host=host,
                target_port=actual_port,
                success=False,
                status=TestResultStatus.AUTH_FAILURE,
                error_message=str(e),
                started_at=datetime.now(),
                duration_ms=(time.time() - start_time) * 1000,
            )

        except socket.timeout:
            return CredentialTestResult(
                credential_id=credential_id,
                credential_name=credential_name,
                credential_type=CredentialType.SSH,
                target_host=host,
                target_port=actual_port,
                success=False,
                status=TestResultStatus.TIMEOUT,
                error_message="Connection timed out",
                started_at=datetime.now(),
                duration_ms=(time.time() - start_time) * 1000,
            )

        except ConnectionRefusedError:
            return CredentialTestResult(
                credential_id=credential_id,
                credential_name=credential_name,
                credential_type=CredentialType.SSH,
                target_host=host,
                target_port=actual_port,
                success=False,
                status=TestResultStatus.CONNECTION_REFUSED,
                error_message=f"Connection refused on port {actual_port}",
                started_at=datetime.now(),
                duration_ms=(time.time() - start_time) * 1000,
            )

        except socket.gaierror as e:
            return CredentialTestResult(
                credential_id=credential_id,
                credential_name=credential_name,
                credential_type=CredentialType.SSH,
                target_host=host,
                target_port=actual_port,
                success=False,
                status=TestResultStatus.DNS_FAILURE,
                error_message=f"DNS resolution failed: {e}",
                started_at=datetime.now(),
                duration_ms=(time.time() - start_time) * 1000,
            )

        except OSError as e:
            if "No route to host" in str(e) or "Network is unreachable" in str(e):
                status = TestResultStatus.HOST_UNREACHABLE
            else:
                status = TestResultStatus.UNKNOWN_ERROR

            return CredentialTestResult(
                credential_id=credential_id,
                credential_name=credential_name,
                credential_type=CredentialType.SSH,
                target_host=host,
                target_port=actual_port,
                success=False,
                status=status,
                error_message=str(e),
                started_at=datetime.now(),
                duration_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            return CredentialTestResult(
                credential_id=credential_id,
                credential_name=credential_name,
                credential_type=CredentialType.SSH,
                target_host=host,
                target_port=actual_port,
                success=False,
                status=TestResultStatus.UNKNOWN_ERROR,
                error_message=str(e),
                started_at=datetime.now(),
                duration_ms=(time.time() - start_time) * 1000,
            )

    def _test_snmpv2c(
            self,
            credential: SNMPv2cCredential,
            credential_id: int,
            credential_name: str,
            host: str,
            port: Optional[int] = None,
            timeout: Optional[int] = None,
    ) -> CredentialTestResult:
        """Test SNMPv2c connection by fetching sysDescr."""
        actual_port = port or credential.port
        actual_timeout = timeout or credential.timeout_seconds

        start_time = time.time()

        if not HAS_PYSNMP:
            return CredentialTestResult(
                credential_id=credential_id,
                credential_name=credential_name,
                credential_type=CredentialType.SNMP_V2C,
                target_host=host,
                target_port=actual_port,
                success=False,
                status=TestResultStatus.UNKNOWN_ERROR,
                error_message="pysnmp not installed",
                started_at=datetime.now(),
                duration_ms=(time.time() - start_time) * 1000,
            )

        try:
            iterator = getCmd(
                SnmpEngine(),
                CommunityData(credential.community, mpModel=1),  # v2c
                UdpTransportTarget(
                    (host, actual_port),
                    timeout=actual_timeout,
                    retries=credential.retries,
                ),
                ContextData(),
                ObjectType(ObjectIdentity('SNMPv2-MIB', 'sysDescr', 0)),
            )

            errorIndication, errorStatus, errorIndex, varBinds = next(iterator)

            if errorIndication:
                # Timeout or other SNMP error
                error_str = str(errorIndication)
                if "timeout" in error_str.lower():
                    status = TestResultStatus.TIMEOUT
                else:
                    status = TestResultStatus.PROTOCOL_ERROR

                return CredentialTestResult(
                    credential_id=credential_id,
                    credential_name=credential_name,
                    credential_type=CredentialType.SNMP_V2C,
                    target_host=host,
                    target_port=actual_port,
                    success=False,
                    status=status,
                    error_message=error_str,
                    started_at=datetime.now(),
                    duration_ms=(time.time() - start_time) * 1000,
                )

            elif errorStatus:
                return CredentialTestResult(
                    credential_id=credential_id,
                    credential_name=credential_name,
                    credential_type=CredentialType.SNMP_V2C,
                    target_host=host,
                    target_port=actual_port,
                    success=False,
                    status=TestResultStatus.AUTH_FAILURE,
                    error_message=f"{errorStatus.prettyPrint()} at {varBinds[int(errorIndex) - 1][0] if errorIndex else '?'}",
                    started_at=datetime.now(),
                    duration_ms=(time.time() - start_time) * 1000,
                )

            else:
                # Success - extract sysDescr
                sys_descr = None
                for varBind in varBinds:
                    sys_descr = str(varBind[1])
                    break

                return CredentialTestResult(
                    credential_id=credential_id,
                    credential_name=credential_name,
                    credential_type=CredentialType.SNMP_V2C,
                    target_host=host,
                    target_port=actual_port,
                    success=True,
                    status=TestResultStatus.SUCCESS,
                    system_description=sys_descr,
                    started_at=datetime.now(),
                    duration_ms=(time.time() - start_time) * 1000,
                )

        except Exception as e:
            return CredentialTestResult(
                credential_id=credential_id,
                credential_name=credential_name,
                credential_type=CredentialType.SNMP_V2C,
                target_host=host,
                target_port=actual_port,
                success=False,
                status=TestResultStatus.UNKNOWN_ERROR,
                error_message=str(e),
                started_at=datetime.now(),
                duration_ms=(time.time() - start_time) * 1000,
            )

    def _test_snmpv3(
            self,
            credential: SNMPv3Credential,
            credential_id: int,
            credential_name: str,
            host: str,
            port: Optional[int] = None,
            timeout: Optional[int] = None,
    ) -> CredentialTestResult:
        """Test SNMPv3 connection by fetching sysDescr."""
        actual_port = port or credential.port
        actual_timeout = timeout or credential.timeout_seconds

        start_time = time.time()

        if not HAS_PYSNMP:
            return CredentialTestResult(
                credential_id=credential_id,
                credential_name=credential_name,
                credential_type=CredentialType.SNMP_V3,
                target_host=host,
                target_port=actual_port,
                success=False,
                status=TestResultStatus.UNKNOWN_ERROR,
                error_message="pysnmp not installed",
                started_at=datetime.now(),
                duration_ms=(time.time() - start_time) * 1000,
            )

        try:
            # Import pysnmp auth/priv protocols
            from pysnmp.hlapi import (
                usmHMACMD5AuthProtocol, usmHMACSHAAuthProtocol,
                usmHMAC128SHA224AuthProtocol, usmHMAC192SHA256AuthProtocol,
                usmHMAC256SHA384AuthProtocol, usmHMAC384SHA512AuthProtocol,
                usmDESPrivProtocol, usmAesCfb128Protocol,
                usmAesCfb192Protocol, usmAesCfb256Protocol,
                usmNoAuthProtocol, usmNoPrivProtocol,
            )

            # Map protocols
            from .models import SNMPv3AuthProtocol, SNMPv3PrivProtocol

            auth_map = {
                SNMPv3AuthProtocol.NONE: usmNoAuthProtocol,
                SNMPv3AuthProtocol.MD5: usmHMACMD5AuthProtocol,
                SNMPv3AuthProtocol.SHA: usmHMACSHAAuthProtocol,
                SNMPv3AuthProtocol.SHA224: usmHMAC128SHA224AuthProtocol,
                SNMPv3AuthProtocol.SHA256: usmHMAC192SHA256AuthProtocol,
                SNMPv3AuthProtocol.SHA384: usmHMAC256SHA384AuthProtocol,
                SNMPv3AuthProtocol.SHA512: usmHMAC384SHA512AuthProtocol,
            }

            priv_map = {
                SNMPv3PrivProtocol.NONE: usmNoPrivProtocol,
                SNMPv3PrivProtocol.DES: usmDESPrivProtocol,
                SNMPv3PrivProtocol.AES: usmAesCfb128Protocol,
                SNMPv3PrivProtocol.AES192: usmAesCfb192Protocol,
                SNMPv3PrivProtocol.AES256: usmAesCfb256Protocol,
            }

            # Build UsmUserData
            usm_kwargs: Dict[str, Any] = {}

            if credential.auth_protocol != SNMPv3AuthProtocol.NONE:
                usm_kwargs["authKey"] = credential.auth_password
                usm_kwargs["authProtocol"] = auth_map[credential.auth_protocol]

            if credential.priv_protocol != SNMPv3PrivProtocol.NONE:
                usm_kwargs["privKey"] = credential.priv_password
                usm_kwargs["privProtocol"] = priv_map[credential.priv_protocol]

            user_data = UsmUserData(credential.username, **usm_kwargs)

            iterator = getCmd(
                SnmpEngine(),
                user_data,
                UdpTransportTarget(
                    (host, actual_port),
                    timeout=actual_timeout,
                    retries=credential.retries,
                ),
                ContextData(contextName=credential.context_name),
                ObjectType(ObjectIdentity('SNMPv2-MIB', 'sysDescr', 0)),
            )

            errorIndication, errorStatus, errorIndex, varBinds = next(iterator)

            if errorIndication:
                error_str = str(errorIndication)
                if "timeout" in error_str.lower():
                    status = TestResultStatus.TIMEOUT
                elif "unknown" in error_str.lower() or "auth" in error_str.lower():
                    status = TestResultStatus.AUTH_FAILURE
                else:
                    status = TestResultStatus.PROTOCOL_ERROR

                return CredentialTestResult(
                    credential_id=credential_id,
                    credential_name=credential_name,
                    credential_type=CredentialType.SNMP_V3,
                    target_host=host,
                    target_port=actual_port,
                    success=False,
                    status=status,
                    error_message=error_str,
                    started_at=datetime.now(),
                    duration_ms=(time.time() - start_time) * 1000,
                )

            elif errorStatus:
                return CredentialTestResult(
                    credential_id=credential_id,
                    credential_name=credential_name,
                    credential_type=CredentialType.SNMP_V3,
                    target_host=host,
                    target_port=actual_port,
                    success=False,
                    status=TestResultStatus.AUTH_FAILURE,
                    error_message=f"{errorStatus.prettyPrint()}",
                    started_at=datetime.now(),
                    duration_ms=(time.time() - start_time) * 1000,
                )

            else:
                sys_descr = None
                for varBind in varBinds:
                    sys_descr = str(varBind[1])
                    break

                return CredentialTestResult(
                    credential_id=credential_id,
                    credential_name=credential_name,
                    credential_type=CredentialType.SNMP_V3,
                    target_host=host,
                    target_port=actual_port,
                    success=True,
                    status=TestResultStatus.SUCCESS,
                    system_description=sys_descr,
                    started_at=datetime.now(),
                    duration_ms=(time.time() - start_time) * 1000,
                )

        except Exception as e:
            return CredentialTestResult(
                credential_id=credential_id,
                credential_name=credential_name,
                credential_type=CredentialType.SNMP_V3,
                target_host=host,
                target_port=actual_port,
                success=False,
                status=TestResultStatus.UNKNOWN_ERROR,
                error_message=str(e),
                started_at=datetime.now(),
                duration_ms=(time.time() - start_time) * 1000,
            )


def check_dependencies() -> Dict[str, bool]:
    """Check which optional dependencies are available."""
    return {
        "paramiko": HAS_PARAMIKO,
        "pysnmp": HAS_PYSNMP,
    }