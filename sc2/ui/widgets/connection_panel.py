"""
SecureCartography v2 - Connection Panel Widget

Contains:
- Seed IP addresses (tag input)
- Domain suffixes (tag input)
- Exclude patterns (text input)
"""

from typing import List, Optional
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QSizePolicy
)
from PyQt6.QtGui import QFont

from ..themes import ThemeColors, ThemeManager
from .panel import Panel
from .tag_input import TagInput


class FormLabel(QLabel):
    """Styled form field label."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("formLabel")
        font = self.font()
        font.setPointSize(10)
        font.setWeight(QFont.Weight.Medium)
        self.setFont(font)


class FormHint(QLabel):
    """Styled form field hint/description."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("formHint")
        font = self.font()
        font.setPointSize(10)
        self.setFont(font)


class ConnectionPanel(Panel):
    """
    Connection configuration panel.

    Layout:
    ┌─ CONNECTION ─────────────────────────────────┐
    │ SEED IP ADDRESS(ES)                          │
    │ ┌──────────────────────────────────────────┐ │
    │ │ 192.168.1.1                              │ │
    │ └──────────────────────────────────────────┘ │
    │ [10.0.0.1 ×] [172.16.0.1 ×]    + Add Seed   │
    │                                              │
    │ DOMAIN SUFFIX(ES)                            │
    │ ┌──────────────────────────────────────────┐ │
    │ │ example.com                              │ │
    │ └──────────────────────────────────────────┘ │
    │ [corp.local ×]                               │
    │                                              │
    │ EXCLUDE PATTERNS                             │
    │ ┌──────────────────────────────────────────┐ │
    │ │ 🔍 e.g., *phone*, *wireless*             │ │
    │ └──────────────────────────────────────────┘ │
    │ sysDescr patterns to skip (comma-separated)  │
    └──────────────────────────────────────────────┘

    Usage:
        panel = ConnectionPanel(theme_manager=tm)

        # Get values
        seeds = panel.seeds
        domains = panel.domains
        excludes = panel.exclude_patterns

        # Set values
        panel.set_seeds(["10.0.0.1", "172.16.0.1"])

        # Connect to changes
        panel.seeds_changed.connect(on_seeds_changed)
    """

    seeds_changed = pyqtSignal(list)
    domains_changed = pyqtSignal(list)
    excludes_changed = pyqtSignal(str)

    def __init__(
        self,
        theme_manager: Optional[ThemeManager] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(
            title="CONNECTION",
            icon="🔗",
            theme_manager=theme_manager,
            parent=parent,
            _defer_theme=True  # Apply theme after _setup_content
        )
        self._setup_content()
        if theme_manager:
            self.apply_theme(theme_manager.theme)

    def _setup_content(self):
        """Build the connection panel content."""
        # Seeds section
        seeds_label = FormLabel("SEED IP ADDRESS(ES)")
        self.content_layout.addWidget(seeds_label)

        self.seeds_input = TagInput(
            placeholder="192.168.1.1",
            add_button_text="+ Add Seed",
            theme_manager=self.theme_manager
        )
        self.seeds_input.tags_changed.connect(self.seeds_changed.emit)
        self.content_layout.addWidget(self.seeds_input)

        # Domains section
        self.content_layout.addSpacing(8)
        domains_label = FormLabel("DOMAIN SUFFIX(ES)")
        self.content_layout.addWidget(domains_label)

        self.domains_input = TagInput(
            placeholder="example.com",
            add_button_text="",  # No add button, just Enter
            theme_manager=self.theme_manager
        )
        self.domains_input.tags_changed.connect(self.domains_changed.emit)
        self.content_layout.addWidget(self.domains_input)

        # Exclude patterns section
        self.content_layout.addSpacing(8)
        excludes_label = FormLabel("EXCLUDE PATTERNS")
        self.content_layout.addWidget(excludes_label)

        self.excludes_input = QLineEdit()
        self.excludes_input.setObjectName("excludesInput")
        self.excludes_input.setPlaceholderText("e.g., SEP, VM")
        self.excludes_input.textChanged.connect(self.excludes_changed.emit)
        self.content_layout.addWidget(self.excludes_input)

        excludes_hint = FormHint("sysDescr patterns to skip (comma-separated)")
        self.content_layout.addWidget(excludes_hint)

    # === Properties ===

    @property
    def seeds(self) -> List[str]:
        """Get current seed IPs, including pending input."""
        seeds = list(self.seeds_input.tags)

        # Also include uncommitted text from input field
        pending = self.seeds_input.input.text().strip()
        if pending:
            # Split by comma in case user entered multiple
            for s in pending.split(','):
                s = s.strip()
                if s and s not in seeds:
                    seeds.append(s)

        return seeds

    @property
    def domains(self) -> List[str]:
        """Get current domain suffixes, including pending input."""
        domains = list(self.domains_input.tags)

        # Also include uncommitted text from input field
        pending = self.domains_input.input.text().strip()
        if pending:
            # Split by comma in case user entered multiple
            for d in pending.split(','):
                d = d.strip()
                if d and d not in domains:
                    domains.append(d)

        return domains

    @property
    def exclude_patterns(self) -> List[str]:
        """Get exclude patterns as list."""
        text = self.excludes_input.text().strip()
        if not text:
            return []
        return [p.strip() for p in text.split(",") if p.strip()]

    # === Setters ===

    def set_seeds(self, seeds: List[str]):
        """Set seed IPs."""
        self.seeds_input.set_tags(seeds)

    def set_domains(self, domains: List[str]):
        """Set domain suffixes."""
        self.domains_input.set_tags(domains)

    def set_exclude_patterns(self, patterns: List[str]):
        """Set exclude patterns."""
        self.excludes_input.setText(", ".join(patterns))

    def clear(self):
        """Clear all fields."""
        self.seeds_input.clear_tags()
        self.domains_input.clear_tags()
        self.excludes_input.clear()

    def _apply_content_theme(self, theme: ThemeColors):
        """Apply theme to panel content."""
        self.seeds_input.apply_theme(theme)
        self.domains_input.apply_theme(theme)

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

        # Hints
        hint_style = f"""
            QLabel#formHint {{
                color: {theme.text_muted};
                background: transparent;
                border: none;
                padding-top: 4px;
            }}
        """
        for hint in self.findChildren(FormHint):
            hint.setStyleSheet(hint_style)

        # Exclude input
        self.excludes_input.setStyleSheet(f"""
            QLineEdit#excludesInput {{
                background-color: {theme.bg_input};
                border: 1px solid {theme.border_dim};
                border-radius: 6px;
                padding: 10px 12px;
                color: {theme.text_primary};
                font-size: 13px;
            }}
            QLineEdit#excludesInput:focus {{
                border-color: {theme.accent};
            }}
            QLineEdit#excludesInput::placeholder {{
                color: {theme.text_muted};
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