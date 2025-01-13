from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QMdiArea, QMdiSubWindow, QTableWidget, QTableWidgetItem,
                             QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QTextEdit,
                             QComboBox, QToolBar, QMessageBox)
from PyQt6.QtCore import Qt
import sqlite3


class DataViewerWindow(QMdiSubWindow):
    def __init__(self, db_path, table_name):
        super().__init__()
        self.setWindowTitle(f"Data Viewer - {table_name}")

        # Create main widget
        main_widget = QWidget()
        # main_widget.setStyleSheet("""
        #             QWidget {
        #                 background-color: #2d2d2d;
        #                 color: white;
        #             }
        #         """)
        layout = QVBoxLayout(main_widget)
        main_widget.setStyleSheet("""
            QMdiSubWindow::title {
                background-color: dark-grey !important;
                color: light-grey !important;
            }
            QMdiSubWindow::title::active {
                background-color: #00cc66 !important; /* Change active subwindow title bar to accent green */
                border: 2px solid green !important; /* Add a border to indicate active status */
            }
        """)
        # Create button layout
        button_layout = QHBoxLayout()
        export_btn = QPushButton("Export to CSV")
        export_btn.clicked.connect(self.export_to_csv)
        button_layout.addStretch()
        button_layout.addWidget(export_btn)
        layout.addLayout(button_layout)

        # Create table widget
        self.table = QTableWidget()
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)

        # Load data
        self.load_data(db_path, table_name)

        # Set the widget as the sub-window's widget
        self.setWidget(main_widget)
        self.resize(600, 400)
        self.setStyleSheet("""
            QMdiSubWindow {
            }
            QMdiSubWindow::title {
                background-color: dark-grey !important;
                color: light-grey !important;
            }
            QMdiSubWindow::title::active {
                background-color: #00cc66 !important; /* Change active subwindow title bar to accent green */
                border: 2px solid green !important; /* Add a border to indicate active status */
            }
        """)

    def export_to_csv(self):
        from PyQt6.QtWidgets import QFileDialog
        import csv

        # Get save file name
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Export CSV",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )

        if file_name:
            try:
                with open(file_name, 'w', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)

                    # Write headers
                    headers = []
                    for col in range(self.table.columnCount()):
                        headers.append(self.table.horizontalHeaderItem(col).text())
                    writer.writerow(headers)

                    # Write data
                    for row in range(self.table.rowCount()):
                        row_data = []
                        for col in range(self.table.columnCount()):
                            item = self.table.item(row, col)
                            row_data.append(item.text() if item else "")
                        writer.writerow(row_data)

                QMessageBox.information(self, "Success", "Data exported successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error exporting data: {str(e)}")

    def load_data(self, db_path, table_name):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Get column names
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [info[1] for info in cursor.fetchall()]

            # Get data
            cursor.execute(f"SELECT * FROM {table_name}")
            data = cursor.fetchall()

            # Set up table
            self.table.setColumnCount(len(columns))
            self.table.setRowCount(len(data))
            self.table.setHorizontalHeaderLabels(columns)

            # Populate data
            for i, row in enumerate(data):
                for j, value in enumerate(row):
                    item = QTableWidgetItem(str(value))
                    self.table.setItem(i, j, item)

            conn.close()

        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Error loading data: {str(e)}")


class SQLQueryWindow(QMdiSubWindow):
    def __init__(self, db_path):
        super().__init__()
        self.setWindowTitle("SQL Query Tool")
        self.db_path = db_path

        # Create main widget
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)

        # Create query editor
        self.query_editor = QTextEdit()
        self.query_editor.setPlaceholderText("Enter your SQL query here...")
        layout.addWidget(self.query_editor)

        # Create button layout
        button_layout = QHBoxLayout()
        run_button = QPushButton("Run Query")
        run_button.clicked.connect(self.run_query)
        export_button = QPushButton("Export to CSV")
        export_button.clicked.connect(self.export_to_csv)
        button_layout.addStretch()
        button_layout.addWidget(run_button)
        button_layout.addWidget(export_button)
        layout.addLayout(button_layout)

        # Create results table
        self.results_table = QTableWidget()
        layout.addWidget(self.results_table)

        # Set the widget as the sub-window's widget
        self.setWidget(main_widget)
        self.resize(800, 600)
        self.setStyleSheet("""
            QMdiSubWindow {
            }
            QMdiSubWindow::title {
                background-color: dark-grey !important;
                color: light-grey !important;
            }
            QMdiSubWindow::title::active {
                background-color: #00cc66 !important; /* Change active subwindow title bar to accent green */
                border: 2px solid green !important; /* Add a border to indicate active status */
            }
        """)


    def export_to_csv(self):
        from PyQt6.QtWidgets import QFileDialog
        import csv

        if self.results_table.rowCount() == 0:
            QMessageBox.warning(self, "No Data", "There is no data to export. Run a query first.")
            return

        # Get save file name
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Export CSV",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )

        if file_name:
            try:
                with open(file_name, 'w', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)

                    # Write headers
                    headers = []
                    for col in range(self.results_table.columnCount()):
                        headers.append(self.results_table.horizontalHeaderItem(col).text())
                    writer.writerow(headers)

                    # Write data
                    for row in range(self.results_table.rowCount()):
                        row_data = []
                        for col in range(self.results_table.columnCount()):
                            item = self.results_table.item(row, col)
                            row_data.append(item.text() if item else "")
                        writer.writerow(row_data)

                QMessageBox.information(self, "Success", "Data exported successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error exporting data: {str(e)}")

    def run_query(self):
        query = self.query_editor.toPlainText().strip()
        if not query:
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Execute query
            cursor.execute(query)

            # Get column names from cursor description
            columns = [description[0] for description in cursor.description]

            # Fetch data
            data = cursor.fetchall()

            # Set up table
            self.results_table.setColumnCount(len(columns))
            self.results_table.setRowCount(len(data))
            self.results_table.setHorizontalHeaderLabels(columns)

            # Populate data
            for i, row in enumerate(data):
                for j, value in enumerate(row):
                    item = QTableWidgetItem(str(value))
                    self.results_table.setItem(i, j, item)

            conn.close()

        except sqlite3.Error as e:
            QMessageBox.critical(self, "Query Error", f"Error executing query: {str(e)}")


class MDIWorkspace(QWidget):

    def __init__(self, db_path, parent=None):
        super().__init__(parent)
        self.db_path = db_path

        # Create main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create toolbar
        toolbar = QToolBar()
        layout.addWidget(toolbar)

        # Add table selector
        self.table_selector = QComboBox()
        toolbar.addWidget(self.table_selector)
        self.populate_table_list()

        # Add buttons
        view_data_btn = QPushButton("View Data")
        view_data_btn.clicked.connect(self.create_data_viewer)
        toolbar.addWidget(view_data_btn)

        toolbar.addSeparator()

        sql_query_btn = QPushButton("SQL Query")
        sql_query_btn.clicked.connect(self.create_sql_query)
        toolbar.addWidget(sql_query_btn)

        # Create MDI area
        self.mdi_area = QMdiArea()
        layout.addWidget(self.mdi_area)

        # Apply the base styling
        # self.setStyleSheet("""
        #     QWidget {
        #         background-color: #1e1e1e;
        #         color: white;
        #     }
        #     QToolBar {
        #         background-color: #2d2d2d;
        #         border: none;
        #         spacing: 5px;
        #         padding: 5px;
        #     }
        #     QPushButton {
        #         background-color: #3d3d3d;
        #         border: none;
        #         padding: 5px 10px;
        #         border-radius: 3px;
        #     }
        #     QPushButton:hover {
        #         background-color: #4d4d4d;
        #     }
        #     QComboBox {
        #         background-color: #3d3d3d;
        #         border: none;
        #         padding: 5px;
        #         border-radius: 3px;
        #         min-width: 200px;
        #     }
        # """)

        # Apply MDI-specific styling directly to the MDI area
        # self.mdi_area.setStyleSheet("""
        #     QMdiArea {
        #         background-color: #1e1e1e;
        #     }
        #     QMdiSubWindow {
        #         background-color: #2d2d2d;
        #
        #     }
        #     QMdiSubWindow:active {
        #         background-color: #2d2d2d;
        #         border: 2px solid #4CAF50;
        #     }
        #     QMdiSubWindow QWidget {
        #         background-color: #2d2d2d;
        #         color: white;
        #     }
        #     QTableWidget {
        #         background-color: #1e1e1e;
        #         color: white;
        #         gridline-color: #3d3d3d;
        #     }
        #     QHeaderView::section {
        #         background-color: #2d2d2d;
        #         color: white;
        #         padding: 5px;
        #         border: none;
        #     }
        #     QTextEdit {
        #         background-color: #1e1e1e;
        #         color: white;
        #         border: none;
        #     }
        # """)

    def populate_table_list(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get list of tables and views with better organization
            cursor.execute("""
                SELECT 
                    name,
                    CASE 
                        WHEN type = 'table' AND name LIKE 'device_%' THEN 'Device Table: '
                        WHEN type = 'table' THEN 'Table: '
                        WHEN name LIKE 'v_device_%' THEN 'Device View: '
                        WHEN name LIKE 'v_interface_%' THEN 'Interface View: '
                        WHEN name LIKE 'v_%' THEN 'View: '
                    END || name as display_name,
                    CASE 
                        WHEN type = 'table' AND name LIKE 'device_%' THEN 1
                        WHEN type = 'table' THEN 2
                        WHEN name LIKE 'v_%' THEN 3
                        ELSE 4
                    END as sort_order
                FROM sqlite_master 
                WHERE type IN ('table', 'view')
                ORDER BY sort_order, name
            """)
            items = cursor.fetchall()

            self.table_selector.clear()
            for name, display_name, _ in items:
                self.table_selector.addItem(display_name, name)  # Store actual name as item data

            conn.close()

        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Error loading tables and views: {str(e)}")

    def create_data_viewer(self):
        # Get the actual table/view name from the stored data
        current_index = self.table_selector.currentIndex()
        if current_index >= 0:
            table_name = self.table_selector.itemData(current_index)
            if table_name:
                sub_window = DataViewerWindow(self.db_path, table_name)
                # sub_window.setWindowFlags(
                #     Qt.WindowType.Window | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowCloseButtonHint)
                sub_window.setWindowFlags(
                    Qt.WindowType.Window |
                    Qt.WindowType.CustomizeWindowHint |
                    Qt.WindowType.WindowTitleHint |
                    Qt.WindowType.WindowCloseButtonHint |
                    Qt.WindowType.WindowMinMaxButtonsHint
                )
                sub_window.setWindowIcon(QIcon(None))  # Set an empty icon
                self.mdi_area.addSubWindow(sub_window)
                sub_window.show()

    def create_sql_query(self):
        sub_window = SQLQueryWindow(self.db_path)
        self.mdi_area.addSubWindow(sub_window)
        sub_window.show()


if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication

    # Create the application
    app = QApplication(sys.argv)

    # Create a simple container window to host our MDI widget
    container = QWidget()
    container.setWindowTitle("MDI Data Browser Test")
    layout = QVBoxLayout(container)

    # Create and add the MDI workspace
    # Update this path to match your database location
    mdi_workspace = MDIWorkspace("surveyor/cmdb.db")
    layout.addWidget(mdi_workspace)

    # Set a reasonable default size
    container.resize(1200, 800)

    # Show the window
    container.show()

    # Start the event loop
    sys.exit(app.exec())