// Notification queue - show one at a time
const _notifQueue = [];
let _notifActive = null;  // { el, timeoutId }

function _getNotifContainer() {
    let container = document.getElementById('notification-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'notification-container';
        container.style.cssText = [
            'position:fixed', 'right:20px', 'bottom:20px', 'z-index:4000',
            'display:flex', 'flex-direction:column', 'align-items:flex-end', 'gap:10px'
        ].join(';');
        document.body.appendChild(container);
    }
    return container;
}

function _dismissActive(then) {
    if (!_notifActive) { if (then) then(); return; }
    const { el, timeoutId } = _notifActive;
    clearTimeout(timeoutId);
    _notifActive = null;
    el.style.animation = 'slideOutRight 0.3s ease-in-out';
    setTimeout(() => {
        if (el.parentNode) el.parentNode.removeChild(el);
        if (then) then();
    }, 300);
}

function _showNext() {
    if (_notifActive || _notifQueue.length === 0) return;
    const item = _notifQueue.shift();
    const { message, type, isPersistent, onClick, isAuthError, onAutoLogin } = item;

    const container = _getNotifContainer();
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;

    if (isAuthError || onClick) notification.style.cursor = 'pointer';
    if (isAuthError) notification.title = 'Click to open login dialog';

    notification.innerHTML = `
        <div class="notification-content">
            <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
            <span>${message}</span>
            ${isAuthError ? '<span class="notification-hint">(Click to login)</span>' : ''}
            <button class="notification-close" onclick="closeNotification(this)">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `;
    notification.style.cssText = [
        `background:${type === 'success' ? 'linear-gradient(135deg,#28A745,#20C997)' : type === 'error' ? 'linear-gradient(135deg,#DC3545,#E74C3C)' : 'linear-gradient(135deg,#17A2B8,#20C997)'}`,
        'color:white', 'padding:1rem 1.5rem', 'border-radius:12px',
        'box-shadow:0 8px 25px rgba(0,0,0,0.2)', 'z-index:4000',
        'animation:slideInRight 0.3s ease-in-out', 'max-width:400px',
        isAuthError ? 'border:2px solid rgba(255,255,255,0.3)' : ''
    ].filter(Boolean).join(';');

    if (onClick) {
        notification.addEventListener('click', (evt) => {
            if (evt.target && evt.target.closest && evt.target.closest('.notification-close')) return;
            try { onClick(); } catch (e) { console.error('Notification onClick failed', e); }
        });
    }

    // Play sound
    try {
        const settings = (typeof AppState !== 'undefined' && AppState && typeof AppState.get === 'function')
            ? (AppState.get('currentSettings') || {}) : {};
        if (settings.notification_sound) {
            const audioCtx = window._notifAudioCtx || (window._notifAudioCtx = new (window.AudioContext || window.webkitAudioContext)());
            const osc = audioCtx.createOscillator();
            const gain = audioCtx.createGain();
            osc.connect(gain); gain.connect(audioCtx.destination);
            osc.frequency.value = type === 'success' ? 880 : type === 'error' ? 440 : 660;
            gain.gain.value = 0.08;
            osc.start(); osc.stop(audioCtx.currentTime + 0.12);
        }
    } catch (e) { /* audio not available */ }

    container.appendChild(notification);

    if (isAuthError && onAutoLogin !== false) {
        setTimeout(() => {
            if (typeof window.showAuthModal === 'function') window.showAuthModal('login');
            else if (typeof window.PINAuthInstance !== 'undefined') window.PINAuthInstance.init();
        }, 1000);
    }

    if (!isPersistent) {
        // Default 5s; if more items are queued we'll cut it short when they arrive
        const duration = 5000;
        const timeoutId = setTimeout(() => {
            _notifActive = null;
            notification.style.animation = 'slideOutRight 0.3s ease-in-out';
            setTimeout(() => {
                if (notification.parentNode) notification.parentNode.removeChild(notification);
                _showNext();
            }, 300);
        }, duration);
        _notifActive = { el: notification, timeoutId };
    }
}

function showNotification(message, type = 'info', options = {}) {
    const isPersistent = options && options.persistent === true;
    const onClick = options && typeof options.onClick === 'function' ? options.onClick : null;
    const isAuthError = type === 'error' && (
        message.toLowerCase().includes('login') ||
        message.toLowerCase().includes('authentication') ||
        message.toLowerCase().includes('access') ||
        message.toLowerCase().includes('unauthorized')
    );

    // If something is currently showing and more items will be queued, cut current to 2s
    if (_notifActive && _notifQueue.length === 0) {
        const { el, timeoutId } = _notifActive;
        clearTimeout(timeoutId);
        const newTimeoutId = setTimeout(() => {
            _notifActive = null;
            el.style.animation = 'slideOutRight 0.3s ease-in-out';
            setTimeout(() => {
                if (el.parentNode) el.parentNode.removeChild(el);
                _showNext();
            }, 300);
        }, 2000);
        _notifActive.timeoutId = newTimeoutId;
    }

    _notifQueue.push({ message, type, isPersistent, onClick, isAuthError, onAutoLogin: options.autoOpenLogin });
    _showNext();
}

function closeNotification(closeButton) {
    const notification = closeButton.closest('.notification');
    if (notification) {
        notification.style.animation = 'slideOutRight 0.3s ease-in-out';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }
}
