/**
 * Theme Management for SecureCartography Visualizer
 * Handles theme switching and persistence
 */

const Theme = {
    /**
     * Initialize theme system
     */
    init() {
        // Load saved theme or default to light
        const savedTheme = localStorage.getItem('theme') || 'light';
        this.setTheme(savedTheme, false);

        // Setup event listener
        const themeSelect = document.getElementById('theme-select');
        if (themeSelect) {
            themeSelect.value = savedTheme;
            themeSelect.addEventListener('change', (e) => {
                this.setTheme(e.target.value);
            });
        }
    },

    /**
     * Set active theme
     */
    setTheme(themeName, save = true) {
        // Update HTML attribute
        document.documentElement.setAttribute('data-theme', themeName);

        // Save preference
        if (save) {
            localStorage.setItem('theme', themeName);
        }

        // Update graph styles if graph exists
        if (Graph.cy) {
            Graph.updateStyles();
        }

        console.log(`Theme set to: ${themeName}`);
    },

    /**
     * Get current theme
     */
    getCurrentTheme() {
        return document.documentElement.getAttribute('data-theme') || 'light';
    }
};