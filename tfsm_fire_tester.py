#!/usr/bin/env python3
"""
TextFSM Template Tester - Debug tool for testing template matching and parsing
"""

import sys
import json
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QTextEdit, QLineEdit, QPushButton,
                             QLabel, QSplitter, QTableWidget, QTableWidgetItem,
                             QTabWidget, QGroupBox, QSpinBox, QCheckBox,
                             QFileDialog, QMessageBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QTextCharFormat, QTextCursor

# Import your existing TextFSM engine
try:
    from secure_cartography.tfsm_fire import TextFSMAutoEngine
except ImportError:
    print("Could not import TextFSMAutoEngine - make sure secure_cartography is in your path")
    sys.exit(1)


class TemplateTestWorker(QThread):
    """Worker thread for template testing to avoid blocking UI"""
    results_ready = pyqtSignal(str, list, float, list)

    def __init__(self, db_path, device_output, filter_string, verbose=True):
        super().__init__()
        self.db_path = db_path
        self.device_output = device_output
        self.filter_string = filter_string
        self.verbose = verbose

    def run(self):
        try:
            engine = TextFSMAutoEngine(self.db_path, verbose=self.verbose)

            # Get all matching templates first for the detailed view
            with engine.connection_manager.get_connection() as conn:
                all_templates = engine.get_filtered_templates(conn, self.filter_string)

            # Find best template
            best_template, best_parsed, best_score = engine.find_best_template(
                self.device_output, self.filter_string
            )

            self.results_ready.emit(best_template or "None", best_parsed or [],
                                    best_score, all_templates)
        except Exception as e:
            self.results_ready.emit(f"Error: {str(e)}", [], 0.0, [])


class TextFSMTester(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TextFSM Template Tester")
        self.setGeometry(100, 100, 1400, 800)

        # Default database path
        self.db_path = "secure_cartography/tfsm_templates.db"

        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Controls section
        controls_group = QGroupBox("Test Controls")
        controls_layout = QVBoxLayout(controls_group)

        # Database path
        db_layout = QHBoxLayout()
        db_layout.addWidget(QLabel("Database Path:"))
        self.db_path_input = QLineEdit(self.db_path)
        db_layout.addWidget(self.db_path_input)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_database)
        db_layout.addWidget(browse_btn)
        controls_layout.addLayout(db_layout)

        # Filter string
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter String:"))
        self.filter_input = QLineEdit("show_lldp_neighbor")
        self.filter_input.setPlaceholderText("e.g., show_lldp_neighbor, show_cdp_neighbor")
        filter_layout.addWidget(self.filter_input)
        controls_layout.addLayout(filter_layout)

        # Options
        options_layout = QHBoxLayout()
        self.verbose_check = QCheckBox("Verbose Output")
        self.verbose_check.setChecked(True)
        options_layout.addWidget(self.verbose_check)

        self.max_templates_spin = QSpinBox()
        self.max_templates_spin.setRange(1, 100)
        self.max_templates_spin.setValue(10)
        options_layout.addWidget(QLabel("Max Templates:"))
        options_layout.addWidget(self.max_templates_spin)
        options_layout.addStretch()
        controls_layout.addLayout(options_layout)

        # Test button
        self.test_btn = QPushButton("Test Templates")
        self.test_btn.clicked.connect(self.test_templates)
        controls_layout.addWidget(self.test_btn)

        layout.addWidget(controls_group)

        # Main content area with splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left side - Input
        input_group = QGroupBox("Device Output")
        input_layout = QVBoxLayout(input_group)

        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("""Paste your device output here, for example:

usa-spine-2#show lldp nei detail
Capability codes:
    (R) Router, (B) Bridge, (T) Telephone, (C) DOCSIS Cable Device
    (W) WLAN Access Point, (P) Repeater, (S) Station, (O) Other

Device ID           Local Intf     Hold-time  Capability      Port ID
usa-spine-1         Eth2           120        B,R             Ethernet2
usa-rtr-1           Eth1           120        R               GigabitEthernet0/2
usa-leaf-3          Eth3           120        R               GigabitEthernet0/0
usa-leaf-2          Eth4           120        R               GigabitEthernet0/0
usa-leaf-1          Eth5           120        R               GigabitEthernet0/0""")

        # Load sample button
        load_sample_btn = QPushButton("Load Sample LLDP Output")
        load_sample_btn.clicked.connect(self.load_sample_output)

        input_layout.addWidget(load_sample_btn)
        input_layout.addWidget(self.input_text)
        splitter.addWidget(input_group)

        # Right side - Results tabs
        self.results_tabs = QTabWidget()

        # Results tab
        results_tab = QWidget()
        results_layout = QVBoxLayout(results_tab)

        # Best match info
        self.best_match_label = QLabel("Best Match: None")
        self.best_match_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        results_layout.addWidget(self.best_match_label)

        self.score_label = QLabel("Score: 0.0")
        results_layout.addWidget(self.score_label)

        # Parsed data table
        self.results_table = QTableWidget()
        results_layout.addWidget(QLabel("Parsed Data:"))
        results_layout.addWidget(self.results_table)

        self.results_tabs.addTab(results_tab, "Best Results")

        # All templates tab
        templates_tab = QWidget()
        templates_layout = QVBoxLayout(templates_tab)

        self.templates_table = QTableWidget()
        self.templates_table.setColumnCount(4)
        self.templates_table.setHorizontalHeaderLabels(["Template", "Score", "Records", "Status"])
        templates_layout.addWidget(self.templates_table)

        self.results_tabs.addTab(templates_tab, "All Templates")

        # Debug log tab
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Courier", 9))
        log_layout.addWidget(self.log_text)

        self.results_tabs.addTab(log_tab, "Debug Log")

        splitter.addWidget(self.results_tabs)
        splitter.setSizes([400, 800])

        layout.addWidget(splitter)

        # Status bar
        self.statusBar().showMessage("Ready - Load device output and test templates")

    def browse_database(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select TextFSM Database", "", "Database Files (*.db);;All Files (*)")
        if file_path:
            self.db_path_input.setText(file_path)
            self.db_path = file_path

    def load_sample_output(self):
        sample_lldp = """usa-spine-2#show lldp neighbors detail
Capability codes:
    (R) Router, (B) Bridge, (T) Telephone, (C) DOCSIS Cable Device
    (W) WLAN Access Point, (P) Repeater, (S) Station, (O) Other

Device ID           Local Intf     Hold-time  Capability      Port ID
usa-spine-1         Eth2           120        B,R             Ethernet2
usa-rtr-1           Eth1           120        R               GigabitEthernet0/2
usa-leaf-3          Eth3           120        R               GigabitEthernet0/0
usa-leaf-2          Eth4           120        R               GigabitEthernet0/0
usa-leaf-1          Eth5           120        R               GigabitEthernet0/0"""

        self.input_text.setPlainText(sample_lldp)
        self.filter_input.setText("show_lldp_neighbor")

    def test_templates(self):
        device_output = self.input_text.toPlainText().strip()
        filter_string = self.filter_input.text().strip()

        if not device_output:
            QMessageBox.warning(self, "Warning", "Please enter device output to test")
            return

        if not Path(self.db_path_input.text()).exists():
            QMessageBox.critical(self, "Error", f"Database file not found: {self.db_path_input.text()}")
            return

        self.db_path = self.db_path_input.text()
        self.test_btn.setEnabled(False)
        self.statusBar().showMessage("Testing templates...")
        self.log_text.clear()

        # Start worker thread
        self.worker = TemplateTestWorker(
            self.db_path, device_output, filter_string, self.verbose_check.isChecked())
        self.worker.results_ready.connect(self.handle_results)
        self.worker.start()

    def handle_results(self, best_template, best_parsed, best_score, all_templates):
        self.test_btn.setEnabled(True)
        self.statusBar().showMessage("Testing complete")

        # Update best match info
        self.best_match_label.setText(f"Best Match: {best_template}")
        self.score_label.setText(f"Score: {best_score:.2f}")

        # Update results table
        if best_parsed:
            self.results_table.setRowCount(len(best_parsed))
            if best_parsed:
                self.results_table.setColumnCount(len(best_parsed[0]))
                self.results_table.setHorizontalHeaderLabels(list(best_parsed[0].keys()))

                for row, item in enumerate(best_parsed):
                    for col, (key, value) in enumerate(item.items()):
                        self.results_table.setItem(row, col, QTableWidgetItem(str(value)))
        else:
            self.results_table.setRowCount(0)
            self.results_table.setColumnCount(0)

        # Update all templates table
        self.templates_table.setRowCount(len(all_templates))
        for row, template in enumerate(all_templates):
            self.templates_table.setItem(row, 0, QTableWidgetItem(template['cli_command']))
            self.templates_table.setItem(row, 1, QTableWidgetItem("N/A"))
            self.templates_table.setItem(row, 2, QTableWidgetItem("N/A"))
            self.templates_table.setItem(row, 3, QTableWidgetItem("Available"))

        # Log detailed results
        self.log_results(best_template, best_parsed, best_score, all_templates)

        # Auto-switch to results tab
        self.results_tabs.setCurrentIndex(0)

    def log_results(self, best_template, best_parsed, best_score, all_templates):
        log_content = []
        log_content.append("=" * 60)
        log_content.append("TEXTFSM TEMPLATE TEST RESULTS")
        log_content.append("=" * 60)
        log_content.append(f"Filter String: {self.filter_input.text()}")
        log_content.append(f"Templates Found: {len(all_templates)}")
        log_content.append(f"Best Template: {best_template}")
        log_content.append(f"Best Score: {best_score:.2f}")
        log_content.append(f"Records Parsed: {len(best_parsed) if best_parsed else 0}")
        log_content.append("")

        if best_parsed:
            log_content.append("PARSED DATA SAMPLE:")
            log_content.append("-" * 40)
            for i, record in enumerate(best_parsed[:3]):  # Show first 3 records
                log_content.append(f"Record {i + 1}:")
                log_content.append(json.dumps(record, indent=2))
                log_content.append("")

            if len(best_parsed) > 3:
                log_content.append(f"... and {len(best_parsed) - 3} more records")
                log_content.append("")

        log_content.append("ALL MATCHING TEMPLATES:")
        log_content.append("-" * 40)
        for template in all_templates:
            log_content.append(f"• {template['cli_command']}")

        self.log_text.setPlainText("\n".join(log_content))


def main():
    app = QApplication(sys.argv)

    # Set application style
    app.setStyle('Fusion')

    tester = TextFSMTester()
    tester.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()