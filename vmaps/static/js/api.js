/**
 * API Client for SecureCartography Visualizer
 * Handles all communication with Flask backend
 * Enhanced with topology editing support
 */

const API = {
    /**
     * List all available maps
     */
    async listMaps() {
        const response = await fetch('/api/maps');
        return await response.json();
    },

    /**
     * Load a specific map (topology + layout)
     */
    async loadMap(mapName) {
        const response = await fetch(`/api/maps/${mapName}`);  // ← Fixed: ( not `
        return await response.json();
    },

    /**
     * Save layout for a map
     */
    async saveLayout(mapName, layoutData) {
        const response = await fetch(`/api/maps/${mapName}/layout`, {  // ← Fixed: ( not `
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(layoutData)
        });
        return await response.json();
    },

    /**
     * Save topology for a map
     */
    async saveTopology(mapName, topologyData) {
        const response = await fetch(`/api/maps/${mapName}/topology`, {  // ← Fixed: ( not `
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(topologyData)
        });
        return await response.json();
    },

    /**
     * Reset/delete layout for a map
     */
    async resetLayout(mapName) {
        const response = await fetch(`/api/maps/${mapName}/layout`, {  // ← Fixed: ( not `
            method: 'DELETE'
        });
        return await response.json();
    },

    /**
     * Upload a new topology file
     */
    async uploadMap(file, mapName = '') {
        const formData = new FormData();
        formData.append('file', file);
        if (mapName) {
            formData.append('map_name', mapName);
        }

        const response = await fetch('/api/maps/upload', {
            method: 'POST',
            body: formData
        });
        return await response.json();
    },

    /**
     * Delete a map entirely
     */
    async deleteMap(mapName) {
        const response = await fetch(`/api/maps/${mapName}`, {  // ← Fixed: ( not `
            method: 'DELETE'
        });
        return await response.json();
    },

    /**
     * Rename a map
     */
    async renameMap(oldName, newName) {
        const response = await fetch(`/api/maps/${oldName}/rename`, {  // ← Fixed: ( not `
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ new_name: newName })
        });
        return await response.json();
    },

    /**
     * Export/download a map's topology
     */
    exportMap(mapName) {
        // Direct download via window location
        window.location.href = `/api/maps/${mapName}/export`;
    },

    /**
     * Copy/duplicate a map
     */
    async copyMap(sourceName, newName) {
        const response = await fetch(`/api/maps/${sourceName}/copy`, {  // ← Fixed: ( not `
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ new_name: newName })
        });
        return await response.json();
    },  // ← Added comma

    /**
     * Load icon mapping configuration
     */
    async loadIconMap() {
        const response = await fetch('/data/platform_icon_map.json');
        return await response.json();
    },

    /**
     * Get system diagnostics
     */
    async getDiagnostics() {
        const response = await fetch('/api/diagnostics');
        return await response.json();
    }
};