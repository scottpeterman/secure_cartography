/**
 * Graph Management for SecureCartography Visualizer
 * Handles Cytoscape.js instance and graph rendering
 * Enhanced with node editing and deletion capabilities
 */

const Graph = {
    cy: null,
    iconMap: null,
    topologyModified: false,

    /**
     * Initialize the graph module
     */
    async init() {
        this.iconMap = await API.loadIconMap();
    },

    /**
     * Get Cytoscape styles based on current theme
     */
    getStyles() {
        // Get computed CSS variables from the document
        const styles = getComputedStyle(document.documentElement);

        return [
            {
                selector: 'node',
                style: {
                    'background-image': 'data(icon)',
                    'background-fit': 'contain',
                    'background-clip': 'none',
                    'width': 60,
                    'height': 60,
                    'label': 'data(label)',
                    'text-valign': 'bottom',
                    'text-halign': 'center',
                    'text-margin-y': 5,
                    'font-size': '12px',
                    'font-weight': '500',
                    'color': styles.getPropertyValue('--md-on-surface').trim(),
                    'text-background-color': styles.getPropertyValue('--md-surface').trim(),
                    'text-background-opacity': 0.9,
                    'text-background-padding': '4px',
                    'text-background-shape': 'roundrectangle',
                    'border-width': 2,
                    'border-color': styles.getPropertyValue('--md-primary').trim(),
                    'border-opacity': 0.3
                }
            },
            {
                selector: 'node:selected',
                style: {
                    'border-width': 3,
                    'border-opacity': 1,
                    'border-color': styles.getPropertyValue('--md-secondary').trim()
                }
            },
            {
                selector: 'edge',
                style: {
                    'width': 2,
                    'line-color': styles.getPropertyValue('--md-primary').trim(),
                    'curve-style': 'bezier',
                    'label': 'data(label)',
                    'font-size': '9px',
                    'font-weight': '500',
                    'color': styles.getPropertyValue('--md-on-surface').trim(),
                    'text-background-color': styles.getPropertyValue('--md-surface').trim(),
                    'text-background-opacity': 0.95,
                    'text-background-padding': '3px',
                    'text-background-shape': 'roundrectangle',
                    'text-rotation': 'autorotate',
                    'text-margin-y': -10
                }
            },
            {
                selector: 'edge:selected',
                style: {
                    'width': 4,
                    'line-color': styles.getPropertyValue('--md-secondary').trim()
                }
            }
        ];
    },

    /**
     * Load topology data into the graph
     */
    async loadTopology(data, skipLayout = false) {
        try {
            UI.showLoading();

            // Update stats
            UI.updateStats(data.nodes.length, data.edges.length, 'loading...');

            // Convert to Cytoscape format
            const elements = [
                ...data.nodes.map(n => ({ data: n.data || n })),
                ...data.edges.map(e => ({ data: e.data || e }))
            ];

            // Destroy existing instance
            if (this.cy) {
                this.cy.destroy();
                this.cy = null;
            }

            // Create new Cytoscape instance
            this.cy = cytoscape({
                container: document.getElementById('cy'),
                elements: elements,
                style: this.getStyles(),
                layout: { name: 'preset' }
            });

            // Setup event handlers
            this.setupEventHandlers();

            // Clear modified flag on fresh load
            this.clearModifiedFlag();

            // Apply layout if needed
            if (!skipLayout) {
                Layout.applyLayout();
            }

            UI.hideLoading();

            // Fit to view
            setTimeout(() => {
                if (this.cy) {
                    this.cy.fit(null, 50);
                }
            }, 300);

        } catch (error) {
            console.error('Error loading topology:', error);
            UI.showToast('Error loading topology: ' + error.message, 'error');
            UI.hideLoading();
        }
    },

    /**
     * Setup event handlers for the graph
     */
    setupEventHandlers() {
        if (!this.cy) return;

        // Node click - show info panel
        this.cy.on('tap', 'node', (evt) => {
            const node = evt.target;
            this.showNodeInfo(node);
        });

        // Edge click - show connection info
        this.cy.on('tap', 'edge', (evt) => {
            const edge = evt.target;
            this.showEdgeInfo(edge);
        });

        // Click on background - hide info panel
        this.cy.on('tap', (evt) => {
            if (evt.target === this.cy) {
                this.hideInfoPanel();
            }
        });

        // Node drag - trigger autosave
        this.cy.on('dragfree', 'node', () => {
            Layout.scheduleAutoSave();
        });
    },

    /**
     * Show node information panel (with edit capabilities)
     */
    showNodeInfo(node) {
        const data = node.data();
        const panel = document.getElementById('info-panel');
        const content = document.getElementById('info-content');

        const html = `
            <div class="info-header">
                <h4>Device Information</h4>
                <div class="info-actions">
                    <button class="icon-btn edit-node-btn" title="Edit Device">✏️</button>
                    <button class="icon-btn delete-node-btn" title="Delete Device">🗑️</button>
                </div>
            </div>
            <div class="info-item">
                <strong>Device:</strong> <span class="info-value">${data.label || data.id}</span>
            </div>
            <div class="info-item">
                <strong>IP Address:</strong> <span class="info-value">${data.ip || 'N/A'}</span>
            </div>
            <div class="info-item">
                <strong>Platform:</strong> <span class="info-value">${data.platform || 'Unknown'}</span>
            </div>
        `;

        content.innerHTML = html;
        panel.classList.add('active');

        // Attach event listeners
        content.querySelector('.edit-node-btn')?.addEventListener('click', () => {
            this.editNode(node);
        });

        content.querySelector('.delete-node-btn')?.addEventListener('click', () => {
            this.deleteNode(node);
        });
    },

    /**
     * Edit node properties
     */
    /**
 * Edit node properties
 * MODIFIED VERSION - with Enhanced Platform Picker
 * Replace lines 218-374 in your graph.js with this code
 */
async editNode(node) {
    const data = node.data();

    // Create edit modal
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal-dialog">
            <div class="modal-header">
                <h3>✏️ Edit Device</h3>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label>Device Name:</label>
                    <input type="text" id="edit-device-name" class="modal-input" value="${data.label || data.id}" placeholder="Device name...">
                </div>
                <div class="form-group">
                    <label>IP Address:</label>
                    <input type="text" id="edit-ip" class="modal-input" value="${data.ip || ''}" placeholder="IP address...">
                </div>
                <div class="form-group">
                    <label>Platform:</label>
                    <div id="edit-platform-selector-container"></div>
                </div>
            </div>
            <div class="modal-footer">
                <button class="md-button md-button-text cancel-btn">Cancel</button>
                <button class="md-button md-button-filled save-btn">Save Changes</button>
            </div>
        </div>
    `;

    document.body.appendChild(modal);

    // Initialize platform selector (NEW!)
    const platformSelector = new PlatformSelector(
        document.getElementById('edit-platform-selector-container'),
        {
            initialValue: data.platform || '',
            allowCustom: true,
            onChange: (value) => {
                console.log('Platform changed to:', value);
            }
        }
    );

    const nameInput = modal.querySelector('#edit-device-name');
    const ipInput = modal.querySelector('#edit-ip');

    nameInput.focus();
    nameInput.select();

    const handleSave = async () => {
        const newName = nameInput.value.trim();
        const newIp = ipInput.value.trim();
        const newPlatform = platformSelector.getValue(); // CHANGED: was platformInput.value.trim()

        if (!newName) {
            UI.showToast('Device name cannot be empty', 'error');
            return;
        }

        // Check if name changed and if it conflicts
        if (newName !== data.id) {
            const existingNode = this.cy.getElementById(newName);
            if (existingNode.length > 0) {
                UI.showToast('A device with this name already exists', 'error');
                return;
            }
        }

        modal.remove();

        try {
            // Update node data
            const oldId = data.id;
            const updates = {
                id: newName,
                label: newName,
                ip: newIp,
                platform: newPlatform
            };

            // Update icon if platform changed
            if (newPlatform !== data.platform && this.iconMap) {
                const iconFile = this.getIconForPlatform(newPlatform, newName);
                updates.icon = `/static/icons_lib/${iconFile}`;
            }

            // If ID changed, need to handle edges
            if (oldId !== newName) {
                // Get all connected edges
                const connectedEdges = node.connectedEdges();
                const edgeData = [];

                connectedEdges.forEach(edge => {
                    const eData = edge.data();
                    edgeData.push({
                        source: eData.source === oldId ? newName : eData.source,
                        target: eData.target === oldId ? newName : eData.target,
                        label: eData.label
                    });
                });

                // Store position
                const position = node.position();

                // Remove old node and edges
                this.cy.remove(node);
                this.cy.remove(connectedEdges);

                // Add new node with updated data
                const newNode = this.cy.add({
                    group: 'nodes',
                    data: updates,
                    position: position
                });

                // Recreate edges
                edgeData.forEach(edge => {
                    this.cy.add({
                        group: 'edges',
                        data: edge
                    });
                });

                // Select new node
                this.cy.nodes().unselect();
                newNode.select();
                this.showNodeInfo(newNode);
            } else {
                // Simple update - no ID change
                Object.keys(updates).forEach(key => {
                    node.data(key, updates[key]);
                });
                this.showNodeInfo(node);
            }

            // Mark topology as modified
            this.markTopologyModified();

            UI.showToast('Device updated successfully', 'success');

        } catch (error) {
            console.error('Error updating node:', error);
            UI.showToast('Error updating device: ' + error.message, 'error');
        }
    };

    const handleCancel = () => {
        modal.remove();
    };

    modal.querySelector('.cancel-btn').addEventListener('click', handleCancel);
    modal.querySelector('.save-btn').addEventListener('click', handleSave);

    // Enter to save (CHANGED: removed platformInput from array)
    [nameInput, ipInput].forEach(input => {
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') handleSave();
            if (e.key === 'Escape') handleCancel();
        });
    });

    modal.addEventListener('click', (e) => {
        if (e.target === modal) handleCancel();
    });
},
    /**
     * Delete a node
     */
    async deleteNode(node) {
        const data = node.data();

        const confirmed = await UI.confirm(
            `Are you sure you want to delete device "${data.label || data.id}"? This will also remove all connections to this device.`,
            'Delete Device'
        );

        if (!confirmed) return;

        try {
            // Get connected edges count for feedback
            const edgeCount = node.connectedEdges().length;

            // Remove node (edges are automatically removed)
            this.cy.remove(node);

            // Hide info panel
            this.hideInfoPanel();

            // Mark topology as modified
            this.markTopologyModified();

            // Update stats
            UI.updateStats(
                this.cy.nodes().length,
                this.cy.edges().length,
                document.getElementById('layout-select').value
            );

            UI.showToast(
                `Device deleted (removed ${edgeCount} connection${edgeCount !== 1 ? 's' : ''})`,
                'success'
            );

        } catch (error) {
            console.error('Error deleting node:', error);
            UI.showToast('Error deleting device: ' + error.message, 'error');
        }
    },

    /**
     * Create a new node
     */
    async createNode() {
        // Create modal for new node
        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal-dialog">
                <div class="modal-header">
                    <h3>➕ Create New Device</h3>
                </div>
                <div class="modal-body">
                    <div class="form-group">
                        <label>Device Name: *</label>
                        <input type="text" id="create-device-name" class="modal-input" placeholder="e.g., router-01" autofocus>
                    </div>
                    <div class="form-group">
                        <label>IP Address:</label>
                        <input type="text" id="create-ip" class="modal-input" placeholder="e.g., 10.0.1.1">
                    </div>
                    <div class="form-group">
                        <label>Platform:</label>
                        <input type="text" id="create-platform" class="modal-input" placeholder="e.g., C8000V, IOSv">
                    </div>
                    <p style="font-size: 12px; color: var(--md-on-surface-variant); margin-top: 8px;">
                        * Device name is required and must be unique
                    </p>
                </div>
                <div class="modal-footer">
                    <button class="md-button md-button-text cancel-btn">Cancel</button>
                    <button class="md-button md-button-filled create-btn">Create Device</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        const nameInput = modal.querySelector('#create-device-name');
        const ipInput = modal.querySelector('#create-ip');
        const platformInput = modal.querySelector('#create-platform');
        const createBtn = modal.querySelector('.create-btn');
        const cancelBtn = modal.querySelector('.cancel-btn');

        nameInput.focus();

        const handleCreate = () => {
            const newName = nameInput.value.trim();
            const newIp = ipInput.value.trim();
            const newPlatform = platformInput.value.trim();

            // Validation
            if (!newName) {
                UI.showToast('Device name is required', 'error');
                nameInput.focus();
                return;
            }

            // Check for duplicate name
            const existingNode = this.cy.getElementById(newName);
            if (existingNode.length > 0) {
                UI.showToast(`Device "${newName}" already exists`, 'error');
                nameInput.focus();
                nameInput.select();
                return;
            }

            // Determine icon
            const iconFile = this.getIconForPlatform(newPlatform, newName);
            const iconUrl = `/static/icons_lib/${iconFile}`;

            // Get center position for new node (or slightly random to avoid overlap)
            const extent = this.cy.extent();
            const centerX = (extent.x1 + extent.x2) / 2 + (Math.random() - 0.5) * 100;
            const centerY = (extent.y1 + extent.y2) / 2 + (Math.random() - 0.5) * 100;

            // Add node to graph
            this.cy.add({
                group: 'nodes',
                data: {
                    id: newName,
                    label: newName,
                    ip: newIp || '',
                    platform: newPlatform || 'Unknown',
                    icon: iconUrl
                },
                position: {
                    x: centerX,
                    y: centerY
                }
            });

            // Mark topology as modified
            this.markTopologyModified();

            // Update stats
            UI.updateStats(
                this.cy.nodes().length,
                this.cy.edges().length,
                document.getElementById('layout-select').value
            );

            UI.showToast(`Device "${newName}" created`, 'success');
            modal.remove();

            // Select the new node
            this.cy.nodes().unselect();
            this.cy.getElementById(newName).select();
            this.showNodeInfo(this.cy.getElementById(newName));
        };

        const handleCancel = () => {
            modal.remove();
        };

        createBtn.addEventListener('click', handleCreate);
        cancelBtn.addEventListener('click', handleCancel);

        [nameInput, ipInput, platformInput].forEach(input => {
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') handleCreate();
                if (e.key === 'Escape') handleCancel();
            });
        });

        modal.addEventListener('click', (e) => {
            if (e.target === modal) handleCancel();
        });
    },

    /**
     * Helper to get icon for platform
     */
    getIconForPlatform(platform, deviceName = '') {
        if (!this.iconMap || !platform) {
            return this.iconMap?.defaults?.default_unknown || 'cloud_(4).jpg';
        }

        // Direct platform pattern match
        for (const [pattern, icon] of Object.entries(this.iconMap.platform_patterns || {})) {
            if (platform.toLowerCase().includes(pattern.toLowerCase())) {
                return icon;
            }
        }

        // Fallback patterns
        const platformLower = platform.toLowerCase();
        const deviceNameLower = deviceName.toLowerCase();

        for (const [deviceType, rules] of Object.entries(this.iconMap.fallback_patterns || {})) {
            // Check platform patterns
            for (const pattern of rules.platform_patterns || []) {
                if (platformLower.includes(pattern.toLowerCase())) {
                    const iconKey = rules.icon || 'default_unknown';
                    return this.iconMap.defaults?.[iconKey] || 'cloud_(4).jpg';
                }
            }

            // Check device name patterns
            if (deviceNameLower) {
                for (const pattern of rules.name_patterns || []) {
                    if (deviceNameLower.includes(pattern.toLowerCase())) {
                        const iconKey = rules.icon || 'default_unknown';
                        return this.iconMap.defaults?.[iconKey] || 'cloud_(4).jpg';
                    }
                }
            }
        }

        return this.iconMap.defaults?.default_unknown || 'cloud_(4).jpg';
    },

    /**
     * Mark topology as modified (needs save)
     */
    markTopologyModified() {
        // Set flag that topology has been modified
        this.topologyModified = true;

        // Update sidebar modified indicator if sidebar exists
        if (window.Sidebar) {
            Sidebar.setModifiedState(true);
        } else {
            // Fallback: Update old toolbar button if sidebar not present (backwards compatibility)
            const saveBtn = document.getElementById('save-layout-btn');
            if (saveBtn && !saveBtn.textContent.includes('*')) {
                saveBtn.innerHTML = '💾 Save Changes *';
                saveBtn.classList.add('pulsing');
            }
        }

        console.log('Topology modified - unsaved changes');
    },

    /**
     * Clear modified flag
     */
    clearModifiedFlag() {
        this.topologyModified = false;

        // Update sidebar modified indicator if sidebar exists
        if (window.Sidebar) {
            Sidebar.setModifiedState(false);
        } else {
            // Fallback: Update old toolbar button if sidebar not present (backwards compatibility)
            const saveBtn = document.getElementById('save-layout-btn');
            if (saveBtn) {
                saveBtn.innerHTML = '💾 Save Layout';
                saveBtn.classList.remove('pulsing');
            }
        }

        console.log('Topology changes saved');
    },

    /**
     * Show edge information panel (with edit capabilities)
     */
    showEdgeInfo(edge) {
        const data = edge.data();
        const panel = document.getElementById('info-panel');
        const content = document.getElementById('info-content');

        const html = `
            <div class="info-header">
                <h4>Connection Information</h4>
                <div class="info-actions">
                    <button class="icon-btn edit-edge-btn" title="Edit Connection">✏️</button>
                    <button class="icon-btn delete-edge-btn" title="Delete Connection">🗑️</button>
                </div>
            </div>
            <div class="info-item">
                <strong>Connection:</strong>
            </div>
            <div class="info-item">
                ${data.source} → ${data.target}
            </div>
            <div class="info-item">
                <strong>Interfaces:</strong>
            </div>
            <div class="info-item">
                ${data.label || 'N/A'}
            </div>
        `;

        content.innerHTML = html;
        panel.classList.add('active');

        // Attach event listeners
        content.querySelector('.edit-edge-btn')?.addEventListener('click', () => {
            this.editEdge(edge);
        });

        content.querySelector('.delete-edge-btn')?.addEventListener('click', () => {
            this.deleteEdge(edge);
        });
    },

    /**
     * Edit edge properties
     */
    async editEdge(edge) {
        const data = edge.data();

        // Parse current interfaces from label
        let sourceInt = '';
        let targetInt = '';
        if (data.label) {
            const parts = data.label.split(' ↔ ');
            if (parts.length === 2) {
                sourceInt = parts[0];
                targetInt = parts[1];
            }
        }

        // Create edit modal
        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal-dialog">
                <div class="modal-header">
                    <h3>✏️ Edit Connection</h3>
                </div>
                <div class="modal-body">
                    <div class="form-group">
                        <label>Source Device:</label>
                        <input type="text" class="modal-input" value="${data.source}" disabled>
                    </div>
                    <div class="form-group">
                        <label>Source Interface:</label>
                        <input type="text" id="edit-source-int" class="modal-input" value="${sourceInt}" placeholder="e.g., Gi1/0/1">
                    </div>
                    <div class="form-group">
                        <label>Target Device:</label>
                        <input type="text" class="modal-input" value="${data.target}" disabled>
                    </div>
                    <div class="form-group">
                        <label>Target Interface:</label>
                        <input type="text" id="edit-target-int" class="modal-input" value="${targetInt}" placeholder="e.g., Gi0/0">
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="md-button md-button-text cancel-btn">Cancel</button>
                    <button class="md-button md-button-filled save-btn">Save Changes</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        const sourceIntInput = modal.querySelector('#edit-source-int');
        const targetIntInput = modal.querySelector('#edit-target-int');
        const saveBtn = modal.querySelector('.save-btn');
        const cancelBtn = modal.querySelector('.cancel-btn');

        sourceIntInput.focus();

        const handleSave = () => {
            const newSourceInt = sourceIntInput.value.trim();
            const newTargetInt = targetIntInput.value.trim();

            // Update edge label
            const newLabel = (newSourceInt && newTargetInt)
                ? `${newSourceInt} ↔ ${newTargetInt}`
                : '';

            edge.data('label', newLabel);

            // Mark topology as modified
            this.markTopologyModified();

            UI.showToast('Connection updated', 'success');
            modal.remove();

            // Refresh info panel
            this.showEdgeInfo(edge);
        };

        const handleCancel = () => {
            modal.remove();
        };

        saveBtn.addEventListener('click', handleSave);
        cancelBtn.addEventListener('click', handleCancel);

        [sourceIntInput, targetIntInput].forEach(input => {
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') handleSave();
                if (e.key === 'Escape') handleCancel();
            });
        });

        modal.addEventListener('click', (e) => {
            if (e.target === modal) handleCancel();
        });
    },

    /**
     * Delete an edge
     */
    async deleteEdge(edge) {
        const data = edge.data();

        const confirmed = await UI.confirm(
            `Are you sure you want to delete the connection between "${data.source}" and "${data.target}"?`,
            'Delete Connection'
        );

        if (!confirmed) return;

        try {
            // Remove edge
            this.cy.remove(edge);

            // Hide info panel
            this.hideInfoPanel();

            // Mark topology as modified
            this.markTopologyModified();

            // Update stats
            UI.updateStats(
                this.cy.nodes().length,
                this.cy.edges().length,
                document.getElementById('layout-select').value
            );

            UI.showToast('Connection deleted', 'success');

        } catch (error) {
            console.error('Error deleting edge:', error);
            UI.showToast('Error deleting connection: ' + error.message, 'error');
        }
    },

    /**
     * Create a new edge (connection mode)
     */
    async createEdge() {
        if (!this.cy) {
            UI.showToast('No graph loaded', 'warning');
            return;
        }

        const nodes = this.cy.nodes();
        if (nodes.length < 2) {
            UI.showToast('Need at least 2 devices to create a connection', 'warning');
            return;
        }

        // Create modal for edge creation
        const modal = document.createElement('div');
        modal.className = 'modal-overlay';

        // Build device options
        const deviceOptions = nodes.map(node => {
            const data = node.data();
            return `<option value="${data.id}">${data.label || data.id}</option>`;
        }).join('');

        modal.innerHTML = `
            <div class="modal-dialog">
                <div class="modal-header">
                    <h3>🔗 Create Connection</h3>
                </div>
                <div class="modal-body">
                    <div class="form-group">
                        <label>Source Device: *</label>
                        <select id="create-edge-source" class="modal-input">
                            <option value="">Select source device...</option>
                            ${deviceOptions}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Source Interface:</label>
                        <input type="text" id="create-edge-source-int" class="modal-input" placeholder="e.g., Gi1/0/1">
                    </div>
                    <div class="form-group">
                        <label>Target Device: *</label>
                        <select id="create-edge-target" class="modal-input">
                            <option value="">Select target device...</option>
                            ${deviceOptions}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Target Interface:</label>
                        <input type="text" id="create-edge-target-int" class="modal-input" placeholder="e.g., Gi0/0">
                    </div>
                    <p style="font-size: 12px; color: var(--md-on-surface-variant); margin-top: 8px;">
                        * Source and target devices are required
                    </p>
                </div>
                <div class="modal-footer">
                    <button class="md-button md-button-text cancel-btn">Cancel</button>
                    <button class="md-button md-button-filled create-btn">Create Connection</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        const sourceSelect = modal.querySelector('#create-edge-source');
        const targetSelect = modal.querySelector('#create-edge-target');
        const sourceIntInput = modal.querySelector('#create-edge-source-int');
        const targetIntInput = modal.querySelector('#create-edge-target-int');
        const createBtn = modal.querySelector('.create-btn');
        const cancelBtn = modal.querySelector('.cancel-btn');

        sourceSelect.focus();

        const handleCreate = () => {
            const sourceId = sourceSelect.value;
            const targetId = targetSelect.value;
            const sourceInt = sourceIntInput.value.trim();
            const targetInt = targetIntInput.value.trim();

            // Validation
            if (!sourceId || !targetId) {
                UI.showToast('Source and target devices are required', 'error');
                return;
            }

            if (sourceId === targetId) {
                UI.showToast('Cannot connect a device to itself', 'error');
                return;
            }

            // Check if edge already exists
            const existingEdge = this.cy.edges(`[source="${sourceId}"][target="${targetId}"], [source="${targetId}"][target="${sourceId}"]`);
            if (existingEdge.length > 0) {
                UI.showToast('Connection already exists between these devices', 'warning');
                return;
            }

            // Create label
            const label = (sourceInt && targetInt)
                ? `${sourceInt} ↔ ${targetInt}`
                : '';

            // Add edge to graph
            const newEdge = this.cy.add({
                group: 'edges',
                data: {
                    id: `${sourceId}-${targetId}`,
                    source: sourceId,
                    target: targetId,
                    label: label
                }
            });

            // Mark topology as modified
            this.markTopologyModified();

            // Update stats
            UI.updateStats(
                this.cy.nodes().length,
                this.cy.edges().length,
                document.getElementById('layout-select').value
            );

            UI.showToast(`Connection created: ${sourceId} ↔ ${targetId}`, 'success');
            modal.remove();

            // Select the new edge
            this.cy.elements().unselect();
            newEdge.select();
            this.showEdgeInfo(newEdge);
        };

        const handleCancel = () => {
            modal.remove();
        };

        createBtn.addEventListener('click', handleCreate);
        cancelBtn.addEventListener('click', handleCancel);

        modal.addEventListener('click', (e) => {
            if (e.target === modal) handleCancel();
        });
    },

    /**
     * Hide info panel
     */
    hideInfoPanel() {
        document.getElementById('info-panel').classList.remove('active');
    },

    /**
     * Fit graph to view
     */
    fitToView() {
        if (this.cy) {
            this.cy.fit(null, 50);
        }
    },

    /**
     * Export graph as PNG
     */
    exportPNG() {
        if (!this.cy) return;

        const bg = getComputedStyle(document.documentElement)
            .getPropertyValue('--md-background').trim();

        const png = this.cy.png({
            output: 'blob',
            bg: bg,
            full: true
        });

        const url = URL.createObjectURL(png);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'topology.png';
        a.click();
        URL.revokeObjectURL(url);

        UI.showToast('Image exported successfully', 'success');
    },

    /**
     * Update graph styles (e.g., after theme change)
     */
    updateStyles() {
        if (this.cy) {
            this.cy.style(this.getStyles());
        }
    },

    /**
     * Export current topology state (for saving)
     */
    exportTopology() {
        if (!this.cy) return null;

        const topology = {};

        this.cy.nodes().forEach(node => {
            const data = node.data();
            topology[data.id] = {
                node_details: {
                    ip: data.ip || '',
                    platform: data.platform || 'Unknown'
                },
                peers: {}
            };
        });

        // Build peer relationships from edges
        this.cy.edges().forEach(edge => {
            const data = edge.data();
            const source = data.source;
            const target = data.target;

            if (!topology[source].peers[target]) {
                topology[source].peers[target] = {
                    connections: []
                };
            }

            // Parse label to get interface names
            const label = data.label || '';
            const interfaces = label.split(' ↔ ');
            if (interfaces.length === 2) {
                topology[source].peers[target].connections.push(interfaces);
            }
        });

        return topology;
    }
};