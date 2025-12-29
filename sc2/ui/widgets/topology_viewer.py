"""
SC2 Topology Viewer Widget
Portable Cytoscape.js-based network topology viewer for PyQt6.

Usage:
    from topology_viewer import TopologyViewer
    
    viewer = TopologyViewer()
    viewer.load_topology(topology_dict)  # or load_topology_file(path)
    viewer.set_theme(theme_colors)
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from sc2.scng.utils.resource_helper import read_resource_text, get_resource_path, resource_exists

from PyQt6.QtCore import (
    Qt, QObject, pyqtSignal, pyqtSlot, QUrl
)
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel

from sc2.ui.widgets.platform_icons import PlatformIconManager, get_platform_icon_manager


class TopologyBridge(QObject):
    """
    Bridge object for QWebChannel communication between Python and JavaScript.
    Exposed to JavaScript as 'bridge'.
    """
    
    # Signals emitted when JS events occur
    viewerReady = pyqtSignal()
    nodeSelected = pyqtSignal(dict)
    edgeSelected = pyqtSignal(dict)
    layoutChanged = pyqtSignal(dict)
    nodeEditRequested = pyqtSignal(dict)  # Double-click to edit

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ready = False

    @pyqtSlot()
    def onViewerReady(self):
        """Called by JS when viewer is initialized."""
        self._ready = True
        self.viewerReady.emit()

    @pyqtSlot(str)
    def onNodeSelected(self, data_json: str):
        """Called by JS when a node is clicked."""
        try:
            data = json.loads(data_json)
            self.nodeSelected.emit(data)
        except json.JSONDecodeError:
            pass

    @pyqtSlot(str)
    def onEdgeSelected(self, data_json: str):
        """Called by JS when an edge is clicked."""
        try:
            data = json.loads(data_json)
            self.edgeSelected.emit(data)
        except json.JSONDecodeError:
            pass

    @pyqtSlot(str)
    def onLayoutChanged(self, positions_json: str):
        """Called by JS when node positions change (drag)."""
        try:
            positions = json.loads(positions_json)
            self.layoutChanged.emit(positions)
        except json.JSONDecodeError:
            pass

    @pyqtSlot(str)
    def onNodeEditRequested(self, data_json: str):
        """Called by JS when user double-clicks a node to edit."""
        try:
            data = json.loads(data_json)
            self.nodeEditRequested.emit(data)
        except json.JSONDecodeError:
            pass

    @property
    def is_ready(self) -> bool:
        return self._ready


class TopologyViewer(QWidget):
    """
    PyQt6 widget for displaying network topology using Cytoscape.js.

    Signals:
        ready: Emitted when the viewer is initialized and ready
        node_selected(dict): Emitted when a node is clicked
        edge_selected(dict): Emitted when an edge is clicked
        layout_changed(dict): Emitted when node positions change
        node_edit_requested(dict): Emitted when a node is double-clicked (for editing)
    """

    # Expose bridge signals at widget level
    ready = pyqtSignal()
    node_selected = pyqtSignal(dict)
    edge_selected = pyqtSignal(dict)
    layout_changed = pyqtSignal(dict)
    node_edit_requested = pyqtSignal(dict)  # Double-click to edit

    def __init__(self, parent=None, show_controls: bool = False,
                 icon_manager: Optional[PlatformIconManager] = None):
        super().__init__(parent)

        self._topology_data: Optional[Dict] = None
        self._pending_theme: Optional[Dict] = None
        self._pending_positions: Optional[Dict] = None
        self._show_controls = show_controls

        # Platform icon manager
        self._icon_manager = icon_manager or get_platform_icon_manager()

        self._setup_ui()
        self._setup_bridge()

    def _setup_ui(self):
        """Create the web view."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._web_view = QWebEngineView()
        # Allow CDN access
        from PyQt6.QtWebEngineCore import QWebEngineSettings
        self._web_view.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        self._web_view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        layout.addWidget(self._web_view)

        # Load the HTML viewer
        html_path = self._get_html_path()
        if html_path.exists():
            self._web_view.setUrl(QUrl.fromLocalFile(str(html_path)))
        else:
            # Fallback: load from embedded resource or show error
            self._web_view.setHtml(self._get_fallback_html())

    def _get_html_path(self) -> Path:
        """Get path to topology_viewer.html using importlib.resources."""
        # Define where your HTML lives - adjust package name to match your structure
        # e.g., if topology_viewer.html is in sc2/ui/topology_viewer.html
        RESOURCE_PACKAGE = 'sc2.ui.widgets'  # <-- adjust this
        RESOURCE_NAME = 'topology_viewer.html'

        try:
            return get_resource_path(RESOURCE_PACKAGE, RESOURCE_NAME)
        except Exception:
            # Fallback for dev mode - check relative to module
            module_dir = Path(__file__).parent
            candidates = [
                module_dir / 'topology_viewer.html',
                module_dir / 'resources' / 'topology_viewer.html',
            ]
            for path in candidates:
                if path.exists():
                    return path
            return candidates[0]


    def _get_fallback_html(self) -> str:
        """Minimal fallback HTML if viewer file is missing."""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body { 
                    background: #1a1a2e; 
                    color: #ff6b6b; 
                    font-family: sans-serif;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    margin: 0;
                }
            </style>
        </head>
        <body>
            <div>
                <h3>⚠️ Topology Viewer Not Found</h3>
                <p>topology_viewer.html is missing from resources.</p>
            </div>
        </body>
        </html>
        """

    def _setup_bridge(self):
        """Setup QWebChannel for Python ↔ JS communication."""
        self._bridge = TopologyBridge(self)
        self._channel = QWebChannel()
        self._channel.registerObject('bridge', self._bridge)
        self._web_view.page().setWebChannel(self._channel)

        # Connect bridge signals to widget signals
        self._bridge.viewerReady.connect(self._on_viewer_ready)
        self._bridge.nodeSelected.connect(self.node_selected.emit)
        self._bridge.edgeSelected.connect(self.edge_selected.emit)
        self._bridge.layoutChanged.connect(self.layout_changed.emit)
        self._bridge.nodeEditRequested.connect(self.node_edit_requested.emit)

    def _on_viewer_ready(self):
        """Handle viewer initialization complete."""
        # Send platform map to JS
        self._send_platform_map()

        # Apply any pending data
        if self._pending_theme:
            self._apply_theme(self._pending_theme)
            self._pending_theme = None

        if self._show_controls:
            self._run_js('TopologyViewer.showControls(true)')

        if self._topology_data:
            self._load_topology_js(self._topology_data)

        if self._pending_positions:
            self._restore_positions(self._pending_positions)
            self._pending_positions = None

        self.ready.emit()

    def _send_platform_map(self):
        """Send platform icon mapping to JavaScript."""
        platform_map_json = self._icon_manager.to_json()
        escaped = platform_map_json.replace('\\', '\\\\').replace("'", "\\'")
        self._run_js(f"TopologyViewer.setPlatformMap('{escaped}')")

    def _run_js(self, script: str, callback: Callable = None):
        """Execute JavaScript in the viewer."""
        if callback:
            self._web_view.page().runJavaScript(script, callback)
        else:
            self._web_view.page().runJavaScript(script)

    def _load_topology_js(self, data: Dict):
        """Send topology to JavaScript viewer with resolved icons."""
        import base64

        # Pre-resolve icon URLs on Python side
        enriched_data = self._enrich_topology_with_icons(data)
        json_str = json.dumps(enriched_data)

        # Base64 encode to avoid ALL escaping issues
        b64_data = base64.b64encode(json_str.encode('utf-8')).decode('ascii')

        print(f"[TopologyViewer] _load_topology_js: {len(json_str)} chars -> {len(b64_data)} b64, {len(enriched_data)} devices")

        # JS will decode: atob(b64) -> JSON.parse()
        self._run_js(f"TopologyViewer.loadTopologyB64('{b64_data}')")

    def _enrich_topology_with_icons(self, data: Dict) -> Dict:
        """Add icon URLs to topology data."""
        # Deep copy to avoid modifying original
        import copy
        data = copy.deepcopy(data)

        # Handle different formats
        if 'cytoscape' in data:
            # VelocityMaps format
            nodes = data['cytoscape'].get('nodes', [])
            for node in nodes:
                node_data = node.get('data', node)
                platform = node_data.get('platform', '')
                node_data['icon'] = self._icon_manager.get_icon_url(platform)

        elif 'nodes' in data:
            # Direct Cytoscape format
            for node in data['nodes']:
                node_data = node.get('data', node)
                platform = node_data.get('platform', '')
                node_data['icon'] = self._icon_manager.get_icon_url(platform)

        else:
            # SC2 map format - add icons to node_details
            for device_name, device_data in data.items():
                if isinstance(device_data, dict):
                    details = device_data.get('node_details', {})
                    platform = details.get('platform', '')
                    details['icon'] = self._icon_manager.get_icon_url(platform)

        return data

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def load_topology(self, data: Dict[str, Any]):
        """
        Load topology data into the viewer.

        Accepts multiple formats:
        - SC2 map format: {"device_name": {"node_details": {...}, "peers": {...}}, ...}
        - Cytoscape format: {"nodes": [...], "edges": [...]}
        - VelocityMaps format: {"cytoscape": {"nodes": [...], "edges": [...]}}

        Args:
            data: Topology dictionary
        """
        self._topology_data = data

        if self._bridge.is_ready:
            self._load_topology_js(data)

    def load_topology_file(self, path: str) -> bool:
        """
        Load topology from JSON file.

        Args:
            path: Path to topology JSON file

        Returns:
            True if loaded successfully
        """
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            self.load_topology(data)
            return True
        except (IOError, json.JSONDecodeError) as e:
            print(f"[TopologyViewer] Error loading {path}: {e}")
            return False

    def clear(self):
        """Clear the topology."""
        self._topology_data = None
        if self._bridge.is_ready:
            self._run_js("TopologyViewer.cy.elements().remove()")

    def fit_view(self):
        """Fit view to show all elements."""
        self._run_js("TopologyViewer.fitView()")

    def update_node(self, node_id: str, data: Dict[str, Any]):
        """
        Update a node's data and refresh its display.

        Args:
            node_id: The node's ID
            data: Updated node data dict (label, ip, platform, discovered, notes, etc.)
        """
        import base64

        # Update icon if platform changed
        if 'platform' in data:
            data['icon'] = self._icon_manager.get_icon_url(data.get('platform', ''))

        json_str = json.dumps(data)
        b64_data = base64.b64encode(json_str.encode('utf-8')).decode('ascii')

        self._run_js(f"TopologyViewer.updateNode('{node_id}', '{b64_data}')")

    def apply_layout(self, algorithm: str = 'cose'):
        """
        Apply layout algorithm.

        Args:
            algorithm: 'cose', 'grid', 'circle', or 'breadthfirst'
        """
        self._run_js(f"TopologyViewer.applyLayout('{algorithm}')")

    def set_theme(self, theme_colors: Dict[str, str]):
        """
        Apply theme colors to the viewer.

        Args:
            theme_colors: Dict mapping CSS variable names to colors, e.g.:
                {
                    '--bg-primary': '#1a1a2e',
                    '--bg-surface': '#16213e',
                    '--text-primary': '#eaeaea',
                    '--accent-primary': '#00d4ff',
                    '--edge-color': '#4a9eff'
                }
        """
        if self._bridge.is_ready:
            self._apply_theme(theme_colors)
        else:
            self._pending_theme = theme_colors

    def _apply_theme(self, theme_colors: Dict[str, str]):
        """Internal: send theme to JS."""
        json_str = json.dumps(theme_colors)
        escaped = json_str.replace('\\', '\\\\').replace("'", "\\'")
        self._run_js(f"TopologyViewer.setTheme('{escaped}')")

    def set_icon_base_path(self, path: str):
        """Set base path for platform icons."""
        self._run_js(f"TopologyViewer.setIconBasePath('{path}')")

    def save_positions(self) -> Optional[Dict[str, Dict[str, float]]]:
        """
        Get current node positions for saving.

        Returns:
            Dict of {node_id: {x: float, y: float}} or None
        """
        result = [None]

        def callback(positions_json):
            if positions_json:
                try:
                    result[0] = json.loads(positions_json)
                except json.JSONDecodeError:
                    pass

        self._run_js("TopologyViewer.exportPositions()", callback)
        return result[0]

    def restore_positions(self, positions: Dict[str, Dict[str, float]]):
        """
        Restore saved node positions.

        Args:
            positions: Dict of {node_id: {x: float, y: float}}
        """
        if self._bridge.is_ready:
            self._restore_positions(positions)
        else:
            self._pending_positions = positions

    def _restore_positions(self, positions: Dict):
        """Internal: send positions to JS."""
        json_str = json.dumps(positions)
        escaped = json_str.replace('\\', '\\\\').replace("'", "\\'")
        self._run_js(f"TopologyViewer.restorePositions('{escaped}')")

    def exportexport_png_base64(self) -> Optional[str]:
        """
        Export current view as PNG.

        Returns:
            Base64-encoded PNG string or None
        """
        result = [None]

        def callback(base64_str):
            result[0] = base64_str

        self._run_js("TopologyViewer.exportPNG()", callback)
        return result[0]

    @property
    def is_ready(self) -> bool:
        """Check if viewer is initialized."""
        return self._bridge.is_ready

    @property
    def node_count(self) -> int:
        """Get number of nodes (returns 0 if data not loaded)."""
        if not self._topology_data:
            return 0

        if 'nodes' in self._topology_data:
            return len(self._topology_data['nodes'])
        elif 'cytoscape' in self._topology_data:
            return len(self._topology_data['cytoscape'].get('nodes', []))
        else:
            # SC2 map format
            return len(self._topology_data)

    @property
    def edge_count(self) -> int:
        """Get number of edges (returns 0 if data not loaded)."""
        if not self._topology_data:
            return 0

        if 'edges' in self._topology_data:
            return len(self._topology_data['edges'])
        elif 'cytoscape' in self._topology_data:
            return len(self._topology_data['cytoscape'].get('edges', []))
        else:
            # SC2 map format - count unique edges
            edges = set()
            for device, data in self._topology_data.items():
                for peer in data.get('peers', {}).keys():
                    edge_id = tuple(sorted([device, peer]))
                    edges.add(edge_id)
            return len(edges)


# =============================================================================
# Convenience: Themed presets for SC2
# =============================================================================

SC2_THEMES = {
    'cyber': {
        '--bg-primary': '#0a0a1a',
        '--bg-surface': '#12122a',
        '--text-primary': '#e0e0e0',
        '--text-secondary': '#888888',
        '--accent-primary': '#00d4ff',
        '--accent-secondary': '#7b2cbf',
        '--border-color': '#2a2a4a',
        '--node-border': '#00d4ff',
        '--edge-color': '#4a9eff'
    },
    'dark': {
        '--bg-primary': '#1a1a1a',
        '--bg-surface': '#252525',
        '--text-primary': '#e0e0e0',
        '--text-secondary': '#888888',
        '--accent-primary': '#ffc107',
        '--accent-secondary': '#ff9800',
        '--border-color': '#3a3a3a',
        '--node-border': '#ffc107',
        '--edge-color': '#ffa000'
    },
    'light': {
        '--bg-primary': '#f5f5f5',
        '--bg-surface': '#ffffff',
        '--text-primary': '#212121',
        '--text-secondary': '#666666',
        '--accent-primary': '#1976d2',
        '--accent-secondary': '#0d47a1',
        '--border-color': '#e0e0e0',
        '--node-border': '#1976d2',
        '--edge-color': '#2196f3'
    }
}


# =============================================================================
# Demo / Test
# =============================================================================

if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow, QToolBar
    from PyQt6.QtGui import QAction

    # Sample topology data (SC2 format)
    SAMPLE_TOPOLOGY = {
        "core-switch": {
            "node_details": {
                "ip": "10.0.0.1",
                "platform": "Cisco Catalyst 9300"
            },
            "peers": {
                "dist-switch-1": {
                    "connections": [["Gi1/0/1", "Gi0/0"]]
                },
                "dist-switch-2": {
                    "connections": [["Gi1/0/2", "Gi0/0"]]
                }
            }
        },
        "dist-switch-1": {
            "node_details": {
                "ip": "10.0.1.1",
                "platform": "Arista DCS-7050"
            },
            "peers": {
                "core-switch": {
                    "connections": [["Gi0/0", "Gi1/0/1"]]
                },
                "access-1": {
                    "connections": [["Gi1/0/1", "Fa0/1"]]
                }
            }
        },
        "dist-switch-2": {
            "node_details": {
                "ip": "10.0.2.1",
                "platform": "Juniper EX4300"
            },
            "peers": {
                "core-switch": {
                    "connections": [["Gi0/0", "Gi1/0/2"]]
                },
                "access-2": {
                    "connections": [["Gi1/0/1", "Fa0/1"]]
                }
            }
        },
        "access-1": {
            "node_details": {
                "ip": "10.0.10.1",
                "platform": "Cisco WS-C2960"
            },
            "peers": {
                "dist-switch-1": {
                    "connections": [["Fa0/1", "Gi1/0/1"]]
                }
            }
        },
        "access-2": {
            "node_details": {
                "ip": "10.0.20.1",
                "platform": "Cisco WS-C2960"
            },
            "peers": {
                "dist-switch-2": {
                    "connections": [["Fa0/1", "Gi1/0/1"]]
                }
            }
        }
    }

    class DemoWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("SC2 Topology Viewer Demo")
            self.setMinimumSize(800, 600)

            # Create viewer
            self.viewer = TopologyViewer(show_controls=True)
            self.setCentralWidget(self.viewer)

            # Toolbar
            toolbar = QToolBar("Main")
            self.addToolBar(toolbar)

            # Theme actions
            for theme_name in SC2_THEMES.keys():
                action = QAction(f"Theme: {theme_name.title()}", self)
                action.triggered.connect(
                    lambda checked, t=theme_name: self.viewer.set_theme(SC2_THEMES[t])
                )
                toolbar.addAction(action)

            toolbar.addSeparator()

            # Layout actions
            for layout in ['cose', 'grid', 'circle', 'breadthfirst']:
                action = QAction(f"Layout: {layout}", self)
                action.triggered.connect(
                    lambda checked, l=layout: self.viewer.apply_layout(l)
                )
                toolbar.addAction(action)

            # Load sample data when ready
            self.viewer.ready.connect(self.on_viewer_ready)

            # Connect signals
            self.viewer.node_selected.connect(
                lambda d: print(f"Node selected: {d.get('label', d.get('id'))}")
            )
            self.viewer.edge_selected.connect(
                lambda d: print(f"Edge selected: {d.get('source')} → {d.get('target')}")
            )

        def on_viewer_ready(self):
            print("[Demo] Viewer ready, loading sample topology...")
            self.viewer.set_theme(SC2_THEMES['cyber'])
            self.viewer.load_topology(SAMPLE_TOPOLOGY)

    app = QApplication(sys.argv)
    window = DemoWindow()
    window.show()
    sys.exit(app.exec())