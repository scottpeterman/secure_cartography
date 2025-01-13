from PyQt6.QtWidgets import (QWidget, QTabWidget, QVBoxLayout, QApplication, QLineEdit, QCheckBox, QTableView,
                             QHeaderView, QHBoxLayout, QTreeWidgetItem, QDialog, QPushButton, QTreeWidget)
from PyQt6.QtCore import Qt, QSettings, QSortFilterProxyModel
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtSql import QSqlDatabase, QSqlTableModel, QSqlQuery

from surveyor.surveyor_device_dialog import DeviceDetailDialog


class ColumnFilterProxyModel(QSortFilterProxyModel):
    def __init__(self):
        super().__init__()
        self.column_filters = {}

    def filterAcceptsRow(self, source_row, source_parent):
        for column, filter_text in self.column_filters.items():
            if filter_text:
                source_index = self.sourceModel().index(source_row, column, source_parent)
                data = str(self.sourceModel().data(source_index))
                if filter_text.lower() not in data.lower():
                    return False
        return True

    def set_column_filter(self, column, filter_text):
        self.column_filters[column] = filter_text
        self.invalidateFilter()


class DevicesTab(QWidget):
    def __init__(self):
        super().__init__()
        self.settings = QSettings('NetworkMapper', 'ResourceBrowser')
        self.dark_mode = self.settings.value('dark_mode', defaultValue=True, type=bool)

        self.setup_ui()
        self.setup_theme_support()

        self.theme_toggle.setChecked(self.dark_mode)
        self.toggle_theme(self.dark_mode)

    def setup_ui(self):
        layout = QVBoxLayout()
        top_layout = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Global Search...")
        self.search_input.returnPressed.connect(lambda: self.global_search(self.search_input.text()))

        top_layout.addWidget(self.search_input)

        self.theme_toggle = QCheckBox("Dark Mode")
        self.theme_toggle.toggled.connect(self.toggle_theme)
        top_layout.addWidget(self.theme_toggle)

        layout.addLayout(top_layout)

        filter_layout = QHBoxLayout()
        self.column_filters = {}
        layout.addLayout(filter_layout)

        self.table = QTableView()
        self.model = QSqlTableModel()

        self.model.setQuery(QSqlQuery("""
            SELECT 
                device_id,
                name,
                ip_address,
                platform,
                vendor,
                model,
                software_version,
                serial_numbers,
                mac_addresses,
                last_updated
            FROM device_summary
            ORDER BY name
        """))

        self.proxy_model = ColumnFilterProxyModel()
        self.proxy_model.setSourceModel(self.model)
        self.table.setModel(self.proxy_model)

        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)

        self.table.hideColumn(0)

        for col in range(1, self.model.columnCount()):
            column_name = self.model.headerData(col, Qt.Orientation.Horizontal)
            filter_input = QLineEdit()
            filter_input.setPlaceholderText(f"Filter {column_name}...")
            filter_input.textChanged.connect(lambda text, col=col: self.proxy_model.set_column_filter(col, text))
            self.column_filters[col] = filter_input
            filter_layout.addWidget(filter_input)
        self.table.doubleClicked.connect(self.open_device_detail)

        layout.addWidget(self.table)
        self.setLayout(layout)
        # self.search_input.textChanged.connect(self.global_search)

    def open_device_detail(self, index):
        # Get the device_id from the hidden column
        device_id_index = self.proxy_model.index(index.row(), 0)
        device_id = self.proxy_model.data(device_id_index)

        # Open the DeviceDetailDialog
        dialog = DeviceDetailDialog(device_id, self)
        dialog.exec()

    def setup_theme_support(self):
        self.dark_palette = QPalette()
        self.light_palette = QPalette()

        self.dark_palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
        self.dark_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        self.dark_palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
        self.dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(42, 42, 42))
        self.dark_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)

        self.light_palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
        self.light_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.black)
        self.light_palette.setColor(QPalette.ColorRole.Base, Qt.GlobalColor.white)
        self.light_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.black)

    def apply_table_theme(self, dark_mode):
        if dark_mode:
            self.table.setStyleSheet("""
                QTableView {
                    background-color: #2D2D2D;
                    color: white;
                }
            """)
        else:
            self.table.setStyleSheet("""
                QTableView {
                    background-color: white;
                    color: black;
                }
            """)

    def toggle_theme(self, checked):
        self.dark_mode = checked
        app = QApplication.instance()

        if checked:
            app.setPalette(self.dark_palette)
            self.apply_table_theme(True)
        else:
            app.setPalette(self.light_palette)
            self.apply_table_theme(False)

        self.settings.setValue('dark_mode', checked)

    def global_search(self, text):
        if len(text) < 3:  # Only search if at least 3 characters
            return

        results = []
        search_term = f"%{text}%"

        query = QSqlQuery()

        # Print the number of parameters we're binding
        print(f"Binding search term: {search_term}")

        query.prepare("""
            WITH matches AS (
                -- Device direct matches
                SELECT 
                    d.device_id,
                    d.name as device_name,
                    d.ip_address,
                    'Device' as type,
                    CASE 
                        WHEN d.name LIKE ? THEN d.name
                        WHEN d.ip_address LIKE ? THEN d.ip_address
                        WHEN d.hostname LIKE ? THEN d.hostname
                    END as match,
                    'Basic device information' as details
                FROM devices d
                WHERE d.name LIKE ? 
                   OR d.ip_address LIKE ? 
                   OR d.hostname LIKE ?

                UNION

                -- Interface matches
                SELECT 
                    d.device_id,
                    d.name as device_name,
                    d.ip_address,
                    'Interface' as type,
                    di.name as match,
                    CASE 
                        WHEN di.ip_address LIKE ? THEN 'IP: ' || di.ip_address
                        WHEN di.mac_address LIKE ? THEN 'MAC: ' || di.mac_address
                        ELSE di.description
                    END as details
                FROM devices d
                JOIN device_interfaces di ON d.device_id = di.device_id
                WHERE di.ip_address LIKE ?
                   OR di.mac_address LIKE ?
                   OR di.name LIKE ?

                UNION

                -- MAC table matches
                SELECT 
                    d.device_id,
                    d.name as device_name,
                    d.ip_address,
                    'MAC Table Entry' as type,
                    dmt.mac_address as match,
                    'VLAN: ' || dmt.vlan_id || ', Interface: ' || dmt.interface as details
                FROM devices d
                JOIN device_mac_table dmt ON d.device_id = dmt.device_id
                WHERE dmt.mac_address LIKE ?

                UNION

                -- ARP table matches
                SELECT 
                    d.device_id,
                    d.name as device_name,
                    d.ip_address,
                    'ARP Entry' as type,
                    dat.ip_address || ' -> ' || dat.mac_address as match,
                    'Interface: ' || dat.interface || 
                    CASE WHEN dat.vrf IS NOT NULL THEN ', VRF: ' || dat.vrf ELSE '' END as details
                FROM devices d
                JOIN device_arp_table dat ON d.device_id = dat.device_id
                WHERE dat.ip_address LIKE ?
                   OR dat.mac_address LIKE ?

                UNION

                -- Config matches
                SELECT 
                    d.device_id,
                    d.name as device_name,
                    d.ip_address,
                    'Configuration' as type,
                    SUBSTR(dc.config, INSTR(LOWER(dc.config), LOWER(?)) - 30, 60) as match,
                    'Found in device configuration' as details
                FROM devices d
                JOIN device_configs dc ON d.device_id = dc.device_id
                WHERE dc.config LIKE ?
                AND dc.collected_at = (
                    SELECT MAX(collected_at) 
                    FROM device_configs 
                    WHERE device_id = d.device_id
                )
            )
            SELECT DISTINCT * FROM matches
            ORDER BY device_name, type
        """)

        # Bind exactly 16 parameters
        for i in range(16):
            query.addBindValue(search_term)
            print(f"Bound parameter {i}")

        if query.exec():
            print("Query executed successfully")
            while query.next():
                results.append({
                    'device_id': query.value(0),
                    'device_name': query.value(1),
                    'ip_address': query.value(2),
                    'type': query.value(3),
                    'match': query.value(4),
                    'details': query.value(5)
                })
        else:
            print("Query error:", query.lastError().text())

        if results:
            dialog = SearchResultsDialog(text, results, self)
            dialog.exec()

class NetworkResourceBrowserWidget(QWidget):
    def __init__(self, db_path, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.init_ui()

    def init_ui(self):
        self.db = QSqlDatabase.addDatabase("QSQLITE")
        self.db.setDatabaseName(self.db_path)
        if not self.db.open():
            raise Exception(f"Failed to open database at {self.db_path}")

        self.layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        self.devices_tab = DevicesTab()
        self.tabs.addTab(self.devices_tab, "Devices")
        self.setLayout(self.layout)


class SearchResultsDialog(QDialog):
    def __init__(self, search_text, results, parent=None):
        super().__init__(parent)
        self.setup_ui(search_text, results)

    def setup_ui(self, search_text, results):
        self.setWindowTitle("Search Results")
        self.resize(800, 600)
        layout = QVBoxLayout(self)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Type", "Match", "Device", "Details"])
        self.tree.setAlternatingRowColors(True)
        self.populate_results(search_text, results)
        layout.addWidget(self.tree)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)
        self.tree.itemDoubleClicked.connect(self.open_device_detail)

    def extract_ip(self, text):
        """Extract IP address from text"""
        if not text:
            return None
        # Handle "IP: x.x.x.x" format
        if 'IP: ' in text:
            text = text.split('IP: ')[1]
        # Handle CIDR notation
        if '/' in text:
            text = text.split('/')[0]
        # Handle "x.x.x.x -> MAC" format
        if ' -> ' in text:
            text = text.split(' -> ')[0]
        # If it looks like an IP, return it
        if text.replace('.', '').isdigit() and text.count('.') == 3:
            return text
        return None

    def find_matching_line(self, device_id, search_text):
        """Find and return the line containing the search text, along with line number"""
        if not device_id or not search_text:
            return None, None, None

        # Use QSqlQuery since we're already in Qt
        query = QSqlQuery()
        query.prepare("SELECT latest_config FROM device_summary WHERE device_id = ?")
        query.addBindValue(device_id)

        if not query.exec() or not query.next():
            print("Failed to get config:", query.lastError().text())
            return None, None, None

        config_text = query.value(0)
        if not config_text:
            return None, None, None

        # Remove % symbols from search text if present
        clean_search = search_text.strip('%')

        # Split into lines and clean them
        lines = [line.strip() for line in config_text.split('\n') if line.strip()]

        print(f"Searching for: '{clean_search}' in device {device_id}")  # Debug print
        for i, line in enumerate(lines, 1):
            if clean_search.lower() in line.lower():  # Case-insensitive search
                return line.strip(), i, len(lines)

        # If no match found, return None with total lines count
        return None, None, len(lines)

    def is_exact_match(self, search_text, field_text):
        """Check for exact matches, with special handling for IPs"""
        if not search_text or not field_text:
            return False

        # Try to extract IPs from both texts
        search_ip = self.extract_ip(search_text)
        field_ip = self.extract_ip(field_text)

        # If searching for an IP and found an IP, compare them
        if search_ip and field_ip:
            return search_ip == field_ip

        # For non-IP searches, do exact string match
        return search_text == field_text

    def populate_results(self, search_text, results):
        devices = {}

        # Extract search text from the first result's match if not provided
        if not search_text and results and len(results) > 0:
            for key in ['match', 'details']:
                if '%' in str(results[0].get(key, '')):
                    search_text = str(results[0][key]).strip('%')
                    break

        print(f"Search text: {search_text}")  # Debug print

        # First Pass: Collect potential matches
        potential_matches = {}
        for result in results:
            device_id = result['device_id']
            if device_id not in potential_matches:
                potential_matches[device_id] = []
            potential_matches[device_id].append(result)

        # Second Pass: Apply exact match logic and populate the tree
        for device_id, device_results in potential_matches.items():
            # Add the device as the root entry if not already added
            if device_id not in devices:
                root_device = device_results[0]  # Assume the first result represents the device
                devices[device_id] = QTreeWidgetItem(self.tree, [
                    "Device",
                    root_device['device_name'],
                    "",
                    f"IP: {root_device['ip_address']}"
                ])

            # Add child entries
            for result in device_results:
                # Always show Configuration and Device results
                if result['type'] in ['Device', 'Configuration']:
                    add_child = True
                # For other types, show if there's no search text or if it's an exact match
                else:
                    if not search_text:
                        add_child = True
                    else:
                        add_child = self.is_exact_match(search_text, result['match'])

                if add_child:
                    display_match = result['match']
                    details = result['details']

                    if result['type'] == 'Configuration':
                        # Here we actually call our new database-searching function
                        matching_line, line_num, total_lines = self.find_matching_line(device_id, search_text)
                        if line_num is not None:
                            display_match = matching_line
                            details = f"Line {line_num}/{total_lines}: {matching_line}"
                        else:
                            details = f"Search term not found in configuration"

                    child = QTreeWidgetItem(devices[device_id], [
                        result['type'],
                        display_match,
                        result['device_name'],
                        details
                    ])
                    child.setData(0, Qt.ItemDataRole.UserRole, device_id)

        self.tree.expandAll()

    def open_device_detail(self, item):
        device_id = item.data(0, Qt.ItemDataRole.UserRole)
        if device_id:
            dialog = DeviceDetailDialog(device_id, self)
            dialog.exec()


if __name__ == "__main__":
    import sys

    class StandaloneBrowser(QApplication):
        def __init__(self, db_path, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.widget = NetworkResourceBrowserWidget(db_path)
            self.widget.setWindowTitle("Surveyor - Standalone Mode")
            self.widget.resize(1200, 800)
            self.widget.show()

    db_path = "cmdb.db"
    app = StandaloneBrowser(db_path, sys.argv)
    sys.exit(app.exec())
