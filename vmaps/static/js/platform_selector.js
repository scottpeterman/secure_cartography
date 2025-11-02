// static/js/platform_selector.js - Enhanced with visual picker button

class PlatformSelector {
    constructor(containerElement, options = {}) {
        this.container = containerElement;
        this.selectedValue = options.initialValue || '';
        this.allowCustom = options.allowCustom !== false;
        this.onChange = options.onChange || (() => {});

        this.render();
    }

    render() {
        const grouped = platformManager.getGroupedPlatforms();

        const html = `
            <div class="platform-selector">
                <div class="platform-input-row">
                    <select id="platform-select" class="platform-dropdown">
                        <option value="">Select Platform...</option>
                        ${Object.entries(grouped).map(([category, platforms]) => `
                            <optgroup label="${category}">
                                ${platforms.map(p => `
                                    <option value="${p.value}"
                                            data-icon="${p.icon}"
                                            ${p.value === this.selectedValue ? 'selected' : ''}>
                                        ${p.label}
                                    </option>
                                `).join('')}
                            </optgroup>
                        `).join('')}
                        ${this.allowCustom ? `
                            <optgroup label="Custom">
                                <option value="__custom__">Custom Platform...</option>
                            </optgroup>
                        ` : ''}
                    </select>

                    <button type="button" class="platform-picker-btn" id="open-platform-picker">
                        <i data-lucide="grid-3x3"></i>
                        <span>Browse</span>
                    </button>
                </div>

                <div class="platform-preview">
                    <img id="platform-icon-preview"
                         src=""
                         alt="Platform icon"
                         style="display: none;">
                    <span id="platform-name-preview" class="platform-name"></span>
                </div>

                ${this.allowCustom ? `
                    <div id="custom-platform-input" style="display: none;">
                        <input type="text"
                               id="custom-platform-text"
                               placeholder="Enter custom platform (e.g., FortiGate-60E)"
                               class="platform-input">
                        <small class="hint">
                            Will use generic icon if no pattern match
                        </small>
                    </div>
                ` : ''}
            </div>
        `;

        this.container.innerHTML = html;
        this.attachEventListeners();
        this.updatePreview();

        // Reinitialize Lucide icons for the new button
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }

    attachEventListeners() {
        const select = document.getElementById('platform-select');
        const customInput = document.getElementById('custom-platform-text');
        const pickerBtn = document.getElementById('open-platform-picker');

        select.addEventListener('change', (e) => {
            if (e.target.value === '__custom__') {
                document.getElementById('custom-platform-input').style.display = 'block';
                document.getElementById('platform-icon-preview').style.display = 'none';
            } else {
                document.getElementById('custom-platform-input').style.display = 'none';
                this.selectedValue = e.target.value;
                this.updatePreview();
                this.onChange(this.selectedValue);
            }
        });

        if (customInput) {
            customInput.addEventListener('input', (e) => {
                this.selectedValue = e.target.value;
                this.onChange(this.selectedValue);
            });
        }

        if (pickerBtn) {
            pickerBtn.addEventListener('click', () => {
                this.showPlatformPickerModal();
            });
        }
    }

    updatePreview() {
        const preview = document.getElementById('platform-icon-preview');
        const namePreview = document.getElementById('platform-name-preview');

        if (this.selectedValue && this.selectedValue !== '__custom__') {
            const icon = platformManager.getIconForPlatform(this.selectedValue);
            preview.src = icon;
            preview.style.display = 'inline-block';

            if (namePreview) {
                namePreview.textContent = this.selectedValue;
                namePreview.style.display = 'inline-block';
            }
        } else {
            preview.style.display = 'none';
            if (namePreview) {
                namePreview.style.display = 'none';
            }
        }
    }

    showPlatformPickerModal() {
        const grouped = platformManager.getGroupedPlatforms();

        // Create modal
        const modal = document.createElement('div');
        modal.className = 'modal platform-picker-modal';
        modal.id = 'platform-picker-modal';
        modal.style.display = 'flex';

        const modalHTML = `
            <div class="modal-content modal-large">
                <div class="modal-header">
                    <h2>
                        <i data-lucide="grid-3x3"></i>
                        Select Platform
                    </h2>
                    <button class="modal-close" data-modal="platform-picker-modal">
                        <i data-lucide="x"></i>
                    </button>
                </div>
                <div class="modal-body">
                    <div class="platform-search">
                        <input type="text"
                               id="platform-search-input"
                               placeholder="Search platforms..."
                               class="platform-search-input">
                    </div>
                    <div class="platform-grid">
                        ${Object.entries(grouped).map(([category, platforms]) => `
                            <div class="platform-category">
                                <h3 class="platform-category-title">${category}</h3>
                                <div class="platform-items">
                                    ${platforms.map(p => `
                                        <div class="platform-item" data-value="${p.value}" data-label="${p.label}">
                                            <img src="${p.icon}" alt="${p.label}" class="platform-item-icon">
                                            <span class="platform-item-label">${p.label}</span>
                                        </div>
                                    `).join('')}
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn-secondary close-picker">
                        Cancel
                    </button>
                </div>
            </div>
        `;

        modal.innerHTML = modalHTML;
        document.body.appendChild(modal);

        // Reinitialize Lucide icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }

        // Add event listeners
        const searchInput = modal.querySelector('#platform-search-input');
        const platformItems = modal.querySelectorAll('.platform-item');
        const closeBtn = modal.querySelector('.close-picker');
        const modalClose = modal.querySelector('.modal-close');

        // Search functionality
        searchInput.addEventListener('input', (e) => {
            const searchTerm = e.target.value.toLowerCase();

            platformItems.forEach(item => {
                const label = item.dataset.label.toLowerCase();
                const value = item.dataset.value.toLowerCase();

                if (label.includes(searchTerm) || value.includes(searchTerm)) {
                    item.style.display = 'flex';
                } else {
                    item.style.display = 'none';
                }
            });

            // Hide empty categories
            modal.querySelectorAll('.platform-category').forEach(category => {
                const visibleItems = category.querySelectorAll('.platform-item[style="display: flex;"], .platform-item:not([style*="display: none"])');
                category.style.display = visibleItems.length > 0 ? 'block' : 'none';
            });
        });

        // Platform item click
        platformItems.forEach(item => {
            item.addEventListener('click', () => {
                const value = item.dataset.value;
                this.setValue(value);
                this.onChange(value);
                modal.remove();
            });
        });

        // Close buttons
        closeBtn.addEventListener('click', () => modal.remove());
        modalClose.addEventListener('click', () => modal.remove());

        // Click outside to close
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });

        // Focus search input
        setTimeout(() => searchInput.focus(), 100);
    }

    getValue() {
        const select = document.getElementById('platform-select');
        if (select.value === '__custom__') {
            return document.getElementById('custom-platform-text').value;
        }
        return select.value;
    }

    setValue(value) {
        this.selectedValue = value;

        // Check if value exists in dropdown
        const select = document.getElementById('platform-select');
        const option = Array.from(select.options).find(opt => opt.value === value);

        if (option) {
            select.value = value;
        } else if (this.allowCustom && value) {
            // Custom value
            select.value = '__custom__';
            document.getElementById('custom-platform-input').style.display = 'block';
            document.getElementById('custom-platform-text').value = value;
        }

        this.updatePreview();
    }
}

console.log("platform_selector.js (enhanced) loaded...");