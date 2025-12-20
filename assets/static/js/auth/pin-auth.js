/**
 * PIN Authentication System
 * Handles 4-digit PIN authentication, setup, and recovery
 */

class PINAuth {
    constructor() {
        this.isAuthenticated = false;
        this.sessionToken = null;
        this.maxPinLength = 4;
        this.setupComplete = false;
        
        // Initialize on load
        this.init();
    }
    
    async init() {
        try {
            // Check if just authenticated (prevent loop after login)
            const justAuthenticated = sessionStorage.getItem('pin_authenticated');
            const authTime = sessionStorage.getItem('pin_auth_time');
            const timeSinceAuth = authTime ? (new Date().getTime() - parseInt(authTime)) : 999999;
            
            // If authenticated within last 10 seconds, skip auth check
            if (justAuthenticated === 'true' && timeSinceAuth < 10000) {
                this.isAuthenticated = true;
                this.hideAllAuthScreens();
                console.log('Recently authenticated, skipping PIN check');
                return;
            }
            
            // Clear old auth flags
            if (timeSinceAuth > 10000) {
                sessionStorage.removeItem('pin_authenticated');
                sessionStorage.removeItem('pin_auth_time');
            }
            
            // Check PIN status
            const status = await this.checkPINStatus();
            
            if (!status.setup_complete) {
                // Show PIN setup screen
                this.showPINSetup();
            } else if (status.session_valid) {
                // Session is still valid (remember PIN enabled)
                this.isAuthenticated = true;
                this.hideAllAuthScreens();
                console.log('Session restored from remember PIN');
                // Initialize app data
                setTimeout(() => {
                    if (typeof Auth !== 'undefined' && typeof Auth.loadAppData === 'function') {
                        Auth.loadAppData();
                    }
                }, 100);
            } else if (!this.isAuthenticated) {
                // Show PIN login screen
                this.showPINLogin(status);
            } else {
                // Already authenticated
                this.hideAllAuthScreens();
            }
        } catch (error) {
            console.error('PIN Auth initialization error:', error);
            this.showError('Failed to initialize authentication');
        }
    }
    
    async checkPINStatus() {
        const response = await fetch('/api/pin/status');
        if (!response.ok) {
            throw new Error('Failed to check PIN status');
        }
        const status = await response.json();
        this.setupComplete = status.setup_complete;
        return status;
    }
    
    showPINSetup() {
        // Hide main app content
        document.body.classList.add('auth-required');
        
        // Create setup modal
        const modal = this.createModal('PIN Setup', `
            <div class="pin-setup-container">
                <div class="pin-setup-header">
                    <h2>🔐 Welcome to Shakshuka</h2>
                    <p>Create a 4-digit PIN to secure your tasks</p>
                </div>
                
                <div class="pin-form">
                    <div class="pin-field-group">
                        <label for="setup-pin">Enter PIN</label>
                        <div class="pin-input-container">
                            <input type="password" id="setup-pin" maxlength="4" 
                                   class="pin-input" placeholder="••••" 
                                   inputmode="numeric" pattern="[0-9]*">
                            <button type="button" class="pin-toggle" onclick="PINAuthInstance.togglePINVisibility('setup-pin')">
                                <i class="fas fa-eye"></i>
                            </button>
                        </div>
                        <small>Enter 4 digits</small>
                    </div>
                    
                    <div class="pin-field-group">
                        <label for="confirm-pin">Confirm PIN</label>
                        <div class="pin-input-container">
                            <input type="password" id="confirm-pin" maxlength="4" 
                                   class="pin-input" placeholder="••••"
                                   inputmode="numeric" pattern="[0-9]*">
                            <button type="button" class="pin-toggle" onclick="PINAuthInstance.togglePINVisibility('confirm-pin')">
                                <i class="fas fa-eye"></i>
                            </button>
                        </div>
                        <small>Re-enter the same PIN</small>
                    </div>
                    
                    <div class="pin-error" id="setup-error"></div>
                    
                    <button class="btn-primary btn-large" onclick="PINAuthInstance.setupPIN()">
                        Create PIN
                    </button>
                </div>
                
                <div class="pin-info">
                    <p><i class="fas fa-info-circle"></i> Your PIN is encrypted and stored locally on your computer.</p>
                    <p><i class="fas fa-shield-alt"></i> After 10 failed attempts, access will be locked for 10 minutes.</p>
                </div>
            </div>
        `);
        
        document.body.appendChild(modal);
        
        // Focus first input
        setTimeout(() => document.getElementById('setup-pin').focus(), 100);
        
        // Add enter key handlers
        document.getElementById('setup-pin').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') document.getElementById('confirm-pin').focus();
        });
        document.getElementById('confirm-pin').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.setupPIN();
        });
    }
    
    showPINLogin(status = {}) {
        // Hide main app content
        document.body.classList.add('auth-required');
        
        const inCooldown = status.in_cooldown || false;
        const secondsRemaining = status.seconds_remaining || 0;
        const failedAttempts = status.failed_attempts || 0;
        const attemptsRemaining = 10 - failedAttempts;
        
        let cooldownMessage = '';
        if (inCooldown) {
            const minutes = Math.floor(secondsRemaining / 60);
            const seconds = secondsRemaining % 60;
            cooldownMessage = `
                <div class="pin-cooldown-warning">
                    <i class="fas fa-clock"></i>
                    Too many failed attempts. Try again in ${minutes}m ${seconds}s
                </div>
            `;
        }
        
        const modal = this.createModal('PIN Login', `
            <div class="pin-login-container">
                <div class="pin-login-header">
                    <div class="app-logo">🍳</div>
                    <h2>Shakshuka</h2>
                    <p>Enter your PIN to continue</p>
                </div>
                
                ${cooldownMessage}
                
                <div class="pin-form">
                    <div class="pin-field-group">
                        <div class="pin-input-container">
                            <input type="password" id="login-pin" maxlength="4" 
                                   class="pin-input pin-input-large" placeholder="••••"
                                   inputmode="numeric" pattern="[0-9]*"
                                   ${inCooldown ? 'disabled' : ''}>
                            <button type="button" class="pin-toggle" onclick="PINAuthInstance.togglePINVisibility('login-pin')"
                                    ${inCooldown ? 'disabled' : ''}>
                                <i class="fas fa-eye"></i>
                            </button>
                        </div>
                    </div>
                    
                    <div class="pin-attempts">
                        ${attemptsRemaining < 10 ? `${attemptsRemaining} attempts remaining` : ''}
                    </div>
                    
                    <div class="pin-error" id="login-error"></div>
                    
                    <div class="pin-remember">
                        <label class="checkbox-label">
                            <input type="checkbox" id="remember-pin" ${inCooldown ? 'disabled' : ''}>
                            <span>Remember for 7 days</span>
                        </label>
                    </div>
                    
                    <button class="btn-primary btn-large" onclick="PINAuthInstance.verifyPIN()"
                            ${inCooldown ? 'disabled' : ''}>
                        <i class="fas fa-unlock"></i> Unlock
                    </button>
                    
                    <button class="btn-text" onclick="PINAuthInstance.showForgotPIN()"
                            ${inCooldown ? 'disabled' : ''}>
                        Forgot PIN?
                    </button>
                </div>
            </div>
        `);
        
        document.body.appendChild(modal);
        
        // Focus input if not in cooldown
        if (!inCooldown) {
            setTimeout(() => document.getElementById('login-pin').focus(), 100);
            document.getElementById('login-pin').addEventListener('keypress', (e) => {
                if (e.key === 'Enter') this.verifyPIN();
            });
        }
        
        // Start cooldown countdown if needed
        if (inCooldown) {
            this.startCooldownCountdown(secondsRemaining);
        }
    }
    
    showForgotPIN() {
        const modal = this.createModal('Reset PIN', `
            <div class="pin-reset-container">
                <div class="pin-reset-header">
                    <h2>🔄 Reset PIN</h2>
                    <p>Create a new 4-digit PIN</p>
                </div>
                
                <div class="pin-form">
                    <div class="pin-field-group">
                        <label for="reset-new-pin">New PIN</label>
                        <div class="pin-input-container">
                            <input type="password" id="reset-new-pin" maxlength="4" 
                                   class="pin-input" placeholder="••••"
                                   inputmode="numeric" pattern="[0-9]*">
                            <button type="button" class="pin-toggle" onclick="PINAuthInstance.togglePINVisibility('reset-new-pin')">
                                <i class="fas fa-eye"></i>
                            </button>
                        </div>
                    </div>
                    
                    <div class="pin-field-group">
                        <label for="reset-confirm-pin">Confirm New PIN</label>
                        <div class="pin-input-container">
                            <input type="password" id="reset-confirm-pin" maxlength="4" 
                                   class="pin-input" placeholder="••••"
                                   inputmode="numeric" pattern="[0-9]*">
                            <button type="button" class="pin-toggle" onclick="PINAuthInstance.togglePINVisibility('reset-confirm-pin')">
                                <i class="fas fa-eye"></i>
                            </button>
                        </div>
                    </div>
                    
                    <div class="pin-error" id="reset-error"></div>
                    
                    <div class="pin-actions">
                        <button class="btn-secondary" onclick="PINAuthInstance.init()">
                            Cancel
                        </button>
                        <button class="btn-primary" onclick="PINAuthInstance.resetPIN()">
                            Reset PIN
                        </button>
                    </div>
                </div>
                
                <div class="pin-warning">
                    <i class="fas fa-exclamation-triangle"></i>
                    This will reset all failed attempt counters and cooldowns.
                </div>
            </div>
        `);
        
        // Remove old modal
        const oldModal = document.querySelector('.pin-auth-modal');
        if (oldModal) oldModal.remove();
        
        document.body.appendChild(modal);
        setTimeout(() => document.getElementById('reset-new-pin').focus(), 100);
        
        document.getElementById('reset-new-pin').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') document.getElementById('reset-confirm-pin').focus();
        });
        document.getElementById('reset-confirm-pin').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.resetPIN();
        });
    }
    
    createModal(title, content) {
        const modal = document.createElement('div');
        modal.className = 'pin-auth-modal';
        modal.innerHTML = `
            <div class="pin-auth-overlay"></div>
            <div class="pin-auth-content">
                ${content}
            </div>
        `;
        return modal;
    }
    
    async setupPIN() {
        const pin = document.getElementById('setup-pin').value;
        const confirmPin = document.getElementById('confirm-pin').value;
        const errorDiv = document.getElementById('setup-error');
        
        errorDiv.textContent = '';
        
        // Validation
        if (!pin || !confirmPin) {
            errorDiv.textContent = 'Please enter PIN in both fields';
            return;
        }
        
        if (pin.length !== 4) {
            errorDiv.textContent = 'PIN must be exactly 4 digits';
            return;
        }
        
        if (!/^\d+$/.test(pin)) {
            errorDiv.textContent = 'PIN must contain only numbers';
            return;
        }
        
        if (pin !== confirmPin) {
            errorDiv.textContent = 'PINs do not match';
            return;
        }
        
        try {
            const response = await fetch('/api/pin/setup', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    pin: pin,
                    confirm_pin: confirmPin
                })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.isAuthenticated = true;
                this.sessionToken = data.session_token;
                // Mark session so init() can skip re-auth briefly
                sessionStorage.setItem('pin_authenticated', 'true');
                sessionStorage.setItem('pin_auth_time', Date.now().toString());
                this.hideAllAuthScreens();
                this.showSuccess('PIN created successfully!');
                
                // Let the main app initialization pipeline handle the loader
                setTimeout(() => {
                    if (typeof Auth !== 'undefined' && typeof Auth.loadAppData === 'function') {
                        Auth.loadAppData();
                    }
                }, 300);
            } else {
                errorDiv.textContent = data.error || 'Failed to setup PIN';
            }
        } catch (error) {
            console.error('Setup PIN error:', error);
            errorDiv.textContent = 'Failed to setup PIN. Please try again.';
        }
    }
    
    async verifyPIN() {
        const pin = document.getElementById('login-pin').value;
        const remember = document.getElementById('remember-pin')?.checked || false;
        const errorDiv = document.getElementById('login-error');
        
        errorDiv.textContent = '';
        
        if (!pin || pin.length !== 4) {
            errorDiv.textContent = 'Please enter a 4-digit PIN';
            return;
        }
        
        try {
            const response = await fetch('/api/pin/verify', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ 
                    pin: pin,
                    remember: remember
                })
            });
            
            const data = await response.json();
            
            if (response.ok && data.success) {
                this.isAuthenticated = true;
                this.sessionToken = data.session_token;
                
                // Store authentication state to prevent re-login
                sessionStorage.setItem('pin_authenticated', 'true');
                sessionStorage.setItem('pin_auth_time', new Date().getTime());
                
                this.hideAllAuthScreens();
                this.showSuccess('Login successful!');
                
                // Let the main app initialization pipeline handle the loader
                setTimeout(() => {
                    if (typeof Auth !== 'undefined' && typeof Auth.loadAppData === 'function') {
                        Auth.loadAppData();
                    }
                }, 300);
            } else {
                errorDiv.textContent = data.error || 'Incorrect PIN';
                
                // Show attempts remaining
                if (data.attempts_remaining !== undefined) {
                    const attemptsDiv = document.querySelector('.pin-attempts');
                    if (attemptsDiv) {
                        attemptsDiv.textContent = `${data.attempts_remaining} attempts remaining`;
                        attemptsDiv.style.color = data.attempts_remaining <= 3 ? '#f44336' : '#ff9800';
                    }
                }
                
                // Clear input
                document.getElementById('login-pin').value = '';
                document.getElementById('login-pin').focus();
                
                // If cooldown triggered, refresh the modal
                if (data.attempts_remaining === 0) {
                    setTimeout(() => this.init(), 1000);
                }
            }
        } catch (error) {
            console.error('Verify PIN error:', error);
            errorDiv.textContent = 'Failed to verify PIN. Please try again.';
        }
    }
    
    async resetPIN() {
        const newPin = document.getElementById('reset-new-pin').value;
        const confirmPin = document.getElementById('reset-confirm-pin').value;
        const errorDiv = document.getElementById('reset-error');
        
        errorDiv.textContent = '';
        
        // Validation
        if (!newPin || !confirmPin) {
            errorDiv.textContent = 'Please enter PIN in both fields';
            return;
        }
        
        if (newPin.length !== 4) {
            errorDiv.textContent = 'PIN must be exactly 4 digits';
            return;
        }
        
        if (!/^\d+$/.test(newPin)) {
            errorDiv.textContent = 'PIN must contain only numbers';
            return;
        }
        
        if (newPin !== confirmPin) {
            errorDiv.textContent = 'PINs do not match';
            return;
        }
        
        try {
            const response = await fetch('/api/pin/reset', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    new_pin: newPin,
                    confirm_pin: confirmPin
                })
            });
            
            const data = await response.json();
            
            if (response.ok && data.success) {
                this.isAuthenticated = true;
                this.sessionToken = data.session_token;
                this.hideAllAuthScreens();
                this.showSuccess('PIN reset successfully!');
                
                // Let the main app initialization pipeline handle the loader
                setTimeout(() => {
                    if (typeof Auth !== 'undefined' && typeof Auth.loadAppData === 'function') {
                        Auth.loadAppData();
                    }
                }, 300);
            } else {
                errorDiv.textContent = data.error || 'Failed to reset PIN';
            }
        } catch (error) {
            console.error('Reset PIN error:', error);
            errorDiv.textContent = 'Failed to reset PIN. Please try again.';
        }
    }
    
    async logout() {
        try {
            await fetch('/api/pin/logout', { method: 'POST' });
            this.isAuthenticated = false;
            this.sessionToken = null;
            window.location.reload();
        } catch (error) {
            console.error('Logout error:', error);
        }
    }
    
    togglePINVisibility(inputId) {
        const input = document.getElementById(inputId);
        const button = input.parentElement.querySelector('.pin-toggle i');
        
        if (input.type === 'password') {
            input.type = 'text';
            button.classList.remove('fa-eye');
            button.classList.add('fa-eye-slash');
        } else {
            input.type = 'password';
            button.classList.remove('fa-eye-slash');
            button.classList.add('fa-eye');
        }
    }
    
    startCooldownCountdown(seconds) {
        const updateCountdown = () => {
            if (seconds <= 0) {
                // Cooldown expired, refresh
                this.init();
                return;
            }
            
            const minutes = Math.floor(seconds / 60);
            const secs = seconds % 60;
            const cooldownDiv = document.querySelector('.pin-cooldown-warning');
            if (cooldownDiv) {
                cooldownDiv.innerHTML = `
                    <i class="fas fa-clock"></i>
                    Too many failed attempts. Try again in ${minutes}m ${secs}s
                `;
            }
            
            seconds--;
            setTimeout(updateCountdown, 1000);
        };
        
        updateCountdown();
    }
    
    hideAllAuthScreens() {
        const modals = document.querySelectorAll('.pin-auth-modal');
        modals.forEach(modal => modal.remove());
        document.body.classList.remove('auth-required');
    }
    
    showSuccess(message) {
        // Use existing notification system if available
        if (typeof showNotification === 'function') {
            showNotification(message, 'success');
        } else {
            console.log('Success:', message);
        }
    }
    
    showError(message) {
        // Use existing notification system if available
        if (typeof showNotification === 'function') {
            showNotification(message, 'error');
        } else {
            console.error('Error:', message);
        }
    }
}

// Create global instance
const PINAuthInstance = new PINAuth();

// Export for use in other modules
window.PINAuth = PINAuth;
window.PINAuthInstance = PINAuthInstance;

// Compatibility function for old auth system
window.showAuthModal = function(mode) {
    // Redirect to PIN authentication
    if (mode === 'login') {
        PINAuthInstance.init();
    } else if (mode === 'setup') {
        PINAuthInstance.showPINSetup();
    }
};

