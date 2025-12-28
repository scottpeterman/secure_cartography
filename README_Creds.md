# SecureCartography NG - Credential Management

Encrypted
credential
vault
for network automation.Supports SSH (password / key), SNMPv2c, and SNMPv3 with secure Fernet encryption.

## Features

- ** Multi - Protocol
Support **: SSH, SNMPv2c, SNMPv3
- ** Secure
Storage **: Fernet
symmetric
encryption
with PBKDF2 key derivation
- ** Multiple
Credentials **: Store and manage
multiple
credentials
per
protocol
- ** Priority
Ordering **: Automatic
fallback
through
credentials
by
priority
- ** Credential
Discovery **: Test
credentials
against
devices in bulk
- ** CLI & Library **: Use
from command line or integrate
into
PyQt6 / Python
apps
- ** Thread - Safe **: Designed
for concurrent access in GUI applications

## Installation

```bash
# Core package
pip
install
scng - creds

# With SSH support
pip
install
scng - creds[ssh]

# With SNMP support
pip
install
scng - creds[snmp]

# Full installation
pip
install
scng - creds[all]
```

## Quick Start

### Command Line

```bash
# Initialize vault
scng - creds
init

# Add SSH credential
scng - creds
add
ssh
lab - -username
admin - -default
# Prompts for password

# Add SSH with key
scng - creds
add
ssh
prod - -username
netadmin - -key - file
~ /.ssh / id_rsa

# Add SNMPv2c
scng - creds
add
snmpv2c
readonly - -community
public

# Add SNMPv3
scng - creds
add
snmpv3
v3user - -username
snmpuser \
- -auth - protocol
sha256 - -auth - password
secret \
- -priv - protocol
aes256 - -priv - password
private

# List credentials
scng - creds
list

# Test credential
scng - creds
test
lab
192.168
.1
.1

# Discover working credentials
scng - creds
discover
192.168
.1
.1 - -type
ssh - -type
snmpv2c
```

### Python Library

```python
from scng_creds import CredentialVault, CredentialType

# Initialize vault (first time only)
vault = CredentialVault()
vault.initialize("master_password")

# Add credentials
vault.add_ssh_credential(
    name="lab",
    username="admin",
    password="secret123",
    is_default=True,
)

vault.add_ssh_credential(
    name="prod",
    username="netadmin",
    key_content=open("~/.ssh/id_rsa").read(),
    priority=50,  # Higher priority than default
)

vault.add_snmpv2c_credential(
    name="readonly",
    community="public",
    is_default=True,
)

vault.add_snmpv3_credential(
    name="v3auth",
    username="snmpuser",
    auth_protocol=SNMPv3AuthProtocol.SHA256,
    auth_password="authpass",
    priv_protocol=SNMPv3PrivProtocol.AES256,
    priv_password="privpass",
)

# Lock when done adding
vault.lock()
```

### Using Credentials

```python
from scng_creds import CredentialVault

vault = CredentialVault()
vault.unlock("master_password")

# Get specific credential
ssh = vault.get_ssh_credential("lab")
print(f"Username: {ssh.username}")
print(f"Has key: {ssh.has_key}")

# Get default for type
default_ssh = vault.get_ssh_credential()  # Returns default

# List all (metadata only - no secrets)
for info in vault.list_credentials():
    print(f"{info.name}: {info.type_display} ({info.auth_summary})")

vault.lock()
```

### Credential Discovery

```python
from scng_creds import CredentialVault, CredentialResolver, CredentialType

vault = CredentialVault()
vault.unlock("master_password")

resolver = CredentialResolver(vault)

# Test single credential
result = resolver.test_ssh_credential("lab", "192.168.1.1")
if result.success:
    print(f"Connected! Prompt: {result.prompt_detected}")

# Discover working credentials for a device
result = resolver.discover_credentials(
    host="192.168.1.1",
    credential_types=[CredentialType.SSH, CredentialType.SNMP_V2C],
    progress_callback=lambda r: print(f"Tested: {r.credential_name}")
)

if result.success:
    print(f"Working credential: {result.matched_credential_name}")

# Bulk discovery
results = resolver.discover_bulk(
    hosts=["192.168.1.1", "192.168.1.2", "192.168.1.3"],
    max_workers=4,
    progress_callback=lambda done, total, r: print(f"{done}/{total}")
)

vault.lock()
```

## PyQt6 Integration

The
library is designed
for seamless PyQt6 integration:

```python
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QMainWindow, QDialog
from scng_creds import CredentialVault, CredentialResolver


class CredentialWorker(QThread):
    """Background worker for credential operations."""
    progress = pyqtSignal(int, int)  # completed, total
    found = pyqtSignal(str, str)  # host, credential_name
    finished = pyqtSignal(list)

    def __init__(self, vault, hosts):
        super().__init__()
        self.vault = vault
        self.hosts = hosts
        self.cancel_event = threading.Event()

    def run(self):
        resolver = CredentialResolver(self.vault)

        def on_progress(completed, total, result):
            self.progress.emit(completed, total)
            if result.success:
                self.found.emit(result.device_name, result.matched_credential_name)

        results = resolver.discover_bulk(
            hosts=self.hosts,
            cancel_event=self.cancel_event,
            progress_callback=on_progress,
        )

        self.finished.emit(results)

    def cancel(self):
        self.cancel_event.set()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.vault = CredentialVault()

        # Check vault state on startup
        if not self.vault.is_initialized:
            self.show_init_dialog()
        elif not self.vault.is_unlocked:
            self.show_unlock_dialog()

    def show_unlock_dialog(self):
        password, ok = QInputDialog.getText(
            self, "Unlock Vault", "Master password:",
            QLineEdit.EchoMode.Password
        )
        if ok:
            try:
                self.vault.unlock(password)
            except InvalidPassword:
                QMessageBox.warning(self, "Error", "Invalid password")


```

## Environment Variables

| Variable | Description |
| ---------- | ------------- |
| `SCNG_VAULT_PASSWORD` | Master
password(
for scripting) |
| `SCNG_VAULT_PATH` | Path
to
vault
database |

## Database Schema

The
vault
uses
SQLite
with encrypted secrets:

- `credentials` - Main
credential
storage(encrypted
secrets as JSON)
- `credential_sets` - Groups
of
credentials
for device assignment
    - `device_credentials` - Discovered
    device / credential
    mappings
- `credential_test_history` - Test
result
history

## Security

- ** Encryption **: Fernet(AES - 128 - CBC + HMAC - SHA256)
- ** Key
Derivation **: PBKDF2 - HMAC - SHA256
with 480, 000 iterations
- ** Password
Verification **: Separate
hash
with 100, 000 iterations
- ** Memory
Safety **: Key
material
cleared
on
lock()

## CLI Reference

```
scng - creds
init
Initialize
vault
scng - creds
unlock
Validate
password(
for scripts)
scng - creds
add
ssh < n > Add
SSH
credential
scng - creds
add
snmpv2c < n > Add
SNMPv2c
credential
scng - creds
add
snmpv3 < n > Add
SNMPv3
credential
scng - creds
list
List
credentials
scng - creds
show < n > [--reveal]
Show
credential
details
scng - creds
remove < n > Remove
credential
scng - creds
set - default < n > Set as default
for type
    scng - creds
    test < n > < host > Test
    against
    host
scng - creds
discover < host > Find
working
credentials
scng - creds
change - password
Change
master
password
scng - creds
deps
Check
optional
dependencies
```

## License

MIT
License - See
LICENSE
file
for details.

## Author

Scott
Peterman([ @ scottpeterman](https: // github.com / scottpeterman))

Part
of
the
SecureCartography
NG
network
automation
toolkit.