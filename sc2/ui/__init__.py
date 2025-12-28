"""
SecureCartography v2 - GUI Package

PyQt6-based graphical interface for network discovery and topology mapping.

Usage:
    from sc2.ui import main
    main()
    
    # Or run as module
    python -m sc2.ui
"""
import os
import sys


from .themes import ThemeManager, ThemeName, ThemeColors, get_theme, THEMES
from .login import LoginDialog, MockVault

__all__ = [
    'ThemeManager',
    'ThemeName', 
    'ThemeColors',
    'get_theme',
    'THEMES',
    'LoginDialog',
    'MockVault',
    'main',
]


def main():
    """
    Application entry point.
    
    Initializes PyQt6 application, shows login dialog,
    and launches main window on successful authentication.

    Usage:
        python -m sc2.ui [--theme cyber|dark|light]
    """
    import sys
    import argparse
    from pathlib import Path
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Secure Cartography v2 GUI")
    parser.add_argument(
        "--theme", "-t",
        choices=["cyber", "dark", "light"],
        default="cyber",
        help="UI theme (default: cyber)"
    )
    args, remaining = parser.parse_known_args()

    # Map string to enum
    theme_map = {
        "cyber": ThemeName.CYBER,
        "dark": ThemeName.DARK,
        "light": ThemeName.LIGHT,
    }
    initial_theme = theme_map[args.theme]

    # High DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # Pass remaining args to Qt (filters out our --theme)
    app = QApplication([sys.argv[0]] + remaining)
    app.setApplicationName("Secure Cartography")
    app.setApplicationVersion("2.0.0")
    app.setOrganizationName("SecureCartography")

    # Initialize theme manager
    theme_manager = ThemeManager(initial_theme)
    app.setStyleSheet(theme_manager.stylesheet)

    # Initialize vault
    # Import here to avoid circular imports and allow testing without vault
    try:
        from sc2.scng.creds import CredentialVault
        vault = CredentialVault()
    except ImportError:
        # Fallback for standalone testing
        print("Warning: Could not import CredentialVault, using mock")
        from .login import MockVault  # type: ignore
        vault = MockVault()

    # Show login dialog
    login = LoginDialog(vault, theme_manager)

    if login.exec():
        # Login successful - show main window
        # TODO: Implement MainWindow
        print("Login successful! Main window would launch here.")

        # Placeholder for main window
        from PyQt6.QtWidgets import QMainWindow, QLabel
        window = QMainWindow()
        window.setWindowTitle("Secure Cartography v2")
        window.setMinimumSize(1200, 800)

        placeholder = QLabel("Main window coming soon...")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        window.setCentralWidget(placeholder)

        window.setStyleSheet(theme_manager.stylesheet)
        window.show()

        sys.exit(app.exec())
    else:
        # Login cancelled
        sys.exit(0)