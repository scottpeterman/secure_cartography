"""
SCNG Audit - Config and inventory collection from discovery output.

Path: scng/audit/__init__.py

Second-pass collector that reads discovery output and collects:
- Running configurations
- Hardware inventory

Also generates PDF audit reports with:
- Device inventory
- Protocol analysis
- Security posture

Usage:
    from sc2.scng.audit import AuditCollector, audit_discovery, generate_report
    from sc2.scng.creds import CredentialVault

    # Collect configs
    vault = CredentialVault()
    vault.unlock("password")
    collector = AuditCollector(vault)
    result = collector.collect("./network_maps/")

    # Generate report
    generate_report("./network_maps/", "audit_report.pdf")
"""

from .collector import (
    AuditCollector,
    AuditResult,
    DeviceAuditResult,
    AuditCommands,
    AUDIT_COMMANDS,
    audit_discovery,
)

from .report import (
    generate_report,
    AuditDataCollector,
    AuditReportGenerator,
    ConfigAnalyzer,
)

__all__ = [
    # Collector
    "AuditCollector",
    "AuditResult",
    "DeviceAuditResult",
    "AuditCommands",
    "AUDIT_COMMANDS",
    "audit_discovery",
    # Report
    "generate_report",
    "AuditDataCollector",
    "AuditReportGenerator",
    "ConfigAnalyzer",
]