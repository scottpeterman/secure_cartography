#!/usr/bin/env python3
"""
SecureCartography Topology Visualizer
Workspace-based architecture for single-server, multi-user deployment

Architecture:
- Maps live in server-side workspace (maps/ directory)
- Each map is a self-contained folder with topology.json + layout.json
- UI provides map selector instead of file upload
- Compatible with desktop packaging and team server deployment
"""

from flask import Flask, render_template, Blueprint, send_from_directory, request, session, jsonify, send_file
import json
import os
from datetime import datetime
from pathlib import Path
import tempfile
import shutil
import re

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-change-in-production')

# Import your existing exporters
from graphml_mapper4 import NetworkGraphMLExporter
from drawio_mapper2 import NetworkDrawioExporter

# Create export blueprint
export_bp = Blueprint('export', __name__, url_prefix='/api/export')

# Configuration
MAPS_WORKSPACE = 'maps'
ICON_MAP_FILE = 'data/platform_icon_map.json'
ICONS_DIR = 'static/icons_lib'


def ensure_workspace():
    """Ensure maps workspace exists"""
    os.makedirs(MAPS_WORKSPACE, exist_ok=True)


def list_available_maps():
    """
    List all available maps in workspace

    Returns:
        List of map names (directory names in workspace)
    """
    ensure_workspace()
    maps = []

    for item in os.listdir(MAPS_WORKSPACE):
        map_path = os.path.join(MAPS_WORKSPACE, item)
        if os.path.isdir(map_path):
            # Check if it has a topology.json file
            topology_file = os.path.join(map_path, 'topology.json')
            if os.path.exists(topology_file):
                maps.append({
                    'name': item,
                    'has_layout': os.path.exists(os.path.join(map_path, 'layout.json')),
                    'topology_size': os.path.getsize(topology_file),
                    'modified': datetime.fromtimestamp(os.path.getmtime(topology_file)).isoformat()
                })

    return sorted(maps, key=lambda x: x['name'])


def get_map_topology_path(map_name):
    """Get path to topology.json for a map"""
    return os.path.join(MAPS_WORKSPACE, map_name, 'topology.json')


def get_map_layout_path(map_name):
    """Get path to layout.json for a map"""
    return os.path.join(MAPS_WORKSPACE, map_name, 'layout.json')


def validate_map_name(map_name):
    """
    Validate map name for security

    Prevents path traversal and ensures safe filesystem operations
    """
    if not map_name:
        return False

    # Prevent path traversal
    if '..' in map_name or '/' in map_name or '\\' in map_name:
        return False

    # Ensure reasonable name (alphanumeric, underscore, hyphen)
    if not re.match(r'^[a-zA-Z0-9_-]+$', map_name):
        return False

    return True


def load_topology(map_name):
    """Load topology JSON for a map"""
    if not validate_map_name(map_name):
        raise ValueError(f"Invalid map name: {map_name}")

    topology_file = get_map_topology_path(map_name)

    try:
        with open(topology_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Topology not found for map: {map_name}")


def load_layout(map_name):
    """Load saved layout for a map"""
    if not validate_map_name(map_name):
        raise ValueError(f"Invalid map name: {map_name}")

    layout_file = get_map_layout_path(map_name)

    if os.path.exists(layout_file):
        try:
            with open(layout_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load layout file {layout_file}: {e}")
            return None
    return None


def save_layout(map_name, layout_data):
    """Save layout for a map"""
    if not validate_map_name(map_name):
        raise ValueError(f"Invalid map name: {map_name}")

    # Ensure map directory exists
    map_dir = os.path.join(MAPS_WORKSPACE, map_name)
    os.makedirs(map_dir, exist_ok=True)

    layout_file = get_map_layout_path(map_name)

    # Add metadata
    layout_data['map_name'] = map_name
    layout_data['server_timestamp'] = datetime.now().isoformat()

    try:
        with open(layout_file, 'w') as f:
            json.dump(layout_data, f, indent=2)
        return True
    except IOError as e:
        print(f"Error saving layout to {layout_file}: {e}")
        return False


def load_icon_map():
    """Load platform icon mapping configuration"""
    try:
        with open(ICON_MAP_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # Return default icon map if file doesn't exist
        return {
            'defaults': {
                'default_unknown': 'cloud_(4).jpg'
            },
            'platform_patterns': {},
            'fallback_patterns': {}
        }


def get_icon_for_platform(platform, icon_map, device_name=''):
    """
    Determine the icon file for a given platform based on mapping rules

    Args:
        platform: Platform string (e.g., '7206VXR', 'IOSv', 'vEOS-lab')
        icon_map: Icon mapping configuration dictionary
        device_name: Optional device name for name pattern matching

    Returns:
        Icon filename (e.g., '7500ars_(7513).jpg')
    """
    if not platform:
        return icon_map['defaults']['default_unknown']

    # Direct platform pattern match
    for pattern, icon in icon_map.get('platform_patterns', {}).items():
        if pattern.lower() in platform.lower():
            return icon

    # Fallback pattern matching with both platform and device name patterns
    platform_lower = platform.lower()
    device_name_lower = device_name.lower() if device_name else ''

    for device_type, rules in icon_map.get('fallback_patterns', {}).items():
        # Check platform patterns first
        for pattern in rules.get('platform_patterns', []):
            if pattern.lower() in platform_lower:
                icon_key = rules.get('icon', 'default_unknown')
                return icon_map['defaults'].get(icon_key, 'cloud_(4).jpg')

        # Check device name patterns if device name provided
        if device_name_lower:
            for pattern in rules.get('name_patterns', []):
                if pattern.lower() in device_name_lower:
                    icon_key = rules.get('icon', 'default_unknown')
                    return icon_map['defaults'].get(icon_key, 'cloud_(4).jpg')

    # Ultimate fallback
    return icon_map['defaults'].get('default_unknown', 'cloud_(4).jpg')


def convert_to_cytoscape(topology_data, icon_map):
    """
    Convert SecureCartography JSON format to Cytoscape.js elements format
    Handles both primary nodes AND leaf nodes that only appear in peer lists
    """
    nodes = []
    edges = []
    edge_set = set()
    node_set = set()  # Track which nodes we've created

    # FIRST PASS: Create nodes from top-level entries
    for device_name, device_data in topology_data.items():
        node_details = device_data.get('node_details', {})
        platform = node_details.get('platform', 'Unknown')
        ip = node_details.get('ip', '')

        icon_file = get_icon_for_platform(platform, icon_map, device_name)
        icon_url = f'/static/icons_lib/{icon_file}'

        nodes.append({
            'data': {
                'id': device_name,
                'label': device_name,
                'ip': ip,
                'platform': platform,
                'icon': icon_url
            }
        })
        node_set.add(device_name)

    # SECOND PASS: Create edges AND discover leaf nodes
    for source_device, device_data in topology_data.items():
        peers = device_data.get('peers', {})

        for target_device, peer_data in peers.items():
            # Check if target node exists, if not create it as a leaf node
            if target_device not in node_set:
                # Create leaf node with minimal information
                icon_file = get_icon_for_platform('Unknown', icon_map, target_device)
                icon_url = f'/static/icons_lib/{icon_file}'

                nodes.append({
                    'data': {
                        'id': target_device,
                        'label': target_device,
                        'ip': '',  # Unknown
                        'platform': 'Leaf Node (Discovered)',
                        'icon': icon_url
                    }
                })
                node_set.add(target_device)

            connections = peer_data.get('connections', [])
            for connection in connections:
                source_int = connection[0]
                target_int = connection[1]

                edge_id = f"{source_device}_{target_device}_{source_int}_{target_int}"
                reverse_edge_id = f"{target_device}_{source_device}_{target_int}_{source_int}"

                if edge_id not in edge_set and reverse_edge_id not in edge_set:
                    edge_set.add(edge_id)

                    edges.append({
                        'data': {
                            'id': edge_id,
                            'source': source_device,
                            'target': target_device,
                            'source_int': source_int,
                            'target_int': target_int,
                            'label': f"{source_int} ↔ {target_int}"
                        }
                    })

    return {'nodes': nodes, 'edges': edges}


# ===== MAIN APP ROUTES =====

@app.route('/')
def index():
    """Main visualization page"""
    return render_template('index.html')


@app.route('/static/themes.css')
def serve_themes():
    """Serve the themes CSS file"""
    return send_from_directory('static', 'themes.css')


@app.route('/api/maps')
def api_list_maps():
    """
    List all available maps in workspace

    Returns:
        {
            "success": true,
            "maps": [
                {"name": "lab", "has_layout": true, "topology_size": 1234, "modified": "..."},
                ...
            ]
        }
    """
    try:
        maps = list_available_maps()
        return jsonify({
            'success': True,
            'maps': maps,
            'workspace': MAPS_WORKSPACE
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/maps/<map_name>')
def api_get_map(map_name):
    """
    Get topology and layout data for a specific map

    Returns:
        {
            "success": true,
            "map_name": "lab",
            "data": {"nodes": [...], "edges": [...]},
            "saved_layout": {...} or null
        }
    """
    try:
        if not validate_map_name(map_name):
            return jsonify({
                'success': False,
                'error': f'Invalid map name: {map_name}'
            }), 400

        print(f"\n[API REQUEST] GET /api/maps/{map_name}")

        # Load topology
        topology = load_topology(map_name)
        print(f"  Loaded topology: {len(topology)} devices")

        # Convert to Cytoscape format
        icon_map = load_icon_map()
        cytoscape_data = convert_to_cytoscape(topology, icon_map)

        # Load saved layout if exists
        saved_layout = load_layout(map_name)

        return jsonify({
            'success': True,
            'map_name': map_name,
            'data': cytoscape_data,
            'saved_layout': saved_layout
        })

    except FileNotFoundError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 404
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/maps/<map_name>/layout', methods=['POST'])
def api_save_map_layout(map_name):
    """
    Save layout for a specific map

    POST body:
    {
        "positions": {"node_id": {"x": 1, "y": 2}, ...},
        "selectedLayout": "cose",
        "timestamp": "ISO_timestamp"
    }
    """
    try:
        if not validate_map_name(map_name):
            return jsonify({
                'success': False,
                'error': f'Invalid map name: {map_name}'
            }), 400

        layout_data = request.get_json()

        if not layout_data or 'positions' not in layout_data:
            return jsonify({
                'success': False,
                'error': 'Invalid layout data'
            }), 400

        print(f"\n[API REQUEST] POST /api/maps/{map_name}/layout")
        print(f"  Saving {len(layout_data['positions'])} node positions")

        success = save_layout(map_name, layout_data)

        if success:
            return jsonify({
                'success': True,
                'message': 'Layout saved successfully',
                'map_name': map_name
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to save layout file'
            }), 500

    except Exception as e:
        print(f"  ERROR: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/maps/<map_name>/layout', methods=['DELETE'])
def api_delete_map_layout(map_name):
    """Delete saved layout for a specific map"""
    try:
        if not validate_map_name(map_name):
            return jsonify({
                'success': False,
                'error': f'Invalid map name: {map_name}'
            }), 400

        layout_file = get_map_layout_path(map_name)

        if os.path.exists(layout_file):
            os.remove(layout_file)
            return jsonify({
                'success': True,
                'message': f'Layout reset for {map_name}'
            })
        else:
            return jsonify({
                'success': True,
                'message': 'No saved layout to reset'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/maps/<map_name>/topology', methods=['POST'])
def api_save_map_topology(map_name):
    """Save/update topology for a specific map (for editing support)"""
    try:
        if not validate_map_name(map_name):
            return jsonify({'success': False, 'error': f'Invalid map name: {map_name}'}), 400

        topology_data = request.get_json()
        if not topology_data:
            return jsonify({'success': False, 'error': 'No topology data provided'}), 400

        topology_file = get_map_topology_path(map_name)

        # Backup existing file
        if os.path.exists(topology_file):
            backup_file = topology_file + '.backup'
            shutil.copy2(topology_file, backup_file)

        # Save new topology
        with open(topology_file, 'w') as f:
            json.dump(topology_data, f, indent=2)

        print(f"\n[TOPOLOGY UPDATE] Saved changes to {map_name} ({len(topology_data)} devices)")

        return jsonify({
            'success': True,
            'message': 'Topology saved successfully',
            'map_name': map_name,
            'device_count': len(topology_data)
        })

    except Exception as e:
        print(f"  ERROR: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route("/data/<path:filename>")
def serve_data(filename):
    """Serve data files (icon map, etc)"""
    return send_from_directory("data", filename)


@app.route('/api/maps/upload', methods=['POST'])
def api_upload_map():
    """Upload a new topology JSON file"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400

        map_name = request.form.get('map_name', '')
        if not map_name:
            map_name = Path(file.filename).stem
        map_name = map_name.replace(' ', '_')

        if not validate_map_name(map_name):
            return jsonify({'success': False, 'error': f'Invalid map name'}), 400

        topology_file = get_map_topology_path(map_name)
        if os.path.exists(topology_file):
            return jsonify({'success': False, 'error': f'Map "{map_name}" already exists'}), 409

        try:
            content = file.read()
            topology_data = json.loads(content)
        except json.JSONDecodeError as e:
            return jsonify({'success': False, 'error': f'Invalid JSON: {str(e)}'}), 400

        map_dir = os.path.join(MAPS_WORKSPACE, map_name)
        os.makedirs(map_dir, exist_ok=True)
        with open(topology_file, 'w') as f:
            json.dump(topology_data, f, indent=2)

        print(f"\n[UPLOAD] Created map: {map_name} ({len(topology_data)} devices)")
        return jsonify({'success': True, 'map_name': map_name, 'device_count': len(topology_data)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/maps/<map_name>', methods=['DELETE'])
def api_delete_map(map_name):
    """Delete an entire map"""
    try:
        if not validate_map_name(map_name):
            return jsonify({'success': False, 'error': 'Invalid map name'}), 400

        map_dir = os.path.join(MAPS_WORKSPACE, map_name)
        if not os.path.exists(map_dir):
            return jsonify({'success': False, 'error': 'Map not found'}), 404

        shutil.rmtree(map_dir)
        print(f"\n[DELETE] Removed map: {map_name}")
        return jsonify({'success': True, 'message': f'Map deleted'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/maps/<map_name>/rename', methods=['PUT'])
def api_rename_map(map_name):
    """Rename a map"""
    try:
        if not validate_map_name(map_name):
            return jsonify({'success': False, 'error': 'Invalid name'}), 400

        data = request.get_json()
        new_name = data.get('new_name', '').strip()

        if not new_name or not validate_map_name(new_name):
            return jsonify({'success': False, 'error': 'Invalid new name'}), 400

        old_dir = os.path.join(MAPS_WORKSPACE, map_name)
        new_dir = os.path.join(MAPS_WORKSPACE, new_name)

        if not os.path.exists(old_dir):
            return jsonify({'success': False, 'error': 'Not found'}), 404
        if os.path.exists(new_dir):
            return jsonify({'success': False, 'error': f'"{new_name}" exists'}), 409

        os.rename(old_dir, new_dir)
        print(f"\n[RENAME] {map_name} -> {new_name}")
        return jsonify({'success': True, 'old_name': map_name, 'new_name': new_name})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/maps/<map_name>/export')
def api_export_map(map_name):
    """Export topology JSON"""
    try:
        if not validate_map_name(map_name):
            return jsonify({'success': False, 'error': 'Invalid name'}), 400

        topology_file = get_map_topology_path(map_name)
        if not os.path.exists(topology_file):
            return jsonify({'success': False, 'error': 'Not found'}), 404

        return send_from_directory(
            os.path.join(MAPS_WORKSPACE, map_name),
            'topology.json',
            as_attachment=True,
            download_name=f'{map_name}_topology.json'
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/maps/<map_name>/copy', methods=['POST'])
def api_copy_map(map_name):
    """Create a copy of an existing map (topology + layout)"""
    try:
        if not validate_map_name(map_name):
            return jsonify({'success': False, 'error': 'Invalid source map name'}), 400

        data = request.get_json()
        new_name = data.get('new_name', '').strip()

        if not new_name or not validate_map_name(new_name):
            return jsonify({'success': False, 'error': 'Invalid new name'}), 400

        source_dir = os.path.join(MAPS_WORKSPACE, map_name)
        dest_dir = os.path.join(MAPS_WORKSPACE, new_name)

        if not os.path.exists(source_dir):
            return jsonify({'success': False, 'error': 'Source map not found'}), 404

        if os.path.exists(dest_dir):
            return jsonify({'success': False, 'error': f'Map "{new_name}" already exists'}), 409

        # Copy entire directory (topology + layout)
        shutil.copytree(source_dir, dest_dir)

        # Update metadata in copied layout file if it exists
        layout_file = os.path.join(dest_dir, 'layout.json')
        if os.path.exists(layout_file):
            try:
                with open(layout_file, 'r') as f:
                    layout_data = json.load(f)

                # Update metadata
                layout_data['map_name'] = new_name
                layout_data['copied_from'] = map_name
                layout_data['copy_timestamp'] = datetime.now().isoformat()

                with open(layout_file, 'w') as f:
                    json.dump(layout_data, f, indent=2)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not update layout metadata: {e}")

        print(f"\n[COPY] Created copy: {map_name} -> {new_name}")

        return jsonify({
            'success': True,
            'source_name': map_name,
            'new_name': new_name,
            'message': f'Successfully copied {map_name} to {new_name}'
        })

    except Exception as e:
        print(f"  ERROR: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/diagnostics')
def api_diagnostics():
    """Diagnostic endpoint to check workspace and icon system"""
    diagnostics = {
        'working_directory': os.getcwd(),
        'workspace': {
            'path': MAPS_WORKSPACE,
            'exists': os.path.exists(MAPS_WORKSPACE),
            'map_count': 0,
            'maps': []
        },
        'icon_map_file': {
            'path': ICON_MAP_FILE,
            'exists': os.path.exists(ICON_MAP_FILE)
        },
        'icons_directory': {
            'path': ICONS_DIR,
            'exists': os.path.exists(ICONS_DIR),
            'icon_count': 0
        }
    }

    # Check workspace
    if os.path.exists(MAPS_WORKSPACE):
        maps = list_available_maps()
        diagnostics['workspace']['map_count'] = len(maps)
        diagnostics['workspace']['maps'] = maps

    # Check icon directory
    if os.path.exists(ICONS_DIR):
        icon_files = [f for f in os.listdir(ICONS_DIR) if f.endswith(('.jpg', '.png', '.gif', '.svg'))]
        diagnostics['icons_directory']['icon_count'] = len(icon_files)

    return jsonify(diagnostics)


# ===== EXPORT BLUEPRINT ROUTES =====

@export_bp.route('/graphml', methods=['POST'])
def export_graphml_with_icons():
    """
    Export topology to GraphML with vendor-specific icons

    Request JSON:
    {
        "map_name": "site_name",
        "layout": "tree",  # grid, tree, balloon
        "include_endpoints": true
    }

    Returns: GraphML file download
    """
    try:
        data = request.json
        map_name = data.get('map_name', 'network_topology')
        layout = data.get('layout', 'tree')
        include_endpoints = data.get('include_endpoints', True)

        if not map_name:
            return jsonify({'error': 'No map name provided'}), 400

        print(f"\n[GRAPHML EXPORT] Map: {map_name}")

        # Load topology from server filesystem
        if not validate_map_name(map_name):
            return jsonify({'error': 'Invalid map name'}), 400

        network_data = load_topology(map_name)
        print(f"  Loaded topology: {len(network_data)} devices")

        # Create temporary output file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.graphml', delete=False) as tmp:
            tmp_path = tmp.name

        # Use your existing exporter with the topology JSON directly
        exporter = NetworkGraphMLExporter(
            include_endpoints=include_endpoints,
            use_icons=True,
            layout_type=layout,
            icons_dir=ICONS_DIR
        )

        exporter.export_to_graphml(network_data, tmp_path)
        print(f"  Exported to: {tmp_path}")

        # Send file and cleanup
        response = send_file(
            tmp_path,
            mimetype='application/xml',
            as_attachment=True,
            download_name=f'{map_name}.graphml'
        )

        # Schedule cleanup after response is sent
        @response.call_on_close
        def cleanup():
            try:
                os.unlink(tmp_path)
            except:
                pass

        return response

    except FileNotFoundError as e:
        return jsonify({'error': f'Map not found: {map_name}'}), 404
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500





@app.route('/api/platform-map')
def get_platform_map():
    """Serve platform icon mapping configuration"""
    platform_map_file = Path('./data/platform_icon_map.json')

    if not platform_map_file.exists():
        # Return default minimal mapping
        return jsonify({
            'base_path': 'static/icons_lib',
            'platform_patterns': {
                'Cisco IOS': 'router.jpg',
                'Cisco Nexus': 'Nexus_7000.jpg',
                'Arista EOS': 'Nexus_5000.jpg',
                'Generic Switch': 'layer_3_switch.jpg',
                'Generic Router': 'router.jpg'
            },
            'defaults': {
                'default_unknown': 'generic_processor.jpg',
                'default_switch': 'layer_3_switch.jpg',
                'default_router': 'router.jpg'
            }
        })

    with open(platform_map_file, 'r', encoding='utf-8') as f:
        platform_map = json.load(f)

    return jsonify(platform_map)


@export_bp.route('/drawio', methods=['POST'])
def export_drawio_with_icons():
    """
    Export topology to DrawIO with vendor-specific icons

    Request JSON:
    {
        "map_name": "site_name",
        "layout": "tree",
        "include_endpoints": true
    }

    Returns: DrawIO file download
    """
    try:
        data = request.json
        map_name = data.get('map_name', 'network_topology')
        layout = data.get('layout', 'tree')
        include_endpoints = data.get('include_endpoints', True)

        if not map_name:
            return jsonify({'error': 'No map name provided'}), 400

        print(f"\n[DRAWIO EXPORT] Map: {map_name}")

        # Load topology from server filesystem
        if not validate_map_name(map_name):
            return jsonify({'error': 'Invalid map name'}), 400

        network_data = load_topology(map_name)
        print(f"  Loaded topology: {len(network_data)} devices")

        # Create temporary output file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.drawio', delete=False) as tmp:
            tmp_path = tmp.name

        # Use your existing exporter with the topology JSON directly
        exporter = NetworkDrawioExporter(
            include_endpoints=include_endpoints,
            use_icons=True,
            layout_type=layout,
            icons_dir=ICONS_DIR
        )

        exporter.export_to_drawio(network_data, tmp_path)
        print(f"  Exported to: {tmp_path}")

        # Send file
        response = send_file(
            tmp_path,
            mimetype='application/xml',
            as_attachment=True,
            download_name=f'{map_name}.drawio'
        )

        @response.call_on_close
        def cleanup():
            try:
                os.unlink(tmp_path)
            except:
                pass

        return response

    except FileNotFoundError as e:
        return jsonify({'error': f'Map not found: {map_name}'}), 404
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ===== APPLICATION STARTUP =====

# Register the export blueprint
app.register_blueprint(export_bp)

if __name__ == '__main__':
    # Ensure required directories exist
    os.makedirs(MAPS_WORKSPACE, exist_ok=True)
    os.makedirs('data', exist_ok=True)
    os.makedirs('static/icons_lib', exist_ok=True)
    os.makedirs('templates', exist_ok=True)

    print("=" * 70)
    print("SecureCartography Topology Visualizer - WORKSPACE ARCHITECTURE")
    print("=" * 70)
    print(f"\nWorking directory: {os.getcwd()}")
    print(f"Maps workspace: {MAPS_WORKSPACE}/")
    print(f"Icon map: {ICON_MAP_FILE}")
    print(f"Icons directory: {ICONS_DIR}/")
    print("=" * 70)

    # Check workspace
    print("\n[WORKSPACE CHECK]")
    if os.path.exists(MAPS_WORKSPACE):
        maps = list_available_maps()
        print(f"  Maps found: {len(maps)}")
        for map_info in maps:
            layout_status = "✓ has layout" if map_info['has_layout'] else "○ no layout"
            print(f"    • {map_info['name']} ({layout_status})")
        if not maps:
            print("    (No maps found - add folders to maps/ directory)")
    else:
        print(f"  Workspace will be created at: {MAPS_WORKSPACE}/")

    # Check icons
    print(f"\n[ICON SYSTEM CHECK]")
    if os.path.exists(ICONS_DIR):
        icon_count = len([f for f in os.listdir(ICONS_DIR) if f.endswith(('.jpg', '.png', '.gif', '.svg'))])
        print(f"  Icons available: {icon_count}")
    else:
        print(f"  Icons directory not found: {ICONS_DIR}")

    if os.path.exists(ICON_MAP_FILE):
        print(f"  Icon map: Found")
    else:
        print(f"  Icon map: NOT FOUND - {ICON_MAP_FILE}")

    print("=" * 70)
    print("\nAPI Endpoints:")
    print("  GET  /api/maps                      - List available maps")
    print("  GET  /api/maps/{map_name}           - Load map topology + layout")
    print("  POST /api/maps/{map_name}/layout    - Save layout")
    print("  DEL  /api/maps/{map_name}/layout    - Reset layout")
    print("  POST /api/maps/{map_name}/topology  - Save topology")
    print("  POST /api/maps/upload               - Upload new map")
    print("  DEL  /api/maps/{map_name}           - Delete map")
    print("  PUT  /api/maps/{map_name}/rename    - Rename map")
    print("  POST /api/maps/{map_name}/copy      - Copy map")
    print("  GET  /api/maps/{map_name}/export    - Export topology JSON")
    print("  POST /api/export/graphml            - Export to GraphML")
    print("  POST /api/export/drawio             - Export to DrawIO")
    print("  GET  /api/diagnostics               - System diagnostics")
    print("=" * 70)
    print("\nWorkspace Structure:")
    print("  maps/")
    print("    lab/")
    print("      topology.json    ← SecureCartography writes here")
    print("      layout.json      ← UI saves positions here")
    print("    production/")
    print("      topology.json")
    print("      layout.json")
    print("=" * 70)

    app.run(debug=True, host='0.0.0.0', port=5000)