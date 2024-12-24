# Secure Cartography

Secure Cartography is a secure, Python-based network discovery and mapping tool designed for network engineers and IT professionals. It leverages SSH-based device interrogation to automate network discovery, visualize network topologies, and merge network maps across multi-vendor environments.

![Main Application](https://raw.githubusercontent.com/scottpeterman/secure_cartography/refs/heads/main/screenshots/slides.gif)

## Version 0.7.0 Highlights

- **Major Performance Improvements**: 10x faster device discovery and processing
- **Enhanced Visualization**: New interactive Mermaid-based network topology viewer
- **Improved Device Support**: Added support for Aruba/HP ProCurve switches (non-CX)
- **Advanced Logging**: Configurable logging levels with improved output formatting
- **UI Improvements**: 
  - Quick-access buttons for browsing output folders and files
  - Modernized topology merge dialog with interactive preview
  - Enhanced dark/light mode support

## Quick Start Guide

1. **Network Discovery and Mapping**
   ```bash
   python -m secure_cartography.scart
   ```

2. **Topology Merge Tool**
   ```bash
   python -m secure_cartography.merge_dialog
   ```

## Key Features

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
- Configurable exclusion patterns (e.g., `othersite-,sep` to exclude specific sites and IP phones)

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

### Security
- Master password-based encryption system
- Machine-specific keyring integration
- No plaintext passwords stored
- PBKDF2-based key derivation
- Encrypted credential storage

### Map Merging
- Interactive topology preview
- Intelligent topology merging with connection deduplication
- Comprehensive merge logging
- Multiple file support

## Installation

### From PyPI
```bash
pip install secure-cartography
```

### From GitHub
```bash
git clone https://github.com/scottpeterman/secure_cartography.git
cd secure_cartography
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Running the Application
```bash
# Run as installed package
scart
merge-dialog

# Or run as module for additional console output
python -m secure_cartography.scart
python -m secure_cartography.merge_dialog
```

## System Requirements
- Python 3.9+
- PyQt6
- NetworkX
- N2G
- Matplotlib
- Cryptography
- PyYAML
- Paramiko

## System Compatibility

### Tested Environments
- Windows 10 & 11
- Ubuntu 24.04
- Mac OSX (latest as of 12-20-24)
- Python versions 3.9 and 3.12

### Known Issues
- Python 3.13: Compatibility issues with Napalm library

## External Tool Integration

### yEd GraphML (.graphml)
![yEd Example](https://raw.githubusercontent.com/scottpeterman/secure_cartography/refs/heads/main/screenshots/yed1.png)
- Multiple automatic layout algorithms
- Advanced grouping capabilities
- Neighborhood analysis
- High-quality vector export

### draw.io (.drawio)
![draw.io Example](https://raw.githubusercontent.com/scottpeterman/secure_cartography/refs/heads/main/screenshots/drawio.png)
- Collaborative diagram editing
- Web-based access
- Multiple export formats
- Custom stencils and shapes

## Version History

### 0.7.0 (Current)
- 10x performance improvement in device discovery
- Added Aruba/HP ProCurve switch support
- New interactive Mermaid-based topology viewer
- Enhanced logging with configurable levels
- Improved UI with quick-access file management
- Better error handling and recovery

### 0.2.0
- Initial ProCurve support
- Improved device discovery reliability
- Enhanced neighbor discovery
- Added debug logging
- Improved topology mapping
- Better platform detection

## Technology Stack

### Core Technologies
- Python 3.9+
- PyQt6 for GUI
- NetworkX for graph processing
- Matplotlib for visualization
- Cryptography.io for security

### Security Components
- PBKDF2 key derivation
- Fernet encryption
- System keyring integration
- Platform-specific secure storage

### Network Interaction
- Paramiko/SSH2 for device communication
- TextFSM for output parsing
- Custom platform detection
- Enhanced interface normalization

### Data Storage
- JSON for topology data
- YAML for configuration
- SVG for visualizations
- Encrypted credential storage

## Security Architecture

### Credential Protection
1. **Master Password System**
   - PBKDF2-derived key generation
   - Machine-specific salt
   - Secure system keyring integration

2. **Storage Security**
   - Fernet encryption for credentials
   - No plaintext password storage
   - Platform-specific secure storage locations

3. **Runtime Security**
   - Memory-safe credential handling
   - Secure credential cleanup
   - Protected GUI input fields