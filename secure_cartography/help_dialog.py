import traceback
from pathlib import Path

from PyQt6.QtCore import QUrl
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QDialogButtonBox, QVBoxLayout, QDialog


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Network Mapper Help")
        self.setMinimumSize(800, 600)  # Larger size for better readability

        # Create layout
        layout = QVBoxLayout(self)

        # Create WebEngine view
        self.web_view = QWebEngineView()
        self.enable_external_content()
        layout.addWidget(self.web_view)

        # Add standard buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)

        # Load the help content
        self.load_help_content()

    def enable_external_content(self):
        """Configure WebEngineView to load external content."""
        settings = self.web_view.settings()

        # Enable loading external resources
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)

        print("External content and JavaScript enabled.")
    def load_help_content(self):
        """Load the help HTML file."""
        # Define potential file locations
        primary_path = Path(__file__).parent / "resources" / "index.html"
        fallback_path = Path(__file__).parent / "index.html"

        # Determine which file to load
        if primary_path.exists() and primary_path.is_file():
            help_file = primary_path
        elif fallback_path.exists() and fallback_path.is_file():
            help_file = fallback_path
        else:
            help_file = None

        if help_file:
            try:
                # Try to load local file
                url = QUrl.fromLocalFile(str(help_file.resolve()))
                self.web_view.setUrl(url)
                print(f"Loaded help content from: {help_file}")
            except Exception as e:
                print("Failed to load the local help file.")
                traceback.print_exc()
                self.load_fallback_content(e)
        else:
            print("Help file not found in any location. Loading fallback content.")
            self.load_fallback_content("Help file not found.")

    def load_fallback_content(self, error_message):
        """Load fallback HTML content."""
        self.web_view.setHtml(self.get_fallback_content())
        print(f"Error encountered: {error_message}")

    def get_fallback_content(self):
        """Return basic HTML content as a fallback."""
        html_text ='''<!DOCTYPE html>
<html>
<head>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            line-height: 1.6;
            margin: 20px;
        }
        h1, h2 { color: #2c3e50; }
        .section { margin-bottom: 20px; }
        .note { 
            background-color: #f8f9fa;
            padding: 10px;
            border-left: 4px solid #2c3e50;
        }
    </style>
</head>
<body>
    <h1>Network Mapper Help</h1>
    
    <div class="section">
        <h2>Configuration Options</h2>
        <h3>Basic Settings</h3>
        <ul>
            <li><strong>Seed IP:</strong> The starting IP address for network discovery. This is where the mapper will begin exploring your network.</li>
            <li><strong>Username/Password:</strong> Primary credentials used to authenticate with network devices.</li>
            <li><strong>Timeout:</strong> Maximum time (in seconds) to wait for a device to respond before moving on.</li>
            <li><strong>Max Devices:</strong> Upper limit on the number of devices to discover. Use this to control the scope of discovery.</li>
        </ul>
        
        <h3>Output Settings</h3>
        <ul>
            <li><strong>Map Name:</strong> Name for the generated network map file (will be saved as SVG).</li>
            <li><strong>Output Directory:</strong> Location where discovery results and network maps will be saved.</li>
            <li><strong>Exclude Pattern:</strong> Patterns for device names or IPs to skip during discovery.</li>
        </ul>
        
        <h3>Advanced Settings</h3>
        <ul>
            <li><strong>Layout Algorithm:</strong> Choose how the network diagram is arranged:
                <ul>
                    <li>kk: Kamada-Kawai algorithm (best for general use)</li>
                    <li>rt: Reingold-Tilford tree layout</li>
                    <li>circular: Devices arranged in a circle</li>
                    <li>multipartite: Layered network layout</li>
                </ul>
            </li>
        </ul>
    </div>

    <div class="section">
        <h2>Controls</h2>
        <ul>
            <li><strong>Start:</strong> Begin the network discovery process using current settings</li>
            <li><strong>Cancel:</strong> Stop the ongoing discovery process</li>
            <li><strong>Log:</strong> Toggle the log window visibility</li>
            <li><strong>Help:</strong> Display this help information</li>
        </ul>
    </div>

    <div class="section">
        <h2>Discovery Process</h2>
        <p>The discovery process works as follows:</p>
        <ol>
            <li>Starts with the seed IP address</li>
            <li>Attempts to connect using provided credentials</li>
            <li>If successful, gathers device information and neighbor data</li>
            <li>Adds discovered neighbors to the queue</li>
            <li>Continues until all reachable devices are mapped or limits are reached</li>
        </ol>
    </div>

    <div class="section">
        <h2>Progress Monitoring</h2>
        <ul>
            <li><strong>Progress Bar:</strong> Shows overall discovery progress</li>
            <li><strong>Device List:</strong> Real-time list of discovered devices
                <ul>
                    <li>Green: Successfully processed devices</li>
                    <li>Red: Failed connection attempts</li>
                    <li>Blue: Currently processing</li>
                </ul>
            </li>
            <li><strong>Statistics:</strong> Running counts of discovered, failed, and queued devices</li>
        </ul>
    </div>

    <div class="section note">
        <h3>Important Notes</h3>
        <ul>
            <li>Ensure you have appropriate permissions before starting discovery</li>
            <li>Large networks may take significant time to map</li>
            <li>Use exclude patterns to skip known non-network devices</li>
            <li>The generated map is saved as an SVG file for easy viewing and editing</li>
        </ul>
    </div>
</body>
</html>'''
        return html_text