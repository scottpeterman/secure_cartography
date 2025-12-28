"""
SecureCartography NG - Credential Data Models.

Dataclasses representing credentials for SSH and SNMP authentication.
All sensitive fields are stored encrypted in the vault.

Design principles:
- Immutable dataclasses for credential data
- Clear separation between metadata (CredentialInfo) and secrets
- Protocol-specific credential classes
- Support for multiple credentials per type with priority ordering
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any


class CredentialType(str, Enum):
    """Credential protocol types."""
    SSH = "ssh"
    SNMP_V2C = "snmp_v2c"
    SNMP_V3 = "snmp_v3"


class SNMPv3AuthProtocol(str, Enum):
    """SNMPv3 authentication protocols."""
    NONE = "none"
    MD5 = "md5"
    SHA = "sha"
    SHA224 = "sha224"
    SHA256 = "sha256"
    SHA384 = "sha384"
    SHA512 = "sha512"


class SNMPv3PrivProtocol(str, Enum):
    """SNMPv3 privacy/encryption protocols."""
    NONE = "none"
    DES = "des"
    AES = "aes"  # AES-128
    AES192 = "aes192"
    AES256 = "aes256"


class SNMPv3SecurityLevel(str, Enum):
    """SNMPv3 security levels (derived from auth/priv settings)."""
    NO_AUTH_NO_PRIV = "noAuthNoPriv"
    AUTH_NO_PRIV = "authNoPriv"
    AUTH_PRIV = "authPriv"


# =============================================================================
# SSH Credentials
# =============================================================================

@dataclass(frozen=True)
class SSHCredential:
    """
    SSH credential for device authentication.

    Supports password auth, key auth, or both (for key passphrase).
    Immutable to prevent accidental modification of secrets.
    """
    username: str
    password: Optional[str] = None
    key_content: Optional[str] = None  # PEM private key content
    key_passphrase: Optional[str] = None

    # Connection hints
    port: int = 22
    timeout_seconds: int = 30

    @property
    def has_key(self) -> bool:
        """Check if SSH key is available."""
        return self.key_content is not None

    @property
    def has_password(self) -> bool:
        """Check if password is available."""
        return self.password is not None

    @property
    def auth_methods(self) -> List[str]:
        """List available authentication methods."""
        methods = []
        if self.has_key:
            methods.append("publickey")
        if self.has_password:
            methods.append("password")
        return methods

    def to_paramiko_kwargs(self) -> Dict[str, Any]:
        """Convert to kwargs for paramiko.SSHClient.connect()."""
        kwargs = {
            "username": self.username,
            "port": self.port,
            "timeout": self.timeout_seconds,
            "allow_agent": False,
            "look_for_keys": False,
        }
        if self.password:
            kwargs["password"] = self.password
        if self.key_content:
            # Key will need to be loaded as RSAKey/Ed25519Key by caller
            kwargs["pkey"] = None  # Placeholder - caller handles key loading
        return kwargs


# =============================================================================
# SNMP v2c Credentials
# =============================================================================

@dataclass(frozen=True)
class SNMPv2cCredential:
    """
    SNMPv2c credential (community string).

    Simple community-based authentication.
    """
    community: str

    # Connection hints
    port: int = 161
    timeout_seconds: int = 5
    retries: int = 2

    @property
    def version(self) -> str:
        return "2c"


# =============================================================================
# SNMP v3 Credentials
# =============================================================================

@dataclass(frozen=True)
class SNMPv3Credential:
    """
    SNMPv3 credential with USM security model.

    Supports all three security levels:
    - noAuthNoPriv: Username only
    - authNoPriv: Username + authentication
    - authPriv: Username + authentication + encryption
    """
    username: str

    # Authentication
    auth_protocol: SNMPv3AuthProtocol = SNMPv3AuthProtocol.NONE
    auth_password: Optional[str] = None

    # Privacy/Encryption
    priv_protocol: SNMPv3PrivProtocol = SNMPv3PrivProtocol.NONE
    priv_password: Optional[str] = None

    # Context (optional)
    context_name: str = ""
    context_engine_id: Optional[str] = None

    # Connection hints
    port: int = 161
    timeout_seconds: int = 5
    retries: int = 2

    @property
    def version(self) -> str:
        return "3"

    @property
    def security_level(self) -> SNMPv3SecurityLevel:
        """Determine security level from auth/priv settings."""
        has_auth = (
                self.auth_protocol != SNMPv3AuthProtocol.NONE
                and self.auth_password
        )
        has_priv = (
                self.priv_protocol != SNMPv3PrivProtocol.NONE
                and self.priv_password
        )

        if has_auth and has_priv:
            return SNMPv3SecurityLevel.AUTH_PRIV
        elif has_auth:
            return SNMPv3SecurityLevel.AUTH_NO_PRIV
        else:
            return SNMPv3SecurityLevel.NO_AUTH_NO_PRIV

    def to_pysnmp_kwargs(self) -> Dict[str, Any]:
        """
        Convert to kwargs suitable for PySNMP UsmUserData.

        Note: Caller should import and use pysnmp types:
            from pysnmp.hlapi import UsmUserData
            user_data = UsmUserData(**cred.to_pysnmp_kwargs())
        """
        kwargs: Dict[str, Any] = {
            "userName": self.username,
        }

        # Map auth protocols to pysnmp constants (by name)
        auth_map = {
            SNMPv3AuthProtocol.MD5: "usmHMACMD5AuthProtocol",
            SNMPv3AuthProtocol.SHA: "usmHMACSHAAuthProtocol",
            SNMPv3AuthProtocol.SHA224: "usmHMAC128SHA224AuthProtocol",
            SNMPv3AuthProtocol.SHA256: "usmHMAC192SHA256AuthProtocol",
            SNMPv3AuthProtocol.SHA384: "usmHMAC256SHA384AuthProtocol",
            SNMPv3AuthProtocol.SHA512: "usmHMAC384SHA512AuthProtocol",
        }

        priv_map = {
            SNMPv3PrivProtocol.DES: "usmDESPrivProtocol",
            SNMPv3PrivProtocol.AES: "usmAesCfb128Protocol",
            SNMPv3PrivProtocol.AES192: "usmAesCfb192Protocol",
            SNMPv3PrivProtocol.AES256: "usmAesCfb256Protocol",
        }

        if self.auth_protocol != SNMPv3AuthProtocol.NONE and self.auth_password:
            kwargs["authKey"] = self.auth_password
            kwargs["authProtocol"] = auth_map.get(self.auth_protocol)

        if self.priv_protocol != SNMPv3PrivProtocol.NONE and self.priv_password:
            kwargs["privKey"] = self.priv_password
            kwargs["privProtocol"] = priv_map.get(self.priv_protocol)

        return kwargs


# =============================================================================
# Credential Metadata (without secrets)
# =============================================================================

@dataclass
class CredentialInfo:
    """
    Credential metadata without secrets.

    Used for listing, display, and selection without exposing sensitive data.
    """
    id: int
    name: str
    credential_type: CredentialType
    description: Optional[str] = None

    # For SSH: username
    # For SNMPv2c: None (community is secret)
    # For SNMPv3: username
    display_username: Optional[str] = None

    # Capability flags
    has_password: bool = False
    has_key: bool = False
    has_auth: bool = False  # SNMPv3
    has_priv: bool = False  # SNMPv3

    # Ordering for multi-credential testing
    priority: int = 100  # Lower = higher priority
    is_default: bool = False

    # Tags for filtering/grouping
    tags: List[str] = field(default_factory=list)

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None

    # Test results
    last_test_success: Optional[bool] = None
    last_test_at: Optional[datetime] = None

    @property
    def type_display(self) -> str:
        """Human-readable credential type."""
        return {
            CredentialType.SSH: "SSH",
            CredentialType.SNMP_V2C: "SNMPv2c",
            CredentialType.SNMP_V3: "SNMPv3",
        }.get(self.credential_type, str(self.credential_type))

    @property
    def auth_summary(self) -> str:
        """Summary of authentication methods available."""
        if self.credential_type == CredentialType.SSH:
            methods = []
            if self.has_password:
                methods.append("password")
            if self.has_key:
                methods.append("key")
            return ", ".join(methods) or "none"
        elif self.credential_type == CredentialType.SNMP_V2C:
            return "community"
        elif self.credential_type == CredentialType.SNMP_V3:
            if self.has_auth and self.has_priv:
                return "authPriv"
            elif self.has_auth:
                return "authNoPriv"
            else:
                return "noAuthNoPriv"
        return "unknown"


# =============================================================================
# Credential Set (grouping multiple credentials)
# =============================================================================

@dataclass
class CredentialSet:
    """
    Named set of credentials for a device or device group.

    Groups related SSH and SNMP credentials together for convenient
    assignment to devices. Supports fallback ordering.
    """
    id: int
    name: str
    description: Optional[str] = None

    # Credential references (by ID, ordered by priority)
    ssh_credential_ids: List[int] = field(default_factory=list)
    snmp_credential_ids: List[int] = field(default_factory=list)

    # Metadata
    tags: List[str] = field(default_factory=list)
    is_default: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# =============================================================================
# Test Results
# =============================================================================

class TestResultStatus(str, Enum):
    """Credential test result status."""
    SUCCESS = "success"
    AUTH_FAILURE = "auth_failure"
    TIMEOUT = "timeout"
    CONNECTION_REFUSED = "connection_refused"
    HOST_UNREACHABLE = "host_unreachable"
    DNS_FAILURE = "dns_failure"
    PROTOCOL_ERROR = "protocol_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class CredentialTestResult:
    """Result of testing a credential against a target."""
    credential_id: int
    credential_name: str
    credential_type: CredentialType

    target_host: str
    target_port: int

    success: bool
    status: TestResultStatus
    error_message: Optional[str] = None

    # Timing
    started_at: Optional[datetime] = None
    duration_ms: float = 0.0

    # Additional info on success
    prompt_detected: Optional[str] = None  # SSH
    system_description: Optional[str] = None  # SNMP sysDescr


@dataclass
class DeviceCredentialTestResult:
    """Aggregate result of testing multiple credentials against a device."""
    device_name: str
    target_host: str

    # Results per credential tested
    test_results: List[CredentialTestResult] = field(default_factory=list)

    # Summary
    success: bool = False
    matched_credential_id: Optional[int] = None
    matched_credential_name: Optional[str] = None
    matched_credential_type: Optional[CredentialType] = None

    # Timing
    total_duration_ms: float = 0.0

    @property
    def attempts(self) -> int:
        """Number of credentials tested."""
        return len(self.test_results)