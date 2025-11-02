# Option A: Quick Plugin (3-5 Days) - Detailed Technical Specification

## Overview

Convert vmaps from standalone Flask application to NetBox Django plugin with **zero functional changes**. The goal is to prove the concept works within NetBox's ecosystem while maintaining 100% feature parity with the current Flask version.

**Timeline: 3-5 days**
**Outcome: Production-ready NetBox plugin that does exactly what vmaps does today**

---

## Day 1: Plugin Structure & Boilerplate (4-6 hours)

### 1.1 Create Plugin Directory Structure

```
netbox-vmaps/
├── netbox_vmaps/                    # Main plugin package
│   ├── __init__.py                  # Plugin metadata
│   ├── navigation.py                # NetBox sidebar integration
│   ├── urls.py                      # URL routing
│   ├── views.py                     # Django views (converted from Flask)
│   ├── api/                         # API endpoints
│   │   ├── __init__.py
│   │   ├── urls.py                  # API URL routing
│   │   └── views.py                 # API view handlers
│   ├── helpers.py                   # All your existing helper functions
│   ├── templates/
│   │   └── netbox_vmaps/
│   │       └── topology.html        # Your index.html (minimal changes)
│   └── static/
│       └── netbox_vmaps/
│           ├── css/                 # Your existing CSS files
│           ├── js/                  # Your existing JS files (no changes)
│           └── icons_lib/           # Your 586 icons
├── pyproject.toml                   # Plugin packaging
├── README.md
└── LICENSE
```

### 1.2 Plugin Metadata (`__init__.py`)

```python
"""
NetBox vMaps Plugin
Network topology visualization and editing for NetBox
"""

__version__ = '1.0.0'

from netbox.plugins import PluginConfig

class VMapsConfig(PluginConfig):
    name = 'netbox_vmaps'
    verbose_name = 'Network Topology Visualizer'
    description = 'Dynamic network topology discovery, visualization, and editing'
    version = __version__
    author = 'Scott Peterman'
    author_email = 'your@email.com'
    base_url = 'vmaps'
    required_settings = []
    default_settings = {
        'maps_workspace': 'maps',  # Where to store topology files
        'icons_dir': 'static/netbox_vmaps/icons_lib',
    }
    min_version = '4.0.0'  # NetBox 4.0+
    max_version = '4.9.99'

config = VMapsConfig
```

### 1.3 Navigation Integration (`navigation.py`)

```python
"""
NetBox sidebar navigation integration
"""

from netbox.plugins import PluginMenuButton, PluginMenuItem
from netbox.plugins.utils import get_plugin_config

menu_items = (
    PluginMenuItem(
        link='plugins:netbox_vmaps:topology',
        link_text='Network Topology',
        permissions=['netbox_vmaps.view_topology'],
        buttons=(
            PluginMenuButton(
                link='plugins:netbox_vmaps:topology',
                title='View Topology',
                icon_class='mdi mdi-graph',
                color='primary'
            ),
        )
    ),
)
```

### 1.4 URL Routing (`urls.py`)

```python
"""
Main URL routing for vmaps plugin
"""

from django.urls import path, include
from . import views

app_name = 'netbox_vmaps'

urlpatterns = [
    # Main topology view
    path('', views.TopologyView.as_view(), name='topology'),
    
    # API endpoints
    path('api/', include('netbox_vmaps.api.urls')),
]
```

---

## Day 2: API Conversion (Flask → Django) (6-8 hours)

### 2.1 Helper Functions Module (`helpers.py`)

**COPY YOUR EXISTING FUNCTIONS UNCHANGED:**

```python
"""
Helper functions for vmaps plugin
These are IDENTICAL to your Flask app.py helper functions
"""

import json
import os
from datetime import datetime
from pathlib import Path
import re

def ensure_workspace(workspace_path):
    """Ensure maps workspace exists"""
    os.makedirs(workspace_path, exist_ok=True)

def validate_map_name(map_name):
    """
    Validate map name for security
    UNCHANGED from Flask version
    """
    if not map_name:
        return False
    if '..' in map_name or '/' in map_name or '\\' in map_name:
        return False
    if not re.match(r'^[a-zA-Z0-9_-]+$', map_name):
        return False
    return True

def load_topology(map_name, workspace_path):
    """
    Load topology JSON for a map
    UNCHANGED from Flask version
    """
    if not validate_map_name(map_name):
        raise ValueError(f"Invalid map name: {map_name}")
    
    topology_file = os.path.join(workspace_path, map_name, 'topology.json')
    
    with open(topology_file, 'r') as f:
        return json.load(f)

def load_layout(map_name, workspace_path):
    """
    Load saved layout for a map
    UNCHANGED from Flask version
    """
    if not validate_map_name(map_name):
        raise ValueError(f"Invalid map name: {map_name}")
    
    layout_file = os.path.join(workspace_path, map_name, 'layout.json')
    
    if os.path.exists(layout_file):
        with open(layout_file, 'r') as f:
            return json.load(f)
    return None

def save_layout(map_name, layout_data, workspace_path):
    """
    Save layout for a map
    UNCHANGED from Flask version
    """
    if not validate_map_name(map_name):
        raise ValueError(f"Invalid map name: {map_name}")
    
    map_dir = os.path.join(workspace_path, map_name)
    os.makedirs(map_dir, exist_ok=True)
    
    layout_file = os.path.join(map_dir, 'layout.json')
    layout_data['map_name'] = map_name
    layout_data['server_timestamp'] = datetime.now().isoformat()
    
    with open(layout_file, 'w') as f:
        json.dump(layout_data, f, indent=2)
    return True

def list_available_maps(workspace_path):
    """
    List all available maps in workspace
    UNCHANGED from Flask version
    """
    ensure_workspace(workspace_path)
    maps = []
    
    for item in os.listdir(workspace_path):
        map_path = os.path.join(workspace_path, item)
        if os.path.isdir(map_path):
            topology_file = os.path.join(map_path, 'topology.json')
            if os.path.exists(topology_file):
                maps.append({
                    'name': item,
                    'has_layout': os.path.exists(os.path.join(map_path, 'layout.json')),
                    'topology_size': os.path.getsize(topology_file),
                    'modified': datetime.fromtimestamp(os.path.getmtime(topology_file)).isoformat()
                })
    
    return sorted(maps, key=lambda x: x['name'])

def load_icon_map(icon_map_path):
    """
    Load platform icon mapping configuration
    UNCHANGED from Flask version
    """
    try:
        with open(icon_map_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            'defaults': {'default_unknown': 'cloud_(4).jpg'},
            'platform_patterns': {},
            'fallback_patterns': {}
        }

# Add all your other helper functions here...
# convert_to_cytoscape(), get_icon_for_platform(), etc.
```

### 2.2 API Views (`api/views.py`)

**Flask routes → Django REST views (mechanical conversion):**

```python
"""
API views for vmaps plugin
Converted from Flask routes with minimal changes
"""

from django.http import JsonResponse, FileResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from netbox.plugins import get_plugin_config
import json
import os
import tempfile

from ..helpers import (
    list_available_maps,
    load_topology,
    load_layout,
    save_layout,
    validate_map_name,
    load_icon_map
)

def get_workspace_path():
    """Get maps workspace path from plugin config"""
    return get_plugin_config('netbox_vmaps', 'maps_workspace', 'maps')

@require_http_methods(["GET"])
def api_list_maps(request):
    """
    GET /api/maps/
    List all available maps
    
    Flask equivalent: @app.route('/api/maps')
    """
    try:
        workspace = get_workspace_path()
        maps = list_available_maps(workspace)
        return JsonResponse({
            'success': True,
            'maps': maps
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@require_http_methods(["GET"])
def api_get_map(request, map_name):
    """
    GET /api/maps/<map_name>/
    Load a specific map (topology + layout)
    
    Flask equivalent: @app.route('/api/maps/<map_name>')
    """
    try:
        if not validate_map_name(map_name):
            return JsonResponse({
                'success': False,
                'error': 'Invalid map name'
            }, status=400)
        
        workspace = get_workspace_path()
        
        topology = load_topology(map_name, workspace)
        layout = load_layout(map_name, workspace)
        
        return JsonResponse({
            'success': True,
            'data': topology,
            'saved_layout': layout
        })
        
    except FileNotFoundError:
        return JsonResponse({
            'success': False,
            'error': f'Map not found: {map_name}'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@csrf_exempt  # For API POST requests
@require_http_methods(["POST"])
def api_save_layout(request, map_name):
    """
    POST /api/maps/<map_name>/layout/
    Save layout for a map
    
    Flask equivalent: @app.route('/api/maps/<map_name>/layout', methods=['POST'])
    """
    try:
        if not validate_map_name(map_name):
            return JsonResponse({
                'success': False,
                'error': 'Invalid map name'
            }, status=400)
        
        layout_data = json.loads(request.body)
        workspace = get_workspace_path()
        
        result = save_layout(map_name, layout_data, workspace)
        
        if result:
            return JsonResponse({
                'success': True,
                'message': 'Layout saved successfully'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Failed to save layout'
            }, status=500)
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def api_save_topology(request, map_name):
    """
    POST /api/maps/<map_name>/topology/
    Save topology for a map
    """
    try:
        if not validate_map_name(map_name):
            return JsonResponse({
                'success': False,
                'error': 'Invalid map name'
            }, status=400)
        
        topology_data = json.loads(request.body)
        workspace = get_workspace_path()
        
        map_dir = os.path.join(workspace, map_name)
        os.makedirs(map_dir, exist_ok=True)
        
        topology_file = os.path.join(map_dir, 'topology.json')
        
        with open(topology_file, 'w') as f:
            json.dump(topology_data, f, indent=2)
        
        return JsonResponse({
            'success': True,
            'message': 'Topology saved successfully'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@require_http_methods(["GET"])
def api_platform_map(request):
    """
    GET /api/platform-map
    Serve platform icon mapping configuration
    """
    try:
        # Look for platform map in plugin static directory
        platform_map_file = os.path.join(
            settings.BASE_DIR,
            'netbox_vmaps',
            'data',
            'platform_icon_map.json'
        )
        
        icon_map = load_icon_map(platform_map_file)
        return JsonResponse(icon_map)
        
    except Exception as e:
        # Return minimal fallback
        return JsonResponse({
            'base_path': 'static/netbox_vmaps/icons_lib',
            'platform_patterns': {
                'Cisco IOS': 'router.jpg',
                'Arista EOS': 'Nexus_5000.jpg',
            },
            'defaults': {
                'default_unknown': 'generic_processor.jpg'
            }
        })

@csrf_exempt
@require_http_methods(["POST"])
def api_upload_map(request):
    """
    POST /api/maps/upload
    Upload a new topology file
    """
    try:
        if 'file' not in request.FILES:
            return JsonResponse({
                'success': False,
                'error': 'No file provided'
            }, status=400)
        
        file = request.FILES['file']
        map_name = request.POST.get('map_name', '')
        
        if not map_name:
            # Generate name from filename
            map_name = file.name.replace('.json', '').replace(/[^a-zA-Z0-9_-]/g, '_')
        
        if not validate_map_name(map_name):
            return JsonResponse({
                'success': False,
                'error': 'Invalid map name'
            }, status=400)
        
        workspace = get_workspace_path()
        map_dir = os.path.join(workspace, map_name)
        os.makedirs(map_dir, exist_ok=True)
        
        topology_file = os.path.join(map_dir, 'topology.json')
        
        # Read and validate JSON
        topology_data = json.loads(file.read())
        
        with open(topology_file, 'w') as f:
            json.dump(topology_data, f, indent=2)
        
        device_count = len(topology_data)
        
        return JsonResponse({
            'success': True,
            'map_name': map_name,
            'device_count': device_count
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON file'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

# Add more API views following the same pattern:
# - api_delete_map()
# - api_rename_map()
# - api_copy_map()
# - api_export_map()
# - api_reset_layout()
# - api_export_graphml()
# - api_export_drawio()
```

### 2.3 API URL Routing (`api/urls.py`)

```python
"""
API URL routing for vmaps
"""

from django.urls import path
from . import views

app_name = 'netbox_vmaps_api'

urlpatterns = [
    # Map operations
    path('maps/', views.api_list_maps, name='list-maps'),
    path('maps/<str:map_name>/', views.api_get_map, name='get-map'),
    path('maps/<str:map_name>/layout/', views.api_save_layout, name='save-layout'),
    path('maps/<str:map_name>/topology/', views.api_save_topology, name='save-topology'),
    path('maps/upload/', views.api_upload_map, name='upload-map'),
    
    # Platform configuration
    path('platform-map/', views.api_platform_map, name='platform-map'),
    
    # Export operations  
    path('export/graphml/', views.api_export_graphml, name='export-graphml'),
    path('export/drawio/', views.api_export_drawio, name='export-drawio'),
]
```

---

## Day 3: Frontend Integration (4-6 hours)

### 3.1 Template Conversion (`templates/netbox_vmaps/topology.html`)

**Take your `index.html` and make minimal changes:**

```django
{% extends 'base/layout.html' %}
{% load static %}
{% load plugins %}

{% block title %}Network Topology Visualizer{% endblock %}

{% block content %}
<!-- Your existing HTML structure, but with Django static tags -->

<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SecureCartography Network Topology</title>

    <!-- Cytoscape.js -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.26.0/cytoscape.min.js"></script>

    <!-- Lucide Icons -->
    <script src="https://unpkg.com/lucide@latest"></script>

    <!-- Theme CSS -->
    <link rel="stylesheet" href="{% static 'netbox_vmaps/themes.css' %}">

    <!-- Application CSS -->
    <link rel="stylesheet" href="{% static 'netbox_vmaps/css/app.css' %}">
    <link rel="stylesheet" href="{% static 'netbox_vmaps/css/sidebar.css' %}">
</head>
<body>
    <!-- Your existing HTML - UNCHANGED -->
    <div class="top-bar">
        <!-- ... -->
    </div>

    <div class="sidebar" id="sidebar">
        <!-- ... -->
    </div>

    <div id="cy-container"></div>

    <!-- JavaScript Modules - Only paths change -->
    <script src="{% static 'netbox_vmaps/js/api.js' %}"></script>
    <script src="{% static 'netbox_vmaps/js/ui.js' %}"></script>
    <script src="{% static 'netbox_vmaps/js/theme.js' %}"></script>
    <script src="{% static 'netbox_vmaps/js/platform_loader.js' %}"></script>
    <script src="{% static 'netbox_vmaps/js/platform_selector.js' %}"></script>
    <script src="{% static 'netbox_vmaps/js/export-graphml.js' %}"></script>
    <script src="{% static 'netbox_vmaps/js/export-enhanced.js' %}"></script>
    <script src="{% static 'netbox_vmaps/js/export-drawio.js' %}"></script>
    <script src="{% static 'netbox_vmaps/js/graph.js' %}"></script>
    <script src="{% static 'netbox_vmaps/js/layout.js' %}"></script>
    <script src="{% static 'netbox_vmaps/js/file-manager.js' %}"></script>
    <script src="{% static 'netbox_vmaps/js/sidebar.js' %}"></script>
    <script src="{% static 'netbox_vmaps/js/app.js' %}"></script>

    <script>
        document.addEventListener('DOMContentLoaded', () => {
            lucide.createIcons();
        });
    </script>
</body>
</html>

{% endblock %}
```

### 3.2 Main View (`views.py`)

```python
"""
Main views for vmaps plugin
"""

from django.shortcuts import render
from django.views.generic import View
from django.contrib.auth.mixins import PermissionRequiredMixin

class TopologyView(PermissionRequiredMixin, View):
    """
    Main topology visualization view
    """
    permission_required = 'netbox_vmaps.view_topology'
    template_name = 'netbox_vmaps/topology.html'
    
    def get(self, request):
        """Render the topology visualizer"""
        return render(request, self.template_name)
```

### 3.3 JavaScript - NO CHANGES NEEDED

**Your JavaScript files work as-is!** The API calls use relative paths that work in both Flask and Django:

```javascript
// api.js - Works unchanged in Django
async listMaps() {
    const response = await fetch('/api/maps');  // Resolves correctly
    return await response.json();
}
```

The only difference is the URL will be `/plugins/vmaps/api/maps/` in NetBox, but Django's URL routing handles that automatically.

---

## Day 4-5: Testing & Refinement (8-10 hours)

### 4.1 Installation Testing

```bash
# Install plugin in NetBox
cd /opt/netbox
source venv/bin/activate
pip install /path/to/netbox-vmaps/

# Add to NetBox configuration
echo "netbox_vmaps" >> /opt/netbox/netbox/configuration.py PLUGINS

# Collect static files
python manage.py collectstatic --no-input

# Create workspace directory
mkdir -p /opt/netbox/netbox/media/netbox_vmaps/maps

# Restart NetBox
sudo systemctl restart netbox
```

### 4.2 Functional Testing Checklist

- [ ] Plugin appears in NetBox sidebar navigation
- [ ] Topology page loads without errors
- [ ] Can upload new topology JSON file
- [ ] Can select and load existing maps
- [ ] Graph renders with Cytoscape
- [ ] Can create new devices
- [ ] Can create new connections
- [ ] Can edit device properties
- [ ] Can edit connection properties
- [ ] Can delete devices and connections
- [ ] Layout algorithms work (breadth-first, COSE, etc.)
- [ ] Can save layout positions
- [ ] Layout positions persist on reload
- [ ] Can export to GraphML with icons
- [ ] Can export to DrawIO with icons
- [ ] Can export topology JSON
- [ ] File manager modal works
- [ ] Can rename maps
- [ ] Can delete maps
- [ ] Can copy/duplicate maps
- [ ] Themes work (Light, Dark, Cyber)
- [ ] Platform selector shows 586 icons
- [ ] Search in platform selector works

### 4.3 Bug Fixes & Polish

**Common issues to address:**

1. **Static file paths** - Ensure icons load correctly
2. **CSRF tokens** - Django requires CSRF tokens for POST requests
3. **Permissions** - Configure NetBox permissions properly
4. **URL routing** - Test all API endpoints work
5. **File storage** - Ensure maps directory is writable

### 4.4 Documentation

```markdown
# NetBox vMaps Plugin

## Installation

```bash
pip install netbox-vmaps
```

Add to `configuration.py`:

```python
PLUGINS = [
    'netbox_vmaps',
]

PLUGINS_CONFIG = {
    'netbox_vmaps': {
        'maps_workspace': '/opt/netbox/netbox/media/netbox_vmaps/maps',
    }
}
```

Run:

```bash
python manage.py collectstatic --no-input
sudo systemctl restart netbox
```

## Usage

1. Navigate to **Plugins → Network Topology** in NetBox sidebar
2. Click **Upload** to import a topology JSON file
3. Select a map from the dropdown to visualize
4. Edit topology using the sidebar tools
5. Save layout to persist device positions

## Features

- Interactive network topology visualization
- Full CRUD operations (Create, Read, Update, Delete devices/connections)
- 586+ vendor-specific device icons
- Multiple layout algorithms
- Export to GraphML, DrawIO, PNG
- Layout position persistence
- Three UI themes (Light, Dark, Cyber)
```

---

## Packaging (`pyproject.toml`)

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "netbox-vmaps"
version = "1.0.0"
description = "Network topology visualization and editing for NetBox"
readme = "README.md"
requires-python = ">=3.8"
license = {text = "MIT"}
authors = [
    {name = "Scott Peterman", email = "your@email.com"}
]
keywords = ["netbox", "plugin", "topology", "visualization", "network"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Framework :: Django",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
]

dependencies = [
    "netbox>=4.0.0",
]

[project.urls]
Homepage = "https://github.com/scottpeterman/netbox-vmaps"
Documentation = "https://github.com/scottpeterman/netbox-vmaps/blob/main/README.md"
Repository = "https://github.com/scottpeterman/netbox-vmaps"

[tool.setuptools.packages.find]
where = ["."]
include = ["netbox_vmaps*"]

[tool.setuptools.package-data]
netbox_vmaps = [
    "templates/**/*.html",
    "static/**/*",
]
```

---

## What You Get After 3-5 Days

✅ **Fully functional NetBox plugin** that does everything vmaps does today
✅ **Native NetBox integration** - appears in sidebar, uses NetBox auth
✅ **Zero feature loss** - all vmaps functionality preserved
✅ **Professional packaging** - installable via pip
✅ **Production ready** - tested and documented

## What You DON'T Get (Yet)

❌ NetBox data integration (import from NetBox DCIM models)
❌ SecureCartography discovery integration  
❌ Write-back to NetBox (export topology → NetBox devices/cables)
❌ NetBox permissions integration (currently basic auth)
❌ Database storage for layouts (currently file-based)

**But that's Option B territory. Option A proves the concept works.**

---

## Risk Assessment

**Low Risk:**
- Conversion is mechanical (Flask → Django patterns are well-known)
- Your code is already well-structured
- JavaScript needs zero changes
- Helper functions copy-paste unchanged

**Medium Risk:**
- NetBox plugin API might have quirks we discover during testing
- Static file serving might need troubleshooting
- CSRF token handling for POST requests

**Mitigation:**
- Start with absolute minimum (single view, single API endpoint)
- Test incrementally
- NetBox plugin documentation is comprehensive
- You've already built one NetBox plugin (you know the patterns)

---

## Success Criteria

**Done when:**
1. Can install plugin in NetBox via pip
2. Plugin appears in NetBox navigation
3. Can open topology visualizer page
4. Can perform all operations that work in Flask version
5. No JavaScript console errors
6. All 586 icons load correctly
7. Can save/load maps with layouts
8. Documentation explains installation and usage

---

## Next Steps After Option A

Once Option A is working, you have a **negotiating position with NetBox Labs**:

"I've built a NetBox plugin that adds network topology visualization and editing. It's production-ready and installable via pip. Would you be interested in discussing partnership opportunities for adding discovery integration and making this part of your ecosystem?"

That conversation happens from a position of strength - you have working code, not just ideas.

---

**Want me to start writing the actual conversion code?** I can generate:
1. The complete plugin boilerplate
2. Flask → Django conversion script
3. Step-by-step conversion commands
4. Testing checklist with commands

This is totally doable in 3-5 days. The architecture you built makes this easy.