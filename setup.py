#!/usr/bin/env python3
"""
Secure Cartography v2 - Setup Script
SSH & SNMP-Based Network Discovery and Topology Mapping
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README for long description
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

# Read requirements.txt
def parse_requirements(filename):
    """Parse requirements.txt, ignoring comments and empty lines."""
    requirements = []
    req_file = this_directory / filename
    if req_file.exists():
        for line in req_file.read_text().splitlines():
            line = line.strip()
            # Skip empty lines, comments, and editable installs
            if line and not line.startswith('#') and not line.startswith('-e'):
                # Remove any inline comments
                if '#' in line:
                    line = line.split('#')[0].strip()
                requirements.append(line)
    return requirements

setup(
    name="secure-cartography",
    version="2.0.5",
    author="Scott Peterman",
    author_email="scottpeterman@gmail.com",
    description="SSH & SNMP-Based Network Discovery and Topology Mapping",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/scottpeterman/secure_cartography",
    license="GPL-3.0",

    # Package discovery
    packages=find_packages(exclude=["tests", "tests.*", "docs", "screenshots"]),

    # Include non-Python files
    include_package_data=True,
    package_data={
        "sc2": [
            "**/*.html",
            "**/*.css",
            "**/*.js",
            "**/*.png",
            "**/*.jpg",
            "**/*.jpeg",
            "**/*.svg",
            "**/*.ico",
            "**/*.gif",
            "**/*.json",
        ],
        "sc2.scng.utils": [
            "tfsm_templates.db",
        ],
        "sc2.ui": [
            "*.html",
            "widgets/*.html",
        ],
    },

    # Python version requirement
    python_requires=">=3.10",

    # Dependencies from requirements.txt
    install_requires=parse_requirements("requirements.txt"),

    # Optional dependencies
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-asyncio>=0.21",
            "black>=23.0",
            "ruff>=0.1",
        ],
    },

    # Entry points
    entry_points={
        "console_scripts": [
            "sc2=sc2.ui.__main__:main",
            "sc2-creds=sc2.scng.creds.cli:main",
            "sc2-discover=sc2.scng.discovery.cli:main",
        ],
        "gui_scripts": [
            "secure-cartography=sc2.ui.__main__:main",
        ],
    },

    # Classifiers
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: X11 Applications :: Qt",
        "Environment :: Win32 (MS Windows)",
        "Environment :: MacOS X",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Information Technology",
        "Intended Audience :: Telecommunications Industry",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: System :: Networking",
        "Topic :: System :: Networking :: Monitoring",
        "Topic :: System :: Systems Administration",
    ],

    # Keywords for PyPI
    keywords=[
        "network",
        "discovery",
        "topology",
        "snmp",
        "ssh",
        "cdp",
        "lldp",
        "cisco",
        "arista",
        "juniper",
        "network-automation",
        "network-mapping",
    ],

    # Project URLs
    project_urls={
        "Bug Reports": "https://github.com/scottpeterman/secure_cartography/issues",
        "Source": "https://github.com/scottpeterman/secure_cartography",
        "Documentation": "https://github.com/scottpeterman/secure_cartography#readme",
    },
)