// Authentication Module

// Global Auth object
const Auth = {
    // Authentication Functions - SIMPLE USER IDENTIFICATION (no auth modal in HTML)
    async checkAuthStatus() {
        // Generate or retrieve unique user ID for this browser session
        let userId = localStorage.getItem('shakshuka_user_id');
        if (!userId) {
            userId = 'user_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('shakshuka_user_id', userId);
            console.log('Generated new user ID:', userId);
        } else {
            console.log('Using existing user ID:', userId);
        }
        
        // Set user as authenticated with unique ID
        AppState.set('isAuthenticated', true);
        AppState.set('passwordSet', true);
        AppState.set('userId', userId);
        
        // Load app data directly
        console.log('Loading app data for user:', userId);
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
            const response = await fetch('/api/auth/setup', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
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
            const response = await fetch('/api/auth/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
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
        Tasks.loadTasks();
        loadSettings();
        loadUpdateSettings();
        generateTimeSlots();
        applyThemeAndDPI();
        setupDailyReset();
        setupKeyboardShortcuts();
        initializeLogging();

        // If we're on the planner page, make sure it's loaded
        const currentPage = AppState.get('currentPage');
        console.log('Current page after loadAppData:', currentPage);
        if (currentPage === 'planner') {
            console.log('Loading planner data after app data load');
            loadPlannerData();
        }
    },

    // Reset user session - generates new user ID
    resetUserSession() {
        console.log('Resetting user session...');
        localStorage.removeItem('shakshuka_user_id');
        console.log('User session reset. Please refresh the page.');
        showNotification('User session reset. Please refresh the page to get a new user ID.', 'info');
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