"""
SecureCartography v2 - Node Edit Dialog

Dialog for editing topology node properties.
Supports both discovered and undiscovered nodes.
"""

from typing import Optional, Dict, Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QTextEdit, QCheckBox,
    QPushButton, QFrame, QWidget
)
from PyQt6.QtGui import QFont

from sc2.ui.themes import ThemeColors, ThemeManager


class NodeEditDialog(QDialog):
    """
    Dialog for editing a topology node's properties.

    Editable fields:
    - Label (hostname)
    - IP Address
    - Platform
    - Discovered status
    - Notes/description

    Signals:
        node_updated(dict): Emitted with updated node data on save
    """

    node_updated = pyqtSignal(dict)

    def __init__(
            self,
            node_data: Dict[str, Any],
            theme_manager: Optional[ThemeManager] = None,
            parent: Optional[QWidget] = None
    ):
        super().__init__(parent)

        self._original_data = node_data.copy()
        self._node_id = node_data.get('id', '')
        self.theme_manager = theme_manager

        self.setWindowTitle(f"Edit Node: {node_data.get('label', node_data.get('id', 'Unknown'))}")
        self.setMinimumWidth(400)
        self.setModal(True)

        self._setup_ui(node_data)

        if theme_manager:
            self.apply_theme(theme_manager.theme)

    def _setup_ui(self, node_data: Dict[str, Any]):
        """Build the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header = QLabel(f"Editing: {node_data.get('label', node_data.get('id', 'Unknown'))}")
        header.setObjectName("dialogHeader")
        font = header.font()
        font.setPointSize(14)
        font.setWeight(QFont.Weight.Bold)
        header.setFont(font)
        layout.addWidget(header)

        # Form
        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Node ID (read-only)
        self._id_label = QLabel(self._node_id)
        self._id_label.setObjectName("readOnlyField")
        form_layout.addRow("Node ID:", self._id_label)

        # Label/Hostname
        self._label_edit = QLineEdit()
        self._label_edit.setObjectName("nodeEditField")
        self._label_edit.setText(node_data.get('label', ''))
        self._label_edit.setPlaceholderText("Device hostname")
        form_layout.addRow("Hostname:", self._label_edit)

        # IP Address
        self._ip_edit = QLineEdit()
        self._ip_edit.setObjectName("nodeEditField")
        self._ip_edit.setText(node_data.get('ip', ''))
        self._ip_edit.setPlaceholderText("e.g., 192.168.1.1")
        form_layout.addRow("IP Address:", self._ip_edit)

        # Platform
        self._platform_edit = QLineEdit()
        self._platform_edit.setObjectName("nodeEditField")
        self._platform_edit.setText(node_data.get('platform', ''))
        self._platform_edit.setPlaceholderText("e.g., Cisco C9300-48P")
        form_layout.addRow("Platform:", self._platform_edit)

        # Discovered checkbox
        self._discovered_check = QCheckBox("Device was discovered")
        self._discovered_check.setChecked(node_data.get('discovered', True))
        form_layout.addRow("Status:", self._discovered_check)

        # Notes
        self._notes_edit = QTextEdit()
        self._notes_edit.setObjectName("nodeNotesField")
        self._notes_edit.setPlaceholderText("Optional notes about this device...")
        self._notes_edit.setText(node_data.get('notes', ''))
        self._notes_edit.setMaximumHeight(80)
        form_layout.addRow("Notes:", self._notes_edit)

        layout.addLayout(form_layout)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("dialogSeparator")
        layout.addWidget(sep)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)

        button_layout.addStretch()

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setObjectName("secondaryButton")
        self._cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self._cancel_btn)

        self._save_btn = QPushButton("Save Changes")
        self._save_btn.setObjectName("primaryButton")
        self._save_btn.clicked.connect(self._on_save)
        self._save_btn.setDefault(True)
        button_layout.addWidget(self._save_btn)

        layout.addLayout(button_layout)

    def _on_save(self):
        """Save changes and emit signal."""
        updated_data = {
            'id': self._node_id,
            'label': self._label_edit.text().strip() or self._node_id,
            'ip': self._ip_edit.text().strip(),
            'platform': self._platform_edit.text().strip(),
            'discovered': self._discovered_check.isChecked(),
            'notes': self._notes_edit.toPlainText().strip(),
        }

        # Preserve any fields we didn't edit
        for key, value in self._original_data.items():
            if key not in updated_data:
                updated_data[key] = value

        self.node_updated.emit(updated_data)
        self.accept()

    def get_updated_data(self) -> Dict[str, Any]:
        """Get the current form data."""
        return {
            'id': self._node_id,
            'label': self._label_edit.text().strip() or self._node_id,
            'ip': self._ip_edit.text().strip(),
            'platform': self._platform_edit.text().strip(),
            'discovered': self._discovered_check.isChecked(),
            'notes': self._notes_edit.toPlainText().strip(),
        }

    def apply_theme(self, theme: ThemeColors):
        """Apply theme styling."""
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {theme.bg_secondary};
            }}

            QLabel#dialogHeader {{
                color: {theme.text_primary};
                background: transparent;
                border: none;
                padding-bottom: 8px;
            }}

            QLabel {{
                color: {theme.text_secondary};
                background: transparent;
            }}

            QLabel#readOnlyField {{
                color: {theme.text_muted};
                font-family: "JetBrains Mono", monospace;
            }}

            QLineEdit#nodeEditField {{
                background-color: {theme.bg_input};
                border: 1px solid {theme.border_dim};
                border-radius: 6px;
                padding: 8px 12px;
                color: {theme.text_primary};
            }}

            QLineEdit#nodeEditField:focus {{
                border-color: {theme.accent};
            }}

            QTextEdit#nodeNotesField {{
                background-color: {theme.bg_input};
                border: 1px solid {theme.border_dim};
                border-radius: 6px;
                padding: 8px;
                color: {theme.text_primary};
            }}

            QTextEdit#nodeNotesField:focus {{
                border-color: {theme.accent};
            }}

            QCheckBox {{
                color: {theme.text_primary};
                spacing: 8px;
            }}

            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {theme.border_secondary};
                border-radius: 4px;
                background-color: {theme.bg_input};
            }}

            QCheckBox::indicator:checked {{
                background-color: {theme.accent};
                border-color: {theme.accent};
            }}

            QFrame#dialogSeparator {{
                background-color: {theme.border_dim};
                max-height: 1px;
            }}

            QPushButton#primaryButton {{
                background-color: {theme.accent};
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                color: {theme.text_on_accent};
                font-weight: 600;
            }}

            QPushButton#primaryButton:hover {{
                background-color: {theme.accent_hover};
            }}

            QPushButton#secondaryButton {{
                background-color: transparent;
                border: 1px solid {theme.border_dim};
                border-radius: 6px;
                padding: 10px 20px;
                color: {theme.text_secondary};
            }}

            QPushButton#secondaryButton:hover {{
                border-color: {theme.border_hover};
                color: {theme.text_primary};
            }}
        """)