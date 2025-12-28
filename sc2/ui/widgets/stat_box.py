"""
SecureCartography v2 - Stat Box Widget

Counter display boxes for progress tracking:
- DISCOVERED (cyan/accent)
- FAILED (red/danger)
- QUEUE (yellow/warning)
- TOTAL (white/primary)
"""

from typing import Optional
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QHBoxLayout, QWidget,
    QSizePolicy
)
from PyQt6.QtGui import QFont

from ..themes import ThemeColors, ThemeManager


class StatBox(QFrame):
    """
    Individual stat counter box.

    Display format:
    ┌─────────┐
    │   24    │  <- Large number (colored)
    │DISCOVERED│ <- Label (muted)
    └─────────┘

    Usage:
        stat = StatBox(
            value=24,
            label="DISCOVERED",
            color_role="accent",  # accent, danger, warning, success, primary
            theme_manager=tm
        )

        # Update value
        stat.set_value(25)
    """

    # Color role mapping
    COLOR_ROLES = {
        "accent": "accent",
        "danger": "accent_danger",
        "warning": "accent_warning",
        "success": "accent_success",
        "primary": "text_primary",
        "muted": "text_muted",
    }

    def __init__(
            self,
            value: int = 0,
            label: str = "",
            color_role: str = "accent",
            theme_manager: Optional[ThemeManager] = None,
            parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self._value = value
        self._label = label
        self._color_role = color_role
        self.theme_manager = theme_manager

        self._setup_ui()
        if theme_manager:
            self.apply_theme(theme_manager.theme)

    def _setup_ui(self):
        """Build the stat box UI."""
        self.setObjectName("statBox")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Value (large number)
        self.value_label = QLabel(str(self._value))
        self.value_label.setObjectName("statValue")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = self.value_label.font()
        font.setPointSize(24)
        font.setWeight(QFont.Weight.Bold)
        self.value_label.setFont(font)
        layout.addWidget(self.value_label)

        # Label
        self.label_label = QLabel(self._label)
        self.label_label.setObjectName("statLabel")
        self.label_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = self.label_label.font()
        font.setPointSize(9)
        font.setWeight(QFont.Weight.Medium)
        self.label_label.setFont(font)
        layout.addWidget(self.label_label)

        # Fixed minimum width for consistency
        self.setMinimumWidth(80)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )

    def set_value(self, value: int):
        """Update the displayed value."""
        self._value = value
        self.value_label.setText(str(value))

    def value(self) -> int:
        """Get current value."""
        return self._value

    def set_label(self, label: str):
        """Update the label text."""
        self._label = label
        self.label_label.setText(label)

    def set_color_role(self, role: str):
        """Change the color role."""
        self._color_role = role
        if self.theme_manager:
            self.apply_theme(self.theme_manager.theme)

    def apply_theme(self, theme: ThemeColors):
        """Apply theme colors."""
        # Get the color for this role
        color_attr = self.COLOR_ROLES.get(self._color_role, "accent")
        value_color = getattr(theme, color_attr, theme.accent)

        self.setStyleSheet(f"""
            QFrame#statBox {{
                background-color: {theme.bg_tertiary};
                border: 1px solid {theme.border_dim};
                border-radius: 8px;
            }}

            QLabel#statValue {{
                color: {value_color};
                background: transparent;
                border: none;
            }}

            QLabel#statLabel {{
                color: {theme.text_muted};
                text-transform: uppercase;
                letter-spacing: 1px;
                background: transparent;
                border: none;
            }}
        """)

    def set_theme(self, theme_manager: ThemeManager):
        """Update theme manager and apply."""
        self.theme_manager = theme_manager
        self.apply_theme(theme_manager.theme)


class StatBoxRow(QWidget):
    """
    Row of stat boxes for progress display.

    ┌─────────┬─────────┬─────────┬─────────┐
    │   24    │    2    │    8    │   34    │
    │DISCOVERED│ FAILED │  QUEUE  │  TOTAL  │
    └─────────┴─────────┴─────────┴─────────┘

    Usage:
        stats = StatBoxRow(theme_manager=tm)

        # Update values
        stats.set_discovered(24)
        stats.set_failed(2)
        stats.set_queued(8)
        # Total updates automatically
    """

    def __init__(
            self,
            theme_manager: Optional[ThemeManager] = None,
            parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._setup_ui()
        if theme_manager:
            self.apply_theme(theme_manager.theme)

    def _setup_ui(self):
        """Build the stat row UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Create stat boxes
        self.discovered = StatBox(
            value=0,
            label="DISCOVERED",
            color_role="accent",
            theme_manager=self.theme_manager
        )
        layout.addWidget(self.discovered)

        self.failed = StatBox(
            value=0,
            label="FAILED",
            color_role="danger",
            theme_manager=self.theme_manager
        )
        layout.addWidget(self.failed)

        self.queued = StatBox(
            value=0,
            label="QUEUE",
            color_role="warning",
            theme_manager=self.theme_manager
        )
        layout.addWidget(self.queued)

        self.total = StatBox(
            value=0,
            label="TOTAL",
            color_role="primary",
            theme_manager=self.theme_manager
        )
        layout.addWidget(self.total)

    def set_discovered(self, value: int):
        """Update discovered count."""
        self.discovered.set_value(value)
        self._update_total()

    def set_failed(self, value: int):
        """Update failed count."""
        self.failed.set_value(value)
        self._update_total()

    def set_queued(self, value: int):
        """Update queue count."""
        self.queued.set_value(value)

    def set_total(self, value: int):
        """Set total directly (if not auto-calculating)."""
        self.total.set_value(value)

    def _update_total(self):
        """Auto-calculate total from discovered + failed."""
        total = self.discovered.value() + self.failed.value()
        self.total.set_value(total)

    def reset(self):
        """Reset all counters to zero."""
        self.discovered.set_value(0)
        self.failed.set_value(0)
        self.queued.set_value(0)
        self.total.set_value(0)

    def apply_theme(self, theme: ThemeColors):
        """Apply theme to all stat boxes."""
        self.discovered.apply_theme(theme)
        self.failed.apply_theme(theme)
        self.queued.apply_theme(theme)
        self.total.apply_theme(theme)

    def set_theme(self, theme_manager: ThemeManager):
        """Update theme manager and apply."""
        self.theme_manager = theme_manager
        self.apply_theme(theme_manager.theme)