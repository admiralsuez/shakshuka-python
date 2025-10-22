/**
 * UI Module - Handles UI components, modals, notifications, and loading screens
 */

const UI = (function() {
    'use strict';
    
    // ==================== Loading Screen ====================
    
    function showLoadingScreen() {
        const loadingScreen = document.getElementById('loading-screen');
        const appContainer = document.getElementById('app-container');
        
        if (loadingScreen && appContainer) {
            loadingScreen.style.display = 'flex';
            appContainer.style.display = 'none';
        }
    }
    
    function hideLoadingScreen() {
        const loadingScreen = document.getElementById('loading-screen');
        const appContainer = document.getElementById('app-container');
        
        if (loadingScreen && appContainer) {
            // Add fade-out class
            loadingScreen.classList.add('fade-out');
            
            // Show app container
            appContainer.style.display = 'block';
            
            // Remove loading screen after fade animation
            setTimeout(() => {
                loadingScreen.style.display = 'none';
            }, 500);
        }
    }
    
    // ==================== Notifications ====================
    
    function showNotification(message, type = 'info', duration = 3000) {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        
        // Add to body
        document.body.appendChild(notification);
        
        // Trigger animation
        setTimeout(() => notification.classList.add('show'), 10);
        
        // Remove after duration
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        }, duration);
    }
    
    function showSuccess(message, duration) {
        showNotification(message, 'success', duration);
    }
    
    function showError(message, duration) {
        showNotification(message, 'error', duration);
    }
    
    function showWarning(message, duration) {
        showNotification(message, 'warning', duration);
    }
    
    function showInfo(message, duration) {
        showNotification(message, 'info', duration);
    }
    
    // ==================== Modals ====================
    
    function showModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('active');
        }
    }
    
    function hideModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('active');
        }
    }
    
    function closeAllModals() {
        const modals = document.querySelectorAll('.modal.active');
        modals.forEach(modal => modal.classList.remove('active'));
    }
    
    // ==================== Add Task Options Modal ====================
    
    function showAddTaskOptions() {
        const existingModal = document.getElementById('add-task-options-modal');
        if (existingModal) {
            existingModal.classList.add('active');
            return;
        }

        const modal = document.createElement('div');
        modal.id = 'add-task-options-modal';
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h2>How would you like to add a task?</h2>
                    <span class="close" onclick="UI.closeAddTaskOptions()">&times;</span>
                </div>
                <div class="add-task-options">
                    <button class="add-task-option" onclick="Tasks.openQuickAddModal(); UI.closeAddTaskOptions();">
                        <i class="fas fa-bolt"></i>
                        <div>
                            <h3>Quick Add</h3>
                            <p>Add a simple task with just a title</p>
                        </div>
                    </button>
                    <button class="add-task-option" onclick="Tasks.openTaskModal(); UI.closeAddTaskOptions();">
                        <i class="fas fa-edit"></i>
                        <div>
                            <h3>Full Form</h3>
                            <p>Add a detailed task with description, priority, and project</p>
                        </div>
                    </button>
                    <button class="add-task-option" onclick="Tasks.openScheduleModal(); UI.closeAddTaskOptions();">
                        <i class="fas fa-calendar-plus"></i>
                        <div>
                            <h3>Schedule Task</h3>
                            <p>Add a task directly to your daily planner</p>
                        </div>
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        modal.classList.add('active');
    }
    
    function closeAddTaskOptions() {
        const modal = document.getElementById('add-task-options-modal');
        if (modal) {
            modal.classList.remove('active');
        }
    }
    
    // ==================== Sidebar ====================
    
    function toggleSidebar() {
        const sidebar = document.querySelector('.sidebar');
        if (sidebar) {
            sidebar.classList.toggle('collapsed');
            
            // Save preference
            const isCollapsed = sidebar.classList.contains('collapsed');
            localStorage.setItem('sidebarCollapsed', isCollapsed);
        }
    }
    
    function initializeSidebar() {
        // Restore sidebar state
        const isCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
        const sidebar = document.querySelector('.sidebar');
        if (sidebar && isCollapsed) {
            sidebar.classList.add('collapsed');
        }
    }
    
    // ==================== Safe Event Listeners ====================
    
    function addSafeEventListener(elementId, event, handler) {
        const element = document.getElementById(elementId);
        if (element) {
            element.addEventListener(event, handler);
        } else {
            console.warn(`Element with ID '${elementId}' not found, skipping event listener`);
        }
    }
    
    // ==================== Public API ====================
    
    return {
        // Loading screen
        showLoadingScreen,
        hideLoadingScreen,
        
        // Notifications
        showNotification,
        showSuccess,
        showError,
        showWarning,
        showInfo,
        
        // Modals
        showModal,
        hideModal,
        closeAllModals,
        showAddTaskOptions,
        closeAddTaskOptions,
        
        // Sidebar
        toggleSidebar,
        initializeSidebar,
        
        // Utilities
        addSafeEventListener
    };
})();

// Expose to global scope for HTML onclick handlers
window.UI = UI;
window.showAddTaskOptions = UI.showAddTaskOptions;
window.closeAddTaskOptions = UI.closeAddTaskOptions;

