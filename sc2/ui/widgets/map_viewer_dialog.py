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

import copy
import json
from pathlib import Path
from typing import Optional, Dict, Any, Set

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


def filter_topology(topology_data: Dict, connected_only: bool = True, include_leaves: bool = False) -> Dict:
    """
    Filter topology based on connection criteria.

    Args:
        topology_data: The topology to filter
        connected_only: If True, exclude orphan nodes (no connections either direction)
        include_leaves: If True, include leaf nodes (referenced but no outgoing peers)
                       If False, only show nodes that have outgoing peer connections

    Connection types:
    - Orphan: No connections in either direction (always excluded if connected_only=True)
    - Leaf: Referenced by others but has no outgoing peers (servers, endpoints, phones)
    - Infrastructure: Has outgoing peer connections (switches, routers, firewalls)
    """
    if not topology_data:
        return topology_data

    # Handle different topology formats
    if 'nodes' in topology_data:
        # Cytoscape format: {"nodes": [...], "edges": [...]}
        return _filter_cytoscape_format(topology_data, connected_only, include_leaves)
    elif 'cytoscape' in topology_data:
        # VelocityMaps format: {"cytoscape": {"nodes": [...], "edges": [...]}}
        filtered_cyto = _filter_cytoscape_format(topology_data['cytoscape'], connected_only, include_leaves)
        result = topology_data.copy()
        result['cytoscape'] = filtered_cyto
        return result
    else:
        # SC2 map format: {device_name: {peers: {...}, node_details: {...}}}
        return _filter_sc2_format(topology_data, connected_only, include_leaves)


def _filter_sc2_format(topology: Dict, connected_only: bool, include_leaves: bool) -> Dict:
    """Filter SC2 native format based on connection criteria."""
    if not connected_only and include_leaves:
        # No filtering needed
        return topology

    # Build set of all referenced peers
    all_referenced_peers: Set[str] = set()
    for node_name, node_data in topology.items():
        if isinstance(node_data, dict):
            for peer_name in node_data.get('peers', {}).keys():
                all_referenced_peers.add(peer_name)
                all_referenced_peers.add(peer_name.lower())

    # Build set of nodes with outgoing peers (infrastructure nodes)
    nodes_with_peers: Set[str] = set()
    for node_name, node_data in topology.items():
        if isinstance(node_data, dict) and node_data.get('peers'):
            nodes_with_peers.add(node_name)
            nodes_with_peers.add(node_name.lower())

    # Filter based on criteria
    # IMPORTANT: Deep copy to avoid mutating original topology data
    filtered = {}
    for node_name, node_data in topology.items():
        if not isinstance(node_data, dict):
            continue

        has_peers = bool(node_data.get('peers'))
        is_referenced = (
            node_name in all_referenced_peers or
            node_name.lower() in all_referenced_peers
        )

        # Determine if node should be included (deep copy to prevent mutation)
        if has_peers:
            # Infrastructure node - always include
            filtered[node_name] = copy.deepcopy(node_data)
        elif is_referenced:
            # Leaf node - include only if include_leaves is True
            if include_leaves:
                filtered[node_name] = copy.deepcopy(node_data)
        else:
            # Orphan node - include only if connected_only is False
            if not connected_only:
                filtered[node_name] = copy.deepcopy(node_data)

    # Also need to filter peer references if we're excluding leaves
    if not include_leaves:
        # Remove peer entries that point to excluded nodes
        for node_name, node_data in filtered.items():
            if 'peers' in node_data:
                filtered_peers = {}
                for peer_name, peer_data in node_data['peers'].items():
                    # Keep peer if it's in our filtered set (has peers itself)
                    peer_in_filtered = (
                        peer_name in nodes_with_peers or
                        peer_name.lower() in nodes_with_peers
                    )
                    if peer_in_filtered:
                        filtered_peers[peer_name] = peer_data
                node_data['peers'] = filtered_peers

    return filtered


def _filter_cytoscape_format(cyto_data: Dict, connected_only: bool, include_leaves: bool) -> Dict:
    """Filter Cytoscape format based on connection criteria."""
    nodes = cyto_data.get('nodes', [])
    edges = cyto_data.get('edges', [])

    if not connected_only and include_leaves:
        # No filtering needed
        return cyto_data

    # Build set of node IDs that are sources (have outgoing connections)
    source_ids: Set[str] = set()
    # Build set of node IDs that are targets (referenced by others)
    target_ids: Set[str] = set()

    for edge in edges:
        edge_data = edge.get('data', edge)
        source = edge_data.get('source', '')
        target = edge_data.get('target', '')
        if source:
            source_ids.add(source)
        if target:
            target_ids.add(target)

    # Filter nodes based on criteria
    filtered_nodes = []
    included_ids: Set[str] = set()

    for node in nodes:
        node_data = node.get('data', node)
        node_id = node_data.get('id', '')

        is_source = node_id in source_ids  # Has outgoing connections
        is_target = node_id in target_ids  # Referenced by others
        is_connected = is_source or is_target

        # Determine if node should be included
        if is_source:
            # Infrastructure node - always include
            filtered_nodes.append(node)
            included_ids.add(node_id)
        elif is_target:
            # Leaf node - include only if include_leaves is True
            if include_leaves:
                filtered_nodes.append(node)
                included_ids.add(node_id)
        else:
            # Orphan node - include only if connected_only is False
            if not connected_only:
                filtered_nodes.append(node)
                included_ids.add(node_id)

    # Filter edges to only include those between included nodes
    filtered_edges = []
    for edge in edges:
        edge_data = edge.get('data', edge)
        source = edge_data.get('source', '')
        target = edge_data.get('target', '')
        if source in included_ids and target in included_ids:
            filtered_edges.append(edge)

    return {
        'nodes': filtered_nodes,
        'edges': filtered_edges
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
        self._topology_data: Optional[Dict] = None  # Original unfiltered data
        self._viewer_ready = False
        self._connected_only = True  # Default: ON (matches CLI behavior)
        self._include_leaves = False  # Default: OFF (hide leaf/endpoint nodes)

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
        self._layout_combo.setFixedWidth(130)
        # Built-in layouts
        self._layout_combo.addItem("Hierarchical", "dagre")      # 0 - Best for network tiers (requires extension)
        self._layout_combo.addItem("Force Directed", "cose")     # 1 - Organic clustering
        self._layout_combo.addItem("Concentric", "concentric")   # 2 - Degree-based rings
        self._layout_combo.addItem("Grid", "grid")               # 3 - Even spacing
        self._layout_combo.addItem("Circle", "circle")           # 4 - Ring layout
        self._layout_combo.addItem("Breadthfirst", "breadthfirst")  # 5 - Tree (needs root)
        self._layout_combo.setCurrentIndex(0)  # Default to Hierarchical (dagre)
        self._layout_combo.currentIndexChanged.connect(self._on_layout_changed)
        toolbar.addWidget(self._layout_combo)

        toolbar.addSeparator()

        # Connected-only checkbox - NOW AFFECTS THE VIEW (not just export)
        self._connected_only_checkbox = QCheckBox("Connected Only")
        self._connected_only_checkbox.setObjectName("connectedOnlyCheckbox")
        self._connected_only_checkbox.setToolTip(
            "Show only devices with connections\n"
            "(hides standalone/orphan nodes)"
        )
        self._connected_only_checkbox.setChecked(True)  # Default ON
        self._connected_only_checkbox.stateChanged.connect(self._on_connected_only_changed)
        toolbar.addWidget(self._connected_only_checkbox)

        # Show Leaves checkbox - controls visibility of endpoint/leaf nodes
        self._show_leaves_checkbox = QCheckBox("Show Leaves")
        self._show_leaves_checkbox.setObjectName("showLeavesCheckbox")
        self._show_leaves_checkbox.setToolTip(
            "Show leaf nodes (servers, endpoints, phones)\n"
            "that don't have their own neighbor data.\n"
            "Uncheck for infrastructure-only view."
        )
        self._show_leaves_checkbox.setChecked(False)  # Default OFF (cleaner view)
        self._show_leaves_checkbox.stateChanged.connect(self._on_show_leaves_changed)
        toolbar.addWidget(self._show_leaves_checkbox)

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

        # Export to yEd GraphML
        export_yed_action = QAction("📊 Export yEd", self)
        export_yed_action.setShortcut(QKeySequence("Ctrl+G"))
        export_yed_action.setToolTip("Export to yEd GraphML format (Ctrl+G)")
        export_yed_action.triggered.connect(self._on_export_graphml)
        toolbar.addAction(export_yed_action)

        export_csv_action = QAction("📋 Export CSV", self)
        export_csv_action.setShortcut(QKeySequence("Ctrl+Shift+E"))
        export_csv_action.setToolTip("Export nodes and edges to CSV (Ctrl+Shift+E)")
        export_csv_action.triggered.connect(self._on_export_csv)
        toolbar.addAction(export_csv_action)

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

    def _on_connected_only_changed(self, state: int):
        """Handle connected-only checkbox toggle - refilter and reload view."""
        self._connected_only = (state == Qt.CheckState.Checked.value)

        # Reload the view with updated filter
        if self._topology_data and self._viewer_ready:
            self._load_topology_to_viewer()
            self._update_stats()

    def _on_show_leaves_changed(self, state: int):
        """Handle show-leaves checkbox toggle - refilter and reload view."""
        self._include_leaves = (state == Qt.CheckState.Checked.value)

        # Reload the view with updated filter
        if self._topology_data and self._viewer_ready:
            self._load_topology_to_viewer()
            self._update_stats()

    def _on_export_csv(self):
        """Export device inventory to CSV."""
        if not self._topology_data:
            QMessageBox.warning(self, "Export", "No topology loaded to export.")
            return

        # Get save path
        default_name = self._current_file.stem + ".csv" if self._current_file else "devices.csv"
        start_dir = str(self._current_file.parent / default_name) if self._current_file else default_name

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Device Inventory to CSV",
            start_dir,
            "CSV Files (*.csv)"
        )

        if not path:
            return

        try:
            import csv

            # Get filtered topology (respects current view filters)
            display_data = self._get_display_topology()
            devices = self._extract_device_inventory(display_data)

            if not devices:
                QMessageBox.warning(self, "Export", "No devices to export.")
                return

            # Collect all fields across all devices
            all_fields = set()
            for device in devices:
                all_fields.update(device.keys())

            # Order fields sensibly
            priority = ['hostname', 'ip', 'platform', 'model', 'serial', 'version', 'site', 'role']
            fieldnames = [f for f in priority if f in all_fields]
            fieldnames += sorted(f for f in all_fields if f not in fieldnames)

            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(devices)

            self._status_label.setText(f"Exported: {Path(path).name} ({len(devices)} devices)")

        except Exception as e:
            QMessageBox.warning(self, "Export Failed", f"Error exporting CSV: {e}")

    def _extract_device_inventory(self, data: Optional[Dict]) -> list:
        """Extract flat device inventory from topology data."""
        if not data:
            return []

        devices = []

        if 'nodes' in data:
            # Cytoscape format
            for node in data.get('nodes', []):
                node_data = node.get('data', node)
                devices.append(dict(node_data))

        elif 'cytoscape' in data:
            # VelocityMaps format
            return self._extract_device_inventory(data['cytoscape'])

        else:
            # SC2 map format
            for device_name, device_data in data.items():
                if not isinstance(device_data, dict):
                    continue

                node_details = device_data.get('node_details', {})
                record = {'hostname': device_name}

                # Pull from node_details first, then top-level
                for key in ['ip', 'platform', 'model', 'serial', 'version', 'site', 'role', 'vendor']:
                    val = node_details.get(key) or device_data.get(key)
                    if val:
                        record[key] = val

                # Add any other scalar fields from node_details
                for k, v in node_details.items():
                    if k not in record and isinstance(v, (str, int, float, bool)):
                        record[k] = v

                devices.append(record)

        return devices

    def _extract_nodes_edges(self, data: Optional[Dict]) -> tuple:
        """
        Extract nodes and edges from topology data in any supported format.

        Returns:
            Tuple of (nodes_list, edges_list) where each is a list of dicts
        """
        if not data:
            return [], []

        nodes = []
        edges = []

        if 'nodes' in data:
            # Cytoscape format: {"nodes": [...], "edges": [...]}
            for node in data.get('nodes', []):
                node_data = node.get('data', node)
                nodes.append(dict(node_data))

            for edge in data.get('edges', []):
                edge_data = edge.get('data', edge)
                edges.append({
                    'source': edge_data.get('source', ''),
                    'source_port': edge_data.get('source_port', edge_data.get('sourcePort', '')),
                    'target': edge_data.get('target', ''),
                    'target_port': edge_data.get('target_port', edge_data.get('targetPort', '')),
                    'edge_id': edge_data.get('id', f"{edge_data.get('source', '')}-{edge_data.get('target', '')}")
                })

        elif 'cytoscape' in data:
            # VelocityMaps format: {"cytoscape": {"nodes": [...], "edges": [...]}}
            return self._extract_nodes_edges(data['cytoscape'])

        else:
            # SC2 map format: {device_name: {peers: {...}, node_details: {...}}}
            seen_edges = set()

            for device_name, device_data in data.items():
                if not isinstance(device_data, dict):
                    continue

                # Build node record
                node_details = device_data.get('node_details', {})
                node_record = {
                    'id': device_name,
                    'label': device_name,
                    'hostname': device_name,
                    'ip': node_details.get('ip', device_data.get('ip', '')),
                    'platform': node_details.get('platform', device_data.get('platform', '')),
                    'model': node_details.get('model', device_data.get('model', '')),
                    'site': node_details.get('site', device_data.get('site', '')),
                }
                # Add any extra fields from node_details
                for k, v in node_details.items():
                    if k not in node_record and isinstance(v, (str, int, float, bool)):
                        node_record[k] = v
                nodes.append(node_record)

                # Build edge records
                for peer_name, peer_data in device_data.get('peers', {}).items():
                    # Create canonical edge ID to avoid duplicates
                    edge_key = tuple(sorted([device_name, peer_name]))
                    if edge_key in seen_edges:
                        continue
                    seen_edges.add(edge_key)

                    # Handle peer_data as dict or list
                    if isinstance(peer_data, dict):
                        local_port = peer_data.get('local_port', '')
                        remote_port = peer_data.get('remote_port', '')
                    elif isinstance(peer_data, list) and peer_data:
                        # List of connections - take first or combine
                        local_port = peer_data[0].get('local_port', '') if peer_data else ''
                        remote_port = peer_data[0].get('remote_port', '') if peer_data else ''
                    else:
                        local_port = ''
                        remote_port = ''

                    edges.append({
                        'source': device_name,
                        'source_port': local_port,
                        'target': peer_name,
                        'target_port': remote_port,
                        'edge_id': f"{device_name}--{peer_name}"
                    })

        return nodes, edges

    def _get_display_topology(self) -> Optional[Dict]:
        """Get topology data for display, applying filters based on checkbox states."""
        if not self._topology_data:
            return None

        # Apply filtering based on current checkbox states
        return filter_topology(
            self._topology_data,
            connected_only=self._connected_only,
            include_leaves=self._include_leaves
        )

    def _load_topology_to_viewer(self):
        """Load the (potentially filtered) topology into the viewer."""
        display_data = self._get_display_topology()
        if display_data and self._viewer_ready:
            self._viewer.load_topology(display_data)
            QTimer.singleShot(500, self._viewer.fit_view)

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

        # Update local topology data (the original, unfiltered data)
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
            self._load_topology_to_viewer()

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

            # Create exporter with current options (use same filter state as view)
            exporter = GraphMLExporter(
                use_icons=True,
                include_endpoints=self._include_leaves,  # Match view filter
                connected_only=self._connected_only,
                layout_type='grid'
            )

            exporter.export(self._topology_data, Path(path))

            # Update status message to reflect filtering
            status_msg = f"Exported: {Path(path).name}"
            filter_notes = []
            if self._connected_only:
                filter_notes.append("connected only")
            if not self._include_leaves:
                filter_notes.append("infra only")
            if filter_notes:
                status_msg += f" ({', '.join(filter_notes)})"
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

    def load_topology(self, data: Dict[str, Any], name: Optional[str] = None):
        """
        Load topology data directly (not from file).

        Args:
            data: Topology dictionary (SC2 format, Cytoscape format, etc.)
            name: Optional name for display in title bar
        """
        if not isinstance(data, dict):
            return

        self._current_file = None  # No file associated
        self._topology_data = data

        display_name = name or "Untitled"
        self.setWindowTitle(f"Map Viewer - {display_name}")

        self._update_stats()
        self._status_label.setText(f"Loaded: {display_name} (from memory)")

        if self._viewer_ready:
            self._load_topology_to_viewer()


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

        # Store data (unfiltered - filtering happens at display time)
        self._current_file = file_path
        self._topology_data = data

        # Update window title
        self.setWindowTitle(f"Map Viewer - {file_path.name}")

        # Update status
        self._update_stats()
        self._status_label.setText(f"Loaded: {file_path.name}")

        # Load into viewer (with filtering if enabled)
        if self._viewer_ready:
            self._load_topology_to_viewer()

        # Emit signal
        self.file_loaded.emit(str(file_path))

        return True

    def _update_stats(self):
        """Update stats display showing both total and displayed counts."""
        if not self._topology_data:
            self._stats_label.setText("")
            return

        # Count from original data
        total_nodes, total_edges = self._count_topology(self._topology_data)

        # Count from filtered data
        display_data = self._get_display_topology()
        display_nodes, display_edges = self._count_topology(display_data)

        # Build status text
        if display_nodes < total_nodes:
            # Filtering is active and reducing node count
            filter_desc = []
            if self._connected_only:
                filter_desc.append("connected")
            if not self._include_leaves:
                filter_desc.append("infra only")

            filter_text = ", ".join(filter_desc) if filter_desc else "filtered"
            self._stats_label.setText(
                f"Devices: {display_nodes}/{total_nodes} ({filter_text}) | Connections: {display_edges}"
            )
        else:
            # No filtering effect
            self._stats_label.setText(f"Devices: {total_nodes} | Connections: {total_edges}")

    def _count_topology(self, data: Optional[Dict]) -> tuple:
        """Count nodes and edges in topology data."""
        if not data:
            return 0, 0

        # Count nodes and edges based on format
        if 'nodes' in data:
            nodes = len(data['nodes'])
            edges = len(data.get('edges', []))
        elif 'cytoscape' in data:
            cyto = data['cytoscape']
            nodes = len(cyto.get('nodes', []))
            edges = len(cyto.get('edges', []))
        else:
            # SC2 map format
            nodes = len(data)
            edges = set()
            for device, device_data in data.items():
                if isinstance(device_data, dict):
                    for peer in device_data.get('peers', {}).keys():
                        edge_id = tuple(sorted([device, peer]))
                        edges.add(edge_id)
            edges = len(edges)

        return nodes, edges

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
            
            QCheckBox#connectedOnlyCheckbox, QCheckBox#showLeavesCheckbox {{
                color: {theme.text_primary};
                spacing: 6px;
                padding: 4px 8px;
            }}
            
            QCheckBox#connectedOnlyCheckbox::indicator, QCheckBox#showLeavesCheckbox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {theme.border_dim};
                border-radius: 3px;
                background-color: {theme.bg_tertiary};
            }}
            
            QCheckBox#connectedOnlyCheckbox::indicator:checked, QCheckBox#showLeavesCheckbox::indicator:checked {{
                background-color: {theme.accent};
                border-color: {theme.accent};
            }}
            
            QCheckBox#connectedOnlyCheckbox::indicator:hover, QCheckBox#showLeavesCheckbox::indicator:hover {{
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