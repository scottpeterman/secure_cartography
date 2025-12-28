"""
SecureCartography NG - Encryption Layer.

Handles all cryptographic operations:
- Key derivation from master password (PBKDF2)
- Symmetric encryption/decryption (Fernet)
- Password hashing for verification

This module is stateless - the VaultEncryption class holds the derived key
in memory only while unlocked.

Security notes:
- Uses PBKDF2-HMAC-SHA256 with 480,000 iterations (OWASP recommendation 2023)
- Fernet provides AES-128-CBC with HMAC-SHA256 authentication
- Salt is randomly generated per vault initialization
- Key material cleared from memory on lock
"""

import os
import hashlib
import base64
import secrets
from typing import Optional, Tuple
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# PBKDF2 iterations - OWASP 2023 recommends 600,000 for PBKDF2-HMAC-SHA256
# Using 480,000 as a balance between security and usability
PBKDF2_ITERATIONS = 480_000

# Salt size in bytes (128 bits)
SALT_SIZE = 16

# Password hash iterations (separate from key derivation)
PASSWORD_HASH_ITERATIONS = 100_000


class EncryptionError(Exception):
    """Base exception for encryption operations."""
    pass


class VaultLocked(EncryptionError):
    """Raised when attempting crypto operations on locked vault."""
    pass


class InvalidPassword(EncryptionError):
    """Raised when vault password verification fails."""
    pass


class DecryptionFailed(EncryptionError):
    """Raised when decryption fails (corrupted or wrong key)."""
    pass


@dataclass
class VaultKeyMaterial:
    """
    Key material derived from master password.

    Contains the salt (stored) and derived key (memory only).
    """
    salt: bytes
    password_hash: bytes  # For verification

    # These are derived and held in memory only
    _derived_key: Optional[bytes] = None
    _fernet: Optional[Fernet] = None

    @property
    def is_unlocked(self) -> bool:
        return self._fernet is not None

    def clear(self):
        """Clear sensitive key material from memory."""
        self._derived_key = None
        self._fernet = None


class VaultEncryption:
    """
    Manages vault encryption/decryption.

    Usage:
        # Initialize new vault
        enc = VaultEncryption()
        salt, pw_hash = enc.initialize("master_password")
        # Store salt and pw_hash

        # Later - unlock existing vault
        enc = VaultEncryption()
        enc.unlock("master_password", stored_salt, stored_pw_hash)

        # Encrypt/decrypt
        ciphertext = enc.encrypt("secret data")
        plaintext = enc.decrypt(ciphertext)

        # Lock when done
        enc.lock()
    """

    def __init__(self):
        self._key_material: Optional[VaultKeyMaterial] = None

    @property
    def is_unlocked(self) -> bool:
        """Check if vault is currently unlocked."""
        return (
                self._key_material is not None
                and self._key_material.is_unlocked
        )

    def initialize(self, master_password: str) -> Tuple[bytes, bytes]:
        """
        Initialize encryption with a new master password.

        Args:
            master_password: Master password for vault.

        Returns:
            Tuple of (salt, password_hash) to be stored.

        Raises:
            ValueError: If password too short.
        """
        if len(master_password) < 8:
            raise ValueError("Master password must be at least 8 characters")

        # Generate random salt
        salt = secrets.token_bytes(SALT_SIZE)

        # Hash password for verification
        password_hash = hashlib.pbkdf2_hmac(
            'sha256',
            master_password.encode('utf-8'),
            salt,
            PASSWORD_HASH_ITERATIONS
        )

        # Derive encryption key
        derived_key = self._derive_key(master_password, salt)

        # Create Fernet instance
        fernet = Fernet(derived_key)

        # Store key material
        self._key_material = VaultKeyMaterial(
            salt=salt,
            password_hash=password_hash,
            _derived_key=derived_key,
            _fernet=fernet,
        )

        return salt, password_hash

    def unlock(
            self,
            password: str,
            salt: bytes,
            stored_password_hash: bytes
    ) -> bool:
        """
        Unlock vault with master password.

        Args:
            password: Master password.
            salt: Salt from vault initialization.
            stored_password_hash: Password hash from vault initialization.

        Returns:
            True if password correct and vault unlocked.

        Raises:
            InvalidPassword: If password verification fails.
        """
        # Verify password
        computed_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            PASSWORD_HASH_ITERATIONS
        )

        if not secrets.compare_digest(computed_hash, stored_password_hash):
            raise InvalidPassword("Invalid vault password")

        # Derive encryption key
        derived_key = self._derive_key(password, salt)

        # Create Fernet instance
        fernet = Fernet(derived_key)

        # Store key material
        self._key_material = VaultKeyMaterial(
            salt=salt,
            password_hash=stored_password_hash,
            _derived_key=derived_key,
            _fernet=fernet,
        )

        return True

    def lock(self):
        """Lock vault, clearing key material from memory."""
        if self._key_material:
            self._key_material.clear()
        self._key_material = None

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a string.

        Args:
            plaintext: String to encrypt.

        Returns:
            Base64-encoded ciphertext.

        Raises:
            VaultLocked: If vault not unlocked.
        """
        if not self.is_unlocked:
            raise VaultLocked("Vault must be unlocked to encrypt")

        ciphertext = self._key_material._fernet.encrypt(
            plaintext.encode('utf-8')
        )
        return ciphertext.decode('ascii')

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt a string.

        Args:
            ciphertext: Base64-encoded ciphertext.

        Returns:
            Decrypted plaintext.

        Raises:
            VaultLocked: If vault not unlocked.
            DecryptionFailed: If decryption fails.
        """
        if not self.is_unlocked:
            raise VaultLocked("Vault must be unlocked to decrypt")

        try:
            plaintext = self._key_material._fernet.decrypt(
                ciphertext.encode('ascii')
            )
            return plaintext.decode('utf-8')
        except InvalidToken as e:
            raise DecryptionFailed(
                "Decryption failed - data may be corrupted or key incorrect"
            ) from e

    def encrypt_bytes(self, data: bytes) -> bytes:
        """Encrypt raw bytes."""
        if not self.is_unlocked:
            raise VaultLocked("Vault must be unlocked to encrypt")
        return self._key_material._fernet.encrypt(data)

    def decrypt_bytes(self, ciphertext: bytes) -> bytes:
        """Decrypt to raw bytes."""
        if not self.is_unlocked:
            raise VaultLocked("Vault must be unlocked to decrypt")
        try:
            return self._key_material._fernet.decrypt(ciphertext)
        except InvalidToken as e:
            raise DecryptionFailed("Decryption failed") from e

    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """Derive encryption key from password using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=PBKDF2_ITERATIONS,
        )
        key = kdf.derive(password.encode('utf-8'))
        return base64.urlsafe_b64encode(key)

    def change_password(
            self,
            current_password: str,
            new_password: str,
            salt: bytes,
            stored_password_hash: bytes
    ) -> Tuple[bytes, bytes]:
        """
        Change master password.

        Note: This only generates new key material. Caller is responsible
        for re-encrypting all stored credentials with the new key.

        Args:
            current_password: Current master password.
            new_password: New master password.
            salt: Current salt.
            stored_password_hash: Current password hash.

        Returns:
            Tuple of (new_salt, new_password_hash).

        Raises:
            InvalidPassword: If current password wrong.
            ValueError: If new password too short.
        """
        # Verify current password
        self.unlock(current_password, salt, stored_password_hash)

        # Initialize with new password
        self.lock()
        return self.initialize(new_password)


def generate_random_password(length: int = 32) -> str:
    """Generate a cryptographically secure random password."""
    alphabet = (
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789"
        "!@#$%^&*"
    )
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def hash_for_display(data: str, length: int = 8) -> str:
    """
    Generate a short hash for display purposes (not security).

    Useful for showing a credential fingerprint without revealing content.
    """
    full_hash = hashlib.sha256(data.encode()).hexdigest()
    return full_hash[:length]