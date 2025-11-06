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
