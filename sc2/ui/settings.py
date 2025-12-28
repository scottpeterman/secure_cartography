"""
SecureCartography v2 - Settings Manager

Persists application settings to ~/.scng/settings.json

Settings include:
- theme: UI theme preference (cyber/dark/light)
- (extensible for future settings)
"""

import json
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field, asdict

from .themes import ThemeName

# Default settings location
DEFAULT_SETTINGS_DIR = Path.home() / ".scng"
DEFAULT_SETTINGS_FILE = "settings.json"


@dataclass
class AppSettings:
    """
    Application settings with defaults.

    Add new settings here as needed - they'll automatically
    get defaults and be persisted.
    """
    theme: str = "cyber"

    # Discovery defaults (can be overridden in UI)
    default_max_depth: int = 3
    default_concurrency: int = 20
    default_timeout: int = 5

    # UI preferences
    window_width: int = 1400
    window_height: int = 1000

    # Recent seeds (for quick access)
    recent_seeds: list = field(default_factory=list)

    # Recent domains
    recent_domains: list = field(default_factory=list)

    def get_theme_enum(self) -> ThemeName:
        """Get theme as ThemeName enum."""
        theme_map = {
            "cyber": ThemeName.CYBER,
            "dark": ThemeName.DARK,
            "light": ThemeName.LIGHT,
        }
        return theme_map.get(self.theme, ThemeName.CYBER)

    def set_theme(self, theme: ThemeName):
        """Set theme from ThemeName enum."""
        self.theme = theme.value


class SettingsManager:
    """
    Manages persistent application settings.

    Usage:
        settings = SettingsManager()

        # Read settings
        theme = settings.get("theme")

        # Write settings
        settings.set("theme", "dark")
        settings.save()

        # Or use the typed settings object
        settings.settings.theme = "light"
        settings.save()
    """

    def __init__(self, settings_dir: Optional[Path] = None):
        """
        Initialize settings manager.

        Args:
            settings_dir: Directory for settings file.
                         Defaults to ~/.scng/
        """
        self._settings_dir = settings_dir or DEFAULT_SETTINGS_DIR
        self._settings_file = self._settings_dir / DEFAULT_SETTINGS_FILE
        self._settings = AppSettings()

        # Ensure directory exists
        self._settings_dir.mkdir(parents=True, exist_ok=True)

        # Load existing settings
        self.load()

    @property
    def settings(self) -> AppSettings:
        """Get the settings object."""
        return self._settings

    @property
    def settings_path(self) -> Path:
        """Get path to settings file."""
        return self._settings_file

    def load(self) -> AppSettings:
        """
        Load settings from disk.

        Returns:
            Loaded settings (or defaults if file doesn't exist).
        """
        if not self._settings_file.exists():
            return self._settings

        try:
            with open(self._settings_file, 'r') as f:
                data = json.load(f)

            # Update settings from loaded data
            for key, value in data.items():
                if hasattr(self._settings, key):
                    setattr(self._settings, key, value)

        except (json.JSONDecodeError, IOError) as e:
            # If settings file is corrupted, just use defaults
            print(f"Warning: Could not load settings: {e}")

        return self._settings

    def save(self) -> bool:
        """
        Save settings to disk.

        Returns:
            True if successful, False otherwise.
        """
        try:
            with open(self._settings_file, 'w') as f:
                json.dump(asdict(self._settings), f, indent=2)
            return True
        except IOError as e:
            print(f"Warning: Could not save settings: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a setting value.

        Args:
            key: Setting name.
            default: Default if setting doesn't exist.

        Returns:
            Setting value or default.
        """
        return getattr(self._settings, key, default)

    def set(self, key: str, value: Any) -> bool:
        """
        Set a setting value.

        Args:
            key: Setting name.
            value: Value to set.

        Returns:
            True if setting exists and was set.
        """
        if hasattr(self._settings, key):
            setattr(self._settings, key, value)
            return True
        return False

    def reset(self):
        """Reset all settings to defaults."""
        self._settings = AppSettings()
        self.save()

    # Convenience methods for common settings

    def get_theme(self) -> ThemeName:
        """Get current theme as enum."""
        return self._settings.get_theme_enum()

    def set_theme(self, theme: ThemeName):
        """Set theme and save."""
        self._settings.set_theme(theme)
        self.save()

    def add_recent_seed(self, seed: str, max_recent: int = 10):
        """Add a seed to recent list."""
        seeds = self._settings.recent_seeds
        if seed in seeds:
            seeds.remove(seed)
        seeds.insert(0, seed)
        self._settings.recent_seeds = seeds[:max_recent]
        self.save()

    def add_recent_domain(self, domain: str, max_recent: int = 5):
        """Add a domain to recent list."""
        domains = self._settings.recent_domains
        if domain in domains:
            domains.remove(domain)
        domains.insert(0, domain)
        self._settings.recent_domains = domains[:max_recent]
        self.save()


# Global settings instance (lazy loaded)
_settings_manager: Optional[SettingsManager] = None


def get_settings() -> SettingsManager:
    """
    Get the global settings manager instance.

    Creates the instance on first call (lazy loading).
    """
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    return _settings_manager