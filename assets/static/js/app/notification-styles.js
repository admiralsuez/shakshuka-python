function injectNotificationStyles() {
    try {
        const existing = document.getElementById('notification-styles');
        if (existing) {
            return;
        }

        // Add CSS for notifications
        const notificationStyles = `
    @keyframes slideInRight {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    
    @keyframes slideOutRight {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
    
    .notification-content {
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
`;

        // Inject notification styles
        const styleSheet = document.createElement('style');
        styleSheet.id = 'notification-styles';
        styleSheet.textContent = notificationStyles;
        document.head.appendChild(styleSheet);
    } catch (e) {
        // Intentionally swallow errors; style injection should never block app startup.
    }
}

injectNotificationStyles();
