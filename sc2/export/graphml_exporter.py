"""
SecureCartography v2 - GraphML Exporter

Exports network topology to yEd-compatible GraphML format with embedded icons.
Based on SC1's proven implementation.

Usage:
    from sc2.export.graphml_exporter import GraphMLExporter

    exporter = GraphMLExporter(use_icons=True)
    exporter.export(topology_data, Path("output.graphml"))
"""

import base64
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from xml.dom import minidom

from sc2.scng.utils.resource_helper import (
    read_resource_bytes,
    get_resource_dir,
    iterate_resources,
    resource_exists, read_resource_text
)

@dataclass
class Connection:
    """Represents a single port-to-port connection."""
    local_port: str
    remote_port: str


@dataclass
class Edge:
    """Represents an edge between two nodes."""
    source: str
    target: str
    connections: List[Connection]


@dataclass
class IconMapping:
    """Maps platform patterns to icon files."""
    patterns: Dict[str, str] = field(default_factory=dict)
    defaults: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def load_from_json(cls, json_path: Path) -> 'IconMapping':
        """Load icon mapping from JSON config file."""
        mapping = cls()
        if json_path.exists():
            with open(json_path, 'r') as f:
                config = json.load(f)
                mapping.patterns = config.get('platform_patterns', {})
                mapping.defaults = config.get('defaults', {})
        return mapping


class GraphMLExporter:
    """
    Export network topology to yEd-compatible GraphML format.

    Features:
    - Embedded JPEG icons for device visualization
    - Platform-based icon matching
    - Port labels on edges
    - Multiple layout algorithms
    """

    # Default icon mapping if no JSON config exists
    DEFAULT_PATTERNS = {
        # Cisco
        'catalyst': 'cisco_switch.jpg',
        'nexus': 'cisco_nexus.jpg',
        'c9': 'cisco_switch.jpg',
        'c3': 'cisco_switch.jpg',
        'ws-c': 'cisco_switch.jpg',
        'isr': 'cisco_router.jpg',
        'asr': 'cisco_router.jpg',
        'csr': 'cisco_router.jpg',
        'ios': 'cisco_switch.jpg',
        'nx-os': 'cisco_nexus.jpg',
        # Arista
        'arista': 'arista_switch.jpg',
        'dcs-': 'arista_switch.jpg',
        'eos': 'arista_switch.jpg',
        'veos': 'arista_switch.jpg',
        # Juniper
        'juniper': 'juniper_switch.jpg',
        'junos': 'juniper_switch.jpg',
        'ex4': 'juniper_switch.jpg',
        'qfx': 'juniper_switch.jpg',
        'mx': 'juniper_router.jpg',
        'srx': 'juniper_firewall.jpg',
        # Palo Alto
        'palo': 'paloalto_firewall.jpg',
        'pan-': 'paloalto_firewall.jpg',
        # Fortinet
        'forti': 'fortinet_firewall.jpg',
        # Generic
        'router': 'router.jpg',
        'switch': 'workgroup_switch.jpg',
        'firewall': 'firewall.jpg',
        'wireless': 'wireless_router.jpg',
        'wap': 'wireless_router.jpg',
        'ap': 'wireless_router.jpg',
    }

    DEFAULT_ICONS = {
        'default_switch': 'workgroup_switch.jpg',
        'default_router': 'router.jpg',
        'default_unknown': 'cloud.jpg',
        'default_endpoint': 'pc.jpg',
    }

    def __init__(
            self,
            use_icons: bool = True,
            icons_dir: Optional[Path] = None,
            include_endpoints: bool = True,
            connected_only: bool = False,
            layout_type: str = 'grid',
            font_size: int = 12,
            font_family: str = "Dialog"
    ):
        self.use_icons = use_icons
        self.include_endpoints = include_endpoints
        self.connected_only = connected_only
        self.layout_type = layout_type
        self.font_size = font_size
        self.font_family = font_family

        # Resolve icons directory using importlib.resources
        self._icons_package = None  # Package path for importlib.resources

        if icons_dir:
            # User provided explicit path - use it directly
            self.icons_dir = Path(icons_dir)
        else:
            # Use package resources - this works in wheels
            # Adjust package name to match your structure
            self._icons_package = 'sc2.ui.assets.icons_lib'

            # For operations that need a real path, try to get it
            # This will work for editable installs and source runs
            try:
                self.icons_dir = get_resource_dir(self._icons_package)
            except RuntimeError:
                # Package is zipped - icons_dir won't work, but _load_icon will
                self.icons_dir = None

        # Rest of __init__ stays the same...
        self.icons: Dict[str, str] = {}
        self.icon_id_map: Dict[str, int] = {}
        self.next_icon_id = 1
        self.patterns = self.DEFAULT_PATTERNS.copy()
        self.default_icons = self.DEFAULT_ICONS.copy()
        self._load_icon_config()
        self.processed_connections: Set[tuple] = set()
        self.mac_pattern = re.compile(r'^([0-9a-f]{4}\.){2}[0-9a-f]{4}$', re.IGNORECASE)

    def _load_icon_config(self):
        """Load icon configuration from JSON if available."""
        config_path = None
        config_data = None

        # Try package resources first (works in wheels)
        if self._icons_package:
            try:
                config_data = read_resource_text(
                    self._icons_package,
                    'platform_icon_map.json'
                )
            except Exception:
                pass

        # Fallback to filesystem path
        if config_data is None and self.icons_dir:
            config_path = self.icons_dir / 'platform_icon_map.json'
            if config_path.exists():
                try:
                    with open(config_path, 'r') as f:
                        config_data = f.read()
                except IOError:
                    pass

        if config_data:
            try:
                import json
                config = json.loads(config_data)
                self.patterns.update(config.get('platform_patterns', {}))
                self.default_icons.update(config.get('defaults', {}))
            except json.JSONDecodeError as e:
                print(f"Warning: Could not parse icon config: {e}")

    def _load_icon(self, filename: str) -> Optional[str]:
        """Load and cache an icon file as base64."""
        if filename in self.icons:
            return self.icons[filename]

        base_name = Path(filename).stem

        # Try package resources first (works in wheels)
        if self._icons_package:
            for ext in ['.jpg', '.jpeg', '.png']:
                resource_name = f"{base_name}{ext}"
                try:
                    icon_bytes = read_resource_bytes(self._icons_package, resource_name)
                    b64_data = base64.b64encode(icon_bytes).decode('utf-8')
                    self.icons[filename] = b64_data
                    return b64_data
                except Exception:
                    continue

        # Fallback to filesystem path
        if self.icons_dir:
            for ext in ['.jpg', '.jpeg', '.png']:
                icon_path = self.icons_dir / f"{base_name}{ext}"
                if icon_path.exists():
                    try:
                        with open(icon_path, 'rb') as f:
                            b64_data = base64.b64encode(f.read()).decode('utf-8')
                            self.icons[filename] = b64_data
                            return b64_data
                    except IOError as e:
                        print(f"Warning: Could not load icon {icon_path}: {e}")

        return None



    def _get_icon_for_node(self, node_id: str, platform: str) -> Tuple[Optional[str], Optional[int]]:
        """
        Get icon data and ID for a node based on platform/name matching.

        Returns:
            Tuple of (base64_data, icon_id) or (None, None)
        """
        if not self.use_icons:
            return None, None

        platform_lower = platform.lower() if platform else ''
        node_id_lower = node_id.lower()

        # Try platform patterns first
        for pattern, icon_file in self.patterns.items():
            if pattern.lower() in platform_lower or pattern.lower() in node_id_lower:
                icon_data = self._load_icon(icon_file)
                if icon_data:
                    # Get or assign icon ID
                    if icon_file not in self.icon_id_map:
                        self.icon_id_map[icon_file] = self.next_icon_id
                        self.next_icon_id += 1
                    return icon_data, self.icon_id_map[icon_file]

        # Fall back to default based on node type
        if self._is_endpoint(node_id, platform):
            default_file = self.default_icons.get('default_endpoint', 'pc.jpg')
        elif 'router' in node_id_lower or 'rtr' in node_id_lower:
            default_file = self.default_icons.get('default_router', 'router.jpg')
        elif 'switch' in node_id_lower or 'sw' in node_id_lower:
            default_file = self.default_icons.get('default_switch', 'workgroup_switch.jpg')
        else:
            default_file = self.default_icons.get('default_unknown', 'cloud.jpg')

        icon_data = self._load_icon(default_file)
        if icon_data:
            if default_file not in self.icon_id_map:
                self.icon_id_map[default_file] = self.next_icon_id
                self.next_icon_id += 1
            return icon_data, self.icon_id_map[default_file]

        return None, None

    def _is_endpoint(self, node_id: str, platform: str) -> bool:
        """Determine if a node is an endpoint device."""
        # MAC address format
        if self.mac_pattern.match(node_id):
            return True

        # Platform keywords
        platform_lower = platform.lower() if platform else ''
        endpoint_keywords = {'endpoint', 'camera', 'phone', 'printer', 'pc', 'workstation'}
        if any(kw in platform_lower for kw in endpoint_keywords):
            return True

        return False

    def _preprocess_topology(self, data: Dict) -> Dict:
        """
        Normalize topology and add missing nodes.

        - Creates entries for referenced but undefined peers
        - Optionally filters out endpoints
        - Optionally filters out standalone (unconnected) nodes
        """
        # Find all referenced nodes
        defined = set(data.keys())
        referenced = set()

        for node_data in data.values():
            if isinstance(node_data, dict) and 'peers' in node_data:
                referenced.update(node_data['peers'].keys())

        # Add undefined nodes
        result = data.copy()
        for node_id in referenced - defined:
            result[node_id] = {
                'node_details': {'ip': '', 'platform': ''},
                'peers': {}
            }

        # Filter endpoints if requested
        if not self.include_endpoints:
            endpoints = {
                nid for nid, ndata in result.items()
                if self._is_endpoint(nid, ndata.get('node_details', {}).get('platform', ''))
            }

            filtered = {}
            for node_id, node_data in result.items():
                if node_id not in endpoints:
                    node_copy = node_data.copy()
                    if 'peers' in node_copy:
                        node_copy['peers'] = {
                            pid: pdata for pid, pdata in node_copy['peers'].items()
                            if pid not in endpoints
                        }
                    filtered[node_id] = node_copy
            result = filtered

        # =============================================================
        # NEW: Filter standalone nodes if connected_only is True
        # =============================================================
        if self.connected_only:
            # Build set of all nodes that have at least one connection
            connected_nodes = set()

            for node_id, node_data in result.items():
                if isinstance(node_data, dict):
                    peers = node_data.get('peers', {})
                    if peers:
                        # This node has outgoing connections
                        connected_nodes.add(node_id)
                        # All its peers are also connected
                        connected_nodes.update(peers.keys())

            # Filter to only connected nodes
            filtered = {}
            for node_id, node_data in result.items():
                if node_id in connected_nodes:
                    filtered[node_id] = node_data

            result = filtered

        return result

    def _calculate_position(self, idx: int, total: int) -> Tuple[float, float]:
        """Calculate node position based on layout type."""
        if self.layout_type == 'grid':
            cols = max(1, int(total ** 0.5))
            row = idx // cols
            col = idx % cols
            return col * 200.0, row * 150.0
        elif self.layout_type == 'circle':
            import math
            angle = 2 * math.pi * idx / max(1, total)
            radius = 50 * total / (2 * math.pi)
            return radius * math.cos(angle), radius * math.sin(angle)
        else:
            # Default: vertical list
            return 0.0, idx * 150.0

    def export(self, topology: Dict, output_path: Path) -> None:
        """
        Export topology to GraphML file.

        Args:
            topology: SC2 map format topology dict
            output_path: Output file path
        """
        # Reset state
        self.icons.clear()
        self.icon_id_map.clear()
        self.next_icon_id = 1
        self.processed_connections.clear()

        # Preprocess
        data = self._preprocess_topology(topology)

        # Create root element with namespaces
        root = ET.Element("graphml")
        root.set("xmlns", "http://graphml.graphdrawing.org/xmlns")
        root.set("xmlns:java", "http://www.yworks.com/xml/yfiles-common/1.0/java")
        root.set("xmlns:sys", "http://www.yworks.com/xml/yfiles-common/markup/primitives/2.0")
        root.set("xmlns:x", "http://www.yworks.com/xml/yfiles-common/markup/2.0")
        root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        root.set("xmlns:y", "http://www.yworks.com/xml/graphml")
        root.set("xmlns:yed", "http://www.yworks.com/xml/yed/3")
        root.set("xsi:schemaLocation",
                 "http://graphml.graphdrawing.org/xmlns http://www.yworks.com/xml/schema/graphml/1.1/ygraphml.xsd")

        # Add keys
        self._add_keys(root)

        # Create graph
        graph = ET.SubElement(root, "graph", id="G", edgedefault="directed")

        # Track icons used
        icon_resources: Dict[int, str] = {}

        # Add nodes
        total_nodes = len(data)
        for idx, (node_id, node_data) in enumerate(data.items()):
            icon_id, icon_data = self._add_node(graph, node_id, node_data, idx, total_nodes)
            if icon_id and icon_data:
                icon_resources[icon_id] = icon_data

        # Add edges
        for source_id, source_data in data.items():
            if 'peers' not in source_data:
                continue
            for target_id, peer_data in source_data['peers'].items():
                connections = [
                    Connection(local, remote)
                    for local, remote in peer_data.get('connections', [])
                ]
                if connections:
                    self._add_edge(graph, Edge(source_id, target_id, connections))

        # Add icon resources
        if icon_resources:
            self._add_resources(root, icon_resources)

        # Write file
        xml_str = ET.tostring(root, encoding='unicode')
        pretty_xml = minidom.parseString(xml_str).toprettyxml(indent="  ")

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(pretty_xml)

    def _add_keys(self, root: ET.Element) -> None:
        """Add GraphML key definitions."""
        keys = [
            ("graph", "d0", "Description", "string", None),
            ("port", "d1", None, None, "portgraphics"),
            ("port", "d2", None, None, "portgeometry"),
            ("port", "d3", None, None, "portuserdata"),
            ("node", "d4", "url", "string", None),
            ("node", "d5", "description", "string", None),
            ("node", "d6", None, None, "nodegraphics"),
            ("graphml", "d7", None, None, "resources"),
            ("edge", "d8", "url", "string", None),
            ("edge", "d9", "description", "string", None),
            ("edge", "d10", None, None, "edgegraphics"),
        ]

        for target, key_id, name, attr_type, yfiles_type in keys:
            key = ET.SubElement(root, "key")
            key.set("for", target)
            key.set("id", key_id)
            if name:
                key.set("attr.name", name)
            if attr_type:
                key.set("attr.type", attr_type)
            if yfiles_type:
                key.set("yfiles.type", yfiles_type)

    def _add_node(
        self,
        graph: ET.Element,
        node_id: str,
        node_data: Dict,
        idx: int,
        total: int
    ) -> Tuple[Optional[int], Optional[str]]:
        """Add a node to the graph, returns (icon_id, icon_data) if icon used."""
        node = ET.SubElement(graph, "node", id=node_id)
        data_elem = ET.SubElement(node, "data", key="d6")

        details = node_data.get('node_details', {})
        ip = details.get('ip', '')
        platform = details.get('platform', '')

        x, y = self._calculate_position(idx, total)

        if self.use_icons:
            icon_data, icon_id = self._get_icon_for_node(node_id, platform)
            if icon_data and icon_id:
                self._add_image_node(data_elem, node_id, ip, platform, x, y, icon_id)
                return icon_id, icon_data

        # Fallback to shape node
        self._add_shape_node(data_elem, node_id, ip, platform, x, y)
        return None, None

    def _add_image_node(
        self,
        data_elem: ET.Element,
        node_id: str,
        ip: str,
        platform: str,
        x: float,
        y: float,
        icon_id: int
    ) -> None:
        """Add an image-based node."""
        image_node = ET.SubElement(data_elem, "y:ImageNode")

        # Geometry
        geom = ET.SubElement(image_node, "y:Geometry")
        geom.set("height", "51.0")
        geom.set("width", "90.0")
        geom.set("x", str(x))
        geom.set("y", str(y))

        # Fill
        fill = ET.SubElement(image_node, "y:Fill")
        fill.set("color", "#CCCCFF")
        fill.set("transparent", "false")

        # Border
        border = ET.SubElement(image_node, "y:BorderStyle")
        border.set("color", "#000000")
        border.set("type", "line")
        border.set("width", "1.0")

        # Label
        label = ET.SubElement(image_node, "y:NodeLabel")
        label.set("alignment", "center")
        label.set("autoSizePolicy", "content")
        label.set("fontFamily", self.font_family)
        label.set("fontSize", str(self.font_size))
        label.set("fontStyle", "plain")
        label.set("hasBackgroundColor", "false")
        label.set("hasLineColor", "false")
        label.set("modelName", "eight_pos")
        label.set("modelPosition", "s")
        label.set("textColor", "#333333")
        label.set("visible", "true")

        # Build label text
        label_parts = [node_id]
        if ip:
            label_parts.append(ip)
        if platform:
            label_parts.append(platform)
        label.text = '\n'.join(label_parts)

        # Image reference
        image = ET.SubElement(image_node, "y:Image")
        image.set("refid", str(icon_id))

    def _add_shape_node(
        self,
        data_elem: ET.Element,
        node_id: str,
        ip: str,
        platform: str,
        x: float,
        y: float
    ) -> None:
        """Add a shape-based node (fallback when icons disabled/unavailable)."""
        shape_node = ET.SubElement(data_elem, "y:ShapeNode")

        # Geometry
        geom = ET.SubElement(shape_node, "y:Geometry")
        geom.set("height", "60")
        geom.set("width", "120")
        geom.set("x", str(x))
        geom.set("y", str(y))

        # Fill
        fill = ET.SubElement(shape_node, "y:Fill")
        fill.set("color", "#FFFFFF")
        fill.set("transparent", "false")

        # Border
        border = ET.SubElement(shape_node, "y:BorderStyle")
        border.set("color", "#000000")
        border.set("type", "line")
        border.set("width", "1.0")

        # Shape
        shape = ET.SubElement(shape_node, "y:Shape")
        shape.set("type", "roundrectangle")

        # Label
        label = ET.SubElement(shape_node, "y:NodeLabel")
        label.set("alignment", "center")
        label.set("autoSizePolicy", "content")
        label.set("fontFamily", self.font_family)
        label.set("fontSize", str(self.font_size))
        label.set("modelName", "internal")
        label.set("modelPosition", "c")
        label.set("textColor", "#000000")
        label.set("visible", "true")

        label_parts = [node_id]
        if platform:
            label_parts.append(platform)
        if ip:
            label_parts.append(ip)
        label.text = '\n'.join(label_parts)

    def _add_edge(self, graph: ET.Element, edge: Edge) -> None:
        """Add edges for each connection."""
        for conn in edge.connections:
            # Create unique key to avoid duplicates
            conn_key = tuple(sorted([
                f"{edge.source}:{conn.local_port}",
                f"{edge.target}:{conn.remote_port}"
            ]))

            if conn_key in self.processed_connections:
                continue
            self.processed_connections.add(conn_key)

            edge_id = f"e{hash(conn_key) % 10000000:x}"
            edge_elem = ET.SubElement(
                graph, "edge",
                id=edge_id,
                source=edge.source,
                target=edge.target
            )

            data_elem = ET.SubElement(edge_elem, "data", key="d10")
            polyline = ET.SubElement(data_elem, "y:PolyLineEdge")

            # Line style
            line = ET.SubElement(polyline, "y:LineStyle")
            line.set("color", "#000000")
            line.set("type", "line")
            line.set("width", "1.0")

            # Arrows (none for undirected)
            arrows = ET.SubElement(polyline, "y:Arrows")
            arrows.set("source", "none")
            arrows.set("target", "none")

            # Port labels
            self._add_edge_label(polyline, conn.local_port, is_source=True)
            self._add_edge_label(polyline, conn.remote_port, is_source=False)

            # Bend style
            bend = ET.SubElement(polyline, "y:BendStyle")
            bend.set("smoothed", "false")

    def _add_edge_label(self, polyline: ET.Element, port: str, is_source: bool) -> None:
        """Add a port label to an edge."""
        label = ET.SubElement(polyline, "y:EdgeLabel")
        label.set("alignment", "center")
        label.set("backgroundColor", "#FFFFFF")
        label.set("configuration", "AutoFlippingLabel")
        label.set("fontFamily", self.font_family)
        label.set("fontSize", str(self.font_size))
        label.set("fontStyle", "plain")
        label.set("hasLineColor", "false")
        label.set("modelName", "free")
        label.set("modelPosition", "anywhere")
        label.set("textColor", "#000000")
        label.set("visible", "true")
        label.set("distance", "10.0")
        label.set("ratio", "0.2" if is_source else "0.8")
        label.set("preferredPlacement", "source_on_edge" if is_source else "target_on_edge")
        label.text = port

    def _add_resources(self, root: ET.Element, icon_resources: Dict[int, str]) -> None:
        """Add resources section with embedded icons."""
        resources_data = ET.SubElement(root, "data", key="d7")
        y_resources = ET.SubElement(resources_data, "y:Resources")

        for icon_id, b64_data in icon_resources.items():
            resource = ET.SubElement(y_resources, "y:Resource")
            resource.set("id", str(icon_id))
            resource.set("type", "java.awt.image.BufferedImage")
            resource.set("xml:space", "preserve")

            # Clean and chunk the base64 data
            clean_data = b64_data.replace('\n', '').replace('\r', '')
            chunks = [clean_data[i:i+76] for i in range(0, len(clean_data), 76)]
            resource.text = '\n'.join(chunks)


# =============================================================================
# CLI
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Export SC2 topology to yEd GraphML format'
    )
    parser.add_argument('input', help='Input topology JSON file')
    parser.add_argument('output', help='Output GraphML file')
    parser.add_argument('--no-icons', action='store_true',
                        help='Use shapes instead of icons')
    parser.add_argument('--no-endpoints', action='store_true',
                        help='Exclude endpoint devices')
    parser.add_argument('--icons-dir', type=str,
                        help='Custom icons directory')
    parser.add_argument('--layout', choices=['grid', 'circle', 'list'],
                        default='grid', help='Layout algorithm')

    args = parser.parse_args()

    # Load topology
    with open(args.input, 'r') as f:
        topology = json.load(f)

    # Create exporter
    exporter = GraphMLExporter(
        use_icons=not args.no_icons,
        icons_dir=Path(args.icons_dir) if args.icons_dir else None,
        include_endpoints=not args.no_endpoints,
        layout_type=args.layout
    )

    # Export
    exporter.export(topology, Path(args.output))
    print(f"Exported to {args.output}")
    print(f"  Nodes: {len(topology)}")
    print(f"  Icons: {'enabled' if not args.no_icons else 'disabled'}")
    print(f"  Layout: {args.layout}")


if __name__ == '__main__':
    main()