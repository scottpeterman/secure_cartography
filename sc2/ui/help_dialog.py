"""
SecureCartography v2 - Help Dialog

Comprehensive help system covering:
- GUI workflow overview
- CLI usage for remote/jump host scenarios
- Security analysis workflow
- Keyboard shortcuts
"""

from typing import Optional
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QTextBrowser,
    QPushButton, QWidget, QScrollArea, QLabel
)
from PyQt6.QtGui import QFont

from .themes import ThemeManager, ThemeColors


class HelpDialog(QDialog):
    """
    Help dialog with tabbed sections for different topics.

    Sections:
    - Overview: What Secure Cartography does
    - GUI Guide: Using the desktop application
    - CLI Guide: Command-line tools for jump hosts
    - Security Analysis: CVE vulnerability workflow
    - Shortcuts: Keyboard shortcuts reference
    """

    def __init__(
            self,
            theme_manager: Optional[ThemeManager] = None,
            parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.theme_manager = theme_manager

        self.setWindowTitle("Secure Cartography - Help")
        self.setMinimumSize(800, 600)
        self.resize(900, 700)

        self._setup_ui()

        if theme_manager:
            self.apply_theme(theme_manager.theme)

    def _setup_ui(self):
        """Build the help dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Tab widget for different help sections
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        # Add help sections
        self.tabs.addTab(self._create_overview_tab(), "Overview")
        self.tabs.addTab(self._create_gui_tab(), "GUI Guide")
        self.tabs.addTab(self._create_cli_tab(), "CLI Guide")
        self.tabs.addTab(self._create_security_tab(), "Security Analysis")
        self.tabs.addTab(self._create_shortcuts_tab(), "Shortcuts")

        layout.addWidget(self.tabs)

        # Close button
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(16, 12, 16, 12)
        button_layout.addStretch()

        self.close_btn = QPushButton("Close")
        self.close_btn.setFixedWidth(100)
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

    def _create_text_browser(self, html: str) -> QTextBrowser:
        """Create a styled text browser with HTML content."""
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(html)
        return browser

    def _create_overview_tab(self) -> QWidget:
        """Overview tab content."""
        html = """
        <h1>Secure Cartography</h1>
        <p><b>Network Discovery &amp; Security Analysis Platform</b></p>

        <h2>What It Does</h2>
        <p>Secure Cartography automatically discovers your network infrastructure using 
        SNMP, CDP, and LLDP protocols. It builds topology maps showing how devices connect, 
        extracts hardware inventory, and identifies security vulnerabilities through CVE analysis.</p>

        <h2>Key Capabilities</h2>
        <table cellpadding="8">
            <tr>
                <td><b>🔍 Discovery</b></td>
                <td>Recursive network crawling from seed devices using CDP/LLDP neighbor data</td>
            </tr>
            <tr>
                <td><b>🗺️ Topology</b></td>
                <td>Interactive network maps with device relationships and connection details</td>
            </tr>
            <tr>
                <td><b>📦 Inventory</b></td>
                <td>Hardware components, serial numbers, software versions across all discovered devices</td>
            </tr>
            <tr>
                <td><b>🔐 Security</b></td>
                <td>CVE vulnerability analysis by mapping platforms to NIST NVD database</td>
            </tr>
            <tr>
                <td><b>🔑 Credentials</b></td>
                <td>Encrypted vault for SNMP credentials with automatic discovery of working creds</td>
            </tr>
        </table>

        <h2>Typical Workflow</h2>
        <ol>
            <li>Configure SNMP credentials in the vault</li>
            <li>Enter seed IP(s) - core routers or switches that see the network</li>
            <li>Set domain filters to constrain discovery scope</li>
            <li>Run discovery - watch the topology build in real-time</li>
            <li>Open Security Analysis to check for known vulnerabilities</li>
            <li>Export maps and reports for documentation</li>
        </ol>

        <h2>Supported Platforms</h2>
        <p>Secure Cartography works with any SNMP-enabled device. Enhanced parsing for:</p>
        <ul>
            <li>Cisco IOS, IOS-XE, IOS-XR, NX-OS</li>
            <li>Arista EOS</li>
            <li>Juniper JUNOS</li>
            <li>Palo Alto PAN-OS</li>
            <li>Fortinet FortiOS</li>
            <li>Aruba/HPE, Dell, Extreme, MikroTik, Ubiquiti</li>
        </ul>
        """
        return self._create_text_browser(html)

    def _create_gui_tab(self) -> QWidget:
        """GUI guide tab content."""
        html = """
        <h1>GUI Guide</h1>

        <h2>Main Window Layout</h2>
        <p>The interface is organized into three columns:</p>

        <h3>Left Column - Connection Setup</h3>
        <ul>
            <li><b>Seed IPs:</b> Starting points for discovery (usually core routers/switches)</li>
            <li><b>Domain Filter:</b> Limit discovery to hostnames matching these domains</li>
            <li><b>Exclude Patterns:</b> Skip devices matching these patterns</li>
            <li><b>Credentials:</b> SNMP credentials from your encrypted vault</li>
        </ul>

        <h3>Middle Column - Options &amp; Actions</h3>
        <ul>
            <li><b>Max Depth:</b> How many hops from seed devices to crawl</li>
            <li><b>Concurrency:</b> Parallel device queries (higher = faster, more load)</li>
            <li><b>Timeout:</b> Per-device SNMP timeout in seconds</li>
            <li><b>No DNS:</b> Use raw IPs from CDP/LLDP (useful for lab environments)</li>
            <li><b>Output Directory:</b> Where to save discovery results</li>
        </ul>

        <h3>Right Column - Results</h3>
        <ul>
            <li><b>Progress:</b> Discovery status and statistics</li>
            <li><b>Topology Preview:</b> Real-time network map as devices are discovered</li>
            <li><b>Discovery Log:</b> Detailed event log with timestamps</li>
        </ul>

        <h2>Header Bar</h2>
        <table cellpadding="8">
            <tr>
                <td><b>? HELP</b></td>
                <td>Opens this help dialog</td>
            </tr>
            <tr>
                <td><b>🔐 SECURITY</b></td>
                <td>Opens CVE vulnerability analysis window</td>
            </tr>
            <tr>
                <td><b>Theme Selector</b></td>
                <td>Switch between Cyber, Dark, and Light themes</td>
            </tr>
        </table>

        <h2>Discovery Process</h2>
        <ol>
            <li>Click <b>START CRAWL</b> to begin discovery</li>
            <li>Watch the topology build in the preview panel</li>
            <li>Click <b>STOP CRAWL</b> to halt discovery early if needed</li>
            <li>Use <b>ENHANCE MAP</b> to open the full interactive map viewer</li>
            <li>Results are automatically saved to the output directory</li>
        </ol>

        <h2>Output Files</h2>
        <p>Discovery creates several files in your output directory:</p>
        <ul>
            <li><code>map.json</code> - Topology data for map viewer</li>
            <li><code>devices.csv</code> - Device inventory spreadsheet</li>
            <li><code>devices.json</code> - Full device data in JSON format</li>
            <li><code>topology.graphml</code> - Network graph for external tools</li>
        </ul>
        """
        return self._create_text_browser(html)

    def _create_cli_tab(self) -> QWidget:
        """CLI guide tab content."""
        html = """
        <h1>CLI Guide</h1>
        <p>Command-line tools for running discovery from jump hosts, automation scripts, 
        or environments without GUI access.</p>

        <h2>Credential Manager</h2>
        <pre>python -m sc2.scng.creds [command] [options]</pre>

        <h3>Commands</h3>
        <table cellpadding="6" border="0">
            <tr><td><code>init</code></td><td>Initialize a new credential vault</td></tr>
            <tr><td><code>unlock</code></td><td>Validate vault password</td></tr>
            <tr><td><code>add</code></td><td>Add a new SNMP credential</td></tr>
            <tr><td><code>list</code></td><td>List all stored credentials</td></tr>
            <tr><td><code>show</code></td><td>Show credential details</td></tr>
            <tr><td><code>remove</code></td><td>Remove a credential</td></tr>
            <tr><td><code>set-default</code></td><td>Set credential as default</td></tr>
            <tr><td><code>test</code></td><td>Test credential against a device</td></tr>
            <tr><td><code>discover</code></td><td>Discover working credentials for a device</td></tr>
            <tr><td><code>change-password</code></td><td>Change vault master password</td></tr>
            <tr><td><code>deps</code></td><td>Check SNMP dependencies</td></tr>
        </table>

        <h3>Options</h3>
        <pre>
--vault-path, -v    Path to vault database 
                    (default: ~/.scng/credentials.db)
--password, -p      Vault password 
                    (or set SCNG_VAULT_PASSWORD env var)
        </pre>

        <h3>Examples</h3>
        <pre>
# Initialize vault on a jump host
python -m sc2.scng.creds init

# Add SNMPv2 credential
python -m sc2.scng.creds add --name "network-ro" \\
    --version 2c --community "readonlystring"

# Add SNMPv3 credential
python -m sc2.scng.creds add --name "secure-snmp" \\
    --version 3 --user "snmpuser" \\
    --auth-proto SHA --auth-pass "authpass123" \\
    --priv-proto AES --priv-pass "privpass123"

# Test credential against device
python -m sc2.scng.creds test 192.168.1.1 --name "network-ro"
        </pre>

        <hr>

        <h2>Network Discovery</h2>
        <pre>python -m sc2.scng.discovery [command] [options]</pre>

        <h3>Commands</h3>
        <table cellpadding="6" border="0">
            <tr><td><code>test</code></td><td>Quick test with inline community string</td></tr>
            <tr><td><code>device</code></td><td>Discover single device using vault credentials</td></tr>
            <tr><td><code>crawl</code></td><td>Recursive network discovery</td></tr>
        </table>

        <h3>Crawl Options</h3>
        <pre>
-d, --depth         Max hops from seed (default: 3)
--domain            Domain filter (can specify multiple)
--exclude           Exclude pattern (can specify multiple)
-o, --output        Output directory
--concurrency       Parallel queries (default: 10)
--timeout           Per-device timeout seconds (default: 5)
--no-dns            Use raw IPs from CDP/LLDP
-v, --verbose       Verbose output
--timestamps        Show timestamps in output
        </pre>

        <h3>Examples</h3>
        <pre>
# Quick SNMP test with community string
python -m sc2.scng.discovery test 192.168.1.1 --community public

# Single device discovery using vault
python -m sc2.scng.discovery device 192.168.1.1

# Recursive crawl with domain filter
python -m sc2.scng.discovery crawl 192.168.1.1 \\
    -d 3 --domain example.com -o ./output

# Home lab (no DNS, use IPs from LLDP/CDP)
python -m sc2.scng.discovery crawl 192.168.1.1 \\
    -d 3 --no-dns

# Large network with high concurrency
python -m sc2.scng.discovery crawl 10.0.0.1 \\
    -d 5 --concurrency 30 -o ./datacenter

# Verbose with timestamps for debugging
python -m sc2.scng.discovery crawl 192.168.1.1 \\
    -v --timestamps
        </pre>

        <hr>

        <h2>Jump Host Workflow</h2>
        <p>When your desktop doesn't have SNMP access but a jump host does:</p>
        <ol>
            <li>SSH to the jump host</li>
            <li>Install Secure Cartography: <code>pip install .</code></li>
            <li>Initialize vault: <code>python -m sc2.scng.creds init</code></li>
            <li>Add credentials: <code>python -m sc2.scng.creds add ...</code></li>
            <li>Run discovery: <code>python -m sc2.scng.discovery crawl ...</code></li>
            <li>Copy output files back to desktop for analysis</li>
            <li>Open in GUI for map viewing and security analysis</li>
        </ol>

        <h2>Environment Variables</h2>
        <table cellpadding="6" border="0">
            <tr><td><code>SCNG_VAULT_PASSWORD</code></td><td>Vault password (avoids -p flag)</td></tr>
            <tr><td><code>SCNG_VAULT_PATH</code></td><td>Custom vault location</td></tr>
        </table>
        """
        return self._create_text_browser(html)

    def _create_security_tab(self) -> QWidget:
        """Security analysis tab content."""
        html = """
        <h1>Security Analysis</h1>
        <p>The Security Analysis window maps discovered platforms to known vulnerabilities 
        using the NIST National Vulnerability Database (NVD).</p>

        <h2>Workflow</h2>
        <ol>
            <li><b>Load CSV:</b> Import the <code>devices.csv</code> from a discovery run</li>
            <li><b>Review Mappings:</b> Check auto-detected platform → CPE mappings</li>
            <li><b>Sync Selected:</b> Query NVD for CVEs matching each platform</li>
            <li><b>Analyze Results:</b> Review CVEs sorted by severity</li>
        </ol>

        <h2>Platform Mapping</h2>
        <p>Secure Cartography automatically parses platform strings and maps them to 
        CPE (Common Platform Enumeration) format for NVD queries:</p>
        <pre>
"Cisco IOS 15.2(4.0.55)E" → cpe:2.3:o:cisco:ios:15.2(4.0.55)e:*:*:*:*:*:*:*
"Arista vEOS-lab EOS 4.33.1F" → cpe:2.3:o:arista:eos:4.33.1f:*:*:*:*:*:*:*
        </pre>

        <h3>Confidence Levels</h3>
        <table cellpadding="6" border="0">
            <tr><td><b>High</b></td><td>Platform matched a known pattern, ready to sync</td></tr>
            <tr><td><b>Medium</b></td><td>Partial match, may need manual verification</td></tr>
            <tr><td><b>Low</b></td><td>Unknown format, requires manual CPE entry</td></tr>
        </table>

        <p>Double-click Vendor, Product, or CPE Version columns to edit mappings manually.</p>

        <h2>CVE Results</h2>
        <p>After syncing, view results in three tabs:</p>
        <ul>
            <li><b>Cached Versions:</b> All synced platforms with CVE counts</li>
            <li><b>Summary:</b> Aggregate statistics and severity breakdown</li>
            <li><b>CVEs:</b> Detailed CVE list for selected platform</li>
        </ul>

        <h3>Severity Colors</h3>
        <table cellpadding="6" border="0">
            <tr><td style="background:#dc2626;color:white;padding:4px 12px"><b>CRITICAL</b></td><td>CVSS 9.0-10.0</td></tr>
            <tr><td style="background:#f97316;color:white;padding:4px 12px"><b>HIGH</b></td><td>CVSS 7.0-8.9</td></tr>
            <tr><td style="background:#eab308;color:black;padding:4px 12px"><b>MEDIUM</b></td><td>CVSS 4.0-6.9</td></tr>
            <tr><td style="background:#22c55e;color:white;padding:4px 12px"><b>LOW</b></td><td>CVSS 0.1-3.9</td></tr>
        </table>

        <h2>NVD API</h2>
        <p>By default, queries are rate-limited to 5 requests per 30 seconds. 
        For faster syncing, get a free API key from:</p>
        <p><a href="https://nvd.nist.gov/developers/request-an-api-key">
        https://nvd.nist.gov/developers/request-an-api-key</a></p>
        <p>Enter your API key in the Security Analysis window to increase the rate limit.</p>

        <h2>Cache</h2>
        <p>CVE data is cached locally to avoid repeated API calls:</p>
        <ul>
            <li>Cache location: <code>~/.scng/cve_cache.db</code></li>
            <li>Use <b>View Cache</b> to see previously synced data</li>
            <li>Check <b>Force Re-sync</b> to refresh stale data</li>
        </ul>

        <h2>Custom Patterns</h2>
        <p>Add custom platform parsing patterns via <b>Add Pattern</b> button. 
        Patterns are stored in <code>~/.scng/platform_patterns.json</code></p>
        """
        return self._create_text_browser(html)

    def _create_shortcuts_tab(self) -> QWidget:
        """Keyboard shortcuts tab content."""
        html = """
        <h1>Keyboard Shortcuts</h1>

        <h2>Main Window</h2>
        <table cellpadding="8" border="0">
            <tr><td><code>Ctrl+Enter</code></td><td>Start/Stop discovery</td></tr>
            <tr><td><code>Ctrl+M</code></td><td>Open map viewer</td></tr>
            <tr><td><code>Ctrl+Shift+S</code></td><td>Open security analysis</td></tr>
            <tr><td><code>F1</code></td><td>Open help</td></tr>
            <tr><td><code>Ctrl+Q</code></td><td>Quit application</td></tr>
        </table>

        <h2>Map Viewer</h2>
        <table cellpadding="8" border="0">
            <tr><td><code>Ctrl+O</code></td><td>Open map file</td></tr>
            <tr><td><code>Ctrl+S</code></td><td>Save map</td></tr>
            <tr><td><code>Ctrl+E</code></td><td>Export image</td></tr>
            <tr><td><code>Ctrl+F</code></td><td>Find device</td></tr>
            <tr><td><code>+</code> / <code>-</code></td><td>Zoom in/out</td></tr>
            <tr><td><code>0</code></td><td>Reset zoom</td></tr>
            <tr><td><code>F</code></td><td>Fit to window</td></tr>
            <tr><td><code>Escape</code></td><td>Clear selection</td></tr>
        </table>

        <h2>Security Analysis</h2>
        <table cellpadding="8" border="0">
            <tr><td><code>Ctrl+O</code></td><td>Load CSV</td></tr>
            <tr><td><code>Ctrl+A</code></td><td>Select all platforms</td></tr>
            <tr><td><code>Enter</code></td><td>Sync selected</td></tr>
            <tr><td><code>Escape</code></td><td>Stop sync</td></tr>
        </table>

        <h2>Tables</h2>
        <table cellpadding="8" border="0">
            <tr><td><code>Ctrl+C</code></td><td>Copy selected cells</td></tr>
            <tr><td><code>Double-click</code></td><td>Edit cell (where supported)</td></tr>
            <tr><td><code>Click header</code></td><td>Sort by column</td></tr>
        </table>
        """
        return self._create_text_browser(html)

    def apply_theme(self, theme: ThemeColors):
        """Apply theme colors to the dialog."""
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {theme.bg_primary};
                color: {theme.text_primary};
            }}

            QTabWidget::pane {{
                background-color: {theme.bg_secondary};
                border: 1px solid {theme.border_dim};
                border-top: none;
            }}

            QTabBar::tab {{
                background-color: {theme.bg_tertiary};
                border: 1px solid {theme.border_dim};
                border-bottom: none;
                padding: 10px 20px;
                color: {theme.text_secondary};
                margin-right: 2px;
            }}

            QTabBar::tab:selected {{
                background-color: {theme.bg_secondary};
                color: {theme.accent};
                border-bottom: 2px solid {theme.accent};
            }}

            QTabBar::tab:hover:!selected {{
                color: {theme.text_primary};
            }}

            QTextBrowser {{
                background-color: {theme.bg_secondary};
                border: none;
                padding: 20px;
                color: {theme.text_primary};
            }}

            QPushButton {{
                background-color: {theme.bg_tertiary};
                border: 1px solid {theme.border_dim};
                border-radius: 6px;
                padding: 10px 20px;
                color: {theme.text_primary};
                font-weight: 500;
            }}

            QPushButton:hover {{
                border-color: {theme.accent};
                color: {theme.accent};
            }}
        """)

        # Style the HTML content in text browsers
        html_style = f"""
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    font-size: 14px;
                    line-height: 1.6;
                    color: {theme.text_primary};
                }}
                h1 {{
                    color: {theme.accent};
                    font-size: 24px;
                    margin-bottom: 16px;
                    border-bottom: 1px solid {theme.border_dim};
                    padding-bottom: 8px;
                }}
                h2 {{
                    color: {theme.text_primary};
                    font-size: 18px;
                    margin-top: 24px;
                    margin-bottom: 12px;
                }}
                h3 {{
                    color: {theme.text_secondary};
                    font-size: 15px;
                    margin-top: 16px;
                    margin-bottom: 8px;
                }}
                code {{
                    background-color: {theme.bg_tertiary};
                    padding: 2px 6px;
                    border-radius: 4px;
                    font-family: 'Consolas', 'Monaco', monospace;
                    font-size: 13px;
                }}
                pre {{
                    background-color: {theme.bg_tertiary};
                    padding: 12px 16px;
                    border-radius: 6px;
                    border-left: 3px solid {theme.accent};
                    overflow-x: auto;
                    font-family: 'Consolas', 'Monaco', monospace;
                    font-size: 13px;
                    line-height: 1.5;
                }}
                table {{
                    border-collapse: collapse;
                    margin: 12px 0;
                }}
                td {{
                    vertical-align: top;
                    padding: 6px 12px;
                }}
                ul, ol {{
                    margin: 8px 0;
                    padding-left: 24px;
                }}
                li {{
                    margin: 4px 0;
                }}
                a {{
                    color: {theme.accent};
                }}
                hr {{
                    border: none;
                    border-top: 1px solid {theme.border_dim};
                    margin: 24px 0;
                }}
            </style>
        """

        # Re-apply HTML with styling to each tab
        for i in range(self.tabs.count()):
            browser = self.tabs.widget(i)
            if isinstance(browser, QTextBrowser):
                current_html = browser.toHtml()
                # Inject style if not already present
                if '<style>' not in current_html:
                    # Get the original content (without Qt's wrapper)
                    browser.setHtml(html_style + browser.toPlainText())
                    # Re-render the actual content
                    if i == 0:
                        browser.setHtml(html_style + self._get_overview_html())
                    elif i == 1:
                        browser.setHtml(html_style + self._get_gui_html())
                    elif i == 2:
                        browser.setHtml(html_style + self._get_cli_html())
                    elif i == 3:
                        browser.setHtml(html_style + self._get_security_html())
                    elif i == 4:
                        browser.setHtml(html_style + self._get_shortcuts_html())

    # HTML content methods for re-theming
    def _get_overview_html(self) -> str:
        return """
        <h1>Secure Cartography</h1>
        <p><b>Network Discovery &amp; Security Analysis Platform</b></p>

        <h2>What It Does</h2>
        <p>Secure Cartography automatically discovers your network infrastructure using 
        SNMP, CDP, and LLDP protocols. It builds topology maps showing how devices connect, 
        extracts hardware inventory, and identifies security vulnerabilities through CVE analysis.</p>

        <h2>Key Capabilities</h2>
        <table cellpadding="8">
            <tr>
                <td><b>🔍 Discovery</b></td>
                <td>Recursive network crawling from seed devices using CDP/LLDP neighbor data</td>
            </tr>
            <tr>
                <td><b>🗺️ Topology</b></td>
                <td>Interactive network maps with device relationships and connection details</td>
            </tr>
            <tr>
                <td><b>📦 Inventory</b></td>
                <td>Hardware components, serial numbers, software versions across all discovered devices</td>
            </tr>
            <tr>
                <td><b>🔐 Security</b></td>
                <td>CVE vulnerability analysis by mapping platforms to NIST NVD database</td>
            </tr>
            <tr>
                <td><b>🔑 Credentials</b></td>
                <td>Encrypted vault for SNMP credentials with automatic discovery of working creds</td>
            </tr>
        </table>

        <h2>Typical Workflow</h2>
        <ol>
            <li>Configure SNMP credentials in the vault</li>
            <li>Enter seed IP(s) - core routers or switches that see the network</li>
            <li>Set domain filters to constrain discovery scope</li>
            <li>Run discovery - watch the topology build in real-time</li>
            <li>Open Security Analysis to check for known vulnerabilities</li>
            <li>Export maps and reports for documentation</li>
        </ol>

        <h2>Supported Platforms</h2>
        <p>Secure Cartography works with any SNMP-enabled device. Enhanced parsing for:</p>
        <ul>
            <li>Cisco IOS, IOS-XE, IOS-XR, NX-OS</li>
            <li>Arista EOS</li>
            <li>Juniper JUNOS</li>
            <li>Palo Alto PAN-OS</li>
            <li>Fortinet FortiOS</li>
            <li>Aruba/HPE, Dell, Extreme, MikroTik, Ubiquiti</li>
        </ul>
        """

    def _get_gui_html(self) -> str:
        return """
        <h1>GUI Guide</h1>

        <h2>Main Window Layout</h2>
        <p>The interface is organized into three columns:</p>

        <h3>Left Column - Connection Setup</h3>
        <ul>
            <li><b>Seed IPs:</b> Starting points for discovery (usually core routers/switches)</li>
            <li><b>Domain Filter:</b> Limit discovery to hostnames matching these domains</li>
            <li><b>Exclude Patterns:</b> Skip devices matching these patterns</li>
            <li><b>Credentials:</b> SNMP credentials from your encrypted vault</li>
        </ul>

        <h3>Middle Column - Options &amp; Actions</h3>
        <ul>
            <li><b>Max Depth:</b> How many hops from seed devices to crawl</li>
            <li><b>Concurrency:</b> Parallel device queries (higher = faster, more load)</li>
            <li><b>Timeout:</b> Per-device SNMP timeout in seconds</li>
            <li><b>No DNS:</b> Use raw IPs from CDP/LLDP (useful for lab environments)</li>
            <li><b>Output Directory:</b> Where to save discovery results</li>
        </ul>

        <h3>Right Column - Results</h3>
        <ul>
            <li><b>Progress:</b> Discovery status and statistics</li>
            <li><b>Topology Preview:</b> Real-time network map as devices are discovered</li>
            <li><b>Discovery Log:</b> Detailed event log with timestamps</li>
        </ul>

        <h2>Header Bar</h2>
        <table cellpadding="8">
            <tr>
                <td><b>? HELP</b></td>
                <td>Opens this help dialog</td>
            </tr>
            <tr>
                <td><b>🔐 SECURITY</b></td>
                <td>Opens CVE vulnerability analysis window</td>
            </tr>
            <tr>
                <td><b>Theme Selector</b></td>
                <td>Switch between Cyber, Dark, and Light themes</td>
            </tr>
        </table>

        <h2>Discovery Process</h2>
        <ol>
            <li>Click <b>START CRAWL</b> to begin discovery</li>
            <li>Watch the topology build in the preview panel</li>
            <li>Click <b>STOP CRAWL</b> to halt discovery early if needed</li>
            <li>Use <b>ENHANCE MAP</b> to open the full interactive map viewer</li>
            <li>Results are automatically saved to the output directory</li>
        </ol>

        <h2>Output Files</h2>
        <p>Discovery creates several files in your output directory:</p>
        <ul>
            <li><code>map.json</code> - Topology data for map viewer</li>
            <li><code>devices.csv</code> - Device inventory spreadsheet</li>
            <li><code>devices.json</code> - Full device data in JSON format</li>
            <li><code>topology.graphml</code> - Network graph for external tools</li>
        </ul>
        """

    def _get_cli_html(self) -> str:
        return """
        <h1>CLI Guide</h1>
        <p>Command-line tools for running discovery from jump hosts, automation scripts, 
        or environments without GUI access.</p>

        <h2>Credential Manager</h2>
        <pre>python -m sc2.scng.creds [command] [options]</pre>

        <h3>Commands</h3>
        <table cellpadding="6" border="0">
            <tr><td><code>init</code></td><td>Initialize a new credential vault</td></tr>
            <tr><td><code>unlock</code></td><td>Validate vault password</td></tr>
            <tr><td><code>add</code></td><td>Add a new SNMP credential</td></tr>
            <tr><td><code>list</code></td><td>List all stored credentials</td></tr>
            <tr><td><code>show</code></td><td>Show credential details</td></tr>
            <tr><td><code>remove</code></td><td>Remove a credential</td></tr>
            <tr><td><code>set-default</code></td><td>Set credential as default</td></tr>
            <tr><td><code>test</code></td><td>Test credential against a device</td></tr>
            <tr><td><code>discover</code></td><td>Discover working credentials for a device</td></tr>
            <tr><td><code>change-password</code></td><td>Change vault master password</td></tr>
            <tr><td><code>deps</code></td><td>Check SNMP dependencies</td></tr>
        </table>

        <h3>Options</h3>
        <pre>
--vault-path, -v    Path to vault database 
                    (default: ~/.scng/credentials.db)
--password, -p      Vault password 
                    (or set SCNG_VAULT_PASSWORD env var)
        </pre>

        <h3>Examples</h3>
        <pre>
# Initialize vault on a jump host
python -m sc2.scng.creds init

# Add SNMPv2 credential
python -m sc2.scng.creds add --name "network-ro" \\
    --version 2c --community "readonlystring"

# Add SNMPv3 credential
python -m sc2.scng.creds add --name "secure-snmp" \\
    --version 3 --user "snmpuser" \\
    --auth-proto SHA --auth-pass "authpass123" \\
    --priv-proto AES --priv-pass "privpass123"

# Test credential against device
python -m sc2.scng.creds test 192.168.1.1 --name "network-ro"
        </pre>

        <hr>

        <h2>Network Discovery</h2>
        <pre>python -m sc2.scng.discovery [command] [options]</pre>

        <h3>Commands</h3>
        <table cellpadding="6" border="0">
            <tr><td><code>test</code></td><td>Quick test with inline community string</td></tr>
            <tr><td><code>device</code></td><td>Discover single device using vault credentials</td></tr>
            <tr><td><code>crawl</code></td><td>Recursive network discovery</td></tr>
        </table>

        <h3>Crawl Options</h3>
        <pre>
-d, --depth         Max hops from seed (default: 3)
--domain            Domain filter (can specify multiple)
--exclude           Exclude pattern (can specify multiple)
-o, --output        Output directory
--concurrency       Parallel queries (default: 10)
--timeout           Per-device timeout seconds (default: 5)
--no-dns            Use raw IPs from CDP/LLDP
-v, --verbose       Verbose output
--timestamps        Show timestamps in output
        </pre>

        <h3>Examples</h3>
        <pre>
# Quick SNMP test with community string
python -m sc2.scng.discovery test 192.168.1.1 --community public

# Single device discovery using vault
python -m sc2.scng.discovery device 192.168.1.1

# Recursive crawl with domain filter
python -m sc2.scng.discovery crawl 192.168.1.1 \\
    -d 3 --domain example.com -o ./output

# Home lab (no DNS, use IPs from LLDP/CDP)
python -m sc2.scng.discovery crawl 192.168.1.1 \\
    -d 3 --no-dns

# Large network with high concurrency
python -m sc2.scng.discovery crawl 10.0.0.1 \\
    -d 5 --concurrency 30 -o ./datacenter

# Verbose with timestamps for debugging
python -m sc2.scng.discovery crawl 192.168.1.1 \\
    -v --timestamps
        </pre>

        <hr>

        <h2>Jump Host Workflow</h2>
        <p>When your desktop doesn't have SNMP access but a jump host does:</p>
        <ol>
            <li>SSH to the jump host</li>
            <li>Install Secure Cartography: <code>pip install .</code></li>
            <li>Initialize vault: <code>python -m sc2.scng.creds init</code></li>
            <li>Add credentials: <code>python -m sc2.scng.creds add ...</code></li>
            <li>Run discovery: <code>python -m sc2.scng.discovery crawl ...</code></li>
            <li>Copy output files back to desktop for analysis</li>
            <li>Open in GUI for map viewing and security analysis</li>
        </ol>

        <h2>Environment Variables</h2>
        <table cellpadding="6" border="0">
            <tr><td><code>SCNG_VAULT_PASSWORD</code></td><td>Vault password (avoids -p flag)</td></tr>
            <tr><td><code>SCNG_VAULT_PATH</code></td><td>Custom vault location</td></tr>
        </table>
        """

    def _get_security_html(self) -> str:
        return """
        <h1>Security Analysis</h1>
        <p>The Security Analysis window maps discovered platforms to known vulnerabilities 
        using the NIST National Vulnerability Database (NVD).</p>

        <h2>Workflow</h2>
        <ol>
            <li><b>Load CSV:</b> Import the <code>devices.csv</code> from a discovery run</li>
            <li><b>Review Mappings:</b> Check auto-detected platform → CPE mappings</li>
            <li><b>Sync Selected:</b> Query NVD for CVEs matching each platform</li>
            <li><b>Analyze Results:</b> Review CVEs sorted by severity</li>
        </ol>

        <h2>Platform Mapping</h2>
        <p>Secure Cartography automatically parses platform strings and maps them to 
        CPE (Common Platform Enumeration) format for NVD queries:</p>
        <pre>
"Cisco IOS 15.2(4.0.55)E" → cpe:2.3:o:cisco:ios:15.2(4.0.55)e:*:*:*:*:*:*:*
"Arista vEOS-lab EOS 4.33.1F" → cpe:2.3:o:arista:eos:4.33.1f:*:*:*:*:*:*:*
        </pre>

        <h3>Confidence Levels</h3>
        <table cellpadding="6" border="0">
            <tr><td><b>High</b></td><td>Platform matched a known pattern, ready to sync</td></tr>
            <tr><td><b>Medium</b></td><td>Partial match, may need manual verification</td></tr>
            <tr><td><b>Low</b></td><td>Unknown format, requires manual CPE entry</td></tr>
        </table>

        <p>Double-click Vendor, Product, or CPE Version columns to edit mappings manually.</p>

        <h2>CVE Results</h2>
        <p>After syncing, view results in three tabs:</p>
        <ul>
            <li><b>Cached Versions:</b> All synced platforms with CVE counts</li>
            <li><b>Summary:</b> Aggregate statistics and severity breakdown</li>
            <li><b>CVEs:</b> Detailed CVE list for selected platform</li>
        </ul>

        <h3>Severity Colors</h3>
        <table cellpadding="6" border="0">
            <tr><td style="background:#dc2626;color:white;padding:4px 12px"><b>CRITICAL</b></td><td>CVSS 9.0-10.0</td></tr>
            <tr><td style="background:#f97316;color:white;padding:4px 12px"><b>HIGH</b></td><td>CVSS 7.0-8.9</td></tr>
            <tr><td style="background:#eab308;color:black;padding:4px 12px"><b>MEDIUM</b></td><td>CVSS 4.0-6.9</td></tr>
            <tr><td style="background:#22c55e;color:white;padding:4px 12px"><b>LOW</b></td><td>CVSS 0.1-3.9</td></tr>
        </table>

        <h2>NVD API</h2>
        <p>By default, queries are rate-limited to 5 requests per 30 seconds. 
        For faster syncing, get a free API key from:</p>
        <p><a href="https://nvd.nist.gov/developers/request-an-api-key">
        https://nvd.nist.gov/developers/request-an-api-key</a></p>
        <p>Enter your API key in the Security Analysis window to increase the rate limit.</p>

        <h2>Cache</h2>
        <p>CVE data is cached locally to avoid repeated API calls:</p>
        <ul>
            <li>Cache location: <code>~/.scng/cve_cache.db</code></li>
            <li>Use <b>View Cache</b> to see previously synced data</li>
            <li>Check <b>Force Re-sync</b> to refresh stale data</li>
        </ul>

        <h2>Custom Patterns</h2>
        <p>Add custom platform parsing patterns via <b>Add Pattern</b> button. 
        Patterns are stored in <code>~/.scng/platform_patterns.json</code></p>
        """

    def _get_shortcuts_html(self) -> str:
        return """
        <h1>Keyboard Shortcuts</h1>

        <h2>Main Window</h2>
        <table cellpadding="8" border="0">
            <tr><td><code>Ctrl+Enter</code></td><td>Start/Stop discovery</td></tr>
            <tr><td><code>Ctrl+M</code></td><td>Open map viewer</td></tr>
            <tr><td><code>Ctrl+Shift+S</code></td><td>Open security analysis</td></tr>
            <tr><td><code>F1</code></td><td>Open help</td></tr>
            <tr><td><code>Ctrl+Q</code></td><td>Quit application</td></tr>
        </table>

        <h2>Map Viewer</h2>
        <table cellpadding="8" border="0">
            <tr><td><code>Ctrl+O</code></td><td>Open map file</td></tr>
            <tr><td><code>Ctrl+S</code></td><td>Save map</td></tr>
            <tr><td><code>Ctrl+E</code></td><td>Export image</td></tr>
            <tr><td><code>Ctrl+F</code></td><td>Find device</td></tr>
            <tr><td><code>+</code> / <code>-</code></td><td>Zoom in/out</td></tr>
            <tr><td><code>0</code></td><td>Reset zoom</td></tr>
            <tr><td><code>F</code></td><td>Fit to window</td></tr>
            <tr><td><code>Escape</code></td><td>Clear selection</td></tr>
        </table>

        <h2>Security Analysis</h2>
        <table cellpadding="8" border="0">
            <tr><td><code>Ctrl+O</code></td><td>Load CSV</td></tr>
            <tr><td><code>Ctrl+A</code></td><td>Select all platforms</td></tr>
            <tr><td><code>Enter</code></td><td>Sync selected</td></tr>
            <tr><td><code>Escape</code></td><td>Stop sync</td></tr>
        </table>

        <h2>Tables</h2>
        <table cellpadding="8" border="0">
            <tr><td><code>Ctrl+C</code></td><td>Copy selected cells</td></tr>
            <tr><td><code>Double-click</code></td><td>Edit cell (where supported)</td></tr>
            <tr><td><code>Click header</code></td><td>Sort by column</td></tr>
        </table>
        """