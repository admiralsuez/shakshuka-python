// Layout Functions
function setLayout(layout) {
    AppState.set('currentLayout', layout);
    
    // Update active button
    document.querySelectorAll('.layout-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-layout="${layout}"]`).classList.add('active');
    
    // Re-render tasks with new layout
    if (AppState.get('currentPage') === 'tasks') {
        renderTasks();
    }
}

// Sidebar Functions
function toggleSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const mainContent = document.querySelector('.main-content');
    const sidebarToggle = document.querySelector('#sidebar-toggle');

    sidebar.classList.toggle('open');
    
    // Toggle active state for visual feedback
    if (sidebarToggle) {
        sidebarToggle.classList.toggle('active');
    }

    // On mobile, toggle sidebar visibility
    if (window.innerWidth <= 768) {
        if (sidebar.style.transform === 'translateX(0px)' || !sidebar.style.transform) {
            sidebar.style.transform = 'translateX(-100%)';
        } else {
            sidebar.style.transform = 'translateX(0px)';
        }
    }
}

// Kill App Function
function killApp() {
    // Show confirmation dialog
    const confirmed = confirm(
        'Are you sure you want to stop the Shakshuka server?\n\n' +
        'This will:\n' +
        '• Close the web application\n' +
        '• Stop the server process\n' +
        '• You will need to restart manually\n\n' +
        'Click OK to continue or Cancel to abort.'
    );
    
    if (!confirmed) {
        return;
    }
    
    // Show loading state
    const killBtn = document.querySelector('#kill-app-btn');
    if (killBtn) {
        const originalHTML = killBtn.innerHTML;
        killBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i><span>Stopping...</span>';
        killBtn.style.pointerEvents = 'none';
        
        // Try to call the backend shutdown endpoint
        fetch('/api/shutdown', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => {
            if (response.ok) {
                // Show success message briefly
                killBtn.innerHTML = '<i class="fas fa-check"></i><span>Stopped!</span>';
                killBtn.style.color = '#28a745';
                
                // Close the browser tab/window after a short delay
                setTimeout(() => {
                    window.close();
                }, 1500);
            } else {
                throw new Error('Failed to stop server');
            }
        })
        .catch(error => {
            console.error('Error stopping server:', error);
            
            // Fallback: try to run Stop-Shakshuka.bat via a different method
            killBtn.innerHTML = '<i class="fas fa-exclamation-triangle"></i><span>Fallback...</span>';
            
            // Try to trigger the stop script
            try {
                // Create a hidden iframe to trigger the stop script
                const iframe = document.createElement('iframe');
                iframe.style.display = 'none';
                iframe.src = 'data:text/html,<script>window.parent.postMessage("stop-server", "*");</script>';
                document.body.appendChild(iframe);
                
                // Listen for the message
                window.addEventListener('message', function(event) {
                    if (event.data === 'stop-server') {
                        // Show final message and close
                        killBtn.innerHTML = '<i class="fas fa-power-off"></i><span>Server Stopped</span>';
                        setTimeout(() => {
                            window.close();
                        }, 1000);
                    }
                });
                
                // Clean up iframe after a delay
                setTimeout(() => {
                    if (iframe.parentNode) {
                        iframe.parentNode.removeChild(iframe);
                    }
                }, 2000);
                
            } catch (fallbackError) {
                console.error('Fallback method failed:', fallbackError);
                
                // Final fallback: just show message and let user close manually
                killBtn.innerHTML = '<i class="fas fa-info-circle"></i><span>Close Browser</span>';
                killBtn.style.color = '#ffc107';
                
                alert(
                    'Unable to automatically stop the server.\n\n' +
                    'Please:\n' +
                    '1. Close this browser tab/window\n' +
                    '2. Run "Stop-Shakshuka.bat" manually\n' +
                    '3. Or use Ctrl+C in the command window'
                );
            }
            
            // Restore button after error
            setTimeout(() => {
                killBtn.innerHTML = originalHTML;
                killBtn.style.pointerEvents = 'auto';
                killBtn.style.color = '';
            }, 3000);
        });
    }
}

// Keyboard Shortcuts
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', function(e) {
        // N key for new task (only when not typing in input fields)
        if ((e.key === 'n' || e.key === 'N') && !isTypingInInput(e.target)) {
            e.preventDefault();
            openTaskModal();
        }
        
        // Enter to save task, Ctrl+Enter for new line
        if (e.target.id === 'task-title' || e.target.id === 'task-description') {
            if (e.key === 'Enter' && !e.ctrlKey) {
                e.preventDefault();
                saveTask();
            }
        }
    });
}

function isTypingInInput(target) {
    // Check if the target is an input field, textarea, or contenteditable
    const inputTypes = ['input', 'textarea', 'select'];
    const isInput = inputTypes.includes(target.tagName.toLowerCase());
    const isContentEditable = target.contentEditable === 'true';
    const isInModal = target.closest('.modal') !== null;
    
    return isInput || isContentEditable || isInModal;
}
