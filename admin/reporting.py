from PyQt6 import QtCharts
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QScrollArea, QFrame, QLabel, QApplication)
from PyQt6.QtCharts import QChart, QChartView, QPieSeries, QBarSeries, QBarSet, QBarCategoryAxis, QValueAxis
from PyQt6.QtCore import QMargins
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PyQt6.QtSql import QSqlQuery, QSqlDatabase
from PyQt6.QtGui import QPalette, QColor, QFont, QPainter
from enum import Enum, auto
from dataclasses import dataclass


class Theme(Enum):
    LIGHT = auto()
    DARK = auto()


@dataclass
class ThemeColors:
    background: str
    surface: str
    primary: str
    text: str
    secondary_text: str
    border: str
    chart_colors: list[str]


class NetworkReportModel:
    def __init__(self, db: QSqlDatabase):
        self.db = db
        self.device_summary = self._fetch_device_summary()
        self.platform_distribution = self._fetch_platform_distribution()
        self.software_distribution = self._fetch_software_distribution()
        self.interface_status = self._fetch_interface_status()
        self.memory_stats = self._fetch_memory_stats()
        self.uptime_summary = self._fetch_uptime_summary()
        self.interface_errors = self._fetch_interface_errors()

    def _fetch_device_summary(self):
        query = QSqlQuery("""
            WITH device_counts AS (
                SELECT 
                    COUNT(DISTINCT d.device_id) as total_devices,
                    COUNT(DISTINCT d.platform) as platform_count,
                    COUNT(DISTINCT d.vendor) as vendor_count,
                    COUNT(DISTINCT dsi.software_version) as software_versions,
                    COUNT(DISTINCT di.name) as total_interfaces
                FROM devices d
                LEFT JOIN device_system_info dsi ON d.device_id = dsi.device_id
                LEFT JOIN device_interfaces di ON d.device_id = di.device_id
            ),
            inventory_counts AS (
                SELECT 
                    COUNT(DISTINCT inv.serial_number) as unique_serials,
                    COUNT(DISTINCT inv.product_id) as unique_products
                FROM device_inventory inv
            )
            SELECT 
                dc.total_devices,
                dc.platform_count,
                dc.vendor_count,
                dc.software_versions,
                dc.total_interfaces,
                ic.unique_serials,
                ic.unique_products
            FROM device_counts dc
            CROSS JOIN inventory_counts ic
        """)
        if query.exec() and query.next():
            return {
                'total_devices': query.value(0),
                'platforms': query.value(1),
                'vendors': query.value(2),
                'software_versions': query.value(3),
                'total_interfaces': query.value(4),
                'unique_serials': query.value(5),
                'unique_products': query.value(6)
            }
        return {
            'total_devices': 0, 'platforms': 0, 'vendors': 0,
            'software_versions': 0, 'total_interfaces': 0,
            'unique_serials': 0, 'unique_products': 0
        }

    def _fetch_platform_distribution(self):
        platforms = []
        counts = []
        query = QSqlQuery("""
            SELECT platform, COUNT(*) as count
            FROM devices
            GROUP BY platform
            ORDER BY count DESC
        """)
        while query.next():
            platforms.append(query.value(0))
            counts.append(query.value(1))
        return {'platforms': platforms, 'counts': counts}

    def _fetch_software_distribution(self):
        versions = []
        counts = []
        query = QSqlQuery("""
            SELECT software_version, COUNT(*) as count
            FROM device_system_info
            GROUP BY software_version
            ORDER BY count DESC
            LIMIT 10
        """)
        while query.next():
            versions.append(query.value(0))
            counts.append(query.value(1))
        return {'versions': versions, 'counts': counts}

    def _fetch_memory_stats(self):
        query = QSqlQuery("""
            SELECT 
                AVG(total_memory) as avg_total_memory,
                AVG(free_memory) as avg_free_memory,
                MIN(free_memory) as min_free_memory,
                COUNT(*) as device_count
            FROM device_hardware
            WHERE total_memory > 0 AND free_memory > 0
            GROUP BY device_id
        """)
        if query.exec() and query.next():
            return {
                'avg_total': query.value(0) or 0,
                'avg_free': query.value(1) or 0,
                'min_free': query.value(2) or 0,
                'device_count': query.value(3) or 0
            }
        return {'avg_total': 0, 'avg_free': 0, 'min_free': 0, 'device_count': 0}

    def _fetch_uptime_summary(self):
        query = QSqlQuery("""
            SELECT 
                AVG(years * 365 + weeks * 7 + days + hours/24.0 + minutes/1440.0) as avg_uptime_days,
                MIN(years * 365 + weeks * 7 + days + hours/24.0 + minutes/1440.0) as min_uptime_days,
                MAX(years * 365 + weeks * 7 + days + hours/24.0 + minutes/1440.0) as max_uptime_days
            FROM device_uptime
        """)
        if query.exec() and query.next():
            return {
                'avg_uptime': query.value(0) or 0,
                'min_uptime': query.value(1) or 0,
                'max_uptime': query.value(2) or 0
            }
        return {'avg_uptime': 0, 'min_uptime': 0, 'max_uptime': 0}

    def _fetch_interface_errors(self):
        query = QSqlQuery("""
            WITH error_stats AS (
                SELECT 
                    device_id,
                    name as interface_name,
                    input_errors,
                    output_errors,
                    input_errors + output_errors as total_errors
                FROM device_interfaces
                WHERE input_errors > 0 OR output_errors > 0
                ORDER BY total_errors DESC
                LIMIT 10
            )
            SELECT 
                d.name as device_name,
                es.interface_name,
                es.input_errors,
                es.output_errors,
                es.total_errors
            FROM error_stats es
            JOIN devices d ON es.device_id = d.device_id
        """)
        errors = []
        while query.next():
            errors.append({
                'device_name': query.value(0),
                'interface_name': query.value(1),
                'input_errors': query.value(2),
                'output_errors': query.value(3),
                'total_errors': query.value(4)
            })
        return errors

    def _fetch_interface_status(self):
        query = QSqlQuery("""
            WITH interface_stats AS (
                SELECT 
                    link_status,
                    protocol_status,
                    COUNT(*) as count,
                    AVG(CAST(REPLACE(REPLACE(bandwidth, 'Gbps', '000'), 'Mbps', '') AS INTEGER)) as avg_bandwidth
                FROM device_interfaces
                WHERE link_status IS NOT NULL
                GROUP BY link_status, protocol_status
            )
            SELECT 
                link_status,
                protocol_status,
                count,
                avg_bandwidth
            FROM interface_stats
            ORDER BY count DESC
        """)
        status = []
        while query.next():
            status.append({
                'link_status': query.value(0),
                'protocol_status': query.value(1),
                'count': query.value(2),
                'avg_bandwidth': query.value(3)
            })
        return status


class ThemeManager:
    DARK_THEME = ThemeColors(
        background="#1A1A1A",
        surface="#2D2D2D",
        primary="#00FFF2",
        text="#FFFFFF",
        secondary_text="#808080",
        border="#404040",
        chart_colors=["#00FFF2", "#1AFFCD", "#33FFB2", "#47FF99"]
    )

    LIGHT_THEME = ThemeColors(
        background="#F5F5F5",
        surface="#FFFFFF",
        primary="#0088A3",
        text="#000000",
        secondary_text="#666666",
        border="#E0E0E0",
        chart_colors=["#0088A3", "#00A3B8", "#00BDCC", "#00D6E1"]
    )

    @classmethod
    def get_theme_colors(cls, theme: Theme) -> ThemeColors:
        return cls.DARK_THEME if theme == Theme.DARK else cls.LIGHT_THEME

    @classmethod
    def get_palette(cls, theme: Theme) -> QPalette:
        colors = cls.get_theme_colors(theme)
        palette = QPalette()

        if theme == Theme.DARK:
            palette.setColor(QPalette.ColorRole.Window, QColor(colors.background))
            palette.setColor(QPalette.ColorRole.WindowText, QColor(colors.text))
            palette.setColor(QPalette.ColorRole.Base, QColor(colors.surface))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(colors.border))
            palette.setColor(QPalette.ColorRole.Text, QColor(colors.text))
        else:
            palette.setColor(QPalette.ColorRole.Window, QColor(colors.background))
            palette.setColor(QPalette.ColorRole.WindowText, QColor(colors.text))
            palette.setColor(QPalette.ColorRole.Base, QColor(colors.surface))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(colors.border))
            palette.setColor(QPalette.ColorRole.Text, QColor(colors.text))

        return palette


class ReportSection(QFrame):
    def __init__(self, title, theme: Theme, parent=None):
        super().__init__(parent)
        self.theme_colors = ThemeManager.get_theme_colors(theme)
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setup_ui(title)

    def setup_ui(self, title):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            QLabel {{
                font-size: 16px;
                font-weight: bold;
                color: {self.theme_colors.primary};
            }}
        """)
        layout.addWidget(title_label)

        self.content_layout = QVBoxLayout()
        layout.addLayout(self.content_layout)

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {self.theme_colors.surface};
                border: 1px solid {self.theme_colors.border};
                border-radius: 5px;
            }}
        """)


class NetworkReport(QWidget):
    def __init__(self, db_path, theme: Theme = Theme.DARK, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.theme_colors = ThemeManager.get_theme_colors(theme)

        self.db = QSqlDatabase.addDatabase("QSQLITE")
        self.db.setDatabaseName(db_path)
        if not self.db.open():
            raise Exception(f"Failed to open database at {db_path}")

        self.model = NetworkReportModel(self.db)
        self.setup_ui()
        self.update_report()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setStyleSheet(f"background-color: {self.theme_colors.surface};")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Network Infrastructure Report")
        title.setStyleSheet(f"""
            QLabel {{
                font-size: 24px;
                font-weight: bold;
                color: {self.theme_colors.text};
            }}
        """)

        theme_btn = QPushButton("Toggle Theme")
        theme_btn.setFixedWidth(120)
        theme_btn.clicked.connect(self.toggle_theme)

        export_btn = QPushButton("Export to PDF")
        export_btn.setFixedWidth(120)

        buttons_style = f"""
            QPushButton {{
                background-color: {self.theme_colors.primary};
                color: {self.theme_colors.surface};
                border: none;
                padding: 5px;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                background-color: {self.theme_colors.chart_colors[1]};
            }}
        """
        theme_btn.setStyleSheet(buttons_style)
        export_btn.setStyleSheet(buttons_style)

        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(theme_btn)
        header_layout.addWidget(export_btn)

        main_layout.addWidget(header)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content.setStyleSheet(f"background-color: {self.theme_colors.background};")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(20)

        # Sections
        self.device_summary = ReportSection("Device Summary", self.theme)
        content_layout.addWidget(self.device_summary)

        self.software_dist = ReportSection("Software Version Distribution", self.theme)
        content_layout.addWidget(self.software_dist)

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def toggle_theme(self):
        self.theme = Theme.LIGHT if self.theme == Theme.DARK else Theme.DARK
        self.theme_colors = ThemeManager.get_theme_colors(self.theme)

        # Update application palette
        app = QApplication.instance()
        app.setPalette(ThemeManager.get_palette(self.theme))

        # Recreate UI with new theme
        # Remove all widgets
        for i in reversed(range(self.layout().count())):
            widget = self.layout().itemAt(i).widget()
            if widget:
                widget.setParent(None)

        # Setup UI again with new theme
        self.setup_ui()
        self.update_report()

    def update_software_distribution(self):
        chart = QChart()
        chart.setBackgroundBrush(QColor(self.theme_colors.surface))
        chart.setTitleBrush(QColor(self.theme_colors.text))
        chart.setTitleFont(QFont("Arial", 12))

        series = QBarSeries()
        software_data = self.model.software_distribution

        bar_set = QBarSet("Devices")
        bar_set.setColor(QColor(self.theme_colors.primary))

        for count in software_data['counts']:
            bar_set.append(count)

        series.append(bar_set)
        chart.addSeries(series)

        # Configure axes
        axis_x = QBarCategoryAxis()
        axis_x.append(software_data['versions'])
        axis_x.setLabelsColor(QColor(self.theme_colors.text))
        axis_x.setLabelsAngle(-45)
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QValueAxis()
        axis_y.setLabelsColor(QColor(self.theme_colors.text))
        axis_y.setGridLineColor(QColor(self.theme_colors.border))
        axis_y.setGridLineVisible(True)
        axis_y.setMinorGridLineVisible(False)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

        chart.setTitle("Software Version Distribution")
        chart.legend().setVisible(False)

        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        chart_view.setMinimumHeight(300)

        # Clear existing content
        for i in reversed(range(self.software_dist.content_layout.count())):
            widget = self.software_dist.content_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        self.software_dist.content_layout.addWidget(chart_view)

    def update_device_summary(self):
        summary_widget = QWidget()
        summary_layout = QHBoxLayout(summary_widget)

        data = self.model.device_summary
        metrics = [
            (f"Total Devices: {data['total_devices']}", "Devices in network"),
            (f"Platforms: {data['platforms']}", "Unique platforms"),
            (f"Vendors: {data['vendors']}", "Different vendors")
        ]

        stats_layout = QVBoxLayout()
        for metric, description in metrics:
            metric_widget = QFrame()
            metric_widget.setStyleSheet(f"""
                QFrame {{
                    background-color: {self.theme_colors.surface};
                    border: 1px solid {self.theme_colors.border};
                    border-radius: 5px;
                    padding: 10px;
                }}
            """)
            metric_layout = QVBoxLayout(metric_widget)

            value_label = QLabel(metric)
            value_label.setStyleSheet(f"""
                QLabel {{
                    font-size: 18px;
                    font-weight: bold;
                    color: {self.theme_colors.text};
                }}
            """)
            desc_label = QLabel(description)
            desc_label.setStyleSheet(f"color: {self.theme_colors.secondary_text};")

            metric_layout.addWidget(value_label)
            metric_layout.addWidget(desc_label)
            stats_layout.addWidget(metric_widget)

        # Platform distribution chart
        chart = QChart()
        chart.setBackgroundBrush(QColor(self.theme_colors.surface))
        chart.setTitleBrush(QColor(self.theme_colors.text))
        chart.setTitleFont(QFont("Arial", 12))

        series = QPieSeries()
        platform_data = self.model.platform_distribution
        for i, (platform, count) in enumerate(zip(platform_data['platforms'], platform_data['counts'])):
            slice = series.append(platform, count)
            color = QColor(self.theme_colors.chart_colors[i % len(self.theme_colors.chart_colors)])
            slice.setBrush(color)

        chart.addSeries(series)
        chart.setTitle("Platform Distribution")
        # Configure legend
        legend = chart.legend()
        legend.setVisible(True)
        legend.setLabelColor(QColor(self.theme_colors.text))
        legend.setAlignment(Qt.AlignmentFlag.AlignRight)
        legend.setFont(QFont("Arial", 9))

        # Use custom markers and format for better readability
        # legend.setMarkerShape(QtCharts.QLegend.MarkerShapeRectangle)
        legend.setShowToolTips(True)

        # Limit label length and add count to legend
        for i, series_slice in enumerate(series.slices()):
            label = platform_data['platforms'][i]
            count = platform_data['counts'][i]
            if len(label) > 15:
                label = f"{label[:15]}..."
            series_slice.setLabel(f"{label} ({count})")

        # Adjust layout to prevent legend overlap
        chart.setMargins(QMargins(10, 10, 100, 10))  # Give more space on the right for legend

        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        chart_view.setMinimumSize(400, 300)

        summary_layout.addLayout(stats_layout)
        summary_layout.addWidget(chart_view)

        # Clear previous content and add new
        for i in reversed(range(self.device_summary.content_layout.count())):
            self.device_summary.content_layout.itemAt(i).widget().setParent(None)
        self.device_summary.content_layout.addWidget(summary_widget)

    def update_report(self):
        self.update_device_summary()
        self.update_software_distribution()


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)

    # Set initial theme
    initial_theme = Theme.DARK
    app.setPalette(ThemeManager.get_palette(initial_theme))

    db_path = "surveyor/cmdb.db"  # Update with your database path
    report = NetworkReport(db_path, theme=initial_theme)
    report.resize(1200, 800)
    report.show()

    sys.exit(app.exec())