import sys
import os
from PyQt6.QtWidgets import (QApplication, QInputDialog, QMessageBox, QLineEdit,
                             QDialog)
from secure_cartography.scart import NetworkMapperWidget
from secure_cartography.credslib import SecureCredentials
from secure_cartography.splash import WebPasswordDialog
from surveyor.surveyor_gui import NetworkResourceBrowserWidget
from admin.admin_gui import AdminShell


def main():
    app = QApplication(sys.argv)
    app.setStyle('fusion')

    # Set up logging directory
    log_dir = os.path.join(os.getcwd(), "log")
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Failed to create log directory: {str(e)}")
            return 1

    # Initialize credentials manager
    creds_manager = SecureCredentials(app_name="NetworkMapper")

    # Handle initial credential setup if needed
    creds_path = creds_manager.config_dir / "network_mapper_passwords.yaml"
    if not creds_path.exists():
        if not handle_initial_setup(creds_manager):
            return 1

    # Show password dialog
    password_dialog = WebPasswordDialog(creds_manager)
    if password_dialog.exec() != QDialog.DialogCode.Accepted:
        return 1

    # Create main window
    window = AdminShell()
    window.app = app

    # Initialize widgets with credentials
    cartography_widget = NetworkMapperWidget(creds_manager=creds_manager, parent=window)
    surveyor_widget = NetworkResourceBrowserWidget(db_path="surveyor/cmdb.db", parent=window)

    # Add widgets to pages
    window.pages["Cartography"] = cartography_widget
    window.pages["Surveyor"] = surveyor_widget

    # Update stacked widget
    window.stack.removeWidget(window.stack.widget(1))  # Remove placeholder Cartography
    window.stack.removeWidget(window.stack.widget(1))  # Remove placeholder Surveyor
    window.stack.insertWidget(1, cartography_widget)
    window.stack.insertWidget(2, surveyor_widget)

    # Center window on screen
    # Center window on screen and set size
    screen = app.primaryScreen()
    screen_geometry = screen.availableGeometry()
    window.setMinimumSize(600, 400)  # Minimum window size
    window.resize(min(800, screen_geometry.width() * 0.8),
                  min(500, screen_geometry.height() * 0.8))
    center_point = screen_geometry.center()
    frame_geometry = window.frameGeometry()
    frame_geometry.moveCenter(center_point)
    window.move(frame_geometry.topLeft())

    window.show()
    return app.exec()


def handle_initial_setup(creds_manager):
    """Handle initial credential setup"""
    password, ok = QInputDialog.getText(
        None,
        "Set Master Password",
        "No credential files found. Enter a master password to create one:",
        QLineEdit.EchoMode.Password
    )

    if ok and password:
        if not creds_manager.setup_new_credentials(password):
            QMessageBox.critical(None, "Error", "Failed to initialize credentials")
            return False
        else:
            QMessageBox.information(None, "Success", "Credentials initialized successfully")
            return True
    return False


if __name__ == '__main__':
    sys.exit(main())