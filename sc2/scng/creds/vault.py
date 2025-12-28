"""
SecureCartography NG - Credential Vault.

High-level credential storage combining encryption and database.
Handles CRUD operations for all credential types.

This is the primary interface for credential management:
- Initialize/unlock/lock vault
- Add/update/remove credentials
- List credentials (metadata only)
- Retrieve decrypted credentials

Thread safety: Each operation acquires its own connection.
For bulk operations, use the transaction context manager.
"""

import json
import base64
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Iterator, Union
from contextlib import contextmanager

from .models import (
    CredentialType, CredentialInfo, CredentialSet,
    SSHCredential, SNMPv2cCredential, SNMPv3Credential,
    SNMPv3AuthProtocol, SNMPv3PrivProtocol,
)
from .encryption import (
    VaultEncryption, VaultLocked, InvalidPassword, DecryptionFailed
)
from .schema import DatabaseManager

# Type alias for any credential type
AnyCredential = Union[SSHCredential, SNMPv2cCredential, SNMPv3Credential]


class VaultError(Exception):
    """Base exception for vault operations."""
    pass


class VaultNotInitialized(VaultError):
    """Raised when vault hasn't been initialized."""
    pass


class CredentialNotFound(VaultError):
    """Raised when credential doesn't exist."""
    pass


class DuplicateCredential(VaultError):
    """Raised when credential name already exists."""
    pass


class CredentialVault:
    """
    Encrypted credential vault.

    Manages secure storage of SSH and SNMP credentials with
    Fernet symmetric encryption.

    Usage:
        vault = CredentialVault(Path("~/.scng/vault.db"))

        # Initialize new vault
        vault.initialize("master_password")

        # Or unlock existing
        vault.unlock("master_password")

        # CRUD operations
        cred_id = vault.add_ssh_credential(
            name="lab",
            username="admin",
            password="secret"
        )

        creds = vault.list_credentials()
        ssh_cred = vault.get_ssh_credential("lab")

        # Lock when done
        vault.lock()

    PyQt6 Integration:
        The vault can be used as a singleton in your application.
        Call unlock() once at application start, then use throughout.
        The is_unlocked property can drive UI state.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize vault.

        Args:
            db_path: Path to vault database.
                     Defaults to ~/.scng/credentials.db
        """
        if db_path is None:
            db_path = Path.home() / ".scng" / "credentials.db"

        self._db = DatabaseManager(db_path)
        self._encryption = VaultEncryption()

    @property
    def db_path(self) -> Path:
        """Get database path."""
        return self._db.db_path

    @property
    def is_unlocked(self) -> bool:
        """Check if vault is currently unlocked."""
        return self._encryption.is_unlocked

    @property
    def is_initialized(self) -> bool:
        """Check if vault has been initialized."""
        if not self._db.is_initialized():
            return False

        # Check for salt in metadata
        salt = self._db.get_vault_metadata("salt")
        return salt is not None

    # =========================================================================
    # Vault Lifecycle
    # =========================================================================

    def initialize(self, master_password: str) -> None:
        """
        Initialize vault with master password.

        Creates database schema and stores encryption metadata.
        Vault will be unlocked after initialization.

        Args:
            master_password: Master password (min 8 characters).

        Raises:
            VaultError: If already initialized.
            ValueError: If password too short.
        """
        if self.is_initialized:
            raise VaultError("Vault already initialized")

        # Initialize database schema
        self._db.initialize()

        # Initialize encryption
        salt, password_hash = self._encryption.initialize(master_password)

        # Store metadata
        self._db.set_vault_metadata("salt", base64.b64encode(salt).decode())
        self._db.set_vault_metadata(
            "password_hash",
            base64.b64encode(password_hash).decode()
        )

    def unlock(self, password: str) -> bool:
        """
        Unlock vault with master password.

        Args:
            password: Master password.

        Returns:
            True if successful.

        Raises:
            VaultNotInitialized: If vault not initialized.
            InvalidPassword: If password incorrect.
        """
        if not self.is_initialized:
            raise VaultNotInitialized("Vault not initialized")

        # Get stored metadata
        salt_b64 = self._db.get_vault_metadata("salt")
        hash_b64 = self._db.get_vault_metadata("password_hash")

        if not salt_b64 or not hash_b64:
            raise VaultNotInitialized("Vault metadata missing")

        salt = base64.b64decode(salt_b64)
        password_hash = base64.b64decode(hash_b64)

        # Unlock encryption
        self._encryption.unlock(password, salt, password_hash)
        return True

    def lock(self) -> None:
        """Lock vault, clearing encryption key from memory."""
        self._encryption.lock()

    def change_password(
            self,
            current_password: str,
            new_password: str
    ) -> None:
        """
        Change master password.

        Re-encrypts all credentials with new key.

        Args:
            current_password: Current master password.
            new_password: New master password.

        Raises:
            InvalidPassword: If current password wrong.
            ValueError: If new password too short.
        """
        if not self.is_initialized:
            raise VaultNotInitialized("Vault not initialized")

        # Ensure unlocked with current password
        if not self.is_unlocked:
            self.unlock(current_password)

        # Get all credentials (decrypted)
        conn = self._db.connection()
        try:
            cursor = conn.execute(
                "SELECT id, secrets_encrypted FROM credentials"
            )
            credentials = []
            for row in cursor:
                decrypted = self._encryption.decrypt(row['secrets_encrypted'])
                credentials.append((row['id'], decrypted))

            # Get stored salt for password change
            salt_b64 = self._db.get_vault_metadata("salt")
            hash_b64 = self._db.get_vault_metadata("password_hash")
            salt = base64.b64decode(salt_b64)
            password_hash = base64.b64decode(hash_b64)

            # Change password (generates new salt and key)
            new_salt, new_hash = self._encryption.change_password(
                current_password, new_password, salt, password_hash
            )

            # Re-encrypt all credentials with new key
            for cred_id, secrets_json in credentials:
                new_encrypted = self._encryption.encrypt(secrets_json)
                conn.execute(
                    "UPDATE credentials SET secrets_encrypted = ? WHERE id = ?",
                    (new_encrypted, cred_id)
                )

            # Update stored metadata
            conn.execute(
                "INSERT OR REPLACE INTO vault_metadata (key, value) VALUES (?, ?)",
                ("salt", base64.b64encode(new_salt).decode())
            )
            conn.execute(
                "INSERT OR REPLACE INTO vault_metadata (key, value) VALUES (?, ?)",
                ("password_hash", base64.b64encode(new_hash).decode())
            )

            conn.commit()
        finally:
            conn.close()

    # =========================================================================
    # SSH Credentials
    # =========================================================================

    def add_ssh_credential(
            self,
            name: str,
            username: str,
            password: Optional[str] = None,
            key_content: Optional[str] = None,
            key_passphrase: Optional[str] = None,
            port: int = 22,
            timeout_seconds: int = 30,
            description: Optional[str] = None,
            priority: int = 100,
            is_default: bool = False,
            tags: Optional[List[str]] = None,
    ) -> int:
        """
        Add SSH credential.

        Args:
            name: Unique credential name.
            username: SSH username.
            password: SSH password (optional if using key).
            key_content: SSH private key PEM content.
            key_passphrase: Passphrase for encrypted key.
            port: SSH port (default 22).
            timeout_seconds: Connection timeout.
            description: Human-readable description.
            priority: Priority for ordering (lower = higher priority).
            is_default: Set as default SSH credential.
            tags: Tags for filtering.

        Returns:
            ID of created credential.
        """
        self._require_unlocked()

        if not password and not key_content:
            raise ValueError("Must provide password or SSH key")

        # Build secrets JSON
        secrets = {}
        if password:
            secrets["password"] = password
        if key_content:
            secrets["key_content"] = key_content
        if key_passphrase:
            secrets["key_passphrase"] = key_passphrase

        secrets_encrypted = self._encryption.encrypt(json.dumps(secrets))

        # Settings
        settings = {"timeout_seconds": timeout_seconds}

        return self._insert_credential(
            name=name,
            credential_type=CredentialType.SSH,
            display_username=username,
            port=port,
            secrets_encrypted=secrets_encrypted,
            settings_json=json.dumps(settings),
            description=description,
            priority=priority,
            is_default=is_default,
            tags=tags or [],
        )

    def get_ssh_credential(
            self,
            name: Optional[str] = None,
            credential_id: Optional[int] = None,
    ) -> Optional[SSHCredential]:
        """
        Get decrypted SSH credential.

        Args:
            name: Credential name (use this or credential_id).
            credential_id: Credential ID.

        Returns:
            SSHCredential or None if not found.
        """
        self._require_unlocked()

        row = self._get_credential_row(
            name=name,
            credential_id=credential_id,
            credential_type=CredentialType.SSH
        )

        if not row:
            return None

        # Decrypt secrets
        secrets = json.loads(self._encryption.decrypt(row['secrets_encrypted']))
        settings = json.loads(row['settings_json'] or '{}')

        return SSHCredential(
            username=row['display_username'],
            password=secrets.get('password'),
            key_content=secrets.get('key_content'),
            key_passphrase=secrets.get('key_passphrase'),
            port=row['port'] or 22,
            timeout_seconds=settings.get('timeout_seconds', 30),
        )

    # =========================================================================
    # SNMP v2c Credentials
    # =========================================================================

    def add_snmpv2c_credential(
            self,
            name: str,
            community: str,
            port: int = 161,
            timeout_seconds: int = 5,
            retries: int = 2,
            description: Optional[str] = None,
            priority: int = 100,
            is_default: bool = False,
            tags: Optional[List[str]] = None,
    ) -> int:
        """
        Add SNMPv2c credential.

        Args:
            name: Unique credential name.
            community: SNMP community string.
            port: SNMP port (default 161).
            timeout_seconds: Request timeout.
            retries: Number of retries.
            description: Human-readable description.
            priority: Priority for ordering.
            is_default: Set as default SNMPv2c credential.
            tags: Tags for filtering.

        Returns:
            ID of created credential.
        """
        self._require_unlocked()

        secrets = {"community": community}
        secrets_encrypted = self._encryption.encrypt(json.dumps(secrets))

        settings = {
            "timeout_seconds": timeout_seconds,
            "retries": retries,
        }

        return self._insert_credential(
            name=name,
            credential_type=CredentialType.SNMP_V2C,
            display_username=None,  # Community is secret
            port=port,
            secrets_encrypted=secrets_encrypted,
            settings_json=json.dumps(settings),
            description=description,
            priority=priority,
            is_default=is_default,
            tags=tags or [],
        )

    def get_snmpv2c_credential(
            self,
            name: Optional[str] = None,
            credential_id: Optional[int] = None,
    ) -> Optional[SNMPv2cCredential]:
        """Get decrypted SNMPv2c credential."""
        self._require_unlocked()

        row = self._get_credential_row(
            name=name,
            credential_id=credential_id,
            credential_type=CredentialType.SNMP_V2C
        )

        if not row:
            return None

        secrets = json.loads(self._encryption.decrypt(row['secrets_encrypted']))
        settings = json.loads(row['settings_json'] or '{}')

        return SNMPv2cCredential(
            community=secrets['community'],
            port=row['port'] or 161,
            timeout_seconds=settings.get('timeout_seconds', 5),
            retries=settings.get('retries', 2),
        )

    # =========================================================================
    # SNMP v3 Credentials
    # =========================================================================

    def add_snmpv3_credential(
            self,
            name: str,
            username: str,
            auth_protocol: SNMPv3AuthProtocol = SNMPv3AuthProtocol.NONE,
            auth_password: Optional[str] = None,
            priv_protocol: SNMPv3PrivProtocol = SNMPv3PrivProtocol.NONE,
            priv_password: Optional[str] = None,
            context_name: str = "",
            context_engine_id: Optional[str] = None,
            port: int = 161,
            timeout_seconds: int = 5,
            retries: int = 2,
            description: Optional[str] = None,
            priority: int = 100,
            is_default: bool = False,
            tags: Optional[List[str]] = None,
    ) -> int:
        """
        Add SNMPv3 credential.

        Args:
            name: Unique credential name.
            username: SNMPv3 security name.
            auth_protocol: Authentication protocol.
            auth_password: Authentication password.
            priv_protocol: Privacy protocol.
            priv_password: Privacy password.
            context_name: SNMP context name.
            context_engine_id: Context engine ID (hex string).
            port: SNMP port (default 161).
            timeout_seconds: Request timeout.
            retries: Number of retries.
            description: Human-readable description.
            priority: Priority for ordering.
            is_default: Set as default SNMPv3 credential.
            tags: Tags for filtering.

        Returns:
            ID of created credential.
        """
        self._require_unlocked()

        # Validate auth/priv combination
        if priv_protocol != SNMPv3PrivProtocol.NONE:
            if auth_protocol == SNMPv3AuthProtocol.NONE:
                raise ValueError(
                    "Privacy requires authentication - set auth_protocol"
                )
            if not priv_password:
                raise ValueError("Privacy protocol requires priv_password")

        if auth_protocol != SNMPv3AuthProtocol.NONE and not auth_password:
            raise ValueError("Authentication protocol requires auth_password")

        secrets = {
            "auth_protocol": auth_protocol.value,
            "priv_protocol": priv_protocol.value,
        }
        if auth_password:
            secrets["auth_password"] = auth_password
        if priv_password:
            secrets["priv_password"] = priv_password

        secrets_encrypted = self._encryption.encrypt(json.dumps(secrets))

        settings = {
            "timeout_seconds": timeout_seconds,
            "retries": retries,
            "context_name": context_name,
        }
        if context_engine_id:
            settings["context_engine_id"] = context_engine_id

        return self._insert_credential(
            name=name,
            credential_type=CredentialType.SNMP_V3,
            display_username=username,
            port=port,
            secrets_encrypted=secrets_encrypted,
            settings_json=json.dumps(settings),
            description=description,
            priority=priority,
            is_default=is_default,
            tags=tags or [],
        )

    def get_snmpv3_credential(
            self,
            name: Optional[str] = None,
            credential_id: Optional[int] = None,
    ) -> Optional[SNMPv3Credential]:
        """Get decrypted SNMPv3 credential."""
        self._require_unlocked()

        row = self._get_credential_row(
            name=name,
            credential_id=credential_id,
            credential_type=CredentialType.SNMP_V3
        )

        if not row:
            return None

        secrets = json.loads(self._encryption.decrypt(row['secrets_encrypted']))
        settings = json.loads(row['settings_json'] or '{}')

        return SNMPv3Credential(
            username=row['display_username'],
            auth_protocol=SNMPv3AuthProtocol(secrets.get('auth_protocol', 'none')),
            auth_password=secrets.get('auth_password'),
            priv_protocol=SNMPv3PrivProtocol(secrets.get('priv_protocol', 'none')),
            priv_password=secrets.get('priv_password'),
            context_name=settings.get('context_name', ''),
            context_engine_id=settings.get('context_engine_id'),
            port=row['port'] or 161,
            timeout_seconds=settings.get('timeout_seconds', 5),
            retries=settings.get('retries', 2),
        )

    # =========================================================================
    # Generic Credential Operations
    # =========================================================================

    def get_credential(
            self,
            name: Optional[str] = None,
            credential_id: Optional[int] = None,
    ) -> Optional[AnyCredential]:
        """
        Get any credential by name or ID.

        Returns the appropriate typed credential object.
        """
        self._require_unlocked()

        row = self._get_credential_row(name=name, credential_id=credential_id)
        if not row:
            return None

        cred_type = CredentialType(row['credential_type'])

        if cred_type == CredentialType.SSH:
            return self.get_ssh_credential(credential_id=row['id'])
        elif cred_type == CredentialType.SNMP_V2C:
            return self.get_snmpv2c_credential(credential_id=row['id'])
        elif cred_type == CredentialType.SNMP_V3:
            return self.get_snmpv3_credential(credential_id=row['id'])

        return None

    def list_credentials(
            self,
            credential_type: Optional[Union[CredentialType, List[CredentialType]]] = None,
            tags: Optional[List[str]] = None,
            include_defaults_only: bool = False,
    ) -> List[CredentialInfo]:
        """
        List credentials (metadata only, no secrets).

        Args:
            credential_type: Filter by type.
            tags: Filter by tags (any match).
            include_defaults_only: Only return default credentials.

        Returns:
            List of CredentialInfo objects.
        """
        conn = self._db.connection()
        try:
            query = """
                SELECT * FROM credentials
                WHERE 1=1
            """
            params: List[Any] = []

            if credential_type:
                if isinstance(credential_type, list):
                    placeholders = ','.join('?' * len(credential_type))
                    query += f" AND credential_type IN ({placeholders})"
                    params.extend(ct.value for ct in credential_type)
                else:
                    query += " AND credential_type = ?"
                    params.append(credential_type.value)

            if include_defaults_only:
                query += " AND is_default = 1"

            query += " ORDER BY priority, name"

            cursor = conn.execute(query, params)

            results = []
            for row in cursor:
                info = self._row_to_credential_info(row)

                # Filter by tags if specified
                if tags:
                    row_tags = json.loads(row['tags_json'] or '[]')
                    if not any(t in row_tags for t in tags):
                        continue

                results.append(info)

            return results
        finally:
            conn.close()

    def get_credentials_by_type(
            self,
            credential_type: CredentialType,
            default_only: bool = False,
    ) -> List[AnyCredential]:
        """
        Get all credentials of a specific type (decrypted).

        Args:
            credential_type: Type to retrieve.
            default_only: Only return default credential.

        Returns:
            List of credential objects.
        """
        self._require_unlocked()

        infos = self.list_credentials(
            credential_type=credential_type,
            include_defaults_only=default_only,
        )

        results = []
        for info in infos:
            cred = self.get_credential(credential_id=info.id)
            if cred:
                results.append(cred)

        return results

    def remove_credential(
            self,
            name: Optional[str] = None,
            credential_id: Optional[int] = None,
    ) -> bool:
        """
        Remove credential.

        Returns True if deleted, False if not found.
        """
        conn = self._db.connection()
        try:
            if name:
                cursor = conn.execute(
                    "DELETE FROM credentials WHERE name = ?",
                    (name,)
                )
            elif credential_id:
                cursor = conn.execute(
                    "DELETE FROM credentials WHERE id = ?",
                    (credential_id,)
                )
            else:
                raise ValueError("Must provide name or credential_id")

            deleted = cursor.rowcount > 0
            conn.commit()
            return deleted
        finally:
            conn.close()

    def set_default(
            self,
            name: Optional[str] = None,
            credential_id: Optional[int] = None,
    ) -> bool:
        """
        Set credential as default for its type.

        Clears default flag on other credentials of same type.
        """
        # Get credential info
        info = self.get_credential_info(name=name, credential_id=credential_id)
        if not info:
            return False

        conn = self._db.connection()
        try:
            # Clear existing defaults for this type
            conn.execute(
                "UPDATE credentials SET is_default = 0 WHERE credential_type = ?",
                (info.credential_type.value,)
            )

            # Set new default
            conn.execute(
                "UPDATE credentials SET is_default = 1 WHERE id = ?",
                (info.id,)
            )

            conn.commit()
            return True
        finally:
            conn.close()

    def get_credential_info(
            self,
            name: Optional[str] = None,
            credential_id: Optional[int] = None,
    ) -> Optional[CredentialInfo]:
        """Get credential metadata (no secrets)."""
        row = self._get_credential_row(
            name=name,
            credential_id=credential_id,
            include_secrets=False
        )
        if not row:
            return None
        return self._row_to_credential_info(row)

    def update_test_result(
            self,
            credential_id: int,
            success: bool,
            error: Optional[str] = None,
    ) -> None:
        """Update credential's last test result."""
        conn = self._db.connection()
        try:
            conn.execute("""
                UPDATE credentials 
                SET last_test_success = ?,
                    last_test_at = datetime('now'),
                    last_test_error = ?
                WHERE id = ?
            """, (1 if success else 0, error, credential_id))
            conn.commit()
        finally:
            conn.close()

    def record_usage(self, credential_id: int) -> None:
        """Record credential usage (updates last_used_at, use_count)."""
        conn = self._db.connection()
        try:
            conn.execute("""
                UPDATE credentials 
                SET last_used_at = datetime('now'),
                    use_count = use_count + 1
                WHERE id = ?
            """, (credential_id,))
            conn.commit()
        finally:
            conn.close()

    # =========================================================================
    # Credential Sets
    # =========================================================================

    def add_credential_set(
            self,
            name: str,
            description: Optional[str] = None,
            ssh_credential_ids: Optional[List[int]] = None,
            snmp_credential_ids: Optional[List[int]] = None,
            tags: Optional[List[str]] = None,
            is_default: bool = False,
    ) -> int:
        """Add credential set (group of credentials)."""
        conn = self._db.connection()
        try:
            if is_default:
                conn.execute(
                    "UPDATE credential_sets SET is_default = 0"
                )

            cursor = conn.execute("""
                INSERT INTO credential_sets (
                    name, description, ssh_credential_ids_json,
                    snmp_credential_ids_json, tags_json, is_default
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                name,
                description,
                json.dumps(ssh_credential_ids or []),
                json.dumps(snmp_credential_ids or []),
                json.dumps(tags or []),
                1 if is_default else 0,
            ))

            set_id = cursor.lastrowid
            conn.commit()
            return set_id
        except sqlite3.IntegrityError as e:
            raise DuplicateCredential(f"Credential set '{name}' already exists") from e
        finally:
            conn.close()

    def get_credential_set(
            self,
            name: Optional[str] = None,
            set_id: Optional[int] = None,
    ) -> Optional[CredentialSet]:
        """Get credential set."""
        conn = self._db.connection()
        try:
            if name:
                cursor = conn.execute(
                    "SELECT * FROM credential_sets WHERE name = ?",
                    (name,)
                )
            elif set_id:
                cursor = conn.execute(
                    "SELECT * FROM credential_sets WHERE id = ?",
                    (set_id,)
                )
            else:
                raise ValueError("Must provide name or set_id")

            row = cursor.fetchone()
            if not row:
                return None

            return CredentialSet(
                id=row['id'],
                name=row['name'],
                description=row['description'],
                ssh_credential_ids=json.loads(row['ssh_credential_ids_json'] or '[]'),
                snmp_credential_ids=json.loads(row['snmp_credential_ids_json'] or '[]'),
                tags=json.loads(row['tags_json'] or '[]'),
                is_default=bool(row['is_default']),
                created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
                updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
            )
        finally:
            conn.close()

    def list_credential_sets(self) -> List[CredentialSet]:
        """List all credential sets."""
        conn = self._db.connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM credential_sets ORDER BY name"
            )

            results = []
            for row in cursor:
                results.append(CredentialSet(
                    id=row['id'],
                    name=row['name'],
                    description=row['description'],
                    ssh_credential_ids=json.loads(row['ssh_credential_ids_json'] or '[]'),
                    snmp_credential_ids=json.loads(row['snmp_credential_ids_json'] or '[]'),
                    tags=json.loads(row['tags_json'] or '[]'),
                    is_default=bool(row['is_default']),
                ))

            return results
        finally:
            conn.close()

    # =========================================================================
    # Private Helpers
    # =========================================================================

    def _require_unlocked(self) -> None:
        """Raise if vault is locked."""
        if not self.is_unlocked:
            raise VaultLocked("Vault must be unlocked")

    def _insert_credential(
            self,
            name: str,
            credential_type: CredentialType,
            display_username: Optional[str],
            port: Optional[int],
            secrets_encrypted: str,
            settings_json: str,
            description: Optional[str],
            priority: int,
            is_default: bool,
            tags: List[str],
    ) -> int:
        """Insert credential row."""
        conn = self._db.connection()
        try:
            # Clear existing default if setting new default
            if is_default:
                conn.execute(
                    "UPDATE credentials SET is_default = 0 WHERE credential_type = ?",
                    (credential_type.value,)
                )

            cursor = conn.execute("""
                INSERT INTO credentials (
                    name, credential_type, description, display_username,
                    port, secrets_encrypted, settings_json, priority,
                    is_default, tags_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                name,
                credential_type.value,
                description,
                display_username,
                port,
                secrets_encrypted,
                settings_json,
                priority,
                1 if is_default else 0,
                json.dumps(tags),
            ))

            cred_id = cursor.lastrowid
            conn.commit()
            return cred_id
        except sqlite3.IntegrityError as e:
            raise DuplicateCredential(f"Credential '{name}' already exists") from e
        finally:
            conn.close()

    def _get_credential_row(
            self,
            name: Optional[str] = None,
            credential_id: Optional[int] = None,
            credential_type: Optional[CredentialType] = None,
            include_secrets: bool = True,
    ) -> Optional[sqlite3.Row]:
        """Get credential row from database."""
        conn = self._db.connection()
        try:
            query = "SELECT * FROM credentials WHERE "
            params: List[Any] = []

            if credential_id:
                query += "id = ?"
                params.append(credential_id)
            elif name:
                query += "name = ?"
                params.append(name)
            else:
                # Get default
                query += "is_default = 1"
                if credential_type:
                    query += " AND credential_type = ?"
                    params.append(credential_type.value)

            if credential_type and credential_id:
                query += " AND credential_type = ?"
                params.append(credential_type.value)

            cursor = conn.execute(query, params)
            return cursor.fetchone()
        finally:
            conn.close()

    def _row_to_credential_info(self, row: sqlite3.Row) -> CredentialInfo:
        """Convert database row to CredentialInfo."""
        cred_type = CredentialType(row['credential_type'])
        tags = json.loads(row['tags_json'] or '[]')

        # Determine capability flags based on type
        # (We can peek at settings_json without decrypting secrets)
        has_password = False
        has_key = False
        has_auth = False
        has_priv = False

        # For capability flags, we'd need to decrypt - skip for listing
        # These will be populated if secrets were decrypted

        return CredentialInfo(
            id=row['id'],
            name=row['name'],
            credential_type=cred_type,
            description=row['description'],
            display_username=row['display_username'],
            has_password=has_password,
            has_key=has_key,
            has_auth=has_auth,
            has_priv=has_priv,
            priority=row['priority'],
            is_default=bool(row['is_default']),
            tags=tags,
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
            last_used_at=datetime.fromisoformat(row['last_used_at']) if row['last_used_at'] else None,
            last_test_success=bool(row['last_test_success']) if row['last_test_success'] is not None else None,
            last_test_at=datetime.fromisoformat(row['last_test_at']) if row['last_test_at'] else None,
        )