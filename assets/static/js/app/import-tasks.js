// Import Tasks Functions
function openImportModal() {
    const modal = document.getElementById('import-modal');
    modal.classList.add('active');
    
    // Reset form
    document.getElementById('import-form').reset();
    document.getElementById('import-preview').style.display = 'none';
    document.getElementById('preview-content').innerHTML = '';
}

function closeImportModal() {
    const modal = document.getElementById('import-modal');
    modal.classList.remove('active');
}

function previewImportFile() {
    const fileInput = document.getElementById('import-file');
    const file = fileInput.files[0];
    
    if (!file) {
        document.getElementById('import-preview').style.display = 'none';
        return;
    }
    
    const reader = new FileReader();
    reader.onload = function(e) {
        const content = e.target.result;
        const preview = document.getElementById('preview-content');
        
        try {
            let previewHtml = '';
            const fileExtension = file.name.toLowerCase().split('.').pop();
            
            if (fileExtension === 'csv') {
                previewHtml = parseCSVPreview(content);
            } else if (fileExtension === 'txt') {
                previewHtml = parseTXTPreview(content);
            } else {
                previewHtml = '<p style="color: red;">Unsupported file format</p>';
            }
            
            preview.innerHTML = previewHtml;
            document.getElementById('import-preview').style.display = 'block';
        } catch (error) {
            preview.innerHTML = `<p style="color: red;">Error parsing file: ${error.message}</p>`;
            document.getElementById('import-preview').style.display = 'block';
        }
    };
    
    reader.readAsText(file);
}

function parseCSVPreview(content) {
    const lines = content.split('\n');
    const header = lines[0].split(',').map(h => h.trim());
    
    let html = '<div class="preview-table">';
    html += '<table style="width: 100%; border-collapse: collapse;">';
    html += '<thead><tr>';
    header.forEach(h => {
        html += `<th style="border: 1px solid #ddd; padding: 8px; background: #f5f5f5;">${h}</th>`;
    });
    html += '</tr></thead><tbody>';
    
    // Show first 5 rows
    for (let i = 1; i < Math.min(6, lines.length); i++) {
        if (lines[i].trim()) {
            const row = lines[i].split(',').map(c => c.trim());
            html += '<tr>';
            row.forEach(cell => {
                html += `<td style="border: 1px solid #ddd; padding: 8px;">${cell}</td>`;
            });
            html += '</tr>';
        }
    }
    
    html += '</tbody></table>';
    html += `<p><em>Showing first ${Math.min(5, lines.length - 1)} rows of ${lines.length - 1} total rows</em></p>`;
    html += '</div>';
    
    return html;
}

function parseTXTPreview(content) {
    const lines = content.split('\n').filter(line => line.trim() && !line.trim().startsWith('#'));
    
    let html = '<div class="preview-list">';
    html += '<ul>';
    
    // Show first 5 lines
    for (let i = 0; i < Math.min(5, lines.length); i++) {
        const parts = lines[i].split('|').map(p => p.trim());
        html += `<li><strong>${parts[0]}</strong>`;
        if (parts[1]) html += ` - ${parts[1]}`;
        if (parts[2]) html += ` (${parts[2]})`;
        html += '</li>';
    }
    
    html += '</ul>';
    html += `<p><em>Showing first ${Math.min(5, lines.length)} tasks of ${lines.length} total tasks</em></p>`;
    html += '</div>';
    
    return html;
}

async function confirmImport() {
    const fileInput = document.getElementById('import-file');
    const file = fileInput.files[0];
    const overwrite = document.getElementById('import-overwrite').checked;
    
    if (!file) {
        showNotification('Please select a file to import', 'error');
        return;
    }
    
    try {
        showLoading(true);
        
        const formData = new FormData();
        formData.append('file', file);
        formData.append('overwrite', overwrite);
        
        const response = await fetch('/api/tasks/import', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showNotification(result.message, 'success');
            
            // Reload tasks
            await loadTasks();
            
            // Show errors if any
            if (result.errors && result.errors.length > 0) {
                console.warn('Import warnings:', result.errors);
                showNotification(`${result.errors.length} warnings during import`, 'warning');
            }
            
            closeImportModal();
        } else {
            showNotification(result.error || 'Import failed', 'error');
        }
    } catch (error) {
        console.error('Import error:', error);
        showNotification('Import failed: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }
}

function downloadSampleCSV() {
    const sampleData = [
        ['title', 'description', 'project', 'duration', 'due_date', 'priority'],
        ['Complete project proposal', 'Write and submit the quarterly project proposal', 'Work', '120', '2024-01-15', 'high'],
        ['Buy groceries', 'Get milk, bread, eggs, and vegetables', 'Personal', '30', '2024-01-10', 'medium'],
        ['Review code changes', 'Review pull request #123 for the new feature', 'Work', '60', '2024-01-12', 'high'],
        ['Call dentist', 'Schedule annual dental checkup', 'Health', '15', '2024-01-20', 'low'],
        ['Update documentation', 'Update API documentation for new endpoints', 'Work', '90', '2024-01-18', 'medium']
    ];
    
    const csvContent = sampleData.map(row => row.join(',')).join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'sample_tasks.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
    
    showNotification('Sample CSV template downloaded!', 'success');
}
