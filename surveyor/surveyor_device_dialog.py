from PyQt6.QtWidgets import (QDialog, QTabWidget, QVBoxLayout, QWidget,
                             QLabel, QGridLayout, QTableView, QHeaderView,
                             QStyledItemDelegate, QGroupBox, QScrollArea, QTextEdit, QPushButton, QInputDialog,
                             QHBoxLayout)
from PyQt6.QtCore import Qt
from PyQt6.QtSql import QSqlQuery, QSqlTableModel
from PyQt6.QtGui import QColor, QTextCursor, QTextCharFormat


class InterfaceDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        if index.column() in [1, 2]:  # Link Status and Protocol Status columns
            value = str(index.data()).lower()
            if 'up' in value or 'connected' in value:
                option.palette.setColor(option.palette.ColorRole.Text, QColor('#00FF00'))  # Green
            elif 'down' in value or 'notconnect' in value:
                option.palette.setColor(option.palette.ColorRole.Text, QColor('#FF4444'))  # Red
        super().paint(painter, option, index)


class DeviceDetailDialog(QDialog):
    def __init__(self, device_id, parent=None):
        super().__init__(parent)
        self.device_id = device_id
        self.dark_mode = parent.theme_toggle.isChecked() if hasattr(parent, 'theme_toggle') else True
        self.setup_ui()
        self.load_device_data()
        self.update_theme(self.dark_mode)

    def setup_ui(self):
        self.setWindowTitle("Device Details")
        self.resize(800, 400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create tab widget
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        layout.addWidget(self.tabs)

        # Create and add tabs
        self.overview_tab = QWidget()
        self.config_tab = QWidget()
        self.interfaces_tab = QWidget()
        self.inventory_tab = QWidget()
        # self.system_info_tab = QWidget()
        self.mac_addresses_tab = QWidget()

        self.tabs.addTab(self.overview_tab, "Overview")
        self.tabs.addTab(self.config_tab, "Configuration")
        self.tabs.addTab(self.interfaces_tab, "Interfaces")
        self.tabs.addTab(self.inventory_tab, "Inventory")
        # self.tabs.addTab(self.system_info_tab, "System Info")
        self.tabs.addTab(self.mac_addresses_tab, "MAC Addresses")

        # Setup layouts for each tab
        self.setup_overview_tab()
        self.setup_config_tab()
        self.setup_interfaces_tab()
        self.setup_inventory_tab()
        self.setup_mac_addresses_tab()

    def setup_config_tab(self):
        layout = QVBoxLayout(self.config_tab)
        layout.setContentsMargins(0, 0, 0, 0)

        # Add button bar at the top
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(5, 5, 5, 5)

        self.search_button = QPushButton("Search Configuration")
        self.search_button.clicked.connect(self.search_config)
        self.search_button.setMinimumWidth(150)
        button_layout.addWidget(self.search_button)
        button_layout.addStretch()

        layout.addLayout(button_layout)

        self.config_text = QTextEdit()
        self.config_text.setReadOnly(True)

        # Set monospace font
        font = self.config_text.font()
        font.setFamily("Courier")
        font.setStyleHint(font.StyleHint.Monospace)
        self.config_text.setFont(font)

        layout.addWidget(self.config_text)

    def search_config(self):
        # Clear any existing highlighting
        cursor = self.config_text.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.setCharFormat(QTextCharFormat())
        cursor.clearSelection()

        # Prompt for search string
        text, ok = QInputDialog.getText(self, 'Search Configuration',
                                        'Enter search string:')
        if ok and text:
            # Create highlight format
            highlight_format = QTextCharFormat()
            highlight_format.setBackground(QColor('yellow'))
            highlight_format.setForeground(QColor('black'))

            # Find and highlight all matches
            cursor = self.config_text.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)

            first_match = None
            while True:
                cursor = self.config_text.document().find(text, cursor)
                if cursor.isNull():
                    break

                # Store the position of the first match
                if first_match is None:
                    first_match = QTextCursor(cursor)

                cursor.mergeCharFormat(highlight_format)

            # Scroll to the first match if found
            if first_match:
                self.config_text.setTextCursor(first_match)
                self.config_text.ensureCursorVisible()

    def setup_overview_tab(self):
        layout = QVBoxLayout(self.overview_tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Create scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Create widget to hold content
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(20)

        # Set the widget in the scroll area
        scroll_area.setWidget(scroll_widget)

        # Create group boxes for SSH and SNMP data
        ssh_group = QGroupBox("SSH-Collected Data")
        snmp_group = QGroupBox("SNMP-Collected Data")

        # Create layouts for each group
        ssh_layout = QGridLayout(ssh_group)
        snmp_layout = QGridLayout(snmp_group)

        ssh_layout.setVerticalSpacing(8)
        ssh_layout.setHorizontalSpacing(25)
        snmp_layout.setVerticalSpacing(8)
        snmp_layout.setHorizontalSpacing(25)

        self.basic_info_labels = {}

        # SSH-collected fields
        ssh_fields = [
            ("Device Information", None),
            ("Name:", "name"),
            ("IP Address:", "ip_address"),
            ("Platform:", "platform"),
            ("Vendor:", "vendor"),
            ("Model:", "model"),
            ("Running Image:", "running_image"),
            ("ROMMON Version:", "rommon_version"),
            ("Boot Reason:", "boot_reason"),
            ("Config Register:", "config_register")
        ]

        # SNMP-collected fields
        snmp_fields = [
            ("System Information", None),
            ("Hostname:", "hostname"),
            ("Software Version:", "software_version"),
            ("Software Image:", "software_image"),
            ("System Uptime", None),
            ("Uptime:", "uptime"),
            ("Last Updated:", "last_updated")
        ]

        # Add SSH fields
        row = 0
        for label_text, field in ssh_fields:
            if field is None:
                # Section header
                section_label = QLabel(label_text)
                section_label.setProperty('class', 'section-header')
                ssh_layout.addWidget(section_label, row, 0, 1, 2)
            else:
                label = QLabel(label_text)
                label.setProperty('class', 'label')

                value_label = QLabel()
                value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                value_label.setProperty('class', 'value')
                value_label.setMinimumWidth(300)
                value_label.setWordWrap(True)

                self.basic_info_labels[field] = value_label
                ssh_layout.addWidget(label, row, 0, Qt.AlignmentFlag.AlignTop)
                ssh_layout.addWidget(value_label, row, 1, Qt.AlignmentFlag.AlignTop)
            row += 1

        # Add SNMP fields
        row = 0
        for label_text, field in snmp_fields:
            if field is None:
                # Section header
                section_label = QLabel(label_text)
                section_label.setProperty('class', 'section-header')
                snmp_layout.addWidget(section_label, row, 0, 1, 2)
            else:
                label = QLabel(label_text)
                label.setProperty('class', 'label')

                value_label = QLabel()
                value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                value_label.setProperty('class', 'value')
                value_label.setMinimumWidth(300)
                value_label.setWordWrap(True)

                self.basic_info_labels[field] = value_label
                snmp_layout.addWidget(label, row, 0, Qt.AlignmentFlag.AlignTop)
                snmp_layout.addWidget(value_label, row, 1, Qt.AlignmentFlag.AlignTop)
            row += 1

        # Add the groups to the scroll layout
        scroll_layout.addWidget(ssh_group)
        scroll_layout.addWidget(snmp_group)
        scroll_layout.addStretch()

        # Add the scroll area to the main layout
        layout.addWidget(scroll_area)


    def setup_interfaces_tab(self):
        layout = QVBoxLayout(self.interfaces_tab)
        layout.setContentsMargins(0, 0, 0, 0)

        self.interfaces_table = QTableView()
        self.interfaces_model = QSqlTableModel()
        self.interfaces_model.setQuery(QSqlQuery(f"""
            SELECT name, link_status, protocol_status, interface_type,
                   mac_address, mtu, ip_address, description
            FROM device_interfaces
            WHERE device_id = {self.device_id}
            ORDER BY name
        """))

        self.interfaces_table.setItemDelegate(InterfaceDelegate())

        # Set column headers
        headers = ["Name", "Link Status", "Protocol Status", "Type",
                   "MAC Address", "MTU", "IP Address", "Description"]
        for i, header in enumerate(headers):
            self.interfaces_model.setHeaderData(i, Qt.Orientation.Horizontal, header)

        self.interfaces_table.setModel(self.interfaces_model)
        self.interfaces_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.interfaces_table.setShowGrid(True)
        self.interfaces_table.setAlternatingRowColors(True)
        self.interfaces_table.verticalHeader().setVisible(False)

        layout.addWidget(self.interfaces_table)
    def setup_inventory_tab(self):
        layout = QVBoxLayout(self.inventory_tab)
        layout.setContentsMargins(0, 0, 0, 0)

        self.inventory_table = QTableView()
        self.inventory_model = QSqlTableModel()
        self.inventory_model.setQuery(QSqlQuery(f"""
            SELECT name as "Name",
                   description as "Description",
                   serial_number as "Serial Number",
                   product_id as "Product ID",
                   version_id as "Version ID",
                   vendor as "Vendor"
            FROM device_inventory
            WHERE device_id = {self.device_id}
            ORDER BY name
        """))

        self.inventory_table.setModel(self.inventory_model)
        self.inventory_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.inventory_table.setShowGrid(True)
        self.inventory_table.setAlternatingRowColors(True)
        self.inventory_table.verticalHeader().setVisible(False)

        layout.addWidget(self.inventory_table)


    def setup_mac_addresses_tab(self):
        layout = QVBoxLayout(self.mac_addresses_tab)
        layout.setContentsMargins(0, 0, 0, 0)

        self.mac_table = QTableView()
        self.mac_model = QSqlTableModel()
        self.mac_model.setQuery(QSqlQuery(f"""
            SELECT source_type as "Source", 
                   interface_name as "Interface",
                   mac_address as "MAC Address",
                   vlan_id as "VLAN",
                   vrf as "VRF"
            FROM mac_addresses_all
            WHERE device_id = {self.device_id}
            ORDER BY source_type, interface_name
        """))

        self.mac_table.setModel(self.mac_model)
        self.mac_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.mac_table.setShowGrid(True)
        self.mac_table.setAlternatingRowColors(True)
        self.mac_table.verticalHeader().setVisible(False)

        layout.addWidget(self.mac_table)

    def load_device_data(self):
        # Load basic device information and system info
        query = QSqlQuery()
        query.prepare("""
            SELECT d.*, dsi.*, du.years, du.weeks, du.days, du.hours, du.minutes
            FROM devices d
            LEFT JOIN device_system_info dsi ON d.device_id = dsi.device_id
            LEFT JOIN device_uptime du ON d.device_id = du.device_id
            WHERE d.device_id = ?
        """)
        query.addBindValue(self.device_id)
        query.exec()

        if query.next():
            # Update all labels
            for field, label in self.basic_info_labels.items():
                value = query.value(query.record().indexOf(field))
                if field == "uptime":
                    # Format uptime from separate fields
                    years = query.value(query.record().indexOf("years")) or 0
                    weeks = query.value(query.record().indexOf("weeks")) or 0
                    days = query.value(query.record().indexOf("days")) or 0
                    hours = query.value(query.record().indexOf("hours")) or 0
                    minutes = query.value(query.record().indexOf("minutes")) or 0

                    uptime_parts = []
                    if years: uptime_parts.append(f"{years} years")
                    if weeks: uptime_parts.append(f"{weeks} weeks")
                    if days: uptime_parts.append(f"{days} days")
                    if hours: uptime_parts.append(f"{hours} hours")
                    if minutes: uptime_parts.append(f"{minutes} minutes")

                    label.setText(", ".join(uptime_parts) if uptime_parts else "")
                else:
                    label.setText(str(value) if value else "")

        config_query = QSqlQuery()
        config_query.prepare("""
                SELECT config
                FROM device_configs
                WHERE device_id = ?
                ORDER BY collected_at DESC
                LIMIT 1
            """)
        config_query.addBindValue(self.device_id)
        config_query.exec()

        if config_query.next():
            config_text = config_query.value(0)
            self.config_text.setText(config_text if config_text else "No configuration available")
        else:
            self.config_text.setText("No configuration available")


    def update_theme(self, dark_mode: bool) -> None:
        colors = {
            'bg': '#1A1A1A' if dark_mode else '#FFFFFF',
            'value_bg': '#2A2A2A' if dark_mode else '#F5F5F5',
            'group_bg': '#262626' if dark_mode else '#F8F8F8',
            'tab_bg': '#2D2D2D' if dark_mode else '#EEEEEE',
            'tab_text': '#808080' if dark_mode else '#666666',
            'tab_selected_bg': '#303030' if dark_mode else '#FFFFFF',
            'tab_selected_text': '#00FFF2' if dark_mode else '#008B8B',
            'accent': '#00FFF2' if dark_mode else '#008B8B',
            'text': '#808080' if dark_mode else '#333333',
            'section_text': '#00FFF2' if dark_mode else '#008B8B',
            'border': '#404040' if dark_mode else '#DDDDDD',
            'table_bg': '#1A1A1A' if dark_mode else '#FFFFFF',
            'table_alt_bg': '#2D2D2D' if dark_mode else '#F5F5F5',
            'status_up': '#4CAF50',
            'status_down': '#F44336',
            'config_bg': '#262626' if dark_mode else '#F8F8F8',
            'config_text': '#E0E0E0' if dark_mode else '#000000',
        }

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors['bg']};
            }}
            QTabWidget::pane {{
                border-top: 1px solid {colors['text']};
                background-color: {colors['bg']};
            }}
            QWidget {{
                background-color: {colors['bg']};
                color: {colors['text']};
            }}
            QGroupBox {{
                background-color: {colors['group_bg']};
                border: 1px solid {colors['border']};
                border-radius: 6px;
                margin-top: 1em;
                padding-top: 10px;
                padding-bottom: 10px;
            }}
            QGroupBox::title {{
                color: {colors['section_text']};
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                font-weight: bold;
            }}
            QLabel.section-header {{
                color: {colors['section_text']};
                font-size: 14px;
                font-weight: bold;
                padding: 10px 0;
            }}
            QLabel.label {{
                font-weight: bold;
                color: {colors['text']};
            }}
            QLabel.value {{
                background-color: {colors['value_bg']};
                padding: 5px 8px;
                border-radius: 4px;
            }}
            QTableView {{
                background-color: {colors['table_bg']};
                alternate-background-color: {colors['table_alt_bg']};
                color: {colors['text']};
                border: none;
                selection-background-color: {colors['accent']};
                selection-color: {colors['bg']};
            }}
            QTableView::item {{
                border: none;
                padding: 5px;
            }}
            QHeaderView::section {{
                background-color: {colors['tab_bg']};
                color: {colors['text']};
                padding: 5px;
                border: none;
                border-bottom: 2px solid {colors['accent']};
            }}
            QTextEdit {{
                background-color: {colors['config_bg']};
                color: {colors['config_text']};
                font-family: Courier;
                border: 1px solid {colors['border']};
                padding: 10px;
                selection-background-color: {colors['accent']};
                selection-color: {colors['bg']};
            }}
        """)

    def toggle_theme(self, dark_mode):
        """Update theme when parent window theme changes"""
        self.dark_mode = dark_mode
        self.update_theme(dark_mode)