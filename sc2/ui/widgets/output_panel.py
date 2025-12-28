"""
SecureCartography v2 - Output Panel Widget

Contains:
- Output directory picker
- Save debug information checkbox
"""

from typing import Optional
from pathlib import Path
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QFileDialog, QSizePolicy, QCheckBox
)
from PyQt6.QtGui import QFont

from ..themes import ThemeColors, ThemeManager
from .panel import Panel


class FormLabel(QLabel):
    """Styled form field label."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("formLabel")
        font = self.font()
        font.setPointSize(10)
        font.setWeight(QFont.Weight.Medium)
        self.setFont(font)


class OutputPanel(Panel):
    """
    Output configuration panel.

    Layout:
    ┌─ OUTPUT ─────────────────────────────────────┐
    │ OUTPUT DIRECTORY                             │
    │ ┌────────────────────────────────────┐ ┌──┐ │
    │ │ /home/user/maps                    │ │📁│ │
    │ └────────────────────────────────────┘ └──┘ │
    │                                              │
    │ ┌──────────────────────────────────────────┐ │
    │ │ [✓] Save debug information               │ │
    │ └──────────────────────────────────────────┘ │
    └──────────────────────────────────────────────┘

    Usage:
        panel = OutputPanel(theme_manager=tm)

        # Get values
        output_dir = panel.output_directory
        save_debug = panel.save_debug

        # Set values
        panel.set_output_directory("/home/user/maps")

        # Connect to changes
        panel.directory_changed.connect(on_dir_changed)
    """

    directory_changed = pyqtSignal(str)
    debug_changed = pyqtSignal(bool)

    def __init__(
        self,
        theme_manager: Optional[ThemeManager] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(
            title="OUTPUT",
            icon="📂",
            theme_manager=theme_manager,
            parent=parent,
            _defer_theme=True  # Apply theme after _setup_content
        )
        self._setup_content()
        if theme_manager:
            self.apply_theme(theme_manager.theme)

    def _setup_content(self):
        """Build the output panel content."""
        # Output directory section
        dir_label = FormLabel("OUTPUT DIRECTORY")
        self.content_layout.addWidget(dir_label)

        dir_row = QHBoxLayout()
        dir_row.setSpacing(8)

        self.directory_input = QLineEdit()
        self.directory_input.setObjectName("directoryInput")
        self.directory_input.setPlaceholderText("/home/user/maps")
        # Set default to user's home/network_maps
        default_dir = str(Path.home() / "network_maps")
        self.directory_input.setText(default_dir)
        self.directory_input.textChanged.connect(self.directory_changed.emit)
        dir_row.addWidget(self.directory_input, 1)

        self.browse_btn = QPushButton("📁")
        self.browse_btn.setObjectName("browseButton")
        self.browse_btn.setFixedSize(40, 40)
        self.browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse_btn.clicked.connect(self._browse_directory)
        dir_row.addWidget(self.browse_btn)

        self.content_layout.addLayout(dir_row)

        # Save debug checkbox
        self.content_layout.addSpacing(8)

        self.debug_frame = QFrame()
        self.debug_frame.setObjectName("debugFrame")
        debug_layout = QHBoxLayout(self.debug_frame)
        debug_layout.setContentsMargins(12, 10, 12, 10)
        debug_layout.setSpacing(12)

        self.debug_checkbox = QCheckBox()
        self.debug_checkbox.setObjectName("debugCheckbox")
        self.debug_checkbox.setChecked(True)
        self.debug_checkbox.stateChanged.connect(
            lambda state: self.debug_changed.emit(state == Qt.CheckState.Checked.value)
        )
        debug_layout.addWidget(self.debug_checkbox)

        debug_label = QLabel("Save debug information")
        debug_label.setObjectName("debugLabel")
        debug_label.setCursor(Qt.CursorShape.PointingHandCursor)
        debug_label.mousePressEvent = lambda e: self.debug_checkbox.toggle()
        debug_layout.addWidget(debug_label, 1)

        self.content_layout.addWidget(self.debug_frame)

    def _browse_directory(self):
        """Open directory picker dialog."""
        current = self.directory_input.text() or str(Path.home())

        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            current,
            QFileDialog.Option.ShowDirsOnly
        )

        if directory:
            self.directory_input.setText(directory)

    # === Properties ===

    @property
    def output_directory(self) -> str:
        """Get output directory path."""
        return self.directory_input.text().strip()

    @property
    def save_debug(self) -> bool:
        """Get save debug option."""
        return self.debug_checkbox.isChecked()

    # === Setters ===

    def set_output_directory(self, path: str):
        """Set output directory."""
        self.directory_input.setText(path)

    def set_save_debug(self, enabled: bool):
        """Set save debug option."""
        self.debug_checkbox.setChecked(enabled)

    def _apply_content_theme(self, theme: ThemeColors):
        """Apply theme to panel content."""
        # Labels
        label_style = f"""
            QLabel#formLabel {{
                color: {theme.text_secondary};
                text-transform: uppercase;
                letter-spacing: 0.5px;
                background: transparent;
                border: none;
                padding-bottom: 4px;
            }}
        """
        for label in self.findChildren(FormLabel):
            label.setStyleSheet(label_style)

        # Directory input
        self.directory_input.setStyleSheet(f"""
            QLineEdit#directoryInput {{
                background-color: {theme.bg_input};
                border: 1px solid {theme.border_dim};
                border-radius: 6px;
                padding: 10px 12px;
                color: {theme.text_primary};
                font-size: 13px;
            }}
            QLineEdit#directoryInput:focus {{
                border-color: {theme.accent};
            }}
            QLineEdit#directoryInput::placeholder {{
                color: {theme.text_muted};
            }}
        """)

        # Browse button
        self.browse_btn.setStyleSheet(f"""
            QPushButton#browseButton {{
                background-color: {theme.bg_tertiary};
                border: 1px solid {theme.border_dim};
                border-radius: 6px;
                color: {theme.text_primary};
                font-size: 16px;
            }}
            QPushButton#browseButton:hover {{
                border-color: {theme.accent};
                background-color: {theme.bg_hover};
            }}
            QPushButton#browseButton:pressed {{
                background-color: {theme.bg_selected};
            }}
        """)

        # Debug frame and checkbox
        self.debug_frame.setStyleSheet(f"""
            QFrame#debugFrame {{
                background-color: {theme.bg_tertiary};
                border: 1px solid {theme.border_dim};
                border-radius: 8px;
            }}
            
            QLabel#debugLabel {{
                color: {theme.text_primary};
                font-size: 13px;
                background: transparent;
                border: none;
            }}
            
            QCheckBox#debugCheckbox {{
                background: transparent;
            }}
            
            QCheckBox#debugCheckbox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {theme.border_dim};
                border-radius: 4px;
                background-color: transparent;
            }}
            
            QCheckBox#debugCheckbox::indicator:checked {{
                background-color: {theme.accent};
                border-color: {theme.accent};
            }}
            
            QCheckBox#debugCheckbox::indicator:hover {{
                border-color: {theme.accent};
            }}
        """)

    def apply_theme(self, theme: ThemeColors):
        """Apply theme to entire panel."""
        super().apply_theme(theme)
        self._apply_content_theme(theme)

    def set_theme(self, theme_manager: ThemeManager):
        """Update theme manager and apply."""
        super().set_theme(theme_manager)
        self._apply_content_theme(theme_manager.theme)