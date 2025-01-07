# import logging
import json
import os
import sys
import traceback

from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
                             QLineEdit, QSpinBox, QComboBox, QPushButton, QLabel,
                             QListWidget, QListWidgetItem, QProgressBar, QGroupBox,
                             QGridLayout, QCheckBox, QSplitter, QDialog, QMessageBox, QMainWindow, QInputDialog,
                             QApplication, QTextEdit, QFileDialog, QSpacerItem, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QSettings
from pathlib import Path
from PyQt6.QtSvgWidgets import QSvgWidget
from secure_cartography.preview_widget import TopologyPreviewWidget
from secure_cartography.mviewer import TopologyViewer
from secure_cartography.credslib import SecureCredentials
from secure_cartography.help_dialog import HelpDialog
from secure_cartography.network_discovery import NetworkDiscovery, DiscoveryConfig
from secure_cartography.logger_manager import logger_manager as logger_manager
from secure_cartography.splash import WebPasswordDialog


class MasterPasswordDialog(QDialog):
    def __init__(self, creds_manager: SecureCredentials, parent=None):
        super().__init__(parent)
        self.creds_manager = creds_manager
        self.setWindowTitle("Enter Master Password")

        layout = QVBoxLayout(self)

        # Password input
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.returnPressed.connect(self.try_unlock)
        layout.addWidget(QLabel("Master Password:"))
        layout.addWidget(self.password_input)

        # Main buttons
        button_box = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.try_unlock)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        self.reset_button = QPushButton("Reset Credentials")
        self.reset_button.clicked.connect(self.reset_credentials)

        button_box.addWidget(self.ok_button)
        button_box.addWidget(self.reset_button)
        button_box.addWidget(self.cancel_button)
        layout.addLayout(button_box)

    def try_unlock(self):
        password = self.password_input.text()
        if not password:
            QMessageBox.warning(self, "Error", "Password cannot be empty")
            return

        if self.creds_manager.unlock(password):
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "Invalid password")

    def reset_credentials(self):
        reply = QMessageBox.warning(
            self,
            "Reset Credentials",
            "Warning: This will remove all stored credentials and reset the master password.\n\n"
            "You will need to re-enter your credentials after this operation.\n\n"
            "Are you sure you want to continue?",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel
        )

        if reply == QMessageBox.StandardButton.Ok:
            try:
                # Remove the salt file
                salt_path = self.creds_manager.config_dir / ".salt"
                if salt_path.exists():
                    salt_path.unlink()

                # Remove the credentials file
                creds_path = self.creds_manager.config_dir / "network_mapper_passwords.yaml"
                if creds_path.exists():
                    creds_path.unlink()

                # Remove the credentials file
                creds_path = self.creds_manager.config_dir / "credentials.yaml"
                if creds_path.exists():
                    creds_path.unlink()
                # Clear the keyring entry
                try:
                    import keyring
                    keyring.delete_password(self.creds_manager.app_name,
                                            self.creds_manager.key_identifier)
                except Exception as e:
                    print(f"Warning: Could not clear keyring entry: {e}")

                QMessageBox.information(
                    self,
                    "Reset Complete",
                    "Credentials have been reset. The application will now shutdown.\n\n"
                    "Next login, you will be prompted to create a new master password."
                )

                # Set flag for successful reset
                self.creds_manager.is_initialized = False
                sys.exit()

            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Reset Failed",
                    f"Failed to reset credentials: {str(e)}\n\nPlease try again."
                )



class NetworkDiscoveryWorker(QThread):
    """Worker thread to run network discovery without blocking the GUI"""
    device_discovered = pyqtSignal(str, str)  # ip, status
    discovery_complete = pyqtSignal(dict)  # stats
    progress_update = pyqtSignal(dict)  # progress updates
    error_occurred = pyqtSignal(str)  # error messages
    log_message = pyqtSignal(str)

    def __init__(self, config):
        super().__init__()
        self.config = config

    def run(self):
        try:
            # Create discovery config with only the parameters it expects
            discovery_config = {
                'seed_ip': self.config['seed_ip'],
                'username': self.config['username'],
                'password': self.config['password'],
                'alternate_username': self.config['alternate_username'],
                'alternate_password': self.config['alternate_password'],
                'domain_name': self.config['domain_name'],
                'exclude_string': self.config['exclude_string'],
                'output_dir': Path(self.config['output_dir']),
                'timeout': self.config['timeout'],
                'max_devices': self.config['max_devices'],
                'save_debug_info': self.config.get('save_debug_info', False),
                'map_name': self.config['map_name'],
                'layout_algo': self.config['layout_algo']

            }

            # Create NetworkDiscovery instance with config
            discovery = NetworkDiscovery(DiscoveryConfig(**discovery_config))

            # Set up progress callback to emit signals
            discovery.set_progress_callback(self._handle_progress)

            # Set up log callback
            discovery.set_log_callback(self._handle_log)

            # Run discovery
            network_map = discovery.crawl()

            # Get stats and emit completion
            stats = discovery.get_discovery_stats()
            self.discovery_complete.emit(stats)

        except Exception as e:
            self.error_occurred.emit(str(e))

    def _handle_log(self, message):
        """Handle log messages from NetworkDiscovery"""
        self.log_message.emit(message)

    def _handle_progress(self, progress_data):
        """Handle progress updates from NetworkDiscovery"""
        # Extract IP and status
        ip = progress_data.get('ip')
        status = progress_data.get('status')

        # Emit device discovered signal if we have both ip and status
        if ip is not None and status is not None:
            self.device_discovered.emit(ip, status)

        # Emit progress update with full stats
        self.progress_update.emit({
            'devices_discovered': progress_data.get('devices_discovered', 0),
            'devices_failed': progress_data.get('devices_failed', 0),
            'devices_queued': progress_data.get('devices_queued', 0),
            'devices_visited': progress_data.get('devices_visited', 0),
            'unreachable_hosts': progress_data.get('unreachable_hosts', 0)
        })

class NetworkMapperWidget(QWidget):
    """A reusable widget for network discovery and mapping"""

    discovery_started = pyqtSignal(dict)  # Emits config when discovery starts
    discovery_completed = pyqtSignal(dict)  # Emits results when discovery completes

    def __init__(self, creds_manager: SecureCredentials, parent=None):
        super().__init__(parent)
        self.settings = QSettings('NetworkMapper', 'NetworkMapperWidget')
        self.creds_manager = creds_manager  # Store reference to creds_manager
        self.dark_mode = self.settings.value('dark_mode', defaultValue=True, type=bool)
        self.parent = parent
        self.setup_ui()
        self.load_settings()
        # self.apply_theme(self.dark_mode)
        self.set_dark_mode(self.dark_mode)

    def setup_ui(self):
        """Initialize the user interface"""
        main_layout = QHBoxLayout(self)  # Main horizontal layout

        # Left side (original controls)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # Configuration group
        config_group = QGroupBox("Configuration")
        config_group.setStyleSheet("""
            QLineEdit, QSpinBox, QComboBox {
                border: 1px solid #666;
                border-radius: 3px;
                padding: 8px 4px; 
                margin: 2px;      
                min-height: 20px; 
            }
        """)
        config_layout = QGridLayout()

        # Create form widgets
        self.seed_ip = QLineEdit()
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)

        self.alt_username = QLineEdit("rtradmin")
        self.alt_password = QLineEdit("Th!$istheW@y")
        self.alt_password.setEchoMode(QLineEdit.EchoMode.Password)

        self.max_devices = QSpinBox()
        self.max_devices.setRange(1, 1000)
        self.max_devices.setValue(100)

        self.timeout = QSpinBox()
        self.timeout.setRange(1, 300)
        self.timeout.setValue(30)

        self.domain = QLineEdit()
        self.map_name = QLineEdit("map")
        self.exclude = QLineEdit()
        self.output_dir = QLineEdit("./output")

        self.save_debug = QCheckBox("Save Debug Info")

        self.layout_algo = QComboBox()
        self.layout_algo.addItems(["kk", "rt", "circular"])

        self.theme_toggle = QCheckBox()
        self.theme_toggle.setChecked(self.dark_mode)
        self.theme_toggle.toggled.connect(self.toggle_theme)

        # Left column
        left_form = QFormLayout()
        left_form.addRow("Seed IP:", self.seed_ip)
        left_form.addRow("Username:", self.username)
        left_form.addRow("Password:", self.password)
        left_form.addRow("Timeout (sec):", self.timeout)
        left_form.addRow("Dark Mode:", self.theme_toggle)

        # Right column with modified output directory row
        right_form = QFormLayout()
        right_form.addRow("Max Devices:", self.max_devices)
        right_form.addRow("Map Name:", self.map_name)
        right_form.addRow("Exclude Pattern:", self.exclude)

        # Output directory with browse button
        output_dir_layout = QHBoxLayout()
        output_dir_layout.addWidget(self.output_dir)
        self.browse_button = QPushButton()
        self.browse_button.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_DirIcon))
        self.browse_button.clicked.connect(self.browse_output_dir)
        self.browse_button.setMaximumWidth(30)
        self.browse_button.setToolTip("Browse for output directory")
        output_dir_layout.addWidget(self.browse_button)
        right_form.addRow("Output Directory:", output_dir_layout)

        right_form.addRow("Diagram Layout:", self.layout_algo)

        # Add both columns to grid
        left_widget_form = QWidget()
        left_widget_form.setLayout(left_form)
        right_widget_form = QWidget()
        right_widget_form.setLayout(right_form)

        config_layout.addWidget(left_widget_form, 0, 0)
        config_layout.addWidget(right_widget_form, 0, 1)

        config_group.setLayout(config_layout)
        left_layout.addWidget(config_group)

        # Progress section
        progress_group = QGroupBox("Discovery Progress")
        progress_layout = QVBoxLayout()

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        progress_layout.addWidget(self.progress_bar)

        # Stats layout
        stats_layout = QHBoxLayout()
        self.discovered_label = QLabel("Discovered: 0")
        self.failed_label = QLabel("Failed: 0")
        self.queue_label = QLabel("Queue: 0")
        self.total_label = QLabel("Total: 0")
        stats_layout.addWidget(self.discovered_label)
        stats_layout.addWidget(self.failed_label)
        stats_layout.addWidget(self.queue_label)
        stats_layout.addWidget(self.total_label)
        progress_layout.addLayout(stats_layout)

        # Device queue list
        self.device_list = QListWidget()
        progress_layout.addWidget(self.device_list)

        progress_group.setLayout(progress_layout)
        left_layout.addWidget(progress_group)

        # Define button styles
        utility_button_style = """
            QPushButton {
                background-color: #34495e;
                border: none;
                color: white;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #2c3e50;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """

        # Control buttons
        button_layout = QHBoxLayout()

        # Start button
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.start_discovery)
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                border: none;
                color: white;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        button_layout.addWidget(self.start_button)

        # Cancel button
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_discovery)
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                border: none;
                color: white;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        self.cancel_button.setEnabled(False)
        button_layout.addWidget(self.cancel_button)

        # Log button
        self.show_log_button = QPushButton("Log")
        self.show_log_button.clicked.connect(self.toggle_log)
        self.show_log_button.setStyleSheet(utility_button_style)
        button_layout.addWidget(self.show_log_button)

        # Open Folder button
        self.open_folder_button = QPushButton()
        self.open_folder_button.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_DirOpenIcon))
        self.open_folder_button.clicked.connect(self.open_output_folder)
        self.open_folder_button.setStyleSheet(utility_button_style)
        self.open_folder_button.setToolTip("Open output folder")
        button_layout.addWidget(self.open_folder_button)

        # Help button
        self.help_button = QPushButton("Help")
        self.help_button.clicked.connect(self.show_help)
        self.help_button.setStyleSheet(utility_button_style)
        button_layout.addWidget(self.help_button)

        left_layout.addLayout(button_layout)

        # Right side
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # Create a vertical splitter for the right side
        right_splitter = QSplitter(Qt.Orientation.Vertical)

        # Preview group
        preview_group = QGroupBox("Map Preview")
        preview_layout = QVBoxLayout()
        # self.preview_widget = QSvgWidget(
        self.preview_widget = TopologyPreviewWidget()
        self.preview_widget.setMinimumSize(600, 200)
        self.preview_widget.dark_mode = self.dark_mode
        preview_layout.addWidget(self.preview_widget)
        self.reset_preview_page()

        # Add Viewer button
        self.viewer_button = QPushButton("Viewer")
        self.viewer_button.setMaximumWidth(100)
        self.viewer_button.clicked.connect(self.open_topology_viewer)
        self.viewer_button.setEnabled(True)  # Initially disabled until map is generated
        preview_layout.addWidget(self.viewer_button)

        preview_group.setLayout(preview_layout)
        # Log group
        self.log_group = QGroupBox("Log Output")
        log_layout = QVBoxLayout()
        self.log_textarea = QTextEdit()
        self.log_textarea.setReadOnly(True)
        log_layout.addWidget(self.log_textarea)

        # Log controls layout
        log_button_layout = QHBoxLayout()

        # Save button
        self.save_log_button = QPushButton("Save")
        self.save_log_button.setMaximumWidth(50)
        self.save_log_button.clicked.connect(self.save_log)
        log_button_layout.addWidget(self.save_log_button)

        # Clear button
        self.clear_log_button = QPushButton("Clear")
        self.clear_log_button.setMaximumWidth(50)
        self.clear_log_button.clicked.connect(self.clear_log)
        log_button_layout.addWidget(self.clear_log_button)

        # Close button
        self.close_log_button = QPushButton("Close")
        self.close_log_button.setMaximumWidth(50)
        self.close_log_button.clicked.connect(self.close_log)
        log_button_layout.addWidget(self.close_log_button)

        # Add log level combo box
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
        self.log_level_combo.setCurrentText('INFO')
        self.log_level_combo.currentTextChanged.connect(self.change_log_level)
        self.log_level_combo.setMaximumWidth(100)

        # Add spacer and combo box
        spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        log_button_layout.addItem(spacer)
        log_button_layout.addWidget(self.log_level_combo)

        # Add button layout to log group
        log_layout.addLayout(log_button_layout)
        self.log_group.setLayout(log_layout)

        # Add both groups to the splitter
        right_splitter.addWidget(preview_group)
        right_splitter.addWidget(self.log_group)

        # Set initial sizes for the splitter
        right_splitter.setSizes([600, 400])

        # Add the splitter to the right layout
        right_layout.addWidget(right_splitter)

        # Add splitter between left and right sides
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)

        main_layout.addWidget(splitter)

        # Initialize theme support
        self.setup_theme_support()
    def setup_theme_support(self):
        """Initialize theme support"""
        self.dark_palette = QPalette()
        self.light_palette = QPalette()

        # Set up dark palette
        self.dark_palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
        self.dark_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        self.dark_palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
        self.dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
        self.dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(25, 25, 25))
        self.dark_palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
        self.dark_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        self.dark_palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
        self.dark_palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        self.dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        self.dark_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        self.dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        self.dark_palette.setColor(QPalette.ColorRole.HighlightedText, QColor(35, 35, 35))

        # Set up light palette
        self.light_palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
        self.light_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.black)
        self.light_palette.setColor(QPalette.ColorRole.Base, Qt.GlobalColor.white)
        self.light_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(233, 233, 233))
        self.light_palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
        self.light_palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.black)
        self.light_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.black)
        self.light_palette.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
        self.light_palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.black)
        self.light_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        self.light_palette.setColor(QPalette.ColorRole.Link, QColor(0, 0, 255))
        self.light_palette.setColor(QPalette.ColorRole.Highlight, QColor(76, 163, 224))
        self.light_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)

        self.theme_toggle.setChecked(self.dark_mode)

    def browse_output_dir(self):
        """Open file dialog to browse for output directory"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            self.output_dir.text(),
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )
        if directory:
            self.output_dir.setText(directory)

    def open_topology_viewer(self):
        """Open the topology viewer window"""
        try:
            # Get the output directory and map name from current config
            config = self.get_config()

            json_path = Path(config['output_dir']) / f"{config['map_name']}.json"
            topology_data = None
            if json_path.exists():
                with open(json_path, 'r') as f:
                    topology_data = json.load(f)

            if self.dark_mode:
                show_dark_map = True
            else:
                show_dark_map = False

            viewer = TopologyViewer(topology_data=topology_data, dark_mode=show_dark_map, parent=self)

            # Get the screen geometry
            screen_geometry = app.primaryScreen().availableGeometry()

            # Get the window size (using sizeHint if the window size isn't explicitly set)
            window_size = viewer.sizeHint()

            # Calculate the center position
            x = (screen_geometry.width() - window_size.width()) // 2
            y = (screen_geometry.height() - window_size.height()) // 2

            # Set the geometry before showing the window
            viewer.setGeometry(x, y, window_size.width(), window_size.height())
            viewer.show()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open topology viewer: {str(e)}")

    def open_output_folder(self):
        """Open the output folder in the system's file explorer"""
        import os
        import platform
        import subprocess

        path = os.path.abspath(self.output_dir.text())

        if not os.path.exists(path):
            QMessageBox.warning(self, "Error", "Output directory does not exist")
            return

        try:
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":  # macOS
                subprocess.Popen(["open", path])
            else:  # Linux
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open folder: {str(e)}")

    def change_log_level(self, string_level):
        """Change the logging level"""
        try:
            # Let logger_manager handle the level validation and setting
            logger_manager.set_level(string_level)

            # Store setting and update UI
            self.log_textarea.append(f"Changed logging level to: {string_level.upper()}")
            self.settings.setValue('log_level', string_level.upper())

        except Exception as e:
            print(f"Error changing log level: {str(e)}")
            traceback.print_exc()

    def set_dark_mode(self, is_dark: bool, save_setting: bool = True):
        """Set the dark mode state programmatically

        Args:
            is_dark: Whether to enable dark mode
            save_setting: Whether to save the setting to persistent storage
        """
        try:
            app = self.parent.app
            if is_dark:  # Dark mode
                app.setPalette(self.dark_palette)
                app.setStyle("fusion")
                self.setStyleSheet("""
                    QGroupBox {
                        border: 1px solid #666;
                        border-radius: 5px;
                        margin-top: 1ex;
                        padding: 10px;
                    }
                    QGroupBox::title {
                        subcontrol-origin: margin;
                        subcontrol-position: top center;
                        padding: 0 3px;
                    }
                    QLineEdit, QSpinBox, QComboBox {
                        border: 1px solid #666;
                        border-radius: 3px;
                        padding: 5px;
                        color: white;
                    }
                    QListWidget {
                        color: white;
                    }
                    QTextEdit {
                        background-color: #000000;
                        color: white;
                    }
                """)
            else:  # Light mode
                app.setPalette(self.light_palette)
                app.setStyle("fusion")
                self.setStyleSheet("""
                    QGroupBox {
                        border: 1px solid #999;
                        border-radius: 5px;
                        margin-top: 1ex;
                        padding: 10px;
                    }
                    QGroupBox::title {
                        subcontrol-origin: margin;
                        subcontrol-position: top center;
                        padding: 0 3px;
                    }
                    QLineEdit, QSpinBox, QComboBox {
                        background-color: white;
                        border: 1px solid #999;
                        border-radius: 3px;
                        padding: 5px;
                        color: black;
                    }
                    QListWidget {
                        background-color: white;
                        color: black;
                    }
                    QTextEdit {
                        background-color: white;
                        color: black;
                    }
                """)

            self.dark_mode = is_dark
            self.theme_toggle.setChecked(is_dark)
            self.preview_widget.dark_mode = is_dark

            # Reload preview if exists
            if hasattr(self, 'current_json_path'):
                self.preview_widget.load_topology(self.current_json_path)

            if save_setting:
                self.settings.setValue('dark_mode', is_dark)

        except Exception as e:
            print(f"Error setting dark mode: {str(e)}")
            traceback.print_exc()

    def toggle_theme(self, checked: bool):
        """Handle user toggling the theme via checkbox"""
        self.set_dark_mode(checked, save_setting=True)
        if self.preview_widget.current_json_path is None:
            self.preview_widget.clear_view()
        else:
            self.preview_widget.load_topology(self.preview_widget.current_json_path)

    def save_log(self):
            """Save log content to file"""
            file_name, _ = QFileDialog.getSaveFileName(
                self,
                "Save Log File",
                "",
                "Text Files (*.txt);;All Files (*)"
            )
            if file_name:
                with open(file_name, 'w') as f:
                    f.write(self.log_textarea.toPlainText())

    def cancel_discovery(self):
            """Cancel the ongoing discovery process"""
            if hasattr(self, 'worker') and self.worker.isRunning():
                self.worker.terminate()
                self.worker.wait()
                self.start_button.setEnabled(True)
                self.cancel_button.setEnabled(False)
                self.progress_bar.setValue(0)
                self.progress_bar.setRange(0, 100)
                QMessageBox.information(self, "Cancelled", "Discovery process has been cancelled.")

    def toggle_log(self):
            """Toggle the visibility of the log group"""
            if self.log_group.isVisible():
                self.log_group.hide()
            else:
                self.log_group.show()

    def show_help(self):
        """Display help information"""
        help_dialog = HelpDialog(self)
        help_dialog.exec()

    def on_log_message(self, message):
        """Handle incoming log messages"""
        self.log_textarea.append(message)
        # Auto-scroll to bottom
        scrollbar = self.log_textarea.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear_log(self):
        """Clear the log text area"""
        self.log_textarea.clear()

    def close_log(self):
        """Hide the log group box"""
        self.log_group.hide()

    def get_config(self):
        """Get current configuration as a dictionary"""
        config = {
            'seed_ip': self.seed_ip.text(),
            'username': self.username.text(),
            'password': self.password.text(),
            'alternate_username': self.alt_username.text(),
            'alternate_password': self.alt_password.text(),
            'max_devices': self.max_devices.value(),
            'domain_name': self.domain.text(),
            'map_name': self.map_name.text(),
            'exclude_string': self.exclude.text(),
            'output_dir': self.output_dir.text(),
            'timeout': self.timeout.value(),
            'save_debug_info': self.save_debug.isChecked(),
            'layout_algo': self.layout_algo.currentText(),
            'dark_mode': self.dark_mode
        }
        return config

    def load_settings(self):
        """Load settings with passwords loaded securely"""
        # Load non-sensitive settings from QSettings
        self.seed_ip.setText(self.settings.value('seed_ip', ''))
        self.username.setText(self.settings.value('username', ''))
        self.alt_username.setText(self.settings.value('alternate_username', 'rtradmin'))
        self.domain.setText(self.settings.value('domain_name', ''))
        self.map_name.setText(self.settings.value('map_name', 'map'))
        self.exclude.setText(self.settings.value('exclude_string', ''))
        self.output_dir.setText(self.settings.value('output_dir', './output'))
        self.timeout.setValue(int(self.settings.value('timeout', 30)))
        self.max_devices.setValue(int(self.settings.value('max_devices', 300)))
        self.save_debug.setChecked(self.settings.value('save_debug_info', False, type=bool))

        # Load and set theme state
        dark_mode = self.settings.value('dark_mode', True, type=bool)
        self.dark_mode = dark_mode
        self.theme_toggle.setChecked(dark_mode)
        self.preview_widget.dark_mode = dark_mode

        # Set layout algorithm
        layout = self.settings.value('layout_algo', 'kk')
        index = self.layout_algo.findText(layout)
        if index >= 0:
            self.layout_algo.setCurrentIndex(index)

        # Load passwords from secure storage if available
        if self.creds_manager.is_unlocked():
            try:
                creds = self.creds_manager.load_credentials(
                    self.creds_manager.config_dir / "network_mapper_passwords.yaml")
                if creds and len(creds) > 0:
                    self.password.setText(self.creds_manager.decrypt_value(creds[0]['primary_password']))
                    self.alt_password.setText(self.creds_manager.decrypt_value(creds[0]['alternate_password']))
            except Exception as e:
                QMessageBox.critical(self, 'Credentials Failure',
                                     "Failed to unload cached credentials, restart and try again")
                print(f"Error loading credentials: {e}")
                sys.exit()

        # Apply theme after loading all settings
        self.toggle_theme(self.dark_mode)
    def save_settings(self):
        """Save settings with passwords stored securely"""
        # Save non-sensitive settings to QSettings
        self.settings.setValue('seed_ip', self.seed_ip.text())
        self.settings.setValue('username', self.username.text())
        self.settings.setValue('alt_username', self.alt_username.text())
        self.settings.setValue('domain_name', self.domain.text())
        self.settings.setValue('map_name', self.map_name.text())
        self.settings.setValue('exclude_string', self.exclude.text())
        self.settings.setValue('output_dir', self.output_dir.text())
        self.settings.setValue('timeout', self.timeout.value())
        self.settings.setValue('max_devices', self.max_devices.value())
        self.settings.setValue('save_debug_info', self.save_debug.isChecked())
        self.settings.setValue('layout_algo', self.layout_algo.currentText())

        # Save passwords securely if credential manager is unlocked
        if self.creds_manager.is_unlocked():
            try:
                # Encrypt each password value individually
                cred = {
                    'alternate_password': self.creds_manager.encrypt_value(self.alt_password.text()),
                    'primary_password': self.creds_manager.encrypt_value(self.password.text())
                }
                self.creds_manager.save_credentials([cred],
                                                    self.creds_manager.config_dir / "network_mapper_passwords.yaml")
            except Exception as e:
                print(f"Error saving credentials: {e}")

    def load_settings(self):
        """Load settings with passwords loaded securely"""
        # Load non-sensitive settings from QSettings
        self.seed_ip.setText(self.settings.value('seed_ip', ''))
        self.username.setText(self.settings.value('username', ''))
        self.alt_username.setText(self.settings.value('alternate_username'))
        self.domain.setText(self.settings.value('domain_name', ''))
        self.map_name.setText(self.settings.value('map_name', 'map'))
        self.exclude.setText(self.settings.value('exclude_string', ''))
        self.output_dir.setText(self.settings.value('output_dir', './output'))
        self.timeout.setValue(int(self.settings.value('timeout', 30)))
        self.max_devices.setValue(int(self.settings.value('max_devices', 300)))
        self.save_debug.setChecked(self.settings.value('save_debug_info', False, type=bool))

        layout = self.settings.value('layout_algo', 'kk')
        index = self.layout_algo.findText(layout)
        if index >= 0:
            self.layout_algo.setCurrentIndex(index)

        # Load passwords from secure storage if available
        if self.creds_manager.is_unlocked():
            try:
                creds = self.creds_manager.load_credentials(
                    self.creds_manager.config_dir / "network_mapper_passwords.yaml")
                if creds and len(creds) > 0:
                    # Decrypt each password value
                    self.password.setText(self.creds_manager.decrypt_value(creds[0]['primary_password']))
                    self.alt_password.setText(self.creds_manager.decrypt_value(creds[0]['alternate_password']))
            except Exception as e:
                QMessageBox.critical(self, 'Credentials Failure',
                                     "Failed to unload cached credentials, restart and try again")
                print(f"Error loading credentials: {e}")
                sys.exit()

    def start_discovery(self):
        """Start the network discovery process"""
        config = self.get_config()
        # self.preview_widget.load("")
        # Save settings before starting discovery
        self.save_settings()

        # Reset UI state
        self.device_list.clear()
        self.progress_bar.setValue(0)
        self.discovered_label.setText("Discovered: 0")
        self.failed_label.setText("Failed: 0")
        self.queue_label.setText("Queue: 0")  # Reset queue count
        self.total_label.setText("Total: 0")
        self.start_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        # Create and start worker thread
        self.worker = NetworkDiscoveryWorker(config)
        self.worker.device_discovered.connect(self.on_device_discovered)
        self.worker.discovery_complete.connect(self.on_discovery_complete)
        self.worker.progress_update.connect(self.on_progress_update)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.log_message.connect(self.on_log_message)
        self.worker.start()

        # Emit that discovery has started
        self.discovery_started.emit(config)

    def on_device_discovered(self, ip, status):
        """Handle discovery of new device"""
        item = QListWidgetItem(f"{ip} - {status}")
        if status == "success":
            item.setBackground(Qt.GlobalColor.green)
        elif status == "failed":
            item.setBackground(Qt.GlobalColor.red)
        self.device_list.addItem(item)
        self.device_list.scrollToBottom()  # Auto-scroll to latest
        # self.progress_bar.setEnabled(True)



        # Update stats
        discovered = sum(1 for i in range(self.device_list.count())
                         if "success" in self.device_list.item(i).text())
        failed = sum(1 for i in range(self.device_list.count())
                     if "failed" in self.device_list.item(i).text())
        total = self.device_list.count()

        self.discovered_label.setText(f"Discovered: {discovered}")
        self.failed_label.setText(f"Failed: {failed}")
        self.total_label.setText(f"Total: {total}")

    def on_discovery_complete(self, stats):
        """Handle completion of discovery process"""
        try:
            self.start_button.setEnabled(True)
            self.discovery_completed.emit(stats)

            # Ensure progress bar is in determinate mode
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)

            # Load and display the SVG
            config = self.get_config()
            svg_path = Path(config['output_dir']) / f"{config['map_name']}.svg"
            json_map_path = Path(config['output_dir']) / f"{config['map_name']}.json"
            print(f"Looking for SVG at: {svg_path}")

            # Add a small delay to ensure file is completely written
            QThread.msleep(500)  # Wait for 500ms

            if svg_path.exists():
                print(f"file found, loading...")
                try:
                    # self.preview_widget.load(str(svg_path.absolute()))
                    self.preview_widget.load_topology(json_map_path)
                    print("Preview loaded successfully")
                except Exception as e:
                    print(f"Error loading SVG: {str(e)}")
            else:
                print(f"SVG file not found at {svg_path}")

            # Force a repaint of the preview widget
            self.preview_widget.update()
            QMessageBox.about(None, "Complete", f"Discovery Job Completed")


        except Exception as e:
            print(f"Error in on_discovery_complete: {str(e)}")
            traceback.print_exc()

    # def on_error(self, error_msg):
    #     """Handle errors during discovery"""
    #     self.start_button.setEnabled(True)
    #     print(f"Error during discovery: {error_msg}")
    #     self.progress_bar.setEnabled(False)
    #     try:
    #         # Load and display the SVG
    #         config = self.get_config()
    #         svg_path = Path(config['output_dir']) / f"{config['map_name']}.svg"
    #         # if svg_path.exists():
    #         #     self.preview_widget.load(str(svg_path))
    #     except Exception:
    #         print(f"unable to load svg preview")
    #         traceback.print_exc()

    def on_error(self, error_msg):
        """Handle errors during discovery"""
        self.start_button.setEnabled(True)
        self.progress_bar.setEnabled(False)

        # Log the error (assuming logging is already handled elsewhere)
        print(f"Error during discovery: {error_msg}")
        self.reset_preview_page()


    def reset_preview_page(self):
        try:
            # Determine background color based on the theme
            background_color = "#000000" if self.dark_mode else "#FFFFFF"

            # Set the web view to display a blank page with the appropriate background color
            blank_page_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{
                        margin: 0;
                        padding: 0;
                        background-color: {background_color};
                    }}
                </style>
            </head>
            <body>
            </body>
            </html>
            """
            self.preview_widget.web_view.setHtml(blank_page_content)
        except Exception as e:
            print(f"Error while handling discovery error: {e}")

    def on_progress_update(self, stats):
        """Handle progress updates from worker"""
        try:
            # Get stats with safe defaults
            discovered = int(stats.get('devices_discovered', 0))
            failed = int(stats.get('devices_failed', 0))
            queue_count = int(stats.get('devices_queued', 0))
            total = discovered + failed

            # Get max devices value safely
            max_devices = max(1, self.max_devices.value())  # Ensure we don't divide by zero

            self.progress_bar.setRange(0, 0)


            # Update status labels
            self.discovered_label.setText(f"Discovered: {discovered}")
            self.failed_label.setText(f"Failed: {failed}")
            self.queue_label.setText(f"Queue: {queue_count}")
            self.total_label.setText(f"Total: {total}")

        except Exception as e:
            print(f"Error in on_progress_update: {str(e)}")
            traceback.print_exc()


def main():
    print(f"Starting Secure Cartograph... wait for master password prompt...")
    global app
    app = QApplication(sys.argv)
    app.setStyle('fusion')
    log_dir = os.path.join(os.getcwd(), "log")
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Failed to create log directory: {str(e)}")
            return 1

    # Initialize credentials manager
    creds_manager = SecureCredentials(app_name="NetworkMapper")
    creds_path = creds_manager.config_dir / "network_mapper_passwords.yaml"
    print(f"creds_path: {creds_path}")
    if not creds_path.exists():
        password, ok = QInputDialog.getText(
            None,
            "Set Master Password",
            "No credential files found. Enter a master password to create one:",
            QLineEdit.EchoMode.Password
        )
        if ok and password:
            if not creds_manager.setup_new_credentials(password):
                QMessageBox.critical(None, "Error", "Failed to initialize credentials")
            else:
                QMessageBox.information(None, "Master Password Reset", "Application will shutdown now")
                sys.exit()
        else:
            sys.exit()

    # Show password dialog
    password_dialog = WebPasswordDialog(creds_manager)
    if password_dialog.exec() != QDialog.DialogCode.Accepted:
        return 1

    # Check if credentials system is initialized
    if not creds_manager.is_initialized:
        password, ok = QInputDialog.getText(
            None,
            "Set Master Password",
            "No credential store found. Enter a master password to create one:",
            QLineEdit.EchoMode.Password
        )
        if ok and password:
            if not creds_manager.setup_new_credentials(password):
                QMessageBox.critical(None, "Error", "Failed to initialize credentials")
                return 1
        else:
            return 1

    # Create and show main window
    window = QMainWindow()
    window.app = app
    window.setWindowTitle("Secure Cartography - an SSH Based Network Mapping Anomaly")
    mapper_widget = NetworkMapperWidget(creds_manager=creds_manager, parent=window)
    window.setCentralWidget(mapper_widget)

    # Set size and center window properly
    window.resize(800, 500)  # Set size first

    # Get the screen geometry
    screen_geometry = app.primaryScreen().availableGeometry()

    # Calculate the center position
    x = (screen_geometry.width() - window.width()) // 2
    y = (screen_geometry.height() - window.height()) // 2
    window.show()
    # Move window to center
    window.move(x, y)

    # Get the desired screen (primary screen)
    screen = app.primaryScreen()
    screen_geometry = screen.availableGeometry()

    # Calculate center position
    frame_geometry = window.frameGeometry()
    center_point = screen_geometry.center()
    frame_geometry.moveCenter(center_point)

    # Move window to center position
    window.move(frame_geometry.topLeft())

    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
# --webEngineArgs --remote-debugging-port=9222