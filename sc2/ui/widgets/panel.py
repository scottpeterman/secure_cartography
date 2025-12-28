"""
SecureCartography v2 - Base Panel Widget

Reusable panel component with title bar, icon, and content area.
All main window panels inherit from this base.
"""

from typing import Optional
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget,
    QSizePolicy
)
from PyQt6.QtGui import QFont

from ..themes import ThemeColors, ThemeManager


class Panel(QFrame):
    """
    Base panel widget with themed title bar and content area.

    Usage:
        panel = Panel("CONNECTION", icon="🔗", theme_manager=tm)
        panel.content_layout.addWidget(my_widget)

    Or subclass:
        class ConnectionPanel(Panel):
            def __init__(self, theme_manager):
                super().__init__("CONNECTION", icon="🔗", theme_manager=theme_manager)
                self._setup_content()
    """

    def __init__(
        self,
        title: str,
        icon: str = "",
        theme_manager: Optional[ThemeManager] = None,
        parent: Optional[QWidget] = None,
        _defer_theme: bool = False  # Subclasses set True to apply theme after setup
    ):
        super().__init__(parent)
        self.title_text = title
        self.icon_text = icon
        self.theme_manager = theme_manager

        self._setup_ui()
        # Only apply theme here if not deferred (for base Panel usage)
        # Subclasses with content should pass _defer_theme=True and call apply_theme after _setup_content
        if theme_manager and not _defer_theme:
            self.apply_theme(theme_manager.theme)

    def _setup_ui(self):
        """Build the panel structure."""
        self.setObjectName("panel")

        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Title bar
        self.title_bar = QFrame()
        self.title_bar.setObjectName("panelTitleBar")
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(16, 12, 16, 12)
        title_layout.setSpacing(8)

        # Icon (if provided)
        if self.icon_text:
            self.icon_label = QLabel(self.icon_text)
            self.icon_label.setObjectName("panelIcon")
            title_layout.addWidget(self.icon_label)

        # Title
        self.title_label = QLabel(self.title_text)
        self.title_label.setObjectName("panelTitle")
        font = self.title_label.font()
        font.setWeight(QFont.Weight.Bold)
        font.setPointSize(10)
        self.title_label.setFont(font)
        title_layout.addWidget(self.title_label)

        title_layout.addStretch()

        # Optional right-side content (subclasses can add widgets here)
        self.title_right_layout = title_layout

        self.main_layout.addWidget(self.title_bar)

        # Content area
        self.content_widget = QFrame()
        self.content_widget.setObjectName("panelContent")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(16, 12, 16, 16)
        self.content_layout.setSpacing(12)

        self.main_layout.addWidget(self.content_widget)

        # Size policy - expand horizontally, fit content vertically
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum
        )

    def add_title_widget(self, widget: QWidget):
        """Add a widget to the right side of the title bar."""
        # Insert before the stretch
        self.title_right_layout.insertWidget(
            self.title_right_layout.count() - 1,
            widget
        )

    def set_title(self, title: str):
        """Update the panel title."""
        self.title_text = title
        self.title_label.setText(title)

    def set_icon(self, icon: str):
        """Update the panel icon."""
        self.icon_text = icon
        if hasattr(self, 'icon_label'):
            self.icon_label.setText(icon)

    def apply_theme(self, theme: ThemeColors):
        """Apply theme colors to the panel."""
        self.setStyleSheet(f"""
            QFrame#panel {{
                background-color: {theme.bg_secondary};
                border: 1px solid {theme.border_dim};
                border-radius: 8px;
            }}
            
            QFrame#panelTitleBar {{
                background-color: transparent;
                border: none;
                border-bottom: 1px solid {theme.border_dim};
            }}
            
            QLabel#panelIcon {{
                color: {theme.accent};
                font-size: 14px;
                background: transparent;
            }}
            
            QLabel#panelTitle {{
                color: {theme.text_primary};
                font-weight: bold;
                text-transform: uppercase;
                letter-spacing: 1px;
                background: transparent;
            }}
            
            QFrame#panelContent {{
                background-color: transparent;
                border: none;
            }}
        """)

    def set_theme(self, theme_manager: ThemeManager):
        """Update theme manager and apply new theme."""
        self.theme_manager = theme_manager
        self.apply_theme(theme_manager.theme)


class CollapsiblePanel(Panel):
    """
    Panel that can be collapsed/expanded.

    Adds a collapse button to the title bar.
    """

    def __init__(
        self,
        title: str,
        icon: str = "",
        theme_manager: Optional[ThemeManager] = None,
        collapsed: bool = False,
        parent: Optional[QWidget] = None
    ):
        super().__init__(title, icon, theme_manager, parent, _defer_theme=True)
        self._collapsed = collapsed
        self._setup_collapse()

        if collapsed:
            self.collapse()

        # Now apply theme after setup is complete
        if theme_manager:
            self.apply_theme(theme_manager.theme)

    def _setup_collapse(self):
        """Add collapse/expand button."""
        from PyQt6.QtWidgets import QPushButton

        self.collapse_btn = QPushButton("▼")
        self.collapse_btn.setObjectName("collapseButton")
        self.collapse_btn.setFixedSize(24, 24)
        self.collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.collapse_btn.clicked.connect(self.toggle_collapse)

        self.add_title_widget(self.collapse_btn)

    def toggle_collapse(self):
        """Toggle collapsed state."""
        if self._collapsed:
            self.expand()
        else:
            self.collapse()

    def collapse(self):
        """Collapse the panel content."""
        self._collapsed = True
        self.content_widget.hide()
        self.collapse_btn.setText("▶")

    def expand(self):
        """Expand the panel content."""
        self._collapsed = False
        self.content_widget.show()
        self.collapse_btn.setText("▼")

    @property
    def is_collapsed(self) -> bool:
        return self._collapsed

    def apply_theme(self, theme: ThemeColors):
        """Apply theme with collapse button styling."""
        super().apply_theme(theme)

        # Add collapse button styling
        self.collapse_btn.setStyleSheet(f"""
            QPushButton#collapseButton {{
                background-color: transparent;
                border: none;
                color: {theme.text_muted};
                font-size: 10px;
            }}
            QPushButton#collapseButton:hover {{
                color: {theme.accent};
            }}
        """)