/**
 * ModalManager - Centralized modal management
 * Provides unified open/close logic for all modals
 */

class ModalManager {
    constructor() {
        this.activeModals = new Set();
        this.setupGlobalListeners();
    }

    setupGlobalListeners() {
        // Close modal on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.activeModals.size > 0) {
                const lastModal = Array.from(this.activeModals).pop();
                this.close(lastModal);
            }
        });
    }

    /**
     * Open a modal by ID
     * @param {string} modalId - The modal element ID
     * @param {Object} options - Optional configuration
     */
    open(modalId, options = {}) {
        const modal = document.getElementById(modalId);
        if (!modal) {
            console.error(`[ModalManager] Modal not found: ${modalId}`);
            return false;
        }

        // Close other modals if not stacking
        if (!options.allowStacking) {
            this.closeAll();
        }

        modal.style.display = 'flex';
        modal.classList.add('active');
        this.activeModals.add(modalId);

        // Focus first input if available
        if (options.autoFocus !== false) {
            const firstInput = modal.querySelector('input, textarea, select');
            if (firstInput) {
                setTimeout(() => firstInput.focus(), 100);
            }
        }

        // Setup backdrop click to close
        if (options.closeOnBackdrop !== false) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    this.close(modalId);
                }
            });
        }

        return true;
    }

    /**
     * Close a modal by ID
     * @param {string} modalId - The modal element ID
     */
    close(modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) {
            console.error(`[ModalManager] Modal not found: ${modalId}`);
            return false;
        }

        modal.style.display = 'none';
        modal.classList.remove('active');
        this.activeModals.delete(modalId);

        return true;
    }

    /**
     * Close all open modals
     */
    closeAll() {
        const modals = Array.from(this.activeModals);
        modals.forEach(modalId => this.close(modalId));
    }

    /**
     * Check if a modal is open
     * @param {string} modalId - The modal element ID
     */
    isOpen(modalId) {
        return this.activeModals.has(modalId);
    }

    /**
     * Toggle a modal
     * @param {string} modalId - The modal element ID
     */
    toggle(modalId) {
        if (this.isOpen(modalId)) {
            this.close(modalId);
        } else {
            this.open(modalId);
        }
    }
}

// Create global instance
window.ModalManager = new ModalManager();

// Backward compatibility - create global helper functions
window.openModal = (modal) => {
    const modalId = typeof modal === 'string' ? modal : modal.id;
    return window.ModalManager.open(modalId);
};

window.closeModal = (modal) => {
    const modalId = typeof modal === 'string' ? modal : modal.id;
    return window.ModalManager.close(modalId);
};
