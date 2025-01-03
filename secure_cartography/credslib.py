# helpers/credslib.py
import os
import sys
import base64
from datetime import datetime
from pathlib import Path
from typing import Optional
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import keyring
import yaml

logger = logging.getLogger(__name__)


def derive_key(password: str, salt: bytes) -> bytes:
    """Derive a key from password and salt using PBKDF2."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


def get_machine_id() -> str:
    """Get a unique machine identifier that persists across reboots."""
    if sys.platform == "win32":
        import winreg
        try:
            with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    "SOFTWARE\\Microsoft\\Cryptography", 0,
                    winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:

                return winreg.QueryValueEx(key, "MachineGuid")[0]

        except Exception:
            logger.warning("Failed to get Windows MachineGuid")

    elif sys.platform == "darwin":
        try:
            import subprocess
            result = subprocess.run(
                ['system_profiler', 'SPHardwareDataType'],
                capture_output=True, text=True
            )
            for line in result.stdout.split('\n'):
                if "Serial Number" in line:
                    return line.split(":")[1].strip()

        except Exception:
            logger.warning("Failed to get macOS hardware serial")

    try:
        with open("/etc/machine-id", "r") as f:
            return f.read().strip()

    except Exception:
        logger.warning("Using fallback machine ID method")
        return str(hash(str(Path.home())))

def get_config_dir(app_name: str) -> Path:
    """Get the appropriate configuration directory for the current platform."""

    default_path: Path = Path.home() / ".config"

    os_path: dict = {
        "win32": Path(os.environ["APPDATA"]),
        "darwin": Path.home() / "Library" / "Application Support",
        "linux": default_path
    }

    base_dir: Path = os_path.get(sys.platform, default_path)

    config_dir = base_dir / app_name
    config_dir.mkdir(parents=True, exist_ok=True)

    return config_dir


class SecureCredentials:
    """Secure credential management system for Windows, Linux, and macOS."""

    def __init__(self, app_name: str = "NetworkMapper") -> None:
        self._app_name: str = app_name
        self._fernet: Optional[Fernet] = None
        self._config_dir: Path = get_config_dir(app_name=app_name)
        self._key_identifier: str = f"{app_name}_key_id"
        self._is_initialized: bool = self._check_initialization()

    @property
    def app_name(self) -> str:
        return self._app_name

    @property
    def key_identifier(self) -> str:
        return self._key_identifier

    @property
    def config_dir(self) -> Path:
        return self._config_dir

    @property
    def is_initialized(self) -> bool:
        return self._is_initialized

    @is_initialized.setter
    def is_initialized(self, value: bool) -> None:
        self._is_initialized = value

    def _check_initialization(self) -> bool:
        """Check if the credential system has been initialized."""
        salt_path: Path = self._config_dir / ".salt"
        return salt_path.exists()

    def is_unlocked(self) -> bool:
        """Check if the credential manager is unlocked."""
        return self._fernet is not None

    def setup_new_credentials(self, master_password: str) -> bool:
        """Initialize the encryption system with a master password."""
        try:
            # Generate a new salt
            salt = os.urandom(16)

            # Generate the encryption key
            key = derive_key(password=master_password, salt=salt)

            # Create a new Fernet instance
            self._fernet = Fernet(key)

            # Store the salt securely
            salt_path: Path = self._config_dir / ".salt"

            with open(salt_path, "wb") as f:
                f.write(salt)

            # Store an identifier in the system keyring
            machine_id: str = get_machine_id()
            keyring.set_password(self._app_name, self._key_identifier, machine_id)

            # Create empty credentials file
            creds_path = self._config_dir / "credentials.yaml"
            self.save_credentials([], creds_path)
            creds_path = self._config_dir / "network_mapper_passwords.yaml"
            self.save_credentials([], creds_path)

            self._is_initialized = True
            return True

        except Exception as e:
            logger.error(f"Failed to setup credentials: {e}")
            return False

    def unlock(self, master_password: str) -> bool:
        """Unlock the credential manager with the master password."""
        try:
            # Verify the keyring identifier
            stored_id = keyring.get_password(self._app_name, self._key_identifier)
            if stored_id != get_machine_id():
                logger.warning("Machine ID mismatch - possible security breach")
                return False

            # Load the salt
            salt_path = self._config_dir / ".salt"
            if not salt_path.exists():
                logger.error("Encryption not initialized")
                return False

            with open(salt_path, "rb") as f:
                salt = f.read()

            # Recreate the encryption key
            key: bytes = derive_key(password=master_password, salt=salt)
            self._fernet = Fernet(key)

            # Test the encryption
            test_data: str = self.encrypt_value("test")
            try:
                self.decrypt_value(test_data)
                return True

            except Exception:
                self._fernet = None
                return False

        except Exception as e:
            logger.error(f"Failed to unlock credential manager: {e}")
            self._fernet = None
            return False

    def encrypt_value(self, value: str) -> str:
        """Encrypt a single value and return as base64 string."""
        if not self._fernet:
            raise RuntimeError("Credential manager not unlocked")

        encrypted: bytes = self._fernet.encrypt(value.encode())
        return base64.b64encode(encrypted).decode('utf-8')

    def decrypt_value(self, encrypted_value: str) -> str:
        """Decrypt a base64 encoded encrypted value."""
        if not self._fernet:
            raise RuntimeError("Credential manager not unlocked")

        encrypted_bytes = base64.b64decode(encrypted_value)
        decrypted = self._fernet.decrypt(encrypted_bytes)
        return decrypted.decode('utf-8')

    # helpers/credslib.py

    def save_credentials(self, creds_list: list, filepath: Path) -> None:
        """Save credentials list to YAML file."""
        if not self._fernet:
            raise RuntimeError("Credential manager not unlocked")

        encrypted_creds = []
        for cred in creds_list:
            encrypted_cred = cred.copy()
            if 'password' in encrypted_cred and encrypted_cred['password']:
                # Directly encrypt the password without additional base64 encoding
                encrypted = self._fernet.encrypt(encrypted_cred['password'].encode())
                encrypted_cred['password'] = encrypted.decode('utf-8')
            encrypted_creds.append(encrypted_cred)

        with open(filepath, 'w') as f:
            yaml.safe_dump({
                'last_modified': datetime.now().isoformat(),
                'credentials': encrypted_creds
            }, f)

    def load_credentials(self, filepath: Path) -> list:
        """Load and decrypt credentials from YAML file."""
        if not self._fernet:
            raise RuntimeError("Credential manager not unlocked")

        if not filepath.exists():
            return []
        print(filepath)
        with open(filepath) as f:
            data = yaml.safe_load(f) or {'credentials': []}

        decrypted_creds = []
        for cred in data.get('credentials', []):
            decrypted_cred = cred.copy()
            if 'password' in decrypted_cred and decrypted_cred['password']:
                try:
                    # Directly decrypt the password without additional base64 decoding
                    decrypted = self._fernet.decrypt(decrypted_cred['password'].encode())
                    decrypted_cred['password'] = decrypted.decode('utf-8')
                except Exception as e:
                    logger.error(f"Failed to decrypt credential: {e}")
                    raise

            decrypted_creds.append(decrypted_cred)

        return decrypted_creds