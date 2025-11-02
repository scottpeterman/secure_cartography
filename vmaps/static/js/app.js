/**
 * Main Application for SecureCartography Visualizer
 * Orchestrates all modules and handles app lifecycle
 */

const App = {
    /**
     * Initialize the application
     */
    async init() {
        console.log('SecureCartography Visualizer - Initializing...');

        try {
            // Initialize theme first
            Theme.init();

            // Initialize modules
            await Graph.init();
            Layout.init();
            FileManager.init();

            // Initialize sidebar (if present - for v2.4+ with sidebar navigation)
            if (window.Sidebar) {
                Sidebar.init();
                console.log('Sidebar navigation initialized');
            }

            // Load available maps
            await this.refreshMapList();

            // Setup event listeners
            this.setupEventListeners();

            UI.hideLoading();
            console.log('Application initialized successfully');

        } catch (error) {
            console.error('Initialization error:', error);
            UI.showToast('Error initializing application: ' + error.message, 'error');
            UI.hideLoading();
        }
    },

    /**
     * Setup global event listeners
     */
    setupEventListeners() {
        // Map selector
        const mapSelect = document.getElementById('map-select');
        if (mapSelect) {
            mapSelect.addEventListener('change', (e) => {
                if (e.target.value) {
                    this.loadMap(e.target.value);
                }
            });
        }

        // Toolbar buttons
        document.getElementById('create-node-btn')?.addEventListener('click', () => Graph.createNode());
        document.getElementById('create-edge-btn')?.addEventListener('click', () => Graph.createEdge());
        document.getElementById('fit-view-btn')?.addEventListener('click', () => Graph.fitToView());
        document.getElementById('reset-layout-btn')?.addEventListener('click', () => Layout.resetLayout());
        document.getElementById('export-png-btn')?.addEventListener('click', () => Graph.exportPNG());
        document.getElementById('save-layout-btn')?.addEventListener('click', () => Layout.saveLayout());
    },

    /**
     * Refresh the map list dropdown
     */
    async refreshMapList() {
        const mapSelect = document.getElementById('map-select');
        if (!mapSelect) return;

        try {
            const result = await API.listMaps();

            if (!result.success) {
                console.error('Failed to load maps:', result.error);
                return;
            }

            const maps = result.maps || [];

            // Clear existing options
            mapSelect.innerHTML = '<option value="">Select a network map...</option>';

            // Add map options
            maps.forEach(map => {
                const option = document.createElement('option');
                option.value = map.name;
                option.textContent = map.has_layout ? `${map.name} ✓` : map.name;
                mapSelect.appendChild(option);
            });

            console.log(`Loaded ${maps.length} maps`);

        } catch (error) {
            console.error('Error refreshing map list:', error);
            UI.showToast('Error loading maps', 'error');
        }
    },

    /**
     * Load a specific map
     */
    async loadMap(mapName) {
        if (!mapName) return;

        console.log(`Loading map: ${mapName}`);
        UI.showLoading();

        try {
            const result = await API.loadMap(mapName);

            if (!result.success) {
                UI.showToast(result.error || 'Failed to load map', 'error');
                UI.hideLoading();
                return;
            }

            // Set current map in layout module
            Layout.setCurrentMap(mapName);

            // Check if we have saved layout
            const hasSavedLayout = result.saved_layout && result.saved_layout.positions;

            // Load topology into graph
            await Graph.loadTopology(result.data, hasSavedLayout);

            // Restore saved layout if available
            if (hasSavedLayout) {
                Layout.restoreLayout(result.saved_layout);
            } else {
                Layout.applyLayout();
            }

            console.log(`Map loaded: ${mapName}`);

        } catch (error) {
            console.error('Error loading map:', error);
            UI.showToast('Error loading map: ' + error.message, 'error');
            UI.hideLoading();
        }
    }
};

// Initialize app when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        setTimeout(() => App.init(), 100);
    });
} else {
    setTimeout(() => App.init(), 100);
}