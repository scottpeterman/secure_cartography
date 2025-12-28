"""
SecureCartography v2 - Topology Preview Panel (SINGLETON VERSION)

Live network topology preview using Cytoscape.js.

CRITICAL: This class enforces a SINGLETON pattern.
Only ONE instance can ever exist. Attempts to create
additional instances will raise an error.
"""

import json
import traceback
from typing import Optional, Dict, Any
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)

from ..themes import ThemeColors, ThemeManager
from .panel import Panel

from .topology_viewer import (
    TopologyViewer as CytoscapeViewer,
    PlatformIconManager,
    get_platform_icon_manager,
)

DEBUG = True


def debug_print(msg: str):
    if DEBUG:
        print(f"[TopologyPreview] {msg}")


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


# Get PyQt's metaclass from Panel's base (QFrame)
_PyQtMeta = type(Panel)


class SingletonMeta(_PyQtMeta):
    """
    Metaclass that enforces singleton pattern.
    Inherits from PyQt's metaclass to avoid conflicts.
    """
    _instances: Dict[type, Any] = {}

    def __call__(cls, *args, **kwargs):
        if cls in cls._instances:
            existing = cls._instances[cls]
            debug_print("=" * 60)
            debug_print(f"🚫 BLOCKED: Attempted to create second {cls.__name__}!")
            debug_print(f"   Existing instance: {id(existing)}")
            debug_print(f"   Call stack:")
            for line in traceback.format_stack()[-6:-1]:
                debug_print(f"      {line.strip()}")
            debug_print("=" * 60)

            # Option 1: Return existing instance (silent singleton)
            # return existing

            # Option 2: Raise error (loud failure - recommended for debugging)
            raise RuntimeError(
                f"Only one {cls.__name__} instance allowed! "
                f"Existing instance: {id(existing)}. "
                f"Check call stack above."
            )

        debug_print(f"✓ Creating first (and only) {cls.__name__} instance")
        instance = super().__call__(*args, **kwargs)
        cls._instances[cls] = instance
        return instance

    @classmethod
    def reset(mcs, cls):
        """Reset singleton (for testing only)."""
        if cls in mcs._instances:
            del mcs._instances[cls]


class TopologyPreviewPanel(Panel, metaclass=SingletonMeta):
    """
    Live topology preview panel - SINGLETON.

    Only ONE instance can exist. The webview is created once
    and never recreated.

    Signals:
        open_full_viewer: Request to open standalone topology viewer
        node_selected: Emitted when a device is clicked
        edge_selected: Emitted when a connection is clicked
    """

    open_full_viewer = pyqtSignal()
    node_selected = pyqtSignal(dict)
    edge_selected = pyqtSignal(dict)

    def __init__(
        self,
        theme_manager: Optional[ThemeManager] = None,
        icon_manager: Optional[PlatformIconManager] = None,
        parent: Optional[QWidget] = None
    ):
        debug_print("=" * 60)
        debug_print("TopologyPreviewPanel.__init__ STARTING")
        debug_print("=" * 60)

        self._current_theme: Optional[ThemeColors] = None
        self._topology_data: Dict[str, Any] = {}
        self._icon_manager = icon_manager or get_platform_icon_manager()
        self._viewer_ready = False
        self._pending_topology: Optional[Dict] = None
        self._viewer: Optional[CytoscapeViewer] = None
        self._webview_id: Optional[int] = None

        super().__init__(
            title="TOPOLOGY PREVIEW",
            icon="🗺",
            theme_manager=theme_manager,
            parent=parent,
            _defer_theme=True
        )

        self._setup_content()

        if theme_manager:
            self.apply_theme(theme_manager.theme)

        debug_print("TopologyPreviewPanel.__init__ COMPLETE")

    def _setup_content(self):
        """Build the panel content - runs exactly ONCE."""
        debug_print("_setup_content() running")

        # Stats row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)

        self._stats_label = QLabel("Devices: 0 | Connections: 0")
        self._stats_label.setObjectName("topoStats")
        stats_row.addWidget(self._stats_label)

        stats_row.addStretch()

        # Bridge status indicator
        self._bridge_status = QLabel("⚪")
        self._bridge_status.setObjectName("bridgeStatus")
        self._bridge_status.setToolTip("JS Bridge: Not connected")
        self._bridge_status.setFixedWidth(20)
        stats_row.addWidget(self._bridge_status)

        # Quick action buttons
        self._fit_btn = QPushButton("Fit")
        self._fit_btn.setObjectName("topoActionBtn")
        self._fit_btn.setFixedWidth(50)
        self._fit_btn.setToolTip("Fit view to all devices")
        self._fit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fit_btn.clicked.connect(self._on_fit_clicked)
        stats_row.addWidget(self._fit_btn)

        self._layout_btn = QPushButton("Layout")
        self._layout_btn.setObjectName("topoActionBtn")
        self._layout_btn.setFixedWidth(60)
        self._layout_btn.setToolTip("Re-apply automatic layout")
        self._layout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._layout_btn.clicked.connect(self._on_layout_clicked)
        stats_row.addWidget(self._layout_btn)

        self._debug_btn = QPushButton("🔍")
        self._debug_btn.setObjectName("topoActionBtn")
        self._debug_btn.setFixedWidth(30)
        self._debug_btn.setToolTip("Debug: Dump state")
        self._debug_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._debug_btn.clicked.connect(self.debug_dump_state)
        stats_row.addWidget(self._debug_btn)

        self._expand_btn = QPushButton("⛶")
        self._expand_btn.setObjectName("topoExpandBtn")
        self._expand_btn.setFixedWidth(30)
        self._expand_btn.setToolTip("Open full topology viewer")
        self._expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._expand_btn.clicked.connect(self.open_full_viewer.emit)
        stats_row.addWidget(self._expand_btn)

        self.content_layout.addLayout(stats_row)

        # Create the ONE AND ONLY CytoscapeViewer
        debug_print("Creating CytoscapeViewer (singleton's viewer)")

        self._viewer = CytoscapeViewer(
            show_controls=False,
            icon_manager=self._icon_manager
        )

        self._webview_id = id(self._viewer._web_view)
        debug_print(f"  WebView id: {self._webview_id}")

        self._viewer._web_view.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )

        # Connect to page load signals to detect reloads/navigation
        self._viewer._web_view.loadStarted.connect(self._on_page_load_started)
        self._viewer._web_view.loadFinished.connect(self._on_page_load_finished)

        self._viewer.setMinimumHeight(250)
        self._viewer.ready.connect(self._on_viewer_ready)
        self._viewer.node_selected.connect(self._on_node_selected)
        self._viewer.edge_selected.connect(self._on_edge_selected)
        self.content_layout.addWidget(self._viewer, 1)

        debug_print("_setup_content() complete")

    def _on_page_load_started(self):
        """Detect when webview starts loading - should only happen once!"""
        if hasattr(self, '_initial_load_done') and self._initial_load_done:
            debug_print("⚠️ PAGE LOAD STARTED - UNEXPECTED RELOAD!")
            debug_print("   This should NOT happen after initial load!")
            import traceback
            for line in traceback.format_stack()[-8:-1]:
                debug_print(f"   {line.strip()}")
        else:
            debug_print("Page load started (initial)")

    def _on_page_load_finished(self, ok: bool):
        """Detect when webview finishes loading."""
        if hasattr(self, '_initial_load_done') and self._initial_load_done:
            debug_print(f"⚠️ PAGE LOAD FINISHED (ok={ok}) - UNEXPECTED!")
            self._viewer_ready = False  # Mark as not ready since page reloaded
            self._bridge_status.setText("🔴")
            self._bridge_status.setToolTip("Page reloaded unexpectedly!")
        else:
            debug_print(f"Page load finished (initial, ok={ok})")
            self._initial_load_done = True

    def _on_viewer_ready(self):
        """Handle Cytoscape viewer initialization."""
        self._viewer_ready = True
        debug_print("=" * 50)
        debug_print("VIEWER READY - JS bridge connected!")
        debug_print(f"  _pending_topology: {len(self._pending_topology) if self._pending_topology else 0} devices")
        debug_print(f"  _topology_data: {len(self._topology_data)} devices")
        debug_print("=" * 50)

        self._bridge_status.setText("🟢")
        self._bridge_status.setToolTip("JS Bridge: Connected")

        if self._current_theme:
            debug_print("Applying theme to viewer")
            viewer_theme = theme_colors_to_viewer_theme(self._current_theme)
            self._viewer.set_theme(viewer_theme)

        # Load any pending topology
        if self._pending_topology:
            debug_print(f"Loading pending topology: {len(self._pending_topology)} devices")
            self._viewer.load_topology(self._pending_topology)
            self._pending_topology = None
        elif self._topology_data:
            # Also try to load existing topology_data if we have it
            debug_print(f"Loading existing topology_data: {len(self._topology_data)} devices")
            self._viewer.load_topology(self._topology_data)

    def _on_node_selected(self, data: dict):
        debug_print(f"Node selected: {data.get('label', data.get('id', 'unknown'))}")
        self.node_selected.emit(data)

    def _on_edge_selected(self, data: dict):
        debug_print(f"Edge selected: {data.get('source', '?')} -> {data.get('target', '?')}")
        self.edge_selected.emit(data)

    def _on_fit_clicked(self):
        if self._viewer and self._viewer_ready:
            self._viewer.fit_view()

    def _on_layout_clicked(self):
        if self._viewer and self._viewer_ready:
            self._viewer.apply_layout('cose')

    def _update_stats(self):
        """Update the stats display."""
        nodes = len(self._topology_data)
        edges = set()
        for device, data in self._topology_data.items():
            for peer in data.get('peers', {}).keys():
                edge_id = tuple(sorted([device, peer]))
                edges.add(edge_id)

        self._stats_label.setText(f"Devices: {nodes} | Connections: {len(edges)}")

    # =========================================================================
    # Public API
    # =========================================================================

    def clear(self):
        """Clear the topology for a new discovery."""
        debug_print("clear()")
        self._topology_data = {}
        self._pending_topology = None

        if self._viewer_ready and self._viewer:
            self._viewer._run_js("TopologyViewer.cy.elements().remove()")

        self._update_stats()

    def load_topology(self, data: Dict[str, Any]):
        """Load complete topology data - SIMPLE VERSION."""
        debug_print(f"load_topology(): {len(data)} devices")

        self._topology_data = data
        self._update_stats()

        if not self._viewer:
            debug_print("  ⚠ No viewer!")
            return

        if not self._viewer._bridge.is_ready:
            debug_print("  ⚠ Bridge not ready, queuing")
            self._pending_topology = data
            return

        debug_print(f"  Sending to JS via viewer.load_topology()...")

        # Use the original TopologyViewer method directly
        # This avoids any callback complexity
        self._viewer.load_topology(data)

        # Schedule fit after layout settles
        QTimer.singleShot(800, self._safe_fit_view)

    def _safe_fit_view(self):
        """Safely call fit_view if still ready."""
        if self._viewer_ready and self._viewer and self._viewer._bridge.is_ready:
            self._viewer.fit_view()

    # =========================================================================
    # DiscoveryController Compatibility
    # =========================================================================

    def update_topology(self, topology: Dict[str, Any]):
        """Called when topology_updated event fires."""
        debug_print(f"update_topology(): {len(topology)} devices")
        self.load_topology(topology)

    def set_device_count(self, count: int):
        """Stats auto-update, this is a no-op."""
        pass

    def set_loading(self):
        """Called at start of discovery."""
        debug_print("set_loading()")
        self.clear()
        self._stats_label.setText("🔄 Discovering...")
        self._bridge_status.setText("🟡")
        self._bridge_status.setToolTip("Discovery in progress")

    def set_ready(self):
        """Called when discovery completes."""
        debug_print("set_ready()")
        self._bridge_status.setText("🟢")
        self._bridge_status.setToolTip("JS Bridge: Connected")
        self._update_stats()

    # =========================================================================
    # Debug
    # =========================================================================

    def debug_dump_state(self):
        """Print current state for debugging."""
        print("\n" + "=" * 60)
        print("🔍 TopologyPreviewPanel Debug (SINGLETON)")
        print("=" * 60)
        print(f"  Instance id: {id(self)}")
        print(f"  viewer_ready: {self._viewer_ready}")
        print(f"  topology_data: {len(self._topology_data)} devices")
        print(f"  pending_topology: {'Yes' if self._pending_topology else 'No'}")

        if self._viewer:
            current_webview_id = id(self._viewer._web_view)
            print(f"  WebView (original): {self._webview_id}")
            print(f"  WebView (current):  {current_webview_id}")
            print(f"  WebView match: {current_webview_id == self._webview_id}")

            if self._viewer_ready:
                self._viewer._run_js(
                    """(function() {
                        if (!TopologyViewer.cy) return 'No Cytoscape instance';
                        return 'Nodes: ' + TopologyViewer.cy.nodes().length + 
                               ', Edges: ' + TopologyViewer.cy.edges().length;
                    })()""",
                    lambda r: print(f"  JS Graph: {r}")
                )
        print("=" * 60 + "\n")

    # =========================================================================
    # Theme
    # =========================================================================

    def apply_theme(self, theme: ThemeColors):
        super().apply_theme(theme)
        self._apply_content_theme(theme)

    def _apply_content_theme(self, theme: ThemeColors):
        self._current_theme = theme

        self._stats_label.setStyleSheet(f"""
            QLabel#topoStats {{
                color: {theme.text_secondary};
                background: transparent;
                border: none;
                font-size: 11px;
            }}
        """)

        self._bridge_status.setStyleSheet(f"""
            QLabel#bridgeStatus {{
                background: transparent;
                border: none;
                font-size: 10px;
            }}
        """)

        btn_style = f"""
            QPushButton#topoActionBtn {{
                background-color: transparent;
                border: 1px solid {theme.border_dim};
                border-radius: 4px;
                padding: 4px 8px;
                color: {theme.text_secondary};
                font-size: 11px;
            }}
            QPushButton#topoActionBtn:hover {{
                border-color: {theme.accent};
                color: {theme.accent};
            }}
        """
        self._fit_btn.setStyleSheet(btn_style)
        self._layout_btn.setStyleSheet(btn_style)
        self._debug_btn.setStyleSheet(btn_style)

        self._expand_btn.setStyleSheet(f"""
            QPushButton#topoExpandBtn {{
                background-color: transparent;
                border: 1px solid {theme.border_dim};
                border-radius: 4px;
                padding: 4px;
                color: {theme.text_secondary};
                font-size: 14px;
            }}
            QPushButton#topoExpandBtn:hover {{
                border-color: {theme.accent};
                color: {theme.accent};
                background-color: {theme.bg_hover};
            }}
        """)

        if self._viewer_ready and self._viewer:
            viewer_theme = theme_colors_to_viewer_theme(theme)
            self._viewer.set_theme(viewer_theme)

    @property
    def is_ready(self) -> bool:
        return self._viewer_ready

    def get_topology_data(self) -> Dict[str, Any]:
        return self._topology_data.copy()