// Account management
async function deleteAccount() {
    if (!confirm('Are you sure you want to delete your account? This will remove all your data permanently.')) {
        return;
    }

    try {
        const response = await Utils.makeAuthenticatedRequest('/api/account/delete', {
            method: 'POST'
        });

        if (response.ok) {
            Utils.safeShowNotification('Account deleted successfully!', 'success');
            // Redirect or reload as needed
        } else {
            Utils.safeShowNotification('Failed to delete account', 'error');
        }
    } catch (error) {
        Utils.Logger.error('Failed to delete account:', error);
        Utils.safeShowNotification('Failed to delete account', 'error');
    }
}

// Load account settings
async function loadAccountSettings() {
    try {
        const response = await Utils.makeAuthenticatedRequest('/api/account');
        
        // Account endpoint doesn't exist yet - gracefully handle
        if (!response.ok) {
            console.log('Account endpoint not available (expected)');
            return;
        }
        
        const account = await response.json();

        // Update UI elements
        if (account.username) {
            document.getElementById('account-username').textContent = account.username;
        }
        if (account.created_at) {
            document.getElementById('account-created').textContent = Utils.formatDate(account.created_at);
        }
        if (account.last_login) {
            document.getElementById('account-last-login').textContent = Utils.formatDate(account.last_login);
        }
    } catch (error) {
        // Account endpoint not implemented yet - suppress error
        console.log('Account settings not available (endpoint not implemented)');
    }
}
