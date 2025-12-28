"""
SecureCartography v2 - Credentials Panel

Full credentials management panel with:
- Credential table with checkboxes
- Type badges (SSH, SNMPv2c, SNMPv3)
- Auth method indicators
- Add/Edit/Remove functionality
- Vault integration
"""

from typing import Optional, List, Dict, Any
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QAbstractItemView, QMenu, QMessageBox, QFrame
)

from ..themes import ThemeColors, ThemeManager
from .panel import Panel
from .credential_dialog import CredentialDialog


class TypeBadge(QLabel):
    """Small colored badge showing credential type."""

    TYPE_COLORS = {
        "ssh": ("#22c55e", "#166534"),      # Green
        "snmp_v2c": ("#3b82f6", "#1d4ed8"),  # Blue
        "snmp_v3": ("#8b5cf6", "#5b21b6"),   # Purple
    }

    TYPE_LABELS = {
        "ssh": "SSH",
        "snmp_v2c": "V2C",
        "snmp_v3": "V3",
    }

    def __init__(self, cred_type: str, parent=None):
        super().__init__(parent)
        self.cred_type = cred_type
        label = self.TYPE_LABELS.get(cred_type, cred_type.upper())
        self.setText(label)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedWidth(42)
        self.setFixedHeight(22)
        self._apply_style()

    def _apply_style(self):
        bg, _ = self.TYPE_COLORS.get(self.cred_type, ("#6b7280", "#374151"))
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {bg};
                color: white;
                border-radius: 4px;
                font-size: 10px;
                font-weight: 600;
                padding: 2px 6px;
            }}
        """)


class AuthBadge(QLabel):
    """Small badge showing auth method (password, key, community, etc.)."""

    def __init__(self, text: str, color: str = "#6b7280", parent=None):
        super().__init__(parent)
        self.setText(text)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {color}30;
                color: {color};
                border: 1px solid {color}50;
                border-radius: 3px;
                font-size: 9px;
                font-weight: 500;
                padding: 1px 4px;
            }}
        """)


class CredentialsPanel(Panel):
    """
    Full credentials management panel.

    Displays credentials in a table with:
    - Checkbox selection
    - Name column
    - Type badge (SSH/V2C/V3)
    - Username/identifier
    - Auth method badges
    - Default indicator

    Provides Add/Edit/Remove functionality connected to vault.

    Signals:
        credentials_changed: Emitted when credentials are modified
        selection_changed: Emitted when selection changes
    """

    credentials_changed = pyqtSignal()
    selection_changed = pyqtSignal(list)  # List of selected credential IDs

    def __init__(
        self,
        vault=None,  # CredentialVault instance
        theme_manager: Optional[ThemeManager] = None,
        parent: Optional[QWidget] = None
    ):
        self.vault = vault
        self._credentials = []  # Cache of CredentialInfo objects
        self._current_theme = None

        super().__init__(
            title="CREDENTIALS",
            icon="🔑",
            theme_manager=theme_manager,
            parent=parent,
            _defer_theme=True
        )
        self._setup_content()
        if theme_manager:
            self.apply_theme(theme_manager.theme)

        # Load credentials if vault is available
        if vault and vault.is_unlocked:
            self.refresh_credentials()

    def apply_theme(self, theme: ThemeColors):
        """Override to ensure content theme is applied on theme change."""
        super().apply_theme(theme)
        self._apply_content_theme(theme)

    def set_vault(self, vault):
        """Set or update the vault reference."""
        self.vault = vault
        if vault and vault.is_unlocked:
            self.refresh_credentials()

    def _setup_content(self):
        """Build the panel content."""
        # Header row with Add button and count
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        self.add_btn = QPushButton("+ Add")
        self.add_btn.setObjectName("addCredButton")
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.clicked.connect(self._on_add_clicked)
        header_row.addWidget(self.add_btn)

        header_row.addStretch()

        self.count_label = QLabel("0 credentials")
        self.count_label.setObjectName("credCount")
        header_row.addWidget(self.count_label)

        self.content_layout.addLayout(header_row)

        # Credentials table
        self.table = QTableWidget()
        self.table.setObjectName("credentialsTable")
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["", "Name", "Type", "User/ID", "Auth"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setMinimumHeight(180)

        # Enable horizontal scrolling
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

        # Column sizing - allow resize, set reasonable minimums
        header = self.table.horizontalHeader()
        header.setMinimumSectionSize(30)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)      # Checkbox
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)    # Name - stretch
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)      # Type badge
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)    # User - stretch
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Auth - fit content

        self.table.setColumnWidth(0, 32)   # Checkbox - compact
        self.table.setColumnWidth(2, 50)   # Type badge

        # Context menu
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.doubleClicked.connect(self._on_row_double_clicked)

        self.content_layout.addWidget(self.table)

        # Placeholder for empty state
        self.placeholder = QLabel(
            "No credentials configured.\n"
            "Click '+ Add' to add credentials."
        )
        self.placeholder.setObjectName("credPlaceholder")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setMinimumHeight(150)
        self.content_layout.addWidget(self.placeholder)

        # Initially show placeholder
        self._update_empty_state()

    def _update_empty_state(self):
        """Show/hide table vs placeholder based on credential count."""
        has_creds = len(self._credentials) > 0
        self.table.setVisible(has_creds)
        self.placeholder.setVisible(not has_creds)
        self.count_label.setText(f"{len(self._credentials)} credential{'s' if len(self._credentials) != 1 else ''}")

    def refresh_credentials(self):
        """Reload credentials from vault."""
        if not self.vault or not self.vault.is_unlocked:
            self._credentials = []
            self._populate_table()
            return

        try:
            self._credentials = self.vault.list_credentials()
            self._populate_table()
        except Exception as e:
            print(f"Error loading credentials: {e}")
            self._credentials = []
            self._populate_table()

    def _populate_table(self):
        """Populate table with credential data."""
        self.table.setRowCount(0)

        for cred in self._credentials:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setRowHeight(row, 36)

            # Checkbox cell
            check_widget = QWidget()
            check_widget.setAutoFillBackground(False)
            check_layout = QHBoxLayout(check_widget)
            check_layout.setContentsMargins(4, 0, 0, 0)
            check_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            checkbox = QCheckBox()
            checkbox.setObjectName("credCheckbox")
            checkbox.setProperty("credential_id", cred.id)
            check_layout.addWidget(checkbox)
            self.table.setCellWidget(row, 0, check_widget)

            # Name cell with default indicator
            name_widget = QWidget()
            name_widget.setAutoFillBackground(False)
            name_layout = QHBoxLayout(name_widget)
            name_layout.setContentsMargins(6, 0, 4, 0)
            name_layout.setSpacing(4)

            name_label = QLabel(cred.name)
            name_label.setObjectName("credName")
            name_layout.addWidget(name_label)

            if cred.is_default:
                default_badge = QLabel("★")
                default_badge.setObjectName("defaultBadge")
                default_badge.setToolTip("Default credential for this type")
                name_layout.addWidget(default_badge)

            name_layout.addStretch()
            self.table.setCellWidget(row, 1, name_widget)

            # Type badge
            type_widget = QWidget()
            type_widget.setAutoFillBackground(False)
            type_layout = QHBoxLayout(type_widget)
            type_layout.setContentsMargins(2, 0, 2, 0)
            type_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            type_badge = TypeBadge(cred.credential_type.value)
            type_layout.addWidget(type_badge)
            self.table.setCellWidget(row, 2, type_widget)

            # Username/ID cell
            user_widget = QWidget()
            user_widget.setAutoFillBackground(False)
            user_layout = QHBoxLayout(user_widget)
            user_layout.setContentsMargins(6, 0, 4, 0)
            user_text = cred.display_username or "-"
            user_label = QLabel(user_text)
            user_label.setObjectName("credUser")
            user_layout.addWidget(user_label)
            user_layout.addStretch()
            self.table.setCellWidget(row, 3, user_widget)

            # Auth badges cell
            auth_widget = QWidget()
            auth_widget.setAutoFillBackground(False)
            auth_layout = QHBoxLayout(auth_widget)
            auth_layout.setContentsMargins(4, 0, 4, 0)
            auth_layout.setSpacing(3)

            # Create badges based on credential type and capabilities
            if cred.credential_type.value == "ssh":
                if cred.has_password:
                    auth_layout.addWidget(AuthBadge("pwd", "#22c55e"))
                if cred.has_key:
                    auth_layout.addWidget(AuthBadge("key", "#3b82f6"))
            elif cred.credential_type.value == "snmp_v2c":
                auth_layout.addWidget(AuthBadge("comm", "#3b82f6"))
            elif cred.credential_type.value == "snmp_v3":
                if cred.has_auth:
                    auth_layout.addWidget(AuthBadge("auth", "#8b5cf6"))
                if cred.has_priv:
                    auth_layout.addWidget(AuthBadge("priv", "#ec4899"))
                if not cred.has_auth and not cred.has_priv:
                    auth_layout.addWidget(AuthBadge("noAuth", "#6b7280"))

            auth_layout.addStretch()
            self.table.setCellWidget(row, 4, auth_widget)

        self._update_empty_state()

    def _show_context_menu(self, position):
        """Show right-click context menu."""
        row = self.table.rowAt(position.y())
        if row < 0:
            return

        menu = QMenu(self)

        edit_action = menu.addAction("✏️ Edit")
        edit_action.triggered.connect(lambda: self._on_edit_credential(row))

        default_action = menu.addAction("⭐ Set as Default")
        default_action.triggered.connect(lambda: self._on_set_default(row))

        menu.addSeparator()

        delete_action = menu.addAction("🗑️ Delete")
        delete_action.triggered.connect(lambda: self._on_delete_credential(row))

        menu.exec(self.table.viewport().mapToGlobal(position))

    def _on_row_double_clicked(self, index):
        """Handle double-click on row to edit."""
        self._on_edit_credential(index.row())

    def _on_add_clicked(self):
        """Handle Add button click."""
        if not self.vault:
            QMessageBox.warning(
                self, "Vault Not Available",
                "Credential vault is not available. Please unlock the vault first."
            )
            return

        dialog = CredentialDialog(
            theme_manager=self.theme_manager,
            edit_mode=False,
            parent=self
        )
        dialog.credential_saved.connect(self._save_new_credential)
        dialog.exec()

    def _save_new_credential(self, cred_type: str, data: Dict[str, Any]):
        """Save a new credential to the vault."""
        if not self.vault or not self.vault.is_unlocked:
            QMessageBox.warning(self, "Error", "Vault is locked.")
            return

        try:
            if cred_type == "ssh":
                self.vault.add_ssh_credential(
                    name=data["name"],
                    username=data["username"],
                    password=data.get("password"),
                    key_content=data.get("key_content"),
                    key_passphrase=data.get("key_passphrase"),
                    port=data.get("port", 22),
                    timeout_seconds=data.get("timeout_seconds", 30),
                    description=data.get("description"),
                    priority=data.get("priority", 100),
                    is_default=data.get("is_default", False),
                )
            elif cred_type == "snmp_v2c":
                self.vault.add_snmpv2c_credential(
                    name=data["name"],
                    community=data["community"],
                    port=data.get("port", 161),
                    timeout_seconds=data.get("timeout_seconds", 5),
                    retries=data.get("retries", 2),
                    description=data.get("description"),
                    priority=data.get("priority", 100),
                    is_default=data.get("is_default", False),
                )
            elif cred_type == "snmp_v3":
                # Map protocol names
                from ...scng.creds.models import SNMPv3AuthProtocol, SNMPv3PrivProtocol

                auth_map = {
                    "none": SNMPv3AuthProtocol.NONE,
                    "md5": SNMPv3AuthProtocol.MD5,
                    "sha": SNMPv3AuthProtocol.SHA,
                    "sha224": SNMPv3AuthProtocol.SHA224,
                    "sha256": SNMPv3AuthProtocol.SHA256,
                    "sha384": SNMPv3AuthProtocol.SHA384,
                    "sha512": SNMPv3AuthProtocol.SHA512,
                }

                priv_map = {
                    "none": SNMPv3PrivProtocol.NONE,
                    "des": SNMPv3PrivProtocol.DES,
                    "aes": SNMPv3PrivProtocol.AES,
                    "aes192": SNMPv3PrivProtocol.AES192,
                    "aes256": SNMPv3PrivProtocol.AES256,
                }

                self.vault.add_snmpv3_credential(
                    name=data["name"],
                    username=data["username"],
                    auth_protocol=auth_map.get(data.get("auth_protocol", "none"), SNMPv3AuthProtocol.NONE),
                    auth_password=data.get("auth_password"),
                    priv_protocol=priv_map.get(data.get("priv_protocol", "none"), SNMPv3PrivProtocol.NONE),
                    priv_password=data.get("priv_password"),
                    port=data.get("port", 161),
                    timeout_seconds=data.get("timeout_seconds", 5),
                    retries=data.get("retries", 2),
                    description=data.get("description"),
                    priority=data.get("priority", 100),
                    is_default=data.get("is_default", False),
                )

            self.refresh_credentials()
            self.credentials_changed.emit()

        except Exception as e:
            QMessageBox.critical(
                self, "Error Saving Credential",
                f"Failed to save credential: {e}"
            )

    def _on_edit_credential(self, row: int):
        """Edit the credential at the given row."""
        if row < 0 or row >= len(self._credentials):
            return

        cred_info = self._credentials[row]

        if not self.vault or not self.vault.is_unlocked:
            QMessageBox.warning(self, "Error", "Vault is locked.")
            return

        # Get full credential data including secrets
        try:
            cred = self.vault.get_credential(credential_id=cred_info.id)
            if not cred:
                QMessageBox.warning(self, "Error", "Credential not found.")
                return

            # Build edit data dict
            edit_data = {
                "name": cred_info.name,
                "description": cred_info.description,
                "priority": cred_info.priority,
                "is_default": cred_info.is_default,
                "credential_type": cred_info.credential_type.value,
            }

            # Add type-specific fields
            if cred_info.credential_type.value == "ssh":
                edit_data.update({
                    "username": cred.username,
                    "password": cred.password or "",
                    "key_content": cred.key_content,
                    "key_passphrase": cred.key_passphrase or "",
                    "port": cred.port,
                    "timeout": cred.timeout_seconds,
                })
            elif cred_info.credential_type.value == "snmp_v2c":
                edit_data.update({
                    "community": cred.community,
                    "port": cred.port,
                    "timeout": cred.timeout_seconds,
                    "retries": cred.retries,
                })
            elif cred_info.credential_type.value == "snmp_v3":
                edit_data.update({
                    "username": cred.username,
                    "auth_protocol": cred.auth_protocol.value,
                    "auth_password": cred.auth_password or "",
                    "priv_protocol": cred.priv_protocol.value,
                    "priv_password": cred.priv_password or "",
                    "port": cred.port,
                    "timeout": cred.timeout_seconds,
                })

            dialog = CredentialDialog(
                theme_manager=self.theme_manager,
                edit_mode=True,
                edit_data=edit_data,
                parent=self
            )
            dialog.credential_saved.connect(
                lambda t, d: self._update_credential(cred_info.id, t, d)
            )
            dialog.exec()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load credential: {e}")

    def _update_credential(self, cred_id: int, cred_type: str, data: Dict[str, Any]):
        """Update an existing credential."""
        if not self.vault or not self.vault.is_unlocked:
            return

        try:
            # Remove old and add new (simpler than partial update)
            self.vault.remove_credential(credential_id=cred_id)
            self._save_new_credential(cred_type, data)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update credential: {e}")

    def _on_set_default(self, row: int):
        """Set credential as default for its type."""
        if row < 0 or row >= len(self._credentials):
            return

        cred_info = self._credentials[row]

        if not self.vault:
            return

        try:
            self.vault.set_default(credential_id=cred_info.id)
            self.refresh_credentials()
            self.credentials_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to set default: {e}")

    def _on_delete_credential(self, row: int):
        """Delete the credential at the given row."""
        if row < 0 or row >= len(self._credentials):
            return

        cred_info = self._credentials[row]

        reply = QMessageBox.question(
            self,
            "Delete Credential",
            f"Are you sure you want to delete '{cred_info.name}'?\n\n"
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.vault.remove_credential(credential_id=cred_info.id)
                self.refresh_credentials()
                self.credentials_changed.emit()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete: {e}")

    def get_selected_credential_ids(self) -> List[int]:
        """Get list of checked credential IDs."""
        selected = []
        for row in range(self.table.rowCount()):
            widget = self.table.cellWidget(row, 0)
            if widget:
                checkbox = widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    cred_id = checkbox.property("credential_id")
                    if cred_id:
                        selected.append(cred_id)
        return selected

    def _apply_content_theme(self, theme: ThemeColors):
        """Apply theme to panel content."""
        # Store theme for cell widget styling
        self._current_theme = theme

        # Add button
        self.add_btn.setStyleSheet(f"""
            QPushButton#addCredButton {{
                background-color: transparent;
                border: 1px solid {theme.accent};
                border-radius: 6px;
                padding: 8px 16px;
                color: {theme.accent};
                font-weight: 500;
            }}
            QPushButton#addCredButton:hover {{
                background-color: {theme.bg_hover};
            }}
        """)

        # Count label
        self.count_label.setStyleSheet(f"""
            QLabel#credCount {{
                color: {theme.text_muted};
                background: transparent;
                border: none;
            }}
        """)

        # Placeholder
        self.placeholder.setStyleSheet(f"""
            QLabel#credPlaceholder {{
                color: {theme.text_muted};
                background-color: {theme.bg_tertiary};
                border: 1px dashed {theme.border_dim};
                border-radius: 8px;
                padding: 20px;
            }}
        """)

        # Table styling - key fix: ensure cell widgets inherit background
        alt_row = theme.bg_hover if theme.is_dark else "#f8fafc"

        self.table.setStyleSheet(f"""
            QTableWidget#credentialsTable {{
                background-color: {theme.bg_secondary};
                alternate-background-color: {alt_row};
                border: 1px solid {theme.border_dim};
                border-radius: 8px;
                gridline-color: transparent;
                selection-background-color: {theme.accent}30;
            }}
            
            QTableWidget#credentialsTable::item {{
                padding: 4px 8px;
                border-bottom: 1px solid {theme.border_dim};
                color: {theme.text_primary};
                background-color: transparent;
            }}
            
            QTableWidget#credentialsTable::item:selected {{
                background-color: {theme.accent}30;
            }}
            
            QHeaderView::section {{
                background-color: {theme.bg_tertiary};
                color: {theme.text_secondary};
                border: none;
                border-bottom: 1px solid {theme.border_dim};
                padding: 6px 8px;
                font-weight: 600;
                font-size: 11px;
            }}
            
            /* Cell widget containers must be transparent */
            QTableWidget#credentialsTable QWidget {{
                background-color: transparent;
            }}
            
            QTableWidget#credentialsTable QLabel {{
                background-color: transparent;
                color: {theme.text_primary};
            }}
            
            QCheckBox#credCheckbox {{
                spacing: 0;
                background: transparent;
            }}
            
            QCheckBox#credCheckbox::indicator {{
                width: 16px;
                height: 16px;
                border: 2px solid {theme.border_dim};
                border-radius: 4px;
                background-color: {theme.bg_primary};
            }}
            
            QCheckBox#credCheckbox::indicator:checked {{
                background-color: {theme.accent};
                border-color: {theme.accent};
            }}
            
            QLabel#credName {{
                color: {theme.text_primary};
                background: transparent;
                font-weight: 500;
            }}
            
            QLabel#defaultBadge {{
                color: {theme.accent};
                background: transparent;
                font-size: 12px;
            }}
        """)

        # Re-populate table to apply new theme to cell widgets
        if self._credentials:
            self._populate_table()

        # Force visual refresh
        self.table.viewport().update()
        self.update()