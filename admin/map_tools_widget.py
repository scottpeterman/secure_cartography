from PyQt6.QtWidgets import QVBoxLayout, QWidget, QLabel, QTabWidget

from map_enhance_widget import TopologyEnhanceWidget
from map_merge_widget import TopologyMergeWidget

# First, let's create the tabbed widget page class
class MapToolsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #3d3d3d;
                background: #1e1e1e;
            }
            QTabBar::tab {
                background: #2d2d2d;
                color: #ffffff;
                padding: 8px 20px;
                border: 1px solid #3d3d3d;
                min-width: 100px;
            }
            QTabBar::tab:selected {
                background: #1e1e1e;
                border-bottom: none;
            }
            QTabBar::tab:hover {
                background: #3d3d3d;
            }
        """)

        # Create the tabs
        self.enhance_tab = TopologyEnhanceWidget()
        self.merge_tab = TopologyMergeWidget()

        # Set up layouts for each tab
        enhance_layout = QVBoxLayout(self.enhance_tab)
        self.enhance_tab.setMaximumWidth(500)
        merge_layout = QVBoxLayout(self.merge_tab)

        # Add placeholder labels (you'll replace these with your actual widgets)
        enhance_layout.addWidget(QLabel("Enhance Tools"))
        merge_layout.addWidget(QLabel("Merge Tools"))

        # Add tabs to tab widget
        self.tab_widget.addTab(self.enhance_tab, "Enhance")
        self.tab_widget.addTab(self.merge_tab, "Merge")

        # Add tab widget to main layout
        layout.addWidget(self.tab_widget)