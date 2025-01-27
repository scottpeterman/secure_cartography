import json
import sys
from importlib import resources

from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QDialog, QFileDialog, QVBoxLayout,
                             QHBoxLayout, QLineEdit, QPushButton, QLabel,
                             QCheckBox, QComboBox, QGroupBox, QMessageBox, QWidget)

from secure_cartography.drawio_mapper2 import NetworkDrawioExporter
from secure_cartography.graphml_mapper4 import NetworkGraphMLExporter
from secure_cartography.icon_map_editor import IconConfigEditor


class TopologyEnhanceWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # with resources.path('secure_cartography', 'icons_lib') as icons_path:
        #     self.icons_path = str(icons_path)
        self.icons_path = str(Path(__file__).parent / 'icons_lib')

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Input File Selection
        input_group = QGroupBox("Input Topology File")
        input_layout = QHBoxLayout()
        self.input_path = QLineEdit()
        self.input_path.setPlaceholderText("Select input JSON topology file...")
        self.input_path.setReadOnly(True)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_input)
        input_layout.addWidget(self.input_path)
        input_layout.addWidget(browse_btn)
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # Output Directory Selection
        output_group = QGroupBox("Output Directory")
        output_layout = QHBoxLayout()
        self.output_path = QLineEdit()
        self.output_path.setPlaceholderText("Select output directory...")
        self.output_path.setReadOnly(True)
        output_browse_btn = QPushButton("Browse...")
        output_browse_btn.clicked.connect(self.browse_output)
        output_layout.addWidget(self.output_path)
        output_layout.addWidget(output_browse_btn)
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)

        # Options Group
        options_group = QGroupBox("Export Options")
        options_layout = QVBoxLayout()

        # Layout selection
        layout_box = QHBoxLayout()
        layout_box.addWidget(QLabel("Layout:"))
        self.layout_combo = QComboBox()
        self.layout_combo.addItems(['grid', 'tree', 'balloon'])
        layout_box.addWidget(self.layout_combo)
        options_layout.addLayout(layout_box)

        # Checkboxes
        self.include_endpoints = QCheckBox("Include endpoint devices")
        self.include_endpoints.setChecked(True)
        options_layout.addWidget(self.include_endpoints)

        self.use_icons = QCheckBox("Use icons for device visualization")
        self.use_icons.setChecked(True)
        options_layout.addWidget(self.use_icons)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        icon_mapping_btn = QPushButton("Edit Icon Mappings")
        icon_mapping_btn.clicked.connect(self.edit_icon_mappings)
        layout.addWidget(icon_mapping_btn)
        # Export Button
        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self.export_topology)
        layout.addWidget(export_btn)

        # Add stretch to push everything to the top
        layout.addStretch()

    def edit_icon_mappings(self):
        self.editor = IconConfigEditor()
        self.editor.show()

    def _get_icons_path(self):
        with resources.path('secure_cartography', 'icons_lib') as icons_path:
            return str(icons_path)
    def browse_input(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select Topology JSON File",
            ".",  # Current working directory
            "JSON Files (*.json)"
        )
        if filename:
            self.input_path.setText(filename)
            if not self.output_path.text():
                self.output_path.setText(str(Path(filename).parent))

    def browse_output(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            ".",  # Current working directory
            QFileDialog.Option.ShowDirsOnly
        )
        if directory:
            self.output_path.setText(directory)

    def export_topology(self):
        input_file = self.input_path.text()
        output_dir = self.output_path.text()

        if not input_file or not output_dir:
            QMessageBox.warning(self, "Missing Information",
                                "Please select both input file and output directory.")
            return

        try:
            with open(input_file, 'r') as f:
                network_data = json.load(f)

            base_name = Path(input_file).stem
            output_base = Path(output_dir) / base_name
            common_params = {
                'include_endpoints': self.include_endpoints.isChecked(),
                'use_icons': self.use_icons.isChecked(),
                'layout_type': self.layout_combo.currentText(),
                'icons_dir': self.icons_path
            }

            drawio_exporter = NetworkDrawioExporter(**common_params)
            drawio_output = output_base.with_suffix('.drawio')
            drawio_exporter.export_to_drawio(network_data, drawio_output)

            graphml_exporter = NetworkGraphMLExporter(**common_params)
            graphml_output = output_base.with_suffix('.graphml')
            graphml_exporter.export_to_graphml(network_data, graphml_output)

            QMessageBox.information(self, "Export Complete",
                                    f"Successfully exported to:\n{drawio_output}\n{graphml_output}")

        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Error during export:\n{str(e)}")


def main():
    app = QApplication(sys.argv)

    # Create a window to hold our widget
    window = QWidget()
    window.setWindowTitle("Topology Enhance")

    # Create layout for the window
    layout = QVBoxLayout(window)

    # Create and add our widget
    enhance_widget = TopologyEnhanceWidget()
    layout.addWidget(enhance_widget)

    # Show the window
    window.resize(600, 400)  # Set a reasonable default size
    window.show()

    # Start the event loop
    sys.exit(app.exec())


if __name__ == '__main__':
    main()