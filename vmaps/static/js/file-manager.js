/**
 * File Manager for SecureCartography Visualizer
 * Handles file operations: upload, delete, rename, export
 */

const FileManager = {
    /**
     * Initialize file manager
     */
    init() {
        this.setupEventListeners();
    },

    /**
     * Setup event listeners for file operations
     */
    setupEventListeners() {
        // File manager button
        const manageBtn = document.getElementById('manage-maps-btn');
        if (manageBtn) {
            manageBtn.addEventListener('click', () => this.showFileManager());
        }
    },

    /**
     * Show file manager modal
     */
    async showFileManager() {
        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.id = 'file-manager-modal';

        // Get current maps
        const mapsData = await API.listMaps();
        const maps = mapsData.success ? mapsData.maps : [];

        modal.innerHTML = `
            <div class="modal-dialog file-manager-dialog">
                <div class="modal-header">
                    <h3>📁 Manage Network Maps</h3>
                    <button class="close-btn" aria-label="Close">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="file-manager-toolbar">
                        <button class="md-button md-button-filled" id="upload-btn">
                            ⬆️ Upload Topology
                        </button>
                        <input type="file" id="file-input" accept=".json" style="display: none;">
                    </div>

                    <div class="maps-list">
                        ${maps.length === 0 ?
                            '<p class="empty-state">No maps yet. Upload a topology JSON file to get started.</p>' :
                            maps.map(map => this.renderMapItem(map)).join('')
                        }
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // Event listeners
        modal.querySelector('.close-btn').addEventListener('click', () => modal.remove());
        modal.addEventListener('click', (e) => {
            if (e.target === modal) modal.remove();
        });

        // Upload button
        const uploadBtn = modal.querySelector('#upload-btn');
        const fileInput = modal.querySelector('#file-input');

        uploadBtn.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', (e) => this.handleFileUpload(e, modal));

        // Map item actions
        modal.querySelectorAll('.map-item').forEach(item => {
            const mapName = item.dataset.mapName;

            item.querySelector('.rename-btn')?.addEventListener('click', () =>
                this.handleRename(mapName, modal));
            item.querySelector('.export-btn')?.addEventListener('click', () =>
                this.handleExport(mapName));
            item.querySelector('.delete-btn')?.addEventListener('click', () =>
                this.handleDelete(mapName, modal));
        });
    },

    /**
     * Render a single map item
     */
    renderMapItem(map) {
        const sizeKB = (map.topology_size / 1024).toFixed(1);
        const modified = new Date(map.modified).toLocaleDateString();
        const hasLayout = map.has_layout ? '✓' : '○';

        return `
            <div class="map-item" data-map-name="${map.name}">
                <div class="map-info">
                    <div class="map-name">${map.name}</div>
                    <div class="map-meta">
                        ${sizeKB} KB • Modified ${modified} • Layout ${hasLayout}
                    </div>
                </div>
                <div class="map-actions">
                    <button class="action-btn rename-btn" title="Rename">✏️</button>
                    <button class="action-btn export-btn" title="Export">⬇️</button>
                    <button class="action-btn delete-btn" title="Delete">🗑️</button>
                </div>
            </div>
        `;
    },

    /**
     * Handle file upload
     */
    async handleFileUpload(event, modal) {
        const file = event.target.files[0];
        if (!file) return;

        // Ask for map name
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
                UI.showToast(`Map "${result.map_name}" uploaded successfully (${result.device_count} devices)`, 'success');
                modal.remove();

                // Refresh map list and load new map
                await App.refreshMapList();
                await App.loadMap(result.map_name);
            } else {
                UI.showToast(result.error || 'Upload failed', 'error');
            }
        } catch (error) {
            UI.showToast('Upload error: ' + error.message, 'error');
        } finally {
            UI.hideLoading();
            event.target.value = ''; // Reset file input
        }
    },

    /**
     * Handle map rename
     */
    async handleRename(oldName, modal) {
        const newName = await UI.prompt(
            'Enter new name for this map:',
            oldName,
            'Rename Map'
        );

        if (!newName || newName === oldName) return;

        UI.showLoading();

        try {
            const result = await API.renameMap(oldName, newName);

            if (result.success) {
                UI.showToast(`Renamed "${oldName}" to "${newName}"`, 'success');
                modal.remove();

                // Refresh and load renamed map
                await App.refreshMapList();
                await App.loadMap(newName);
            } else {
                UI.showToast(result.error || 'Rename failed', 'error');
            }
        } catch (error) {
            UI.showToast('Rename error: ' + error.message, 'error');
        } finally {
            UI.hideLoading();
        }
    },

    /**
     * Handle map export
     */
    handleExport(mapName) {
        UI.showToast(`Downloading ${mapName}...`, 'info');
        API.exportMap(mapName);
    },

    /**
     * Handle map deletion
     */
    async handleDelete(mapName, modal) {
        const confirmed = await UI.confirm(
            `Are you sure you want to delete "${mapName}"? This will remove the topology and any saved layout.`,
            'Delete Map'
        );

        if (!confirmed) return;

        UI.showLoading();

        try {
            const result = await API.deleteMap(mapName);

            if (result.success) {
                UI.showToast(`Map "${mapName}" deleted`, 'success');
                modal.remove();

                // Refresh map list
                await App.refreshMapList();

                // Clear current view if deleted map was active
                const mapSelect = document.getElementById('map-select');
                if (mapSelect.value === mapName) {
                    mapSelect.value = '';
                    if (window.Graph && window.Graph.cy) {
                        window.Graph.cy.destroy();
                        window.Graph.cy = null;
                    }
                }
            } else {
                UI.showToast(result.error || 'Delete failed', 'error');
            }
        } catch (error) {
            UI.showToast('Delete error: ' + error.message, 'error');
        } finally {
            UI.hideLoading();
        }
    }
};