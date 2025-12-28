"""
SecureCartography v2 - Toggle Switch Widget

Styled toggle switch for boolean options like:
- No DNS Mode
- Verbose Output
"""

from typing import Optional
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect
from PyQt6.QtWidgets import (
    QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel,
    QSizePolicy
)
from PyQt6.QtGui import QPainter, QColor, QPainterPath

from ..themes import ThemeColors, ThemeManager


class ToggleSwitch(QWidget):
    """
    Animated toggle switch widget.

    Features:
    - Smooth sliding animation
    - Theme-aware colors
    - Click to toggle

    Usage:
        toggle = ToggleSwitch(theme_manager=tm)
        toggle.toggled.connect(on_toggle)

        # Check/set state
        if toggle.isChecked():
            ...
        toggle.setChecked(True)
    """

    toggled = pyqtSignal(bool)

    def __init__(
            self,
            checked: bool = False,
            theme_manager: Optional[ThemeManager] = None,
            parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self._checked = checked
        self.theme_manager = theme_manager

        # Colors (will be set by theme)
        self._bg_off = "#2a2a2a"
        self._bg_on = "#00ffff"
        self._handle_color = "#ffffff"
        self._border_color = "#3a3a3a"

        # Dimensions
        self._width = 44
        self._height = 24
        self._handle_margin = 2
        self._handle_size = self._height - (self._handle_margin * 2)

        # Animation
        self._handle_position = self._handle_margin if not checked else (
                self._width - self._handle_size - self._handle_margin
        )

        self.setFixedSize(self._width, self._height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        if theme_manager:
            self.apply_theme(theme_manager.theme)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool, animated: bool = True):
        """Set the toggle state."""
        if checked == self._checked:
            return

        self._checked = checked

        target = (
            self._width - self._handle_size - self._handle_margin
            if checked else self._handle_margin
        )

        if animated:
            self._animate_handle(target)
        else:
            self._handle_position = target
            self.update()

        self.toggled.emit(checked)

    def toggle(self):
        """Toggle the current state."""
        self.setChecked(not self._checked)

    def _animate_handle(self, target: float):
        """Animate handle to target position."""
        # Simple animation using timer
        from PyQt6.QtCore import QTimer

        start = self._handle_position
        steps = 10
        step_size = (target - start) / steps
        current_step = [0]  # Mutable for closure

        def step():
            current_step[0] += 1
            if current_step[0] >= steps:
                self._handle_position = target
                timer.stop()
            else:
                self._handle_position = start + (step_size * current_step[0])
            self.update()

        timer = QTimer(self)
        timer.timeout.connect(step)
        timer.start(15)  # ~60fps

    def paintEvent(self, event):
        """Custom paint for toggle switch."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background track
        bg_color = QColor(self._bg_on if self._checked else self._bg_off)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg_color)

        # Rounded rectangle for track
        track_rect = self.rect()
        painter.drawRoundedRect(
            track_rect,
            self._height / 2,
            self._height / 2
        )

        # Handle (circle)
        painter.setBrush(QColor(self._handle_color))
        handle_x = int(self._handle_position)
        handle_y = self._handle_margin
        painter.drawEllipse(
            handle_x,
            handle_y,
            self._handle_size,
            self._handle_size
        )

        painter.end()

    def mousePressEvent(self, event):
        """Handle click to toggle."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle()

    def apply_theme(self, theme: ThemeColors):
        """Apply theme colors."""
        self._bg_off = theme.bg_tertiary
        self._bg_on = theme.accent
        self._handle_color = theme.text_on_accent if theme.is_dark else "#ffffff"
        self._border_color = theme.border_dim
        self.update()

    def set_theme(self, theme_manager: ThemeManager):
        """Update theme manager and apply."""
        self.theme_manager = theme_manager
        self.apply_theme(theme_manager.theme)


class ToggleOption(QFrame):
    """
    Toggle switch with label and description.

    Matches the mockup's toggle option rows:
    ┌─────────────────────────────────────────────┐
    │ No DNS Mode                          [═══○] │
    │ Use IPs from LLDP/CDP only (home lab)       │
    └─────────────────────────────────────────────┘

    Usage:
        option = ToggleOption(
            label="No DNS Mode",
            description="Use IPs from LLDP/CDP only (home lab)",
            theme_manager=tm
        )
        option.toggled.connect(on_toggle)
    """

    toggled = pyqtSignal(bool)

    def __init__(
            self,
            label: str,
            description: str = "",
            checked: bool = False,
            theme_manager: Optional[ThemeManager] = None,
            parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.label_text = label
        self.description_text = description
        self.theme_manager = theme_manager

        self._setup_ui(checked)
        if theme_manager:
            self.apply_theme(theme_manager.theme)

    def _setup_ui(self, checked: bool):
        """Build the option UI."""
        self.setObjectName("toggleOption")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        # Text column
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        self.label = QLabel(self.label_text)
        self.label.setObjectName("toggleLabel")
        text_layout.addWidget(self.label)

        if self.description_text:
            self.description = QLabel(self.description_text)
            self.description.setObjectName("toggleDescription")
            self.description.setWordWrap(True)
            text_layout.addWidget(self.description)

        layout.addLayout(text_layout, 1)

        # Toggle switch
        self.toggle = ToggleSwitch(checked=checked, theme_manager=self.theme_manager)
        self.toggle.toggled.connect(self.toggled.emit)
        layout.addWidget(self.toggle)

        # Make entire frame clickable
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        """Click anywhere to toggle."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle.toggle()

    def isChecked(self) -> bool:
        return self.toggle.isChecked()

    def setChecked(self, checked: bool):
        self.toggle.setChecked(checked)

    def apply_theme(self, theme: ThemeColors):
        """Apply theme colors."""
        self.toggle.apply_theme(theme)

        self.setStyleSheet(f"""
            QFrame#toggleOption {{
                background-color: {theme.bg_tertiary};
                border: 1px solid {theme.border_dim};
                border-radius: 8px;
            }}

            QFrame#toggleOption:hover {{
                border-color: {theme.border_hover};
            }}

            QLabel#toggleLabel {{
                color: {theme.text_primary};
                font-size: 13px;
                font-weight: 500;
                background: transparent;
                border: none;
            }}

            QLabel#toggleDescription {{
                color: {theme.text_muted};
                font-size: 11px;
                background: transparent;
                border: none;
            }}
        """)

    def set_theme(self, theme_manager: ThemeManager):
        """Update theme manager and apply."""
        self.theme_manager = theme_manager
        self.apply_theme(theme_manager.theme)