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

    const SPLIT_CONTENT_PREFIX = '__SHAKSHUKA_SPLIT_V1__';
    const SPLIT_CONTENT_PREFIX_B64 = '__SHAKSHUKA_SPLIT_B64_V1__';

    function decodeHtmlEntities(str) {
        if (typeof str !== 'string' || !str) return '';
        if (!/[&][a-zA-Z#0-9]+;/.test(str)) return str;
        try {
            const textarea = document.createElement('textarea');
            textarea.innerHTML = str;
            return textarea.value;
        } catch (e) {
            return str;
        }
    }

    function base64EncodeUnicode(str) {
        try {
            return btoa(unescape(encodeURIComponent(str)));
        } catch (e) {
            return '';
        }
    }

    function base64DecodeUnicode(str) {
        try {
            return decodeURIComponent(escape(atob(str)));
        } catch (e) {
            return '';
        }
    }

    function decodeSplitContent(raw) {
        if (typeof raw !== 'string') {
            return { primary: '', secondary: '', encoded: false };
        }
        if (raw.startsWith(SPLIT_CONTENT_PREFIX_B64)) {
            const b64 = raw.slice(SPLIT_CONTENT_PREFIX_B64.length);
            const json = base64DecodeUnicode(b64);
            try {
                const parsed = JSON.parse(json);
                const primary = parsed && typeof parsed.primary === 'string' ? parsed.primary : '';
                const secondary = parsed && typeof parsed.secondary === 'string' ? parsed.secondary : '';
                return { primary, secondary, encoded: true };
            } catch (e) {
                return { primary: raw, secondary: '', encoded: false };
            }
        }
        if (!raw.startsWith(SPLIT_CONTENT_PREFIX)) {
            return { primary: raw, secondary: '', encoded: false };
        }
        try {
            const payloadRaw = raw.slice(SPLIT_CONTENT_PREFIX.length);
            const payload = decodeHtmlEntities(payloadRaw);
            const parsed = JSON.parse(payload);
            const primary = parsed && typeof parsed.primary === 'string' ? parsed.primary : '';
            const secondary = parsed && typeof parsed.secondary === 'string' ? parsed.secondary : '';
            return { primary, secondary, encoded: true };
        } catch (e) {
            return { primary: raw, secondary: '', encoded: false };
        }
    }

    function getEncodedNoteContent(note) {
        const primary = note && typeof note.content === 'string' ? note.content : '';
        const secondary = note && typeof note.content_secondary === 'string' ? note.content_secondary : '';
        const shouldEncode = !!(note && note.__splitEncoded) || secondary.length > 0;
        if (!shouldEncode) {
            return primary;
        }
        try {
            const json = JSON.stringify({ primary, secondary });
            return SPLIT_CONTENT_PREFIX_B64 + base64EncodeUnicode(json);
        } catch (e) {
            return primary;
        }
    }

    function ensureNoteHasSplitFields(note) {
        if (!note || typeof note !== 'object') return;
        const decoded = decodeSplitContent(note.content);
        if (decoded.encoded) {
            note.content = decoded.primary;
            note.content_secondary = decoded.secondary;
            note.__splitEncoded = true;
        } else {
            if (typeof note.content !== 'string') {
                note.content = '';
            }
            if (typeof note.content_secondary !== 'string') {
                note.content_secondary = '';
            }
        }
    }

    function autoEnableSplitViewIfActiveNoteHasSecondary() {
        const note = getActiveNote();
        if (!note) return;
        const secondary = typeof note.content_secondary === 'string' ? note.content_secondary : '';
        if (secondary.trim().length > 0) {
            splitViewEnabled = true;
        }
    }

    // Context menu for note tabs (right-click)
    let tabContextMenuEl = null;
    let tabContextNoteId = null;

    function debugLog(...args) {
        if (window.Utils && typeof Utils.debugLog === 'function') {
            Utils.debugLog('[Notes]', ...args);
        }
    }

    // Temporarily disable "ephemeral" empty note behavior so that even brand-
    // new blank notes are treated as real notes and fully persisted.
    function isEphemeralNote(note) {
        return false;
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
            notes.forEach(ensureNoteHasSplitFields);
            notes.forEach(note => {
                if (note && note.__saving) {
                    delete note.__saving;
                }
            });
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
            // Deprecated: split view is now a second pane of the SAME note.
            secondaryNoteId = null;
            autoEnableSplitViewIfActiveNoteHasSecondary();
            ensureUniqueNoteIds();
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
            // Persist all notes, including empty ones, for now.
            const persistedNotes = notes.map(note => {
                const copy = Object.assign({}, note);
                if (copy.__saving) {
                    delete copy.__saving;
                }
                return copy;
            });

            // Ensure openNoteIds and activeNoteId only reference existing notes.
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
                secondaryNoteId: null,
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
            let cachedParsed = null;
            if (!Array.isArray(serverNotes) || !serverNotes.length) {
                // If the server returns an empty list but the browser has a
                // cached notes payload, prefer the local cache to avoid
                // accidentally clobbering user notes during transient backend
                // issues or DB path changes.
                const cached = window.localStorage.getItem(STORAGE_KEY);
                if (cached) {
                    debugLog('No notes from server; loading from localStorage cache');
                    loadNotesFromLocalStorage();
                    return;
                }

                debugLog('No notes from server and no local cache, creating default');
                const welcome = await createNoteOnServer('Welcome', '');
                notes = welcome ? [welcome] : [createNoteObject('Welcome')];
            } else {
                notes = serverNotes;

                notes.forEach(ensureNoteHasSplitFields);

                // Defensive: if we ever end up with duplicate IDs (bad cache/older builds),
                // fix them so two distinct notes cannot overwrite each other.
                ensureUniqueNoteIds();

                try {
                    const cachedRaw = window.localStorage.getItem(STORAGE_KEY);
                    if (cachedRaw) {
                        cachedParsed = JSON.parse(cachedRaw);
                        const cachedNotes = cachedParsed && Array.isArray(cachedParsed.notes) ? cachedParsed.notes : [];
                        if (cachedNotes.length) {
                            const cachedById = new Map(cachedNotes.map(n => [n.id, n]));
                            for (const note of notes) {
                                const cachedNote = cachedById.get(note.id);
                                const serverContentEmpty = (!note.content && !note.content_secondary);
                                const cachedHasContent = cachedNote && ((typeof cachedNote.content === 'string' && cachedNote.content.length > 0) || (typeof cachedNote.content_secondary === 'string' && cachedNote.content_secondary.length > 0));
                                if (serverContentEmpty && cachedHasContent) {
                                    const serverUpdated = Date.parse(note.updated_at || '') || 0;
                                    const cachedUpdated = Date.parse(cachedNote.updated_at || '') || 0;
                                    if (cachedUpdated > serverUpdated) {
                                        note.content = typeof cachedNote.content === 'string' ? cachedNote.content : '';
                                        note.content_secondary = typeof cachedNote.content_secondary === 'string' ? cachedNote.content_secondary : '';
                                        if (typeof note.content_secondary === 'string' && note.content_secondary.length > 0) {
                                            note.__splitEncoded = true;
                                        }
                                        saveNoteToServer(note);
                                    }
                                }
                            }
                        }
                    }
                } catch (e) {
                    // Ignore cache merge issues
                }
            }
            const ids = notes.map(n => n && n.id).filter(Boolean);
            let desiredOpenIds = [];
            let desiredActiveId = null;
            let desiredSplit = false;
            try {
                if (!cachedParsed) {
                    const cachedRaw = window.localStorage.getItem(STORAGE_KEY);
                    if (cachedRaw) {
                        cachedParsed = JSON.parse(cachedRaw);
                    }
                }
            } catch (e) {
                cachedParsed = null;
            }
            if (cachedParsed) {
                desiredSplit = !!cachedParsed.splitViewEnabled;
                if (Array.isArray(cachedParsed.openNoteIds) && cachedParsed.openNoteIds.length) {
                    desiredOpenIds = cachedParsed.openNoteIds.filter(id => typeof id === 'string' && ids.includes(id));
                }
                if (cachedParsed.activeNoteId && ids.includes(cachedParsed.activeNoteId)) {
                    desiredActiveId = cachedParsed.activeNoteId;
                }
            }

            if (!desiredOpenIds.length && ids.length) {
                desiredOpenIds = ids.slice();
            }
            if (desiredActiveId && !desiredOpenIds.includes(desiredActiveId)) {
                desiredOpenIds.unshift(desiredActiveId);
            }
            openNoteIds = desiredOpenIds;
            activeNoteId = desiredActiveId || openNoteIds[0] || ids[0] || null;
            splitViewEnabled = desiredSplit;
            autoEnableSplitViewIfActiveNoteHasSecondary();
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

        // Avoid spamming the server with multiple concurrent saves for the
        // same brand-new local note. A simple per-note flag is enough here.
        if (note.__saving) {
            return;
        }
        note.__saving = true;

        const replaceNoteIdReferences = (oldId, newId) => {
            if (!oldId || !newId || oldId === newId) return;
            try {
                if (Array.isArray(openNoteIds) && openNoteIds.length) {
                    openNoteIds = openNoteIds.map(id => id === oldId ? newId : id);
                }
                if (activeNoteId === oldId) {
                    activeNoteId = newId;
                }
                if (secondaryNoteId === oldId) {
                    secondaryNoteId = newId;
                }

                const primary = document.getElementById('notes-editor-primary');
                const secondary = document.getElementById('notes-editor-secondary');
                if (primary && primary.dataset && primary.dataset.noteId === oldId) {
                    primary.dataset.noteId = newId;
                }
                if (secondary && secondary.dataset && secondary.dataset.noteId === oldId) {
                    secondary.dataset.noteId = newId;
                }
            } catch (e) {
                // no-op
            }
        };

        try {
            const payload = {
                title: note.title,
                content: getEncodedNoteContent(note)
            };
            const oldId = note.id;

            // If this is a local-only scratch ID (note-...), go straight to a
            // POST create instead of first attempting PUT (which 404s).
            let response;
            if (typeof oldId === 'string' && oldId.startsWith('note-')) {
                const created = await createNoteOnServer(note.title, getEncodedNoteContent(note));
                if (created && created.id) {
                    note.id = created.id;
                    note.created_at = created.created_at;
                    note.updated_at = created.updated_at;

                    replaceNoteIdReferences(oldId, note.id);

                    if (splitViewEnabled && secondaryNoteId === activeNoteId) {
                        let candidateId = null;
                        if (Array.isArray(openNoteIds) && openNoteIds.length) {
                            candidateId = openNoteIds.find(openId => openId !== activeNoteId && notes.some(n => n.id === openId)) || null;
                        }
                        if (!candidateId) {
                            const anyOther = notes.find(n => n.id !== activeNoteId);
                            candidateId = anyOther ? anyOther.id : null;
                        }
                        if (candidateId) {
                            secondaryNoteId = candidateId;
                        }
                    }
                    // Replace in notes array if an entry with the old id still exists
                    const idx = notes.findIndex(n => n.id === oldId);
                    if (idx !== -1) {
                        notes[idx] = note;
                    }
                }
                saveAllNotesToLocalStorage();
                return;
            } else {
                response = await fetch(`/api/notes/${encodeURIComponent(oldId)}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
            }

            if (response && response.status === 404) {
                // Note does not exist on the server yet (e.g. initial local-only note).
                // Create it and update local IDs so future saves work.
                const created = await createNoteOnServer(note.title, getEncodedNoteContent(note));
                if (created && created.id) {
                    note.id = created.id;
                    note.created_at = created.created_at;
                    note.updated_at = created.updated_at;

                    replaceNoteIdReferences(oldId, note.id);

                    if (splitViewEnabled && secondaryNoteId === activeNoteId) {
                        let candidateId = null;
                        if (Array.isArray(openNoteIds) && openNoteIds.length) {
                            candidateId = openNoteIds.find(openId => openId !== activeNoteId && notes.some(n => n.id === openId)) || null;
                        }
                        if (!candidateId) {
                            const anyOther = notes.find(n => n.id !== activeNoteId);
                            candidateId = anyOther ? anyOther.id : null;
                        }
                        if (candidateId) {
                            secondaryNoteId = candidateId;
                        }
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

            if (response && !response.ok) {
                throw new Error('Failed to save note');
            }

            // Successful PUT → keep local cache in sync
            saveAllNotesToLocalStorage();
        } catch (err) {
            console.error('Failed to save note to server', err);
            // Still keep local cache so user doesn't lose work
            saveAllNotesToLocalStorage();
        } finally {
            note.__saving = false;
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

    function makeLocalNoteId() {
        try {
            if (window.crypto && typeof window.crypto.randomUUID === 'function') {
                return 'note-' + window.crypto.randomUUID();
            }
        } catch (e) {
            // ignore
        }
        return 'note-' + Date.now() + '-' + Math.floor(Math.random() * 1000000000);
    }

    function createNoteObject(title) {
        const id = makeLocalNoteId();
        const now = new Date().toLocaleString();
        return {
            id,
            title: title || 'Untitled',
            content: '',
            content_secondary: '',
            created_at: now,
            updated_at: now
        };
    }

    function ensureUniqueNoteIds() {
        if (!Array.isArray(notes) || !notes.length) {
            return;
        }

        const seen = new Set();
        let changed = false;

        for (const note of notes) {
            if (!note || typeof note !== 'object') {
                continue;
            }
            const id = note.id;
            if (typeof id !== 'string' || !id || seen.has(id)) {
                note.id = makeLocalNoteId();
                changed = true;
            }
            seen.add(note.id);
        }

        const ids = notes.map(n => n && n.id).filter(Boolean);
        if (!Array.isArray(openNoteIds)) {
            openNoteIds = [];
        }
        openNoteIds = openNoteIds.filter(id => typeof id === 'string' && ids.includes(id));
        openNoteIds = Array.from(new Set(openNoteIds));
        if (!openNoteIds.length && ids.length) {
            openNoteIds = ids.slice();
            changed = true;
        }

        if (!activeNoteId || !ids.includes(activeNoteId)) {
            activeNoteId = openNoteIds[0] || ids[0] || null;
            changed = true;
        }
        if (secondaryNoteId && !ids.includes(secondaryNoteId)) {
            secondaryNoteId = null;
            changed = true;
        }
        if (secondaryNoteId && secondaryNoteId === activeNoteId) {
            secondaryNoteId = null;
            changed = true;
        }
        if (changed) {
            saveAllNotesToLocalStorage();
        }
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

    function ensureSplitPaneChoiceModal() {
        let modal = document.getElementById('notes-split-pane-choice-modal');
        if (modal) return modal;

        modal = document.createElement('div');
        modal.id = 'notes-split-pane-choice-modal';
        modal.className = 'modal';
        modal.style.display = 'none';
        modal.innerHTML = `
            <div class="modal-content" style="max-width: 520px;">
                <div class="modal-header">
                    <h2>Replace split pane</h2>
                    <button class="modal-close" type="button" data-action="cancel">&times;</button>
                </div>
                <div class="modal-body">
                    <p id="notes-split-pane-choice-text" style="color: var(--text-secondary); margin: 0;"></p>
                </div>
                <div class="modal-footer" style="display:flex; gap: 0.5rem; justify-content: flex-end;">
                    <button id="notes-split-pane-choice-left-btn" class="btn-secondary" type="button" data-action="left">Primary (Left)</button>
                    <button id="notes-split-pane-choice-right-btn" class="btn-primary" type="button" data-action="right">Secondary (Right)</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        return modal;
    }

    function promptSplitPaneSide(context) {
        return new Promise((resolve) => {
            const modal = ensureSplitPaneChoiceModal();
            if (!modal) {
                resolve(null);
                return;
            }

            const targetTitle = context && context.targetTitle ? String(context.targetTitle) : 'this note';
            const leftTitle = context && context.leftTitle ? String(context.leftTitle) : 'Untitled';
            const rightTitle = context && context.rightTitle ? String(context.rightTitle) : 'Untitled';

            const textEl = modal.querySelector('#notes-split-pane-choice-text');
            if (textEl) {
                textEl.textContent = `Open "${targetTitle}" in which editor? Primary: "${leftTitle}" | Secondary: "${rightTitle}"`;
            }

            const cleanup = () => {
                modal.style.display = 'none';
                modal.classList.remove('active');
                modal.removeEventListener('click', onClick);
            };

            const onClick = (e) => {
                const btn = e.target && e.target.closest ? e.target.closest('[data-action]') : null;
                if (!btn) return;
                const action = btn.getAttribute('data-action');
                if (action === 'left') {
                    cleanup();
                    resolve('left');
                } else if (action === 'right') {
                    cleanup();
                    resolve('right');
                } else if (action === 'cancel') {
                    cleanup();
                    resolve(null);
                }
            };

            modal.addEventListener('click', onClick);
            modal.style.display = 'flex';
            modal.classList.add('active');
        });
    }

    function flushEditorsToNotes() {
        const primaryEl = document.getElementById('notes-editor-primary');
        const secondaryEl = document.getElementById('notes-editor-secondary');
        if (primaryEl) {
            try { handleEditorInput(primaryEl); } catch (e) {}
        }
        if (secondaryEl) {
            try { handleEditorInput(secondaryEl); } catch (e) {}
        }
    }

    async function openNoteInSplit(noteId) {
        if (!noteId) return false;
        const target = notes.find(n => n.id === noteId);
        if (!target) return false;

        if (!Array.isArray(openNoteIds)) {
            openNoteIds = [];
        }
        if (!openNoteIds.includes(noteId)) {
            openNoteIds.push(noteId);
        }

        const primaryEl = document.getElementById('notes-editor-primary');
        const secondaryEl = document.getElementById('notes-editor-secondary');
        const secondaryHasContent = !!(secondaryEl && typeof secondaryEl.value === 'string' && secondaryEl.value.trim().length > 0);

        let side = 'right';
        if (splitViewEnabled && secondaryHasContent) {
            const currentLeftId = activeNoteId;
            const currentRightId = (secondaryNoteId && secondaryNoteId !== activeNoteId) ? secondaryNoteId : null;
            const leftNote = notes.find(n => n.id === currentLeftId) || null;
            const rightNote = currentRightId ? (notes.find(n => n.id === currentRightId) || null) : null;
            const leftTitle = leftNote && leftNote.title ? leftNote.title : 'Untitled';
            const rightTitle = rightNote
                ? (rightNote.title || 'Untitled')
                : (leftTitle + ' (secondary pane)');

            side = await promptSplitPaneSide({
                targetTitle: target.title || 'Untitled',
                leftTitle,
                rightTitle
            });
            if (!side) {
                return false;
            }
        }

        flushEditorsToNotes();

        const currentLeftId = activeNoteId;
        const currentRightId = (secondaryNoteId && secondaryNoteId !== activeNoteId) ? secondaryNoteId : null;

        splitViewEnabled = true;

        if (side === 'left') {
            if (noteId === currentRightId) {
                activeNoteId = noteId;
                secondaryNoteId = currentLeftId && currentLeftId !== noteId ? currentLeftId : null;
            } else {
                activeNoteId = noteId;
                if (currentRightId && currentRightId !== activeNoteId) {
                    secondaryNoteId = currentRightId;
                } else {
                    secondaryNoteId = null;
                }
            }
        } else {
            if (noteId === currentLeftId) {
                secondaryNoteId = null;
            } else {
                secondaryNoteId = noteId;
            }
        }

        if (typeof saveNotes === 'function') {
            saveNotes();
        }
        render();
        return true;
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

            // Note: double-click to rename is intentionally restricted to the
            // title span (see titleSpan dblclick handler) so that double-
            // clicking the close button does NOT trigger rename.

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
        // Bind the current note ID to the editor so input events always update
        // the note that was actually visible when the user typed, even if
        // activeNoteId changes slightly later (e.g. when clicking the + tab).
        primary.dataset.noteId = primaryNote.id;
        primary.title = primaryNote.title || 'Untitled';
        primary.setAttribute('aria-label', 'Notes editor (primary): ' + (primaryNote.title || 'Untitled'));

        let secondaryNote = null;
        if (splitViewEnabled && secondaryNoteId && secondaryNoteId !== primaryNote.id) {
            secondaryNote = notes.find(n => n.id === secondaryNoteId) || null;
        }

        if (secondaryNote) {
            secondary.value = secondaryNote.content || '';
            secondary.dataset.noteId = secondaryNote.id;
            secondary.title = secondaryNote.title || 'Untitled';
            secondary.setAttribute('aria-label', 'Notes editor (secondary): ' + (secondaryNote.title || 'Untitled'));
        } else {
            secondary.value = primaryNote.content_secondary || '';
            secondary.dataset.noteId = primaryNote.id;
            secondary.title = primaryNote.title || 'Untitled';
            secondary.setAttribute('aria-label', 'Notes editor (secondary): ' + (primaryNote.title || 'Untitled'));
        }

        ensureSecondaryEditorVisibility();
    }

    function render() {
        renderTabs();
        renderEditors();
    }

    function createNewNote() {
        // Derive a simple sequential label (Note 1, Note 2, ...)
        const baseIndex = notes.length + 1;
        const title = 'Note ' + baseIndex;

        // Create a local-only note first. It will only be persisted to SQLite
        // once the user actually edits it (content/title), via saveNoteToServer.
        const note = createNoteObject(title);

        // Keep the existing notes list, but add the new note to the front so it
        // is easy to find in the View Notes list if needed.
        notes.unshift(note);

        // Ensure openNoteIds exists and append the new tab at the end so it
        // appears just before the + button.
        if (!Array.isArray(openNoteIds)) {
            openNoteIds = [];
        }
        openNoteIds.push(note.id);

        // New tab should always gain focus, regardless of existing content.
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
        note.updated_at = new Date().toLocaleString();
        renderTabs();
        saveNoteToServer(note);
        scheduleSavedNotification();
    }

    function handleEditorInput(editor) {
        if (!editor) return;

        let targetNote = null;
        let boundId = null;

        // Prefer the note ID that was bound to this editor when it was last
        // rendered. This avoids races where activeNoteId changes (e.g. when
        // clicking + to open a new tab) while keystrokes are still being
        // processed for the previously visible note.
        if (editor.dataset && editor.dataset.noteId) {
            boundId = editor.dataset.noteId;
            targetNote = notes.find(n => n.id === boundId) || null;
        }

        // Fallback: derive target note from active/split-view state.
        if (!targetNote) {
            if (editor.id === 'notes-editor-secondary' && splitViewEnabled && secondaryNoteId && secondaryNoteId !== activeNoteId) {
                targetNote = notes.find(n => n.id === secondaryNoteId) || getActiveNote();
            } else {
                targetNote = getActiveNote();
            }
        }

        if (!targetNote) return;

        // Mark this note as "touched" so it is no longer treated as an
        // ephemeral scratch note, even if the user later clears its content.
        targetNote.__touched = true;

        if (editor.id === 'notes-editor-secondary') {
            const derivedSecondaryId = (boundId && boundId !== activeNoteId)
                ? boundId
                : (splitViewEnabled && secondaryNoteId && secondaryNoteId !== activeNoteId ? secondaryNoteId : null);

            // If the right pane is currently showing a different note, always
            // write to that note's primary content and NEVER to the active
            // note's content_secondary.
            if (derivedSecondaryId && derivedSecondaryId !== activeNoteId) {
                const rightNote = notes.find(n => n.id === derivedSecondaryId) || targetNote;
                if (!rightNote) return;
                rightNote.__touched = true;
                rightNote.content = editor.value;
                rightNote.updated_at = new Date().toLocaleString();
                saveNoteToServer(rightNote);
                scheduleSavedNotification();
                return;
            }

            // Otherwise this is "same note" split (secondary pane belongs to
            // the active note).
            const active = getActiveNote();
            if (!active) return;
            active.__touched = true;
            active.content_secondary = editor.value;
            active.__splitEncoded = true;
            active.updated_at = new Date().toLocaleString();
            saveNoteToServer(active);
            scheduleSavedNotification();
            return;
        } else {
            targetNote.content = editor.value;
        }
        targetNote.updated_at = new Date().toLocaleString();
        saveNoteToServer(targetNote);
        scheduleSavedNotification();
    }

    function toggleSplitView() {
        splitViewEnabled = !splitViewEnabled;

        ensureSecondaryEditorVisibility();
        saveNotes();
        renderEditors();

        if (splitViewEnabled && window.showNotification) {
            const primaryNote = getActiveNote();
            const leftTitle = primaryNote && primaryNote.title ? primaryNote.title : 'Untitled';
            window.showNotification(`Split view: ${leftTitle}`, 'info');
        }
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
                    const stripped = line.replace(/^([#]+\s|[-*]\s|\d+\.\s?|\[ \]\s)/, '');
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

        const stripped = line.replace(/^([#]+\s|[-*]\s|\d+\.\s?|\[ \]\s)/, '');
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
                    openNoteInSplit(id).catch(() => {});
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
                const visibleNotes = notes; // all notes are visible now
                if (this.checked) {
                    selectedNoteIds = new Set(visibleNotes.map(n => n.id));
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
            // Ephemeral filtering disabled: show all notes, including empty ones.

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
                openNoteInSplit(note.id)
                    .then((changed) => {
                        if (changed) {
                            closeNotesListModal();
                        }
                    })
                    .catch(() => {
                        closeNotesListModal();
                    });
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

        // Only count real, non-ephemeral notes when driving the Select All
        // checkbox state, to match what is actually visible in the list.
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
