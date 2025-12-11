// Notes page module: simple Notepad++-style notes with tabs, autosave, optional split view
(function () {
'use strict';

    const STORAGE_KEY = 'shakshuka_notes_v1';
    const SAVED_NOTIFICATION_DELAY = 10000; // ms after typing stops

    let notes = [];
    let activeNoteId = null;
    let splitViewEnabled = false;
    let secondaryNoteId = null; // when split view is on, which note is shown in the secondary editor
    let openNoteIds = [];
    let savedNotificationTimer = null;
    let lastFocusedEditor = 'primary'; // 'primary' | 'secondary'
    let commandMenuEl = null;
    let commandMenuEditor = null;
    let selectedNoteIds = new Set(); // for bulk actions in View Notes modal

    // Context menu for note tabs (right-click)
    let tabContextMenuEl = null;
    let tabContextNoteId = null;

    function debugLog(...args) {
        if (window.Utils && typeof Utils.debugLog === 'function') {
            Utils.debugLog('[Notes]', ...args);
        }
    }

    function isEphemeralNote(note) {
        if (!note) return false;
        const title = (note.title || '').trim();
        const content = (note.content || '').trim();
        // Local-only ID pattern from createNoteObject
        const isLocalId = typeof note.id === 'string' && note.id.startsWith('note-');
        const isDefaultTitle = /^Note \d+$/.test(title);
        return isLocalId && isDefaultTitle && content === '';
    }

    function loadNotesFromLocalStorage() {
        try {
            const raw = window.localStorage.getItem(STORAGE_KEY);
            if (!raw) {
                debugLog('No existing notes in localStorage');
                notes = [createNoteObject('Welcome')];
                activeNoteId = notes[0].id;
                openNoteIds = [activeNoteId];
                return;
            }
            const parsed = JSON.parse(raw);
            if (!parsed || !Array.isArray(parsed.notes) || !parsed.notes.length) {
                notes = [createNoteObject('Welcome')];
                activeNoteId = notes[0].id;
                openNoteIds = [activeNoteId];
                return;
            }
            notes = parsed.notes;
            openNoteIds = Array.isArray(parsed.openNoteIds) && parsed.openNoteIds.length
                ? parsed.openNoteIds.filter(id => notes.some(n => n.id === id))
                : notes.map(n => n.id);
            const candidateActiveId = parsed.activeNoteId;
            if (candidateActiveId && notes.some(n => n.id === candidateActiveId)) {
                activeNoteId = candidateActiveId;
            } else {
                activeNoteId = openNoteIds[0] || (notes[0] && notes[0].id);
            }
            splitViewEnabled = !!parsed.splitViewEnabled;
            // Secondary note ID is optional; fall back to active if missing/invalid.
            if (parsed.secondaryNoteId && notes.some(n => n.id === parsed.secondaryNoteId)) {
                secondaryNoteId = parsed.secondaryNoteId;
            } else {
                secondaryNoteId = null;
            }
            debugLog('Loaded notes from localStorage', { count: notes.length });
        } catch (e) {
            console.error('Failed to load notes from localStorage', e);
            notes = [createNoteObject('Welcome')];
            activeNoteId = notes[0].id;
            openNoteIds = [activeNoteId];
        }
    }

    function saveAllNotesToLocalStorage() {
        try {
            // Do not persist ephemeral, completely empty local notes.
            const persistedNotes = notes.filter(n => !isEphemeralNote(n));

            // Ensure openNoteIds and activeNoteId only reference persisted notes.
            let persistedOpenIds = Array.isArray(openNoteIds)
                ? openNoteIds.filter(id => persistedNotes.some(n => n.id === id))
                : [];

            if (!persistedOpenIds.length && persistedNotes.length) {
                persistedOpenIds = [persistedNotes[0].id];
            }

            let persistedActiveId = activeNoteId;
            if (!persistedNotes.some(n => n.id === persistedActiveId)) {
                persistedActiveId = persistedOpenIds[0] || (persistedNotes[0] && persistedNotes[0].id) || null;
            }

            const payload = {
                notes: persistedNotes,
                activeNoteId: persistedActiveId,
                splitViewEnabled,
                secondaryNoteId,
                openNoteIds: persistedOpenIds
            };
            window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
            debugLog('Saved notes to localStorage', { count: persistedNotes.length });
        } catch (e) {
            console.error('Failed to save notes to localStorage', e);
        }
    }

    // Backward-compatible wrapper used by various helpers in this module.
    // Currently it only updates the localStorage cache because server sync
    // is handled per-note via saveNoteToServer/createNoteOnServer.
    function saveNotes() {
        saveAllNotesToLocalStorage();
    }

    async function loadNotes() {
        try {
            const response = await fetch('/api/notes');
            if (!response.ok) {
                throw new Error('Failed to load notes');
            }
            const serverNotes = await response.json();
            if (!Array.isArray(serverNotes) || !serverNotes.length) {
                debugLog('No notes from server, creating default');
                const welcome = await createNoteOnServer('Welcome', '');
                notes = welcome ? [welcome] : [createNoteObject('Welcome')];
            } else {
                notes = serverNotes;
            }
            activeNoteId = notes[0].id;
            openNoteIds = [activeNoteId];
            splitViewEnabled = false;
            secondaryNoteId = null;
            debugLog('Loaded notes from server', { count: notes.length });
            saveAllNotesToLocalStorage();
        } catch (err) {
            console.error('Failed to load notes from server', err);
            // Fallback to localStorage cache so notes are not lost when API is unavailable
            loadNotesFromLocalStorage();
        }
    }

    async function saveNoteToServer(note) {
        if (!note || !note.id) return;
        try {
            const payload = {
                title: note.title,
                content: note.content
            };
            const oldId = note.id;
            const response = await fetch(`/api/notes/${encodeURIComponent(oldId)}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (response.status === 404) {
                // Note does not exist on the server yet (e.g. initial local-only note).
                // Create it and update local IDs so future saves work.
                const created = await createNoteOnServer(note.title, note.content);
                if (created && created.id) {
                    note.id = created.id;
                    note.created_at = created.created_at;
                    note.updated_at = created.updated_at;

                    // Update references in openNoteIds/activeNoteId
                    openNoteIds = openNoteIds.map(id => id === oldId ? note.id : id);
                    if (activeNoteId === oldId) {
                        activeNoteId = note.id;
                    }
                    // Replace in notes array if an entry with the old id still exists
                    const idx = notes.findIndex(n => n.id === oldId);
                    if (idx !== -1) {
                        notes[idx] = note;
                    }
                }
                saveAllNotesToLocalStorage();
                return;
            }

            if (!response.ok) {
                throw new Error('Failed to save note');
            }

            // Successful PUT → keep local cache in sync
            saveAllNotesToLocalStorage();
        } catch (err) {
            console.error('Failed to save note to server', err);
            // Still keep local cache so user doesn't lose work
            saveAllNotesToLocalStorage();
        }
    }

    async function createNoteOnServer(title, content) {
        try {
            const response = await fetch('/api/notes', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title, content })
            });
            if (!response.ok) {
                throw new Error('Failed to create note');
            }
            return await response.json();
        } catch (err) {
            console.error('Failed to create note on server', err);
            return null;
        }
    }

    function scheduleSavedNotification() {
        if (savedNotificationTimer) {
            clearTimeout(savedNotificationTimer);
        }
        savedNotificationTimer = window.setTimeout(() => {
            savedNotificationTimer = null;
            if (window.showNotification) {
                window.showNotification('All changes saved', 'success');
            }
        }, SAVED_NOTIFICATION_DELAY);
    }

    function createNoteObject(title) {
        const id = 'note-' + Date.now() + '-' + Math.floor(Math.random() * 10000);
        const now = new Date().toISOString();
        return {
            id,
            title: title || 'Untitled',
            content: '',
            created_at: now,
            updated_at: now
        };
    }

    function getActiveNote() {
        return notes.find(n => n.id === activeNoteId) || notes[0] || null;
    }

    function setActiveNote(id) {
        if (!id) return;
        // Trust the ID and let getActiveNote() fall back if needed
        activeNoteId = id;
        render();
    }

    function ensureSecondaryEditorVisibility() {
        const editorsContainer = document.getElementById('notes-editors');
        const secondary = document.getElementById('notes-editor-secondary');
        if (!editorsContainer || !secondary) return;
        if (splitViewEnabled) {
            editorsContainer.classList.add('notes-editors--split');
            secondary.classList.add('notes-editor--visible');
        } else {
            editorsContainer.classList.remove('notes-editors--split');
            secondary.classList.remove('notes-editor--visible');
        }
    }

    function renderTabs() {
        const container = document.getElementById('notes-tabs');
        if (!container) return;
        container.innerHTML = '';

        // Derive open notes from openNoteIds; fallback to all notes if needed
        let openNotes = Array.isArray(openNoteIds) && openNoteIds.length
            ? openNoteIds.map(id => notes.find(n => n.id === id)).filter(Boolean)
            : notes.slice();

        if (!openNotes.length && notes.length) {
            // Ensure at least one open tab when there are notes
            openNoteIds = [notes[0].id];
            openNotes = [notes[0]];
            if (!activeNoteId) {
                activeNoteId = notes[0].id;
            }
            saveNotes();
        }

        openNotes.forEach(note => {
            const isActive = note.id === activeNoteId;
            const btn = document.createElement('button');
            btn.className = 'notes-tab filter-tab' + (isActive ? ' active' : '');
            btn.type = 'button';
            btn.dataset.noteId = note.id;

            const titleSpan = document.createElement('span');
            titleSpan.className = 'notes-tab-title';
            titleSpan.textContent = note.title || 'Untitled';
            btn.appendChild(titleSpan);

            // Allow renaming via double-click on the title text
            titleSpan.addEventListener('dblclick', function (ev) {
                ev.stopPropagation();
                renameActiveNote(note.id);
            });

            // Closable tabs: show "x" button, but prevent closing when only one note remains
            const closeBtn = document.createElement('button');
            closeBtn.type = 'button';
            closeBtn.className = 'notes-tab-close';
            closeBtn.innerHTML = '&times;';
            closeBtn.title = 'Close note';
            closeBtn.addEventListener('click', function (ev) {
                ev.stopPropagation();
                closeNote(note.id);
            });
            btn.appendChild(closeBtn);

            btn.addEventListener('click', function () {
                setActiveNote(note.id);
            });

            // Right-click context menu for tab actions
            btn.addEventListener('contextmenu', function (e) {
                e.preventDefault();
                openTabContextMenu(note.id, e.clientX, e.clientY);
            });

            // Fallback: double-click anywhere on the tab also triggers rename
            btn.addEventListener('dblclick', function (ev) {
                ev.preventDefault();
                ev.stopPropagation();
                renameActiveNote(note.id);
            });

            container.appendChild(btn);
        });
    }

    function renderEditors() {
        const primary = document.getElementById('notes-editor-primary');
        const secondary = document.getElementById('notes-editor-secondary');
        const primaryNote = getActiveNote();
        if (!primary || !secondary || !primaryNote) return;

        // Primary editor always shows the active note.
        primary.value = primaryNote.content || '';

        // Secondary editor can show a different note when split view is enabled.
        let secondaryNote = primaryNote;
        if (splitViewEnabled && secondaryNoteId && secondaryNoteId !== activeNoteId) {
            const candidate = notes.find(n => n.id === secondaryNoteId);
            if (candidate) {
                secondaryNote = candidate;
            }
        }
        secondary.value = secondaryNote.content || '';

        ensureSecondaryEditorVisibility();
    }

    function render() {
        renderTabs();
        renderEditors();
    }

    function createNewNote() {
        const baseIndex = notes.length + 1;
        const title = 'Note ' + baseIndex;
        // Create a local-only note first. It will only be persisted to SQLite
        // once the user actually edits it (content/title), via saveNoteToServer.
        const note = createNoteObject(title);
        notes.unshift(note);
        openNoteIds.push(note.id);
        activeNoteId = note.id;
        saveAllNotesToLocalStorage();
        render();
    }

    function closeNote(id) {
        if (!id) return;
        if (!Array.isArray(openNoteIds)) {
            openNoteIds = notes.map(n => n.id);
        }
        if (openNoteIds.length <= 1) {
            // Never close the last remaining open tab
            if (window.showNotification) {
                window.showNotification('At least one note must remain open', 'warning');
            }
            return;
        }
        const idx = openNoteIds.indexOf(id);
        if (idx === -1) return;
        const wasActive = activeNoteId === id;
        openNoteIds.splice(idx, 1);
        if (wasActive) {
            const nextId = openNoteIds[idx] || openNoteIds[openNoteIds.length - 1] || null;
            activeNoteId = nextId;
        }
        render();
        saveNotes();
    }

    function renameActiveNote(id) {
        const note = notes.find(n => n.id === id);
        if (!note) return;
        const newTitle = window.prompt('Rename note', note.title || '');
        if (newTitle == null) return;
        const trimmed = newTitle.trim();
        if (!trimmed) return;
        note.title = trimmed;
        note.updated_at = new Date().toISOString();
        renderTabs();
        saveNoteToServer(note);
        scheduleSavedNotification();
    }

    function handleEditorInput(editor) {
        if (!editor) return;

        let targetNote;
        // If the secondary editor is focused and split view is on, edit the secondary note.
        if (editor.id === 'notes-editor-secondary' && splitViewEnabled && secondaryNoteId && secondaryNoteId !== activeNoteId) {
            targetNote = notes.find(n => n.id === secondaryNoteId) || getActiveNote();
        } else {
            targetNote = getActiveNote();
        }

        if (!targetNote) return;

        targetNote.content = editor.value;
        targetNote.updated_at = new Date().toISOString();
        saveNoteToServer(targetNote);
        scheduleSavedNotification();
    }

    function toggleSplitView() {
        splitViewEnabled = !splitViewEnabled;
        ensureSecondaryEditorVisibility();
        saveNotes();
    }

    function getFocusedEditor() {
        if (lastFocusedEditor === 'secondary' && splitViewEnabled) {
            return document.getElementById('notes-editor-secondary') || document.getElementById('notes-editor-primary');
        }
        return document.getElementById('notes-editor-primary');
    }

    function handleEditorKeydown(e, editor) {
        // Slash command menu - open inline formatting menu
        if (!e.ctrlKey && !e.metaKey && !e.altKey && e.key === '/') {
            e.preventDefault();
            openCommandMenu(editor);
            return;
        }

        // Auto-detect list prefixes when user types '-' or '1.' then space at start of line
        if (!e.ctrlKey && !e.metaKey && !e.altKey && e.key === ' ') {
            const value = editor.value;
            const start = editor.selectionStart;
            const end = editor.selectionEnd;
            if (start === end) {
                const lineStart = value.lastIndexOf('\n', start - 1) + 1;
                const rawPrefix = value.substring(lineStart, start);

                // "- " or "* " → bullet list
                if (/^[-*]$/.test(rawPrefix)) {
                    e.preventDefault();
                    applyLinePrefix(editor, '- ');
                    return;
                }

                // "1." → numbered list (respect the typed number)
                const numMatch = rawPrefix.match(/^(\d+)\.$/);
                if (numMatch) {
                    e.preventDefault();
                    const prefix = numMatch[1] + '. ';

                    const lineEnd = value.indexOf('\n', start);
                    const endPos = lineEnd === -1 ? value.length : lineEnd;
                    const line = value.substring(lineStart, endPos);
                    const stripped = line.replace(/^([#]+\s|[-*]\s|\d+\.\s|\[ \]\s)/, '');
                    const newLine = prefix + stripped;
                    editor.value = value.substring(0, lineStart) + newLine + value.substring(endPos);
                    const newCursor = lineStart + newLine.length;
                    editor.selectionStart = editor.selectionEnd = newCursor;
                    saveNotes();
                    scheduleSavedNotification();
                    return;
                }
            }
        }

        // Escape should close the command menu when open
        if (e.key === 'Escape' && commandMenuEl) {
            closeCommandMenu();
        }

        // Auto-continue numbered/bullet lists on Enter
        if (e.key === 'Enter') {
            const value = editor.value;
            const start = editor.selectionStart;
            const end = editor.selectionEnd;
            if (start === end) {
                const lineStart = value.lastIndexOf('\n', start - 1) + 1;
                const lineEnd = value.indexOf('\n', start);
                const endPos = lineEnd === -1 ? value.length : lineEnd;
                const line = value.substring(lineStart, endPos);

                // Numbered list continuation
                let match = line.match(/^(\d+)\.\s(.*)$/);
                if (match) {
                    e.preventDefault();
                    const currentNumber = parseInt(match[1], 10);
                    const content = match[2];

                    if (content.trim() === '') {
                        // Empty numbered line: exit list by removing prefix and keeping a blank line
                        const beforeLine = value.substring(0, lineStart);
                        const afterLine = value.substring(endPos);
                        const newValue = beforeLine + '' + afterLine;
                        editor.value = newValue;
                        editor.selectionStart = editor.selectionEnd = lineStart;
                        saveNotes();
                        scheduleSavedNotification();
                        return;
                    } else {
                        // Continue with next number
                        const beforeCaret = value.substring(0, start);
                        const afterCaret = value.substring(start);
                        const nextNumber = currentNumber + 1;
                        const insert = '\n' + nextNumber + '. ';
                        editor.value = beforeCaret + insert + afterCaret;
                        const newPos = start + insert.length;
                        editor.selectionStart = editor.selectionEnd = newPos;
                        saveNotes();
                        scheduleSavedNotification();
                        return;
                    }
                }

                // Bullet list continuation (- or *)
                match = line.match(/^([-*])\s(.*)$/);
                if (match) {
                    e.preventDefault();
                    const bullet = match[1];
                    const content = match[2];

                    if (content.trim() === '') {
                        // Empty bullet line: exit list
                        const beforeLine = value.substring(0, lineStart);
                        const afterLine = value.substring(endPos);
                        const newValue = beforeLine + '' + afterLine;
                        editor.value = newValue;
                        editor.selectionStart = editor.selectionEnd = lineStart;
                        saveNotes();
                        scheduleSavedNotification();
                        return;
                    } else {
                        // Continue bullet on next line
                        const beforeCaret = value.substring(0, start);
                        const afterCaret = value.substring(start);
                        const insert = '\n' + bullet + ' ';
                        editor.value = beforeCaret + insert + afterCaret;
                        const newPos = start + insert.length;
                        editor.selectionStart = editor.selectionEnd = newPos;
                        saveNotes();
                        scheduleSavedNotification();
                        return;
                    }
                }
            }
        }

        // Tab indentation
        if (e.key === 'Tab') {
            e.preventDefault();
            const value = editor.value;
            const start = editor.selectionStart;
            const end = editor.selectionEnd;

            const before = value.substring(0, start);
            const selection = value.substring(start, end);
            const after = value.substring(end);

            if (e.shiftKey) {
                // Outdent: remove leading 4 spaces or a tab on each selected line
                const lineStart = value.lastIndexOf('\n', start - 1) + 1;
                const lineEnd = end;
                const block = value.substring(lineStart, lineEnd);
                const outdented = block.replace(/^( {1,4}|\t)/gm, '');
                const delta = block.length - outdented.length;
                editor.value = value.substring(0, lineStart) + outdented + value.substring(lineEnd);
                const newStart = Math.max(start - delta, lineStart);
                const newEnd = end - delta;
                editor.selectionStart = newStart;
                editor.selectionEnd = newEnd;
            } else {
                if (selection && selection.indexOf('\n') !== -1) {
                    // Multi-line indent
                    const lineStart = value.lastIndexOf('\n', start - 1) + 1;
                    const lineEnd = end;
                    const block = value.substring(lineStart, lineEnd);
                    const indented = block.replace(/^/gm, '    ');
                    editor.value = value.substring(0, lineStart) + indented + value.substring(lineEnd);
                    const added = indented.length - block.length;
                    editor.selectionStart = start + 4;
                    editor.selectionEnd = end + added;
                } else {
                    // Single insertion of 4 spaces
                    editor.value = before + '    ' + selection + after;
                    const cursor = start + 4;
                    editor.selectionStart = cursor;
                    editor.selectionEnd = cursor;
                }
            }
        }
    }

    function applyLinePrefix(editor, prefix) {
        const value = editor.value;
        const pos = editor.selectionStart;
        const lineStart = value.lastIndexOf('\n', pos - 1) + 1;
        const lineEnd = value.indexOf('\n', pos);
        const endPos = lineEnd === -1 ? value.length : lineEnd;
        const line = value.substring(lineStart, endPos);

        const stripped = line.replace(/^([#]+\s|[-*]\s|\d+\.\s|\[ \]\s)/, '');
        const newLine = prefix + stripped;
        editor.value = value.substring(0, lineStart) + newLine + value.substring(endPos);
        const newCursor = lineStart + newLine.length;
        editor.selectionStart = editor.selectionEnd = newCursor;
        saveNotes();
        scheduleSavedNotification();
    }

    // Inline formatting helpers removed for now (bold/underline not used)
    function applyInlineWrap(editor, marker) {
        const value = editor.value;
        let start = editor.selectionStart;
        let end = editor.selectionEnd;

        if (start === end) {
            // No selection: insert marker pair and place caret between
            const before = value.slice(0, start);
            const after = value.slice(end);
            const insertion = marker + marker;
            editor.value = before + insertion + after;
            const caret = start + marker.length;
            editor.selectionStart = editor.selectionEnd = caret;
            saveNotes();
            scheduleSavedNotification();
            return;
        }

        const selected = value.slice(start, end);
        const before = value.slice(0, start);
        const after = value.slice(end);

        const full = value.slice(start - marker.length, end + marker.length);
        const wrapped = marker + selected + marker;

        if (full === wrapped) {
            // Toggle off formatting
            editor.value = before.slice(0, -marker.length) + selected + after.slice(marker.length);
            const caretStart = start - marker.length;
            const caretEnd = end - marker.length;
            editor.selectionStart = caretStart;
            editor.selectionEnd = caretEnd;
        } else {
            // Apply formatting
            editor.value = before + wrapped + after;
            const caretStart = start + marker.length;
            const caretEnd = end + marker.length;
            editor.selectionStart = caretStart;
            editor.selectionEnd = caretEnd;
        }

        saveNotes();
        scheduleSavedNotification();
    }

    function clearFormatting(editor) {
        const value = editor.value;
        const pos = editor.selectionStart;
        const lineStart = value.lastIndexOf('\n', pos - 1) + 1;
        const lineEnd = value.indexOf('\n', pos);
        const endPos = lineEnd === -1 ? value.length : lineEnd;
        const line = value.substring(lineStart, endPos);

        // Remove list / header prefixes
        const noPrefix = line.replace(/^([#]+\s|[-*]\s|\d+\.\s|\[ \]\s)/, '');
        // For now, we only care about prefixes; inline markers are left as-is
        const cleanedLine = noPrefix;

        editor.value = value.substring(0, lineStart) + cleanedLine + value.substring(endPos);
        const newCursor = lineStart + cleanedLine.length;
        editor.selectionStart = editor.selectionEnd = newCursor;
        saveNotes();
        scheduleSavedNotification();
    }

    function applyCommand(editor, type) {
        switch (type) {
            case 'bullet':
                applyLinePrefix(editor, '- ');
                break;
            case 'numbered':
                applyLinePrefix(editor, '1. ');
                break;
            case 'header':
                applyLinePrefix(editor, '# ');
                break;
            case 'clear':
                clearFormatting(editor);
                break;
            default:
                break;
        }
    }

    function ensureCommandMenu() {
        if (commandMenuEl) return commandMenuEl;
        commandMenuEl = document.createElement('div');
        commandMenuEl.className = 'notes-command-menu';
        commandMenuEl.innerHTML = '';
        document.body.appendChild(commandMenuEl);
        return commandMenuEl;
    }

    function ensureTabContextMenu() {
        if (tabContextMenuEl) return tabContextMenuEl;
        tabContextMenuEl = document.createElement('div');
        tabContextMenuEl.className = 'notes-tab-context-menu';
        tabContextMenuEl.innerHTML = '';
        document.body.appendChild(tabContextMenuEl);
        return tabContextMenuEl;
    }

    function closeTabContextMenu() {
        if (!tabContextMenuEl) return;
        tabContextMenuEl.style.display = 'none';
        tabContextNoteId = null;
    }

    function openTabContextMenu(noteId, clientX, clientY) {
        tabContextNoteId = noteId;
        const menu = ensureTabContextMenu();
        menu.innerHTML = '';

        const items = [
            { label: 'Open in split view', action: 'split' },
            { label: 'Rename note',        action: 'rename' },
            { label: 'Close note',         action: 'close' },
        ];

        items.forEach(item => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'notes-tab-context-item';
            btn.textContent = item.label;
            btn.dataset.action = item.action;

            btn.addEventListener('click', function () {
                const id = tabContextNoteId;
                if (!id) {
                    closeTabContextMenu();
                    return;
                }
                if (item.action === 'split') {
                    // Ensure this note is in the open tabs list
                    if (!Array.isArray(openNoteIds)) {
                        openNoteIds = [];
                    }
                    if (!openNoteIds.includes(id)) {
                        openNoteIds.push(id);
                    }
                    secondaryNoteId = id;
                    splitViewEnabled = true;
                    if (typeof saveNotes === 'function') {
                        saveNotes();
                    }
                    render();
                } else if (item.action === 'rename') {
                    renameActiveNote(id);
                } else if (item.action === 'close') {
                    closeNote(id);
                }
                closeTabContextMenu();
            });

            menu.appendChild(btn);
        });

        // Position menu near cursor with basic viewport clamping
        menu.style.display = 'flex';
        const menuRect = menu.getBoundingClientRect();
        const padding = 8;
        let left = clientX;
        let top = clientY;

        const maxLeft = window.innerWidth - menuRect.width - padding;
        const maxTop = window.innerHeight - menuRect.height - padding;
        if (left > maxLeft) left = maxLeft;
        if (top > maxTop) top = maxTop;
        if (left < padding) left = padding;
        if (top < padding) top = padding;

        menu.style.left = left + 'px';
        menu.style.top = top + 'px';
    }

    function openCommandMenu(editor) {
        commandMenuEditor = editor;
        const menu = ensureCommandMenu();
        menu.innerHTML = '';

        const options = [
            { label: 'Bullet list',   type: 'bullet' },
            { label: 'Numbered list', type: 'numbered' },
            { label: 'Large header',  type: 'header' },
            { label: 'Clear',         type: 'clear' }
        ];

        const buttons = [];

        options.forEach((opt, index) => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'notes-command-item';
            btn.textContent = opt.label;
            btn.dataset.commandType = opt.type;

            btn.addEventListener('click', function () {
                const editorRef = commandMenuEditor;
                if (editorRef) {
                    applyCommand(editorRef, opt.type);
                }
                closeCommandMenu();
                if (editorRef) {
                    editorRef.focus();
                }
            });

            btn.addEventListener('keydown', function (e) {
                const lastIndex = buttons.length - 1;
                if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    const next = index === lastIndex ? 0 : index + 1;
                    buttons[next].focus();
                } else if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    const prev = index === 0 ? lastIndex : index - 1;
                    buttons[prev].focus();
                } else if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    btn.click();
                } else if (e.key === 'Escape') {
                    e.preventDefault();
                    const editorRef = commandMenuEditor;
                    closeCommandMenu();
                    if (editorRef) {
                        editorRef.focus();
                    }
                }
            });

            buttons.push(btn);
            menu.appendChild(btn);
        });

        // Approximate caret position inside the textarea so the menu appears near the cursor
        const rect = editor.getBoundingClientRect();
        const value = editor.value;
        const pos = editor.selectionStart || 0;
        const before = value.slice(0, pos);
        const lines = before.split('\n');
        const lineIndex = lines.length - 1;
        const colIndex = lines[lines.length - 1].length;

        const style = window.getComputedStyle(editor);
        const fontSize = parseFloat(style.fontSize) || 14;
        const lineHeight = parseFloat(style.lineHeight) || fontSize * 1.4;
        const paddingTop = parseFloat(style.paddingTop) || 0;
        const paddingLeft = parseFloat(style.paddingLeft) || 0;
        const charWidth = fontSize * 0.6; // rough monospace approximation

        const caretX = rect.left + window.scrollX + paddingLeft + colIndex * charWidth - editor.scrollLeft;
        const caretY = rect.top  + window.scrollY + paddingTop + lineIndex * lineHeight - editor.scrollTop;

        menu.style.display = 'flex';
        const menuRect = menu.getBoundingClientRect();

        let top  = caretY + lineHeight + 4; // just below the current line
        let left = caretX;

        // Clamp to viewport / editor bounds a bit
        const maxLeft = rect.left + window.scrollX + rect.width - menuRect.width - 8;
        if (left > maxLeft) left = maxLeft;
        if (left < rect.left + window.scrollX + 4) left = rect.left + window.scrollX + 4;

        menu.style.top  = `${top}px`;
        menu.style.left = `${left}px`;

        // Delay focus slightly so it reliably lands on the first item after rendering
        if (buttons.length) {
            setTimeout(() => {
                if (buttons[0]) {
                    buttons[0].focus();
                }
            }, 0);
        }
    }

    function closeCommandMenu() {
        if (!commandMenuEl) return;
        commandMenuEl.style.display = 'none';
    }

    async function addSelectionToTask() {
        const editor = getFocusedEditor();
        if (!editor) return;
        const start = editor.selectionStart;
        const end = editor.selectionEnd;
        const text = (editor.value || '').slice(start, end).trim();
        if (!text) {
            if (window.showNotification) {
                window.showNotification('Select some text in the note first', 'warning');
            }
            return;
        }

        const preview = text.length > 120 ? text.slice(0, 120) + '…' : text;
        const ok = window.confirm ? window.confirm(`Make this selection a task?\n\n"${preview}"`) : true;
        if (!ok) {
            return;
        }

        const taskPayload = {
            title: text,
            description: '',
            project: '',
            estimated_duration: 60
        };

        try {
            if (typeof window.createTask === 'function') {
                await window.createTask(taskPayload);
            } else if (window.Utils && typeof Utils.apiCall === 'function') {
                await Utils.apiCall('/api/tasks', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(taskPayload)
                });
            }
            if (window.showNotification) {
                window.showNotification('Task created from note selection', 'success');
            }
        } catch (err) {
            console.error('Failed to create task from selection', err);
            if (window.showNotification) {
                window.showNotification('Failed to create task from selection', 'error');
            }
        }
    }

    function attachEventHandlers() {
        const viewListBtn = document.getElementById('notes-view-list-btn');
        const splitToggleBtn = document.getElementById('notes-split-toggle-btn');
        const addSelectionBtn = document.getElementById('notes-add-selection-task-btn');
        const newTabBtn = document.getElementById('notes-tab-new');
        const primary = document.getElementById('notes-editor-primary');
        const secondary = document.getElementById('notes-editor-secondary');
        const bulkDeleteBtn = document.getElementById('notes-delete-selected-btn');
        const selectAllCheckbox = document.getElementById('notes-select-all');

        if (viewListBtn) {
            viewListBtn.addEventListener('click', openNotesListModal);
        }
        if (splitToggleBtn) {
            splitToggleBtn.addEventListener('click', toggleSplitView);
        }
        if (addSelectionBtn) {
            addSelectionBtn.addEventListener('click', addSelectionToTask);
        }
        if (newTabBtn) {
            newTabBtn.addEventListener('click', createNewNote);
        }
        if (primary) {
            primary.addEventListener('input', function () { handleEditorInput(primary); });
            primary.addEventListener('focus', function () { lastFocusedEditor = 'primary'; });
            primary.addEventListener('keydown', function (e) { handleEditorKeydown(e, primary); });
        }
        if (secondary) {
            secondary.addEventListener('input', function () { handleEditorInput(secondary); });
            secondary.addEventListener('focus', function () { lastFocusedEditor = 'secondary'; });
            secondary.addEventListener('keydown', function (e) { handleEditorKeydown(e, secondary); });
        }

        const closeListBtn = document.getElementById('close-notes-list-modal');
        if (closeListBtn) {
            closeListBtn.addEventListener('click', closeNotesListModal);
        }
        if (bulkDeleteBtn) {
            bulkDeleteBtn.addEventListener('click', deleteSelectedNotes);
        }
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', function () {
                if (this.checked) {
                    selectedNoteIds = new Set(notes.map(n => n.id));
                } else {
                    selectedNoteIds.clear();
                }
                renderNotesList();
                updateNotesBulkControls();
            });
        }

        // Close command menu on outside click
        if (!window.__notesCommandMenuOutsideClick) {
            document.addEventListener('click', function (e) {
                if (commandMenuEl && commandMenuEl.style.display === 'flex' && !commandMenuEl.contains(e.target)) {
                    closeCommandMenu();
                    commandMenuEditor = null;
                }
                if (tabContextMenuEl && tabContextMenuEl.style.display === 'flex' && !tabContextMenuEl.contains(e.target)) {
                    closeTabContextMenu();
                }
            });
            window.__notesCommandMenuOutsideClick = true;
        }
    }

    function renderNotesList() {
        const listEl = document.getElementById('notes-list');
        if (!listEl) return;
        listEl.innerHTML = '';
        notes.forEach(note => {
            // Do not show ephemeral blank notes in the View Notes modal.
            if (isEphemeralNote(note)) return;

            const li = document.createElement('li');

            const selectCheckbox = document.createElement('input');
            selectCheckbox.type = 'checkbox';
            selectCheckbox.className = 'notes-list-select';
            selectCheckbox.checked = selectedNoteIds.has(note.id);
            selectCheckbox.addEventListener('click', function (ev) {
                ev.stopPropagation();
            });
            selectCheckbox.addEventListener('change', function (ev) {
                ev.stopPropagation();
                if (this.checked) {
                    selectedNoteIds.add(note.id);
                } else {
                    selectedNoteIds.delete(note.id);
                }
                updateNotesBulkControls();
            });

            const title = document.createElement('span');
            title.className = 'notes-list-title';
            title.textContent = note.title || 'Untitled';

            const meta = document.createElement('span');
            meta.className = 'notes-list-meta';
            if (note.updated_at) {
                try {
                    const dt = new Date(note.updated_at);
                    meta.textContent = dt.toLocaleString();
                } catch (e) {
                    meta.textContent = note.updated_at;
                }
            }

            const renameBtn = document.createElement('button');
            renameBtn.type = 'button';
            renameBtn.className = 'notes-list-rename-btn';
            renameBtn.innerHTML = '<i class="fas fa-pen"></i>';
            renameBtn.title = 'Rename note';
            renameBtn.addEventListener('click', function (ev) {
                ev.stopPropagation();
                renameActiveNote(note.id);
                renderNotesList();
            });

            const deleteBtn = document.createElement('button');
            deleteBtn.type = 'button';
            deleteBtn.className = 'notes-list-delete-btn';
            deleteBtn.innerHTML = '<i class="fas fa-trash"></i>';
            deleteBtn.title = 'Delete note';
            deleteBtn.addEventListener('click', function (ev) {
                ev.stopPropagation();
                deleteNote(note.id);
            });

            const openInSplitBtn = document.createElement('button');
            openInSplitBtn.type = 'button';
            openInSplitBtn.className = 'notes-list-split-open-btn';
            openInSplitBtn.innerHTML = '<i class="fas fa-columns"></i>';
            openInSplitBtn.title = 'Open in split view';
            openInSplitBtn.addEventListener('click', function (ev) {
                ev.stopPropagation();
                // Ensure this note is in the open tabs list
                if (!Array.isArray(openNoteIds)) {
                    openNoteIds = [];
                }
                if (!openNoteIds.includes(note.id)) {
                    openNoteIds.push(note.id);
                }
                // Set as the secondary note and enable split view
                secondaryNoteId = note.id;
                splitViewEnabled = true;
                if (typeof saveNotes === 'function') {
                    saveNotes();
                }
                render();
                closeNotesListModal();
            });

            li.appendChild(selectCheckbox);
            li.appendChild(title);
            li.appendChild(meta);
            li.appendChild(renameBtn);
            li.appendChild(openInSplitBtn);
            li.appendChild(deleteBtn);
            li.addEventListener('click', function () {
                // When a note is chosen from the list, make sure it is also
                // represented as an open tab and becomes the active note.
                if (!Array.isArray(openNoteIds)) {
                    openNoteIds = [];
                }
                if (!openNoteIds.includes(note.id)) {
                    openNoteIds.push(note.id);
                }
                setActiveNote(note.id);
                // Persist updated open tabs + active note to local cache
                if (typeof saveNotes === 'function') {
                    saveNotes();
                }
                closeNotesListModal();
            });
            listEl.appendChild(li);
        });
    }

    function updateNotesBulkControls() {
        const bulkDeleteBtn = document.getElementById('notes-delete-selected-btn');
        const selectAllCheckbox = document.getElementById('notes-select-all');
        if (!bulkDeleteBtn || !selectAllCheckbox) return;
        const count = selectedNoteIds.size;
        bulkDeleteBtn.disabled = !count;
        bulkDeleteBtn.textContent = count > 0 ? `Delete ${count} selected` : 'Delete selected';

        const total = notes.length;
        if (!total) {
            selectAllCheckbox.checked = false;
            selectAllCheckbox.indeterminate = false;
            return;
        }
        if (count === 0) {
            selectAllCheckbox.checked = false;
            selectAllCheckbox.indeterminate = false;
        } else if (count === total) {
            selectAllCheckbox.checked = true;
            selectAllCheckbox.indeterminate = false;
        } else {
            selectAllCheckbox.checked = false;
            selectAllCheckbox.indeterminate = true;
        }
    }

    function deleteSelectedNotes() {
        if (!selectedNoteIds.size) return;
        const count = selectedNoteIds.size;
        const confirmed = window.confirm ? window.confirm(`Delete ${count} selected note${count > 1 ? 's' : ''} permanently?`) : true;
        if (!confirmed) return;

        const idsToDelete = Array.from(selectedNoteIds);
        // Use skipConfirm flag to avoid repeated prompts
        idsToDelete.forEach(id => deleteNote(id, { skipConfirm: true }));
        selectedNoteIds.clear();
        updateNotesBulkControls();
    }

    function openNotesListModal() {
        const modal = document.getElementById('notes-list-modal');
        if (!modal) return;
        selectedNoteIds = new Set();
        renderNotesList();
        updateNotesBulkControls();
        modal.style.display = 'flex';
        modal.classList.add('active');
    }

    function closeNotesListModal() {
        const modal = document.getElementById('notes-list-modal');
        if (!modal) return;
        modal.classList.remove('active');
        modal.style.display = 'none';
    }

    function deleteNote(id, options) {
        if (!id) return;
        const idx = notes.findIndex(n => n.id === id);
        if (idx === -1) return;
        const skipConfirm = options && options.skipConfirm;
        const confirmed = skipConfirm ? true : (window.confirm ? window.confirm('Delete this note permanently?') : true);
        if (!confirmed) return;

        const noteId = notes[idx].id;
        notes.splice(idx, 1);

        // Delete on server (fire and forget)
        try {
            fetch(`/api/notes/${encodeURIComponent(noteId)}`, { method: 'DELETE' });
        } catch (e) {
            console.error('Failed to delete note on server', e);
        }

        // Always update local cache
        saveAllNotesToLocalStorage();

        if (Array.isArray(openNoteIds)) {
            const openIdx = openNoteIds.indexOf(noteId);
            if (openIdx !== -1) openNoteIds.splice(openIdx, 1);
        }

        // If we've deleted all notes, immediately create a fresh default welcome note
        if (!notes.length) {
            const welcomeNote = createNoteObject('Welcome');
            notes.push(welcomeNote);
            openNoteIds = [welcomeNote.id];
            activeNoteId = welcomeNote.id;
            secondaryNoteId = null;
        } else {
            if (activeNoteId === noteId) {
                // Active note was deleted: fall back to first open tab or first remaining note
                activeNoteId = (openNoteIds && openNoteIds[0]) || (notes[0] && notes[0].id) || null;
            }
            if (secondaryNoteId === noteId) {
                secondaryNoteId = null;
            }
        }

        render();
        renderNotesList();
        saveNotes();
    }

    function init() {
        const page = document.getElementById('notes-page');
        if (!page) return;
        loadNotes().then(() => {
            render();
            attachEventHandlers();
        });
    }

    // Expose a minimal API if needed later
    window.Notes = {
        init,
        addSelectionToTask
    };

    // Initialize when DOM is ready so that navigating to Notes works on first open
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
