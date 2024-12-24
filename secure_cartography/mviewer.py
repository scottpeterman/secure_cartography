import sys
import json
import networkx as nx
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QDialog, QVBoxLayout,
                             QHBoxLayout, QPushButton, QComboBox, QLabel,
                             QFileDialog, QMessageBox, QWidget, QToolBar)
from PyQt6.QtCore import Qt
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtGui import QAction


class TopologyViewer(QMainWindow):
    """Standalone/integrated network topology viewer"""

    def __init__(self, topology_data=None, dark_mode=True, parent=None):
        super().__init__(parent)
        self.topology_data = topology_data
        self.dark_mode = dark_mode
        self.network_graph = None
        self.initUI()

        if topology_data:
            self.analyze_topology()
            self.render_diagram()

    def initUI(self):
        """Initialize the user interface"""
        self.setWindowTitle('Network Topology Viewer')
        self.setGeometry(100, 100, 1200, 800)

        # Create central widget
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

        # Add separator
        toolbar.addSeparator()

        # Add zoom controls
        zoom_in_action = QAction('Zoom In', self)
        zoom_in_action.setShortcut('Ctrl++')
        zoom_in_action.triggered.connect(self.zoom_in)
        toolbar.addAction(zoom_in_action)

        zoom_out_action = QAction('Zoom Out', self)
        zoom_out_action.setShortcut('Ctrl+-')
        zoom_out_action.triggered.connect(self.zoom_out)
        toolbar.addAction(zoom_out_action)

        zoom_reset_action = QAction('Reset Zoom', self)
        zoom_reset_action.setShortcut('Ctrl+0')
        zoom_reset_action.triggered.connect(self.zoom_reset)
        toolbar.addAction(zoom_reset_action)

        # Add layout selector
        layout_label = QLabel("Layout:")
        toolbar.addWidget(layout_label)

        self.layout_combo = QComboBox()
        self.layout_combo.addItems(['TD', 'LR', 'circle'])
        self.layout_combo.currentTextChanged.connect(self.render_diagram)
        toolbar.addWidget(self.layout_combo)

        # Create web view
        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view)

        # Apply theme-based styling
        self.apply_theme()

    def apply_theme(self):
        """Apply dark/light mode styling"""
        if self.dark_mode:
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #2b2b2b;
                    color: white;
                }
                QComboBox {
                    background-color: #3b3b3b;
                    color: white;
                    border: 1px solid #666;
                    padding: 5px;
                    border-radius: 3px;
                    min-width: 100px;
                }
                QToolBar {
                    background-color: #2b2b2b;
                    border: none;
                    spacing: 5px;
                    padding: 5px;
                }
                QToolBar QLabel {
                    color: white;
                    margin-left: 10px;
                }
                QAction {
                    color: white;
                }
                QToolButton {
                    background-color: #3b3b3b;
                    border: 1px solid #666;
                    border-radius: 3px;
                    padding: 5px;
                    color: white;
                }
                QToolButton:hover {
                    background-color: #4b4b4b;
                }
            """)
        else:
            self.setStyleSheet("""
                QMainWindow {
                    background-color: white;
                    color: black;
                }
                QComboBox {
                    background-color: white;
                    color: black;
                    border: 1px solid #ccc;
                    padding: 5px;
                    border-radius: 3px;
                    min-width: 100px;
                }
                QToolBar {
                    background-color: #f5f5f5;
                    border: none;
                    spacing: 5px;
                    padding: 5px;
                }
                QToolBar QLabel {
                    color: black;
                    margin-left: 10px;
                }
                QAction {
                    color: black;
                }
                QToolButton {
                    background-color: white;
                    border: 1px solid #ccc;
                    border-radius: 3px;
                    padding: 5px;
                }
                QToolButton:hover {
                    background-color: #f0f0f0;
                }
            """)

    def zoom_in(self):
        """Increase the zoom level"""
        if self.web_view:
            self.web_view.setZoomFactor(self.web_view.zoomFactor() + 0.1)

    def zoom_out(self):
        """Decrease the zoom level"""
        if self.web_view:
            self.web_view.setZoomFactor(max(0.1, self.web_view.zoomFactor() - 0.1))

    def zoom_reset(self):
        """Reset zoom to default level"""
        if self.web_view:
            self.web_view.setZoomFactor(1.0)

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
                    self.topology_data = json.load(f)
                self.analyze_topology()
                self.render_diagram()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load file: {str(e)}")

    def save_file(self):
        """Save the current diagram as HTML"""
        if not self.topology_data:
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


    def analyze_topology(self):
        """Analyze network topology using NetworkX"""
        G = nx.Graph()

        # Add nodes and edges
        added_edges = set()
        for node, data in self.topology_data.items():
            G.add_node(node,
                       ip=data['node_details'].get('ip', ''),
                       platform=data['node_details'].get('platform', ''))

            for peer, peer_data in data['peers'].items():
                # Add all peers as nodes, whether they're in topology_data or not
                if peer not in G:
                    G.add_node(peer,
                               ip=peer_data.get('ip', ''),
                               platform=peer_data.get('platform', ''),
                               is_leaf=peer not in self.topology_data)

                edge_key = tuple(sorted([node, peer]))
                if edge_key not in added_edges:
                    connections = peer_data.get('connections', [])
                    label = f"{connections[0][0]} - {connections[0][1]}" if connections else ""
                    G.add_edge(node, peer, connection=label)
                    added_edges.add(edge_key)

        # Calculate topology metrics
        degrees = dict(G.degree())
        betweenness = nx.betweenness_centrality(G)
        clustering = nx.clustering(G)

        # Classify nodes
        for node in G.nodes():
            is_core = degrees[node] > 2 and betweenness[node] > 0.1
            is_edge = degrees[node] == 1 or clustering[node] == 0
            is_gateway = betweenness[node] > 0.15 and degrees[node] <= 3

            G.nodes[node]['role'] = 'core' if is_core else 'gateway' if is_gateway else 'edge'
            G.nodes[node]['metric_degree'] = degrees[node]
            G.nodes[node]['metric_betweenness'] = betweenness[node]
            G.nodes[node]['metric_clustering'] = clustering[node]

        self.network_graph = G

    def generate_mermaid(self):
        """Generate Mermaid diagram code using topology analysis"""
        if not self.network_graph:
            return "graph TD\nA[No data loaded]"

        layout = self.layout_combo.currentText()

        layout_mapping = {
            'TD': 'TD',
            'LR': 'LR',
            'circle': 'TB',
            'kk': 'LR',
            'rt': 'TD',
            'circular': 'TB',
            'multipartite': 'LR'
        }

        mermaid_layout = layout_mapping.get(layout, 'TD')
        diagram_type = "flowchart" if layout == "circle" else "graph"
        lines = [f"{diagram_type} {mermaid_layout}"]

        # Add styling classes
        # lines.extend([
        #     "classDef core fill:#ff7676,stroke:#333,stroke-width:2px;",
        #     "classDef gateway fill:#76ff76,stroke:#333,stroke-width:2px;",
        #     "classDef edge fill:#7676ff,stroke:#333,stroke-width:1px;"
        # ])

        processed_nodes = set()
        processed_connections = set()

        for node in self.network_graph.nodes():
            node_id = node.replace("-", "_")
            node_data = self.network_graph.nodes[node]

            if node_id not in processed_nodes:
                # Different info display for leaf vs network nodes
                if node_data.get('is_leaf', False):
                    node_info = [node]
                    if node_data.get('ip'):
                        node_info.append(f"ip: {node_data['ip']}")
                else:
                    node_info = [
                        node,
                        f"ip: {node_data.get('ip', 'N/A')}",
                        f"platform: {node_data.get('platform', 'N/A')}"
                    ]

                role = 'edge' if node_data.get('is_leaf', False) else node_data.get('role', 'core')
                lines.append(f'{node_id}["{("<br>").join(node_info)}"]:::{role}')
                processed_nodes.add(node_id)

            for neighbor in self.network_graph.neighbors(node):
                neighbor_id = neighbor.replace("-", "_")
                connection_pair = tuple(sorted([node_id, neighbor_id]))

                if connection_pair not in processed_connections:
                    edge_data = self.network_graph.edges[node, neighbor]
                    connection_label = edge_data.get('connection', '')
                    if connection_label:
                        lines.append(f'{node_id} <-->|"{connection_label}"| {neighbor_id}')
                    else:
                        lines.append(f'{node_id} <--> {neighbor_id}')
                    processed_connections.add(connection_pair)

        return "\n".join(lines)
    def generate_html(self, mermaid_code):
        """Generate HTML with enhanced styling and interactivity"""
        theme = "dark" if self.dark_mode else "default"
        return f'''
        <!DOCTYPE html>
        <html>
        <head>
            <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
            <script>
                mermaid.initialize({{
                    startOnLoad: true,
                    theme: '{theme}',
                    securityLevel: 'loose',
                    maxZoom: 3,
                    minZoom: 0.1,
                    flowchart: {{
                        curve: 'basis',
                        padding: 20,
                        nodeSpacing: 50,
                        rankSpacing: 50,
                        htmlLabels: true
                    }}
                }});
            </script>
            <style>
                body {{
                    margin: 0;
                    padding: 20px;
                    background-color: {self.dark_mode and '#1a1a1a' or '#ffffff'};
                    overflow: hidden;
                }}
                .mermaid {{
                    cursor: move;
                }}
            </style>
        </head>
        <body>
            <div class="mermaid">
                {mermaid_code}
            </div>
            <script>
                document.addEventListener('DOMContentLoaded', function() {{
                    const diagram = document.querySelector('.mermaid');
                    let isPanning = false;
                    let startPoint = {{ x: 0, y: 0 }};
                    let currentTranslate = {{ x: 0, y: 0 }};
                    let currentZoom = 1;

                    diagram.addEventListener('mousedown', (e) => {{
                        isPanning = true;
                        startPoint = {{
                            x: e.clientX - currentTranslate.x,
                            y: e.clientY - currentTranslate.y
                        }};
                    }});

                    document.addEventListener('mousemove', (e) => {{
                        if (!isPanning) return;
                        currentTranslate = {{
                            x: e.clientX - startPoint.x,
                            y: e.clientY - startPoint.y
                        }};
                        updateTransform();
                    }});

                    document.addEventListener('mouseup', () => {{
                        isPanning = false;
                    }});

                    diagram.addEventListener('wheel', (e) => {{
                        if (e.ctrlKey) {{
                            e.preventDefault();
                            const delta = e.deltaY > 0 ? 0.9 : 1.1;
                            const newZoom = currentZoom * delta;
                            if (newZoom >= 0.1 && newZoom <= 3) {{
                                currentZoom = newZoom;
                                const rect = diagram.getBoundingClientRect();
                                const mouseX = e.clientX - rect.left;
                                const mouseY = e.clientY - rect.top;
                                currentTranslate.x = e.clientX - (mouseX * delta);
                                currentTranslate.y = e.clientY - (mouseY * delta);
                                updateTransform();
                            }}
                        }}
                    }});

                    function updateTransform() {{
                        diagram.style.transform = 
                            `translate(${{currentTranslate.x}}px, ${{currentTranslate.y}}px) scale(${{currentZoom}})`;
                    }}
                }});
            </script>
        </body>
        </html>
        '''

    def render_diagram(self):
        """Render the current diagram in the web view"""
        if self.topology_data:
            html_content = self.generate_html(self.generate_mermaid())
            self.web_view.setHtml(html_content)
        else:
            # Show empty state
            self.web_view.setHtml(self.generate_html("graph TD\nA[No data loaded]"))

def main():
    """Standalone entry point"""
    app = QApplication(sys.argv)

    # Set up dark/light mode detection
    if hasattr(app.style(), 'darkMode'):
        dark_mode = app.style().darkMode()
    else:
        # Default to dark mode if can't detect
        dark_mode = True

    viewer = TopologyViewer(dark_mode=dark_mode)
    viewer.show()

    return app.exec()

if __name__ == '__main__':
    sys.exit(main())