"""
SecureCartography v2 - Main Window

Main application window with:
- Three-column layout
- Vault integration
- Login flow wiring
"""
from threading import settrace
from typing import Optional
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QSizePolicy, QSpacerItem,
    QSplitter
)
from PyQt6.QtGui import QFont

from .settings import SettingsManager, get_settings
from .themes import ThemeManager, ThemeName, ThemeColors, StyledComboBox
from .widgets import (
    ConnectionPanel,
    DiscoveryOptionsPanel,
    OutputPanel,
    ProgressPanel,
    TopologyPreviewPanel,
    DiscoveryLogPanel,
    Panel,
)
from .widgets.credentials_panel import CredentialsPanel
from .widgets.map_viewer_dialog import MapViewerDialog
from .widgets.security_widget import SecurityWidget
from .help_dialog import HelpDialog
from ..scng.discovery.discovery_controller import DiscoveryController


class HeaderBar(QFrame):
    """
    Application header bar with title, help button, and theme selector.

    ┌─────────────────────────────────────────────────────────────────┐
    │ 🔗 SECURE CARTOGRAPHY                        [? Help] [Theme ▼] │
    └─────────────────────────────────────────────────────────────────┘
    """

    help_clicked = pyqtSignal()
    security_clicked = pyqtSignal()
    theme_changed = pyqtSignal(ThemeName)

    def __init__(
        self,
        theme_manager: ThemeManager,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._setup_ui()
        self.apply_theme(theme_manager.theme)

    def _setup_ui(self):
        """Build the header bar UI."""
        self.setObjectName("headerBar")
        self.setFixedHeight(56)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(16)

        # Logo/Icon
        self.logo_label = QLabel("🔗")
        self.logo_label.setObjectName("headerLogo")
        font = self.logo_label.font()
        font.setPointSize(18)
        self.logo_label.setFont(font)
        layout.addWidget(self.logo_label)

        # Title
        self.title_label = QLabel("SECURE CARTOGRAPHY")
        self.title_label.setObjectName("headerTitle")
        font = self.title_label.font()
        font.setPointSize(14)
        font.setWeight(QFont.Weight.Bold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
        self.title_label.setFont(font)
        layout.addWidget(self.title_label)

        layout.addStretch()

        # Help button
        self.help_btn = QPushButton("? HELP")
        self.help_btn.setObjectName("helpButton")
        self.help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.help_btn.clicked.connect(self.help_clicked.emit)
        layout.addWidget(self.help_btn)

        # Security analysis button
        self.security_btn = QPushButton("🔐 SECURITY")
        self.security_btn.setObjectName("securityButton")
        self.security_btn.setToolTip("CVE Vulnerability Analysis")
        self.security_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.security_btn.clicked.connect(self.security_clicked.emit)
        layout.addWidget(self.security_btn)

        # Theme selector
        self.theme_combo = StyledComboBox()
        self.theme_combo.setObjectName("headerThemeCombo")
        self.theme_combo.setFixedWidth(130)
        self.theme_combo.addItem("⚡ Cyber", ThemeName.CYBER)
        self.theme_combo.addItem("🌙 Dark", ThemeName.DARK)
        self.theme_combo.addItem("☀️ Light", ThemeName.LIGHT)

        # Set current theme
        for i in range(self.theme_combo.count()):
            if self.theme_combo.itemData(i) == self.theme_manager.theme_name:
                self.theme_combo.setCurrentIndex(i)
                break

        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        layout.addWidget(self.theme_combo)

    def _on_theme_changed(self, index: int):
        """Handle theme selection change."""
        theme_name = self.theme_combo.itemData(index)
        if theme_name:
            self.theme_changed.emit(theme_name)

    def apply_theme(self, theme: ThemeColors):
        """Apply theme colors to header."""
        self.theme_combo.set_theme_colors(theme)

        self.setStyleSheet(f"""
            QFrame#headerBar {{
                background-color: {theme.bg_secondary};
                border: none;
                border-bottom: 1px solid {theme.border_dim};
            }}
            
            QLabel#headerLogo {{
                color: {theme.accent};
                background: transparent;
                border: none;
            }}
            
            QLabel#headerTitle {{
                color: {theme.text_primary};
                background: transparent;
                border: none;
            }}
            
            QPushButton#helpButton {{
                background-color: transparent;
                border: 1px solid {theme.border_dim};
                border-radius: 6px;
                padding: 8px 16px;
                color: {theme.text_secondary};
                font-weight: 500;
            }}
            
            QPushButton#helpButton:hover {{
                border-color: {theme.accent};
                color: {theme.accent};
            }}
            
            QPushButton#securityButton {{
                background-color: transparent;
                border: 1px solid {theme.border_dim};
                border-radius: 6px;
                padding: 8px 16px;
                color: {theme.text_secondary};
                font-weight: 500;
            }}
            
            QPushButton#securityButton:hover {{
                border-color: {theme.accent_danger};
                color: {theme.accent_danger};
            }}
            
            QComboBox#headerThemeCombo {{
                background-color: {theme.bg_tertiary};
                border: 1px solid {theme.border_dim};
                border-radius: 6px;
                padding: 8px 12px;
                color: {theme.text_primary};
            }}
            
            QComboBox#headerThemeCombo:hover {{
                border-color: {theme.accent};
            }}
            
            QComboBox#headerThemeCombo::drop-down {{
                border: none;
                width: 20px;
            }}
            
            QComboBox#headerThemeCombo::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid {theme.text_secondary};
            }}
        """)


class ActionButtonsPanel(Panel):
    """
    Panel containing the main action buttons:
    - Start Crawl (primary)
    - Test Single
    - Enhance Map
    """

    start_crawl_clicked = pyqtSignal()
    test_single_clicked = pyqtSignal()
    enhance_map_clicked = pyqtSignal()

    def __init__(
        self,
        theme_manager: Optional[ThemeManager] = None,
        parent: Optional[QWidget] = None
    ):
        self._is_running = False
        super().__init__(
            title="",  # No title for action panel
            icon="",
            theme_manager=theme_manager,
            parent=parent,
            _defer_theme=True
        )
        self._setup_content()
        if theme_manager:
            self.apply_theme(theme_manager.theme)

    def apply_theme(self, theme: ThemeColors):
        """Override to ensure content theme is applied on theme change."""
        super().apply_theme(theme)
        self._apply_content_theme(theme)

    def _setup_content(self):
        """Build button layout."""
        # Remove title bar for this panel
        self.title_bar.hide()

        # Primary action button
        self.start_btn = QPushButton("▶  START CRAWL")
        self.start_btn.setObjectName("primaryButton")
        self.start_btn.setFixedHeight(48)
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.clicked.connect(self.start_crawl_clicked.emit)
        self.content_layout.addWidget(self.start_btn)

        # Secondary buttons row
        secondary_layout = QHBoxLayout()
        secondary_layout.setSpacing(12)

        self.test_btn = QPushButton("◉  TEST SINGLE")
        self.test_btn.setObjectName("secondaryButton")
        self.test_btn.setFixedHeight(40)
        self.test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.test_btn.clicked.connect(self.test_single_clicked.emit)
        secondary_layout.addWidget(self.test_btn)

        self.enhance_btn = QPushButton("🗺  ENHANCE MAP")
        self.enhance_btn.setObjectName("secondaryButton")
        self.enhance_btn.setFixedHeight(40)
        self.enhance_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.enhance_btn.clicked.connect(self.enhance_map_clicked.emit)
        secondary_layout.addWidget(self.enhance_btn)

        self.content_layout.addLayout(secondary_layout)

    def set_running(self, running: bool):
        """Toggle between running/stopped state."""
        self._is_running = running
        if running:
            self.start_btn.setText("⏹  STOP CRAWL")
            self.start_btn.setObjectName("stopButton")
        else:
            self.start_btn.setText("▶  START CRAWL")
            self.start_btn.setObjectName("primaryButton")
        self._apply_content_theme(self.theme_manager.theme if self.theme_manager else None)

    def _apply_content_theme(self, theme: ThemeColors):
        """Apply theme to buttons."""
        if not theme:
            return

        button_text = theme.bg_primary if theme.is_dark else "#ffffff"

        if self._is_running:
            # Stop button styling
            self.start_btn.setStyleSheet(f"""
                QPushButton#stopButton {{
                    background-color: {theme.accent_danger};
                    border: none;
                    border-radius: 8px;
                    color: white;
                    font-weight: 600;
                    font-size: 14px;
                }}
                QPushButton#stopButton:hover {{
                    background-color: #dc2626;
                }}
            """)
        else:
            # Start button styling
            self.start_btn.setStyleSheet(f"""
                QPushButton#primaryButton {{
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:0,
                        stop:0 {theme.accent_dim},
                        stop:1 {theme.accent}
                    );
                    border: none;
                    border-radius: 8px;
                    color: {button_text};
                    font-weight: 600;
                    font-size: 14px;
                }}
                QPushButton#primaryButton:hover {{
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:0,
                        stop:0 {theme.accent},
                        stop:1 {theme.accent_dim}
                    );
                }}
            """)

        # Secondary buttons
        self.test_btn.setStyleSheet(f"""
            QPushButton#secondaryButton {{
                background-color: transparent;
                border: 1px solid {theme.border_dim};
                border-radius: 6px;
                color: {theme.text_secondary};
                font-weight: 500;
            }}
            QPushButton#secondaryButton:hover {{
                border-color: {theme.accent};
                color: {theme.accent};
            }}
        """)
        self.enhance_btn.setStyleSheet(f"""
            QPushButton#secondaryButton {{
                background-color: transparent;
                border: 1px solid {theme.border_dim};
                border-radius: 6px;
                color: {theme.text_secondary};
                font-weight: 500;
            }}
            QPushButton#secondaryButton:hover {{
                border-color: {theme.accent};
                color: {theme.accent};
            }}
        """)


class MainWindow(QMainWindow):
    """
    Main application window.

    Receives an unlocked vault from LoginDialog and provides
    full credential management and discovery functionality.
    """

    def __init__(
        self,
        vault=None,
        theme_name: ThemeName = ThemeName.CYBER,
        settings: Optional[SettingsManager] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.vault = vault
        self.theme_manager = ThemeManager(theme_name)
        self.settings = settings or get_settings()

        self.setWindowTitle("Secure Cartography")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)

        # Initialize window references before _apply_theme
        self._security_window = None
        self._map_viewer_dialog = None
        self._help_dialog = None

        self._setup_ui()
        self._connect_signals()
        self._apply_theme()
        self.discovery_controller = DiscoveryController(self)

    def set_vault(self, vault):
        """Set the vault after login."""
        self.vault = vault
        # Update credentials panel with vault
        if hasattr(self, 'credentials_panel'):
            self.credentials_panel.set_vault(vault)

    def _setup_ui(self):
        """Build the main window UI."""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header bar
        self.header = HeaderBar(theme_manager=self.theme_manager)
        main_layout.addWidget(self.header)

        # Main content area with splitter
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setObjectName("mainSplitter")
        self.splitter.setHandleWidth(6)
        self.splitter.setChildrenCollapsible(False)

        # === Left Column (Connection + Credentials) ===
        left_scroll = QScrollArea()
        left_scroll.setObjectName("leftScrollArea")
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        left_content = QWidget()
        left_content.setObjectName("leftContent")
        left_col = QVBoxLayout(left_content)
        left_col.setContentsMargins(16, 16, 8, 16)
        left_col.setSpacing(16)

        self.connection_panel = ConnectionPanel(theme_manager=self.theme_manager)
        left_col.addWidget(self.connection_panel)

        self.credentials_panel = CredentialsPanel(
            vault=self.vault,
            theme_manager=self.theme_manager
        )
        left_col.addWidget(self.credentials_panel)

        left_col.addStretch()
        left_scroll.setWidget(left_content)
        self.splitter.addWidget(left_scroll)

        # === Middle Column (Options + Output + Actions) ===
        middle_scroll = QScrollArea()
        middle_scroll.setObjectName("middleScrollArea")
        middle_scroll.setWidgetResizable(True)
        middle_scroll.setFrameShape(QFrame.Shape.NoFrame)
        middle_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        middle_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        middle_content = QWidget()
        middle_content.setObjectName("middleContent")
        middle_col = QVBoxLayout(middle_content)
        middle_col.setContentsMargins(8, 16, 8, 16)
        middle_col.setSpacing(16)

        self.options_panel = DiscoveryOptionsPanel(theme_manager=self.theme_manager)
        middle_col.addWidget(self.options_panel)

        self.output_panel = OutputPanel(theme_manager=self.theme_manager)
        middle_col.addWidget(self.output_panel)

        self.action_buttons = ActionButtonsPanel(theme_manager=self.theme_manager)
        middle_col.addWidget(self.action_buttons)

        middle_col.addStretch()
        middle_scroll.setWidget(middle_content)
        self.splitter.addWidget(middle_scroll)

        # === Right Column (Progress + Preview + Log) ===
        right_scroll = QScrollArea()
        right_scroll.setObjectName("rightScrollArea")
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        right_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        right_content = QWidget()
        right_content.setObjectName("rightContent")
        right_col = QVBoxLayout(right_content)
        right_col.setContentsMargins(8, 16, 16, 16)
        right_col.setSpacing(16)

        self.progress_panel = ProgressPanel(theme_manager=self.theme_manager)
        self.progress_panel.set_idle()
        right_col.addWidget(self.progress_panel)

        self.preview_panel = TopologyPreviewPanel(theme_manager=self.theme_manager)
        right_col.addWidget(self.preview_panel)

        self.log_panel = DiscoveryLogPanel(theme_manager=self.theme_manager)
        right_col.addWidget(self.log_panel)

        right_scroll.setWidget(right_content)
        self.splitter.addWidget(right_scroll)

        # Set initial splitter sizes (proportional: 30%, 35%, 35%)
        self.splitter.setSizes([350, 400, 450])

        # Set minimum widths for each section
        left_scroll.setMinimumWidth(280)
        middle_scroll.setMinimumWidth(300)
        right_scroll.setMinimumWidth(350)

        main_layout.addWidget(self.splitter, 1)

    def _connect_signals(self):
        """Connect widget signals."""
        # Theme switching
        self.header.theme_changed.connect(self._on_theme_changed)

        # Help button
        self.header.help_clicked.connect(self._on_help_clicked)

        # Security analysis button
        self.header.security_clicked.connect(self._on_security_clicked)

        # Action buttons
        self.action_buttons.start_crawl_clicked.connect(self._on_start_crawl)
        self.action_buttons.test_single_clicked.connect(self._on_test_single)
        self.action_buttons.enhance_map_clicked.connect(self._on_enhance_map)

        # Preview panel expand button
        self.preview_panel.open_full_viewer.connect(self._on_enhance_map)

        # Credentials changes
        self.credentials_panel.credentials_changed.connect(self._on_credentials_changed)

    def _on_theme_changed(self, theme_name: ThemeName):
        """Handle theme change from header."""
        self.theme_manager.set_theme(theme_name)
        self.settings.set_theme(theme_name)
        self._apply_theme()

    def _apply_theme(self):
        """Apply current theme to all widgets."""
        theme = self.theme_manager.theme

        # Main window and splitter styling
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {theme.bg_primary};
            }}
            
            QSplitter#mainSplitter {{
                background-color: {theme.bg_primary};
            }}
            
            QSplitter#mainSplitter::handle {{
                background-color: {theme.border_dim};
            }}
            
            QSplitter#mainSplitter::handle:hover {{
                background-color: {theme.accent};
            }}
            
            QScrollArea {{
                background-color: {theme.bg_primary};
                border: none;
            }}
            
            QWidget#leftContent,
            QWidget#middleContent,
            QWidget#rightContent {{
                background-color: {theme.bg_primary};
            }}
            
            /* Scrollbar styling */
            QScrollBar:vertical {{
                background-color: {theme.bg_primary};
                width: 10px;
                margin: 0;
            }}
            
            QScrollBar::handle:vertical {{
                background-color: {theme.scrollbar_handle};
                border-radius: 5px;
                min-height: 20px;
            }}
            
            QScrollBar::handle:vertical:hover {{
                background-color: {theme.scrollbar_hover};
            }}
            
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {{
                background: none;
            }}
            
            QScrollBar:horizontal {{
                background-color: {theme.bg_primary};
                height: 10px;
                margin: 0;
            }}
            
            QScrollBar::handle:horizontal {{
                background-color: {theme.scrollbar_handle};
                border-radius: 5px;
                min-width: 20px;
            }}
            
            QScrollBar::handle:horizontal:hover {{
                background-color: {theme.scrollbar_hover};
            }}
            
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
        """)

        # Update all panels
        self.header.apply_theme(theme)
        self.connection_panel.apply_theme(theme)
        self.credentials_panel.apply_theme(theme)
        self.options_panel.apply_theme(theme)
        self.output_panel.apply_theme(theme)
        self.action_buttons.apply_theme(theme)
        self.progress_panel.apply_theme(theme)
        self.preview_panel.apply_theme(theme)
        self.log_panel.apply_theme(theme)

        # Sync security window if open
        if self._security_window and self._security_window.isVisible():
            self._security_window.apply_theme(theme)

        # Sync map viewer if open
        if self._map_viewer_dialog and self._map_viewer_dialog.isVisible():
            self._map_viewer_dialog.apply_theme(theme)

        # Sync help dialog if open
        if self._help_dialog and self._help_dialog.isVisible():
            self._help_dialog.apply_theme(theme)

    # === Action Handlers ===

    def _on_help_clicked(self):
        """Handle help button click."""
        if self._help_dialog is None:
            self._help_dialog = HelpDialog(
                theme_manager=self.theme_manager,
                parent=self
            )

        # Ensure theme is current
        self._help_dialog.apply_theme(self.theme_manager.theme)
        self._help_dialog.show()
        self._help_dialog.raise_()
        self._help_dialog.activateWindow()

    def _on_security_clicked(self):
        """Launch security analysis window."""
        if self._security_window is None or not self._security_window.isVisible():
            self._security_window = SecurityWidget(
                theme_manager=self.theme_manager,
                parent=None  # Independent window
            )
            self._security_window.setWindowTitle("Secure Cartography - Security Analysis")
            self._security_window.resize(1200, 800)
            self._security_window.show()
            self.log_panel.info("Security Analysis window opened")
        else:
            self._security_window.raise_()
            self._security_window.activateWindow()

    def _on_credentials_changed(self):
        """Handle credentials being added/removed/modified."""
        count = len(self.credentials_panel._credentials)
        self.log_panel.info(f"Credentials updated ({count} total)")

    def _on_start_crawl(self):
        """Handle start/stop crawl button click."""
        # If running, stop it
        if self.discovery_controller.is_running:
            self.discovery_controller.cancel()
            return

        # Get configuration from panels
        seeds = self.connection_panel.seeds
        domains = self.connection_panel.domains
        excludes = self.connection_panel.exclude_patterns

        depth = self.options_panel.max_depth
        concurrency = self.options_panel.concurrency
        timeout = self.options_panel.timeout
        no_dns = self.options_panel.no_dns
        verbose = self.options_panel.verbose

        output_dir = self.output_panel.output_directory

        if not seeds:
            self.log_panel.error("No seed IPs configured")
            return

        # Check for credentials
        cred_count = len(self.credentials_panel._credentials)
        if cred_count == 0:
            self.log_panel.warning("No credentials configured - discovery may fail")

        # Start discovery (controller handles UI state updates via events)
        self.discovery_controller.start_crawl(
            seeds=seeds,
            max_depth=depth,
            domains=domains,
            exclude_patterns=excludes,
            output_dir=output_dir,
            concurrency=concurrency,
            timeout=timeout,
            no_dns=no_dns,
            verbose=verbose,
        )

    def _on_test_single(self):
        """Handle test single button click."""
        seeds = self.connection_panel.seeds
        if not seeds:
            self.log_panel.error("No seed IP to test")
            return

        self.log_panel.info(f"Testing connectivity to {seeds[0]}...")
        # TODO: Run single device test

    def _on_enhance_map(self):
        """Handle map viewer button click."""
        from pathlib import Path

        if self._map_viewer_dialog is None:
            self._map_viewer_dialog = MapViewerDialog(
                theme_manager=self.theme_manager,
                parent=self
            )

        self._map_viewer_dialog.show()
        self._map_viewer_dialog.raise_()
        self._map_viewer_dialog.activateWindow()

        # Load from preview panel data directly
        topology_data = self.preview_panel.get_topology_data()

        if topology_data:
            self._map_viewer_dialog.load_topology(topology_data, name="Discovery Map")
            self.log_panel.info(f"Map Viewer opened with {len(topology_data)} devices")
        else:
            # Fallback to file if no data in preview
            output_dir = self.output_panel.output_directory
            if output_dir:
                map_file = Path(output_dir) / "map.json"
                if map_file.exists():
                    self._map_viewer_dialog.open_file(str(map_file))
                    self.log_panel.info(f"Map Viewer loaded: {map_file.name}")
                    return
            self.log_panel.info("Map Viewer opened (no topology loaded)")