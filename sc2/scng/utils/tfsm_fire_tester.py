#!/usr/bin/env python3
"""
TextFSM Template Tester - Enhanced Edition
Debug tool for testing template matching, manual parsing, and template management

Features:
- Database-driven template testing with auto-scoring
- Manual TextFSM template testing (no database required)
- Full CRUD interface for tfsm_templates.db
- Light/Dark/Cyber theme support

Author: Scott Peterman
License: MIT
"""

import sys
import json
import sqlite3
import hashlib
import traceback
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QLabel, QSplitter, QTableWidget,
    QTableWidgetItem, QTabWidget, QGroupBox, QSpinBox, QCheckBox,
    QFileDialog, QMessageBox, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QHeaderView, QAbstractItemView, QMenu, QInputDialog,
    QStatusBar, QToolBar, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QAction, QIcon, QColor, QPalette, QShortcut, QKeySequence

import textfsm
import io
from collections import defaultdict


def get_package_db_path() -> Path:
    """Database is in same directory as this module."""
    return Path(__file__).parent / "tfsm_templates.db"


def find_database(db_path: Optional[str] = None) -> Optional[Path]:
    """Find database - explicit path first, then package location."""
    def is_valid_db(path: Path) -> bool:
        return path.exists() and path.is_file() and path.stat().st_size > 0

    if db_path:
        p = Path(db_path)
        return p if is_valid_db(p) else None

    package_db = get_package_db_path()
    return package_db if is_valid_db(package_db) else None


# Try to import requests for NTC GitHub download
REQUESTS_AVAILABLE = False
try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    pass

# Try to import the engine, but don't fail if not available (manual mode still works)
TFSM_ENGINE_AVAILABLE = False
try:
    from sc2.scng.utils.tfsm_fire import TextFSMAutoEngine

    TFSM_ENGINE_AVAILABLE = True
except ImportError:
    try:
        # Relative import (alternative for package context)
        from .tfsm_fire import TextFSMAutoEngine

        TFSM_ENGINE_AVAILABLE = True
    except ImportError:
        try:
            # Standalone mode - direct import
            from sc2.scng.utils import TextFSMAutoEngine

            TFSM_ENGINE_AVAILABLE = True
        except ImportError:
            try:
                # Fallback to secure_cartography
                from secure_cartography.tfsm_fire import TextFSMAutoEngine

                TFSM_ENGINE_AVAILABLE = True
            except ImportError:
                pass

# =============================================================================
# NTC TEMPLATES GITHUB DOWNLOAD
# =============================================================================

GITHUB_API_URL = "https://api.github.com/repos/networktocode/ntc-templates/contents/ntc_templates/templates"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/networktocode/ntc-templates/master/ntc_templates/templates"

VENDOR_PREFIXES = [
    'cisco', 'arista', 'juniper', 'hp', 'dell', 'paloalto', 'fortinet',
    'brocade', 'extreme', 'huawei', 'mikrotik', 'ubiquiti', 'vmware',
    'checkpoint', 'alcatel', 'avaya', 'ruckus', 'f5', 'a10', 'linux',
    'yamaha', 'zyxel', 'enterasys', 'adtran', 'ciena', 'nokia', 'watchguard'
]


def extract_platform(filename: str) -> str:
    """Extract platform name from template filename."""
    name = filename.replace('.textfsm', '')
    parts = name.split('_')
    if len(parts) >= 2 and parts[0] in VENDOR_PREFIXES:
        return f"{parts[0]}_{parts[1]}"
    if parts[0] in VENDOR_PREFIXES:
        return parts[0]
    return parts[0]


class NTCDownloadWorker(QThread):
    """Worker thread for downloading NTC templates"""
    progress = pyqtSignal(int, int, str)  # current, total, status
    finished = pyqtSignal(dict)  # stats dict
    error = pyqtSignal(str)

    def __init__(self, platforms: list, db_path: str, replace: bool = False):
        super().__init__()
        self.platforms = platforms
        self.db_path = db_path
        self.db_path = db_path or str(get_package_db_path())
        self.replace = replace
        self.templates_to_download = []


    def run(self):
        try:
            # Fetch template list
            response = requests.get(GITHUB_API_URL, timeout=30)
            response.raise_for_status()

            files = response.json()
            all_templates = [f for f in files if f['name'].endswith('.textfsm')]

            # Group by platform
            platforms_map = defaultdict(list)
            for t in all_templates:
                platform = extract_platform(t['name'])
                platforms_map[platform].append(t)

            # Filter to selected platforms
            for platform in self.platforms:
                if platform in platforms_map:
                    self.templates_to_download.extend(platforms_map[platform])

            if not self.templates_to_download:
                self.finished.emit({'imported': 0, 'updated': 0, 'skipped': 0, 'errors': 0})
                return

            # Connect to database
            conn = sqlite3.connect(self.db_path)
            print(f"db_path: {self.db_path}")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cli_command TEXT UNIQUE,
                    cli_content TEXT,
                    textfsm_content TEXT,
                    textfsm_hash TEXT,
                    source TEXT,
                    created TEXT
                )
            """)
            cursor = conn.cursor()

            stats = {'imported': 0, 'updated': 0, 'skipped': 0, 'errors': 0}
            total = len(self.templates_to_download)

            for i, template in enumerate(self.templates_to_download, 1):
                name = template['name']
                cli_command = name.replace('.textfsm', '')

                try:
                    # Download content
                    url = f"{GITHUB_RAW_BASE}/{name}"
                    resp = requests.get(url, timeout=30)
                    resp.raise_for_status()
                    content = resp.text

                    textfsm_hash = hashlib.md5(content.encode()).hexdigest()
                    created = datetime.now().isoformat()

                    # Check if exists
                    cursor.execute("SELECT textfsm_hash FROM templates WHERE cli_command = ?", (cli_command,))
                    existing = cursor.fetchone()

                    if existing:
                        if self.replace and existing[0] != textfsm_hash:
                            cursor.execute("""
                                UPDATE templates 
                                SET textfsm_content = ?, textfsm_hash = ?, source = ?, created = ?
                                WHERE cli_command = ?
                            """, (content, textfsm_hash, "ntc-templates", created, cli_command))
                            stats['updated'] += 1
                            status = "U"
                        else:
                            stats['skipped'] += 1
                            status = "."
                    else:
                        cursor.execute("""
                            INSERT INTO templates (cli_command, cli_content, textfsm_content, textfsm_hash, source, created)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (cli_command, "", content, textfsm_hash, "ntc-templates", created))
                        stats['imported'] += 1
                        status = "+"

                    self.progress.emit(i, total, f"{status} {cli_command}")

                except Exception as e:
                    traceback.print_exc()

                    stats['errors'] += 1
                    self.progress.emit(i, total, f"E {cli_command}: {str(e)[:30]}")

            conn.commit()
            conn.close()
            self.finished.emit(stats)

        except Exception as e:
            traceback.print_exc()

            self.error.emit(str(e))


class NTCDownloadDialog(QDialog):
    """Dialog for selecting and downloading NTC templates from GitHub"""

    def __init__(self, parent=None, db_path: str = "tfsm_templates.db"):
        super().__init__(parent)
        self.db_path = db_path
        self.platforms = {}
        self.setWindowTitle("Download NTC Templates from GitHub")
        self.setMinimumSize(600, 500)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Info label
        info = QLabel("Download TextFSM templates directly from networktocode/ntc-templates GitHub repository.")
        info.setWordWrap(True)
        layout.addWidget(info)

        # Fetch button
        fetch_layout = QHBoxLayout()
        self.fetch_btn = QPushButton("Fetch Available Platforms")
        self.fetch_btn.clicked.connect(self.fetch_platforms)
        fetch_layout.addWidget(self.fetch_btn)
        fetch_layout.addStretch()
        layout.addLayout(fetch_layout)

        # Platform list
        list_group = QGroupBox("Available Platforms")
        list_layout = QVBoxLayout(list_group)

        # Select all / none buttons
        select_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.setProperty("secondary", True)
        select_all_btn.clicked.connect(self.select_all)
        select_layout.addWidget(select_all_btn)

        select_none_btn = QPushButton("Select None")
        select_none_btn.setProperty("secondary", True)
        select_none_btn.clicked.connect(self.select_none)
        select_layout.addWidget(select_none_btn)

        select_layout.addStretch()

        self.status_label = QLabel("")
        select_layout.addWidget(self.status_label)
        list_layout.addLayout(select_layout)

        # Platform table with checkboxes
        self.platform_table = QTableWidget()
        self.platform_table.setColumnCount(3)
        self.platform_table.setHorizontalHeaderLabels(["Select", "Platform", "Templates"])
        self.platform_table.horizontalHeader().setStretchLastSection(True)
        self.platform_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.platform_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        list_layout.addWidget(self.platform_table)

        layout.addWidget(list_group)

        # Options
        options_layout = QHBoxLayout()
        self.replace_check = QCheckBox("Replace existing templates if content changed")
        options_layout.addWidget(self.replace_check)
        options_layout.addStretch()
        layout.addLayout(options_layout)

        # Progress
        self.progress_label = QLabel("")
        layout.addWidget(self.progress_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.download_btn = QPushButton("Download Selected")
        self.download_btn.clicked.connect(self.start_download)
        self.download_btn.setEnabled(False)
        btn_layout.addWidget(self.download_btn)

        close_btn = QPushButton("Close")
        close_btn.setProperty("secondary", True)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def fetch_platforms(self):
        """Fetch available platforms from GitHub"""
        if not REQUESTS_AVAILABLE:
            QMessageBox.critical(self, "Error", "requests library not available.\nInstall with: pip install requests")
            return

        self.fetch_btn.setEnabled(False)
        self.status_label.setText("Fetching from GitHub...")
        QApplication.processEvents()

        try:
            response = requests.get(GITHUB_API_URL, timeout=30)
            response.raise_for_status()

            files = response.json()
            templates = [f for f in files if f['name'].endswith('.textfsm')]

            # Group by platform
            self.platforms = defaultdict(list)
            for t in templates:
                platform = extract_platform(t['name'])
                self.platforms[platform].append(t)

            # Populate table
            self.platform_table.setRowCount(len(self.platforms))
            for row, (platform, tmpl_list) in enumerate(sorted(self.platforms.items(), key=lambda x: -len(x[1]))):
                # Checkbox
                checkbox = QCheckBox()
                self.platform_table.setCellWidget(row, 0, checkbox)

                # Platform name
                self.platform_table.setItem(row, 1, QTableWidgetItem(platform))

                # Template count
                self.platform_table.setItem(row, 2, QTableWidgetItem(str(len(tmpl_list))))

            self.status_label.setText(f"Found {len(templates)} templates across {len(self.platforms)} platforms")
            self.download_btn.setEnabled(True)

        except Exception as e:
            traceback.print_exc()

            QMessageBox.critical(self, "Error", f"Failed to fetch platforms:\n{str(e)}")
            self.status_label.setText("Fetch failed")

        self.fetch_btn.setEnabled(True)

    def select_all(self):
        for row in range(self.platform_table.rowCount()):
            checkbox = self.platform_table.cellWidget(row, 0)
            if checkbox:
                checkbox.setChecked(True)

    def select_none(self):
        for row in range(self.platform_table.rowCount()):
            checkbox = self.platform_table.cellWidget(row, 0)
            if checkbox:
                checkbox.setChecked(False)

    def get_selected_platforms(self) -> list:
        selected = []
        for row in range(self.platform_table.rowCount()):
            checkbox = self.platform_table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                item = self.platform_table.item(row, 1)
                if item:
                    selected.append(item.text())
        return selected

    def start_download(self):
        selected = self.get_selected_platforms()
        if not selected:
            QMessageBox.warning(self, "Warning", "Please select at least one platform")
            return

        self.download_btn.setEnabled(False)
        self.fetch_btn.setEnabled(False)
        self.progress_label.setText("Starting download...")

        self.worker = NTCDownloadWorker(selected, self.db_path, self.replace_check.isChecked())
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.download_finished)
        self.worker.error.connect(self.download_error)
        self.worker.start()

    def update_progress(self, current: int, total: int, status: str):
        self.progress_label.setText(f"[{current}/{total}] {status}")

    def download_finished(self, stats: dict):
        self.download_btn.setEnabled(True)
        self.fetch_btn.setEnabled(True)

        msg = f"Download Complete!\n\nImported: {stats['imported']}\nUpdated: {stats['updated']}\nSkipped: {stats['skipped']}\nErrors: {stats['errors']}"
        self.progress_label.setText(
            f"Done: {stats['imported']} imported, {stats['updated']} updated, {stats['skipped']} skipped")
        QMessageBox.information(self, "Download Complete", msg)

    def download_error(self, error: str):
        self.download_btn.setEnabled(True)
        self.fetch_btn.setEnabled(True)
        self.progress_label.setText("Download failed")
        QMessageBox.critical(self, "Error", f"Download failed:\n{error}")


# =============================================================================
# THEME DEFINITIONS
# =============================================================================

THEMES = {
    "light": {
        "name": "Light",
        "window_bg": "#FAFAFA",
        "surface_bg": "#FFFFFF",
        "surface_alt": "#F5F5F5",
        "primary": "#6D4C41",
        "primary_hover": "#5D4037",
        "primary_text": "#FFFFFF",
        "text": "#212121",
        "text_secondary": "#757575",
        "border": "#E0E0E0",
        "input_bg": "#FFFFFF",
        "input_border": "#BDBDBD",
        "input_focus": "#6D4C41",
        "success": "#4CAF50",
        "warning": "#FF9800",
        "error": "#F44336",
        "table_header": "#EFEBE9",
        "table_alt_row": "#FAFAFA",
        "selection": "#D7CCC8",
        "scrollbar_bg": "#F5F5F5",
        "scrollbar_handle": "#BDBDBD",
        "code_bg": "#F5F5F5",
    },
    "dark": {
        "name": "Dark",
        "window_bg": "#1E1E1E",
        "surface_bg": "#252526",
        "surface_alt": "#2D2D30",
        "primary": "#8B6914",
        "primary_hover": "#A67C00",
        "primary_text": "#FFFFFF",
        "text": "#D4D4D4",
        "text_secondary": "#808080",
        "border": "#3E3E42",
        "input_bg": "#3C3C3C",
        "input_border": "#3E3E42",
        "input_focus": "#8B6914",
        "success": "#6A9955",
        "warning": "#CE9178",
        "error": "#F14C4C",
        "table_header": "#2D2D30",
        "table_alt_row": "#2A2A2A",
        "selection": "#264F78",
        "scrollbar_bg": "#1E1E1E",
        "scrollbar_handle": "#424242",
        "code_bg": "#1E1E1E",
    },
    "cyber": {
        "name": "Cyber",
        "window_bg": "#0A0E14",
        "surface_bg": "#0D1117",
        "surface_alt": "#161B22",
        "primary": "#00D4AA",
        "primary_hover": "#00F5C4",
        "primary_text": "#0A0E14",
        "text": "#00D4AA",
        "text_secondary": "#00A080",
        "border": "#00D4AA40",
        "input_bg": "#0D1117",
        "input_border": "#00D4AA60",
        "input_focus": "#00D4AA",
        "success": "#00D4AA",
        "warning": "#FFB800",
        "error": "#FF3366",
        "table_header": "#161B22",
        "table_alt_row": "#0D1117",
        "selection": "#00D4AA30",
        "scrollbar_bg": "#161B22",
        "scrollbar_handle": "#00D4AA",
        "code_bg": "#0A0E14",
    }
}


def get_stylesheet(theme_name: str) -> str:
    """Generate stylesheet for the given theme"""
    t = THEMES.get(theme_name, THEMES["light"])

    return f"""
        QMainWindow {{
            background-color: {t['window_bg']};
            color: {t['text']};
        }}

        QMainWindow > QWidget {{
            background-color: {t['window_bg']};
        }}

        QDialog {{
            background-color: {t['window_bg']};
            color: {t['text']};
        }}

        QWidget {{
            color: {t['text']};
            font-family: 'Segoe UI', 'SF Pro Display', sans-serif;
            font-size: 13px;
        }}

        QSplitter {{
            background-color: {t['window_bg']};
        }}

        QTabWidget {{
            background-color: {t['window_bg']};
        }}

        QGroupBox {{
            background-color: {t['surface_bg']};
            border: 1px solid {t['border']};
            border-radius: 8px;
            margin-top: 12px;
            padding: 16px;
            padding-top: 24px;
            font-weight: 600;
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 12px;
            padding: 0 8px;
            color: {t['text']};
            background-color: {t['surface_bg']};
        }}

        QTabWidget::pane {{
            background-color: {t['surface_bg']};
            border: 1px solid {t['border']};
            border-radius: 8px;
            padding: 8px;
        }}

        QTabBar::tab {{
            background-color: {t['surface_alt']};
            color: {t['text_secondary']};
            border: 1px solid {t['border']};
            border-bottom: none;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            padding: 8px 16px;
            margin-right: 2px;
        }}

        QTabBar::tab:selected {{
            background-color: {t['surface_bg']};
            color: {t['primary']};
            border-bottom: 2px solid {t['primary']};
        }}

        QTabBar::tab:hover:!selected {{
            background-color: {t['selection']};
        }}

        QPushButton {{
            background-color: {t['primary']};
            color: {t['primary_text']};
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: 600;
        }}

        QPushButton:hover {{
            background-color: {t['primary_hover']};
        }}

        QPushButton:pressed {{
            background-color: {t['primary']};
        }}

        QPushButton:disabled {{
            background-color: {t['border']};
            color: {t['text_secondary']};
        }}

        QPushButton[secondary="true"] {{
            background-color: {t['surface_alt']};
            color: {t['text']};
            border: 1px solid {t['border']};
        }}

        QPushButton[secondary="true"]:hover {{
            background-color: {t['selection']};
            border-color: {t['primary']};
        }}

        QPushButton[danger="true"] {{
            background-color: {t['error']};
        }}

        QPushButton[danger="true"]:hover {{
            background-color: {t['error']};
        }}

        QLineEdit, QSpinBox {{
            background-color: {t['input_bg']};
            color: {t['text']};
            border: 1px solid {t['input_border']};
            border-radius: 6px;
            padding: 8px 12px;
        }}

        QLineEdit:focus, QSpinBox:focus {{
            border-color: {t['input_focus']};
            border-width: 2px;
        }}

        QTextEdit {{
            background-color: {t['code_bg']};
            color: {t['text']};
            border: 1px solid {t['border']};
            border-radius: 6px;
            padding: 8px;
            font-family: 'Fira Code', 'Consolas', 'Monaco', monospace;
            font-size: 12px;
        }}

        QTextEdit:focus {{
            border-color: {t['input_focus']};
        }}

        QComboBox {{
            background-color: {t['input_bg']};
            color: {t['text']};
            border: 1px solid {t['input_border']};
            border-radius: 6px;
            padding: 8px 12px;
            min-width: 120px;
        }}

        QComboBox::drop-down {{
            border: none;
            width: 24px;
        }}

        QComboBox::down-arrow {{
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 6px solid {t['text_secondary']};
            margin-right: 8px;
        }}

        QComboBox QAbstractItemView {{
            background-color: {t['surface_bg']};
            color: {t['text']};
            border: 1px solid {t['border']};
            selection-background-color: {t['selection']};
        }}

        QTableWidget {{
            background-color: {t['surface_bg']};
            color: {t['text']};
            border: 1px solid {t['border']};
            border-radius: 6px;
            gridline-color: {t['border']};
        }}

        QTableWidget QTableCornerButton::section {{
            background-color: {t['table_header']};
            border: none;
        }}

        QTableWidget QHeaderView {{
            background-color: {t['table_header']};
        }}

        QTableView {{
            background-color: {t['surface_bg']};
            color: {t['text']};
            gridline-color: {t['border']};
        }}

        QTableView::item {{
            background-color: {t['surface_bg']};
            color: {t['text']};
            padding: 8px;
        }}

        QTableWidget::item {{
            background-color: {t['surface_bg']};
            color: {t['text']};
            padding: 8px;
        }}

        QTableWidget::item:selected, QTableView::item:selected {{
            background-color: {t['selection']};
        }}

        QTableWidget::item:alternate {{
            background-color: {t['table_alt_row']};
        }}

        QHeaderView {{
            background-color: {t['table_header']};
        }}

        QHeaderView::section {{
            background-color: {t['table_header']};
            color: {t['text']};
            border: none;
            border-bottom: 1px solid {t['border']};
            border-right: 1px solid {t['border']};
            padding: 10px 8px;
            font-weight: 600;
        }}

        QCheckBox {{
            spacing: 8px;
        }}

        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border: 2px solid {t['input_border']};
            border-radius: 4px;
            background-color: {t['input_bg']};
        }}

        QCheckBox::indicator:checked {{
            background-color: {t['primary']};
            border-color: {t['primary']};
        }}

        QLabel {{
            color: {t['text']};
        }}

        QLabel[heading="true"] {{
            font-size: 16px;
            font-weight: 600;
            color: {t['text']};
        }}

        QLabel[subheading="true"] {{
            color: {t['text_secondary']};
            font-size: 12px;
        }}

        QSplitter::handle {{
            background-color: {t['border']};
        }}

        QSplitter::handle:horizontal {{
            width: 2px;
        }}

        QSplitter::handle:vertical {{
            height: 2px;
        }}

        QScrollBar:vertical {{
            background-color: {t['scrollbar_bg']};
            width: 12px;
            border-radius: 6px;
        }}

        QScrollBar::handle:vertical {{
            background-color: {t['scrollbar_handle']};
            min-height: 30px;
            border-radius: 6px;
            margin: 2px;
        }}

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}

        QScrollBar:horizontal {{
            background-color: {t['scrollbar_bg']};
            height: 12px;
            border-radius: 6px;
        }}

        QScrollBar::handle:horizontal {{
            background-color: {t['scrollbar_handle']};
            min-width: 30px;
            border-radius: 6px;
            margin: 2px;
        }}

        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}

        QStatusBar {{
            background-color: {t['surface_alt']};
            color: {t['text_secondary']};
            border-top: 1px solid {t['border']};
        }}

        QMenu {{
            background-color: {t['surface_bg']};
            color: {t['text']};
            border: 1px solid {t['border']};
            border-radius: 6px;
            padding: 4px;
        }}

        QMenu::item {{
            padding: 8px 24px;
            border-radius: 4px;
        }}

        QMenu::item:selected {{
            background-color: {t['selection']};
        }}

        QToolBar {{
            background-color: {t['surface_alt']};
            border: none;
            border-bottom: 1px solid {t['border']};
            padding: 4px;
            spacing: 4px;
        }}

        QFrame[frameShape="4"] {{
            background-color: {t['border']};
            max-height: 1px;
        }}
    """


# =============================================================================
# WORKER THREADS
# =============================================================================

class TemplateTestWorker(QThread):
    """Worker thread for database template testing"""
    results_ready = pyqtSignal(str, list, float, list, str)  # Added template_content
    error_occurred = pyqtSignal(str)

    def __init__(self, db_path: str, device_output: str, filter_string: str, verbose: bool = True):
        super().__init__()
        self.db_path = db_path
        self.device_output = device_output
        self.filter_string = filter_string
        self.verbose = verbose

    def run(self):
        if not TFSM_ENGINE_AVAILABLE:
            self.error_occurred.emit("TextFSM Engine not available. Use Manual Test tab instead.")
            return

        try:
            engine = TextFSMAutoEngine(self.db_path, verbose=self.verbose)

            with engine.connection_manager.get_connection() as conn:
                all_templates = engine.get_filtered_templates(conn, self.filter_string)

            # Handle different return formats from find_best_template
            result = engine.find_best_template(self.device_output, self.filter_string)

            if len(result) == 4:
                best_template, best_parsed, best_score, template_content = result
            elif len(result) == 3:
                best_template, best_parsed, best_score = result
                template_content = None
            else:
                best_template, best_parsed, best_score, template_content = None, None, 0.0, None

            # If we didn't get template_content from engine, try to fetch it from DB
            if template_content is None and best_template:
                with engine.connection_manager.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT textfsm_content FROM templates WHERE cli_command = ?",
                        (best_template,)
                    )
                    row = cursor.fetchone()
                    if row:
                        template_content = row['textfsm_content'] if isinstance(row, dict) else row[0]

            self.results_ready.emit(
                best_template or "None",
                best_parsed or [],
                best_score,
                [dict(t) for t in all_templates],
                template_content or ""
            )
        except Exception as e:
            traceback.print_exc()
            self.error_occurred.emit(str(e))


class ManualTestWorker(QThread):
    """Worker thread for manual template testing"""
    results_ready = pyqtSignal(list, list, str)  # headers, data, error

    def __init__(self, template_content: str, device_output: str):
        super().__init__()
        self.template_content = template_content
        self.device_output = device_output

    def run(self):
        try:
            template = textfsm.TextFSM(io.StringIO(self.template_content))
            parsed = template.ParseText(self.device_output)
            headers = template.header
            self.results_ready.emit(headers, parsed, "")
        except Exception as e:
            traceback.print_exc()

            self.results_ready.emit([], [], str(e))


# =============================================================================
# TEMPLATE EDITOR DIALOG
# =============================================================================

class TemplateEditorDialog(QDialog):
    """Dialog for creating/editing templates"""

    def __init__(self, parent=None, template_data: Optional[Dict] = None):
        super().__init__(parent)
        self.template_data = template_data
        self.setWindowTitle("Edit Template" if template_data else "New Template")
        self.setMinimumSize(800, 600)
        self.init_ui()

        if template_data:
            self.load_template(template_data)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Form fields
        form_layout = QFormLayout()
        form_layout.setSpacing(12)

        self.cli_command_input = QLineEdit()
        self.cli_command_input.setPlaceholderText("e.g., cisco_ios_show_ip_arp")
        form_layout.addRow("CLI Command:", self.cli_command_input)

        self.source_input = QLineEdit()
        self.source_input.setPlaceholderText("e.g., ntc-templates, custom")
        form_layout.addRow("Source:", self.source_input)

        layout.addLayout(form_layout)

        # Template content
        content_label = QLabel("TextFSM Template Content:")
        content_label.setProperty("heading", True)
        layout.addWidget(content_label)

        self.textfsm_content = QTextEdit()
        self.textfsm_content.setPlaceholderText("""Value IP_ADDRESS (\\d+\\.\\d+\\.\\d+\\.\\d+)
Value MAC_ADDRESS ([a-fA-F0-9:.-]+)
Value INTERFACE (\\S+)

Start
  ^${IP_ADDRESS}\\s+${MAC_ADDRESS}\\s+${INTERFACE} -> Record

End""")
        self.textfsm_content.setMinimumHeight(300)
        layout.addWidget(self.textfsm_content)

        # CLI content (optional)
        cli_label = QLabel("CLI Content (optional):")
        layout.addWidget(cli_label)

        self.cli_content = QTextEdit()
        self.cli_content.setMaximumHeight(100)
        self.cli_content.setPlaceholderText("Original CLI command documentation or notes...")
        layout.addWidget(self.cli_content)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def load_template(self, data: Dict):
        self.cli_command_input.setText(data.get('cli_command', ''))
        self.source_input.setText(data.get('source', ''))
        self.textfsm_content.setPlainText(data.get('textfsm_content', ''))
        self.cli_content.setPlainText(data.get('cli_content', ''))

    def get_template_data(self) -> Dict:
        content = self.textfsm_content.toPlainText()
        return {
            'cli_command': self.cli_command_input.text().strip(),
            'source': self.source_input.text().strip() or 'custom',
            'textfsm_content': content,
            'textfsm_hash': hashlib.md5(content.encode()).hexdigest(),
            'cli_content': self.cli_content.toPlainText().strip(),
            'created': datetime.now().isoformat()
        }

    def validate(self) -> tuple[bool, str]:
        if not self.cli_command_input.text().strip():
            return False, "CLI Command is required"
        if not self.textfsm_content.toPlainText().strip():
            return False, "TextFSM content is required"

        # Try to parse the template
        try:
            textfsm.TextFSM(io.StringIO(self.textfsm_content.toPlainText()))
        except Exception as e:
            traceback.print_exc()

            return False, f"Invalid TextFSM template: {str(e)}"

        return True, ""

    def accept(self):
        valid, error = self.validate()
        if not valid:
            QMessageBox.warning(self, "Validation Error", error)
            return
        super().accept()


# =============================================================================
# MAIN APPLICATION
# =============================================================================

class TextFSMTester(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TextFSM Template Tester")
        self.setGeometry(100, 100, 1400, 900)

        # Settings
        db = find_database()
        self.db_path = str(db) if db else str(get_package_db_path())
        self.current_theme = "dark"

        self.init_ui()
        self.apply_theme(self.current_theme)


    def init_ui(self):
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        self.create_toolbar()

        # Main content
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(16, 16, 16, 16)

        # Main tabs
        self.main_tabs = QTabWidget()

        # Tab 1: Database Testing
        self.main_tabs.addTab(self.create_db_test_tab(), "Database Test")

        # Tab 2: Manual Testing
        self.main_tabs.addTab(self.create_manual_test_tab(), "Manual Test")

        # Tab 3: Template Manager (CRUD)
        self.main_tabs.addTab(self.create_template_manager_tab(), "Template Manager")

        content_layout.addWidget(self.main_tabs)
        layout.addWidget(content_widget)

        # Status bar
        self.statusBar().showMessage("Ready")

    def create_toolbar(self):
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(20, 20))
        self.addToolBar(toolbar)

        # Theme selector
        theme_label = QLabel("  Theme: ")
        toolbar.addWidget(theme_label)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark", "Cyber"])
        self.theme_combo.setCurrentText(self.current_theme.capitalize())
        self.theme_combo.currentTextChanged.connect(lambda t: self.apply_theme(t.lower()))
        toolbar.addWidget(self.theme_combo)

        toolbar.addSeparator()

        # Database selector
        db_label = QLabel("  Database: ")
        toolbar.addWidget(db_label)

        self.db_path_input = QLineEdit(self.db_path)
        self.db_path_input.setMinimumWidth(300)
        toolbar.addWidget(self.db_path_input)

        browse_btn = QPushButton("Browse")
        browse_btn.setProperty("secondary", True)
        browse_btn.clicked.connect(self.browse_database)
        toolbar.addWidget(browse_btn)

        toolbar.addSeparator()

        # Quick actions
        new_db_btn = QPushButton("New DB")
        new_db_btn.setProperty("secondary", True)
        new_db_btn.clicked.connect(self.create_new_database)
        toolbar.addWidget(new_db_btn)

    def create_db_test_tab(self) -> QWidget:
        """Create the database testing tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Controls
        controls_group = QGroupBox("Test Controls")
        controls_layout = QVBoxLayout(controls_group)

        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter String:"))
        self.filter_input = QLineEdit("show_lldp_neighbor")
        self.filter_input.setPlaceholderText("e.g., show_lldp_neighbor, show_cdp_neighbor, show_ip_arp")
        filter_layout.addWidget(self.filter_input)
        controls_layout.addLayout(filter_layout)

        options_layout = QHBoxLayout()
        self.verbose_check = QCheckBox("Verbose Output")
        self.verbose_check.setChecked(True)
        options_layout.addWidget(self.verbose_check)
        options_layout.addStretch()

        self.db_test_btn = QPushButton("Test Against Database")
        self.db_test_btn.clicked.connect(self.test_db_templates)
        options_layout.addWidget(self.db_test_btn)
        controls_layout.addLayout(options_layout)

        layout.addWidget(controls_group)

        # Splitter for input/output
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Input
        input_group = QGroupBox("Device Output")
        input_layout = QVBoxLayout(input_group)

        sample_btn = QPushButton("Load Sample LLDP")
        sample_btn.setProperty("secondary", True)
        sample_btn.clicked.connect(self.load_sample_output)
        input_layout.addWidget(sample_btn)

        self.db_input_text = QTextEdit()
        self.db_input_text.setPlaceholderText("Paste device output here...")
        input_layout.addWidget(self.db_input_text)
        splitter.addWidget(input_group)

        # Results
        results_widget = QWidget()
        results_layout = QVBoxLayout(results_widget)
        results_layout.setContentsMargins(0, 0, 0, 0)

        self.db_results_tabs = QTabWidget()

        # Best results tab
        best_tab = QWidget()
        best_layout = QVBoxLayout(best_tab)

        self.best_match_label = QLabel("Best Match: None")
        self.best_match_label.setProperty("heading", True)
        best_layout.addWidget(self.best_match_label)

        self.score_label = QLabel("Score: 0.0")
        self.score_label.setProperty("subheading", True)
        best_layout.addWidget(self.score_label)

        self.db_results_table = QTableWidget()
        self.db_results_table.setAlternatingRowColors(True)
        best_layout.addWidget(self.db_results_table)

        # Export buttons for database test results
        db_export_layout = QHBoxLayout()
        export_db_json_btn = QPushButton("Export JSON")
        export_db_json_btn.setProperty("secondary", True)
        export_db_json_btn.clicked.connect(self.export_db_results_json)
        db_export_layout.addWidget(export_db_json_btn)

        export_db_csv_btn = QPushButton("Export CSV")
        export_db_csv_btn.setProperty("secondary", True)
        export_db_csv_btn.clicked.connect(self.export_db_results_csv)
        db_export_layout.addWidget(export_db_csv_btn)

        db_export_layout.addStretch()
        best_layout.addLayout(db_export_layout)

        self.db_results_tabs.addTab(best_tab, "Best Results")

        # All templates tab
        all_tab = QWidget()
        all_layout = QVBoxLayout(all_tab)
        self.all_templates_table = QTableWidget()
        self.all_templates_table.setColumnCount(4)
        self.all_templates_table.setHorizontalHeaderLabels(["Template", "Score", "Records", "Status"])
        self.all_templates_table.setAlternatingRowColors(True)
        all_layout.addWidget(self.all_templates_table)
        self.db_results_tabs.addTab(all_tab, "All Matching Templates")

        # Log tab
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        self.db_log_text = QTextEdit()
        self.db_log_text.setReadOnly(True)
        log_layout.addWidget(self.db_log_text)
        self.db_results_tabs.addTab(log_tab, "Debug Log")

        # Template Content tab (shows the winning template)
        template_tab = QWidget()
        template_tab_layout = QVBoxLayout(template_tab)

        template_info_layout = QHBoxLayout()
        self.template_name_label = QLabel("No template matched yet")
        self.template_name_label.setProperty("heading", True)
        template_info_layout.addWidget(self.template_name_label)
        template_info_layout.addStretch()

        copy_template_btn = QPushButton("Copy to Clipboard")
        copy_template_btn.setProperty("secondary", True)
        copy_template_btn.clicked.connect(self.copy_template_to_clipboard)
        template_info_layout.addWidget(copy_template_btn)

        use_in_manual_btn = QPushButton("Open in Manual Test")
        use_in_manual_btn.setProperty("secondary", True)
        use_in_manual_btn.clicked.connect(self.use_template_in_manual)
        template_info_layout.addWidget(use_in_manual_btn)

        template_tab_layout.addLayout(template_info_layout)

        self.template_content_text = QTextEdit()
        self.template_content_text.setReadOnly(True)
        self.template_content_text.setPlaceholderText("The matched template content will appear here...")
        template_tab_layout.addWidget(self.template_content_text)

        self.db_results_tabs.addTab(template_tab, "Template Content")

        results_layout.addWidget(self.db_results_tabs)
        splitter.addWidget(results_widget)

        splitter.setSizes([400, 600])
        layout.addWidget(splitter)

        return widget

    def create_manual_test_tab(self) -> QWidget:
        """Create the manual testing tab (no database required)"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Description
        desc_label = QLabel("Test TextFSM templates directly without database. Perfect for template development.")
        desc_label.setProperty("subheading", True)
        layout.addWidget(desc_label)

        # Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left side - inputs
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Template input
        template_group = QGroupBox("TextFSM Template")
        template_layout = QVBoxLayout(template_group)

        template_btn_layout = QHBoxLayout()
        load_template_btn = QPushButton("Load from File")
        load_template_btn.setProperty("secondary", True)
        load_template_btn.clicked.connect(self.load_template_file)
        template_btn_layout.addWidget(load_template_btn)

        load_sample_template_btn = QPushButton("Load Sample")
        load_sample_template_btn.setProperty("secondary", True)
        load_sample_template_btn.clicked.connect(self.load_sample_template)
        template_btn_layout.addWidget(load_sample_template_btn)
        template_btn_layout.addStretch()
        template_layout.addLayout(template_btn_layout)

        self.manual_template_text = QTextEdit()
        self.manual_template_text.setPlaceholderText("""Value NEIGHBOR (\\S+)
Value LOCAL_INTERFACE (\\S+)
Value NEIGHBOR_INTERFACE (\\S+)

Start
  ^${NEIGHBOR}\\s+${LOCAL_INTERFACE}\\s+\\d+\\s+\\S+\\s+${NEIGHBOR_INTERFACE} -> Record""")
        template_layout.addWidget(self.manual_template_text)
        left_layout.addWidget(template_group)

        # Device output input
        output_group = QGroupBox("Device Output")
        output_layout = QVBoxLayout(output_group)

        output_btn_layout = QHBoxLayout()
        load_output_btn = QPushButton("Load from File")
        load_output_btn.setProperty("secondary", True)
        load_output_btn.clicked.connect(self.load_output_file)
        output_btn_layout.addWidget(load_output_btn)

        load_sample_output_btn = QPushButton("Load Sample")
        load_sample_output_btn.setProperty("secondary", True)
        load_sample_output_btn.clicked.connect(self.load_sample_manual_output)
        output_btn_layout.addWidget(load_sample_output_btn)
        output_btn_layout.addStretch()
        output_layout.addLayout(output_btn_layout)

        self.manual_output_text = QTextEdit()
        self.manual_output_text.setPlaceholderText("Paste device output here...")
        output_layout.addWidget(self.manual_output_text)
        left_layout.addWidget(output_group)

        splitter.addWidget(left_widget)

        # Right side - results
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        results_group = QGroupBox("Parse Results")
        results_inner_layout = QVBoxLayout(results_group)

        self.manual_test_btn = QPushButton("Parse Template")
        self.manual_test_btn.clicked.connect(self.test_manual_template)
        results_inner_layout.addWidget(self.manual_test_btn)

        self.manual_status_label = QLabel("")
        self.manual_status_label.setProperty("subheading", True)
        results_inner_layout.addWidget(self.manual_status_label)

        self.manual_results_table = QTableWidget()
        self.manual_results_table.setAlternatingRowColors(True)
        results_inner_layout.addWidget(self.manual_results_table)

        # Export buttons
        export_layout = QHBoxLayout()
        export_json_btn = QPushButton("Export JSON")
        export_json_btn.setProperty("secondary", True)
        export_json_btn.clicked.connect(self.export_manual_results_json)
        export_layout.addWidget(export_json_btn)

        export_csv_btn = QPushButton("Export CSV")
        export_csv_btn.setProperty("secondary", True)
        export_csv_btn.clicked.connect(self.export_manual_results_csv)
        export_layout.addWidget(export_csv_btn)

        save_template_btn = QPushButton("Save to Database")
        save_template_btn.clicked.connect(self.save_manual_template_to_db)
        export_layout.addWidget(save_template_btn)

        export_layout.addStretch()
        results_inner_layout.addLayout(export_layout)

        right_layout.addWidget(results_group)
        splitter.addWidget(right_widget)

        splitter.setSizes([500, 500])
        layout.addWidget(splitter)

        return widget

    def create_template_manager_tab(self) -> QWidget:
        """Create the template manager (CRUD) tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Search/filter bar
        filter_group = QGroupBox("Search Templates")
        filter_layout = QHBoxLayout(filter_group)

        filter_layout.addWidget(QLabel("Search:"))
        self.mgr_search_input = QLineEdit()
        self.mgr_search_input.setPlaceholderText("Filter by command name...")
        self.mgr_search_input.textChanged.connect(self.filter_templates)
        filter_layout.addWidget(self.mgr_search_input)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setProperty("secondary", True)
        refresh_btn.clicked.connect(self.load_all_templates)
        filter_layout.addWidget(refresh_btn)

        layout.addWidget(filter_group)

        # Template table
        self.mgr_table = QTableWidget()
        self.mgr_table.setColumnCount(5)
        self.mgr_table.setHorizontalHeaderLabels(["ID", "CLI Command", "Source", "Created", "Hash"])
        self.mgr_table.setAlternatingRowColors(True)
        self.mgr_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.mgr_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.mgr_table.horizontalHeader().setStretchLastSection(True)
        self.mgr_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.mgr_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.mgr_table.customContextMenuRequested.connect(self.show_template_context_menu)
        self.mgr_table.doubleClicked.connect(self.edit_selected_template)
        layout.addWidget(self.mgr_table)

        # Action buttons
        btn_layout = QHBoxLayout()

        add_btn = QPushButton("Add Template")
        add_btn.clicked.connect(self.add_template)
        btn_layout.addWidget(add_btn)

        edit_btn = QPushButton("Edit Selected")
        edit_btn.setProperty("secondary", True)
        edit_btn.clicked.connect(self.edit_selected_template)
        btn_layout.addWidget(edit_btn)

        delete_btn = QPushButton("Delete Selected")
        delete_btn.setProperty("danger", True)
        delete_btn.clicked.connect(self.delete_selected_template)
        btn_layout.addWidget(delete_btn)

        btn_layout.addStretch()

        import_btn = QPushButton("Import from NTC")
        import_btn.setProperty("secondary", True)
        import_btn.clicked.connect(self.import_from_ntc)
        btn_layout.addWidget(import_btn)

        download_btn = QPushButton("Download from NTC")
        download_btn.setProperty("secondary", True)
        download_btn.clicked.connect(self.download_from_ntc)
        btn_layout.addWidget(download_btn)

        export_btn = QPushButton("Export All")
        export_btn.setProperty("secondary", True)
        export_btn.clicked.connect(self.export_all_templates)
        btn_layout.addWidget(export_btn)

        layout.addLayout(btn_layout)

        # Template preview
        preview_group = QGroupBox("Template Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.mgr_preview_text = QTextEdit()
        self.mgr_preview_text.setReadOnly(True)
        self.mgr_preview_text.setMaximumHeight(200)
        preview_layout.addWidget(self.mgr_preview_text)

        layout.addWidget(preview_group)

        # Connect selection change to preview
        self.mgr_table.selectionModel().selectionChanged.connect(self.update_template_preview)

        return widget

    # =========================================================================
    # THEME HANDLING
    # =========================================================================

    def apply_theme(self, theme_name: str):
        self.current_theme = theme_name
        self.setStyleSheet(get_stylesheet(theme_name))

    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================

    def browse_database(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select TextFSM Database", "", "Database Files (*.db);;All Files (*)"
        )
        if file_path:
            self.db_path_input.setText(file_path)
            self.db_path = file_path
            self.load_all_templates()

    def create_new_database(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Create New Database", "tfsm_templates.db", "Database Files (*.db)"
        )
        if file_path:
            try:
                conn = sqlite3.connect(file_path)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS templates (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        cli_command TEXT NOT NULL,
                        cli_content TEXT,
                        textfsm_content TEXT NOT NULL,
                        textfsm_hash TEXT,
                        source TEXT,
                        created TEXT
                    )
                """)
                conn.commit()
                conn.close()

                self.db_path = file_path
                self.db_path_input.setText(file_path)
                self.statusBar().showMessage(f"Created new database: {file_path}")
                QMessageBox.information(self, "Success", f"Created new database: {file_path}")
            except Exception as e:
                traceback.print_exc()

                QMessageBox.critical(self, "Error", f"Failed to create database: {str(e)}")

    def get_db_connection(self) -> Optional[sqlite3.Connection]:
        """Get database connection."""
        import traceback

        # Always use the current value from the input field
        db_path = Path(self.db_path_input.text().strip())

        # Update self.db_path to match
        self.db_path = str(db_path)

        if not db_path.exists():
            QMessageBox.warning(
                self, "Database Not Found",
                f"Database file not found:\n{db_path}\n\n"
                f"Use 'New DB' to create one or 'Browse' to locate an existing database."
            )
            return None

        if db_path.is_dir():
            QMessageBox.warning(
                self, "Invalid Path",
                f"Path is a DIRECTORY, not a file:\n{db_path}\n\n"
                f"Please select the actual .db file, not a folder."
            )
            return None

        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            return conn
        except Exception as e:
            tb = traceback.format_exc()
            print(f"[DB Connection Error] {db_path}\n{tb}", file=sys.stderr)
            QMessageBox.critical(
                self, "Database Error",
                f"Failed to open database:\n{db_path}\n\nError: {e}"
            )
            return None

    # =========================================================================
    # DATABASE TEST TAB
    # =========================================================================

    def test_db_templates(self):
        device_output = self.db_input_text.toPlainText().strip()
        filter_string = self.filter_input.text().strip()

        if not device_output:
            QMessageBox.warning(self, "Warning", "Please enter device output to test")
            return

        if not Path(self.db_path_input.text()).exists():
            QMessageBox.critical(self, "Error", f"Database not found: {self.db_path_input.text()}")
            return

        self.db_path = self.db_path_input.text()
        self.db_test_btn.setEnabled(False)
        self.statusBar().showMessage("Testing templates...")
        self.db_log_text.clear()

        self.worker = TemplateTestWorker(
            self.db_path, device_output, filter_string, self.verbose_check.isChecked()
        )
        self.worker.results_ready.connect(self.handle_db_results)
        self.worker.error_occurred.connect(self.handle_db_error)
        self.worker.start()

    def handle_db_results(self, best_template: str, best_parsed: list, best_score: float,
                          all_templates: list, template_content: str):
        self.db_test_btn.setEnabled(True)
        self.statusBar().showMessage("Testing complete")

        self.best_match_label.setText(f"Best Match: {best_template}")
        self.score_label.setText(f"Score: {best_score:.2f}")

        # Store template content for later use
        self._current_template_content = template_content
        self._current_template_name = best_template

        # Store parsed data for export
        self._db_parsed_data = best_parsed

        # Update results table
        if best_parsed:
            self.db_results_table.setRowCount(len(best_parsed))
            self.db_results_table.setColumnCount(len(best_parsed[0]))
            self.db_results_table.setHorizontalHeaderLabels(list(best_parsed[0].keys()))

            for row, item in enumerate(best_parsed):
                for col, (key, value) in enumerate(item.items()):
                    self.db_results_table.setItem(row, col, QTableWidgetItem(str(value)))
        else:
            self.db_results_table.setRowCount(0)
            self.db_results_table.setColumnCount(0)

        # Update all templates table
        self.all_templates_table.setRowCount(len(all_templates))
        for row, template in enumerate(all_templates):
            self.all_templates_table.setItem(row, 0, QTableWidgetItem(template.get('cli_command', '')))
            self.all_templates_table.setItem(row, 1, QTableWidgetItem("N/A"))
            self.all_templates_table.setItem(row, 2, QTableWidgetItem("N/A"))
            self.all_templates_table.setItem(row, 3, QTableWidgetItem("Available"))

        # Update template content tab
        self.template_name_label.setText(f"Template: {best_template}")
        if template_content:
            self.template_content_text.setPlainText(template_content)
        else:
            self.template_content_text.setPlainText("(Template content not available)")

        # Log
        self.log_db_results(best_template, best_parsed, best_score, all_templates)
        self.db_results_tabs.setCurrentIndex(0)

    def handle_db_error(self, error: str):
        self.db_test_btn.setEnabled(True)
        self.statusBar().showMessage("Error occurred")
        QMessageBox.critical(self, "Error", error)

    def log_db_results(self, best_template: str, best_parsed: list, best_score: float, all_templates: list):
        log = []
        log.append("=" * 60)
        log.append("TEXTFSM TEMPLATE TEST RESULTS")
        log.append("=" * 60)
        log.append(f"Filter String: {self.filter_input.text()}")
        log.append(f"Templates Found: {len(all_templates)}")
        log.append(f"Best Template: {best_template}")
        log.append(f"Best Score: {best_score:.2f}")
        log.append(f"Records Parsed: {len(best_parsed) if best_parsed else 0}")
        log.append("")

        if best_parsed:
            log.append("PARSED DATA SAMPLE:")
            log.append("-" * 40)
            for i, record in enumerate(best_parsed[:3]):
                log.append(f"Record {i + 1}:")
                log.append(json.dumps(record, indent=2))
                log.append("")

            if len(best_parsed) > 3:
                log.append(f"... and {len(best_parsed) - 3} more records")

        log.append("")
        log.append("ALL MATCHING TEMPLATES:")
        log.append("-" * 40)
        for t in all_templates:
            log.append(f"• {t.get('cli_command', 'Unknown')}")

        self.db_log_text.setPlainText("\n".join(log))

    def load_sample_output(self):
        sample = """usa-spine-2#show lldp neighbors detail
Capability codes:
    (R) Router, (B) Bridge, (T) Telephone, (C) DOCSIS Cable Device
    (W) WLAN Access Point, (P) Repeater, (S) Station, (O) Other

Device ID           Local Intf     Hold-time  Capability      Port ID
usa-spine-1         Eth2           120        B,R             Ethernet2
usa-rtr-1           Eth1           120        R               GigabitEthernet0/2
usa-leaf-3          Eth3           120        R               GigabitEthernet0/0
usa-leaf-2          Eth4           120        R               GigabitEthernet0/0
usa-leaf-1          Eth5           120        R               GigabitEthernet0/0"""
        self.db_input_text.setPlainText(sample)
        self.filter_input.setText("show_lldp_neighbor")

    def copy_template_to_clipboard(self):
        """Copy the current template content to clipboard"""
        if hasattr(self, '_current_template_content') and self._current_template_content:
            clipboard = QApplication.clipboard()
            clipboard.setText(self._current_template_content)
            self.statusBar().showMessage("Template copied to clipboard")
        else:
            QMessageBox.warning(self, "Warning", "No template content to copy")

    def use_template_in_manual(self):
        """Load the current template into the Manual Test tab"""
        if hasattr(self, '_current_template_content') and self._current_template_content:
            self.manual_template_text.setPlainText(self._current_template_content)
            # Also copy the device output
            device_output = self.db_input_text.toPlainText()
            if device_output:
                self.manual_output_text.setPlainText(device_output)
            self.main_tabs.setCurrentIndex(1)  # Switch to Manual Test tab
            self.statusBar().showMessage("Template loaded into Manual Test tab")
        else:
            QMessageBox.warning(self, "Warning", "No template content to load")

    def export_db_results_json(self):
        """Export database test results to JSON"""
        if not hasattr(self, '_db_parsed_data') or not self._db_parsed_data:
            QMessageBox.warning(self, "Warning", "No results to export. Run a test first.")
            return

        # Generate default filename from template name
        default_name = "results.json"
        if hasattr(self, '_current_template_name') and self._current_template_name:
            default_name = f"{self._current_template_name}_results.json"

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export JSON", default_name, "JSON Files (*.json)"
        )
        if file_path:
            try:
                with open(file_path, 'w') as f:
                    json.dump(self._db_parsed_data, f, indent=2)
                self.statusBar().showMessage(f"Exported {len(self._db_parsed_data)} records to {file_path}")
            except Exception as e:
                traceback.print_exc()

                QMessageBox.critical(self, "Error", f"Export failed: {str(e)}")

    def export_db_results_csv(self):
        """Export database test results to CSV"""
        if not hasattr(self, '_db_parsed_data') or not self._db_parsed_data:
            QMessageBox.warning(self, "Warning", "No results to export. Run a test first.")
            return

        # Generate default filename from template name
        default_name = "results.csv"
        if hasattr(self, '_current_template_name') and self._current_template_name:
            default_name = f"{self._current_template_name}_results.csv"

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", default_name, "CSV Files (*.csv)"
        )
        if file_path:
            try:
                import csv
                # Get headers from first record
                headers = list(self._db_parsed_data[0].keys())
                with open(file_path, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=headers)
                    writer.writeheader()
                    writer.writerows(self._db_parsed_data)
                self.statusBar().showMessage(f"Exported {len(self._db_parsed_data)} records to {file_path}")
            except Exception as e:
                traceback.print_exc()

                QMessageBox.critical(self, "Error", f"Export failed: {str(e)}")

    # =========================================================================
    # MANUAL TEST TAB
    # =========================================================================

    def load_template_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load TextFSM Template", "", "TextFSM Files (*.textfsm *.template);;All Files (*)"
        )
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    self.manual_template_text.setPlainText(f.read())
                self.statusBar().showMessage(f"Loaded template: {file_path}")
            except Exception as e:
                traceback.print_exc()

                QMessageBox.critical(self, "Error", f"Failed to load file: {str(e)}")

    def load_output_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Device Output", "", "Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    self.manual_output_text.setPlainText(f.read())
                self.statusBar().showMessage(f"Loaded output: {file_path}")
            except Exception as e:
                traceback.print_exc()

                QMessageBox.critical(self, "Error", f"Failed to load file: {str(e)}")

    def load_sample_template(self):
        sample = """Value NEIGHBOR (\\S+)
Value LOCAL_INTERFACE (\\S+)
Value HOLD_TIME (\\d+)
Value CAPABILITY (\\S+)
Value NEIGHBOR_INTERFACE (\\S+)

Start
  ^${NEIGHBOR}\\s+${LOCAL_INTERFACE}\\s+${HOLD_TIME}\\s+${CAPABILITY}\\s+${NEIGHBOR_INTERFACE} -> Record

End"""
        self.manual_template_text.setPlainText(sample)

    def load_sample_manual_output(self):
        sample = """Device ID           Local Intf     Hold-time  Capability      Port ID
usa-spine-1         Eth2           120        B,R             Ethernet2
usa-rtr-1           Eth1           120        R               GigabitEthernet0/2
usa-leaf-3          Eth3           120        R               GigabitEthernet0/0
usa-leaf-2          Eth4           120        R               GigabitEthernet0/0
usa-leaf-1          Eth5           120        R               GigabitEthernet0/0"""
        self.manual_output_text.setPlainText(sample)

    def test_manual_template(self):
        template_content = self.manual_template_text.toPlainText().strip()
        device_output = self.manual_output_text.toPlainText().strip()

        if not template_content:
            QMessageBox.warning(self, "Warning", "Please enter a TextFSM template")
            return

        if not device_output:
            QMessageBox.warning(self, "Warning", "Please enter device output")
            return

        self.manual_test_btn.setEnabled(False)
        self.statusBar().showMessage("Parsing...")

        self.manual_worker = ManualTestWorker(template_content, device_output)
        self.manual_worker.results_ready.connect(self.handle_manual_results)
        self.manual_worker.start()

    def handle_manual_results(self, headers: list, data: list, error: str):
        self.manual_test_btn.setEnabled(True)

        if error:
            self.manual_status_label.setText(f"Error: {error}")
            self.manual_results_table.setRowCount(0)
            self.manual_results_table.setColumnCount(0)
            self.statusBar().showMessage("Parse failed")
            return

        self.manual_status_label.setText(f"Successfully parsed {len(data)} records with {len(headers)} fields")
        self.statusBar().showMessage(f"Parsed {len(data)} records")

        # Populate table
        self.manual_results_table.setRowCount(len(data))
        self.manual_results_table.setColumnCount(len(headers))
        self.manual_results_table.setHorizontalHeaderLabels(headers)

        for row_idx, row in enumerate(data):
            for col_idx, value in enumerate(row):
                self.manual_results_table.setItem(row_idx, col_idx, QTableWidgetItem(str(value)))

        # Store for export
        self._manual_headers = headers
        self._manual_data = data

    def export_manual_results_json(self):
        if not hasattr(self, '_manual_data') or not self._manual_data:
            QMessageBox.warning(self, "Warning", "No results to export")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export JSON", "results.json", "JSON Files (*.json)"
        )
        if file_path:
            try:
                results = [dict(zip(self._manual_headers, row)) for row in self._manual_data]
                with open(file_path, 'w') as f:
                    json.dump(results, f, indent=2)
                self.statusBar().showMessage(f"Exported to {file_path}")
            except Exception as e:
                traceback.print_exc()

                QMessageBox.critical(self, "Error", f"Export failed: {str(e)}")

    def export_manual_results_csv(self):
        if not hasattr(self, '_manual_data') or not self._manual_data:
            QMessageBox.warning(self, "Warning", "No results to export")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "results.csv", "CSV Files (*.csv)"
        )
        if file_path:
            try:
                import csv
                with open(file_path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(self._manual_headers)
                    writer.writerows(self._manual_data)
                self.statusBar().showMessage(f"Exported to {file_path}")
            except Exception as e:
                traceback.print_exc()

                QMessageBox.critical(self, "Error", f"Export failed: {str(e)}")

    def save_manual_template_to_db(self):
        template_content = self.manual_template_text.toPlainText().strip()
        if not template_content:
            QMessageBox.warning(self, "Warning", "No template to save")
            return

        # Validate template first
        try:
            textfsm.TextFSM(io.StringIO(template_content))
        except Exception as e:
            traceback.print_exc()

            QMessageBox.critical(self, "Error", f"Invalid template: {str(e)}")
            return

        name, ok = QInputDialog.getText(
            self, "Save Template", "Enter CLI command name (e.g., cisco_ios_show_ip_arp):"
        )
        if ok and name:
            conn = self.get_db_connection()
            if conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO templates (cli_command, textfsm_content, textfsm_hash, source, created)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        name,
                        template_content,
                        hashlib.md5(template_content.encode()).hexdigest(),
                        'manual',
                        datetime.now().isoformat()
                    ))
                    conn.commit()
                    conn.close()
                    self.statusBar().showMessage(f"Template saved: {name}")
                    QMessageBox.information(self, "Success", f"Template '{name}' saved to database")
                    self.load_all_templates()
                except Exception as e:
                    traceback.print_exc()

                    QMessageBox.critical(self, "Error", f"Failed to save: {str(e)}")

    # =========================================================================
    # TEMPLATE MANAGER TAB
    # =========================================================================

    def load_all_templates(self):
        conn = self.get_db_connection()
        if not conn:
            return

        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, cli_command, source, created, textfsm_hash FROM templates ORDER BY cli_command")
            templates = cursor.fetchall()
            conn.close()

            self.mgr_table.setRowCount(len(templates))
            for row, t in enumerate(templates):
                self.mgr_table.setItem(row, 0, QTableWidgetItem(str(t['id'])))
                self.mgr_table.setItem(row, 1, QTableWidgetItem(t['cli_command'] or ''))
                self.mgr_table.setItem(row, 2, QTableWidgetItem(t['source'] or ''))
                self.mgr_table.setItem(row, 3, QTableWidgetItem(t['created'] or ''))
                self.mgr_table.setItem(row, 4, QTableWidgetItem(t['textfsm_hash'] or ''))

            self.statusBar().showMessage(f"Loaded {len(templates)} templates")

            # Store all templates for filtering
            self._all_templates = templates

        except Exception as e:
            traceback.print_exc()

            QMessageBox.critical(self, "Error", f"Failed to load templates: {str(e)}")

    def filter_templates(self, text: str):
        if not hasattr(self, '_all_templates'):
            return

        search = text.lower()
        for row in range(self.mgr_table.rowCount()):
            item = self.mgr_table.item(row, 1)  # CLI command column
            if item:
                match = search in item.text().lower()
                self.mgr_table.setRowHidden(row, not match)

    def update_template_preview(self):
        selected = self.mgr_table.selectedItems()
        if not selected:
            self.mgr_preview_text.clear()
            return

        row = selected[0].row()
        template_id = self.mgr_table.item(row, 0).text()

        conn = self.get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT textfsm_content FROM templates WHERE id = ?", (template_id,))
                result = cursor.fetchone()
                conn.close()

                if result:
                    self.mgr_preview_text.setPlainText(result['textfsm_content'])
            except Exception as e:
                traceback.print_exc()

                self.mgr_preview_text.setPlainText(f"Error loading preview: {str(e)}")

    def show_template_context_menu(self, pos):
        menu = QMenu(self)

        edit_action = menu.addAction("Edit")
        edit_action.triggered.connect(self.edit_selected_template)

        duplicate_action = menu.addAction("Duplicate")
        duplicate_action.triggered.connect(self.duplicate_selected_template)

        menu.addSeparator()

        test_action = menu.addAction("Test in Manual Tab")
        test_action.triggered.connect(self.test_selected_in_manual)

        menu.addSeparator()

        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(self.delete_selected_template)

        menu.exec(self.mgr_table.viewport().mapToGlobal(pos))

    def add_template(self):
        dialog = TemplateEditorDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_template_data()

            conn = self.get_db_connection()
            if conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO templates (cli_command, cli_content, textfsm_content, textfsm_hash, source, created)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        data['cli_command'],
                        data['cli_content'],
                        data['textfsm_content'],
                        data['textfsm_hash'],
                        data['source'],
                        data['created']
                    ))
                    conn.commit()
                    conn.close()

                    self.statusBar().showMessage(f"Added template: {data['cli_command']}")
                    self.load_all_templates()
                except Exception as e:
                    traceback.print_exc()

                    QMessageBox.critical(self, "Error", f"Failed to add template: {str(e)}")

    def edit_selected_template(self):
        selected = self.mgr_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Warning", "Please select a template to edit")
            return

        row = selected[0].row()
        template_id = self.mgr_table.item(row, 0).text()

        conn = self.get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM templates WHERE id = ?", (template_id,))
                template = cursor.fetchone()
                conn.close()

                if template:
                    dialog = TemplateEditorDialog(self, dict(template))
                    if dialog.exec() == QDialog.DialogCode.Accepted:
                        data = dialog.get_template_data()

                        conn = self.get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE templates SET
                                cli_command = ?, cli_content = ?, textfsm_content = ?,
                                textfsm_hash = ?, source = ?
                            WHERE id = ?
                        """, (
                            data['cli_command'],
                            data['cli_content'],
                            data['textfsm_content'],
                            data['textfsm_hash'],
                            data['source'],
                            template_id
                        ))
                        conn.commit()
                        conn.close()

                        self.statusBar().showMessage(f"Updated template: {data['cli_command']}")
                        self.load_all_templates()
            except Exception as e:
                traceback.print_exc()

                QMessageBox.critical(self, "Error", f"Failed to edit template: {str(e)}")

    def delete_selected_template(self):
        selected = self.mgr_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Warning", "Please select a template to delete")
            return

        row = selected[0].row()
        template_id = self.mgr_table.item(row, 0).text()
        cli_command = self.mgr_table.item(row, 1).text()

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete '{cli_command}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            conn = self.get_db_connection()
            if conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM templates WHERE id = ?", (template_id,))
                    conn.commit()
                    conn.close()

                    self.statusBar().showMessage(f"Deleted template: {cli_command}")
                    self.load_all_templates()
                except Exception as e:
                    traceback.print_exc()

                    QMessageBox.critical(self, "Error", f"Failed to delete: {str(e)}")

    def duplicate_selected_template(self):
        selected = self.mgr_table.selectedItems()
        if not selected:
            return

        row = selected[0].row()
        template_id = self.mgr_table.item(row, 0).text()

        conn = self.get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM templates WHERE id = ?", (template_id,))
                template = dict(cursor.fetchone())

                # Modify for duplicate
                template['cli_command'] = template['cli_command'] + '_copy'
                template['created'] = datetime.now().isoformat()

                cursor.execute("""
                    INSERT INTO templates (cli_command, cli_content, textfsm_content, textfsm_hash, source, created)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    template['cli_command'],
                    template.get('cli_content', ''),
                    template['textfsm_content'],
                    template.get('textfsm_hash', ''),
                    template.get('source', 'duplicate'),
                    template['created']
                ))
                conn.commit()
                conn.close()

                self.statusBar().showMessage(f"Duplicated template: {template['cli_command']}")
                self.load_all_templates()
            except Exception as e:
                traceback.print_exc()

                QMessageBox.critical(self, "Error", f"Failed to duplicate: {str(e)}")

    def test_selected_in_manual(self):
        selected = self.mgr_table.selectedItems()
        if not selected:
            return

        row = selected[0].row()
        template_id = self.mgr_table.item(row, 0).text()

        conn = self.get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT textfsm_content FROM templates WHERE id = ?", (template_id,))
                result = cursor.fetchone()
                conn.close()

                if result:
                    self.manual_template_text.setPlainText(result['textfsm_content'])
                    self.main_tabs.setCurrentIndex(1)  # Switch to Manual Test tab
                    self.statusBar().showMessage("Template loaded into Manual Test tab")
            except Exception as e:
                traceback.print_exc()

                QMessageBox.critical(self, "Error", f"Failed to load template: {str(e)}")

    def import_from_ntc(self):
        """Import templates from ntc-templates directory"""
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select ntc-templates Directory"
        )
        if not dir_path:
            return

        templates_dir = Path(dir_path)
        if not templates_dir.exists():
            QMessageBox.critical(self, "Error", "Directory not found")
            return

        # Look for .textfsm files
        template_files = list(templates_dir.glob("**/*.textfsm"))
        if not template_files:
            template_files = list(templates_dir.glob("**/*.template"))

        if not template_files:
            QMessageBox.warning(self, "Warning", "No TextFSM template files found")
            return

        conn = self.get_db_connection()
        if not conn:
            return

        imported = 0
        skipped = 0

        try:
            cursor = conn.cursor()

            for file_path in template_files:
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()

                    # Derive cli_command from filename
                    cli_command = file_path.stem  # filename without extension

                    # Check if already exists
                    cursor.execute("SELECT id FROM templates WHERE cli_command = ?", (cli_command,))
                    if cursor.fetchone():
                        skipped += 1
                        continue

                    cursor.execute("""
                        INSERT INTO templates (cli_command, textfsm_content, textfsm_hash, source, created)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        cli_command,
                        content,
                        hashlib.md5(content.encode()).hexdigest(),
                        'ntc-templates',
                        datetime.now().isoformat()
                    ))
                    imported += 1

                except Exception as e:
                    traceback.print_exc()

                    print(f"Error importing {file_path}: {e}")
                    continue

            conn.commit()
            conn.close()

            self.statusBar().showMessage(f"Imported {imported} templates, skipped {skipped} duplicates")
            QMessageBox.information(
                self, "Import Complete",
                f"Imported: {imported}\nSkipped (duplicates): {skipped}"
            )
            self.load_all_templates()

        except Exception as e:
            traceback.print_exc()

            QMessageBox.critical(self, "Error", f"Import failed: {str(e)}")

    def download_from_ntc(self):
        """Download templates from ntc-templates GitHub repository"""
        if not REQUESTS_AVAILABLE:
            QMessageBox.critical(
                self, "Error",
                "requests library not available.\nInstall with: pip install requests"
            )
            return

        dialog = NTCDownloadDialog(self, self.db_path_input.text())
        dialog.exec()
        self.load_all_templates()

    def export_all_templates(self):
        """Export all templates to a directory"""
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Export Directory"
        )
        if not dir_path:
            return

        conn = self.get_db_connection()
        if not conn:
            return

        try:
            cursor = conn.cursor()
            cursor.execute("SELECT cli_command, textfsm_content FROM templates")
            templates = cursor.fetchall()
            conn.close()

            export_dir = Path(dir_path)
            exported = 0

            for t in templates:
                file_path = export_dir / f"{t['cli_command']}.textfsm"
                with open(file_path, 'w') as f:
                    f.write(t['textfsm_content'])
                exported += 1

            self.statusBar().showMessage(f"Exported {exported} templates")
            QMessageBox.information(self, "Export Complete", f"Exported {exported} templates to {dir_path}")

        except Exception as e:
            traceback.print_exc()

            QMessageBox.critical(self, "Error", f"Export failed: {str(e)}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = TextFSMTester()
    window.show()

    # Load templates on startup if database exists
    if Path(window.db_path).exists():
        window.load_all_templates()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()