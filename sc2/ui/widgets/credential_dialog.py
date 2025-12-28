"""
SecureCartography v2 - Credential Dialog

Modal dialog for adding/editing credentials.
Supports SSH, SNMPv2c, and SNMPv3 credential types with appropriate forms.
"""

from typing import Optional, Dict, Any
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QWidget, QTabWidget, QFormLayout,
    QComboBox, QSpinBox, QTextEdit, QFileDialog, QMessageBox,
    QCheckBox, QGroupBox
)

from ..themes import ThemeColors, ThemeManager, ThemeName


class CredentialDialog(QDialog):
    """
    Dialog for adding or editing credentials.

    Provides tabbed interface for:
    - SSH credentials (username, password, key)
    - SNMPv2c credentials (community string)
    - SNMPv3 credentials (user, auth, priv)

    Signals:
        credential_saved: Emitted when credential is saved with (type, data) tuple
    """

    credential_saved = pyqtSignal(str, dict)  # (credential_type, data_dict)

    def __init__(
            self,
            theme_manager: ThemeManager,
            edit_mode: bool = False,
            edit_data: Optional[Dict[str, Any]] = None,
            parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.edit_mode = edit_mode
        self.edit_data = edit_data or {}

        self.setWindowTitle("Edit Credential" if edit_mode else "Add Credential")
        self.setMinimumSize(520, 640)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowCloseButtonHint
        )

        self._setup_ui()
        self._apply_theme()

        if edit_mode and edit_data:
            self._populate_form(edit_data)

    def _setup_ui(self):
        """Build the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Header
        header = QLabel("Edit Credential" if self.edit_mode else "Add New Credential")
        header.setObjectName("dialogHeader")
        font = header.font()
        font.setPointSize(14)
        font.setBold(True)
        header.setFont(font)
        layout.addWidget(header)

        # Common fields section
        common_group = QGroupBox("General")
        common_group.setObjectName("credentialGroup")
        common_layout = QFormLayout(common_group)
        common_layout.setSpacing(12)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., lab-switches, prod-routers")
        self.name_input.setObjectName("credInput")
        if self.edit_mode:
            self.name_input.setEnabled(False)  # Can't change name on edit
        common_layout.addRow("Name:", self.name_input)

        self.description_input = QLineEdit()
        self.description_input.setPlaceholderText("Optional description")
        self.description_input.setObjectName("credInput")
        common_layout.addRow("Description:", self.description_input)

        self.priority_input = QSpinBox()
        self.priority_input.setRange(1, 999)
        self.priority_input.setValue(100)
        self.priority_input.setObjectName("credInput")
        common_layout.addRow("Priority:", self.priority_input)

        self.default_check = QCheckBox("Set as default for this type")
        self.default_check.setObjectName("credCheck")
        common_layout.addRow("", self.default_check)

        layout.addWidget(common_group)

        # Credential type tabs
        self.tabs = QTabWidget()
        self.tabs.setObjectName("credentialTabs")

        # SSH Tab
        ssh_widget = QWidget()
        ssh_layout = QFormLayout(ssh_widget)
        ssh_layout.setSpacing(12)
        ssh_layout.setContentsMargins(16, 16, 16, 16)

        self.ssh_username = QLineEdit()
        self.ssh_username.setPlaceholderText("admin")
        self.ssh_username.setObjectName("credInput")
        ssh_layout.addRow("Username:", self.ssh_username)

        self.ssh_password = QLineEdit()
        self.ssh_password.setPlaceholderText("Leave empty if using key only")
        self.ssh_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.ssh_password.setObjectName("credInput")
        ssh_layout.addRow("Password:", self.ssh_password)

        # SSH Key section
        key_row = QHBoxLayout()
        self.ssh_key_path = QLineEdit()
        self.ssh_key_path.setPlaceholderText("Path to private key file")
        self.ssh_key_path.setObjectName("credInput")
        key_row.addWidget(self.ssh_key_path)

        self.ssh_key_browse = QPushButton("Browse...")
        self.ssh_key_browse.setObjectName("browseButton")
        self.ssh_key_browse.clicked.connect(self._browse_key_file)
        key_row.addWidget(self.ssh_key_browse)
        ssh_layout.addRow("Key File:", key_row)

        self.ssh_key_passphrase = QLineEdit()
        self.ssh_key_passphrase.setPlaceholderText("If key is encrypted")
        self.ssh_key_passphrase.setEchoMode(QLineEdit.EchoMode.Password)
        self.ssh_key_passphrase.setObjectName("credInput")
        ssh_layout.addRow("Key Passphrase:", self.ssh_key_passphrase)

        self.ssh_port = QSpinBox()
        self.ssh_port.setRange(1, 65535)
        self.ssh_port.setValue(22)
        self.ssh_port.setObjectName("credInput")
        ssh_layout.addRow("Port:", self.ssh_port)

        self.ssh_timeout = QSpinBox()
        self.ssh_timeout.setRange(5, 120)
        self.ssh_timeout.setValue(30)
        self.ssh_timeout.setSuffix(" sec")
        self.ssh_timeout.setObjectName("credInput")
        ssh_layout.addRow("Timeout:", self.ssh_timeout)

        self.tabs.addTab(ssh_widget, "🔐 SSH")

        # SNMPv2c Tab
        snmpv2_widget = QWidget()
        snmpv2_layout = QFormLayout(snmpv2_widget)
        snmpv2_layout.setSpacing(12)
        snmpv2_layout.setContentsMargins(16, 16, 16, 16)

        self.snmpv2_community = QLineEdit()
        self.snmpv2_community.setPlaceholderText("public")
        self.snmpv2_community.setEchoMode(QLineEdit.EchoMode.Password)
        self.snmpv2_community.setObjectName("credInput")
        snmpv2_layout.addRow("Community:", self.snmpv2_community)

        # Show/hide toggle for community
        self.snmpv2_show = QCheckBox("Show community string")
        self.snmpv2_show.toggled.connect(
            lambda checked: self.snmpv2_community.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        snmpv2_layout.addRow("", self.snmpv2_show)

        self.snmpv2_port = QSpinBox()
        self.snmpv2_port.setRange(1, 65535)
        self.snmpv2_port.setValue(161)
        self.snmpv2_port.setObjectName("credInput")
        snmpv2_layout.addRow("Port:", self.snmpv2_port)

        self.snmpv2_timeout = QSpinBox()
        self.snmpv2_timeout.setRange(1, 30)
        self.snmpv2_timeout.setValue(5)
        self.snmpv2_timeout.setSuffix(" sec")
        self.snmpv2_timeout.setObjectName("credInput")
        snmpv2_layout.addRow("Timeout:", self.snmpv2_timeout)

        self.snmpv2_retries = QSpinBox()
        self.snmpv2_retries.setRange(0, 5)
        self.snmpv2_retries.setValue(2)
        self.snmpv2_retries.setObjectName("credInput")
        snmpv2_layout.addRow("Retries:", self.snmpv2_retries)

        self.tabs.addTab(snmpv2_widget, "📡 SNMPv2c")

        # SNMPv3 Tab
        snmpv3_widget = QWidget()
        snmpv3_layout = QFormLayout(snmpv3_widget)
        snmpv3_layout.setSpacing(12)
        snmpv3_layout.setContentsMargins(16, 16, 16, 16)

        self.snmpv3_username = QLineEdit()
        self.snmpv3_username.setPlaceholderText("snmpuser")
        self.snmpv3_username.setObjectName("credInput")
        snmpv3_layout.addRow("Username:", self.snmpv3_username)

        # Auth section
        auth_group = QGroupBox("Authentication")
        auth_group.setObjectName("subGroup")
        auth_layout = QFormLayout(auth_group)

        self.snmpv3_auth_protocol = QComboBox()
        self.snmpv3_auth_protocol.setObjectName("credCombo")
        self.snmpv3_auth_protocol.addItems([
            "None", "MD5", "SHA", "SHA-224", "SHA-256", "SHA-384", "SHA-512"
        ])
        self.snmpv3_auth_protocol.currentIndexChanged.connect(self._update_snmpv3_state)
        auth_layout.addRow("Protocol:", self.snmpv3_auth_protocol)

        self.snmpv3_auth_password = QLineEdit()
        self.snmpv3_auth_password.setPlaceholderText("Authentication password")
        self.snmpv3_auth_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.snmpv3_auth_password.setObjectName("credInput")
        auth_layout.addRow("Password:", self.snmpv3_auth_password)

        snmpv3_layout.addRow(auth_group)

        # Privacy section
        priv_group = QGroupBox("Privacy (Encryption)")
        priv_group.setObjectName("subGroup")
        priv_layout = QFormLayout(priv_group)

        self.snmpv3_priv_protocol = QComboBox()
        self.snmpv3_priv_protocol.setObjectName("credCombo")
        self.snmpv3_priv_protocol.addItems([
            "None", "DES", "AES-128", "AES-192", "AES-256"
        ])
        self.snmpv3_priv_protocol.currentIndexChanged.connect(self._update_snmpv3_state)
        priv_layout.addRow("Protocol:", self.snmpv3_priv_protocol)

        self.snmpv3_priv_password = QLineEdit()
        self.snmpv3_priv_password.setPlaceholderText("Privacy password")
        self.snmpv3_priv_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.snmpv3_priv_password.setObjectName("credInput")
        priv_layout.addRow("Password:", self.snmpv3_priv_password)

        snmpv3_layout.addRow(priv_group)

        self.snmpv3_port = QSpinBox()
        self.snmpv3_port.setRange(1, 65535)
        self.snmpv3_port.setValue(161)
        self.snmpv3_port.setObjectName("credInput")
        snmpv3_layout.addRow("Port:", self.snmpv3_port)

        self.snmpv3_timeout = QSpinBox()
        self.snmpv3_timeout.setRange(1, 30)
        self.snmpv3_timeout.setValue(5)
        self.snmpv3_timeout.setSuffix(" sec")
        self.snmpv3_timeout.setObjectName("credInput")
        snmpv3_layout.addRow("Timeout:", self.snmpv3_timeout)

        self.tabs.addTab(snmpv3_widget, "🔒 SNMPv3")

        layout.addWidget(self.tabs)

        # Button row
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("cancelButton")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        button_layout.addStretch()

        self.save_btn = QPushButton("💾 Save Credential")
        self.save_btn.setObjectName("saveButton")
        self.save_btn.clicked.connect(self._on_save)
        button_layout.addWidget(self.save_btn)

        layout.addLayout(button_layout)

        # Initial state update
        self._update_snmpv3_state()

    def _update_snmpv3_state(self):
        """Update SNMPv3 field states based on protocol selections."""
        auth_enabled = self.snmpv3_auth_protocol.currentIndex() > 0
        priv_enabled = self.snmpv3_priv_protocol.currentIndex() > 0

        self.snmpv3_auth_password.setEnabled(auth_enabled)
        self.snmpv3_priv_password.setEnabled(priv_enabled)

        # Privacy requires authentication
        if priv_enabled and not auth_enabled:
            self.snmpv3_auth_protocol.setCurrentIndex(2)  # SHA

    def _browse_key_file(self):
        """Open file dialog for SSH key selection."""
        home = str(Path.home())
        ssh_dir = str(Path.home() / ".ssh")
        start_dir = ssh_dir if Path(ssh_dir).exists() else home

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select SSH Private Key",
            start_dir,
            "All Files (*)"
        )

        if file_path:
            self.ssh_key_path.setText(file_path)

    def _populate_form(self, data: Dict[str, Any]):
        """Populate form fields from existing credential data."""
        # Common fields
        self.name_input.setText(data.get("name", ""))
        self.description_input.setText(data.get("description", ""))
        self.priority_input.setValue(data.get("priority", 100))
        self.default_check.setChecked(data.get("is_default", False))

        cred_type = data.get("credential_type", "ssh")

        if cred_type == "ssh":
            self.tabs.setCurrentIndex(0)
            self.ssh_username.setText(data.get("username", ""))
            self.ssh_password.setText(data.get("password", ""))
            self.ssh_key_path.setText(data.get("key_path", ""))
            self.ssh_key_passphrase.setText(data.get("key_passphrase", ""))
            self.ssh_port.setValue(data.get("port", 22))
            self.ssh_timeout.setValue(data.get("timeout", 30))

        elif cred_type == "snmp_v2c":
            self.tabs.setCurrentIndex(1)
            self.snmpv2_community.setText(data.get("community", ""))
            self.snmpv2_port.setValue(data.get("port", 161))
            self.snmpv2_timeout.setValue(data.get("timeout", 5))
            self.snmpv2_retries.setValue(data.get("retries", 2))

        elif cred_type == "snmp_v3":
            self.tabs.setCurrentIndex(2)
            self.snmpv3_username.setText(data.get("username", ""))

            # Auth protocol
            auth_map = {"none": 0, "md5": 1, "sha": 2, "sha224": 3, "sha256": 4, "sha384": 5, "sha512": 6}
            auth_proto = data.get("auth_protocol", "none").lower()
            self.snmpv3_auth_protocol.setCurrentIndex(auth_map.get(auth_proto, 0))
            self.snmpv3_auth_password.setText(data.get("auth_password", ""))

            # Priv protocol
            priv_map = {"none": 0, "des": 1, "aes": 2, "aes192": 3, "aes256": 4}
            priv_proto = data.get("priv_protocol", "none").lower()
            self.snmpv3_priv_protocol.setCurrentIndex(priv_map.get(priv_proto, 0))
            self.snmpv3_priv_password.setText(data.get("priv_password", ""))

            self.snmpv3_port.setValue(data.get("port", 161))
            self.snmpv3_timeout.setValue(data.get("timeout", 5))

    def _validate_and_collect(self) -> Optional[tuple]:
        """
        Validate form and collect data.

        Returns:
            Tuple of (credential_type, data_dict) or None if validation fails.
        """
        # Common validation
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation Error", "Credential name is required.")
            self.name_input.setFocus()
            return None

        # Check for invalid characters in name
        if not name.replace("-", "").replace("_", "").replace(".", "").isalnum():
            QMessageBox.warning(
                self, "Validation Error",
                "Name can only contain letters, numbers, hyphens, underscores, and dots."
            )
            self.name_input.setFocus()
            return None

        common_data = {
            "name": name,
            "description": self.description_input.text().strip() or None,
            "priority": self.priority_input.value(),
            "is_default": self.default_check.isChecked(),
        }

        tab_index = self.tabs.currentIndex()

        if tab_index == 0:  # SSH
            username = self.ssh_username.text().strip()
            password = self.ssh_password.text()
            key_path = self.ssh_key_path.text().strip()

            if not username:
                QMessageBox.warning(self, "Validation Error", "SSH username is required.")
                self.ssh_username.setFocus()
                return None

            if not password and not key_path:
                QMessageBox.warning(
                    self, "Validation Error",
                    "SSH requires either a password or key file."
                )
                return None

            # Load key content if path provided
            key_content = None
            if key_path:
                try:
                    with open(key_path, 'r') as f:
                        key_content = f.read()
                except Exception as e:
                    QMessageBox.warning(
                        self, "Key File Error",
                        f"Could not read key file: {e}"
                    )
                    return None

            return ("ssh", {
                **common_data,
                "username": username,
                "password": password or None,
                "key_content": key_content,
                "key_passphrase": self.ssh_key_passphrase.text() or None,
                "port": self.ssh_port.value(),
                "timeout_seconds": self.ssh_timeout.value(),
            })

        elif tab_index == 1:  # SNMPv2c
            community = self.snmpv2_community.text()

            if not community:
                QMessageBox.warning(self, "Validation Error", "Community string is required.")
                self.snmpv2_community.setFocus()
                return None

            return ("snmp_v2c", {
                **common_data,
                "community": community,
                "port": self.snmpv2_port.value(),
                "timeout_seconds": self.snmpv2_timeout.value(),
                "retries": self.snmpv2_retries.value(),
            })

        elif tab_index == 2:  # SNMPv3
            username = self.snmpv3_username.text().strip()

            if not username:
                QMessageBox.warning(self, "Validation Error", "SNMPv3 username is required.")
                self.snmpv3_username.setFocus()
                return None

            # Map protocol selections
            auth_protocols = ["none", "md5", "sha", "sha224", "sha256", "sha384", "sha512"]
            priv_protocols = ["none", "des", "aes", "aes192", "aes256"]

            auth_proto = auth_protocols[self.snmpv3_auth_protocol.currentIndex()]
            priv_proto = priv_protocols[self.snmpv3_priv_protocol.currentIndex()]

            auth_password = self.snmpv3_auth_password.text()
            priv_password = self.snmpv3_priv_password.text()

            # Validate auth/priv requirements
            if auth_proto != "none" and not auth_password:
                QMessageBox.warning(
                    self, "Validation Error",
                    "Authentication password required when auth protocol is set."
                )
                self.snmpv3_auth_password.setFocus()
                return None

            if priv_proto != "none" and not priv_password:
                QMessageBox.warning(
                    self, "Validation Error",
                    "Privacy password required when privacy protocol is set."
                )
                self.snmpv3_priv_password.setFocus()
                return None

            if priv_proto != "none" and auth_proto == "none":
                QMessageBox.warning(
                    self, "Validation Error",
                    "Privacy requires authentication to be enabled."
                )
                return None

            return ("snmp_v3", {
                **common_data,
                "username": username,
                "auth_protocol": auth_proto,
                "auth_password": auth_password or None,
                "priv_protocol": priv_proto,
                "priv_password": priv_password or None,
                "port": self.snmpv3_port.value(),
                "timeout_seconds": self.snmpv3_timeout.value(),
                "retries": 2,  # Default
            })

        return None

    def _on_save(self):
        """Handle save button click."""
        result = self._validate_and_collect()
        if result:
            cred_type, data = result
            self.credential_saved.emit(cred_type, data)
            self.accept()

    def _apply_theme(self):
        """Apply theme colors to dialog."""
        theme = self.theme_manager.theme

        # Compute colors
        if theme.name == "Cyber":
            bg_input = "#0a1a1a"
            border_input = "#1a3a3a"
            bg_group = "#0d1117"
        elif theme.name == "Dark":
            bg_input = "#1a1508"
            border_input = "#2a2510"
            bg_group = "#0d0d0d"
        else:  # Light
            bg_input = "#ffffff"
            border_input = "#d0d0d0"
            bg_group = "#f8f8f8"

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {theme.bg_primary};
            }}

            QLabel#dialogHeader {{
                color: {theme.text_primary};
                background: transparent;
            }}

            QGroupBox {{
                color: {theme.text_secondary};
                background-color: {bg_group};
                border: 1px solid {theme.border_dim};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 8px;
                font-weight: 500;
            }}

            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
            }}

            QGroupBox#subGroup {{
                background-color: transparent;
                border: 1px solid {border_input};
            }}

            QLabel {{
                color: {theme.text_secondary};
                background: transparent;
            }}

            QLineEdit#credInput {{
                background-color: {bg_input};
                border: 1px solid {border_input};
                border-radius: 6px;
                padding: 8px 12px;
                color: {theme.text_primary};
            }}

            QLineEdit#credInput:focus {{
                border-color: {theme.accent};
            }}

            QLineEdit#credInput:disabled {{
                background-color: {theme.bg_tertiary};
                color: {theme.text_muted};
            }}

            QSpinBox#credInput {{
                background-color: {bg_input};
                border: 1px solid {border_input};
                border-radius: 6px;
                padding: 8px 12px;
                color: {theme.text_primary};
            }}

            QSpinBox#credInput:focus {{
                border-color: {theme.accent};
            }}

            QComboBox#credCombo {{
                background-color: {bg_input};
                border: 1px solid {border_input};
                border-radius: 6px;
                padding: 8px 12px;
                color: {theme.text_primary};
            }}

            QComboBox#credCombo:focus {{
                border-color: {theme.accent};
            }}

            QComboBox#credCombo::drop-down {{
                border: none;
                width: 24px;
            }}

            QComboBox#credCombo QAbstractItemView {{
                background-color: {theme.bg_secondary};
                border: 1px solid {border_input};
                selection-background-color: {theme.accent};
                selection-color: {theme.bg_primary};
            }}

            QCheckBox#credCheck {{
                color: {theme.text_secondary};
                spacing: 8px;
            }}

            QCheckBox#credCheck::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {border_input};
                border-radius: 4px;
                background-color: {bg_input};
            }}

            QCheckBox#credCheck::indicator:checked {{
                background-color: {theme.accent};
                border-color: {theme.accent};
            }}

            QTabWidget#credentialTabs::pane {{
                background-color: {bg_group};
                border: 1px solid {theme.border_dim};
                border-radius: 8px;
                border-top-left-radius: 0;
            }}

            QTabBar::tab {{
                background-color: {theme.bg_tertiary};
                color: {theme.text_secondary};
                border: 1px solid {theme.border_dim};
                border-bottom: none;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }}

            QTabBar::tab:selected {{
                background-color: {bg_group};
                color: {theme.accent};
                border-bottom: 2px solid {theme.accent};
            }}

            QTabBar::tab:hover:!selected {{
                background-color: {theme.bg_hover};
            }}

            QPushButton#browseButton {{
                background-color: {theme.bg_tertiary};
                border: 1px solid {border_input};
                border-radius: 6px;
                padding: 8px 16px;
                color: {theme.text_secondary};
            }}

            QPushButton#browseButton:hover {{
                border-color: {theme.accent};
                color: {theme.accent};
            }}

            QPushButton#cancelButton {{
                background-color: transparent;
                border: 1px solid {theme.border_dim};
                border-radius: 6px;
                padding: 12px 24px;
                color: {theme.text_secondary};
            }}

            QPushButton#cancelButton:hover {{
                border-color: {theme.text_secondary};
            }}

            QPushButton#saveButton {{
                background-color: {theme.accent};
                border: none;
                border-radius: 6px;
                padding: 12px 24px;
                color: {theme.bg_primary};
                font-weight: 600;
            }}

            QPushButton#saveButton:hover {{
                background-color: {theme.accent_dim};
            }}
        """)

    def apply_theme(self, theme: ThemeColors):
        """Public method to update theme."""
        self._apply_theme()