# Secure Cartography

Secure Cartography is a secure, Python-based network discovery and mapping tool designed for network engineers and IT professionals. It leverages SSH-based device interrogation to automate network discovery, visualize network topologies, and merge network maps across multi-vendor environments.

![Main Application](screenshots/scart.png)

**Topology Merge Tool**
   ```bash
   python -m secure_cartography.merge_dialog
   ```

![Map Merge Tool](screenshots/map_merge.png)

**Architecture**
![arch](docs/architecture.png)


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

### Medium to Large diagrams
![Complex Network Map](screenshots/complexmap.png)

### Network Discovery
- Multi-threaded SSH-based device discovery
- Support for multiple vendor platforms (Cisco IOS, NX-OS, Arista EOS)
- Configurable discovery depth and timeout settings
- Real-time discovery progress monitoring
- Device platform auto-detection
- Smart exclusion pattern support (e.g., `othersite-,sep` to exclude specific sites and IP phones)

### Security
- Master password-based encryption system
- Machine-specific keyring integration
- No plaintext passwords stored
- PBKDF2-based key derivation
- Encrypted credential storage

### Visualization
- Dark mode optimized network diagrams
- Multiple layout algorithms:
  - Kamada-Kawai (KK) for general topologies
  - Circular layout for ring networks
  - Multipartite for layered networks
- SVG output for high-quality graphics
- Real-time preview capabilities

### Map Merging
- Intelligent topology merging with preview
- Maintains connection integrity
- Connection de-duplication
- Multiple file support
- Comprehensive merge logging

## Installation

### From GitHub
```bash
# Clone the repository
git clone https://github.com/scottpeterman/secure_cartography.git
cd secure_cartography

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

PyPI package coming soon!

## Core Requirements
- Python 3.9+
- PyQt6
- NetworkX
- Matplotlib
- Cryptography
- PyYAML
- Paramiko

## Supported Export Formats

### yEd GraphML (.graphml)
![yEd Example](screenshots/yed1.png)
- Multiple automatic layout algorithms
- Advanced grouping capabilities
- Neighborhood analysis for large networks
- High-quality vector export

### draw.io (.drawio)
![draw.io Example](screenshots/drawio.png)
- Collaborative diagram editing
- Web-based access
- Multiple export formats
- Custom stencils and shapes

[Technical documentation continues below...]

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

# Appendix A: TFSM_Fire - Intelligent Template Matching

## Overview

TFSM_Fire represents a novel approach to TextFSM template matching that uses an intelligent scoring system and thread-safe database operations to automatically select the best parsing template for network device output.

![tfsm_fire](docs/tfsm_fire.png)
## Key Features

### 1. Intelligent Template Selection
```python
def find_best_template(self, device_output: str, filter_string: Optional[str] = None) -> Tuple[
    Optional[str], Optional[List[Dict]], float]:
```
- Automatically evaluates multiple templates against device output
- Returns the best matching template, parsed output, and confidence score
- Uses sophisticated scoring algorithm to determine template fitness
- Supports optional filtering to narrow template search space

### 2. Thread-Safe Design
```python
class ThreadSafeConnection:
    """Thread-local storage for SQLite connections"""
    def __init__(self, db_path: str, verbose: bool = False):
        self.db_path = db_path
        self.verbose = verbose
        self._local = threading.local()
```
- Implements thread-local storage for database connections
- Ensures safe concurrent access to template database
- Manages connection lifecycle automatically
- Supports high-performance parallel template matching

### 3. Scoring Algorithm
The template scoring system evaluates matches based on multiple factors:
- Number of successfully parsed records
- Special handling for version command output
- Intelligent weighting based on command type
- Score normalization for consistent evaluation

### 4. Template Filtering
```python
def get_filtered_templates(self, connection: sqlite3.Connection, filter_string: Optional[str] = None):
    """Get filtered templates from database using provided connection."""
    if filter_string:
        filter_terms = filter_string.replace('-', '_').split('_')
        query = "SELECT * FROM templates WHERE 1=1"
        params = []
        for term in filter_terms:
            if term and len(term) > 2:
                query += " AND cli_command LIKE ?"
                params.append(f"%{term}%")
```
- Smart filtering of template database
- Handles hyphenated command names
- Minimum term length requirements
- SQL injection prevention

