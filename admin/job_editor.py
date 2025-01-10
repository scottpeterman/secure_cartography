import os
import json
from typing import Dict, Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QDialogButtonBox, QGroupBox,
    QCheckBox, QSpinBox, QWidget
)


class SchemaBasedJobDialog(QDialog):
    """Job editor dialog based on JSON schema definition."""

    def __init__(self, job_data: Dict, schema_file: str, parent=None):
        super().__init__(parent)
        self.job_data = job_data
        self.schema = self.load_schema(schema_file)
        self.arg_widgets = {}
        self.setup_ui()

    def load_schema(self, schema_file: str) -> Dict:
        # schema_file = f"./admin/{schema_file}"
        """Load argument schema from JSON file."""
        with open(schema_file, 'r') as f:
            return json.load(f)

    def setup_ui(self):
        """Initialize the dialog UI."""
        self.setWindowTitle("Edit Job")
        self.setMinimumWidth(600)
        layout = QVBoxLayout(self)

        # Basic info group
        basic_group = QGroupBox("Basic Information")
        basic_layout = QGridLayout()

        # Job name
        self.name_input = QLineEdit(self.job_data.get('name', ''))
        basic_layout.addWidget(QLabel("Name:"), 0, 0)
        basic_layout.addWidget(self.name_input, 0, 1)

        # Script (readonly since schema is script-specific)
        self.script_input = QLineEdit(self.schema['script'])
        self.script_input.setReadOnly(False)
        basic_layout.addWidget(QLabel("Script:"), 1, 0)
        basic_layout.addWidget(self.script_input, 1, 1)

        # Schedule
        self.schedule_input = QLineEdit(self.job_data.get('schedule', 'manual'))
        schedule_help = QPushButton("?")
        schedule_help.clicked.connect(self.show_schedule_help)
        basic_layout.addWidget(QLabel("Schedule:"), 2, 0)
        basic_layout.addWidget(self.schedule_input, 2, 1)
        basic_layout.addWidget(schedule_help, 2, 2)

        # Log file
        self.log_input = QLineEdit(self.job_data.get('log_file', ''))
        log_browse = QPushButton("Browse")
        log_browse.clicked.connect(
            lambda: self.browse_save_file("Log Files (*.log);;All Files (*)", self.log_input)
        )
        basic_layout.addWidget(QLabel("Log File:"), 3, 0)
        basic_layout.addWidget(self.log_input, 3, 1)
        basic_layout.addWidget(log_browse, 3, 2)

        basic_group.setLayout(basic_layout)
        layout.addWidget(basic_group)

        # Add argument groups from schema
        for group_name, group_data in self.schema['argument_groups'].items():
            group = QGroupBox(group_data['title'])
            group_layout = QGridLayout()
            current_row = 0

            for arg in group_data['args']:
                widget = self.create_widget_for_arg(arg)
                if not widget:
                    continue

                # Label with required indicator
                label_text = f"{arg['name']}:"
                if arg.get('required'):
                    label_text = f"{label_text} *"
                group_layout.addWidget(QLabel(label_text), current_row, 0)
                group_layout.addWidget(widget, current_row, 1)

                # Add browse button for file types
                if arg['type'] == 'file':
                    browse = QPushButton("Browse")
                    browse.clicked.connect(
                        lambda checked, w=widget, a=arg: self.browse_for_arg(w, a)
                    )
                    group_layout.addWidget(browse, current_row, 2)

                # Add help text
                if arg.get('help'):
                    help_label = QLabel(arg['help'])
                    help_label.setStyleSheet("color: gray; font-size: 10px;")
                    current_row += 1
                    group_layout.addWidget(help_label, current_row, 1, 1, 2)

                current_row += 1
                self.arg_widgets[arg['flag']] = widget

            group.setLayout(group_layout)
            layout.addWidget(group)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.parse_existing_args()

    def create_widget_for_arg(self, arg: Dict) -> Optional[QWidget]:
        """Create appropriate widget based on argument schema."""
        arg_type = arg['type']

        if arg_type == 'flag':
            widget = QCheckBox()
            return widget

        elif arg_type == 'integer':
            widget = QSpinBox()
            widget.setRange(arg.get('min', -1000000), arg.get('max', 1000000))
            if 'default' in arg:
                widget.setValue(arg['default'])
            return widget

        elif arg_type in ['string', 'file', 'password']:
            widget = QLineEdit()
            if 'default' in arg:
                widget.setText(str(arg['default']))
            if arg_type == 'password':
                widget.setEchoMode(QLineEdit.EchoMode.Password)
            return widget

        return None

    def browse_for_arg(self, widget: QLineEdit, arg: Dict):
        """Handle browse button for file arguments."""
        if arg.get('is_output', False):
            filename, _ = QFileDialog.getSaveFileName(
                self, f"Select {arg['name']}", "", arg['file_filter']
            )
        else:
            filename, _ = QFileDialog.getOpenFileName(
                self, f"Select {arg['name']}", "", arg['file_filter']
            )
        if filename:
            widget.setText(filename)

    def browse_save_file(self, file_filter: str, target: QLineEdit):
        """Open file dialog for selecting a save location."""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Select Save Location", "", file_filter
        )
        if filename:
            target.setText(filename)

    def show_schedule_help(self):
        """Show help dialog for cron schedule format."""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(
            self,
            "Schedule Help",
            "Schedule formats:\n\n"
            "manual - Run manually only\n"
            "cron: * * * * * - Cron format:\n"
            "  ┌───────────── minute (0-59)\n"
            "  │ ┌───────────── hour (0-23)\n"
            "  │ │ ┌───────────── day of month (1-31)\n"
            "  │ │ │ ┌───────────── month (1-12)\n"
            "  │ │ │ │ ┌───────────── day of week (0-6)\n"
            "  │ │ │ │ │\n"
            "  * * * * *\n\n"
            "Examples:\n"
            "*/5 * * * * - Every 5 minutes\n"
            "0 */6 * * * - Every 6 hours\n"
            "0 0 * * * - Daily at midnight"
        )

    def parse_existing_args(self):
        """Parse existing arguments into form fields."""
        existing_args = self.job_data.get('args', [])
        i = 0
        while i < len(existing_args):
            flag = existing_args[i]
            if flag not in self.arg_widgets:
                i += 1
                continue

            widget = self.arg_widgets[flag]

            # Handle flags (checkboxes)
            if isinstance(widget, QCheckBox):
                widget.setChecked(True)
                i += 1
                continue

            # Handle value arguments
            if i + 1 < len(existing_args):
                value = existing_args[i + 1]
                if isinstance(widget, QLineEdit):
                    widget.setText(value)
                elif isinstance(widget, QSpinBox):
                    widget.setValue(int(value))
                i += 2
            else:
                i += 1

    def get_job_data(self) -> Dict:
        """Get the edited job data as a dictionary."""
        args = []

        # Build argument list from widgets
        for group_data in self.schema['argument_groups'].values():
            for arg in group_data['args']:
                flag = arg['flag']
                if flag not in self.arg_widgets:
                    continue

                widget = self.arg_widgets[flag]
                if isinstance(widget, QCheckBox):
                    if widget.isChecked():
                        args.append(flag)
                else:
                    value = None
                    if isinstance(widget, QLineEdit):
                        value = widget.text().strip()
                    elif isinstance(widget, QSpinBox):
                        value = str(widget.value())

                    if value:
                        args.extend([flag, value])

        # Return data in format matching Job.to_dict()
        return {
            'name': self.name_input.text(),
            'script': self.script_input.text(),
            'args': args,
            'schedule': self.schedule_input.text(),
            'log_file': self.log_input.text()
        }
