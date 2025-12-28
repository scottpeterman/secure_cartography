"""
SecureCartography v2 - Login Dialog

Vault unlock screen with password authentication.
Matches the mockup design with icon, title, and styled inputs.
"""
import traceback
from pathlib import Path
from typing import Optional, Callable

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QPixmap, QColor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QWidget, QMessageBox, QApplication,
    QGraphicsDropShadowEffect
)

from .themes import ThemeColors, ThemeManager, ThemeName, fix_all_comboboxes, StyledComboBox
from .settings import SettingsManager, get_settings


class IconLabel(QLabel):
    """
    Label that renders a simple icon using unicode or custom painting.
    For PyQt6, we'll use a simple approach with unicode symbols
    or custom SVG rendering.
    """

    def __init__(self, icon_char: str = "🔒", size: int = 32, parent=None):
        super().__init__(parent)
        self.setText(icon_char)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = self.font()
        font.setPointSize(size)
        self.setFont(font)


class ThemeBanner(QLabel):
    """
    Theme-aware banner image widget.

    Displays different banner images based on the active theme.
    Automatically handles scaling and aspect ratio preservation.
    """

    # Mapping of theme names to banner image filenames
    BANNER_MAP = {
        ThemeName.CYBER: "banner_cyber.png",
        ThemeName.DARK: "banner_amber.png",
        ThemeName.LIGHT: "banner_light.png",
    }

    def __init__(self, theme_name: ThemeName = ThemeName.CYBER,
                 max_width: int = 320, max_height: int = 120, parent=None):
        super().__init__(parent)
        self._theme_name = theme_name
        self._max_width = max_width
        self._max_height = max_height
        self._assets_path = self._find_assets_path()

        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent; border: none;")

        self._load_banner()

    def _find_assets_path(self) -> Path:
        """Locate the assets directory."""
        # Try relative to this file
        local_path = Path(__file__).parent / "assets"
        if local_path.exists():
            return local_path

        # Try from package root
        package_path = Path(__file__).parent.parent / "ui" / "assets"
        if package_path.exists():
            return package_path

        # Fallback - current directory
        return Path("assets")

    def _load_banner(self):
        """Load and display the banner for current theme."""
        banner_file = self.BANNER_MAP.get(self._theme_name, "banner_cyber.png")
        banner_path = self._assets_path / banner_file

        if banner_path.exists():
            pixmap = QPixmap(str(banner_path))

            # Scale while preserving aspect ratio
            scaled = pixmap.scaled(
                self._max_width,
                self._max_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.setPixmap(scaled)
            self.setFixedSize(scaled.size())
        else:
            # Fallback to text if image not found
            self.setText(f"[Banner: {banner_file}]")
            self.setFixedSize(self._max_width, self._max_height)

    def set_theme(self, theme_name: ThemeName):
        """Switch to a different theme's banner."""
        if theme_name != self._theme_name:
            self._theme_name = theme_name
            self._load_banner()

    def set_max_size(self, width: int, height: int):
        """Update maximum dimensions and reload."""
        self._max_width = width
        self._max_height = height
        self._load_banner()


class PasswordInput(QWidget):
    """
    Styled password input with visibility toggle,
    matching the mockup's ThemedInput component.
    """

    textChanged = pyqtSignal(str)
    returnPressed = pyqtSignal()

    def __init__(self, placeholder: str = "Enter password...", parent=None):
        super().__init__(parent)
        self._setup_ui(placeholder)

    def _setup_ui(self, placeholder: str):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Container frame for styling
        self.container = QFrame()
        self.container.setObjectName("passwordContainer")
        container_layout = QHBoxLayout(self.container)
        container_layout.setContentsMargins(12, 0, 8, 0)
        container_layout.setSpacing(8)

        # Shield icon (as text for simplicity)
        self.icon_label = QLabel("🛡")
        self.icon_label.setStyleSheet("background: transparent; border: none;")
        container_layout.addWidget(self.icon_label)

        # Password input
        self.input = QLineEdit()
        self.input.setPlaceholderText(placeholder)
        self.input.setEchoMode(QLineEdit.EchoMode.Password)
        self.input.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                padding: 10px 0;
                font-size: 14px;
            }
        """)
        self.input.textChanged.connect(self.textChanged.emit)
        self.input.returnPressed.connect(self.returnPressed.emit)
        container_layout.addWidget(self.input, 1)

        # Visibility toggle
        self.toggle_btn = QPushButton("👁")
        self.toggle_btn.setFixedSize(32, 32)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                opacity: 0.7;
            }
        """)
        self.toggle_btn.clicked.connect(self._toggle_visibility)
        container_layout.addWidget(self.toggle_btn)

        layout.addWidget(self.container)

        self._visible = False

    def _toggle_visibility(self):
        self._visible = not self._visible
        if self._visible:
            self.input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_btn.setText("🔒")
        else:
            self.input.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_btn.setText("👁")

    def text(self) -> str:
        return self.input.text()

    def setText(self, text: str):
        self.input.setText(text)

    def clear(self):
        self.input.clear()

    def setFocus(self):
        self.input.setFocus()

    def apply_theme(self, theme: ThemeColors):
        """Apply theme colors to the input."""
        # Compute theme-appropriate colors
        if theme.name == "Cyber":
            bg_input = "#0a1a1a"
            border_dim = "#1a3a3a"
        elif theme.name == "Dark":
            bg_input = "#1a1508"
            border_dim = "#2a2510"
        else:  # Light
            bg_input = "#f5f5f5"
            border_dim = "#d0d0d0"

        self.container.setStyleSheet(f"""
            QFrame#passwordContainer {{
                background-color: {bg_input};
                border: 1px solid {border_dim};
                border-radius: 8px;
            }}
        """)
        self.icon_label.setStyleSheet(f"""
            background: transparent; 
            border: none;
            color: {theme.text_muted};
        """)
        self.input.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                border: none;
                padding: 10px 0;
                font-size: 14px;
                color: {theme.text_primary};
            }}
        """)
        self.toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                font-size: 14px;
                color: {theme.text_muted};
            }}
            QPushButton:hover {{
                color: {theme.accent};
            }}
        """)


class LoginDialog(QDialog):
    """
    Vault login dialog.

    Handles:
    - First-time vault initialization
    - Vault unlock with password
    - Vault reset (delete and reinitialize)

    Signals:
        vault_unlocked: Emitted when vault is successfully unlocked
    """

    vault_unlocked = pyqtSignal(object)  # Emits the unlocked vault

    def __init__(
        self,
        vault,  # CredentialVault instance
        theme_manager: ThemeManager,
        settings: Optional[SettingsManager] = None,
        parent=None
    ):
        super().__init__(parent)
        self.vault = vault
        self.theme_manager = theme_manager
        self.settings = settings or get_settings()

        self.setWindowTitle("Secure Cartography")
        self.setFixedSize(420, 620)  # Fixed size for clean layout
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._setup_ui()
        self._apply_theme()

    def _setup_ui(self):
        """Build the login dialog UI."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Content card
        self.card = QFrame()
        self.card.setObjectName("loginCard")
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(32, 24, 32, 24)
        card_layout.setSpacing(0)  # Control spacing manually

        # Top accent line
        self.accent_line = QFrame()
        self.accent_line.setFixedHeight(3)
        self.accent_line.setObjectName("accentLine")
        card_layout.addWidget(self.accent_line)

        # Theme selector row (right-aligned)
        theme_row = QHBoxLayout()
        theme_row.setContentsMargins(0, 12, 0, 0)
        theme_row.addStretch()

        self.theme_combo = StyledComboBox()
        self.theme_combo.setFixedWidth(120)
        self.theme_combo.setFixedHeight(32)
        self.theme_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_combo.addItem("⚡ Cyber", ThemeName.CYBER)
        self.theme_combo.addItem("🌙 Dark", ThemeName.DARK)
        self.theme_combo.addItem("☀️ Light", ThemeName.LIGHT)

        # Set popup colors from current theme
        self.theme_combo.set_theme_colors(self.theme_manager.theme)

        # Set current theme from settings
        current_theme = self.theme_manager.theme_name
        for i in range(self.theme_combo.count()):
            if self.theme_combo.itemData(i) == current_theme:
                self.theme_combo.setCurrentIndex(i)
                break

        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        theme_row.addWidget(self.theme_combo)

        card_layout.addLayout(theme_row)

        # Spacer
        card_layout.addSpacing(16)

        # Banner image (theme-aware)
        banner_container = QWidget()
        banner_container.setObjectName("bannerContainer")
        banner_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        banner_layout = QHBoxLayout(banner_container)
        banner_layout.setContentsMargins(0, 0, 0, 0)
        banner_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.banner = ThemeBanner(
            theme_name=self.theme_manager.theme_name,
            max_width=320,
            max_height=100
        )
        banner_layout.addWidget(self.banner)

        card_layout.addWidget(banner_container)

        # Spacer
        card_layout.addSpacing(16)

        # Title
        self.title_label = QLabel("SECURE CARTOGRAPHY")
        self.title_label.setObjectName("heading")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setFixedHeight(28)
        font = self.title_label.font()
        font.setPointSize(18)
        font.setBold(True)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
        self.title_label.setFont(font)
        card_layout.addWidget(self.title_label)

        # Spacer
        card_layout.addSpacing(8)

        # Subtitle
        self.subtitle_label = QLabel("SSH-Based Network Discovery & Mapping")
        self.subtitle_label.setObjectName("subheading")
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setFixedHeight(20)
        card_layout.addWidget(self.subtitle_label)

        # Spacer before form
        card_layout.addSpacing(28)

        # Password section
        form_container = QWidget()
        form_container.setObjectName("formContainer")
        form_container.setAutoFillBackground(False)
        form_layout = QVBoxLayout(form_container)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(10)

        self.password_label = QLabel("MASTER PASSWORD")
        self.password_label.setObjectName("sectionTitle")
        self.password_label.setFixedHeight(16)
        form_layout.addWidget(self.password_label)

        self.password_input = PasswordInput("Enter master key...")
        self.password_input.setFixedHeight(48)
        form_layout.addWidget(self.password_input)

        # Status message (for errors)
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusError")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setFixedHeight(40)
        self.status_label.hide()
        form_layout.addWidget(self.status_label)

        self.form_container = form_container  # Save reference for styling
        card_layout.addWidget(form_container)

        # Spacer before buttons
        card_layout.addSpacing(24)

        # Buttons
        button_container = QWidget()
        button_container.setObjectName("buttonContainer")
        button_layout = QVBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(12)

        self.unlock_btn = QPushButton("🛡  UNLOCK SYSTEM")
        self.unlock_btn.setFixedHeight(48)
        self.unlock_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.unlock_btn.clicked.connect(self._on_unlock)
        button_layout.addWidget(self.unlock_btn)

        self.reset_btn = QPushButton("↺  RESET CREDENTIALS")
        self.reset_btn.setFixedHeight(48)
        self.reset_btn.setObjectName("danger")
        self.reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_btn.clicked.connect(self._on_reset)
        button_layout.addWidget(self.reset_btn)

        self.button_container = button_container  # Save reference for styling
        card_layout.addWidget(button_container)

        # Spacer before version
        card_layout.addSpacing(24)

        # Version info
        self.version_label = QLabel("v2.0.0")
        self.version_label.setObjectName("muted")
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.version_label.setFixedHeight(16)
        card_layout.addWidget(self.version_label)

        # Bottom padding
        card_layout.addSpacing(8)

        main_layout.addWidget(self.card)

        # Connect enter key
        self.password_input.returnPressed.connect(self._on_unlock)

        # Update UI based on vault state
        self._update_for_vault_state()

    def _update_for_vault_state(self):
        """Update UI based on whether vault exists."""
        if self.vault.is_initialized:
            self.unlock_btn.setText("🛡  UNLOCK SYSTEM")
            self.reset_btn.show()
        else:
            self.unlock_btn.setText("🛡  CREATE VAULT")
            self.reset_btn.hide()

    def _apply_theme(self):
        """Apply current theme to dialog."""
        theme = self.theme_manager.theme

        # Compute theme-appropriate colors
        # These approximate the rgba values from the mockup for each theme
        if theme.name == "Cyber":
            bg_input = "#0a1a1a"
            bg_hover = "#0f2626"
            border_dim = "#1a3a3a"
            border_secondary = "#2a5a5a"
            shadow_color = QColor(0, 255, 255, 50)
        elif theme.name == "Dark":
            bg_input = "#1a1508"
            bg_hover = "#1f1a0a"
            border_dim = "#2a2510"
            border_secondary = "#4a4020"
            shadow_color = QColor(0, 0, 0, 100)
        else:  # Light
            bg_input = "#f5f5f5"
            bg_hover = "#eeeeee"
            border_dim = "#d0d0d0"
            border_secondary = "#b0b8d0"
            shadow_color = QColor(0, 0, 0, 30)

        # Dialog background is transparent (for the rounded card effect)
        self.setStyleSheet("background-color: transparent;")

        # Card styling - this is the main visible background
        self.card.setStyleSheet(f"""
            QFrame#loginCard {{
                background-color: {theme.bg_secondary};
                border: 1px solid {border_secondary};
                border-radius: 16px;
            }}
        """)

        # Explicitly set all intermediate container backgrounds to transparent
        # These are layout containers that shouldn't have visible backgrounds
        transparent_style = "background-color: transparent; border: none;"
        self.form_container.setStyleSheet(transparent_style)
        self.button_container.setStyleSheet(transparent_style)

        # Add shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setXOffset(0)
        shadow.setYOffset(10)
        shadow.setColor(shadow_color)
        self.card.setGraphicsEffect(shadow)

        # Accent line gradient
        self.accent_line.setStyleSheet(f"""
            QFrame#accentLine {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 transparent,
                    stop:0.5 {theme.accent},
                    stop:1 transparent
                );
                border: none;
                border-radius: 1px;
            }}
        """)
        try:
            fix_all_comboboxes(self,self.theme_manager.theme)
        except Exception as e:
            traceback.print_exc()

        # Update banner for current theme
        self.banner.set_theme(self.theme_manager.theme_name)

        # Labels
        self.title_label.setStyleSheet(f"""
            QLabel#heading {{
                color: {theme.text_primary};
                background: transparent;
                border: none;
            }}
        """)

        self.subtitle_label.setStyleSheet(f"""
            QLabel#subheading {{
                color: {theme.text_secondary};
                background: transparent;
                border: none;
            }}
        """)

        self.password_label.setStyleSheet(f"""
            QLabel#sectionTitle {{
                color: {theme.text_secondary};
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 1px;
                background: transparent;
                border: none;
            }}
        """)

        self.status_label.setStyleSheet(f"""
            QLabel#statusError {{
                color: {theme.accent_danger};
                background: transparent;
                border: none;
                padding: 8px;
            }}
        """)

        self.version_label.setStyleSheet(f"""
            QLabel#muted {{
                color: {theme.text_muted};
                background: transparent;
                border: none;
            }}
        """)

        # Password input
        self.password_input.apply_theme(theme)

        # Theme combo box
        self.theme_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {theme.bg_tertiary};
                border: 1px solid {border_dim};
                border-radius: 6px;
                padding: 6px 12px;
                color: {theme.text_primary};
                font-size: 12px;
            }}
            QComboBox:hover {{
                border-color: {theme.accent};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid {theme.text_secondary};
                width: 0;
                height: 0;
                margin-right: 6px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {theme.bg_secondary};
                border: 1px solid {border_dim};
                selection-background-color: {theme.accent};
                selection-color: {theme.bg_primary};
                outline: none;
                padding: 4px;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 6px 12px;
                min-height: 24px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {bg_hover};
            }}
        """)

        # Update combobox popup colors for the new theme
        self.theme_combo.set_theme_colors(theme)

        # Buttons
        button_text_color = theme.bg_primary if theme.is_dark else "#ffffff"
        self.unlock_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 {theme.accent_dim},
                    stop:1 {theme.accent}
                );
                color: {button_text_color};
                border: 1px solid {theme.accent};
                border-radius: 8px;
                padding: 14px 20px;
                font-weight: 600;
                font-size: 13px;
                letter-spacing: 1px;
            }}
            QPushButton:hover {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 {theme.accent},
                    stop:1 {theme.accent_dim}
                );
            }}
            QPushButton:pressed {{
                background-color: {theme.accent_dim};
            }}
        """)

        self.reset_btn.setStyleSheet(f"""
            QPushButton#danger {{
                background-color: transparent;
                color: {theme.accent_danger};
                border: 1px solid {theme.accent_danger};
                border-radius: 8px;
                padding: 14px 20px;
                font-weight: 600;
                font-size: 13px;
                letter-spacing: 1px;
            }}
            QPushButton#danger:hover {{
                background-color: {theme.accent_danger};
                color: white;
            }}
        """)

    def _show_error(self, message: str):
        """Show error message."""
        self.status_label.setText(message)
        self.status_label.show()

    def _hide_error(self):
        """Hide error message."""
        self.status_label.hide()

    def _on_unlock(self):
        """Handle unlock/create button click."""
        password = self.password_input.text()

        if not password:
            self._show_error("Please enter a password")
            return

        self._hide_error()

        try:
            if self.vault.is_initialized:
                # Unlock existing vault
                self.vault.unlock(password)
            else:
                # Initialize new vault
                if len(password) < 8:
                    self._show_error("Password must be at least 8 characters")
                    return
                self.vault.initialize(password)

            # Success - emit signal and close
            self.vault_unlocked.emit(self.vault)
            self.accept()

        except Exception as e:
            error_msg = str(e)
            if "Invalid" in error_msg or "password" in error_msg.lower():
                self._show_error("Invalid password")
            else:
                self._show_error(f"Error: {error_msg}")
            self.password_input.clear()
            self.password_input.setFocus()

    def _on_reset(self):
        """Handle reset credentials button click."""
        reply = QMessageBox.warning(
            self,
            "Reset Credentials",
            "This will DELETE all stored credentials.\n\n"
            "This action cannot be undone.\n\n"
            "Are you sure you want to continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Delete vault database
                db_path = self.vault.db_path
                if db_path.exists():
                    db_path.unlink()

                # Also delete salt file if separate
                salt_path = db_path.parent / ".salt"
                if salt_path.exists():
                    salt_path.unlink()

                # Reinitialize vault object
                self.vault = type(self.vault)(db_path)
                self._update_for_vault_state()

                self._show_error("Vault reset. Please create a new password.")
                self.password_input.clear()
                self.password_input.setFocus()

            except Exception as e:
                self._show_error(f"Reset failed: {e}")

    def showEvent(self, event):
        """Focus password input on show."""
        super().showEvent(event)
        self.password_input.setFocus()

    def set_theme(self, theme_name: ThemeName):
        """Change theme and reapply styling."""
        self.theme_manager.set_theme(theme_name)
        self._apply_theme()

    def _on_theme_changed(self, index: int):
        """Handle theme dropdown selection."""
        theme = self.theme_combo.itemData(index)
        if theme:
            # Update theme manager
            self.theme_manager.set_theme(theme)

            # Save to settings
            self.settings.set_theme(theme)

            # Update application-wide stylesheet
            app = QApplication.instance()
            if app:
                app.setStyleSheet(self.theme_manager.stylesheet)

            # Reapply dialog-specific styling
            self._apply_theme()


# =============================================================================
# Mock Vault for Testing
# =============================================================================

class MockVault:
    """
    Mock vault for testing UI without real credentials.
    Password 'testpass' unlocks, anything else fails.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self._initialized = True
        self._unlocked = False
        self.db_path = db_path or Path.home() / ".scng" / "test_vault.db"

    @property
    def is_initialized(self):
        return self._initialized

    @property
    def is_unlocked(self):
        return self._unlocked

    def initialize(self, password):
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters")
        self._initialized = True
        self._unlocked = True

    def unlock(self, password):
        if password != "testpass":
            raise Exception("Invalid vault password")
        self._unlocked = True
        return True

    def lock(self):
        self._unlocked = False


# =============================================================================
# Standalone testing
# =============================================================================

if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)

    theme_manager = ThemeManager(ThemeName.CYBER)
    vault = MockVault()

    dialog = LoginDialog(vault, theme_manager)

    # Test theme switching
    # dialog.set_theme(ThemeName.DARK)
    # dialog.set_theme(ThemeName.LIGHT)

    if dialog.exec() == QDialog.DialogCode.Accepted:
        print("Vault unlocked successfully!")
    else:
        print("Login cancelled")

    sys.exit()