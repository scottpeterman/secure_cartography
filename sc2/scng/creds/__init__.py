"""
SecureCartography NG - Credential Management.

A secure credential vault for network automation, supporting:
- SSH (password and key authentication)
- SNMPv2c (community strings)
- SNMPv3 (USM with auth/priv)

Quick Start:
    from scng_creds import CredentialVault

    # Initialize vault (first time)
    vault = CredentialVault()
    vault.initialize("master_password")

    # Add credentials
    vault.add_ssh_credential(
        name="lab",
        username="admin",
        password="secret123",
        is_default=True,
    )

    vault.add_snmpv2c_credential(
        name="readonly",
        community="public",
    )

    # Later - unlock and use
    vault = CredentialVault()
    vault.unlock("master_password")

    # Get credentials
    ssh = vault.get_ssh_credential("lab")
    print(f"Connecting as {ssh.username}")

    # List all (no secrets shown)
    for info in vault.list_credentials():
        print(f"{info.name}: {info.type_display}")

    vault.lock()

PyQt6 Integration:
    The vault is designed for GUI use:
    - Call unlock() once at app start
    - is_unlocked property for UI state
    - Thread-safe operations
    - CredentialResolver supports progress callbacks

    Example:
        class MainWindow(QMainWindow):
            def __init__(self):
                self.vault = CredentialVault()
                if self.vault.is_initialized:
                    self.show_unlock_dialog()
                else:
                    self.show_init_dialog()
"""

__version__ = "0.1.0"
__author__ = "Scott Peterman"

# Core vault
from .vault import (
    CredentialVault,
    VaultError,
    VaultNotInitialized,
    CredentialNotFound,
    DuplicateCredential,
    AnyCredential,
)

# Encryption layer
from .encryption import (
    VaultEncryption,
    VaultLocked,
    InvalidPassword,
    DecryptionFailed,
    generate_random_password,
)

# Models
from .models import (
    # Types
    CredentialType,
    SNMPv3AuthProtocol,
    SNMPv3PrivProtocol,
    SNMPv3SecurityLevel,
    TestResultStatus,

    # Credential objects
    SSHCredential,
    SNMPv2cCredential,
    SNMPv3Credential,

    # Metadata
    CredentialInfo,
    CredentialSet,

    # Test results
    CredentialTestResult,
    DeviceCredentialTestResult,
)

# Resolver for testing/discovery
from .resolver import (
    CredentialResolver,
    ResolverError,
    check_dependencies,
)

# Public API
__all__ = [
    # Version
    "__version__",

    # Core
    "CredentialVault",
    "CredentialResolver",
    "VaultEncryption",

    # Exceptions
    "VaultError",
    "VaultNotInitialized",
    "VaultLocked",
    "InvalidPassword",
    "DecryptionFailed",
    "CredentialNotFound",
    "DuplicateCredential",
    "ResolverError",

    # Types
    "CredentialType",
    "SNMPv3AuthProtocol",
    "SNMPv3PrivProtocol",
    "SNMPv3SecurityLevel",
    "TestResultStatus",

    # Credentials
    "SSHCredential",
    "SNMPv2cCredential",
    "SNMPv3Credential",
    "AnyCredential",

    # Metadata
    "CredentialInfo",
    "CredentialSet",

    # Results
    "CredentialTestResult",
    "DeviceCredentialTestResult",

    # Utilities
    "generate_random_password",
    "check_dependencies",
]