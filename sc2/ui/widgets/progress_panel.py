"""
SecureCartography v2 - Progress Panel Widget

Displays discovery progress:
- Stat counters (discovered, failed, queue, total)
- Current target being discovered
- Depth indicator
- Progress bar
"""

from typing import Optional
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QWidget, QSizePolicy
)
from PyQt6.QtGui import QFont

from ..themes import ThemeColors, ThemeManager
from .panel import Panel
from .stat_box import StatBoxRow


class ProgressPanel(Panel):
    """
    Progress tracking panel for discovery operations.

    Layout:
    ┌─ PROGRESS ──────────────────────────────────┐
    │ ┌─────────┬─────────┬─────────┬─────────┐   │
    │ │   24    │    2    │    8    │   34    │   │
    │ │DISCOVERED│ FAILED │  QUEUE  │  TOTAL  │   │
    │ └─────────┴─────────┴─────────┴─────────┘   │
    │                                              │
    │ → Discovering: core-switch-01.corp.local    │
    │                                              │
    │ Depth 2 of 3                           70%  │
    │ ████████████████████░░░░░░░░░░░░░░░░░░░░░░  │
    └──────────────────────────────────────────────┘

    Usage:
        progress = ProgressPanel(theme_manager=tm)

        # Update from ProgressState
        progress.set_discovered(24)
        progress.set_failed(2)
        progress.set_queued(8)
        progress.set_current_target("core-switch-01.corp.local")
        progress.set_depth(2, 3)
        progress.set_progress(70)
    """

    def __init__(
        self,
        theme_manager: Optional[ThemeManager] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(
            title="PROGRESS",
            icon="📊",
            theme_manager=theme_manager,
            parent=parent,
            _defer_theme=True  # Apply theme after _setup_content
        )
        self._setup_content()
        if theme_manager:
            self.apply_theme(theme_manager.theme)

    def _setup_content(self):
        """Build the progress panel content."""
        # Stat boxes row
        self.stats = StatBoxRow(theme_manager=self.theme_manager)
        self.content_layout.addWidget(self.stats)

        # Current target display
        self.target_frame = QFrame()
        self.target_frame.setObjectName("currentTarget")
        target_layout = QHBoxLayout(self.target_frame)
        target_layout.setContentsMargins(12, 8, 12, 8)
        target_layout.setSpacing(8)

        self.target_arrow = QLabel("→")
        self.target_arrow.setObjectName("targetArrow")
        target_layout.addWidget(self.target_arrow)

        self.target_label = QLabel("Discovering:")
        self.target_label.setObjectName("targetPrefix")
        target_layout.addWidget(self.target_label)

        self.target_value = QLabel("Waiting...")
        self.target_value.setObjectName("targetValue")
        self.target_value.setFont(QFont("JetBrains Mono", 11))
        target_layout.addWidget(self.target_value, 1)

        self.content_layout.addWidget(self.target_frame)

        # Depth and progress row
        progress_header = QHBoxLayout()
        progress_header.setSpacing(8)

        self.depth_label = QLabel("Depth 0 of 0")
        self.depth_label.setObjectName("depthLabel")
        progress_header.addWidget(self.depth_label)

        progress_header.addStretch()

        self.percent_label = QLabel("0%")
        self.percent_label.setObjectName("percentLabel")
        progress_header.addWidget(self.percent_label)

        self.content_layout.addLayout(progress_header)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("discoveryProgress")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.content_layout.addWidget(self.progress_bar)

    # === Public API ===

    def set_discovered(self, count: int):
        """Update discovered counter."""
        self.stats.set_discovered(count)

    def set_failed(self, count: int):
        """Update failed counter."""
        self.stats.set_failed(count)

    def set_queued(self, count: int):
        """Update queue counter."""
        self.stats.set_queued(count)

    def set_total(self, count: int):
        """Update total counter."""
        self.stats.set_total(count)

    def set_current_target(self, target: str):
        """Update the current target display."""
        self.target_value.setText(target if target else "Waiting...")

    def set_depth(self, current: int, maximum: int):
        """Update depth indicator."""
        self.depth_label.setText(f"Depth {current} of {maximum}")

    def set_progress(self, percent: int):
        """Update progress bar and percentage."""
        percent = max(0, min(100, percent))  # Clamp 0-100
        self.progress_bar.setValue(percent)
        self.percent_label.setText(f"{percent}%")

    def reset(self):
        """Reset all progress indicators."""
        self.stats.reset()
        self.set_current_target("")
        self.set_depth(0, 0)
        self.set_progress(0)

    def set_idle(self):
        """Set to idle state (before/after crawl)."""
        self.set_current_target("Ready")
        self.target_arrow.setText("●")

    def set_running(self):
        """Set to running state."""
        self.target_arrow.setText("→")

    def set_complete(self, elapsed_seconds: float = 0):
        """Set to complete state."""
        self.target_arrow.setText("✓")
        if elapsed_seconds > 0:
            self.set_current_target(f"Complete ({elapsed_seconds:.1f}s)")
        else:
            self.set_current_target("Complete")
        self.set_progress(100)

    def set_error(self, message: str = ""):
        """Set to error state."""
        self.target_arrow.setText("✗")
        self.set_current_target(message if message else "Error")

    def _apply_content_theme(self, theme: ThemeColors):
        """Apply theme to progress panel content."""
        self.stats.apply_theme(theme)

        # Current target frame
        self.target_frame.setStyleSheet(f"""
            QFrame#currentTarget {{
                background-color: {theme.bg_tertiary};
                border: 1px solid {theme.border_dim};
                border-radius: 6px;
            }}
            
            QLabel#targetArrow {{
                color: {theme.accent};
                font-size: 14px;
                background: transparent;
                border: none;
            }}
            
            QLabel#targetPrefix {{
                color: {theme.text_secondary};
                font-size: 12px;
                background: transparent;
                border: none;
            }}
            
            QLabel#targetValue {{
                color: {theme.text_primary};
                background: transparent;
                border: none;
            }}
        """)

        # Depth and percent labels
        self.depth_label.setStyleSheet(f"""
            QLabel#depthLabel {{
                color: {theme.text_muted};
                font-size: 11px;
                background: transparent;
            }}
        """)

        self.percent_label.setStyleSheet(f"""
            QLabel#percentLabel {{
                color: {theme.text_muted};
                font-size: 11px;
                background: transparent;
            }}
        """)

        # Progress bar with gradient
        self.progress_bar.setStyleSheet(f"""
            QProgressBar#discoveryProgress {{
                background-color: {theme.bg_tertiary};
                border: none;
                border-radius: 4px;
            }}
            
            QProgressBar#discoveryProgress::chunk {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {theme.accent_dim},
                    stop:1 {theme.accent}
                );
                border-radius: 4px;
            }}
        """)

    def apply_theme(self, theme: ThemeColors):
        """Apply theme to entire panel."""
        super().apply_theme(theme)
        self._apply_content_theme(theme)

    def set_theme(self, theme_manager: ThemeManager):
        """Update theme manager and apply."""
        super().set_theme(theme_manager)
        self._apply_content_theme(theme_manager.theme)