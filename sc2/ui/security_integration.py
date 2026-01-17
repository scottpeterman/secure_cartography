"""
Security Widget Integration for Secure Cartography Main Window

This module provides integration of the SecurityWidget into the main app.
Simply import and use the SecurityLauncher class.

Integration Steps:
1. Import this module
2. Create SecurityLauncher with your theme_manager
3. Add the button to your toolbar/layout
4. (Optional) Connect theme change signals

Example usage in main_window.py:

    from .security_integration import SecurityLauncher

    class MainWindow(QMainWindow):
        def __init__(self):
            ...
            # In your toolbar setup:
            self.security_launcher = SecurityLauncher(self.theme_manager, parent=self)
            self.toolbar.addWidget(self.security_launcher.button)

            # If you have theme change signals:
            self.theme_changed.connect(self.security_launcher.update_theme)
"""

from typing import Optional
from PyQt6.QtWidgets import QPushButton, QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon


# Import paths - adjust these based on your project structure
# from .widgets.security_widget import SecurityWidget
# from .themes import ThemeManager, ThemeColors


class SecurityLauncher:
    """
    Manages the Security Analysis window lifecycle.

    Keeps a single window instance and brings it to front when button clicked.
    Handles theme synchronization between main app and security window.
    """

    def __init__(self, theme_manager, parent: Optional[QWidget] = None):
        """
        Initialize the security launcher.

        Args:
            theme_manager: ThemeManager instance from main app
            parent: Parent widget (typically MainWindow)
        """
        self.theme_manager = theme_manager
        self.parent = parent
        self._window: Optional['SecurityWidget'] = None

        # Create the launcher button
        self.button = QPushButton("🔐 Security")
        self.button.setToolTip("CVE Vulnerability Analysis")
        self.button.clicked.connect(self._launch)

        # Apply initial theme to button if using custom styling
        self._style_button()

    def _style_button(self):
        """Apply theme-aware styling to the button."""
        theme = self.theme_manager.theme
        self.button.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.bg_tertiary};
                border: 1px solid {theme.border_dim};
                border-radius: 6px;
                padding: 8px 16px;
                color: {theme.text_primary};
                font-weight: bold;
            }}
            QPushButton:hover {{
                border-color: {theme.accent_danger};
                color: {theme.accent_danger};
            }}
            QPushButton:pressed {{
                background-color: {theme.bg_hover};
            }}
        """)

    def _launch(self):
        """Open or bring to front the security window."""
        # Import here to avoid circular imports if needed
        from sc2.ui.widgets.security_widget import SecurityWidget  # Adjust import path as needed

        if self._window is None or not self._window.isVisible():
            # Create new window
            self._window = SecurityWidget(
                theme_manager=self.theme_manager,
                parent=None  # None = independent window, not embedded
            )
            self._window.setWindowTitle("Secure Cartography - Security Analysis")
            self._window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
            self._window.resize(1200, 800)
            self._window.show()
        else:
            # Bring existing window to front
            self._window.raise_()
            self._window.activateWindow()

    def update_theme(self, theme_name=None):
        """
        Update the security window theme.

        Call this when main app theme changes.

        Args:
            theme_name: Optional ThemeName enum (uses current from theme_manager if None)
        """
        self._style_button()

        if self._window is not None and self._window.isVisible():
            self._window.apply_theme(self.theme_manager.theme)

    def close(self):
        """Clean up the security window on app exit."""
        if self._window is not None:
            self._window.close()
            self._window = None


# =============================================================================
# Alternative: Direct integration methods for main_window.py
# =============================================================================

def add_security_button_to_toolbar(toolbar, theme_manager, launch_callback):
    """
    Add security button to an existing QToolBar.

    Args:
        toolbar: QToolBar to add button to
        theme_manager: ThemeManager instance
        launch_callback: Function to call when button clicked

    Returns:
        QPushButton: The created button
    """
    theme = theme_manager.theme
    btn = QPushButton("🔐 Security")
    btn.setToolTip("CVE Vulnerability Analysis")
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {theme.bg_tertiary};
            border: 1px solid {theme.border_dim};
            border-radius: 6px;
            padding: 8px 16px;
            color: {theme.text_primary};
            font-weight: bold;
        }}
        QPushButton:hover {{
            border-color: {theme.accent_danger};
            color: {theme.accent_danger};
        }}
    """)
    btn.clicked.connect(launch_callback)
    toolbar.addWidget(btn)
    return btn


def create_security_action(main_window, theme_manager):
    """
    Create a QAction for the menu bar.

    Args:
        main_window: QMainWindow instance
        theme_manager: ThemeManager instance

    Returns:
        QAction: Menu action for security analysis
    """
    from PyQt6.QtGui import QAction

    action = QAction("Security Analysis", main_window)
    action.setShortcut("Ctrl+Shift+S")
    action.setToolTip("Open CVE vulnerability analysis (Ctrl+Shift+S)")

    # Store window reference on main_window
    main_window._security_window = None

    def launch():
        from sc2.ui.widgets.security_widget import SecurityWidget

        if main_window._security_window is None or not main_window._security_window.isVisible():
            main_window._security_window = SecurityWidget(
                theme_manager=theme_manager,
                parent=None
            )
            main_window._security_window.setWindowTitle("Secure Cartography - Security Analysis")
            main_window._security_window.resize(1200, 800)
            main_window._security_window.show()
        else:
            main_window._security_window.raise_()
            main_window._security_window.activateWindow()

    action.triggered.connect(launch)
    return action


# =============================================================================
# Inline Example: Paste this into your MainWindow class
# =============================================================================

INLINE_INTEGRATION_EXAMPLE = """
# --- Paste into MainWindow.__init__() after theme_manager is created ---

# Security analysis launcher
self._security_window = None
self.security_btn = QPushButton("🔐 Security")
self.security_btn.setToolTip("CVE Vulnerability Analysis")
self.security_btn.clicked.connect(self._open_security_analysis)

# Add to your toolbar:
# self.toolbar.addWidget(self.security_btn)

# Or add to a layout:
# self.button_layout.addWidget(self.security_btn)


# --- Add this method to MainWindow ---

def _open_security_analysis(self):
    '''Launch security analysis window.'''
    from .widgets.security_widget import SecurityWidget  # Adjust import path

    if self._security_window is None or not self._security_window.isVisible():
        self._security_window = SecurityWidget(
            theme_manager=self.theme_manager,
            parent=None  # Independent window
        )
        self._security_window.setWindowTitle("Secure Cartography - Security Analysis")
        self._security_window.resize(1200, 800)
        self._security_window.show()
    else:
        self._security_window.raise_()
        self._security_window.activateWindow()


# --- In your theme change handler, add: ---

def _on_theme_changed(self, theme_name):
    '''Handle theme changes.'''
    # ... existing theme change code ...

    # Update security window if open
    if self._security_window is not None and self._security_window.isVisible():
        self._security_window.apply_theme(self.theme_manager.theme)
"""

if __name__ == "__main__":
    print("Security Integration Module")
    print("=" * 50)
    print("\nThis module provides integration helpers for SecurityWidget.")
    print("\nSee INLINE_INTEGRATION_EXAMPLE for copy-paste code.")
    print("\n" + INLINE_INTEGRATION_EXAMPLE)