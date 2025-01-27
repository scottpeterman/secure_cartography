# Secure Cartography & Surveyor Suite

## Overview
The **Secure Cartography & Surveyor Suite** is a comprehensive, Python-based network discovery, mapping, and management toolkit. Designed for network engineers, IT administrators, and SMBs, it provides robust features for automated device interrogation, network topology visualization, and configuration management, all while maintaining strict security standards.

![arch](screenshots/poc/slides1.gif)

Key features include:
- **Automated Discovery:** SSH-based interrogation with platform auto-detection
- **Network Mapping:** JSON-based storage with support for CDP/LLDP protocols
- **Device Inventory & Configuration:** Inventory parsing and configuration backup for multi-vendor environments
- **Extensive GUI Support:** Modern PyQt6-based interface with detailed device dialogs and search functionality
- **Advanced Topology Management:** Interactive merging and enhancement tools with visual previews

---

## Version Highlights

### Version 0.8.3 - 0.9.2 Highlights
- **Major Performance Improvements:** 10x faster device discovery and processing
- **Enhanced Visualization:** New interactive Mermaid-based network topology viewer
- **Improved Device Support:** Added support for Aruba/HP ProCurve switches (non-CX)
- **Advanced Logging:** Configurable logging levels with improved output formatting
- **UI Improvements:**
  - Quick-access buttons for browsing output folders and files
  - Modernized topology merge dialog with interactive preview
  - Enhanced dark/light mode support
  - New node editor interface with platform auto-completion
  - Comprehensive icon mapping system

---


## Features

### Network Discovery
- Multi-threaded SSH-based device discovery with optimized queue management
- Support for multiple vendor platforms:
  - Cisco IOS
  - Cisco NX-OS
  - Arista EOS
  - Aruba/HP ProCurve (non-CX)
- Improved device tracking and neighbor discovery
- Real-time progress monitoring with enhanced logging
- Smart platform detection and validation
- Configurable exclusion patterns

### Visualization
- Interactive topology viewer with Mermaid diagrams
- Dark/Light mode theme support
- Multiple export formats:
  - SVG for high-quality graphics
  - GraphML for yEd integration
  - Draw.io compatible format
- Multiple layout algorithms:
  - Kamada-Kawai (KK) for general topologies
  - Circular layout for ring networks
  - Multipartite for layered networks
  - Grid layout for structured networks
  - Tree layout for hierarchical networks
  - Balloon layout for radial hierarchies

### Topology Enhancement
- Interactive node editing with platform auto-completion
- Bulk peer node updates
- Customizable icon mappings for different export formats
- Visual preview of topology changes
- Support for device-specific icons and shapes
- Pattern-based platform mapping

### Map Merging
- Interactive topology preview with SVG visualization
- Intelligent topology merging with connection deduplication
- Comprehensive merge logging
- Multiple file support
- Dark mode interface
- Real-time merge preview
- Automatic output filename suggestions

### Security
- Master password-based encryption system
- Machine-specific keyring integration
- PBKDF2-based key derivation
- Encrypted credential storage

### Device Inventory
- Parses and normalizes inventory using TextFSM templates
- Vendor-specific command mappings for Arista, Cisco IOS, and NX-OS
- Multiprocessing support for large-scale operations

### Configuration Management
- Collects and stores running configurations
- SQLite database integration for secure storage
- Handles privilege escalation (e.g., `enable` mode for Cisco)

### GUI
- PyQt6-based interface
- Devices tab with column filtering and global search
- Device Detail Dialog:
  - Overview, Interfaces, Inventory, and MAC Address tabs
  - Real-time theme switching (dark/light modes)
- Node Editor Interface:
  - Double-click editing functionality
  - Platform auto-completion
  - Bulk peer updates
- Icon Configuration:
  - Separate Draw.io and GraphML mappings
  - Visual icon/shape selection
  - Pattern matching configuration

## Installation

### From PyPI
```bash
pip install secure-cartography
```

### From GitHub
```bash
git clone -b v2 https://github.com/scottpeterman/secure_cartography.git
cd secure_cartography
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Running the Application
```bash
# Run as installed package
pip install not yet available !

# Or run as as an application for additional console output
python main_ui.py
```

---

## System Requirements
- Python 3.9+
- PyQt6
- NetworkX
- N2G
- Matplotlib
- Cryptography
- PyYAML
- Paramiko

### System Compatibility

#### Tested Environments
- Windows 10 & 11
- Ubuntu 24.04
- Mac OSX (latest as of 12-20-24)
- Python versions 3.9 and 3.12

#### Known Issues
- Python 3.13: Compatibility issues with Napalm library

---

## External Tool Integration

### yEd GraphML (.graphml)
![yEd Example](https://raw.githubusercontent.com/scottpeterman/secure_cartography/refs/heads/v2/screenshots/poc/graphml.png)
- Multiple automatic layout algorithms
- Advanced grouping capabilities
- Neighborhood analysis
- High-quality vector export

### draw.io (.drawio)
![draw.io Example](https://raw.githubusercontent.com/scottpeterman/secure_cartography/refs/heads/v2/screenshots/poc/drawio.png)
- Collaborative diagram editing
- Web-based access
- Multiple export formats
- Custom stencils and shapes

---

## Appendix A: CLI Usage

Secure Cartography includes a CLI tool for automation and scripting. The tool can be run as either an installed package or module:

```bash
# Run as installed package
sc --help

# Run as module
python -m secure_cartography.sc --help
```

### Configuration Options

#### YAML Configuration
Create a YAML file with your settings:
```yaml
seed_ip: 172.16.101.1
max_devices: 500
output_dir: "./cli/home"
#username: admin   --- can be here, but its clear text! Please use the environment variable option
#password: pw
verbose: true
map_name: home_network
layout: "rt"  # Optional, defaults to kk
domain: ''    # Optional
exclude: ''   # Optional
timeout: 60   # Optional
```

#### Enhancing Maps
### Maps with ICONS
![Enhance maps Example](https://raw.githubusercontent.com/scottpeterman/secure_cartography/refs/heads/v2/screenshots/poc/enhance.png)
Maps by default are text and boxes and lines. If you want a more traditional network diagram look, choose the "Enhance" button after creating your map, select the "map_name.json" file, hit export, and it will generate new .graphml and .drawio files with icons.


#### Environment Variables
Set credentials using environment variables:
- `SC_USERNAME`: Primary device username
- `SC_PASSWORD`: Primary device password
- `SC_ALT_USERNAME`: Alternate device username (optional)
- `SC_ALT_PASSWORD`: Alternate device password (optional)

```bash
# Windows
set SC_USERNAME=admin
set SC_PASSWORD=mypass

# Linux/Mac
export SC_USERNAME=admin
export SC_PASSWORD=mypass
```

#### CLI Arguments
```bash
sc --yaml config.yaml --seed-ip 192.168.1.1 --verbose
```

Full argument list:
- `--yaml`: Path to YAML config file
- `--seed-ip`: Starting IP address
- `--username`: Device username
- `--password`: Device password
- `--alt-username`: Alternate username
- `--alt-password`: Alternate password
- `--domain`: Domain name
- `--exclude`: Comma-separated exclude patterns
- `--output-dir`: Output directory path
- `--timeout`: Connection timeout (seconds)
- `--max-devices`: Maximum devices to discover
- `--map-name`: Output map name
- `--layout`: Graph layout algorithm
- `--verbose`: Enable debug logging

### Example Usage

Basic discovery with YAML config:
```bash
sc --yaml network_config.yaml --verbose
```

Full CLI configuration:
```bash
sc --seed-ip 192.168.1.1 --username admin --password secret \
   --output-dir ./maps --max-devices 50 --timeout 60 \
   --map-name office_network --layout kk --verbose
```

Using environment variables:
```bash
export SC_USERNAME=admin
export SC_PASSWORD=secret
sc --yaml config.yaml
```

---

## Appendix B: Surveyor GUI Features

Surveyor extends the capabilities of Secure Cartography with an intuitive GUI for advanced network management tasks:

### Key Features

- **Job Management:**
  - Define, edit, and schedule jobs for tasks like device fingerprinting, configuration backup, SNMP collection, and more.
  - Visualize job statuses in real-time with logs and last run details.

- **Interactive Interface:**
  - Dark/light mode support.
  - Detailed job configuration dialogs with support for required and optional arguments.

- **Live Log Monitoring:**
  - View real-time logs during job execution.

- **Screenshots**

#### Home Dashboard
![home Dashboard](https://raw.githubusercontent.com/scottpeterman/secure_cartography/refs/heads/v2/screenshots/poc/home.png)

#### Jobs View
![Job Configuration](https://raw.githubusercontent.com/scottpeterman/secure_cartography/refs/heads/v2/screenshots/poc/jobs.png)

#### Data Exports
![Tables](https://raw.githubusercontent.com/scottpeterman/secure_cartography/refs/heads/v2/screenshots/poc/db.png)

---

## Licensing
This project is licensed under the GNU General Public License v3.0 (GPLv3).

---

## Contributions
Contributions are welcome! Please submit pull requests to the main repository or reach out via the issues page.

---
