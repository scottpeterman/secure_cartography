import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QStackedWidget,
                             QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
                             QFrame, QSpacerItem, QSizePolicy, QScrollArea,
                             QSplitter)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPalette, QColor, QPixmap
from PyQt6.QtSvgWidgets import QSvgWidget
from pathlib import Path

from admin.bling_home import MarketingHomeWidget
from admin.hud_icons import get_router_svg, get_switch_svg, get_firewall_svg
from admin.mdi_data_gui import MDIWorkspace
from admin.nav_icons import get_home_svg, get_cartography_svg, get_surveyor_svg, get_jobs_svg, get_settings_svg
from admin.reporting import NetworkReport
from admin.scheduler import SchedulerWidget

class ScrollableStackedWidget(QScrollArea):
    """A QScrollArea wrapper around QStackedWidget for handling overflow content in a SPA-style UI"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.stack = QStackedWidget()
        self.setWidget(self.stack)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def addWidget(self, widget):
        """Add a widget to the stack"""
        return self.stack.addWidget(widget)

    def setCurrentWidget(self, widget):
        """Switch to display the specified widget"""
        self.stack.setCurrentWidget(widget)

    def insertWidget(self, index, widget):
        """Insert a widget at the specified index"""
        return self.stack.insertWidget(index, widget)

    def removeWidget(self, widget):
        """Remove a widget from the stack"""
        return self.stack.removeWidget(widget)

    def widget(self, index):
        """Get widget at specified index"""
        return self.stack.widget(index)


class NavigationButton(QPushButton):
    def __init__(self, text, svg_content=None, parent=None):
        super().__init__(parent)
        self.full_text = text
        self.svg_content = svg_content
        self.setCheckable(True)
        self.setMinimumHeight(40)

        # Set button styling
        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 0px;
                text-align: left;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
            }
            QPushButton:checked {
                background-color: #1e1e1e;
                border-left: 3px solid #4CAF50;
            }
        """)

        # Create main layout with smaller margins
        self.button_layout = QHBoxLayout(self)
        self.button_layout.setContentsMargins(8, 4, 8, 4)
        self.button_layout.setSpacing(8)

        # Create SVG widget with smaller size
        if svg_content:
            self.icon_widget = QSvgWidget()
            self.icon_widget.setFixedSize(20, 20)
            self.icon_widget.load(bytes(svg_content, encoding='utf-8'))
            self.button_layout.addWidget(self.icon_widget)
        else:
            self.icon_widget = None

        # Create text label with smaller font
        self.text_label = QLabel(text)
        self.text_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 13px;
                background-color: transparent;
            }
        """)
        self.button_layout.addWidget(self.text_label)
        self.button_layout.addStretch()

    def setCollapsed(self, collapsed):
        """Handle collapsed state"""
        if collapsed:
            self.text_label.hide()
            if self.icon_widget:
                self.button_layout.setContentsMargins(10, 4, 10, 4)
                self.icon_widget.setFixedSize(20, 20)
            self.setToolTip(self.full_text)
        else:
            self.text_label.show()
            if self.icon_widget:
                self.button_layout.setContentsMargins(8, 4, 8, 4)
                self.icon_widget.setFixedSize(20, 20)
            self.setToolTip("")


class AdminShell(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Secure Cartography Suite")

        # Main layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create splitter
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # Navigation sidebar
        self.sidebar = QFrame()
        self.sidebar.setMaximumWidth(250)
        self.sidebar.setMinimumWidth(100)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # Hamburger menu button
        self.toggle_button = QPushButton("☰")
        self.toggle_button.setFixedSize(50, 50)
        self.toggle_button.setStyleSheet("""
            QPushButton {
                color: white;
                border: none;
                background-color: transparent;
                font-size: 20px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
            }
        """)
        self.toggle_button.clicked.connect(self.toggle_sidebar)
        # Minimum and initial sizing
        # self.setMinimumSize(800, 500)  # Minimum window size
        # self.resize(1200, 800)  # Initial window size

        # Center the window on screen
        screen = QApplication.primaryScreen().geometry()
        # self.move(
        #     (screen.width() - self.width()) // 2,
        #     (screen.height() - self.height()) // 2
        # )
        sidebar_layout.addWidget(self.toggle_button)

        # Add logo container
        logo_container = QWidget()
        logo_container.setMinimumHeight(80)
        logo_layout = QHBoxLayout(logo_container)
        logo_layout.setContentsMargins(10, 10, 10, 10)
        logo_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_layout.setSpacing(8)

        # Create SVG widgets for logos
        self.logo_widgets = []
        for i, svg_func in enumerate([get_router_svg, get_switch_svg, get_firewall_svg]):
            logo_widget = QSvgWidget()
            logo_widget.setFixedSize(40, 40)
            svg_content = svg_func().replace('var(--icon-color, #000000)', '#4CAF50').replace('#000000', '#4CAF50')
            logo_widget.load(bytes(svg_content, encoding='utf-8'))
            logo_layout.addWidget(logo_widget, alignment=Qt.AlignmentFlag.AlignCenter)
            self.logo_widgets.append(logo_widget)
            if i > 0:  # For all but first icon
                logo_widget.setVisible(True)

        # Add logo container to sidebar
        sidebar_layout.addWidget(logo_container)

        # Add a subtle separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #3d3d3d;")
        separator.setMaximumHeight(1)
        sidebar_layout.addWidget(separator)

        # Initialize pages dictionary and stacked widget
        self.pages = {}
        self.stack = ScrollableStackedWidget()

        # Set up navigation menu with icons
        self.nav_buttons = []
        nav_items = {
            "Home": get_home_svg(),
            "Cartography": get_cartography_svg(),
            "Surveyor": get_surveyor_svg(),
            "Jobs": get_jobs_svg(),
            "DB": get_settings_svg()
        }

        # Create navigation buttons and placeholder pages
        for text, svg in nav_items.items():
            # Create and add navigation button
            btn = NavigationButton(text, svg)
            btn.clicked.connect(lambda checked, x=text: self.change_page(x))
            self.nav_buttons.append(btn)
            sidebar_layout.addWidget(btn)

            if text == "Home":
                # Create a widget for the home page
                # home_widget = QWidget()
                home_widget = NetworkReport("surveyor/cmdb.db")
                self.pages[text] = home_widget
                self.stack.addWidget(home_widget)
                title_label = QLabel("Welcome to Secure\nCartography Suite")
                title_label.setStyleSheet("""
                    QLabel {
                        color: white;
                        font-size: 42px;
                        font-weight: bold;
                        padding: 20px;
                    }
                """)
                title_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
                title_label.setWordWrap(True)

                # Create a label for the image
                image_label = QLabel()
                image_label.setStyleSheet("""
                    QLabel {
                        background-color: transparent;
                        padding: 0px;
                    }
                """)
                image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

                # Load the image with correct extension
                splash_path = "C:/Users/speterman/PycharmProjects/secure_cartography_distro/assets/splash2.jpeg"

                if Path(splash_path).exists():
                    pixmap = QPixmap(splash_path)
                    if not pixmap.isNull():
                        scaled_pixmap = pixmap.scaled(
                            1200,  # Fixed width
                            800,  # Fixed height
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        image_label.setPixmap(scaled_pixmap)

                # Add widgets to layout
                # self.ome_layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignHCenter)
                # home_layout.addWidget(image_label, alignment=Qt.AlignmentFlag.AlignHCenter)
                # home_layout.addStretch()

                # Set the widget background
                # home_widget.setStyleSheet("""
                #     QWidget {
                #         background-color: #1e1e1e;
                #     }
                # """)

                # self.pages[text] = home_widget
                # self.stack.addWidget(home_widget)

            elif text == "Jobs":
                # Create the SchedulerWidget instance
                jobs_widget = SchedulerWidget("")

                # Set up styling for consistency
                jobs_widget.setStyleSheet("background-color: #1e1e1e;")

                # Store the widget in the pages dictionary and add it to the stack
                self.pages[text] = jobs_widget
                self.stack.addWidget(jobs_widget)

            elif text == "DB":
                # Create the MDI workspace for database
                db_widget = MDIWorkspace("surveyor/cmdb.db")
                # db_widget.setStyleSheet("""
                #                 QWidget {
                #                     background-color: #1e1e1e;
                #                 }
                #                 QToolBar {
                #                     background-color: #2d2d2d;
                #                     border: none;
                #                     spacing: 5px;
                #                     padding: 5px;
                #                 }
                #                 QPushButton {
                #                     background-color: #3d3d3d;
                #                     color: white;
                #                     border: none;
                #                     padding: 5px 10px;
                #                     border-radius: 3px;
                #                 }
                #                 QPushButton:hover {
                #                     background-color: #4d4d4d;
                #                 }
                #                 QComboBox {
                #                     background-color: #3d3d3d;
                #                     color: white;
                #                     border: none;
                #                     padding: 5px;
                #                     border-radius: 3px;
                #                     min-width: 200px;
                #                 }
                #                 QComboBox::drop-down {
                #                     border: none;
                #                 }
                #                 QComboBox::down-arrow {
                #                     border: none;
                #                     background: #4d4d4d;
                #                 }
                #                 QMdiArea {
                #                     background-color: #1e1e1e;
                #                 }
                #             """)
                self.pages[text] = db_widget
                self.stack.addWidget(db_widget)
            else:
                if text not in self.pages:
                    page = QWidget()
                    page.setStyleSheet("background-color: #1e1e1e;")
                    self.pages[text] = page
                    self.stack.addWidget(page)

        # Add spacer to sidebar
        sidebar_layout.addStretch(1)

        # Add widgets to splitter
        self.splitter.addWidget(self.sidebar)
        self.splitter.addWidget(self.stack)

        # Set initial splitter sizes
        self.splitter.setSizes([100, self.width() - 100])

        # Add splitter to main layout
        layout.addWidget(self.splitter)

        # Set initial page and button state
        self.nav_buttons[0].setChecked(True)
        self.change_page("Home")

        # Set dark theme
        self.set_dark_theme()

    def toggle_sidebar(self):
        """Toggle sidebar between expanded and collapsed states"""
        current_width = self.sidebar.width()
        new_width = 50 if current_width > 50 else 250

        # Animate width change
        self.sidebar.setMaximumWidth(new_width)
        self.sidebar.setMinimumWidth(new_width)

        # Update button states
        collapsed = new_width == 50
        for btn in self.nav_buttons:
            btn.setCollapsed(collapsed)

        # Update logo sizes and visibility based on sidebar state
        new_size = 25 if collapsed else 40
        for i, logo_widget in enumerate(self.logo_widgets):
            logo_widget.setFixedSize(new_size, new_size)
            if i > 0:  # For all but first icon
                logo_widget.setVisible(not collapsed)

        # Update splitter sizes
        self.splitter.setSizes([new_width, self.width() - new_width])

    def change_page(self, page_name):
        """Change the current page and update button states"""
        if page_name in self.pages:
            self.stack.setCurrentWidget(self.pages[page_name])
            for btn in self.nav_buttons:
                btn.setChecked(btn.text_label.text() == page_name)

    def set_dark_theme(self):
        """Apply dark theme to the application"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QFrame {
                background-color: #2d2d2d;
                color: #ffffff;
            }
            QSplitter::handle {
                background-color: #3d3d3d;
            }
            QSplitter::handle:hover {
                background-color: #4d4d4d;
            }
            QScrollArea {
                border: none;
                background-color: #1e1e1e;
            }
        """)