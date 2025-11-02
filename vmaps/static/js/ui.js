/**
 * UI Utilities for SecureCartography Visualizer
 * Toast notifications, modals, and other UI helpers
 */

const UI = {
    /**
     * Show a toast notification
     */
    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;

        document.body.appendChild(toast);

        // Animate in
        setTimeout(() => toast.classList.add('show'), 10);

        // Remove after 3 seconds
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    },

    /**
     * Show loading overlay
     */
    showLoading() {
        document.getElementById('loading').classList.remove('hidden');
    },

    /**
     * Hide loading overlay
     */
    hideLoading() {
        document.getElementById('loading').classList.add('hidden');
    },

    /**
     * Show a confirmation dialog
     */
    async confirm(message, title = 'Confirm') {
        return new Promise((resolve) => {
            const modal = document.createElement('div');
            modal.className = 'modal-overlay';
            modal.innerHTML = `
                <div class="modal-dialog">
                    <div class="modal-header">
                        <h3>${title}</h3>
                    </div>
                    <div class="modal-body">
                        <p>${message}</p>
                    </div>
                    <div class="modal-footer">
                        <button class="md-button md-button-text cancel-btn">Cancel</button>
                        <button class="md-button md-button-filled confirm-btn">Confirm</button>
                    </div>
                </div>
            `;

            document.body.appendChild(modal);

            modal.querySelector('.cancel-btn').addEventListener('click', () => {
                modal.remove();
                resolve(false);
            });

            modal.querySelector('.confirm-btn').addEventListener('click', () => {
                modal.remove();
                resolve(true);
            });

            // Close on overlay click
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    modal.remove();
                    resolve(false);
                }
            });
        });
    },

    /**
     * Show a prompt dialog
     */
    async prompt(message, defaultValue = '', title = 'Input') {
        return new Promise((resolve) => {
            const modal = document.createElement('div');
            modal.className = 'modal-overlay';
            modal.innerHTML = `
                <div class="modal-dialog">
                    <div class="modal-header">
                        <h3>${title}</h3>
                    </div>
                    <div class="modal-body">
                        <p>${message}</p>
                        <input type="text" class="modal-input" value="${defaultValue}" placeholder="Enter value...">
                    </div>
                    <div class="modal-footer">
                        <button class="md-button md-button-text cancel-btn">Cancel</button>
                        <button class="md-button md-button-filled confirm-btn">OK</button>
                    </div>
                </div>
            `;

            document.body.appendChild(modal);

            const input = modal.querySelector('.modal-input');
            input.focus();
            input.select();

            const handleConfirm = () => {
                const value = input.value.trim();
                modal.remove();
                resolve(value || null);
            };

            const handleCancel = () => {
                modal.remove();
                resolve(null);
            };

            modal.querySelector('.cancel-btn').addEventListener('click', handleCancel);
            modal.querySelector('.confirm-btn').addEventListener('click', handleConfirm);

            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') handleConfirm();
                if (e.key === 'Escape') handleCancel();
            });

            modal.addEventListener('click', (e) => {
                if (e.target === modal) handleCancel();
            });
        });
    },

    /**
     * Update statistics display
     */
    updateStats(devices, connections, layout) {
        document.getElementById('stat-devices').textContent = devices;
        document.getElementById('stat-connections').textContent = connections;
        document.getElementById('stat-layout').textContent = layout;
    }
};