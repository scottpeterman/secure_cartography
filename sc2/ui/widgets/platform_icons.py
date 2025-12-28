"""
SC2 Platform Icon Manager
Loads platform-to-icon mapping from platform_icon_map.json and resolves to actual icon files.

Updated for wheel compatibility using importlib.resources.

Usage:
    from platform_icons import get_platform_icon_manager

    manager = get_platform_icon_manager()
    icon_url = manager.get_icon_url('Cisco C9300')
    # Returns: 'file:///path/to/icons_lib/layer_3_switch.jpg'
"""

import json
import sys
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass, field

# importlib.resources for package resource access (works in wheels)
if sys.version_info >= (3, 9):
    from importlib.resources import files, as_file
else:
    # pip install importlib_resources for Python 3.7-3.8
    from importlib_resources import files, as_file


# Package containing platform_icon_map.json and icons
# Adjust to match your actual package structure
ICONS_PACKAGE = 'sc2.ui.assets.icons_lib'
CONFIG_FILENAME = 'platform_icon_map.json'


@dataclass
class PlatformIconManager:
    """
    Manages platform-to-icon mappings using the VelocityMaps icon library.

    Loads configuration from platform_icon_map.json which contains:
    - platform_patterns: Direct platform string -> icon mappings
    - defaults: Default icons by device category
    - fallback_patterns: Pattern-based matching when direct match fails
    """

    config_path: Optional[Path] = None
    icons_dir: Optional[Path] = None
    _icons_package: Optional[str] = None  # For importlib.resources access

    # Loaded from JSON
    platform_patterns: Dict[str, str] = field(default_factory=dict)
    defaults: Dict[str, str] = field(default_factory=dict)
    fallback_patterns: Dict[str, dict] = field(default_factory=dict)

    def __post_init__(self):
        """Load configuration on init."""
        # Try package resources first (works in wheels)
        if self._try_load_from_package():
            return

        # Fallback to filesystem paths (dev mode)
        if self.config_path is None:
            self.config_path = self._find_config_path_filesystem()

        if self.config_path and self.config_path.exists():
            self._load_config_from_file()
        else:
            self._load_builtin_defaults()

    def _try_load_from_package(self) -> bool:
        """
        Try to load config from package resources (importlib.resources).
        Returns True if successful, False to fall back to filesystem.
        """
        try:
            pkg_files = files(ICONS_PACKAGE)
            config_traversable = pkg_files.joinpath(CONFIG_FILENAME)

            # Try to read the config
            config_text = config_traversable.read_text(encoding='utf-8')
            config = json.loads(config_text)

            # Successfully loaded - store package reference for icon loading
            self._icons_package = ICONS_PACKAGE

            # Try to get a real filesystem path for icons_dir (optional, for compatibility)
            try:
                # This works for editable installs and unzipped packages
                with as_file(pkg_files) as pkg_path:
                    self.icons_dir = Path(pkg_path)
            except Exception:
                # Zipped package - icons_dir stays None, we'll use _icons_package
                self.icons_dir = None

            # Load the config data
            self.platform_patterns = config.get('platform_patterns', {})
            self.defaults = config.get('defaults', {})
            self.fallback_patterns = config.get('fallback_patterns', {})

            return True

        except Exception as e:
            # Package resources not available - fall back to filesystem
            return False

    def _find_config_path_filesystem(self) -> Optional[Path]:
        """Find platform_icon_map.json in expected filesystem locations (dev mode)."""
        module_dir = Path(__file__).parent

        candidates = [
            # Relative to widgets/ -> ui/assets/icons_lib/
            module_dir.parent / 'assets' / 'icons_lib' / 'platform_icon_map.json',
            # Relative to ui/ -> assets/icons_lib/
            module_dir / 'assets' / 'icons_lib' / 'platform_icon_map.json',
            # Direct in module dir
            module_dir / 'platform_icon_map.json',
            # Up one level
            module_dir.parent / 'platform_icon_map.json',
        ]

        for path in candidates:
            if path.exists():
                return path

        return None

    def _load_config_from_file(self):
        """Load configuration from JSON file on filesystem."""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)

            # Set icons directory relative to config file
            base_path = config.get('base_path', 'icons_lib')
            self.icons_dir = self.config_path.parent / base_path
            if not self.icons_dir.exists():
                # Try just using the config's parent directory
                self.icons_dir = self.config_path.parent

            self.platform_patterns = config.get('platform_patterns', {})
            self.defaults = config.get('defaults', {})
            self.fallback_patterns = config.get('fallback_patterns', {})

        except (IOError, json.JSONDecodeError) as e:
            print(f"[PlatformIconManager] Failed to load config: {e}")
            self._load_builtin_defaults()

    def _load_builtin_defaults(self):
        """Fallback defaults if no config file found."""
        self.defaults = {
            'default_switch': 'layer_3_switch.jpg',
            'default_router': 'router.jpg',
            'default_firewall': 'firewall.jpg',
            'default_endpoint': 'pc.jpg',
            'default_wireless': 'wireless.jpg',
            'default_unknown': 'generic_processor.jpg',
            'default_phone': 'ip_phone.jpg',
            'default_ata': 'ata.jpg',
        }

        # Try package resources first
        try:
            pkg_files = files(ICONS_PACKAGE)
            self._icons_package = ICONS_PACKAGE
            try:
                with as_file(pkg_files) as pkg_path:
                    self.icons_dir = Path(pkg_path)
            except Exception:
                self.icons_dir = None
            return
        except Exception:
            pass

        # Fall back to filesystem paths
        module_dir = Path(__file__).parent
        candidates = [
            module_dir.parent / 'assets' / 'icons_lib',
            module_dir / 'assets' / 'icons_lib',
            module_dir / 'icons',
        ]

        for path in candidates:
            if path.exists():
                self.icons_dir = path
                break

    def get_icon_for_platform(self, platform: str, device_name: str = "") -> Optional[str]:
        """
        Get icon filename for a platform string.

        Args:
            platform: Platform/model string (e.g., "Cisco C9300-48P")
            device_name: Optional device hostname for fallback matching

        Returns:
            Icon filename or None
        """
        if not platform:
            return self._get_default_icon('unknown')

        platform_lower = platform.lower()

        # 1. Try direct platform pattern matches (case-insensitive substring)
        for pattern, icon in self.platform_patterns.items():
            if pattern.lower() in platform_lower:
                return icon

        # 2. Try fallback pattern matching
        device_name_lower = device_name.lower() if device_name else ""

        for category, config in self.fallback_patterns.items():
            # Check platform patterns
            for pattern in config.get('platform_patterns', []):
                if pattern.lower() in platform_lower:
                    default_key = config.get('icon', f'default_{category}')
                    return self.defaults.get(default_key)

            # Check name patterns if device_name provided
            if device_name_lower:
                for pattern in config.get('name_patterns', []):
                    if pattern.lower() in device_name_lower:
                        default_key = config.get('icon', f'default_{category}')
                        return self.defaults.get(default_key)

        # 3. Infer from common keywords
        icon = self._infer_icon_from_platform(platform_lower)
        if icon:
            return icon

        # 4. Return unknown default
        return self._get_default_icon('unknown')

    def _infer_icon_from_platform(self, platform_lower: str) -> Optional[str]:
        """Infer device type from platform string keywords."""
        if any(kw in platform_lower for kw in ['switch', 'nexus', 'catalyst', 'c9', 'ws-c', 'dcs', 'qfx', 'ex']):
            return self._get_default_icon('switch')
        if any(kw in platform_lower for kw in ['router', 'isr', 'asr', 'csr', 'mx']):
            return self._get_default_icon('router')
        if any(kw in platform_lower for kw in ['firewall', 'asa', 'ftd', 'palo', 'srx']):
            return self._get_default_icon('firewall')
        if any(kw in platform_lower for kw in ['wireless', 'ap', 'wlc', 'aironet']):
            return self._get_default_icon('wireless')
        if any(kw in platform_lower for kw in ['phone', 'sep']):
            return self._get_default_icon('phone')
        if any(kw in platform_lower for kw in ['ata', 'vg']):
            return self._get_default_icon('ata')
        if any(kw in platform_lower for kw in ['linux', 'debian', 'ubuntu', 'centos', 'server']):
            return self._get_default_icon('endpoint')

        return None

    def _get_default_icon(self, device_type: str) -> Optional[str]:
        """Get default icon for device type."""
        key = f'default_{device_type}'
        return self.defaults.get(key, self.defaults.get('default_unknown'))

    def _read_icon_bytes(self, icon_filename: str) -> Optional[bytes]:
        """
        Read icon file bytes, using package resources or filesystem.
        """
        # Try package resources first
        if self._icons_package:
            try:
                pkg_files = files(self._icons_package)
                icon_traversable = pkg_files.joinpath(icon_filename)
                return icon_traversable.read_bytes()
            except Exception:
                pass

            # Try alternate extensions
            base_name = icon_filename.rsplit('.', 1)[0] if '.' in icon_filename else icon_filename
            for ext in ['.jpg', '.png', '.svg', '.gif']:
                try:
                    icon_traversable = pkg_files.joinpath(base_name + ext)
                    return icon_traversable.read_bytes()
                except Exception:
                    continue

        # Fall back to filesystem
        if self.icons_dir:
            icon_path = self.icons_dir / icon_filename
            if icon_path.exists():
                return icon_path.read_bytes()

            # Try alternate extensions
            base_name = icon_filename.rsplit('.', 1)[0] if '.' in icon_filename else icon_filename
            for ext in ['.jpg', '.png', '.svg', '.gif']:
                alt_path = self.icons_dir / (base_name + ext)
                if alt_path.exists():
                    return alt_path.read_bytes()

        return None

    def get_icon_path(self, platform: str, device_name: str = "") -> Optional[Path]:
        """
        Get full path to icon file.

        Note: May return None for zipped packages. Use get_icon_bytes() for
        guaranteed access in all installation types.

        Returns:
            Path object or None if not found
        """
        icon_filename = self.get_icon_for_platform(platform, device_name)
        if not icon_filename:
            return None

        # Try to get a real filesystem path
        if self._icons_package:
            try:
                pkg_files = files(self._icons_package)
                icon_traversable = pkg_files.joinpath(icon_filename)
                # Use as_file to get a real path (extracts if needed)
                with as_file(icon_traversable) as real_path:
                    if real_path.exists():
                        return real_path
            except Exception:
                pass

        # Fall back to icons_dir
        if self.icons_dir:
            icon_path = self.icons_dir / icon_filename
            if icon_path.exists():
                return icon_path

            # Try without extension variations
            for ext in ['.jpg', '.png', '.svg', '.gif']:
                alt_path = self.icons_dir / (icon_filename.rsplit('.', 1)[0] + ext)
                if alt_path.exists():
                    return alt_path

        return None

    def get_icon_bytes(self, platform: str, device_name: str = "") -> Optional[bytes]:
        """
        Get icon file as bytes. Works reliably in all installation types.

        Args:
            platform: Platform string
            device_name: Optional device name for fallback matching

        Returns:
            Icon file bytes or None
        """
        icon_filename = self.get_icon_for_platform(platform, device_name)
        if not icon_filename:
            return None
        return self._read_icon_bytes(icon_filename)

    def get_icon_base64(self, platform: str, device_name: str = "") -> Optional[str]:
        """
        Get icon as base64-encoded string. Useful for embedding in HTML/GraphML.

        Returns:
            Base64 string or None
        """
        import base64
        icon_bytes = self.get_icon_bytes(platform, device_name)
        if icon_bytes:
            return base64.b64encode(icon_bytes).decode('utf-8')
        return None

    def get_icon_url(self, platform: str, device_name: str = "") -> str:
        """
        Get icon as URL for use in web views.

        Args:
            platform: Platform string
            device_name: Optional device name for fallback matching

        Returns:
            file:// URL, data: URL, or fallback SVG URL
        """
        # Try to get a file path first
        icon_path = self.get_icon_path(platform, device_name)
        if icon_path and icon_path.exists():
            return icon_path.as_uri()

        # Fall back to data: URL with embedded image
        icon_bytes = self.get_icon_bytes(platform, device_name)
        if icon_bytes:
            import base64
            # Detect mime type from first bytes
            if icon_bytes[:3] == b'\xff\xd8\xff':
                mime = 'image/jpeg'
            elif icon_bytes[:8] == b'\x89PNG\r\n\x1a\n':
                mime = 'image/png'
            elif icon_bytes[:4] == b'GIF8':
                mime = 'image/gif'
            elif b'<svg' in icon_bytes[:100]:
                mime = 'image/svg+xml'
            else:
                mime = 'application/octet-stream'

            b64 = base64.b64encode(icon_bytes).decode('utf-8')
            return f'data:{mime};base64,{b64}'

        # Final fallback to inline SVG
        return self._get_fallback_svg_url(platform)

    def _get_fallback_svg_url(self, platform: str) -> str:
        """Generate inline SVG data URL as fallback."""
        platform_lower = (platform or '').lower()

        # Determine device type for SVG color
        if any(kw in platform_lower for kw in ['switch', 'nexus', 'catalyst', 'c9', 'dcs']):
            fill, stroke = '#2a4a7a', '#4a9eff'
        elif any(kw in platform_lower for kw in ['router', 'isr', 'asr']):
            fill, stroke = '#4a2a7a', '#9a4aff'
        elif any(kw in platform_lower for kw in ['firewall', 'asa']):
            fill, stroke = '#7a2a2a', '#ff4a4a'
        else:
            fill, stroke = '#3a3a3a', '#888888'

        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
            <rect x="4" y="14" width="40" height="20" rx="3" fill="{fill}" stroke="{stroke}" stroke-width="2"/>
            <circle cx="12" cy="24" r="2" fill="#00ff88"/>
            <circle cx="18" cy="24" r="2" fill="#00ff88"/>
            <circle cx="24" cy="24" r="2" fill="#ffaa00"/>
        </svg>'''

        from urllib.parse import quote
        return 'data:image/svg+xml,' + quote(svg.strip())

    def to_json(self) -> str:
        """Export current config as JSON (for JS viewer)."""
        return json.dumps({
            'base_path': str(self.icons_dir) if self.icons_dir else '',
            'platform_patterns': self.platform_patterns,
            'defaults': self.defaults,
        })

    def get_available_icons(self) -> List[str]:
        """List all available icon files."""
        icons = []

        # Try package resources first
        if self._icons_package:
            try:
                pkg_files = files(self._icons_package)
                for item in pkg_files.iterdir():
                    if item.name.endswith(('.jpg', '.png', '.svg', '.gif')):
                        icons.append(item.name)
                if icons:
                    return sorted(icons)
            except Exception:
                pass

        # Fall back to filesystem
        if self.icons_dir and self.icons_dir.exists():
            for ext in ['*.jpg', '*.png', '*.svg', '*.gif']:
                icons.extend([p.name for p in self.icons_dir.glob(ext)])

        return sorted(icons)


# =============================================================================
# Global instance
# =============================================================================

_default_manager: Optional[PlatformIconManager] = None


def get_platform_icon_manager() -> PlatformIconManager:
    """Get the default platform icon manager instance."""
    global _default_manager
    if _default_manager is None:
        _default_manager = PlatformIconManager()
    return _default_manager


def get_icon_url(platform: str, device_name: str = "") -> str:
    """Convenience function to get icon URL for platform."""
    return get_platform_icon_manager().get_icon_url(platform, device_name)


# =============================================================================
# Test
# =============================================================================

if __name__ == '__main__':
    manager = PlatformIconManager()

    print("Platform Icon Manager Test")
    print("=" * 60)
    print(f"Config path: {manager.config_path}")
    print(f"Icons dir: {manager.icons_dir}")
    print(f"Icons package: {manager._icons_package}")
    print(f"Platform patterns: {len(manager.platform_patterns)}")
    print(f"Fallback patterns: {len(manager.fallback_patterns)}")
    print(f"Available icons: {len(manager.get_available_icons())}")
    print()

    test_platforms = [
        ("Cisco C9300-48P", "core-sw-01"),
        ("Cisco Nexus9000", "dc-spine-01"),
        ("Arista DCS-7050", "leaf-sw-01"),
        ("Juniper QFX5100", "edge-sw-01"),
        ("Cisco ISR", "branch-rtr-01"),
        ("Cisco ASA", "fw-01"),
        ("Linux", "server-01"),
        ("Unknown Platform", "mystery-device"),
    ]

    for platform, name in test_platforms:
        icon = manager.get_icon_for_platform(platform, name)
        icon_bytes = manager.get_icon_bytes(platform, name)
        exists = "✓" if icon_bytes else "✗"
        print(f"{platform:25} -> {icon:30} [{exists}]")