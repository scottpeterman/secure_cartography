"""
SecureCartography v2 - UI Entry Point

Application startup with:
- Login dialog for vault unlock
- Main window launch on successful authentication
- Theme persistence
"""
import os
import sys

os.environ["QTWEBENGINE_REMOTE_DEBUGGING"] = "9222"
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QDialog

from sc2.ui.themes import ThemeManager, ThemeName
from sc2.ui.settings import SettingsManager, get_settings
from sc2.ui.login import LoginDialog
from sc2.ui.main_window import MainWindow


def run_app():
    """
    Run the Secure Cartography application.

    Flow:
    1. Initialize Qt application
    2. Load settings (including saved theme)
    3. Initialize vault
    4. Show login dialog
    5. On successful unlock, show main window with vault
    """
    # High DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Secure Cartography")
    app.setApplicationVersion("2.0.0")

    # Load settings
    settings = get_settings()
    theme_name = settings.get_theme()

    # Initialize theme manager
    theme_manager = ThemeManager(theme_name)

    # Set application-wide stylesheet
    app.setStyleSheet(theme_manager.stylesheet)

    # Initialize vault
    try:
        from ..scng.creds.vault import CredentialVault
        vault = CredentialVault()
    except ImportError as e:
        print(f"Warning: Could not import CredentialVault: {e}")
        print("Using mock vault for development")
        from .login import MockVault
        vault = MockVault()

    # Show login dialog
    login_dialog = LoginDialog(
        vault=vault,
        theme_manager=theme_manager,
        settings=settings
    )

    # Connect vault unlock to main window launch
    main_window: Optional[MainWindow] = None

    def on_vault_unlocked(unlocked_vault):
        """Handle successful vault unlock."""
        nonlocal main_window

        # Create and show main window - pass settings for theme persistence
        main_window = MainWindow(
            vault=unlocked_vault,
            theme_name=theme_manager.theme_name,
            settings=settings  # FIX: Pass settings so MainWindow can persist theme changes
        )
        main_window.show()

    login_dialog.vault_unlocked.connect(on_vault_unlocked)

    # Run login dialog
    result = login_dialog.exec()

    if result != QDialog.DialogCode.Accepted:
        # User cancelled or closed login
        sys.exit(0)

    # Run main event loop
    sys.exit(app.exec())


def main():
    """Entry point for console_scripts."""
    run_app()


if __name__ == "__main__":
    main()