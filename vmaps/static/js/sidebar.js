/**
 * Sidebar Navigation for SecureCartography Visualizer
 * Handles collapsible sidebar with hamburger menu
 */

const Sidebar = {
    collapsed: false,

    /**
     * Initialize sidebar
     */
    init() {
        console.log('[Sidebar] Initializing with hamburger menu pattern...');

        // Wait for DOM if needed
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                this.setupEventListeners();
                this.restoreState();
            });
        } else {
            this.setupEventListeners();
            this.restoreState();
        }
    },

    /**
     * Setup all sidebar event listeners
     */
    setupEventListeners() {
        console.log('[Sidebar] Setting up event listeners...');

        // Hamburger menu button (SIMPLE AND CLEAN)
        const hamburgerBtn = document.getElementById('hamburger-btn');
        if (hamburgerBtn) {
            hamburgerBtn.addEventListener('click', () => {
                console.log('[Sidebar] Hamburger clicked');
                this.toggle();
            });
            console.log('[Sidebar] ✓ Hamburger menu bound successfully');
        } else {
            console.error('[Sidebar] ✗ Hamburger button not found!');
        }

        // Map operation buttons
        document.getElementById('upload-map-btn')?.addEventListener('click', () => {
            this.triggerFileUpload();
        });

        document.getElementById('export-map-btn')?.addEventListener('click', () => {
            this.handleDirectExport();
        });

        document.getElementById('copy-map-btn')?.addEventListener('click', () => {
            this.handleCopyMap();
        });

        document.getElementById('manage-maps-btn')?.addEventListener('click', () => {
            if (window.FileManager) {
                FileManager.showFileManager();
            }
        });

        document.getElementById('save-changes-btn')?.addEventListener('click', async () => {
            await Layout.saveLayout();
        });

        document.getElementById('save-layout-btn')?.addEventListener('click', async () => {
            await Layout.saveLayout();
        });

        // Export buttons
        document.getElementById('export-graphml-btn')?.addEventListener('click', () => {
            this.handleExportGraphML();
        });

        document.getElementById('export-drawio-btn')?.addEventListener('click', () => {
            this.handleExportDrawIO();
        });

        // Create overlay for mobile
        this.createOverlay();
    },

    /**
     * Toggle sidebar collapsed/expanded state
     */
    toggle() {
        const sidebar = document.getElementById('sidebar');
        if (!sidebar) {
            console.error('[Sidebar] Sidebar element not found!');
            return;
        }

        this.collapsed = !this.collapsed;

        if (this.collapsed) {
            sidebar.classList.add('collapsed');
            console.log('[Sidebar] Collapsed');
        } else {
            sidebar.classList.remove('collapsed');
            sidebar.classList.add('mobile-visible');
            console.log('[Sidebar] Expanded');
        }

        // Show/hide overlay on mobile
        const overlay = document.getElementById('sidebar-overlay');
        if (overlay) {
            if (this.collapsed) {
                overlay.classList.remove('active');
            } else {
                overlay.classList.add('active');
            }
        }

        // Save state to localStorage
        localStorage.setItem('sidebar-collapsed', this.collapsed);

        // Trigger Cytoscape resize after animation
        if (window.Graph && Graph.cy) {
            setTimeout(() => {
                Graph.cy.resize();
                Graph.cy.fit(null, 50);
            }, 350);
        }
    },

    /**
     * Restore sidebar state from localStorage
     */
    restoreState() {
        const saved = localStorage.getItem('sidebar-collapsed');
        if (saved === 'true') {
            const sidebar = document.getElementById('sidebar');
            if (sidebar) {
                this.collapsed = true;
                sidebar.classList.add('collapsed');
                console.log('[Sidebar] Restored collapsed state from localStorage');
            }
        }
    },

    /**
     * Create overlay for mobile sidebar
     */
    createOverlay() {
        // Check if overlay already exists
        if (document.getElementById('sidebar-overlay')) {
            return;
        }

        const overlay = document.createElement('div');
        overlay.id = 'sidebar-overlay';
        overlay.className = 'sidebar-overlay';

        // Click overlay to close sidebar on mobile
        overlay.addEventListener('click', () => {
            if (!this.collapsed) {
                this.toggle();
            }
        });

        document.body.appendChild(overlay);
    },

    /**
     * Trigger file upload dialog
     */
    triggerFileUpload() {
        let fileInput = document.getElementById('hidden-file-input');

        if (!fileInput) {
            fileInput = document.createElement('input');
            fileInput.type = 'file';
            fileInput.id = 'hidden-file-input';
            fileInput.accept = '.json';
            fileInput.style.display = 'none';
            fileInput.addEventListener('change', (e) => this.handleFileUpload(e));
            document.body.appendChild(fileInput);
        }

        fileInput.click();
    },

    /**
     * Handle file upload from sidebar button
     */
    async handleFileUpload(event) {
        const file = event.target.files[0];
        if (!file) return;

        const defaultName = file.name.replace('.json', '').replace(/[^a-zA-Z0-9_-]/g, '_');
        const mapName = await UI.prompt(
            'Enter a name for this map:',
            defaultName,
            'Upload Topology'
        );

        if (!mapName) return;

        UI.showLoading();

        try {
            const result = await API.uploadMap(file, mapName);

            if (result.success) {
                UI.showToast(
                    `Map "${result.map_name}" uploaded successfully (${result.device_count} devices)`,
                    'success'
                );

                await App.refreshMapList();

                const mapSelect = document.getElementById('map-select');
                mapSelect.value = result.map_name;

                await App.loadMap(result.map_name);
            } else {
                UI.showToast(result.error || 'Upload failed', 'error');
            }
        } catch (error) {
            UI.showToast('Upload error: ' + error.message, 'error');
        } finally {
            UI.hideLoading();
            event.target.value = '';
        }
    },

    /**
     * Handle direct export from sidebar
     */
    handleDirectExport() {
        const mapSelect = document.getElementById('map-select');
        const currentMap = mapSelect.value;

        if (!currentMap) {
            UI.showToast('Please select a map first', 'warning');
            return;
        }

        UI.showToast(`Downloading ${currentMap}...`, 'info');
        API.exportMap(currentMap);
    },

    /**
     * Handle copy/duplicate map
     */
    async handleCopyMap() {
        const mapSelect = document.getElementById('map-select');
        const currentMap = mapSelect.value;

        if (!currentMap) {
            UI.showToast('Please select a map to copy', 'warning');
            return;
        }

        const newName = await UI.prompt(
            `Create a copy of "${currentMap}". Enter new name:`,
            `${currentMap}_copy`,
            'Copy Map'
        );

        if (!newName) return;

        UI.showLoading();

        try {
            const result = await API.copyMap(currentMap, newName);

            if (result.success) {
                UI.showToast(`Created copy: ${newName}`, 'success');

                await App.refreshMapList();

                mapSelect.value = newName;
                await App.loadMap(newName);
            } else {
                UI.showToast(result.error || 'Copy failed', 'error');
            }
        } catch (error) {
            console.error('Copy error:', error);
            UI.showToast('Copy error: ' + error.message, 'error');
        } finally {
            UI.hideLoading();
        }
    },

    /**
     * Handle GraphML export (with icons via Python backend)
     */
    async handleExportGraphML() {
        const mapSelect = document.getElementById('map-select');
        const currentMap = mapSelect.value;

        if (!currentMap) {
            UI.showToast('Please select a map first', 'warning');
            return;
        }

        if (typeof EnhancedExporter !== 'undefined') {
            const options = await EnhancedExporter.showExportDialog('graphml');
            if (options) {
                await EnhancedExporter.exportGraphML(
                    `${currentMap}.graphml`,
                    options.layout,
                    options.includeEndpoints
                );
            }
        } else {
            UI.showToast('Enhanced exporter not loaded', 'error');
        }
    },

    /**
     * Handle DrawIO export (with icons via Python backend)
     */
    async handleExportDrawIO() {
        const mapSelect = document.getElementById('map-select');
        const currentMap = mapSelect.value;

        if (!currentMap) {
            UI.showToast('Please select a map first', 'warning');
            return;
        }

        if (typeof EnhancedExporter !== 'undefined') {
            const options = await EnhancedExporter.showExportDialog('drawio');
            if (options) {
                await EnhancedExporter.exportDrawIO(
                    `${currentMap}.drawio`,
                    options.layout,
                    options.includeEndpoints
                );
            }
        } else {
            UI.showToast('DrawIO exporter not loaded', 'error');
        }
    },


    /**
     * Show/hide the modified state indicator
     * Called by Graph module when topology changes
     */
    setModifiedState(modified) {
        const saveChangesBtn = document.getElementById('save-changes-btn');
        const saveLayoutBtn = document.getElementById('save-layout-btn');

        if (!saveChangesBtn || !saveLayoutBtn) return;

        if (modified) {
            saveChangesBtn.style.display = 'flex';
            saveLayoutBtn.style.display = 'none';
        } else {
            saveChangesBtn.style.display = 'none';
            saveLayoutBtn.style.display = 'flex';
        }
    },

    /**
     * Update map selector after operations
     */
    updateMapSelector(maps) {
        const mapSelect = document.getElementById('map-select');
        if (!mapSelect) return;

        const currentValue = mapSelect.value;

        mapSelect.innerHTML = '<option value="">Select a network map...</option>';

        maps.forEach(map => {
            const option = document.createElement('option');
            option.value = map.name;
            option.textContent = map.has_layout ? `${map.name} ✓` : map.name;
            mapSelect.appendChild(option);
        });

        if (currentValue && maps.find(m => m.name === currentValue)) {
            mapSelect.value = currentValue;
        }
    }
};

// Self-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        console.log('[Sidebar] Self-initializing on DOMContentLoaded...');
        Sidebar.init();
    });
} else {
    console.log('[Sidebar] Self-initializing immediately...');
    Sidebar.init();
}