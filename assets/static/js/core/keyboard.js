/**
 * Keyboard Shortcuts Module
 * Handles all keyboard shortcuts and input detection
 */

const Keyboard = (function() {
    'use strict';

    // Check if user is typing in an input field
    function isTypingInInput(target) {
        const inputTypes = ['input', 'textarea', 'select'];
        const isInput = inputTypes.includes(target.tagName.toLowerCase());
        const isContentEditable = target.contentEditable === 'true';
        return isInput || isContentEditable;
    }

    // Setup keyboard shortcuts
    function setupKeyboardShortcuts() {
        document.addEventListener('keydown', function(e) {
            const isTyping = isTypingInInput(e.target);
            
            // Escape - Close modals (highest priority)
            if (e.key === 'Escape') {
                e.preventDefault();
                e.stopPropagation();
                
                // Close any open modals
                if (typeof Tasks !== 'undefined') {
                    if (Tasks.closeTaskModal) Tasks.closeTaskModal();
                    if (Tasks.closeQuickAddModal) Tasks.closeQuickAddModal();
                    if (Tasks.closeStrikeModal) Tasks.closeStrikeModal();
                    if (Tasks.closeScheduleModal) Tasks.closeScheduleModal();
                }
                if (typeof closePasswordModal !== 'undefined') closePasswordModal();
                if (typeof closeBackupModal !== 'undefined') closeBackupModal();
                if (typeof closeUpdateModal !== 'undefined') closeUpdateModal();
                if (typeof closeLogsModal !== 'undefined') closeLogsModal();
                if (typeof closeChangelogModal !== 'undefined') closeChangelogModal();
                if (typeof closeAddTaskOptions !== 'undefined') closeAddTaskOptions();
                return;
            }
            
// N or n - focus inline quick add on Tasks page (or open modal)
            if ((!e.ctrlKey && !e.metaKey && !e.altKey) && ((e.key && e.key.toLowerCase() === 'n') || e.code === 'KeyN')) {
                if (isTyping) return; // do not trigger while typing in inputs
                e.preventDefault();
                const quick = document.getElementById('inline-quick-add');
                if (quick && typeof AppState !== 'undefined' && AppState.get && AppState.get('currentPage') === 'tasks') {
                    quick.focus();
                    try { quick.select(); } catch (err) {}
                } else if (typeof Tasks !== 'undefined' && Tasks.openQuickAddModal) {
                    Tasks.openQuickAddModal();
                }
            }
            
            // Ctrl/Cmd + N - Quick add task
            if ((e.ctrlKey || e.metaKey) && (e.key === 'n' || e.key === 'N')) {
                e.preventDefault();
                if (typeof Tasks !== 'undefined' && Tasks.openQuickAddModal) {
                    Tasks.openQuickAddModal();
                }
            }

            // Ctrl/Cmd + S - Save current task
            if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                e.preventDefault();
                const editingTaskId = AppState.get('editingTaskId');
                if (editingTaskId && typeof Tasks !== 'undefined' && Tasks.saveTask) {
                    Tasks.saveTask();
                }
            }
        });
        
        Utils.Logger.info('Keyboard shortcuts initialized');
    }

    // Public API
    return {
        setup: setupKeyboardShortcuts,
        isTypingInInput
    };
})();

// Keyboard Shortcuts Modal
function showKeyboardShortcutsModal() {
    const shortcuts = [
        { key: 'N', description: 'Focus quick add input / New task' },
        { key: 'Ctrl + N', description: 'Open quick add modal' },
        { key: 'Ctrl + S', description: 'Save current task' },
        { key: 'Ctrl + F', description: 'Search tasks (on Tasks page)' },
        { key: 'Escape', description: 'Close any open modal' },
        { key: '1', description: 'Go to Tasks page' },
        { key: '2', description: 'Go to Analytics page' },
        { key: '3', description: 'Go to Planner page' },
        { key: '4', description: 'Go to Notes page' },
        { key: '5', description: 'Go to Settings page' },
    ];
    
    const shortcutRows = shortcuts.map(s => `
        <div class="shortcut-row">
            <kbd class="shortcut-key">${s.key}</kbd>
            <span class="shortcut-description">${s.description}</span>
        </div>
    `).join('');
    
    const modalHtml = `
        <div class="modal active" id="keyboard-shortcuts-modal" style="display:flex; position:fixed; top:0; left:0; right:0; bottom:0; z-index:9999; background:rgba(0,0,0,0.5); align-items:center; justify-content:center;" onclick="closeKeyboardShortcutsModal(event)">
            <div class="modal-content shortcuts-modal" style="position:relative; background:var(--surface-color); border-radius:16px; max-width:500px; width:90%; max-height:80vh; overflow:auto;" onclick="event.stopPropagation()">
                <div class="modal-header">
                    <h2><i class="fas fa-keyboard"></i> Keyboard Shortcuts</h2>
                    <button class="modal-close" onclick="closeKeyboardShortcutsModal()">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="shortcuts-list">
                        ${shortcutRows}
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn-primary" onclick="closeKeyboardShortcutsModal()">Got it!</button>
                </div>
            </div>
        </div>
    `;
    
    // Add modal to body
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    // Add styles if not already present
    if (!document.getElementById('shortcuts-modal-styles')) {
        const styles = document.createElement('style');
        styles.id = 'shortcuts-modal-styles';
        styles.textContent = `
            .shortcuts-modal {
                max-width: 500px;
                width: 90%;
            }
            .shortcuts-list {
                display: flex;
                flex-direction: column;
                gap: 12px;
            }
            .shortcut-row {
                display: flex;
                align-items: center;
                gap: 16px;
                padding: 8px 0;
                border-bottom: 1px solid var(--border-color);
            }
            .shortcut-row:last-child {
                border-bottom: none;
            }
            .shortcut-key {
                display: inline-block;
                min-width: 100px;
                padding: 6px 12px;
                background: var(--surface-color);
                border: 1px solid var(--border-color);
                border-radius: 6px;
                font-family: monospace;
                font-size: 0.9rem;
                font-weight: 600;
                text-align: center;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .shortcut-description {
                color: var(--text-color);
                font-size: 0.95rem;
            }
        `;
        document.head.appendChild(styles);
    }
}

function closeKeyboardShortcutsModal(event) {
    if (event && event.target !== event.currentTarget) return;
    const modal = document.getElementById('keyboard-shortcuts-modal');
    if (modal) modal.remove();
}

// Make functions globally available
window.showKeyboardShortcutsModal = showKeyboardShortcutsModal;
window.closeKeyboardShortcutsModal = closeKeyboardShortcutsModal;
