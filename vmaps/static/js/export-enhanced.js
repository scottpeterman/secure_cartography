/**
 * Enhanced Export Module for SecureCartography Visualizer
 * Sends map name to backend, which loads topology and exports using Python libraries
 */

const EnhancedExporter = {
    /**
     * Export to GraphML with vendor-specific icons (via Python backend)
     */
    async exportGraphML(filename = 'network_topology.graphml', layout = 'tree', includeEndpoints = true) {
        if (!Graph.cy) {
            UI.showToast('No graph to export', 'warning');
            return;
        }

        try {
            UI.showLoading();

            // Get current map name
            const mapSelect = document.getElementById('map-select');
            const mapName = mapSelect?.value || 'network_topology';

            // Call Flask API with just the map name - backend loads topology
            const response = await fetch('/api/export/graphml', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    map_name: mapName,
                    layout: layout,
                    include_endpoints: includeEndpoints
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Export failed');
            }

            // Download the file
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = filename || `${mapName}.graphml`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);

            UI.showToast('GraphML exported with icons successfully', 'success');

        } catch (error) {
            console.error('GraphML export error:', error);
            UI.showToast('GraphML export failed: ' + error.message, 'error');
        } finally {
            UI.hideLoading();
        }
    },

    /**
     * Export to DrawIO with vendor-specific icons (via Python backend)
     */
    async exportDrawIO(filename = 'network_topology.drawio', layout = 'tree', includeEndpoints = true) {
        if (!Graph.cy) {
            UI.showToast('No graph to export', 'warning');
            return;
        }

        try {
            UI.showLoading();

            // Get current map name
            const mapSelect = document.getElementById('map-select');
            const mapName = mapSelect?.value || 'network_topology';

            // Call Flask API with just the map name - backend loads topology
            const response = await fetch('/api/export/drawio', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    map_name: mapName,
                    layout: layout,
                    include_endpoints: includeEndpoints
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Export failed');
            }

            // Download the file
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = filename || `${mapName}.drawio`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);

            UI.showToast('DrawIO exported with icons successfully', 'success');

        } catch (error) {
            console.error('DrawIO export error:', error);
            UI.showToast('DrawIO export failed: ' + error.message, 'error');
        } finally {
            UI.hideLoading();
        }
    },

    /**
     * Show export options dialog
     */
    async showExportDialog(format = 'graphml') {
        const formatLabel = format === 'graphml' ? 'GraphML' : 'DrawIO';

        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal-dialog">
                <div class="modal-header">
                    <h3>Export ${formatLabel}</h3>
                </div>
                <div class="modal-body">
                    <div style="margin-bottom: 15px;">
                        <label style="display: block; margin-bottom: 5px;">Layout Algorithm:</label>
                        <select id="export-layout" class="modal-input">
                            <option value="tree">Tree (Hierarchical)</option>
                            <option value="grid">Grid (Organized)</option>
                            <option value="balloon">Balloon (Radial)</option>
                        </select>
                    </div>
                    <div style="margin-bottom: 15px;">
                        <label style="display: flex; align-items: center; cursor: pointer;">
                            <input type="checkbox" id="export-endpoints" checked style="margin-right: 8px;">
                            Include endpoint devices
                        </label>
                    </div>
                    <p style="color: #666; font-size: 12px; margin-top: 10px;">
                        ✨ Exports include vendor-specific icons and device metadata
                    </p>
                </div>
                <div class="modal-footer">
                    <button class="md-button md-button-text cancel-btn">Cancel</button>
                    <button class="md-button md-button-filled export-btn">Export</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        return new Promise((resolve) => {
            modal.querySelector('.cancel-btn').addEventListener('click', () => {
                modal.remove();
                resolve(null);
            });

            modal.querySelector('.export-btn').addEventListener('click', () => {
                const layout = modal.querySelector('#export-layout').value;
                const includeEndpoints = modal.querySelector('#export-endpoints').checked;
                modal.remove();
                resolve({ layout, includeEndpoints });
            });

            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    modal.remove();
                    resolve(null);
                }
            });
        });
    }
};

// Make available globally
window.EnhancedExporter = EnhancedExporter;