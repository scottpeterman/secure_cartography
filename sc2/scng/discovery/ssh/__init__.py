"""
SCNG SSH Discovery - SSH-based fallback for neighbor discovery.

Path: scng/discovery/ssh/__init__.py

When SNMP fails or lacks neighbor data, SSH collection provides
fallback using TextFSM templates for multi-vendor parsing.

Uses tfsm_fire from scng.utils when available, with embedded
templates as fallback.

Usage:
    from sc2.scng.discovery.ssh import SSHCollector, collect_neighbors_ssh

    # Using collector class
    collector = SSHCollector(username="admin", password="secret")
    result = collector.collect("192.168.1.1")

    # Using convenience function
    neighbors, errors = collect_neighbors_ssh(
        "192.168.1.1",
        username="admin",
        password="secret",
    )
"""

from .client import SSHClient, SSHClientConfig, filter_ansi_sequences, PAGINATION_DISABLE_SHOTGUN
from .collector import (
    SSHCollector,
    SSHCollectorResult,
    collect_neighbors_ssh,
    detect_vendor_from_output,
    VendorCommands,
    VENDOR_COMMANDS,
)
from .parsers import (
    TextFSMParser,
    ParseResult,
    OutputCleaner,
)

__all__ = [
    # Client
    'SSHClient',
    'SSHClientConfig',
    'filter_ansi_sequences',
    'PAGINATION_DISABLE_SHOTGUN',
    # Collector
    'SSHCollector',
    'SSHCollectorResult',
    'collect_neighbors_ssh',
    'detect_vendor_from_output',
    'VendorCommands',
    'VENDOR_COMMANDS',
    # Parsers
    'TextFSMParser',
    'ParseResult',
    'OutputCleaner',
]