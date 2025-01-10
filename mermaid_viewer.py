import sys
import json
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QToolBar, QFileDialog, QComboBox, QMessageBox)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QAction
from typing import Optional, Dict, Any


class TopologyViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_file: Optional[Path] = None
        self.current_data: Optional[Dict[str, Any]] = None
        self.initUI()

    def initUI(self):
        """Initialize the user interface"""
        self.setWindowTitle('Network Topology Viewer')
        self.setGeometry(100, 100, 1200, 800)

        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Create toolbar
        toolbar = QToolBar()
        self.addToolBar(toolbar)

        # Add toolbar actions
        open_action = QAction('Open', self)
        open_action.triggered.connect(self.open_file)
        toolbar.addAction(open_action)

        save_action = QAction('Save', self)
        save_action.triggered.connect(self.save_file)
        toolbar.addAction(save_action)

        render_action = QAction('Render', self)
        render_action.triggered.connect(self.render_diagram)
        toolbar.addAction(render_action)

        # Add layout combo box
        self.layout_combo = QComboBox()
        self.layout_combo.addItems(['TD', 'LR'])
        self.layout_combo.currentTextChanged.connect(self.render_diagram)
        toolbar.addWidget(self.layout_combo)

        # Create web view
        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view)

        # Set initial content
        self.set_initial_content()

    def set_initial_content(self):
        """Set initial HTML content with Mermaid CDN"""
        initial_html = '''
        <!DOCTYPE html>
        <html>
        <head>
            <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
            <script>
                mermaid.initialize({
                    startOnLoad: true,
                    theme: 'default',
                    securityLevel: 'loose'
                });
            </script>
        </head>
        <body>
            <div class="mermaid">
                graph TD
                    A[Open a topology file to begin]
            </div>
        </body>
        </html>
        '''
        self.web_view.setHtml(initial_html)

    def open_file(self):
        """Open and load a topology JSON file"""
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Open Topology File",
            "",
            "JSON Files (*.json);;All Files (*)"
        )

        if file_name:
            try:
                with open(file_name, 'r') as f:
                    self.current_data = json.load(f)
                self.current_file = Path(file_name)
                self.render_diagram()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load file: {str(e)}")

    def save_file(self):
        """Save the current diagram as HTML"""
        if not self.current_data:
            QMessageBox.warning(self, "Warning", "No diagram to save!")
            return

        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Save Diagram",
            "",
            "HTML Files (*.html);;All Files (*)"
        )

        if file_name:
            try:
                html_content = self.generate_html(self.generate_mermaid())
                with open(file_name, 'w') as f:
                    f.write(html_content)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save file: {str(e)}")

    def generate_mermaid(self) -> str:
        """Generate Mermaid diagram code from the current data"""
        if not self.current_data:
            return "graph TD\nA[No data loaded]"

        layout = self.layout_combo.currentText()
        diagram_type = "flowchart" if layout == "circle" else "graph"
        lines = [f"{diagram_type} {layout}"]

        # Add styling classes
        lines.extend([
            "classDef core fill:#f9f,stroke:#333,stroke-width:2px;",
            "classDef switch fill:#bbf,stroke:#333,stroke-width:1px;",
            "classDef endpoint fill:#dfd,stroke:#333,stroke-width:1px;"
        ])

        # Process nodes and connections
        processed_nodes = set()
        for node, details in self.current_data.items():
            node_id = node.replace("-", "_")

            # Add node if not already processed
            if node_id not in processed_nodes:
                node_info = [node]
                if details.get("node_details"):
                    for key, value in details["node_details"].items():
                        if value:
                            node_info.append(f"{key}: {value}")

                lines.append(f'{node_id}["{("<br>").join(node_info)}"]')
                processed_nodes.add(node_id)

            # Process peer connections
            for peer, peer_details in details.get("peers", {}).items():
                peer_id = peer.replace("-", "_")

                # Add peer node if not already processed
                if peer_id not in processed_nodes:
                    peer_info = [peer]
                    if peer_details.get("ip"):
                        peer_info.append(f"ip: {peer_details['ip']}")
                    if peer_details.get("platform"):
                        peer_info.append(f"platform: {peer_details['platform']}")

                    lines.append(f'{peer_id}["{("<br>").join(peer_info)}"]')
                    processed_nodes.add(peer_id)

                # Add connections
                for conn in peer_details.get("connections", []):
                    lines.append(
                        f'{node_id} -->|"{conn[0]} - {conn[1]}"| {peer_id}'
                    )

        return "\n".join(lines)

    def generate_html(self, mermaid_code: str) -> str:
        """Generate full HTML page with Mermaid diagram"""
        return f'''
        <!DOCTYPE html>
        <html>
        <head>
            <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
            <script>
                mermaid.initialize({{
                    startOnLoad: true,
                    theme: 'default',
                    securityLevel: 'loose'
                }});
            </script>
        </head>
        <body>
            <div class="mermaid">
                {mermaid_code}
            </div>
        </body>
        </html>
        '''

    def render_diagram(self):
        """Render the current diagram in the web view"""
        if self.current_data:
            html_content = self.generate_html(self.generate_mermaid())
            self.web_view.setHtml(html_content)


def main():
    app = QApplication(sys.argv)
    viewer = TopologyViewer()
    viewer.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()