from PyQt6.QtWidgets import (QWidget, QTabWidget, QVBoxLayout, QApplication, QLineEdit, QCheckBox, QTableView, QHeaderView, QHBoxLayout)
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
        self.search_input.textChanged.connect(self.global_search)

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
        for col in range(self.model.columnCount()):
            self.proxy_model.set_column_filter(col, text)


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
