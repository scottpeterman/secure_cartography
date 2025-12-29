"""
SecureCartography v2 - Map Viewer Dialog

Full-featured standalone topology viewer for opening and viewing map JSON files.
Provides layout controls, export options, and theme-aware rendering.

Usage:
    dialog = MapViewerDialog(theme_manager=tm, parent=main_window)
    dialog.show()  # or dialog.exec() for modal

    # Open with file:
    dialog.open_file("/path/to/map.json")
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton,
    QFileDialog, QFrame, QComboBox, QMessageBox, QSizePolicy,
    QToolBar, QStatusBar, QWidget, QCheckBox
)
from PyQt6.QtGui import QAction, QKeySequence

from sc2.ui.themes import ThemeColors, ThemeManager
from sc2.ui.widgets.topology_viewer import TopologyViewer, SC2_THEMES
from sc2.ui.widgets.platform_icons import PlatformIconManager, get_platform_icon_manager


def theme_colors_to_viewer_theme(theme: ThemeColors) -> Dict[str, str]:
    """Convert SC2 ThemeColors to topology viewer CSS variables."""
    return {
        '--bg-primary': theme.bg_primary,
        '--bg-surface': theme.bg_secondary,
        '--text-primary': theme.text_primary,
        '--text-secondary': theme.text_secondary,
        '--accent-primary': theme.accent,
        '--accent-secondary': theme.accent_dim,
        '--border-color': theme.border_dim,
        '--node-border': theme.accent,
        '--edge-color': theme.accent_dim,
    }


class MapViewerDialog(QDialog):
    """
    Full-featured Map Viewer dialog.

    Features:
    - Open map JSON files (SC2, VelocityMaps, or raw Cytoscape formats)
    - Interactive topology view with pan/zoom
    - Multiple layout algorithms
    - Export to PNG
    - Theme-aware

    Signals:
        file_loaded(str): Emitted when a file is successfully loaded (path)
    """

    file_loaded = pyqtSignal(str)

    def __init__(
        self,
        theme_manager: Optional[ThemeManager] = None,
        icon_manager: Optional[PlatformIconManager] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)

        self.theme_manager = theme_manager
        self._current_theme: Optional[ThemeColors] = None
        self._icon_manager = icon_manager or get_platform_icon_manager()
        self._current_file: Optional[Path] = None
        self._topology_data: Optional[Dict] = None
        self._viewer_ready = False
        self._export_connected_only = False  # Track checkbox state

        self.setWindowTitle("Map Viewer")
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)

        self._setup_ui()
        self._connect_signals()

        if theme_manager:
            self.apply_theme(theme_manager.theme)

    def _setup_ui(self):
        """Build the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        self._toolbar = self._create_toolbar()
        layout.addWidget(self._toolbar)

        # Topology viewer (main content - no splitter needed now)
        self._viewer = TopologyViewer(
            show_controls=False,
            icon_manager=self._icon_manager
        )
        self._viewer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self._viewer, 1)

        # Status bar
        self._status_bar = QStatusBar()
        self._status_bar.setObjectName("mapViewerStatus")
        self._status_label = QLabel("No map loaded")
        self._status_bar.addWidget(self._status_label)

        self._stats_label = QLabel("")
        self._status_bar.addPermanentWidget(self._stats_label)

        layout.addWidget(self._status_bar)

    def _create_toolbar(self) -> QToolBar:
        """Create the toolbar with actions."""
        toolbar = QToolBar("Map Viewer Tools")
        toolbar.setObjectName("mapViewerToolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(toolbar.iconSize())  # Keep default

        # Open file
        open_action = QAction("📂 Open", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.setToolTip("Open map JSON file (Ctrl+O)")
        open_action.triggered.connect(self._on_open_file)
        toolbar.addAction(open_action)

        toolbar.addSeparator()

        # Layout selector
        layout_label = QLabel(" Layout: ")
        toolbar.addWidget(layout_label)

        self._layout_combo = QComboBox()
        self._layout_combo.setObjectName("layoutCombo")
        self._layout_combo.setFixedWidth(120)
        self._layout_combo.addItem("Auto (CoSE)", "cose")
        self._layout_combo.addItem("Grid", "grid")
        self._layout_combo.addItem("Circle", "circle")
        self._layout_combo.addItem("Hierarchical", "breadthfirst")
        self._layout_combo.currentIndexChanged.connect(self._on_layout_changed)
        toolbar.addWidget(self._layout_combo)

        toolbar.addSeparator()

        # View controls
        fit_action = QAction("⊡ Fit View", self)
        fit_action.setShortcut(QKeySequence("F"))
        fit_action.setToolTip("Fit view to all devices (F)")
        fit_action.triggered.connect(self._on_fit_view)
        toolbar.addAction(fit_action)

        refresh_action = QAction("↻ Reload", self)
        refresh_action.setShortcut(QKeySequence.StandardKey.Refresh)
        refresh_action.setToolTip("Reload current file (F5)")
        refresh_action.triggered.connect(self._on_reload)
        toolbar.addAction(refresh_action)

        toolbar.addSeparator()

        # Export PNG
        export_action = QAction("💾 Export PNG", self)
        export_action.setShortcut(QKeySequence("Ctrl+E"))
        export_action.setToolTip("Export as PNG image (Ctrl+E)")
        export_action.triggered.connect(self._on_export_png)
        toolbar.addAction(export_action)

        toolbar.addSeparator()

        # Connected-only checkbox for export
        self._connected_only_checkbox = QCheckBox("Connected Only")
        self._connected_only_checkbox.setObjectName("connectedOnlyCheckbox")
        self._connected_only_checkbox.setToolTip(
            "Export only devices with connections\n"
            "(excludes standalone/orphan nodes)"
        )
        self._connected_only_checkbox.setChecked(False)
        self._connected_only_checkbox.stateChanged.connect(
            lambda state: setattr(self, '_export_connected_only', state == 2)
        )
        toolbar.addWidget(self._connected_only_checkbox)

        # Export to yEd GraphML
        export_yed_action = QAction("📊 Export yEd", self)
        export_yed_action.setShortcut(QKeySequence("Ctrl+G"))
        export_yed_action.setToolTip("Export to yEd GraphML format (Ctrl+G)")
        export_yed_action.triggered.connect(self._on_export_graphml)
        toolbar.addAction(export_yed_action)

        # Save (for edited topology)
        save_action = QAction("📄 Save Map", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.setToolTip("Save edited topology to file (Ctrl+S)")
        save_action.triggered.connect(self._on_save_map)
        toolbar.addAction(save_action)

        # Spacer
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        # Close button
        close_action = QAction("✕ Close", self)
        close_action.setShortcut(QKeySequence.StandardKey.Close)
        close_action.triggered.connect(self.close)
        toolbar.addAction(close_action)

        return toolbar

    def _connect_signals(self):
        """Connect viewer signals."""
        self._viewer.ready.connect(self._on_viewer_ready)

        # Node editing (requires updated topology_viewer.py with node_edit_requested signal)
        if hasattr(self._viewer, 'node_edit_requested'):
            self._viewer.node_edit_requested.connect(self._on_node_edit_requested)

    def _on_node_edit_requested(self, node_data: dict):
        """Handle double-click request to edit a node."""
        from sc2.ui.widgets.node_edit_dialog import NodeEditDialog

        dialog = NodeEditDialog(
            node_data=node_data,
            theme_manager=self.theme_manager,
            parent=self
        )

        dialog.node_updated.connect(self._on_node_updated)
        dialog.exec()

    def _on_node_updated(self, updated_data: dict):
        """Handle node data update from edit dialog."""
        node_id = updated_data.get('id')
        if not node_id:
            return

        # Update local topology data
        if self._topology_data:
            # Detect format and update accordingly
            if 'nodes' in self._topology_data:
                # Cytoscape format: {"nodes": [...], "edges": [...]}
                self._update_cytoscape_node(self._topology_data, node_id, updated_data)
            elif 'cytoscape' in self._topology_data:
                # VelocityMaps format: {"cytoscape": {"nodes": [...], "edges": [...]}}
                self._update_cytoscape_node(self._topology_data['cytoscape'], node_id, updated_data)
            else:
                # SC2 map format (dict of device_name -> data)
                self._update_sc2_node(node_id, updated_data)

        # Push update to JS viewer (requires updated topology_viewer.py)
        if hasattr(self._viewer, 'update_node'):
            self._viewer.update_node(node_id, updated_data)

        self._status_label.setText(f"Updated: {updated_data.get('label', node_id)}")

    def _update_sc2_node(self, node_id: str, updated_data: dict):
        """Update or create a node in SC2 map format."""
        if node_id in self._topology_data:
            # Existing discovered device - update node_details
            device_data = self._topology_data[node_id]
            if 'node_details' not in device_data:
                device_data['node_details'] = {}
            device_data['node_details']['ip'] = updated_data.get('ip', '')
            device_data['node_details']['platform'] = updated_data.get('platform', '')
            device_data['node_details']['notes'] = updated_data.get('notes', '')
        else:
            # Previously undiscovered node - create new entry
            # This promotes an undiscovered peer to a proper device entry
            self._topology_data[node_id] = {
                'node_details': {
                    'ip': updated_data.get('ip', ''),
                    'platform': updated_data.get('platform', ''),
                    'notes': updated_data.get('notes', ''),
                },
                'peers': {}  # Empty peers - will be populated if relationships exist
            }

    def _update_cytoscape_node(self, cyto_data: dict, node_id: str, updated_data: dict):
        """Update a node in Cytoscape format."""
        nodes = cyto_data.get('nodes', [])
        for node in nodes:
            node_data = node.get('data', node)
            if node_data.get('id') == node_id:
                node_data['label'] = updated_data.get('label', node_id)
                node_data['ip'] = updated_data.get('ip', '')
                node_data['platform'] = updated_data.get('platform', '')
                node_data['discovered'] = updated_data.get('discovered', True)
                node_data['notes'] = updated_data.get('notes', '')
                return

        # Node not found - add it (was undiscovered placeholder)
        nodes.append({
            'data': {
                'id': node_id,
                'label': updated_data.get('label', node_id),
                'ip': updated_data.get('ip', ''),
                'platform': updated_data.get('platform', ''),
                'discovered': updated_data.get('discovered', True),
                'notes': updated_data.get('notes', ''),
            }
        })

    def _on_viewer_ready(self):
        """Handle viewer initialization."""
        self._viewer_ready = True

        # Apply theme if we have one stored
        if self._current_theme:
            viewer_theme = theme_colors_to_viewer_theme(self._current_theme)
            self._viewer.set_theme(viewer_theme)

        # Load pending data
        if self._topology_data:
            self._viewer.load_topology(self._topology_data)
            QTimer.singleShot(500, self._viewer.fit_view)

    def _on_open_file(self):
        """Open file dialog to select a map JSON."""
        start_dir = str(self._current_file.parent) if self._current_file else ""

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Map File",
            start_dir,
            "JSON Files (*.json);;All Files (*)"
        )

        if path:
            self.open_file(path)

    def _on_layout_changed(self, index: int):
        """Apply selected layout algorithm."""
        if not self._viewer_ready:
            return

        algorithm = self._layout_combo.itemData(index)
        if algorithm:
            self._viewer.apply_layout(algorithm)

    def _on_fit_view(self):
        """Fit view to all elements."""
        if self._viewer_ready:
            self._viewer.fit_view()

    def _on_reload(self):
        """Reload current file."""
        if self._current_file and self._current_file.exists():
            self.open_file(str(self._current_file))

    def _on_export_png(self):
        """Export topology as PNG."""
        if not self._viewer_ready or not self._topology_data:
            QMessageBox.warning(self, "Export", "No topology loaded to export.")
            return

        # Get save path
        default_name = self._current_file.stem + ".png" if self._current_file else "topology.png"
        start_dir = str(self._current_file.parent / default_name) if self._current_file else default_name

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Topology as PNG",
            start_dir,
            "PNG Images (*.png)"
        )

        if not path:
            return

        # Export (async callback approach)
        def on_png_ready(base64_data):
            if not base64_data:
                QMessageBox.warning(self, "Export Failed", "Failed to generate PNG.")
                return

            try:
                import base64
                png_bytes = base64.b64decode(base64_data)
                with open(path, 'wb') as f:
                    f.write(png_bytes)
                self._status_label.setText(f"Exported: {Path(path).name}")
            except Exception as e:
                QMessageBox.warning(self, "Export Failed", f"Error saving file: {e}")

        self._viewer._run_js("TopologyViewer.exportPNG()", on_png_ready)

    def _on_export_graphml(self):
        """Export topology to yEd GraphML format."""
        if not self._topology_data:
            QMessageBox.warning(self, "Export", "No topology loaded to export.")
            return

        # Determine default filename
        if self._current_file:
            default_name = self._current_file.stem + ".graphml"
            start_dir = str(self._current_file.parent / default_name)
        else:
            start_dir = "topology.graphml"

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export to yEd GraphML",
            start_dir,
            "GraphML Files (*.graphml)"
        )

        if not path:
            return

        try:
            from sc2.export.graphml_exporter import GraphMLExporter

            # Create exporter with current options
            exporter = GraphMLExporter(
                use_icons=True,
                include_endpoints=True,
                connected_only=self._export_connected_only,
                layout_type='grid'
            )

            exporter.export(self._topology_data, Path(path))

            # Update status message to reflect filtering
            status_msg = f"Exported: {Path(path).name}"
            if self._export_connected_only:
                status_msg += " (connected only)"
            self._status_label.setText(status_msg)

        except ImportError:
            QMessageBox.warning(
                self,
                "Export Failed",
                "GraphML exporter not available.\n"
                "Ensure sc2.export.graphml_exporter is installed."
            )
        except Exception as e:
            QMessageBox.warning(self, "Export Failed", f"Error exporting: {e}")

    def _on_save_map(self):
        """Save edited topology to JSON file."""
        if not self._topology_data:
            QMessageBox.warning(self, "Save", "No topology loaded to save.")
            return

        # Get save path
        if self._current_file:
            default_path = str(self._current_file)
        else:
            default_path = "topology.json"

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Topology Map",
            default_path,
            "JSON Files (*.json)"
        )

        if not path:
            return

        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self._topology_data, f, indent=2)

            self._current_file = Path(path)
            self.setWindowTitle(f"Map Viewer - {self._current_file.name}")
            self._status_label.setText(f"Saved: {self._current_file.name}")
        except IOError as e:
            QMessageBox.warning(self, "Save Failed", f"Error saving file: {e}")

    def open_file(self, path: str) -> bool:
        """
        Open and display a map JSON file.

        Args:
            path: Path to JSON file

        Returns:
            True if loaded successfully
        """
        file_path = Path(path)

        if not file_path.exists():
            QMessageBox.warning(self, "File Not Found", f"File not found:\n{path}")
            return False

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            QMessageBox.warning(self, "Invalid JSON", f"Failed to parse JSON:\n{e}")
            return False
        except IOError as e:
            QMessageBox.warning(self, "Read Error", f"Failed to read file:\n{e}")
            return False

        # Validate we got something useful
        if not isinstance(data, dict):
            QMessageBox.warning(self, "Invalid Format", "Map file must be a JSON object.")
            return False

        # Store data
        self._current_file = file_path
        self._topology_data = data

        # Update window title
        self.setWindowTitle(f"Map Viewer - {file_path.name}")

        # Update status
        self._update_stats()
        self._status_label.setText(f"Loaded: {file_path.name}")

        # Load into viewer
        if self._viewer_ready:
            self._viewer.load_topology(data)
            QTimer.singleShot(500, self._viewer.fit_view)

        # Emit signal
        self.file_loaded.emit(str(file_path))

        return True

    def _update_stats(self):
        """Update stats display."""
        if not self._topology_data:
            self._stats_label.setText("")
            return

        # Count nodes and edges based on format
        if 'nodes' in self._topology_data:
            nodes = len(self._topology_data['nodes'])
            edges = len(self._topology_data.get('edges', []))
        elif 'cytoscape' in self._topology_data:
            cyto = self._topology_data['cytoscape']
            nodes = len(cyto.get('nodes', []))
            edges = len(cyto.get('edges', []))
        else:
            # SC2 map format
            nodes = len(self._topology_data)
            edges = set()
            for device, data in self._topology_data.items():
                if isinstance(data, dict):
                    for peer in data.get('peers', {}).keys():
                        edge_id = tuple(sorted([device, peer]))
                        edges.add(edge_id)
            edges = len(edges)

        self._stats_label.setText(f"Devices: {nodes} | Connections: {edges}")

    def _apply_content_theme(self, theme: ThemeColors):
        """Apply theme to dialog content."""
        self._current_theme = theme

        # Apply to viewer if ready
        if self._viewer_ready:
            viewer_theme = theme_colors_to_viewer_theme(theme)
            self._viewer.set_theme(viewer_theme)

        # Dialog styling
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {theme.bg_primary};
            }}
            
            QToolBar#mapViewerToolbar {{
                background-color: {theme.bg_secondary};
                border: none;
                border-bottom: 1px solid {theme.border_dim};
                spacing: 8px;
                padding: 4px 8px;
            }}
            
            QToolBar#mapViewerToolbar QToolButton {{
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 6px 12px;
                color: {theme.text_primary};
                font-size: 12px;
            }}
            
            QToolBar#mapViewerToolbar QToolButton:hover {{
                background-color: {theme.bg_hover};
                border-color: {theme.border_dim};
            }}
            
            QToolBar#mapViewerToolbar QToolButton:pressed {{
                background-color: {theme.bg_tertiary};
            }}
            
            QToolBar#mapViewerToolbar QLabel {{
                color: {theme.text_secondary};
                background: transparent;
            }}
            
            QComboBox#layoutCombo {{
                background-color: {theme.bg_tertiary};
                border: 1px solid {theme.border_dim};
                border-radius: 4px;
                padding: 4px 8px;
                color: {theme.text_primary};
                min-height: 24px;
            }}
            
            QComboBox#layoutCombo:hover {{
                border-color: {theme.accent};
            }}
            
            QComboBox#layoutCombo::drop-down {{
                border: none;
                width: 20px;
            }}
            
            QComboBox#layoutCombo::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid {theme.text_secondary};
            }}
            
            QComboBox#layoutCombo QAbstractItemView {{
                background-color: {theme.bg_secondary};
                border: 1px solid {theme.border_dim};
                selection-background-color: {theme.accent};
                color: {theme.text_primary};
            }}
            
            QCheckBox#connectedOnlyCheckbox {{
                color: {theme.text_primary};
                spacing: 6px;
                padding: 4px 8px;
            }}
            
            QCheckBox#connectedOnlyCheckbox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {theme.border_dim};
                border-radius: 3px;
                background-color: {theme.bg_tertiary};
            }}
            
            QCheckBox#connectedOnlyCheckbox::indicator:checked {{
                background-color: {theme.accent};
                border-color: {theme.accent};
            }}
            
            QCheckBox#connectedOnlyCheckbox::indicator:hover {{
                border-color: {theme.accent};
            }}
            
            QStatusBar#mapViewerStatus {{
                background-color: {theme.bg_secondary};
                border-top: 1px solid {theme.border_dim};
                color: {theme.text_secondary};
                font-size: 11px;
            }}
            
            QStatusBar#mapViewerStatus QLabel {{
                color: {theme.text_secondary};
                padding: 2px 8px;
            }}
        """)

    def apply_theme(self, theme: ThemeColors):
        """Apply theme to entire dialog."""
        self._apply_content_theme(theme)

    def set_theme(self, theme_manager: ThemeManager):
        """Update theme manager and apply."""
        self.theme_manager = theme_manager
        self._apply_content_theme(theme_manager.theme)


# =============================================================================
# Standalone test
# =============================================================================

if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    dialog = MapViewerDialog()
    dialog.show()

    sys.exit(app.exec())