import sys
import traceback

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
                             QLineEdit, QSpinBox, QComboBox, QPushButton, QLabel,
                             QListWidget, QListWidgetItem, QProgressBar, QGroupBox,
                             QGridLayout, QCheckBox, QSplitter, QDialog, QMessageBox, QMainWindow, QInputDialog,
                             QApplication)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QSettings
from pathlib import Path
import yaml

from credslib import SecureCredentials
from network_discovery import NetworkDiscovery, DiscoveryConfig
from PyQt6.QtSvgWidgets import QSvgWidget


class MasterPasswordDialog(QDialog):
    def __init__(self, creds_manager: SecureCredentials, parent=None):
        super().__init__(parent)
        self.creds_manager = creds_manager
        self.setWindowTitle("Enter Master Password")

        layout = QVBoxLayout(self)

        # Password input
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(QLabel("Master Password:"))
        layout.addWidget(self.password_input)

        # Buttons
        button_box = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.try_unlock)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)

        button_box.addWidget(self.ok_button)
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



class NetworkDiscoveryWorker(QThread):
    """Worker thread to run network discovery without blocking the GUI"""
    device_discovered = pyqtSignal(str, str)  # ip, status
    discovery_complete = pyqtSignal(dict)  # stats
    progress_update = pyqtSignal(dict)  # progress updates
    error_occurred = pyqtSignal(str)  # error messages

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
                'map_name': self.config['map_name']
            }

            # Create NetworkDiscovery instance with config
            discovery = NetworkDiscovery(DiscoveryConfig(**discovery_config))

            # Set up progress callback to emit signals
            discovery.set_progress_callback(self._handle_progress)

            # Run discovery
            network_map = discovery.crawl()

            # Get stats and emit completion
            stats = discovery.get_discovery_stats()
            self.discovery_complete.emit(stats)

        except Exception as e:
            self.error_occurred.emit(str(e))

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

        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        main_layout = QHBoxLayout(self)  # Changed to horizontal layout

        # Left side (original controls)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # Configuration group
        config_group = QGroupBox("Configuration")
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
        self.layout_algo.addItems(["kk", "rt", "circular", "multipartite"])

        # Left column
        left_form = QFormLayout()
        left_form.addRow("Seed IP:", self.seed_ip)
        left_form.addRow("Username:", self.username)
        left_form.addRow("Password:", self.password)
        left_form.addRow("Alt Username:", self.alt_username)
        left_form.addRow("Alt Password:", self.alt_password)
        left_form.addRow("Timeout (sec):", self.timeout)

        # Right column
        right_form = QFormLayout()
        right_form.addRow("Max Devices:", self.max_devices)
        right_form.addRow("Domain:", self.domain)
        right_form.addRow("Map Name:", self.map_name)
        right_form.addRow("Exclude Pattern:", self.exclude)
        right_form.addRow("Output Directory:", self.output_dir)
        right_form.addRow("Diagram Layout:", self.layout_algo)
        right_form.addRow("", self.save_debug)

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

        # Control buttons
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("Start Discovery")
        self.start_button.clicked.connect(self.start_discovery)
        button_layout.addWidget(self.start_button)

        left_layout.addLayout(button_layout)

        # Right side (preview pane)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        preview_group = QGroupBox("Map Preview")
        preview_layout = QVBoxLayout()

        # Use QSvgWidget for SVG display
        self.preview_widget = QSvgWidget()
        self.preview_widget.setMinimumSize(600, 600)  # Set minimum size
        preview_layout.addWidget(self.preview_widget)

        preview_group.setLayout(preview_layout)
        right_layout.addWidget(preview_group)

        # Add splitter between left and right sides
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)

        main_layout.addWidget(splitter)

    def get_config(self):
        """Get current configuration as a dictionary"""
        return {
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
            # Store layout separately as it's not part of DiscoveryConfig
            'layout_algo': self.layout_algo.currentText()
        }

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
        self.max_devices.setValue(int(self.settings.value('max_devices', 100)))
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
                print(f"Error loading credentials: {e}")

    def start_discovery(self):
        """Start the network discovery process"""
        config = self.get_config()

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

        # Create and start worker thread
        self.worker = NetworkDiscoveryWorker(config)
        self.worker.device_discovered.connect(self.on_device_discovered)
        self.worker.discovery_complete.connect(self.on_discovery_complete)
        self.worker.progress_update.connect(self.on_progress_update)
        self.worker.error_occurred.connect(self.on_error)
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
            print(f"Looking for SVG at: {svg_path}")

            # Add a small delay to ensure file is completely written
            QThread.msleep(500)  # Wait for 500ms

            if svg_path.exists():
                print(f"SVG file found, loading...")
                try:
                    self.preview_widget.load(str(svg_path.absolute()))
                    print("SVG loaded successfully")
                except Exception as e:
                    print(f"Error loading SVG: {str(e)}")
            else:
                print(f"SVG file not found at {svg_path}")

            # Force a repaint of the preview widget
            self.preview_widget.update()

        except Exception as e:
            print(f"Error in on_discovery_complete: {str(e)}")
            traceback.print_exc()

    def on_error(self, error_msg):
        """Handle errors during discovery"""
        self.start_button.setEnabled(True)
        print(f"Error during discovery: {error_msg}")
        self.progress_bar.setEnabled(False)
        try:
            # Load and display the SVG
            config = self.get_config()
            svg_path = Path(config['output_dir']) / f"{config['map_name']}.svg"
            if svg_path.exists():
                self.preview_widget.load(str(svg_path))
        except Exception:
            print(f"unable to load svg preview")
            traceback.print_exc()

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
    app = QApplication(sys.argv)

    # Initialize credentials manager
    creds_manager = SecureCredentials(app_name="NetworkMapper")

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

    # Show password dialog
    password_dialog = MasterPasswordDialog(creds_manager)
    if password_dialog.exec() != QDialog.DialogCode.Accepted:
        return 1

    # Create and show main window
    window = QMainWindow()
    window.setWindowTitle("Secure Cartography - an SSH Based Network Mapping Anomaly")
    mapper_widget = NetworkMapperWidget(creds_manager=creds_manager)  # Pass creds_manager to widget
    window.setCentralWidget(mapper_widget)
    window.show()

    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
