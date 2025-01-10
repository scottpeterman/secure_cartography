from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QFrame, QScrollArea, QPushButton, QSpacerItem, QSizePolicy)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QFont, QPainter, QColor, QLinearGradient
from PyQt6.QtSvgWidgets import QSvgWidget


class FeatureCard(QFrame):
    """A custom widget for displaying feature information"""

    def __init__(self, title, description, icon_svg=None, parent=None):
        super().__init__(parent)
        self.setObjectName("featureCard")
        self.setStyleSheet("""
            #featureCard {
                background-color: #2d2d2d;
                border-radius: 8px;
                padding: 20px;
                margin: 10px;
            }
            #featureCard:hover {
                background-color: #3d3d3d;
            }
        """)

        layout = QVBoxLayout(self)

        # Icon (if provided)
        if icon_svg:
            icon = QSvgWidget()
            icon.load(bytes(icon_svg, encoding='utf-8'))
            icon.setFixedSize(QSize(32, 32))
            layout.addWidget(icon, alignment=Qt.AlignmentFlag.AlignCenter)

        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 18px;
                font-weight: bold;
                margin-bottom: 10px;
            }
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Description
        desc_label = QLabel(description)
        desc_label.setStyleSheet("color: #cccccc; font-size: 14px;")
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc_label)


class StatisticWidget(QFrame):
    """A custom widget for displaying statistics"""

    def __init__(self, value, label, parent=None):
        super().__init__(parent)
        self.setObjectName("statWidget")
        self.setStyleSheet("""
            #statWidget {
                background-color: #2d2d2d;
                border-radius: 8px;
                padding: 15px;
                margin: 5px;
            }
        """)

        layout = QVBoxLayout(self)

        value_label = QLabel(value)
        value_label.setStyleSheet("""
            QLabel {
                color: #4CAF50;
                font-size: 24px;
                font-weight: bold;
            }
        """)
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        desc_label = QLabel(label)
        desc_label.setStyleSheet("color: #cccccc; font-size: 14px;")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(value_label)
        layout.addWidget(desc_label)


class MarketingHomeWidget(QScrollArea):
    """A marketing-focused home page widget"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Main container widget
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setSpacing(40)
        main_layout.setContentsMargins(40, 40, 40, 40)

        # Hero Section
        hero_widget = QWidget()
        hero_layout = QVBoxLayout(hero_widget)

        title = QLabel("Secure Cartography Suite")
        title.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 48px;
                font-weight: bold;
            }
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel("Advanced network discovery and visualization platform\nfor modern infrastructure")
        subtitle.setStyleSheet("color: #cccccc; font-size: 18px;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)

        # Statistics Section
        stats_widget = QWidget()
        stats_layout = QHBoxLayout(stats_widget)

        statistics = [
            ("190+", "Total Devices"),
            ("38", "Platforms"),
            ("2", "Vendors")
        ]

        for value, label in statistics:
            stats_layout.addWidget(StatisticWidget(value, label))

        # Features Section
        features_widget = QWidget()
        features_layout = QHBoxLayout(features_widget)

        features = [
            ("Network Discovery",
             "Automatically map your entire network infrastructure with our advanced discovery engine"),
            ("Visual Topology",
             "Generate beautiful, interactive network topology maps that help you understand your infrastructure"),
            ("Deep Auditing",
             "Track device inventory, OS, state and connections with our advanced monitoring capabilities")
        ]

        for title, desc in features:
            features_layout.addWidget(FeatureCard(title, desc))

        # Visualization Preview
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)

        preview_title = QLabel("Powerful Network Visualization")
        preview_title.setStyleSheet("color: white; font-size: 24px; font-weight: bold;")
        preview_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        preview_image = QLabel()
        preview_image.setPixmap(QPixmap("assets/splash2.jpeg").scaled(
            800, 400, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        ))
        preview_image.setAlignment(Qt.AlignmentFlag.AlignCenter)

        preview_layout.addWidget(preview_title)
        preview_layout.addWidget(preview_image)

        # Call to Action
        cta_widget = QFrame()
        cta_widget.setObjectName("ctaWidget")
        cta_widget.setStyleSheet("""
            #ctaWidget {
                background-color: #2d2d2d;
                border-radius: 12px;
                padding: 30px;
            }
        """)
        cta_layout = QVBoxLayout(cta_widget)

        cta_title = QLabel("Ready to map your network?")
        cta_title.setStyleSheet("color: white; font-size: 24px; font-weight: bold;")
        cta_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        start_button = QPushButton("Start Discovery")
        start_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        start_button.setFixedWidth(200)

        cta_layout.addWidget(cta_title)
        cta_layout.addWidget(start_button, alignment=Qt.AlignmentFlag.AlignCenter)

        # Add all sections to main layout
        main_layout.addWidget(hero_widget)
        main_layout.addWidget(stats_widget)
        main_layout.addWidget(features_widget)
        # main_layout.addWidget(preview_widget)
        main_layout.addWidget(cta_widget)

        # Set the container as the scroll area's widget
        self.setWidget(container)