/**
 * Daily Reset Overlay
 * Shows a loading animation when daily reset occurs
 */

const DailyResetOverlay = {
    show() {
        // Create overlay if it doesn't exist
        let overlay = document.getElementById('daily-reset-overlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.id = 'daily-reset-overlay';
            overlay.className = 'daily-reset-overlay';
            overlay.innerHTML = `
                <div class="daily-reset-content">
                    <div class="daily-reset-spinner"></div>
                    <h2 class="daily-reset-title">Tasks are being reset...</h2>
                    <p class="daily-reset-subtitle">Starting a fresh day</p>
                </div>
            `;
            document.body.appendChild(overlay);
        }

        // Show overlay with fade-in
        overlay.style.display = 'flex';
        setTimeout(() => {
            overlay.classList.add('active');
        }, 10);

        console.log('[DailyResetOverlay] Showing reset overlay');
    },

    hide() {
        const overlay = document.getElementById('daily-reset-overlay');
        if (overlay) {
            overlay.classList.remove('active');
            setTimeout(() => {
                overlay.style.display = 'none';
            }, 300); // Match CSS transition duration
        }
        console.log('[DailyResetOverlay] Hiding reset overlay');
    },

    showForDuration(duration = 2000) {
        this.show();
        setTimeout(() => {
            this.hide();
        }, duration);
    }
};

// Export globally
window.DailyResetOverlay = DailyResetOverlay;
