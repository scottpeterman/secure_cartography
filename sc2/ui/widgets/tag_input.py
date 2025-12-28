"""
SecureCartography v2 - Tag Input Widget

Text input that creates removable tags, used for:
- Seed IP addresses
- Domain suffixes
"""

from typing import List, Optional
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLineEdit,
    QLabel, QPushButton, QSizePolicy
)
from PyQt6.QtGui import QFont

from ..themes import ThemeColors, ThemeManager


class Tag(QFrame):
    """
    Individual removable tag widget.

    Displays text with an X button to remove.
    """

    removed = pyqtSignal(str)  # Emits tag text when removed

    def __init__(
            self,
            text: str,
            theme: Optional[ThemeColors] = None,
            parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.tag_text = text
        self.theme = theme
        self._setup_ui()
        if theme:
            self.apply_theme(theme)

    def _setup_ui(self):
        """Build the tag UI."""
        self.setObjectName("tag")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 4, 4)
        layout.setSpacing(4)

        # Tag text
        self.text_label = QLabel(self.tag_text)
        self.text_label.setObjectName("tagText")
        font = self.text_label.font()
        font.setPointSize(11)
        self.text_label.setFont(font)
        layout.addWidget(self.text_label)

        # Remove button
        self.remove_btn = QPushButton("×")
        self.remove_btn.setObjectName("tagRemove")
        self.remove_btn.setFixedSize(18, 18)
        self.remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remove_btn.clicked.connect(self._on_remove)
        layout.addWidget(self.remove_btn)

        self.setSizePolicy(
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Fixed
        )

    def _on_remove(self):
        """Handle remove button click."""
        self.removed.emit(self.tag_text)

    def apply_theme(self, theme: ThemeColors):
        """Apply theme colors."""
        self.theme = theme
        self.setStyleSheet(f"""
            QFrame#tag {{
                background-color: {theme.bg_tertiary};
                border: 1px solid {theme.border_dim};
                border-radius: 4px;
            }}

            QLabel#tagText {{
                color: {theme.accent};
                background: transparent;
                border: none;
            }}

            QPushButton#tagRemove {{
                background-color: transparent;
                border: none;
                color: {theme.text_muted};
                font-size: 14px;
                font-weight: bold;
            }}

            QPushButton#tagRemove:hover {{
                color: {theme.accent_danger};
            }}
        """)


class TagInput(QWidget):
    """
    Input widget that creates removable tags.

    Features:
    - Text input with placeholder
    - Press Enter or click "+ Add" to create tag
    - Tags displayed in a flow layout below
    - X button on each tag to remove

    Usage:
        tag_input = TagInput(
            placeholder="192.168.1.1",
            add_button_text="+ Add Seed",
            theme_manager=tm
        )
        tag_input.tags_changed.connect(on_tags_changed)

        # Get current tags
        seeds = tag_input.tags

        # Set tags programmatically
        tag_input.set_tags(["10.0.0.1", "172.16.0.1"])
    """

    tags_changed = pyqtSignal(list)  # Emits list of tag strings

    def __init__(
            self,
            placeholder: str = "",
            add_button_text: str = "+ Add",
            theme_manager: Optional[ThemeManager] = None,
            parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.placeholder = placeholder
        self.add_button_text = add_button_text
        self.theme_manager = theme_manager
        self._tags: List[str] = []
        self._tag_widgets: List[Tag] = []

        self._setup_ui()
        if theme_manager:
            self.apply_theme(theme_manager.theme)

    def _setup_ui(self):
        """Build the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Input row
        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        # Text input
        self.input = QLineEdit()
        self.input.setPlaceholderText(self.placeholder)
        self.input.setObjectName("tagInputField")
        self.input.returnPressed.connect(self._add_current)
        input_row.addWidget(self.input, 1)

        # Add button (optional, for explicit add action)
        if self.add_button_text:
            self.add_btn = QPushButton(self.add_button_text)
            self.add_btn.setObjectName("tagAddButton")
            self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.add_btn.clicked.connect(self._add_current)
            input_row.addWidget(self.add_btn)

        layout.addLayout(input_row)

        # Tags container (flow layout approximation)
        self.tags_container = QFrame()
        self.tags_container.setObjectName("tagsContainer")
        self.tags_layout = FlowLayout(self.tags_container)
        self.tags_layout.setContentsMargins(0, 0, 0, 0)
        self.tags_layout.setSpacing(6)

        layout.addWidget(self.tags_container)

    def _add_current(self):
        """Add the current input text as a tag."""
        text = self.input.text().strip()
        if text and text not in self._tags:
            self.add_tag(text)
            self.input.clear()

    def add_tag(self, text: str):
        """Add a tag."""
        if text in self._tags:
            return

        self._tags.append(text)

        # Create tag widget
        theme = self.theme_manager.theme if self.theme_manager else None
        tag = Tag(text, theme)
        tag.removed.connect(self._on_tag_removed)

        self._tag_widgets.append(tag)
        self.tags_layout.addWidget(tag)

        self.tags_changed.emit(self._tags.copy())

    def remove_tag(self, text: str):
        """Remove a tag by text."""
        if text not in self._tags:
            return

        self._tags.remove(text)

        # Find and remove widget
        for tag in self._tag_widgets:
            if tag.tag_text == text:
                self._tag_widgets.remove(tag)
                self.tags_layout.removeWidget(tag)
                tag.deleteLater()
                break

        self.tags_changed.emit(self._tags.copy())

    def _on_tag_removed(self, text: str):
        """Handle tag removal signal."""
        self.remove_tag(text)

    def set_tags(self, tags: List[str]):
        """Set tags programmatically, replacing existing."""
        self.clear_tags()
        for tag in tags:
            self.add_tag(tag)

    def clear_tags(self):
        """Remove all tags."""
        for tag in self._tag_widgets.copy():
            self.remove_tag(tag.tag_text)

    @property
    def tags(self) -> List[str]:
        """Get current list of tags."""
        return self._tags.copy()

    def apply_theme(self, theme: ThemeColors):
        """Apply theme colors."""
        # Update existing tags
        for tag in self._tag_widgets:
            tag.apply_theme(theme)

        # Style input and button
        self.input.setStyleSheet(f"""
            QLineEdit#tagInputField {{
                background-color: {theme.bg_input};
                border: 1px solid {theme.border_dim};
                border-radius: 6px;
                padding: 10px 12px;
                color: {theme.text_primary};
                font-size: 13px;
            }}
            QLineEdit#tagInputField:focus {{
                border-color: {theme.accent};
            }}
            QLineEdit#tagInputField::placeholder {{
                color: {theme.text_muted};
            }}
        """)

        if hasattr(self, 'add_btn'):
            self.add_btn.setStyleSheet(f"""
                QPushButton#tagAddButton {{
                    background-color: transparent;
                    border: 1px solid {theme.accent};
                    border-radius: 6px;
                    padding: 10px 16px;
                    color: {theme.accent};
                    font-weight: 500;
                }}
                QPushButton#tagAddButton:hover {{
                    background-color: {theme.bg_hover};
                }}
                QPushButton#tagAddButton:pressed {{
                    background-color: {theme.bg_selected};
                }}
            """)

        self.tags_container.setStyleSheet(f"""
            QFrame#tagsContainer {{
                background: transparent;
                border: none;
            }}
        """)

    def set_theme(self, theme_manager: ThemeManager):
        """Update theme manager and apply."""
        self.theme_manager = theme_manager
        self.apply_theme(theme_manager.theme)


class FlowLayout(QVBoxLayout):
    """
    Simple flow layout approximation using horizontal layouts.

    Note: For a true flow layout, you'd need a custom QLayout.
    This is a simplified version that wraps widgets into rows.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._widgets = []
        self._rows = []
        self._spacing = 6

    def setSpacing(self, spacing):
        self._spacing = spacing
        super().setSpacing(spacing)

    def addWidget(self, widget):
        """Add widget to flow layout."""
        self._widgets.append(widget)
        self._rebuild()

    def removeWidget(self, widget):
        """Remove widget from flow layout."""
        if widget in self._widgets:
            self._widgets.remove(widget)
            widget.setParent(None)
            self._rebuild()

    def _rebuild(self):
        """Rebuild rows with current widgets."""
        # Clear existing rows
        for row in self._rows:
            while row.count():
                item = row.takeAt(0)
                # Don't delete widget, just remove from layout
            self.removeItem(row)
        self._rows.clear()

        # Create new row
        current_row = QHBoxLayout()
        current_row.setSpacing(self._spacing)
        current_row.setContentsMargins(0, 0, 0, 0)

        for widget in self._widgets:
            current_row.addWidget(widget)

        current_row.addStretch()
        self._rows.append(current_row)
        super().addLayout(current_row)