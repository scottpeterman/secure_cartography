"""
SecureCartography v2 - UI Widgets

Custom themed widgets for the SC2 GUI.

Panels:
    Panel - Base panel with title bar
    CollapsiblePanel - Panel that can collapse/expand
    ConnectionPanel - Seed IPs, domains, exclude patterns
    DiscoveryOptionsPanel - Depth, concurrency, toggles, etc.
    OutputPanel - Output directory, debug option
    ProgressPanel - Stats, current target, progress bar
    TopologyPreviewPanel - Topology visualization placeholder
    DiscoveryLogPanel - Styled log output

Primitives:
    TagInput - Text input that creates removable tags
    Tag - Individual removable tag
    ToggleSwitch - Animated toggle switch
    ToggleOption - Toggle with label and description
    StatBox - Individual stat counter
    StatBoxRow - Row of stat counters
"""

# Base panel
from .panel import Panel, CollapsiblePanel

# Primitives
from .tag_input import TagInput, Tag
from .toggle_switch import ToggleSwitch, ToggleOption
from .stat_box import StatBox, StatBoxRow

# Panels
from .connection_panel import ConnectionPanel
from .discovery_options import DiscoveryOptionsPanel
from .output_panel import OutputPanel
from .progress_panel import ProgressPanel
from .topology_preview_panel import TopologyPreviewPanel
from .discovery_log import DiscoveryLogPanel, LogLevel

__all__ = [
    # Base
    'Panel',
    'CollapsiblePanel',

    # Primitives
    'TagInput',
    'Tag',
    'ToggleSwitch',
    'ToggleOption',
    'StatBox',
    'StatBoxRow',

    # Panels
    'ConnectionPanel',
    'DiscoveryOptionsPanel',
    'OutputPanel',
    'ProgressPanel',
    'TopologyPreviewPanel',
    'DiscoveryLogPanel',
    'LogLevel',
]