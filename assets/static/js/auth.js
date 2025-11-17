// Authentication Module - Simplified for PIN Authentication

// Global Auth object
const Auth = {
    // Authentication handled by PIN system
    async checkAuthStatus() {
        // Set default user data (PIN auth handles access control)
        console.log('Using PIN authentication system');
        
        // Set default user data
        AppState.set('isAuthenticated', true);
        AppState.set('passwordSet', true);
        AppState.set('userId', 'default_user');
        AppState.set('username', 'default_user');
        
        // Load app data
        console.log('Loading app data for default user');
        this.loadAppData();
    },

    showAuthModal(mode) {
        console.log('Showing auth modal in mode:', mode);
        const authModal = document.getElementById('auth-modal');
        const setupForm = document.getElementById('setup-form');
        const loginForm = document.getElementById('login-form');
        const authModalTitle = document.getElementById('auth-modal-title');
        const authSwitchText = document.getElementById('auth-switch-text');
        const authSwitchBtn = document.getElementById('auth-switch-btn');

        console.log('Auth modal element:', authModal);
        console.log('Setup form element:', setupForm);
        console.log('Login form element:', loginForm);

        if (!authModal) {
            console.error('Auth modal element not found!');
            return;
        }

        if (mode === 'setup') {
            setupForm.style.display = 'block';
            loginForm.style.display = 'none';
            authModalTitle.textContent = 'Welcome to Shakshuka';
            authSwitchText.textContent = 'Already have an account?';
            authSwitchBtn.textContent = 'Login';
        } else {
            setupForm.style.display = 'none';
            loginForm.style.display = 'block';
            authModalTitle.textContent = 'Login to Shakshuka';
            authSwitchText.textContent = "Don't have an account?";
            authSwitchBtn.textContent = 'Setup';

            // Auto-fill password if remembered
            const savedPassword = localStorage.getItem('shakshuka_password');
            if (savedPassword) {
                const passwordInput = document.getElementById('login-password');
                const rememberCheckbox = document.getElementById('remember-password');
                if (passwordInput) {
                    passwordInput.value = savedPassword;
                }
                if (rememberCheckbox) {
                    rememberCheckbox.checked = true;
                }
            }
        }

        authModal.style.display = 'flex';
        authModal.style.position = 'fixed';
        authModal.style.top = '0';
        authModal.style.left = '0';
        authModal.style.width = '100%';
        authModal.style.height = '100%';
        authModal.style.zIndex = '9999';
        authModal.style.backgroundColor = 'rgba(0, 0, 0, 0.6)';
        authModal.style.alignItems = 'center';
        authModal.style.justifyContent = 'center';
        console.log('Auth modal displayed, style:', authModal.style.display);
    },

    hideAuthModal() {
        const authModal = document.getElementById('auth-modal');
        authModal.style.display = 'none';
    },

    async setupPassword() {
        const password = document.getElementById('setup-password').value.trim();
        const confirmPassword = document.getElementById('setup-confirm-password').value.trim();

        console.log('Setup Password Debug:');
        console.log('- Password element:', document.getElementById('setup-password'));
        console.log('- Confirm password element:', document.getElementById('setup-confirm-password'));
        console.log('- Password value:', password);
        console.log('- Confirm password value:', confirmPassword);
        console.log('- Password length:', password.length);
        console.log('- Confirm password length:', confirmPassword.length);
        console.log('- Passwords match:', password === confirmPassword);

        if (!password || !confirmPassword) {
            console.log('Validation failed: Empty fields');
            Utils.safeShowNotification('Please fill in both password fields', 'error');
            return;
        }

        if (password !== confirmPassword) {
            Utils.safeShowNotification('Passwords do not match', 'error');
            return;
        }

        if (password.length < 6) {
            Utils.safeShowNotification('Password must be at least 6 characters', 'error');
            return;
        }

        try {
            const response = await apiCall('/api/auth/setup', {
                method: 'POST',
                body: JSON.stringify({ password })
            });

            if (response.ok) {
                AppState.set('isAuthenticated', true);
                AppState.set('passwordSet', true);
                this.hideAuthModal();
                this.loadAppData();
                Utils.safeShowNotification('Account setup successful!', 'success');
            } else {
                const error = await response.json();
                console.error('Setup error response:', error);
                Utils.safeShowNotification(error.error || 'Setup failed', 'error');
            }
        } catch (error) {
            console.error('Setup error:', error);
            Utils.safeShowNotification('Setup failed', 'error');
        }
    },

    async login() {
        const password = document.getElementById('login-password').value;
        const rememberPassword = document.getElementById('remember-password')?.checked || false;

        if (!password) {
            Utils.safeShowNotification('Please enter your password', 'error');
            return;
        }

        try {
            const response = await apiCall('/api/auth/login', {
                method: 'POST',
                body: JSON.stringify({ password })
            });

            if (response.ok) {
                AppState.set('isAuthenticated', true);
                AppState.set('passwordSet', true);

                // Remember password if checkbox is checked
                if (rememberPassword) {
                    localStorage.setItem('shakshuka_password', password);
                } else {
                    localStorage.removeItem('shakshuka_password');
                }

                this.hideAuthModal();
                this.loadAppData();
                Utils.safeShowNotification('Login successful!', 'success');
            } else {
                const error = await response.json();
                Utils.safeShowNotification(error.error || 'Login failed', 'error');
            }
        } catch (error) {
            console.error('Login error:', error);
            Utils.safeShowNotification('Login failed', 'error');
        }
    },

    loadAppData() {
        console.log('loadAppData called');
        // Load all app data after authentication
        
        // Safety check: ensure Tasks object exists before calling
        if (typeof Tasks !== 'undefined' && Tasks.loadTasks) {
            Tasks.loadTasks();
        } else {
            console.warn('Tasks object not yet loaded, trying again with delay');
            setTimeout(() => {
                if (typeof Tasks !== 'undefined' && Tasks.loadTasks) {
                    Tasks.loadTasks();
                } else {
                    console.error('Tasks module failed to load - calling loadTasks directly');
                    // Fallback: if Tasks still isn't defined, try calling global function
                    if (typeof loadTasksGlobal === 'function') {
                        loadTasksGlobal();
                    }
                }
            }, 100);
        }
        
        // Call initialization functions with safety checks
        if (typeof window.Settings !== 'undefined' && typeof window.Settings.load === 'function') {
            window.Settings.load(); // Preferred path: uses Settings module and handles theme + loader
        } else if (typeof loadSettings === 'function') {
            // Fallback to legacy global implementation if needed
            loadSettings();
        } else {
            console.warn('loadSettings not available');
        }
        
        if (typeof loadUpdateSettings === 'function') {
            loadUpdateSettings();
        } else {
            console.warn('loadUpdateSettings not available');
        }
        
        // Prefer Planner v2 lazy initialization when navigating to planner page
        if (typeof window.ensurePlannerV2Init === 'function') {
            // Do nothing here; planner v2 will initialize on navigateToPage('planner')
        } else if (typeof generateTimeSlots === 'function') {
            const timeGrid = document.getElementById('time-grid');
            if (timeGrid) {
                generateTimeSlots();
            } else {
                console.log('Time grid not in DOM yet, will generate when navigating to planner');
            }
        } else {
            console.warn('Planner initialization not available');
        }
        
        if (typeof setupDailyReset === 'function') {
            setupDailyReset();
        } else {
            console.warn('setupDailyReset not available');
        }
        
        // setupKeyboardShortcuts(); // REMOVED - now handled by Keyboard module in app-init.js
        
        if (typeof initializeLogging === 'function') {
            initializeLogging();
        } else {
            console.warn('initializeLogging not available');
        }

        // Always start with tasks page on load
        const currentPage = 'tasks';
        console.log('Current page after loadAppData:', currentPage);
        
// Navigate to the tasks page
        if (typeof navigateToPage === 'function') {
            navigateToPage(currentPage);
        } else {
            console.warn('navigateToPage not available');
        }
        try { if (window.NavbarScheduleCard && typeof window.NavbarScheduleCard.init === 'function') { window.NavbarScheduleCard.init(); } } catch(e) {}
    },

    // Reset user session - generates new user ID
    resetUserSession() {
        console.log('Resetting enhanced user session...');
        localStorage.removeItem('shakshuka_user_id');
        sessionStorage.removeItem('shakshuka_session_id');
        console.log('Enhanced user session reset. Please refresh the page.');
        showNotification('Enhanced user session reset. Please refresh the page to get a new user ID.', 'info');
    }
};

// Make Auth globally available
window.Auth = Auth;

// Global functions for backward compatibility
function hideAuthModal() {
    Auth.hideAuthModal();
}

async function setupPassword() {
    return Auth.setupPassword();
}

async function login() {
    return Auth.login();
}

function loadAppData() {
    return Auth.loadAppData();
}