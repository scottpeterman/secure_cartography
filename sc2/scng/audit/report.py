"""
SCNG Audit Report Generator - PDF report from audit output.

Path: scng/audit/report.py

Reads audit folder (device.json, config.txt, inventory.txt per device)
and generates a professional PDF audit report.

Features:
- Executive summary with device/vendor breakdown
- Device inventory table
- Protocol analysis (routing, security, services)
- Config-based feature detection
"""

import json
import re
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any, Set
from datetime import datetime
from collections import Counter

logger = logging.getLogger(__name__)


# =============================================================================
# Config Pattern Matching
# =============================================================================

# Patterns to detect protocols and features in configs
CONFIG_PATTERNS = {
    "routing": {
        "BGP": [
            r"router bgp \d+",
            r"neighbor .* remote-as \d+",
        ],
        "OSPF": [
            r"router ospf \d+",
            r"network .* area \d+",
        ],
        "EIGRP": [
            r"router eigrp \d+",
        ],
        "IS-IS": [
            r"router isis",
            r"net \d+\.\d+",
        ],
        "Static": [
            r"ip route \d+\.\d+\.\d+\.\d+",
        ],
        "RIP": [
            r"router rip",
        ],
    },
    "security": {
        "SNMPv2": [
            r"snmp-server community \S+",
        ],
        "SNMPv3": [
            r"snmp-server user \S+",
            r"snmp-server group \S+",
        ],
        "AAA": [
            r"aaa authentication",
            r"aaa authorization",
            r"aaa accounting",
        ],
        "TACACS+": [
            r"tacacs-server host",
            r"tacacs server \S+",
        ],
        "RADIUS": [
            r"radius-server host",
            r"radius server \S+",
        ],
        "ACLs": [
            r"ip access-list (standard|extended)",
            r"access-list \d+",
        ],
    },
    "services": {
        "NTP": [
            r"ntp server \d+\.\d+\.\d+\.\d+",
        ],
        "Syslog": [
            r"logging host \d+\.\d+\.\d+\.\d+",
            r"logging \d+\.\d+\.\d+\.\d+",
        ],
        "SSHv2": [
            r"ip ssh version 2",
        ],
        "SNMP": [
            r"snmp-server",
        ],
        "HTTP/S": [
            r"ip http server",
            r"ip http secure-server",
        ],
    },
    "switching": {
        "VLANs": [
            r"vlan \d+",
        ],
        "STP": [
            r"spanning-tree mode",
        ],
        "Port-Channel": [
            r"interface [Pp]ort-channel\d+",
        ],
        "VPC/MLAG": [
            r"vpc domain",
            r"mlag configuration",
        ],
    },
}

# Juniper-specific patterns
JUNIPER_PATTERNS = {
    "routing": {
        "BGP": [r"protocols bgp", r"group .* neighbor"],
        "OSPF": [r"protocols ospf", r"area \d+\.\d+"],
        "IS-IS": [r"protocols isis"],
        "Static": [r"routing-options static route"],
    },
    "security": {
        "SNMPv3": [r"snmp v3"],
        "AAA": [r"system authentication-order"],
        "TACACS+": [r"tacplus-server"],
        "Firewall": [r"security policies"],
    },
    "services": {
        "NTP": [r"ntp server"],
        "Syslog": [r"syslog host"],
        "SSHv2": [r"ssh protocol-version v2"],
    },
}

# Arista-specific patterns (mostly Cisco-like but some differences)
ARISTA_PATTERNS = {
    "routing": {
        "BGP": [r"router bgp \d+"],
        "OSPF": [r"router ospf \d+"],
        "Static": [r"ip route"],
    },
    "security": {
        "AAA": [r"aaa authentication", r"aaa authorization"],
        "TACACS+": [r"tacacs-server"],
    },
    "switching": {
        "MLAG": [r"mlag configuration"],
        "VXLAN": [r"interface [Vv]xlan"],
    },
}


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class DeviceInfo:
    """Extracted device information for reporting."""
    hostname: str
    ip_address: str
    vendor: str
    platform: str
    sys_descr: str = ""  # Full system description
    uptime_days: Optional[float] = None
    interface_count: int = 0
    neighbor_count: int = 0
    discovered_via: str = "unknown"
    credential_used: str = "unknown"
    config_size: int = 0
    inventory_size: int = 0
    features: Dict[str, Set[str]] = field(default_factory=dict)


@dataclass
class AuditSummary:
    """Summary statistics for the audit."""
    total_devices: int = 0
    vendors: Dict[str, int] = field(default_factory=dict)
    protocols: Dict[str, int] = field(default_factory=dict)
    security_features: Dict[str, int] = field(default_factory=dict)
    services: Dict[str, int] = field(default_factory=dict)
    devices_with_bgp: int = 0
    devices_with_ospf: int = 0
    devices_with_snmpv2_only: int = 0
    devices_with_snmpv3: int = 0
    devices_with_aaa: int = 0
    total_interfaces: int = 0
    total_neighbors: int = 0


# =============================================================================
# Config Analyzer
# =============================================================================

class ConfigAnalyzer:
    """Analyze device configs for protocol and feature detection."""

    def __init__(self):
        self.patterns = CONFIG_PATTERNS

    def analyze(self, config: str, vendor: str = "cisco") -> Dict[str, Set[str]]:
        """
        Analyze config and return detected features by category.

        Returns:
            Dict mapping category -> set of detected features
            e.g., {"routing": {"BGP", "OSPF"}, "security": {"SNMPv2", "AAA"}}
        """
        features: Dict[str, Set[str]] = {
            "routing": set(),
            "security": set(),
            "services": set(),
            "switching": set(),
        }

        if not config:
            return features

        # Select patterns based on vendor
        if vendor.lower() == "juniper":
            patterns = {**self.patterns, **JUNIPER_PATTERNS}
        elif vendor.lower() == "arista":
            patterns = {**self.patterns, **ARISTA_PATTERNS}
        else:
            patterns = self.patterns

        config_lower = config.lower()

        for category, feature_patterns in patterns.items():
            if category not in features:
                features[category] = set()

            for feature_name, regexes in feature_patterns.items():
                for regex in regexes:
                    if re.search(regex, config, re.IGNORECASE | re.MULTILINE):
                        features[category].add(feature_name)
                        break  # Found this feature, no need to check more patterns

        return features


# =============================================================================
# Report Data Collector
# =============================================================================

class AuditDataCollector:
    """Collect and aggregate audit data for reporting."""

    def __init__(self, audit_path: str):
        self.audit_path = Path(audit_path)
        self.analyzer = ConfigAnalyzer()
        self.devices: List[DeviceInfo] = []
        self.summary = AuditSummary()

    def collect(self) -> None:
        """Collect data from all devices in audit folder."""
        if not self.audit_path.exists():
            raise ValueError(f"Audit path not found: {self.audit_path}")

        # Find all device folders
        device_folders = []
        for item in self.audit_path.iterdir():
            if item.is_dir() and (item / "device.json").exists():
                device_folders.append(item)

        logger.info(f"Found {len(device_folders)} devices in {self.audit_path}")

        for folder in sorted(device_folders):
            device_info = self._process_device(folder)
            if device_info:
                self.devices.append(device_info)

        # Build summary
        self._build_summary()

    def _process_device(self, folder: Path) -> Optional[DeviceInfo]:
        """Process a single device folder."""
        device_json = folder / "device.json"
        config_file = folder / "config.txt"
        inventory_file = folder / "inventory.txt"

        try:
            with open(device_json) as f:
                data = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load {device_json}: {e}")
            return None

        # Extract platform from sys_descr
        sys_descr = data.get("sys_descr", "") or ""
        platform = self._extract_platform(sys_descr, data.get("vendor", "unknown"))

        # Clean sys_descr for display (normalize line endings)
        sys_descr_clean = sys_descr.replace("\r\n", "\n").replace("\r", "\n").strip()

        # Calculate uptime in days
        uptime_ticks = data.get("uptime_ticks")
        uptime_days = None
        if uptime_ticks:
            # SNMP ticks are 1/100th second
            uptime_days = uptime_ticks / 100 / 86400

        # Read config if present
        config_content = ""
        config_size = 0
        if config_file.exists():
            try:
                config_content = config_file.read_text()
                config_size = len(config_content)
            except Exception as e:
                logger.warning(f"Failed to read config: {e}")

        # Read inventory if present
        inventory_size = 0
        if inventory_file.exists():
            try:
                inventory_size = inventory_file.stat().st_size
            except Exception:
                pass

        # Analyze config for features
        vendor = data.get("vendor", "unknown")
        features = self.analyzer.analyze(config_content, vendor)

        return DeviceInfo(
            hostname=data.get("hostname", folder.name),
            ip_address=data.get("ip_address", "unknown"),
            vendor=vendor,
            platform=platform,
            sys_descr=sys_descr_clean,
            uptime_days=uptime_days,
            interface_count=len(data.get("interfaces", [])),
            neighbor_count=len(data.get("neighbors", [])),
            discovered_via=data.get("discovered_via", "unknown"),
            credential_used=data.get("credential_used", "unknown"),
            config_size=config_size,
            inventory_size=inventory_size,
            features=features,
        )

    def _extract_platform(self, sys_descr: str, vendor: str) -> str:
        """Extract platform/model from sysDescr."""
        if not sys_descr:
            return "Unknown"

        # Cisco patterns
        if "cisco" in vendor.lower():
            # Match "IOSv Software" or "IOS Software"
            match = re.search(r"Cisco ([\w\-]+)", sys_descr)
            if match:
                return f"Cisco {match.group(1)}"
            match = re.search(r"(IOS[v]?)\s+Software.*Version\s+([\d\.()A-Z]+)", sys_descr)
            if match:
                return f"Cisco {match.group(1)} {match.group(2)}"

        # Arista
        if "arista" in vendor.lower():
            match = re.search(r"Arista ([\w\-]+)", sys_descr)
            if match:
                return f"Arista {match.group(1)}"
            if "vEOS" in sys_descr:
                match = re.search(r"EOS version ([\d\.A-Z]+)", sys_descr)
                if match:
                    return f"Arista vEOS {match.group(1)}"

        # Juniper
        if "juniper" in vendor.lower():
            match = re.search(r"(SRX|QFX|MX|EX)[\d]+", sys_descr)
            if match:
                return f"Juniper {match.group(0)}"
            match = re.search(r"JUNOS.*?(\d+\.\d+)", sys_descr)
            if match:
                return f"Juniper JUNOS {match.group(1)}"

        # Fallback: first 40 chars
        return sys_descr[:40].strip() + "..." if len(sys_descr) > 40 else sys_descr.strip()

    def _build_summary(self) -> None:
        """Build summary statistics from collected devices."""
        self.summary.total_devices = len(self.devices)

        vendor_counter: Counter = Counter()
        protocol_counter: Counter = Counter()
        security_counter: Counter = Counter()
        service_counter: Counter = Counter()

        for device in self.devices:
            # Vendor count
            vendor_counter[device.vendor.title()] += 1

            # Interface/neighbor totals
            self.summary.total_interfaces += device.interface_count
            self.summary.total_neighbors += device.neighbor_count

            # Protocol counts
            routing = device.features.get("routing", set())
            for proto in routing:
                protocol_counter[proto] += 1

            if "BGP" in routing:
                self.summary.devices_with_bgp += 1
            if "OSPF" in routing:
                self.summary.devices_with_ospf += 1

            # Security counts
            security = device.features.get("security", set())
            for feat in security:
                security_counter[feat] += 1

            if "SNMPv3" in security:
                self.summary.devices_with_snmpv3 += 1
            elif "SNMPv2" in security:
                self.summary.devices_with_snmpv2_only += 1

            if "AAA" in security:
                self.summary.devices_with_aaa += 1

            # Service counts
            services = device.features.get("services", set())
            for svc in services:
                service_counter[svc] += 1

        self.summary.vendors = dict(vendor_counter)
        self.summary.protocols = dict(protocol_counter)
        self.summary.security_features = dict(security_counter)
        self.summary.services = dict(service_counter)


# =============================================================================
# PDF Report Generator
# =============================================================================

class AuditReportGenerator:
    """Generate PDF audit report."""

    def __init__(self, collector: AuditDataCollector):
        self.collector = collector
        self.styles = None
        self.story = []

    def generate(self, output_path: str) -> str:
        """
        Generate PDF report.

        Args:
            output_path: Path for output PDF file.

        Returns:
            Path to generated PDF.
        """
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            PageBreak, KeepTogether
        )
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

        output_path = Path(output_path)

        # Create document
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch,
        )

        # Setup styles
        self.styles = getSampleStyleSheet()
        self.styles.add(ParagraphStyle(
            name='CenterTitle',
            parent=self.styles['Title'],
            alignment=TA_CENTER,
            fontSize=18,
            spaceAfter=20,
        ))
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceBefore=20,
            spaceAfter=10,
            textColor=colors.HexColor('#1a5276'),
        ))
        self.styles.add(ParagraphStyle(
            name='TableCell',
            parent=self.styles['Normal'],
            fontSize=8,
            leading=10,
        ))
        self.styles.add(ParagraphStyle(
            name='SmallText',
            parent=self.styles['Normal'],
            fontSize=9,
        ))

        self.story = []

        # Build report sections
        self._add_title_page()
        self._add_executive_summary()
        self._add_device_inventory()
        self._add_protocol_analysis()
        self._add_security_analysis()
        self._add_device_details()

        # Build PDF
        doc.build(self.story)

        return str(output_path)

    def _add_title_page(self) -> None:
        """Add title page."""
        from reportlab.platypus import Spacer, Paragraph
        from reportlab.lib.units import inch

        self.story.append(Spacer(1, 2*inch))

        self.story.append(Paragraph(
            "Network Audit Report",
            self.styles['CenterTitle']
        ))

        self.story.append(Spacer(1, 0.5*inch))

        # Report metadata
        self.story.append(Paragraph(
            f"<para alignment='center'>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</para>",
            self.styles['Normal']
        ))
        self.story.append(Paragraph(
            f"<para alignment='center'>Source: {self.collector.audit_path}</para>",
            self.styles['Normal']
        ))
        self.story.append(Paragraph(
            f"<para alignment='center'>Devices: {self.collector.summary.total_devices}</para>",
            self.styles['Normal']
        ))

        self.story.append(Spacer(1, inch))

        # Tool credit
        self.story.append(Paragraph(
            "<para alignment='center'><i>Generated by SecureCartography v2</i></para>",
            self.styles['SmallText']
        ))

        from reportlab.platypus import PageBreak
        self.story.append(PageBreak())

    def _add_executive_summary(self) -> None:
        """Add executive summary section."""
        from reportlab.platypus import Spacer, Paragraph, Table, TableStyle
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from reportlab.graphics.shapes import Drawing, String
        from reportlab.graphics.charts.piecharts import Pie

        summary = self.collector.summary

        self.story.append(Paragraph("Executive Summary", self.styles['SectionHeader']))

        # Overview stats
        overview_text = f"""
        This audit covers <b>{summary.total_devices}</b> network devices with 
        <b>{summary.total_interfaces}</b> interfaces and 
        <b>{summary.total_neighbors}</b> discovered neighbors.
        """
        self.story.append(Paragraph(overview_text, self.styles['Normal']))
        self.story.append(Spacer(1, 0.2*inch))

        # === UPTIME ANALYSIS ===
        self._add_uptime_analysis()

        # Vendor breakdown table
        if summary.vendors:
            self.story.append(Paragraph("<b>Vendor Distribution</b>", self.styles['Normal']))
            self.story.append(Spacer(1, 0.1*inch))

            vendor_data = [["Vendor", "Count", "Percentage"]]
            for vendor, count in sorted(summary.vendors.items(), key=lambda x: -x[1]):
                pct = (count / summary.total_devices * 100) if summary.total_devices > 0 else 0
                vendor_data.append([vendor, str(count), f"{pct:.1f}%"])

            vendor_table = Table(vendor_data, colWidths=[2*inch, inch, inch])
            vendor_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            self.story.append(vendor_table)
            self.story.append(Spacer(1, 0.3*inch))

        # Key findings
        self.story.append(Paragraph("<b>Key Findings</b>", self.styles['Normal']))
        self.story.append(Spacer(1, 0.1*inch))

        findings = []

        if summary.devices_with_bgp > 0:
            findings.append(f"• {summary.devices_with_bgp} devices running BGP")
        if summary.devices_with_ospf > 0:
            findings.append(f"• {summary.devices_with_ospf} devices running OSPF")
        if summary.devices_with_snmpv2_only > 0:
            findings.append(f"• <font color='red'>{summary.devices_with_snmpv2_only} devices with SNMPv2 only (consider upgrading to SNMPv3)</font>")
        if summary.devices_with_snmpv3 > 0:
            findings.append(f"• {summary.devices_with_snmpv3} devices with SNMPv3 configured")
        if summary.devices_with_aaa > 0:
            findings.append(f"• {summary.devices_with_aaa} devices with AAA configured")

        if not findings:
            findings.append("• No routing or security protocols detected in configs")

        for finding in findings:
            self.story.append(Paragraph(finding, self.styles['SmallText']))

    def _add_uptime_analysis(self) -> None:
        """Add uptime distribution pie chart and table."""
        from reportlab.platypus import Spacer, Paragraph, Table, TableStyle
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from reportlab.graphics.shapes import Drawing, String, Rect
        from reportlab.graphics.charts.piecharts import Pie

        # Categorize devices by uptime
        categories = {
            "< 3 months": {"count": 0, "devices": [], "color": colors.HexColor('#27ae60'), "severity": "Good"},
            "3-6 months": {"count": 0, "devices": [], "color": colors.HexColor('#2ecc71'), "severity": "Normal"},
            "6-12 months": {"count": 0, "devices": [], "color": colors.HexColor('#f39c12'), "severity": "Review"},
            "1-2 years": {"count": 0, "devices": [], "color": colors.HexColor('#e67e22'), "severity": "Warning"},
            "> 2 years": {"count": 0, "devices": [], "color": colors.HexColor('#c0392b'), "severity": "Critical"},
            "Unknown": {"count": 0, "devices": [], "color": colors.HexColor('#95a5a6'), "severity": "N/A"},
        }

        for device in self.collector.devices:
            if device.uptime_days is None:
                categories["Unknown"]["count"] += 1
                categories["Unknown"]["devices"].append(device.hostname)
            elif device.uptime_days < 90:  # < 3 months
                categories["< 3 months"]["count"] += 1
                categories["< 3 months"]["devices"].append(device.hostname)
            elif device.uptime_days < 180:  # 3-6 months
                categories["3-6 months"]["count"] += 1
                categories["3-6 months"]["devices"].append(device.hostname)
            elif device.uptime_days < 365:  # 6-12 months
                categories["6-12 months"]["count"] += 1
                categories["6-12 months"]["devices"].append(device.hostname)
            elif device.uptime_days < 730:  # 1-2 years
                categories["1-2 years"]["count"] += 1
                categories["1-2 years"]["devices"].append(device.hostname)
            else:  # > 2 years
                categories["> 2 years"]["count"] += 1
                categories["> 2 years"]["devices"].append(device.hostname)

        self.story.append(Paragraph("<b>Uptime Analysis</b>", self.styles['Normal']))
        self.story.append(Spacer(1, 0.1*inch))

        self.story.append(Paragraph(
            "<i>Extended uptime may indicate deferred maintenance and missed security patches.</i>",
            self.styles['SmallText']
        ))
        self.story.append(Spacer(1, 0.1*inch))

        # Filter to only categories with devices
        active_categories = {k: v for k, v in categories.items() if v["count"] > 0}

        if not active_categories:
            self.story.append(Paragraph("No uptime data available.", self.styles['Normal']))
            self.story.append(Spacer(1, 0.2*inch))
            return

        # Create side-by-side layout: pie chart + legend/table
        # Using a table to position them

        # Build pie chart
        drawing = Drawing(200, 150)
        pie = Pie()
        pie.x = 60
        pie.y = 25
        pie.width = 100
        pie.height = 100

        # Data for pie
        pie_data = []
        pie_colors = []
        pie_labels = []

        for cat_name, cat_data in active_categories.items():
            pie_data.append(cat_data["count"])
            pie_colors.append(cat_data["color"])
            pie_labels.append(cat_name)

        pie.data = pie_data
        pie.labels = None  # We'll use a separate legend

        for i, color in enumerate(pie_colors):
            pie.slices[i].fillColor = color
            pie.slices[i].strokeColor = colors.white
            pie.slices[i].strokeWidth = 1

        drawing.add(pie)

        # Build legend table
        legend_data = [["Uptime", "Count", "Severity"]]
        for cat_name, cat_data in active_categories.items():
            severity = cat_data["severity"]
            # Color code severity text
            if severity == "Critical":
                sev_text = f"<font color='#c0392b'><b>{severity}</b></font>"
            elif severity == "Warning":
                sev_text = f"<font color='#e67e22'><b>{severity}</b></font>"
            elif severity == "Review":
                sev_text = f"<font color='#f39c12'>{severity}</font>"
            else:
                sev_text = severity

            legend_data.append([
                cat_name,
                str(cat_data["count"]),
                Paragraph(sev_text, self.styles['SmallText'])
            ])

        legend_table = Table(legend_data, colWidths=[1.2*inch, 0.6*inch, 0.8*inch])
        legend_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
        ]))

        # Combine pie chart and legend in a table
        combined_table = Table([[drawing, legend_table]], colWidths=[2.5*inch, 3*inch])
        combined_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))

        self.story.append(combined_table)

        # Add warning callout for critical devices
        critical_devices = categories["> 2 years"]["devices"] + categories["1-2 years"]["devices"]
        if critical_devices:
            self.story.append(Spacer(1, 0.1*inch))

            warning_text = f"<font color='#c0392b'><b>⚠ Devices requiring attention:</b></font> "
            warning_text += ", ".join(critical_devices[:5])
            if len(critical_devices) > 5:
                warning_text += f" (+{len(critical_devices) - 5} more)"

            self.story.append(Paragraph(warning_text, self.styles['SmallText']))

        self.story.append(Spacer(1, 0.3*inch))

    def _add_device_inventory(self) -> None:
        """Add device inventory table."""
        from reportlab.platypus import Spacer, Paragraph, Table, TableStyle, PageBreak
        from reportlab.lib import colors
        from reportlab.lib.units import inch

        self.story.append(PageBreak())
        self.story.append(Paragraph("Device Inventory", self.styles['SectionHeader']))

        # Build table data
        table_data = [["Hostname", "IP Address", "Vendor", "Platform", "Uptime", "Intf", "Nbr"]]

        for device in sorted(self.collector.devices, key=lambda d: d.hostname):
            uptime_str = f"{device.uptime_days:.1f}d" if device.uptime_days else "N/A"

            # Truncate platform if too long
            platform = device.platform
            if len(platform) > 25:
                platform = platform[:22] + "..."

            table_data.append([
                device.hostname,
                device.ip_address,
                device.vendor.title(),
                platform,
                uptime_str,
                str(device.interface_count),
                str(device.neighbor_count),
            ])

        # Create table
        col_widths = [1.5*inch, 1.1*inch, 0.7*inch, 1.8*inch, 0.6*inch, 0.4*inch, 0.4*inch]
        inventory_table = Table(table_data, colWidths=col_widths, repeatRows=1)

        inventory_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('ALIGN', (4, 1), (-1, -1), 'CENTER'),  # Right-align numeric columns
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('TOPPADDING', (0, 1), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
        ]))

        self.story.append(inventory_table)

    def _add_protocol_analysis(self) -> None:
        """Add protocol analysis section."""
        from reportlab.platypus import Spacer, Paragraph, Table, TableStyle, PageBreak
        from reportlab.lib import colors
        from reportlab.lib.units import inch

        self.story.append(PageBreak())
        self.story.append(Paragraph("Protocol Analysis", self.styles['SectionHeader']))

        # Routing protocols
        self.story.append(Paragraph("<b>Routing Protocols</b>", self.styles['Normal']))
        self.story.append(Spacer(1, 0.1*inch))

        # Build protocol matrix
        table_data = [["Hostname", "BGP", "OSPF", "EIGRP", "IS-IS", "Static", "RIP"]]

        for device in sorted(self.collector.devices, key=lambda d: d.hostname):
            routing = device.features.get("routing", set())
            row = [
                device.hostname,
                "✓" if "BGP" in routing else "",
                "✓" if "OSPF" in routing else "",
                "✓" if "EIGRP" in routing else "",
                "✓" if "IS-IS" in routing else "",
                "✓" if "Static" in routing else "",
                "✓" if "RIP" in routing else "",
            ]
            table_data.append(row)

        col_widths = [1.8*inch, 0.6*inch, 0.6*inch, 0.6*inch, 0.6*inch, 0.6*inch, 0.6*inch]
        proto_table = Table(table_data, colWidths=col_widths, repeatRows=1)

        proto_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5276')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('TOPPADDING', (0, 1), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 2),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#eaf2f8')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
        ]))

        self.story.append(proto_table)

    def _add_security_analysis(self) -> None:
        """Add security analysis section."""
        from reportlab.platypus import Spacer, Paragraph, Table, TableStyle, PageBreak
        from reportlab.lib import colors
        from reportlab.lib.units import inch

        self.story.append(PageBreak())
        self.story.append(Paragraph("Security Analysis", self.styles['SectionHeader']))

        # Security features matrix
        self.story.append(Paragraph("<b>Security Features by Device</b>", self.styles['Normal']))
        self.story.append(Spacer(1, 0.1*inch))

        table_data = [["Hostname", "SNMPv2", "SNMPv3", "AAA", "TACACS+", "RADIUS", "ACLs"]]

        for device in sorted(self.collector.devices, key=lambda d: d.hostname):
            security = device.features.get("security", set())

            # Flag SNMPv2-only as a concern
            snmpv2_cell = "⚠️" if ("SNMPv2" in security and "SNMPv3" not in security) else ("✓" if "SNMPv2" in security else "")

            row = [
                device.hostname,
                snmpv2_cell,
                "✓" if "SNMPv3" in security else "",
                "✓" if "AAA" in security else "",
                "✓" if "TACACS+" in security else "",
                "✓" if "RADIUS" in security else "",
                "✓" if "ACLs" in security else "",
            ]
            table_data.append(row)

        col_widths = [1.8*inch, 0.7*inch, 0.7*inch, 0.6*inch, 0.7*inch, 0.7*inch, 0.6*inch]
        sec_table = Table(table_data, colWidths=col_widths, repeatRows=1)

        sec_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#922b21')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('TOPPADDING', (0, 1), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 2),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9ebea')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
        ]))

        self.story.append(sec_table)

        self.story.append(Spacer(1, 0.3*inch))

        # Legend
        self.story.append(Paragraph("<b>Legend:</b> ✓ = Configured, ⚠️ = SNMPv2 without SNMPv3 (security concern)",
                                     self.styles['SmallText']))

    def _add_device_details(self) -> None:
        """Add device details appendix with full system descriptions."""
        from reportlab.platypus import Spacer, Paragraph, Table, TableStyle, PageBreak, KeepTogether
        from reportlab.lib import colors
        from reportlab.lib.units import inch

        self.story.append(PageBreak())
        self.story.append(Paragraph("Appendix: Device Details", self.styles['SectionHeader']))

        self.story.append(Paragraph(
            "Full system descriptions (sysDescr) for each discovered device.",
            self.styles['SmallText']
        ))
        self.story.append(Spacer(1, 0.2*inch))

        for device in sorted(self.collector.devices, key=lambda d: d.hostname):
            # Format sys_descr - replace newlines with <br/> for PDF
            if device.sys_descr:
                # Escape any XML/HTML special chars and convert newlines
                sys_descr_formatted = device.sys_descr.replace("&", "&amp;")
                sys_descr_formatted = sys_descr_formatted.replace("<", "&lt;")
                sys_descr_formatted = sys_descr_formatted.replace(">", "&gt;")
                sys_descr_formatted = sys_descr_formatted.replace("\n", "<br/>")
            else:
                sys_descr_formatted = "<i>No system description available</i>"

            # Build device detail block
            detail_content = []

            # Header row with hostname and IP
            header_text = f"<b>{device.hostname}</b> ({device.ip_address})"
            detail_content.append(Paragraph(header_text, self.styles['Normal']))

            # Metadata line
            uptime_str = f"{device.uptime_days:.1f} days" if device.uptime_days else "N/A"
            meta_text = f"<font size='8'>Vendor: {device.vendor.title()} | Uptime: {uptime_str} | Discovered via: {device.discovered_via}</font>"
            detail_content.append(Paragraph(meta_text, self.styles['SmallText']))

            detail_content.append(Spacer(1, 0.05*inch))

            # System description in a styled box
            sys_descr_para = Paragraph(
                f"<font size='7' face='Courier'>{sys_descr_formatted}</font>",
                self.styles['Normal']
            )

            # Wrap in a table for background color
            desc_table = Table([[sys_descr_para]], colWidths=[7*inch])
            desc_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f4f6f7')),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            detail_content.append(desc_table)

            detail_content.append(Spacer(1, 0.15*inch))

            # Try to keep each device block together
            self.story.append(KeepTogether(detail_content))


# =============================================================================
# CLI Function
# =============================================================================

def generate_report(
    audit_path: str,
    output_path: Optional[str] = None,
    verbose: bool = False,
) -> str:
    """
    Generate PDF audit report from audit folder.

    Args:
        audit_path: Path to audit output folder.
        output_path: Optional output PDF path (default: audit_report_<timestamp>.pdf)
        verbose: Enable verbose output.

    Returns:
        Path to generated PDF.
    """
    # Default output path
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"audit_report_{timestamp}.pdf"

    if verbose:
        print(f"Collecting data from: {audit_path}")

    # Collect data
    collector = AuditDataCollector(audit_path)
    collector.collect()

    if verbose:
        print(f"Found {len(collector.devices)} devices")
        print(f"Generating report: {output_path}")

    # Generate report
    generator = AuditReportGenerator(collector)
    result_path = generator.generate(output_path)

    if verbose:
        print(f"Report generated: {result_path}")

    return result_path