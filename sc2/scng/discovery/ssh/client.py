"""
SCNG SSH Client - Paramiko wrapper for network device SSH.

Path: scng/discovery/ssh/client.py

Adapted from VCollector's ssh_client.py with:
- scng.creds integration
- Legacy device support (old ciphers/KEX)
- ANSI sequence filtering
- Sophisticated prompt detection
- Pagination disabling

Invoke-shell only - no exec mode. This is required for most network devices.
"""

import os
import re
import time
import logging
from io import StringIO
from dataclasses import dataclass
from typing import Optional

import paramiko

logger = logging.getLogger(__name__)


def filter_ansi_sequences(text: str) -> str:
    """
    Remove ANSI escape sequences and control characters.

    Args:
        text: Input text with potential ANSI sequences.

    Returns:
        Cleaned text.
    """
    if not text:
        return text

    # Comprehensive pattern for ANSI sequences and control chars
    ansi_pattern = r'\x1b\[[0-9;?]*[a-zA-Z]|\x1b[()][AB012]|\x07|[\x00-\x08\x0B\x0C\x0E-\x1F]'
    return re.sub(ansi_pattern, '', text)


# Pagination disable commands - shotgun approach
# Fire all of these; wrong ones just error harmlessly
PAGINATION_DISABLE_SHOTGUN = [
    'terminal length 0',           # Cisco IOS/IOS-XE/NX-OS, Arista, Dell, Ubiquiti
    'terminal pager 0',            # Cisco ASA
    'set cli screen-length 0',     # Juniper Junos
    'screen-length 0 temporary',   # Huawei VRP
    'disable clipaging',           # Extreme EXOS
    'terminal more disable',       # Extreme VOSS
    'no page',                     # HP ProCurve
    'set cli pager off',           # Palo Alto
]


@dataclass
class SSHClientConfig:
    """SSH connection configuration."""
    host: str
    username: str
    password: Optional[str] = None
    key_content: Optional[str] = None  # PEM string (in-memory)
    key_file: Optional[str] = None     # Path to key file
    key_passphrase: Optional[str] = None
    port: int = 22
    timeout: int = 30
    shell_timeout: float = 5.0
    inter_command_time: float = 1.0
    expect_prompt_timeout: int = 3000  # ms
    prompt_count: int = 3
    legacy_mode: bool = False
    debug: bool = False

    def __post_init__(self):
        if not self.password and not self.key_content and not self.key_file:
            raise ValueError("Either password, key_content, or key_file required")


class LegacySSHSupport:
    """Configure Paramiko for legacy device compatibility."""

    @staticmethod
    def configure_legacy_algorithms():
        """Set algorithm preferences for legacy devices."""
        paramiko.Transport._preferred_kex = (
            "diffie-hellman-group1-sha1",
            "diffie-hellman-group14-sha1",
            "diffie-hellman-group-exchange-sha1",
            "diffie-hellman-group-exchange-sha256",
            "ecdh-sha2-nistp256",
            "ecdh-sha2-nistp384",
            "ecdh-sha2-nistp521",
            "curve25519-sha256",
            "curve25519-sha256@libssh.org",
            "diffie-hellman-group16-sha512",
            "diffie-hellman-group18-sha512"
        )

        paramiko.Transport._preferred_ciphers = (
            "aes128-cbc",
            "aes256-cbc",
            "3des-cbc",
            "aes192-cbc",
            "aes128-ctr",
            "aes192-ctr",
            "aes256-ctr",
            "aes256-gcm@openssh.com",
            "aes128-gcm@openssh.com",
            "chacha20-poly1305@openssh.com",
        )

        paramiko.Transport._preferred_keys = (
            "ssh-rsa",
            "ssh-dss",
            "ecdsa-sha2-nistp256",
            "ecdsa-sha2-nistp384",
            "ecdsa-sha2-nistp521",
            "ssh-ed25519",
            "rsa-sha2-256",
            "rsa-sha2-512"
        )


class SSHClient:
    """
    SSH client for network device interaction.

    Uses invoke_shell for interactive session - required for most
    network devices that don't support direct exec.

    Example:
        config = SSHClientConfig(
            host="192.168.1.1",
            username="admin",
            password="secret",
            legacy_mode=True,
        )
        client = SSHClient(config)
        client.connect()
        prompt = client.find_prompt()
        client.set_expect_prompt(prompt)
        output = client.execute_command("show version")
        client.disconnect()
    """

    def __init__(self, config: SSHClientConfig):
        self.config = config
        self._client: Optional[paramiko.SSHClient] = None
        self._shell: Optional[paramiko.Channel] = None
        self._output_buffer = StringIO()
        self._detected_prompt: Optional[str] = None
        self._expect_prompt: Optional[str] = None

    def connect(self) -> None:
        """Establish SSH connection and open shell."""
        logger.debug(f"Connecting to {self.config.host}:{self.config.port}")

        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Apply legacy algorithm support
        if self.config.legacy_mode:
            LegacySSHSupport.configure_legacy_algorithms()

        # Build connection params
        connect_params = {
            'hostname': self.config.host,
            'port': self.config.port,
            'username': self.config.username,
            'timeout': self.config.timeout,
            'allow_agent': False,
            'look_for_keys': False,
            'disabled_algorithms': {'pubkeys': ['rsa-sha2-512', 'rsa-sha2-256']}
        }

        # Add authentication
        if self.config.key_content or self.config.key_file:
            pkey = self._load_private_key()
            connect_params['pkey'] = pkey
            if self.config.password:
                connect_params['password'] = self.config.password
        else:
            connect_params['password'] = self.config.password

        # Connect with fallback for SHA2 RSA
        try:
            self._client.connect(**connect_params)
        except Exception:
            logger.debug("Retrying with SHA2 RSA algorithms enabled")
            connect_params.pop('disabled_algorithms', None)
            self._client.connect(**connect_params)

        logger.debug(f"Connected to {self.config.host}")

        # Open interactive shell
        self._create_shell()

    def _create_shell(self) -> None:
        """Create interactive shell stream."""
        logger.debug("Creating shell stream")

        self._shell = self._client.invoke_shell(
            term='xterm',
            width=200,
            height=24
        )
        self._shell.settimeout(self.config.timeout)

        # Wait for shell initialization
        time.sleep(2)

        # Read initial output
        self._drain_output()

    def _load_private_key(self) -> paramiko.PKey:
        """Load private key from PEM string or file."""
        passphrase = self.config.key_passphrase

        # Determine key source
        if self.config.key_content:
            key_source = StringIO(self.config.key_content)
            load_method = 'from_private_key'
            logger.debug("Loading key from memory")
        elif self.config.key_file:
            key_file = os.path.expanduser(self.config.key_file)
            if not os.path.exists(key_file):
                raise ValueError(f"Key file not found: {key_file}")
            key_source = key_file
            load_method = 'from_private_key_file'
            logger.debug(f"Loading key from file: {key_file}")
        else:
            raise ValueError("No key source provided")

        # Try each key type
        key_classes = [
            ('Ed25519', paramiko.Ed25519Key),
            ('RSA', paramiko.RSAKey),
            ('ECDSA', paramiko.ECDSAKey),
        ]

        for key_name, key_class in key_classes:
            try:
                loader = getattr(key_class, load_method)
                if load_method == 'from_private_key':
                    # Reset StringIO position for each attempt
                    if hasattr(key_source, 'seek'):
                        key_source.seek(0)
                    return loader(key_source, password=passphrase)
                else:
                    return loader(key_source, password=passphrase)
            except Exception as e:
                logger.debug(f"{key_name} key load failed: {e}")
                continue

        raise ValueError("Unable to load private key - unsupported format")

    def _recv_filtered(self, size: int = 4096) -> str:
        """Read from shell with ANSI filtering."""
        try:
            raw_data = self._shell.recv(size).decode('utf-8', errors='replace')
            return filter_ansi_sequences(raw_data)
        except Exception as e:
            logger.debug(f"Error reading from shell: {e}")
            return ""

    def _drain_output(self) -> str:
        """Read all available output from shell."""
        output = ""
        while self._shell.recv_ready():
            chunk = self._recv_filtered()
            output += chunk
            time.sleep(0.05)
        return output

    def find_prompt(self, attempt_count: int = 5, timeout: float = 5.0) -> str:
        """
        Auto-detect command prompt.

        Sends newlines and analyzes output to find prompt pattern.

        Args:
            attempt_count: Number of detection attempts.
            timeout: Timeout per attempt in seconds.

        Returns:
            Detected prompt string.
        """
        if not self._shell:
            raise RuntimeError("Shell not initialized")

        logger.debug("Attempting to auto-detect command prompt")

        # Clear any pending data
        self._drain_output()

        # Send newline to trigger prompt
        self._shell.send("\n")
        time.sleep(3)

        # Collect output
        buffer = ""
        start_time = time.time()
        while time.time() - start_time < 3:
            if self._shell.recv_ready():
                buffer += self._recv_filtered()
            else:
                time.sleep(0.1)

        # Try to extract prompt
        prompt = self._extract_prompt(buffer)
        if prompt:
            self._detected_prompt = prompt
            logger.debug(f"Detected prompt: {prompt!r}")
            return prompt

        # Additional attempts
        for i in range(attempt_count):
            logger.debug(f"Prompt detection attempt {i + 1}/{attempt_count}")

            self._shell.send("\n")
            buffer = ""

            start_time = time.time()
            while time.time() - start_time < timeout:
                if self._shell.recv_ready():
                    buffer += self._recv_filtered()
                else:
                    if buffer:
                        prompt = self._extract_prompt(buffer)
                        if prompt:
                            self._detected_prompt = prompt
                            logger.debug(f"Detected prompt: {prompt!r}")
                            return prompt
                    time.sleep(0.1)

            if buffer:
                prompt = self._extract_prompt(buffer)
                if prompt:
                    self._detected_prompt = prompt
                    logger.debug(f"Detected prompt: {prompt!r}")
                    return prompt

        # Fallback
        logger.warning("Could not detect prompt, using default '#'")
        self._detected_prompt = "#"
        return "#"

    def _extract_prompt(self, buffer: str) -> Optional[str]:
        """Extract prompt from buffer content."""
        if not buffer or not buffer.strip():
            return None

        # Get non-empty lines
        lines = [line.strip() for line in buffer.split('\n') if line.strip()]
        if not lines:
            return None

        # Prompt patterns - ordered by specificity
        patterns = [
            r'([A-Za-z0-9\-_.@()]+[#>$%])\s*$',  # Standard prompts
            r'([^\r\n]+[#>$%])\s*$',              # Anything ending with prompt char
        ]

        # Common prompt endings
        common_endings = ['#', '>', '$', '%', ':', ']', ')']

        # Check last lines for prompt
        for line in reversed(lines[-5:]):  # Check last 5 lines
            # Skip if line is too long (probably output, not prompt)
            if len(line) > 60:
                continue

            # Try regex patterns
            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    prompt = match.group(1).strip()
                    # Handle repeated prompts (e.g., "router# router# router#")
                    base = self._extract_base_prompt(prompt)
                    return base if base else prompt

            # Check for common endings
            if any(line.endswith(char) for char in common_endings) and len(line) < 40:
                return line

        return None

    def _extract_base_prompt(self, text: str) -> Optional[str]:
        """Extract base prompt from potentially repeated text."""
        # Check for repeated patterns
        for ending in ['#', '>', '$', '%']:
            if ending in text:
                parts = text.split(ending)
                if len(parts) > 2:
                    # Multiple occurrences - check if repeated
                    base = parts[0].strip() + ending
                    if len(base) < 40:
                        return base
        return None

    def extract_hostname_from_prompt(self, prompt: Optional[str] = None) -> Optional[str]:
        """
        Extract hostname from detected prompt.

        Handles common formats:
        - Cisco/Arista/Juniper: "hostname#" or "hostname>"
        - Linux: "user@hostname:~$" or "user@hostname $"
        - Juniper: "user@hostname>"

        Args:
            prompt: Prompt string (uses detected prompt if None).

        Returns:
            Extracted hostname or None.
        """
        prompt = prompt or self._detected_prompt
        if not prompt:
            return None

        # Linux style: user@hostname:path$ or user@hostname$
        match = re.match(r'^[^@]+@([A-Za-z0-9\-_.]+)', prompt)
        if match:
            return match.group(1)

        # Network device style: hostname# or hostname> or hostname(config)#
        # Strip config mode indicators first
        clean_prompt = re.sub(r'\([^)]+\)', '', prompt)
        match = re.match(r'^([A-Za-z0-9\-_.]+)[#>$%:\]]', clean_prompt)
        if match:
            return match.group(1)

        return None

    @property
    def hostname(self) -> Optional[str]:
        """Get hostname extracted from prompt."""
        return self.extract_hostname_from_prompt()

    def set_expect_prompt(self, prompt: str) -> None:
        """Set the prompt string to expect after commands."""
        self._expect_prompt = prompt
        logger.debug(f"Expect prompt set to: {prompt!r}")

    def disable_pagination(self) -> None:
        """
        Disable pagination by trying common commands.

        Fires multiple vendor commands - wrong ones just error harmlessly.
        """
        logger.debug("Disabling pagination (shotgun approach)")

        for cmd in PAGINATION_DISABLE_SHOTGUN:
            try:
                self._shell.send(cmd + '\n')
                time.sleep(0.3)
                self._drain_output()  # Discard response/errors
            except Exception as e:
                logger.debug(f"Pagination cmd failed (expected): {cmd} - {e}")

        # Small settle time
        time.sleep(0.5)
        self._drain_output()

    def execute_command(
        self,
        command: str,
        timeout: Optional[float] = None,
    ) -> str:
        """
        Execute command and return output.

        Args:
            command: Command string. Can be comma-separated for multiple commands.
            timeout: Override default timeout.

        Returns:
            Command output with ANSI sequences filtered.
        """
        if not self._shell:
            raise RuntimeError("Not connected")

        timeout = timeout or self.config.expect_prompt_timeout / 1000

        # Split comma-separated commands
        commands = [cmd.strip() for cmd in command.split(',') if cmd.strip()]

        output_buffer = StringIO()

        for cmd in commands:
            if cmd in ('\\n', '\n'):
                self._shell.send('\n')
                time.sleep(0.1)
                continue

            logger.debug(f"Sending: {cmd}")
            self._shell.send(cmd + '\n')

            # Wait for prompt
            cmd_output = self._wait_for_prompt(timeout)
            output_buffer.write(cmd_output)

            time.sleep(self.config.inter_command_time)

        return output_buffer.getvalue()

    def _wait_for_prompt(self, timeout: float) -> str:
        """Wait for prompt to appear in output."""
        prompt = self._expect_prompt or self._detected_prompt

        if not prompt:
            # No prompt detection - just wait and read
            time.sleep(self.config.shell_timeout)
            return self._drain_output()

        output = ""
        end_time = time.time() + timeout

        while time.time() < end_time:
            if self._shell.recv_ready():
                chunk = self._recv_filtered()
                output += chunk

                if prompt in output:
                    logger.debug("Prompt detected in output")
                    return output

            time.sleep(0.01)

        logger.warning(f"Timeout waiting for prompt after {timeout}s")
        return output

    def disconnect(self) -> None:
        """Close SSH connection."""
        if self._shell:
            try:
                self._shell.close()
            except Exception as e:
                logger.debug(f"Shell close error: {e}")
            self._shell = None

        if self._client:
            try:
                self._client.close()
            except Exception as e:
                logger.debug(f"Client close error: {e}")
            self._client = None

        logger.debug(f"Disconnected from {self.config.host}")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False