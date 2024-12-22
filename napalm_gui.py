import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QLineEdit, QComboBox,
                             QPushButton, QTextEdit, QGridLayout, QMessageBox)
from PyQt6.QtCore import Qt
import napalm
import json
from typing import Optional, Dict, Any


class NapalmTester(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NAPALM SSH Tester")
        self.setMinimumSize(800, 600)

        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # Create input form
        form_layout = QGridLayout()

        # IP Address input
        form_layout.addWidget(QLabel("IP Address:"), 0, 0)
        self.ip_input = QLineEdit()
        form_layout.addWidget(self.ip_input, 0, 1)

        # Driver selection
        form_layout.addWidget(QLabel("Driver:"), 1, 0)
        self.driver_combo = QComboBox()

        # Initialize SSH-only NAPALM drivers
        self.drivers = {
            "ios": {"name": "ios"},
            "iosxr": {"name": "iosxr"},
            "junos": {"name": "junos"},
            "eos": {"name": "eos", "optional_args": {"transport": "ssh"}},
            "nxos_ssh": {"name": "nxos_ssh"},
            "huawei": {"name": "huawei"},
            "procurve": {"name": "procurve"},  # HP ProCurve
            "aruba_cx": {"name": "aruba_cx"}   # Aruba CX
        }

        # Populate combo box
        for driver in self.drivers.keys():
            self.driver_combo.addItem(driver)

        form_layout.addWidget(self.driver_combo, 1, 1)

        # Username input
        form_layout.addWidget(QLabel("Username:"), 2, 0)
        self.username_input = QLineEdit()
        form_layout.addWidget(self.username_input, 2, 1)

        # Password input
        form_layout.addWidget(QLabel("Password:"), 3, 0)
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        form_layout.addWidget(self.password_input, 3, 1)

        # Add form to main layout
        layout.addLayout(form_layout)

        # Create button grid for NAPALM features
        button_layout = QGridLayout()
        self.create_feature_buttons(button_layout)
        layout.addLayout(button_layout)

        # Output area
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        layout.addWidget(self.output_text)

        # Clear output button
        clear_button = QPushButton("Clear Output")
        clear_button.clicked.connect(self.clear_output)
        layout.addWidget(clear_button)

    def create_feature_buttons(self, layout: QGridLayout) -> None:
        """Create buttons for testing different NAPALM features"""
        features = [
            ("Test Connection", self.test_connection),
            ("Get Facts", self.get_facts),
            ("Get Interfaces", self.get_interfaces),
            ("Get BGP Neighbors", self.get_bgp_neighbors),
            ("Get LLDP Neighbors", self.get_lldp_neighbors),
            ("Get Config", self.get_config),
            ("Get ARP Table", self.get_arp_table),
            ("Get MAC Table", self.get_mac_table),
            ("Get NTP Servers", self.get_ntp_servers),
            ("Get SNMP Info", self.get_snmp_information),
            ("Get Users", self.get_users),
            ("Get VLANs", self.get_vlans)
        ]

        row = 0
        col = 0
        max_cols = 3

        for feature_name, callback in features:
            button = QPushButton(feature_name)
            button.clicked.connect(callback)
            layout.addWidget(button, row, col)

            col += 1
            if col >= max_cols:
                col = 0
                row += 1

    def get_driver(self) -> Optional[Any]:
        """Initialize NAPALM driver with current settings"""
        try:
            driver_name = self.driver_combo.currentText()
            driver = napalm.get_network_driver(driver_name)

            # Base driver options
            driver_opts = {
                'hostname': self.ip_input.text(),
                'username': self.username_input.text(),
                'password': self.password_input.text()
            }

            # Add SSH transport for EOS
            if driver_name == 'eos':
                driver_opts['optional_args'] = {'transport': 'ssh'}

            device = driver(**driver_opts)
            return device

        except Exception as e:
            self.log_error(f"Failed to initialize driver: {str(e)}")
            return None

    def execute_napalm_command(self, command_name: str, func_name: str) -> None:
        """Execute a NAPALM getter function and display results"""
        device = self.get_driver()
        if not device:
            return

        try:
            device.open()
            getter = getattr(device, func_name)
            result = getter()
            self.log_output(f"\n{command_name} Results:", json.dumps(result, indent=2))
            device.close()
        except Exception as e:
            self.log_error(f"{command_name} failed: {str(e)}")
            try:
                device.close()
            except:
                pass

    def test_connection(self) -> None:
        """Test basic connection to device"""
        device = self.get_driver()
        if not device:
            return

        try:
            device.open()
            self.log_success("Connection successful!")
            device.close()
        except Exception as e:
            self.log_error(f"Connection failed: {str(e)}")

    def get_facts(self) -> None:
        self.execute_napalm_command("Get Facts", "get_facts")

    def get_interfaces(self) -> None:
        self.execute_napalm_command("Get Interfaces", "get_interfaces")

    def get_bgp_neighbors(self) -> None:
        self.execute_napalm_command("Get BGP Neighbors", "get_bgp_neighbors")

    def get_lldp_neighbors(self) -> None:
        self.execute_napalm_command("Get LLDP Neighbors", "get_lldp_neighbors")

    def get_config(self) -> None:
        self.execute_napalm_command("Get Config", "get_config")

    def get_arp_table(self) -> None:
        self.execute_napalm_command("Get ARP Table", "get_arp_table")

    def get_mac_table(self) -> None:
        self.execute_napalm_command("Get MAC Table", "get_mac_address_table")

    def get_ntp_servers(self) -> None:
        self.execute_napalm_command("Get NTP Servers", "get_ntp_servers")

    def get_snmp_information(self) -> None:
        self.execute_napalm_command("Get SNMP Information", "get_snmp_information")

    def get_users(self) -> None:
        self.execute_napalm_command("Get Users", "get_users")

    def get_vlans(self) -> None:
        self.execute_napalm_command("Get VLANs", "get_vlans")

    def log_output(self, title: str, message: str) -> None:
        """Add formatted output to text area"""
        self.output_text.append(f"\n{'-' * 50}")
        self.output_text.append(title)
        self.output_text.append(f"{'-' * 50}\n")
        self.output_text.append(message)
        self.output_text.append(f"\n{'-' * 50}")

    def log_error(self, message: str) -> None:
        """Log error message to output"""
        self.output_text.append(f"\nERROR: {message}\n")
        QMessageBox.critical(self, "Error", message)

    def log_success(self, message: str) -> None:
        """Log success message to output"""
        self.output_text.append(f"\nSUCCESS: {message}\n")

    def clear_output(self) -> None:
        """Clear the output text area"""
        self.output_text.clear()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = NapalmTester()
    window.show()
    sys.exit(app.exec())