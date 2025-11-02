/**
 * Layout Management for SecureCartography Visualizer
 * Handles layout algorithms and position persistence
 * Enhanced to save topology changes
 */

const Layout = {
    currentMapName: null,
    autoSaveTimeout: null,

    /**
     * Initialize layout module
     */
    init() {
        this.setupEventListeners();
    },

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        const layoutSelect = document.getElementById('layout-select');
        if (layoutSelect) {
            layoutSelect.addEventListener('change', () => this.applyLayout());
        }
    },

    /**
     * Apply selected layout algorithm
     */
    applyLayout() {
        if (!Graph.cy) return;

        const layoutName = document.getElementById('layout-select').value;
        UI.updateStats(
            Graph.cy.nodes().length,
            Graph.cy.edges().length,
            layoutName
        );

        let layoutConfig = {
            name: layoutName,
            animate: true,
            animationDuration: 500,
            fit: true,
            padding: 50
        };

        // Specific configurations for different layouts
        if (layoutName === 'cose') {
            layoutConfig.nodeRepulsion = 8000;
            layoutConfig.idealEdgeLength = 100;
            layoutConfig.edgeElasticity = 100;
            layoutConfig.nestingFactor = 5;
            layoutConfig.gravity = 80;
            layoutConfig.numIter = 1000;
        } else if (layoutName === 'breadthfirst') {
            layoutConfig.directed = true;
            layoutConfig.spacingFactor = 1.5;
        } else if (layoutName === 'circle') {
            layoutConfig.spacingFactor = 1.5;
        } else if (layoutName === 'concentric') {
            layoutConfig.spacingFactor = 1.5;
        }

        const layout = Graph.cy.layout(layoutConfig);
        layout.run();
    },

    /**
     * Save current layout positions (and topology if modified)
     */
    async saveLayout() {
        if (!Graph.cy) {
            console.log('Cannot save: no graph instance');
            return;
        }

        if (!this.currentMapName) {
            UI.showToast('No map selected', 'warning');
            return;
        }

        try {
            // Gather positions
            const positions = {};
            Graph.cy.nodes().forEach(node => {
                const pos = node.position();
                positions[node.id()] = { x: pos.x, y: pos.y };
            });

            const layoutData = {
                positions: positions,
                selectedLayout: document.getElementById('layout-select').value,
                timestamp: new Date().toISOString()
            };

            // Save layout
            const layoutResult = await API.saveLayout(this.currentMapName, layoutData);

            // If topology was modified, save it too
            if (Graph.topologyModified) {
                const topologyData = Graph.exportTopology();
                if (topologyData) {
                    await API.saveTopology(this.currentMapName, topologyData);
                    Graph.clearModifiedFlag();
                    UI.showToast(`Topology and layout saved for ${this.currentMapName}`, 'success');
                } else {
                    UI.showToast(`Layout saved for ${this.currentMapName}`, 'success');
                }
            } else if (layoutResult.success) {
                UI.showToast(`Layout saved for ${this.currentMapName}`, 'success');
            }

            // Update map selector to show checkmark
            const mapSelect = document.getElementById('map-select');
            const option = mapSelect.querySelector(`option[value="${this.currentMapName}"]`);
            if (option && !option.textContent.includes('✓')) {
                option.textContent = `${this.currentMapName} ✓`;
            }

        } catch (error) {
            console.error('Save layout error:', error);
            UI.showToast('Error saving layout', 'error');
        }
    },

    /**
     * Reset layout to default
     */
    async resetLayout() {
        if (!Graph.cy || !this.currentMapName) return;

        const confirmed = await UI.confirm(
            'Reset layout to default? This will delete your saved positions.',
            'Reset Layout'
        );

        if (!confirmed) return;

        try {
            const result = await API.resetLayout(this.currentMapName);

            if (result.success) {
                this.applyLayout();
                UI.showToast('Layout reset successfully', 'success');

                // Update map selector to remove checkmark
                const mapSelect = document.getElementById('map-select');
                const option = mapSelect.querySelector(`option[value="${this.currentMapName}"]`);
                if (option) {
                    option.textContent = this.currentMapName;
                }
            }
        } catch (error) {
            console.error('Reset error:', error);
            UI.showToast('Error resetting layout', 'error');
        }
    },

    /**
     * Restore saved layout positions
     */
    restoreLayout(savedLayout) {
        if (!Graph.cy || !savedLayout || !savedLayout.positions) return;

        console.log('Restoring saved layout...');

        // Restore positions
        Graph.cy.nodes().forEach(node => {
            const savedPos = savedLayout.positions[node.id()];
            if (savedPos) {
                node.position(savedPos);
            }
        });

        // Restore selected layout algorithm
        if (savedLayout.selectedLayout) {
            document.getElementById('layout-select').value = savedLayout.selectedLayout;
            UI.updateStats(
                Graph.cy.nodes().length,
                Graph.cy.edges().length,
                savedLayout.selectedLayout + ' (saved)'
            );
        }

        Graph.cy.fit(null, 50);
    },

    /**
     * Schedule autosave (debounced)
     */
    scheduleAutoSave() {
        if (this.autoSaveTimeout) {
            clearTimeout(this.autoSaveTimeout);
        }

        // Auto-save disabled - user must manually save
        // (Uncomment below to enable auto-save after 2 seconds)
        // this.autoSaveTimeout = setTimeout(() => {
        //     this.saveLayout();
        // }, 2000);
    },

    /**
     * Set current map name
     */
    setCurrentMap(mapName) {
        this.currentMapName = mapName;
    }
};