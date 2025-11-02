// Platform Manager - Loads and manages platform icon mappings
class PlatformManager {
    constructor() {
        this.platformMap = null;
        this.platforms = [];
        this.iconCache = {};
        this.loaded = false;
        this.loading = false;
    }

    async loadPlatformMap() {
        if (this.loaded) {
            console.log('Platform map already loaded');
            return true;
        }

        if (this.loading) {
            console.log('Platform map is currently loading...');
            // Wait for existing load to complete
            return new Promise((resolve) => {
                const checkInterval = setInterval(() => {
                    if (!this.loading) {
                        clearInterval(checkInterval);
                        resolve(this.loaded);
                    }
                }, 100);
            });
        }

        this.loading = true;

        try {
            console.log('Loading platform map from /api/platform-map');
            const response = await fetch('/api/platform-map');

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            this.platformMap = await response.json();
            console.log('Platform map loaded successfully:', this.platformMap);

            this.buildPlatformList();
            this.loaded = true;
            this.loading = false;

            console.log(`Built ${this.platforms.length} platform options`);
            return true;

        } catch (error) {
            console.error('Failed to load platform map:', error);

            // Use minimal fallback
            this.platformMap = {
                base_path: 'static/icons_lib',
                platform_patterns: {
                    'Cisco IOS': 'router.jpg',
                    'Cisco Nexus': 'Nexus_7000.jpg',
                    'Arista EOS': 'Nexus_5000.jpg',
                    'Generic Switch': 'layer_3_switch.jpg',
                    'Generic Router': 'router.jpg'
                },
                defaults: {
                    default_unknown: 'generic_processor.jpg',
                    default_switch: 'layer_3_switch.jpg',
                    default_router: 'router.jpg'
                }
            };

            console.log('Using fallback platform map');
            this.buildPlatformList();
            this.loaded = true;
            this.loading = false;

            return false;
        }
    }

    buildPlatformList() {
    const platforms = [];

    // Normalize base_path
    let basePath = this.platformMap.base_path || 'icons_lib';

    // Ensure it starts with /static/
    if (!basePath.startsWith('/')) {
        basePath = '/' + basePath;
    }
    if (!basePath.startsWith('/static/')) {
        basePath = '/static/' + basePath.replace(/^static\//, '');
    }

    // Add all platform patterns
    if (this.platformMap.platform_patterns) {
        for (const [pattern, icon] of Object.entries(this.platformMap.platform_patterns)) {
            platforms.push({
                value: pattern,
                label: pattern,
                icon: `${basePath}/${icon}`,
                category: this.categorizePattern(pattern)
            });
        }
    }

    // Add defaults as options
    if (this.platformMap.defaults) {
        for (const [key, icon] of Object.entries(this.platformMap.defaults)) {
            const label = key.replace('default_', '').replace('_', ' ');
            platforms.push({
                value: `Generic ${label}`,
                label: `Generic ${label.charAt(0).toUpperCase() + label.slice(1)}`,
                icon: `${basePath}/${icon}`,
                category: 'Generic'
            });
        }
    }

    this.platforms = platforms;
    console.log('Platform list built:', this.platforms.length, 'platforms');
    console.log('Sample icon path:', this.platforms[0]?.icon);
}
    categorizePattern(pattern) {
        const p = pattern.toLowerCase();

        // Cisco
        if (p.startsWith('c9') || p.startsWith('ws-c') ||
            p.includes('nexus') || p.startsWith('isr') ||
            p.startsWith('cisco') || p.includes('catalyst')) {
            return 'Cisco';
        }

        // Arista
        if (p.startsWith('dcs-') || p.includes('arista') || p === 'veos') {
            return 'Arista';
        }

        // Juniper
        if (p.includes('juniper') || p.includes('qfx')) {
            return 'Juniper';
        }

        // Linux/Unix
        if (p.includes('linux') || p.includes('debian') || p.includes('ubuntu')) {
            return 'Linux/Unix';
        }

        // Voice
        if (p.includes('phone') || p === 'sep' || p === 'ata' || p === 'vg') {
            return 'Voice';
        }

        return 'Other';
    }

    getGroupedPlatforms() {
        const grouped = {};

        for (const platform of this.platforms) {
            if (!grouped[platform.category]) {
                grouped[platform.category] = [];
            }
            grouped[platform.category].push(platform);
        }

        // Sort categories
        const sortOrder = ['Cisco', 'Arista', 'Juniper', 'Voice', 'Linux/Unix', 'Other', 'Generic'];
        const sorted = {};

        for (const category of sortOrder) {
            if (grouped[category]) {
                sorted[category] = grouped[category].sort((a, b) =>
                    a.label.localeCompare(b.label)
                );
            }
        }

        return sorted;
    }

    getIconForPlatform(platformValue) {
    // Check if platform map is loaded
    if (!this.platformMap) {
        console.warn('Platform map not loaded yet, returning generic icon');
        return '/static/icons_lib/generic_processor.jpg';
    }

    const platform = this.platforms.find(p => p.value === platformValue);
    if (platform) {
        // Ensure path starts with /static/
        let iconPath = platform.icon;
        if (!iconPath.startsWith('/')) {
            iconPath = '/' + iconPath;
        }
        if (!iconPath.startsWith('/static/')) {
            iconPath = '/static/' + iconPath.replace(/^static\//, '');
        }
        return iconPath;
    }

    // Fallback to default unknown icon
    const defaultIcon = this.platformMap.defaults?.default_unknown || 'generic_processor.jpg';
    let iconPath = `${this.platformMap.base_path}/${defaultIcon}`;

    // Ensure path starts with /static/
    if (!iconPath.startsWith('/')) {
        iconPath = '/' + iconPath;
    }
    if (!iconPath.startsWith('/static/')) {
        iconPath = '/static/' + iconPath.replace(/^static\//, '');
    }

    return iconPath;
}
}

// Global instance
const platformManager = new PlatformManager();

// Auto-load on page load
document.addEventListener('DOMContentLoaded', async () => {
    console.log('Auto-loading platform map...');
    await platformManager.loadPlatformMap();
});