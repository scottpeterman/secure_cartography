"""
SC2 Platform Icon Manager
Loads platform-to-icon mapping from platform_icon_map.json and resolves to actual icon files.

Usage:
    from platform_icons import get_platform_icon_manager

    manager = get_platform_icon_manager()
    icon_url = manager.get_icon_url('Cisco C9300')
    # Returns: 'file:///path/to/icons_lib/layer_3_switch.jpg'
"""

import json
import re
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass, field


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

    # Loaded from JSON
    platform_patterns: Dict[str, str] = field(default_factory=dict)
    defaults: Dict[str, str] = field(default_factory=dict)
    fallback_patterns: Dict[str, dict] = field(default_factory=dict)

    def __post_init__(self):
        """Load configuration on init."""
        if self.config_path is None:
            # Default location relative to this module
            self.config_path = self._find_config_path()

        if self.config_path and self.config_path.exists():
            self._load_config()
        else:
            self._load_builtin_defaults()

    def _find_config_path(self) -> Optional[Path]:
        """Find platform_icon_map.json in expected locations."""
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

    def _load_config(self):
        """Load configuration from JSON file."""
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

        # Find icons directory
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

    def get_icon_path(self, platform: str, device_name: str = "") -> Optional[Path]:
        """
        Get full path to icon file.

        Returns:
            Path object or None if not found
        """
        icon_filename = self.get_icon_for_platform(platform, device_name)
        if not icon_filename or not self.icons_dir:
            return None

        icon_path = self.icons_dir / icon_filename
        if icon_path.exists():
            return icon_path

        # Try without extension variations
        for ext in ['.jpg', '.png', '.svg', '.gif']:
            alt_path = self.icons_dir / (icon_filename.rsplit('.', 1)[0] + ext)
            if alt_path.exists():
                return alt_path

        return None

    def get_icon_url(self, platform: str, device_name: str = "") -> str:
        """
        Get icon as file:// URL for use in web views.

        Args:
            platform: Platform string
            device_name: Optional device name for fallback matching

        Returns:
            file:// URL string, or data: URL fallback
        """
        icon_path = self.get_icon_path(platform, device_name)

        if icon_path and icon_path.exists():
            return icon_path.as_uri()

        # Fallback to inline SVG
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
        if not self.icons_dir or not self.icons_dir.exists():
            return []

        icons = []
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
    print(f"Platform patterns: {len(manager.platform_patterns)}")
    print(f"Fallback patterns: {len(manager.fallback_patterns)}")
    print(f"Available icons: {len(manager.get_available_icons())}")
    print()

    test_platforms = [
        ("Cisco C9300-48P", "core-sw-01"),
        ("Cisco Nexus9000", "dc-spine-01"),
        ("Arista DCS-7050", "leaf-sw-01"),
        ("Juniper QFX5100", "edge-sw-01"),
        ("Cisco ISR4331", "branch-rtr-01"),
        ("Cisco ASA 5525", "fw-01"),
        ("Linux", "server-01"),
        ("Unknown Platform", "mystery-device"),
    ]

    for platform, name in test_platforms:
        icon = manager.get_icon_for_platform(platform, name)
        path = manager.get_icon_path(platform, name)
        exists = "✓" if path and path.exists() else "✗"
        print(f"{platform:25} -> {icon:30} [{exists}]")