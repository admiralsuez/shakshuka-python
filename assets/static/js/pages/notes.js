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
    let currentFolderFilter = null;  // null = All notes, otherwise folder name
    let explorerSortMode = 'updated';
    let explorerFilterText = '';

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

    // Context menu for explorer (folders + notes)
    let explorerContextMenuEl = null;
    let explorerContextTarget = null; // { type: 'note'|'folder', noteId?, folderKey? }

    // Track drag state for explorer drag-and-drop
    let draggedNoteId = null;

    // Virtual folders allow empty folders (with 0 notes) to appear in the
    // explorer and persist across reloads even before any note is moved into
    // them.
    let virtualFolders = new Set();

    function loadVirtualFolders() {
        try {
            if (!window.localStorage) return;
            const raw = window.localStorage.getItem('shakshuka_notes_folders_v1');
            if (!raw) return;
            const arr = JSON.parse(raw);
            if (Array.isArray(arr)) {
                virtualFolders = new Set(
                    arr
                        .filter(name => typeof name === 'string')
                        .map(name => name.trim())
                        .filter(name => name.length > 0)
                );
            }
        } catch (e) {
            // best-effort only
        }
    }

    function saveVirtualFolders() {
        try {
            if (!window.localStorage) return;
            const arr = Array.from(virtualFolders);
            window.localStorage.setItem('shakshuka_notes_folders_v1', JSON.stringify(arr));
        } catch (e) {
            // best-effort only
        }
    }

    function debugLog(...args) {
        if (window.Utils && typeof Utils.debugLog === 'function') {
            Utils.debugLog('[Notes]', ...args);
        }
    }

    // Approximate maximum size for the notes cache in localStorage (200 MB).
    const MAX_NOTES_CACHE_BYTES = 200 * 1024 * 1024;

    function estimateStringBytes(str) {
        if (!str || typeof str !== 'string') return 0;
        try {
            // Blob gives a closer approximation across browsers.
            return new Blob([str]).size;
        } catch (e) {
            // Fallback: number of UTF-16 code units.
            return str.length;
        }
    }

    function markCacheOverBudget(flag) {
        try {
            if (!window.localStorage) return;
            window.localStorage.setItem('shakshuka_notes_cache_over_budget', flag ? '1' : '0');
        } catch (e) {
            // best-effort only
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
            
            // Migration: if openNoteIds contains ALL notes, reset to just the active/first note
            let rawOpenIds = Array.isArray(parsed.openNoteIds) && parsed.openNoteIds.length
                ? parsed.openNoteIds.filter(id => notes.some(n => n.id === id))
                : [];
            
            // If no openNoteIds or if openNoteIds contains all notes (old behavior), reset to just first
            if (!rawOpenIds.length || rawOpenIds.length === notes.length) {
                const candidateActiveId = parsed.activeNoteId;
                if (candidateActiveId && notes.some(n => n.id === candidateActiveId)) {
                    openNoteIds = [candidateActiveId];
                } else {
                    openNoteIds = [notes[0].id];
                }
            } else {
                openNoteIds = rawOpenIds;
            }
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

            const json = JSON.stringify(payload);
            const sizeBytes = estimateStringBytes(json);

            if (sizeBytes > MAX_NOTES_CACHE_BYTES) {
                // Cache is too large; mark for cleanup and attempt to push any
                // unsynced notes to the server, but avoid writing an even
                // larger payload into localStorage.
                markCacheOverBudget(true);
                debugLog('Notes cache over 200MB — skipping localStorage write and scheduling best-effort flush', { bytes: sizeBytes });

                if (typeof flushUnsyncedNotesToServerBestEffort === 'function') {
                    try {
                        flushUnsyncedNotesToServerBestEffort();
                    } catch (e) {
                        // best-effort only
                    }
                }
                return;
            }

            window.localStorage.setItem(STORAGE_KEY, json);
            markCacheOverBudget(false);
            debugLog('Saved notes to localStorage', { count: persistedNotes.length, bytes: sizeBytes });
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

    // Best-effort background flush of obviously unsynced notes to the server
    // (e.g., local-only IDs) when the cache grows too large.
    async function flushUnsyncedNotesToServerBestEffort() {
        if (!Array.isArray(notes) || !notes.length) return;
        const candidates = notes.filter(n => {
            if (!n || typeof n !== 'object') return false;
            if (typeof n.id === 'string' && n.id.startsWith('note-')) return true;
            if (!n.created_at || !n.updated_at) return true;
            return !!n.__touched;
        });
        for (const note of candidates) {
            try {
                await saveNoteToServer(note);
            } catch (e) {
                // Ignore individual failures; this is best-effort only.
            }
        }
    }

    async function loadNotes() {
        try {
            let serverNotes = null;
            if (window.Utils && typeof window.Utils.apiRequestJson === 'function') {
                serverNotes = await window.Utils.apiRequestJson('/api/notes', {}, { expectObject: false, retries: 1, retryDelayMs: 500 });
            } else {
                const response = await fetch('/api/notes', { credentials: 'include' });
                if (!response.ok) {
                    throw new Error('Failed to load notes');
                }
                serverNotes = await response.json();
            }
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
                const welcome = await createNoteOnServer('Welcome', '', null);
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
                    const rawOpenIds = cachedParsed.openNoteIds.filter(id => typeof id === 'string' && ids.includes(id));
                    // Migration: if openNoteIds contains ALL notes (old behavior), reset to just active/first note
                    if (rawOpenIds.length === notes.length) {
                        const candidateActiveId = cachedParsed.activeNoteId;
                        if (candidateActiveId && ids.includes(candidateActiveId)) {
                            desiredOpenIds = [candidateActiveId];
                        } else {
                            desiredOpenIds = [ids[0]];
                        }
                    } else {
                        desiredOpenIds = rawOpenIds;
                    }
                }
                if (cachedParsed.activeNoteId && ids.includes(cachedParsed.activeNoteId)) {
                    desiredActiveId = cachedParsed.activeNoteId;
                }
            }

            if (!desiredOpenIds.length && ids.length) {
                desiredOpenIds = [ids[0]];
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
                content: getEncodedNoteContent(note),
                folder: (note.folder && typeof note.folder === 'string') ? note.folder : undefined,
            };
            const oldId = note.id;

            // If this is a local-only scratch ID (note-...), go straight to a
            // POST create instead of first attempting PUT (which 404s).
            let response = null;
            if (typeof oldId === 'string' && oldId.startsWith('note-')) {
                const created = await createNoteOnServer(note.title, getEncodedNoteContent(note), (note.folder && typeof note.folder === 'string') ? note.folder : null);
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
                if (window.Utils && typeof window.Utils.apiCall === 'function') {
                    response = await window.Utils.apiCall(`/api/notes/${encodeURIComponent(oldId)}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                } else {
                    response = await fetch(`/api/notes/${encodeURIComponent(oldId)}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload),
                        credentials: 'include'
                    });
                }
            }

            if (response && response.status === 404) {
                // Note does not exist on the server yet (e.g. initial local-only note).
                // Create it and update local IDs so future saves work.
                const created = await createNoteOnServer(note.title, getEncodedNoteContent(note), (note.folder && typeof note.folder === 'string') ? note.folder : null);
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

    async function createNoteOnServer(title, content, folder) {
        try {
            let note = null;
            if (window.Utils && typeof window.Utils.apiRequestJson === 'function') {
                note = await window.Utils.apiRequestJson(
                    '/api/notes',
                    {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ title, content, folder })
                    },
                    { expectObject: true, retries: 0 }
                );
            } else {
                const response = await fetch('/api/notes', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title, content, folder }),
                    credentials: 'include'
                });
                if (!response.ok) {
                    throw new Error('Failed to create note');
                }
                note = await response.json();
            }
            return note;
        } catch (err) {
            console.error('Failed to create note on server', err);
            if (window.Utils && typeof window.Utils.safeShowNotification === 'function') {
                window.Utils.safeShowNotification('Failed to create note on server', 'error');
            }
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

    function createNoteObject(title, folder) {
        const id = makeLocalNoteId();
        const now = new Date().toLocaleString();
        const folderClean = (folder && typeof folder === 'string') ? folder.trim() : '';
        if (folderClean) {
            virtualFolders.add(folderClean);
            saveVirtualFolders();
        }
        return {
            id,
            title: title || 'Untitled',
            content: '',
            content_secondary: '',
            folder: folderClean || null,
            created_at: now,
            updated_at: now
        };
    }

    function getFoldersSummary() {
        const summary = new Map();
        for (const note of notes) {
            if (!note || typeof note !== 'object') continue;
            const folder = (note.folder && typeof note.folder === 'string') ? note.folder : '';
            const key = folder || '';
            const prev = summary.get(key) || 0;
            summary.set(key, prev + 1);
        }
        // Ensure virtual folders show up even if they currently have 0 notes
        if (virtualFolders && virtualFolders.size) {
            for (const name of virtualFolders) {
                if (name && !summary.has(name)) {
                    summary.set(name, 0);
                }
            }
        }
        return summary;
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

    function scrollEditorsIntoView() {
        const primary = document.getElementById('notes-editor-primary');
        if (!primary) return;
        try {
            primary.scrollIntoView({ behavior: 'smooth', block: 'start' });
        } catch (e) {
            try {
                const rect = primary.getBoundingClientRect();
                window.scrollTo({
                    top: rect.top + window.scrollY - 80,
                    behavior: 'smooth'
                });
            } catch (err) {
                // best-effort only
            }
        }
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

    function showNotesDashboard() {
        const dash = document.getElementById('notes-dashboard-view');
        const editorView = document.getElementById('notes-editor-view');
        if (dash) dash.style.display = '';
        if (editorView) editorView.style.display = 'none';
    }

    function showNoteEditorView() {
        const dash = document.getElementById('notes-dashboard-view');
        const editorView = document.getElementById('notes-editor-view');
        if (dash) dash.style.display = 'none';
        if (editorView) editorView.style.display = '';
        scrollEditorsIntoView();
    }

    function renderNotesExplorer() {
        const explorer = document.getElementById('notes-explorer');
        if (!explorer) return;

        const folderListEl = document.getElementById('notes-folder-list');
        const notesListEl = document.getElementById('notes-explorer-notes');
        const currentFolderTitleEl = document.getElementById('notes-explorer-current-folder');
        if (!folderListEl || !notesListEl || !currentFolderTitleEl) return;

        // Folders summary
        const summary = getFoldersSummary();
        folderListEl.innerHTML = '';

        const makeFolderItem = (label, folderKey) => {
            const li = document.createElement('li');
            li.className = 'notes-folder-item';
            const isAll = folderKey === null;
            const isUnsorted = folderKey === '';
            if ((isAll && currentFolderFilter === null) ||
                (isUnsorted && currentFolderFilter === '') ||
                (!isAll && !isUnsorted && folderKey === currentFolderFilter)) {
                li.classList.add('active');
            }
            li.dataset.folder = folderKey === null ? '' : (folderKey || '');

            const nameSpan = document.createElement('span');
            nameSpan.textContent = label;
            li.appendChild(nameSpan);

            const countSpan = document.createElement('span');
            countSpan.className = 'notes-folder-count';
            let count = 0;
            if (folderKey === null) {
                // "All notes" pseudo-folder = sum of all notes
                summary.forEach(v => { count += v || 0; });
            } else if (folderKey === '') {
                count = summary.get('') || 0;
            } else {
                count = summary.get(folderKey) || 0;
            }
            countSpan.textContent = String(count);
            li.appendChild(countSpan);

            li.addEventListener('click', function () {
                if (folderKey === null) {
                    currentFolderFilter = null;        // All notes
                } else if (folderKey === '') {
                    currentFolderFilter = '';          // Unsorted
                } else {
                    currentFolderFilter = folderKey;   // Named folder
                }
                renderNotesExplorer();
            });

            // Drag-and-drop target for notes (except the "All notes" pseudo-folder)
            if (folderKey !== null) {
                li.addEventListener('dragover', function (e) {
                    if (!draggedNoteId) return;
                    e.preventDefault();
                    this.classList.add('drag-over');
                });
                li.addEventListener('dragleave', function (e) {
                    this.classList.remove('drag-over');
                });
                li.addEventListener('drop', function (e) {
                    if (!draggedNoteId) {
                        this.classList.remove('drag-over');
                        return;
                    }
                    e.preventDefault();
                    this.classList.remove('drag-over');
                    const note = notes.find(n => n.id === draggedNoteId);
                    if (!note) return;
                    const key = this.dataset.folder || '';
                    const newFolder = key ? key : null;
                    note.folder = newFolder;
                    note.updated_at = new Date().toLocaleString();
                    saveNoteToServer(note);
                    render();
                });
            }

            // Context menu for real named folders only
            if (folderKey && String(folderKey).trim().length > 0) {
                li.addEventListener('contextmenu', function (e) {
                    e.preventDefault();
                    const key = this.dataset.folder || '';
                    openExplorerContextMenuForFolder(key, e.clientX, e.clientY);
                });
            }

            return li;
        };

        // "All notes" pseudo-folder
        const allLi = makeFolderItem('All notes', null);
        folderListEl.appendChild(allLi);

        // Root/unsorted folder (empty folder name) if there are notes without a folder
        if (summary.get('')) {
            folderListEl.appendChild(makeFolderItem('Unsorted', ''));
        }

        // Actual named folders (sorted alphabetically)
        const namedFolders = Array.from(summary.keys()).filter(k => k && k.trim().length > 0).sort((a, b) => a.localeCompare(b));
        namedFolders.forEach(folderName => {
            folderListEl.appendChild(makeFolderItem(folderName, folderName));
        });

        // Notes list for current folder
        notesListEl.innerHTML = '';
        let filteredNotes = notes.slice();
        if (currentFolderFilter !== null) {
            const target = (currentFolderFilter || '').toLowerCase();
            filteredNotes = filteredNotes.filter(n => {
                const f = (n.folder && typeof n.folder === 'string') ? n.folder.toLowerCase() : '';
                return f === target;
            });
        }

        // Update header title
        if (currentFolderFilter === null) {
            currentFolderTitleEl.textContent = 'All notes';
        } else if (currentFolderFilter === '') {
            currentFolderTitleEl.textContent = 'Unsorted';
        } else {
            currentFolderTitleEl.textContent = currentFolderFilter;
        }

        // Apply text filter and sort
        if (explorerFilterText && explorerFilterText.trim()) {
            const q = explorerFilterText.trim().toLowerCase();
            filteredNotes = filteredNotes.filter(note => {
                const title = (note.title || '').toLowerCase();
                const content = (note.content || '').toLowerCase();
                return title.includes(q) || content.includes(q);
            });
        }

        const sortMode = explorerSortMode || 'updated';
        filteredNotes.sort((a, b) => {
            if (sortMode === 'title') {
                const ta = (a.title || '').toLowerCase();
                const tb = (b.title || '').toLowerCase();
                if (ta < tb) return -1;
                if (ta > tb) return 1;
                return 0;
            }

            const createdA = a.created_at ? new Date(a.created_at).getTime() : 0;
            const createdB = b.created_at ? new Date(b.created_at).getTime() : 0;
            const updatedA = a.updated_at ? new Date(a.updated_at).getTime() : createdA;
            const updatedB = b.updated_at ? new Date(b.updated_at).getTime() : createdB;

            if (sortMode === 'created') {
                return createdB - createdA; // newest first
            }

            // Default: sort by updated_at (newest first)
            return updatedB - updatedA;
        });

        filteredNotes.forEach(note => {
            const li = document.createElement('div');
            li.className = 'notes-explorer-note' + (note.id === activeNoteId ? ' active' : '');
            li.dataset.noteId = note.id;
            li.draggable = true;

            const titleSpan = document.createElement('span');
            titleSpan.className = 'notes-explorer-note-title';
            titleSpan.textContent = note.title || 'Untitled';
            li.appendChild(titleSpan);

            const metaSpan = document.createElement('span');
            metaSpan.className = 'notes-explorer-note-meta';
            if (note.updated_at) {
                metaSpan.textContent = String(note.updated_at);
            } else if (note.created_at) {
                metaSpan.textContent = String(note.created_at);
            }
            li.appendChild(metaSpan);

            li.addEventListener('click', function () {
                const id = this.dataset.noteId;
                if (!id) return;
                if (!Array.isArray(openNoteIds)) {
                    openNoteIds = [];
                }
                if (!openNoteIds.includes(id)) {
                    openNoteIds.push(id);
                }
                activeNoteId = id;
                saveNotes();
                render();
                showNoteEditorView();
            });

            li.addEventListener('dragstart', function (e) {
                const id = this.dataset.noteId;
                if (!id) return;
                draggedNoteId = id;
                try {
                    e.dataTransfer.effectAllowed = 'move';
                    e.dataTransfer.setData('text/plain', id);
                } catch (err) {
                    // ignore
                }
            });

            li.addEventListener('dragend', function () {
                draggedNoteId = null;
                const folders = document.querySelectorAll('.notes-folder-item.drag-over');
                folders.forEach(el => el.classList.remove('drag-over'));
            });

            li.addEventListener('contextmenu', function (e) {
                e.preventDefault();
                const id = this.dataset.noteId;
                if (!id) return;
                openExplorerContextMenuForNote(id, e.clientX, e.clientY);
            });

            notesListEl.appendChild(li);
        });
    }

    function render() {
        renderNotesExplorer();
        renderTabs();
        renderEditors();
    }

    function createNewNote() {
        // Derive a simple sequential label (Note 1, Note 2, ...)
        const baseIndex = notes.length + 1;
        const title = 'Note ' + baseIndex;

        // Determine folder based on current explorer selection
        const folder = (currentFolderFilter === null) ? null : (currentFolderFilter || '');

        // Create a local-only note first. It will only be persisted to SQLite
        // once the user actually edits it (content/title), via saveNoteToServer.
        const note = createNoteObject(title, folder);

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
        showNoteEditorView();
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

                // "-" or "*" → bullet list. Respect which bullet the user typed
                // and avoid inserting a second '-' when the line currently only
                // contains the marker.
                if (/^[-*]$/.test(rawPrefix)) {
                    e.preventDefault();
                    applyLinePrefix(editor, rawPrefix + ' ');
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
                    const stripped = line.replace(/^([#]+\s|[-*]\s?|\d+\.\s?|\[ \]\s)/, '');
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

        const stripped = line.replace(/^([#]+\s|[-*]\s?|\d+\.\s?|\[ \]\s)/, '');
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

    function ensureExplorerContextMenu() {
        if (explorerContextMenuEl) return explorerContextMenuEl;
        explorerContextMenuEl = document.createElement('div');
        // Reuse same visual style as tab context menu
        explorerContextMenuEl.className = 'notes-tab-context-menu';
        explorerContextMenuEl.innerHTML = '';
        document.body.appendChild(explorerContextMenuEl);
        return explorerContextMenuEl;
    }

    function closeExplorerContextMenu() {
        if (!explorerContextMenuEl) return;
        explorerContextMenuEl.style.display = 'none';
        explorerContextTarget = null;
    }

    // Temporarily store a deleted note so Undo can restore it
    let pendingDeletedNote = null;
    let pendingDeletedOpenIndex = -1;
    let pendingDeletedWasActive = false;
    let pendingDeletedWasSecondary = false;

    function deleteNoteWithUndo(noteId) {
        if (!noteId) return;
        const idx = notes.findIndex(n => n.id === noteId);
        if (idx === -1) return;

        // Store note data for undo
        pendingDeletedNote = JSON.parse(JSON.stringify(notes[idx]));
        pendingDeletedOpenIndex = Array.isArray(openNoteIds) ? openNoteIds.indexOf(noteId) : -1;
        pendingDeletedWasActive = activeNoteId === noteId;
        pendingDeletedWasSecondary = secondaryNoteId === noteId;

        // Remove from notes array
        notes.splice(idx, 1);

        // Delete on server (fire and forget)
        try {
            fetch(`/api/notes/${encodeURIComponent(noteId)}`, { method: 'DELETE' });
        } catch (e) {
            console.error('Failed to delete note on server', e);
        }

        // Update local cache
        saveAllNotesToLocalStorage();

        // Remove from open tabs
        if (Array.isArray(openNoteIds)) {
            const openIdx = openNoteIds.indexOf(noteId);
            if (openIdx !== -1) openNoteIds.splice(openIdx, 1);
        }

        // Handle edge case: all notes deleted
        if (!notes.length) {
            const welcomeNote = createNoteObject('Welcome');
            notes.push(welcomeNote);
            openNoteIds = [welcomeNote.id];
            activeNoteId = welcomeNote.id;
            secondaryNoteId = null;
        } else {
            if (activeNoteId === noteId) {
                activeNoteId = (openNoteIds && openNoteIds[0]) || (notes[0] && notes[0].id) || null;
            }
            if (secondaryNoteId === noteId) {
                secondaryNoteId = null;
            }
        }

        render();
        saveNotes();

        // Show undo notification
        const deletedTitle = pendingDeletedNote.title || 'Untitled';
        if (window.showNotification) {
            window.showNotification(`Note "${deletedTitle}" deleted. Click to undo.`, 'info', {
                durationMs: 5000,
                onClick: undoDeleteNote
            });
        }
    }

    function undoDeleteNote() {
        if (!pendingDeletedNote) return;

        // Re-add the note
        notes.push(pendingDeletedNote);

        // Restore to open tabs at original position if possible
        if (pendingDeletedOpenIndex !== -1 && Array.isArray(openNoteIds)) {
            openNoteIds.splice(pendingDeletedOpenIndex, 0, pendingDeletedNote.id);
        } else if (Array.isArray(openNoteIds) && !openNoteIds.includes(pendingDeletedNote.id)) {
            openNoteIds.push(pendingDeletedNote.id);
        }

        // Restore active/secondary state
        if (pendingDeletedWasActive) {
            activeNoteId = pendingDeletedNote.id;
        }
        if (pendingDeletedWasSecondary) {
            secondaryNoteId = pendingDeletedNote.id;
        }

        // Sync to server (recreate the note)
        try {
            fetch('/api/notes', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(pendingDeletedNote)
            });
        } catch (e) {
            console.error('Failed to restore note on server', e);
        }

        const restoredTitle = pendingDeletedNote.title || 'Untitled';
        pendingDeletedNote = null;
        pendingDeletedOpenIndex = -1;
        pendingDeletedWasActive = false;
        pendingDeletedWasSecondary = false;

        // Update local cache and re-render
        saveAllNotesToLocalStorage();
        render();
        saveNotes();

        if (window.showNotification) {
            window.showNotification(`Note "${restoredTitle}" restored.`, 'success');
        }
    }

    function openTabContextMenu(noteId, clientX, clientY) {
        tabContextNoteId = noteId;
        const menu = ensureTabContextMenu();
        menu.innerHTML = '';

        const items = [
            { label: 'Open in split view', action: 'split' },
            { label: 'Rename note',        action: 'rename' },
            { label: 'Close note',         action: 'close' },
            { label: 'Delete note',        action: 'delete', className: 'notes-tab-context-item--danger' },
        ];

        items.forEach(item => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'notes-tab-context-item' + (item.className ? ' ' + item.className : '');
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
                } else if (item.action === 'delete') {
                    deleteNoteWithUndo(id);
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

    function openExplorerContextMenuForNote(noteId, clientX, clientY) {
        if (!noteId) return;
        explorerContextTarget = { type: 'note', noteId };
        const menu = ensureExplorerContextMenu();
        menu.innerHTML = '';

        const items = [
            { label: 'Open',          action: 'open' },
            { label: 'Rename',        action: 'rename' },
            { label: 'Delete',        action: 'delete', className: 'notes-tab-context-item--danger' },
            { label: 'Move to folder…', action: 'move' },
        ];

        items.forEach(item => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'notes-tab-context-item' + (item.className ? ' ' + item.className : '');
            btn.textContent = item.label;
            btn.dataset.action = item.action;

            btn.addEventListener('click', function () {
                const target = explorerContextTarget;
                if (!target || target.type !== 'note' || !target.noteId) {
                    closeExplorerContextMenu();
                    return;
                }
                const id = target.noteId;
                if (item.action === 'open') {
                    // Same behavior as clicking the note in explorer
                    if (!Array.isArray(openNoteIds)) openNoteIds = [];
                    if (!openNoteIds.includes(id)) openNoteIds.push(id);
                    activeNoteId = id;
                    saveNotes();
                    render();
                } else if (item.action === 'rename') {
                    renameActiveNote(id);
                } else if (item.action === 'delete') {
                    deleteNoteWithUndo(id);
                } else if (item.action === 'move') {
                    openFolderDialog({ mode: 'move-note', target: { noteId: id } });
                }
                closeExplorerContextMenu();
            });

            menu.appendChild(btn);
        });

        // Position near cursor
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

    function openExplorerContextMenuForFolder(folderKey, clientX, clientY) {
        // Only allow context menu for real named folders (skip All/Unsorted)
        if (!folderKey || !String(folderKey).trim()) {
            return;
        }
        const folderName = String(folderKey).trim();
        explorerContextTarget = { type: 'folder', folderKey: folderName };
        const menu = ensureExplorerContextMenu();
        menu.innerHTML = '';

        const items = [
            { label: 'Rename folder',                     action: 'rename-folder' },
            { label: 'Delete folder (keep notes in Unsorted)', action: 'delete-folder', className: 'notes-tab-context-item--danger' },
        ];

        items.forEach(item => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'notes-tab-context-item' + (item.className ? ' ' + item.className : '');
            btn.textContent = item.label;
            btn.dataset.action = item.action;

            btn.addEventListener('click', function () {
                const target = explorerContextTarget;
                if (!target || target.type !== 'folder' || !target.folderKey) {
                    closeExplorerContextMenu();
                    return;
                }
                const oldName = target.folderKey;

                if (item.action === 'rename-folder') {
                    openFolderDialog({ mode: 'rename-folder', target: { folderKey: oldName } });
                    closeExplorerContextMenu();
                    return;
                } else if (item.action === 'delete-folder') {
                    // Move notes to Unsorted (folder = null)
                    notes.forEach(n => {
                        if (!n || typeof n !== 'object') return;
                        if ((n.folder || '') === oldName) {
                            n.folder = null;
                            n.updated_at = new Date().toLocaleString();
                            saveNoteToServer(n);
                        }
                    });
                    if (virtualFolders.has(oldName)) {
                        virtualFolders.delete(oldName);
                        saveVirtualFolders();
                    }
                    currentFolderFilter = null;
                    render();
                }

                closeExplorerContextMenu();
            });

            menu.appendChild(btn);
        });

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

    async function importNoteFromImage() {
        try {
            const fileInput = document.createElement('input');
            fileInput.type = 'file';
            fileInput.accept = 'image/*';
            fileInput.style.display = 'none';

            fileInput.addEventListener('change', async function handleFileChange() {
                try {
                    const file = fileInput.files && fileInput.files[0];
                    if (!file) {
                        return;
                    }

                    const formData = new FormData();
                    formData.append('file', file);

                    let response;
                    try {
                        response = await fetch('/api/notes/ocr-extract', {
                            method: 'POST',
                            body: formData
                        });
                    } catch (err) {
                        console.error('OCR request failed', err);
                        if (window.showNotification) {
                            window.showNotification('Failed to contact OCR service. Please try again.', 'error');
                        }
                        return;
                    }

                    let data = null;
                    try {
                        data = await response.json();
                    } catch (err) {
                        console.error('Failed to parse OCR response JSON', err);
                    }

                    if (!response.ok || !data || data.success !== true) {
                        const message = (data && data.error) || 'Failed to extract text from image.';
                        console.error('OCR response error', response.status, message, data);
                        if (window.showNotification) {
                            window.showNotification(message, 'error');
                        }
                        return;
                    }

                    const rawText = typeof data.text === 'string' ? data.text : '';
                    const normalizedText = rawText.trim();
                    if (!normalizedText) {
                        if (window.showNotification) {
                            window.showNotification('No text could be extracted from the image.', 'warning');
                        }
                        return;
                    }

                    const lines = normalizedText.split('\n').map(l => l.trim());
                    const firstNonEmpty = lines.find(l => l.length > 0) || 'Imported note';
                    const title = firstNonEmpty.slice(0, 80);

                    let folder = null;
                    if (currentFolderFilter && typeof currentFolderFilter === 'string' && currentFolderFilter.trim().length > 0) {
                        folder = currentFolderFilter;
                    } else {
                        folder = null; // All/Unsorted both map to null folder in backend
                    }

                    let createdNote = null;
                    try {
                        createdNote = await createNoteOnServer(title, normalizedText, folder);
                    } catch (err) {
                        console.error('Failed to create note from OCR text', err);
                        if (window.showNotification) {
                            window.showNotification('Failed to create note from OCR text.', 'error');
                        }
                        return;
                    }

                    if (!createdNote) {
                        if (window.showNotification) {
                            window.showNotification('Failed to create note from OCR text.', 'error');
                        }
                        return;
                    }

                    ensureNoteHasSplitFields(createdNote);
                    notes.unshift(createdNote);

                    // Open the new note in the primary editor
                    openNoteIds = openNoteIds.filter(id => id !== createdNote.id);
                    openNoteIds.unshift(createdNote.id);
                    activeNoteId = createdNote.id;

                    saveStateToStorage();
                    render();

                    if (window.showNotification) {
                        window.showNotification('Note imported from image', 'success');
                    }
                } finally {
                    try {
                        if (fileInput && fileInput.parentNode) {
                            fileInput.parentNode.removeChild(fileInput);
                        }
                    } catch (e) {
                        // no-op
                    }
                }
            }, { once: true });

            document.body.appendChild(fileInput);
            try {
                fileInput.click();
            } catch (err) {
                console.error('Failed to open file picker for OCR import', err);
                if (window.showNotification) {
                    window.showNotification('Could not open file picker for image import.', 'error');
                }
            }
        } catch (err) {
            console.error('Unexpected error in importNoteFromImage', err);
            if (window.showNotification) {
                window.showNotification('Failed to import note from image.', 'error');
            }
        }
    }

    function attachEventHandlers() {
        const viewListBtn = document.getElementById('notes-view-list-btn');
        const splitToggleBtn = document.getElementById('notes-split-toggle-btn');
        const addSelectionBtn = document.getElementById('notes-add-selection-task-btn');
        const newTabBtn = document.getElementById('notes-tab-new');
        const importImageBtn = document.getElementById('notes-import-image-btn');
        const quickAddBtn = document.getElementById('notes-quick-add-btn');
        const addFolderBtn = document.getElementById('notes-add-folder-btn');
        const primary = document.getElementById('notes-editor-primary');
        const secondary = document.getElementById('notes-editor-secondary');

        const filterInput = document.getElementById('notes-explorer-filter');
        const sortSelect = document.getElementById('notes-explorer-sort');
        const folderDialogClose = document.getElementById('notes-folder-dialog-close');
        const folderDialogCancel = document.getElementById('notes-folder-dialog-cancel');
        const folderDialogApply = document.getElementById('notes-folder-dialog-apply');

        if (viewListBtn) {
            // "View all notes" brings you back to the dashboard view.
            viewListBtn.addEventListener('click', function () {
                showNotesDashboard();
            });
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
        if (importImageBtn) {
            importImageBtn.addEventListener('click', importNoteFromImage);
        }
        if (filterInput) {
            filterInput.addEventListener('input', function () {
                explorerFilterText = this.value || '';
                renderNotesExplorer();
            });
        }
        if (sortSelect) {
            sortSelect.addEventListener('change', function () {
                const val = (this.value || '').toLowerCase();
                explorerSortMode = (val === 'title' || val === 'created') ? val : 'updated';
                renderNotesExplorer();
            });
        }

        if (folderDialogClose) {
            folderDialogClose.addEventListener('click', closeFolderDialog);
        }
        if (folderDialogCancel) {
            folderDialogCancel.addEventListener('click', closeFolderDialog);
        }
        if (folderDialogApply) {
            folderDialogApply.addEventListener('click', applyFolderDialog);
        }
        if (newTabBtn) {
            newTabBtn.addEventListener('click', createNewNote);
        }
        if (quickAddBtn) {
            quickAddBtn.addEventListener('click', createNewNote);
        }
        if (addFolderBtn) {
            addFolderBtn.addEventListener('click', function () {
                openFolderDialog({ mode: 'new-folder' });
            });
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

        // Close command and context menus on outside click
        if (!window.__notesCommandMenuOutsideClick) {
            document.addEventListener('click', function (e) {
                if (commandMenuEl && commandMenuEl.style.display === 'flex' && !commandMenuEl.contains(e.target)) {
                    closeCommandMenu();
                    commandMenuEditor = null;
                }
                if (tabContextMenuEl && tabContextMenuEl.style.display === 'flex' && !tabContextMenuEl.contains(e.target)) {
                    closeTabContextMenu();
                }
                if (explorerContextMenuEl && explorerContextMenuEl.style.display === 'flex' && !explorerContextMenuEl.contains(e.target)) {
                    closeExplorerContextMenu();
                }
            });
            window.__notesCommandMenuOutsideClick = true;
        }
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
        saveNotes();
    }

    // Folder dialog state
    let folderDialogMode = null; // 'move-note' | 'rename-folder' | 'new-folder'
    let folderDialogTarget = null; // { noteId? , folderKey? }

    function getAllFolderNames() {
        const names = new Set();
        const summary = getFoldersSummary();
        summary.forEach((_, key) => {
            if (key && key.trim().length > 0) {
                names.add(key.trim());
            }
        });
        if (virtualFolders && virtualFolders.size) {
            for (const name of virtualFolders) {
                if (name && !names.has(name)) {
                    names.add(name);
                }
            }
        }
        return Array.from(names).sort((a, b) => a.localeCompare(b));
    }

    function openFolderDialog(config) {
        folderDialogMode = config && config.mode ? config.mode : null;
        folderDialogTarget = config && config.target ? config.target : null;

        const modal = document.getElementById('notes-folder-dialog-modal');
        if (!modal) return;
        const titleEl = document.getElementById('notes-folder-dialog-title');
        const selectEl = document.getElementById('notes-folder-dialog-select');
        const inputEl = document.getElementById('notes-folder-dialog-name');

        if (!selectEl || !inputEl || !titleEl) return;

        if (folderDialogMode === 'move-note') {
            titleEl.textContent = 'Move note to folder';
        } else if (folderDialogMode === 'rename-folder') {
            titleEl.textContent = 'Rename folder';
        } else if (folderDialogMode === 'new-folder') {
            titleEl.textContent = 'New folder';
        } else {
            titleEl.textContent = 'Folder';
        }

        // Populate existing folders
        const names = getAllFolderNames();
        selectEl.innerHTML = '';
        const blankOpt = document.createElement('option');
        blankOpt.value = '';
        blankOpt.textContent = 'Unsorted';
        selectEl.appendChild(blankOpt);

        names.forEach(name => {
            const opt = document.createElement('option');
            opt.value = name;
            opt.textContent = name;
            selectEl.appendChild(opt);
        });

        // Hide existing-folder select when creating a brand new folder; show it otherwise.
        const selectGroup = selectEl.parentElement;
        if (selectGroup) {
            if (folderDialogMode === 'new-folder') {
                selectGroup.style.display = 'none';
            } else {
                selectGroup.style.display = '';
            }
        }

        // Default selection / input value based on context
        inputEl.value = '';
        if (folderDialogMode === 'move-note' && folderDialogTarget && folderDialogTarget.noteId) {
            const note = notes.find(n => n.id === folderDialogTarget.noteId);
            const currentFolder = note && note.folder ? String(note.folder) : '';
            selectEl.value = currentFolder;
            inputEl.value = currentFolder;
        } else if (folderDialogMode === 'rename-folder' && folderDialogTarget && folderDialogTarget.folderKey) {
            const currentFolder = String(folderDialogTarget.folderKey);
            selectEl.value = currentFolder;
            inputEl.value = currentFolder;
        } else {
            selectEl.value = '';
        }

        modal.classList.add('active');
        modal.style.display = 'flex';
        try { inputEl.focus(); } catch (e) { /* no-op */ }
    }

    function closeFolderDialog() {
        const modal = document.getElementById('notes-folder-dialog-modal');
        if (modal) {
            modal.classList.remove('active');
            modal.style.display = 'none';
        }
        folderDialogMode = null;
        folderDialogTarget = null;
    }

    function applyFolderDialog() {
        const selectEl = document.getElementById('notes-folder-dialog-select');
        const inputEl = document.getElementById('notes-folder-dialog-name');
        if (!selectEl || !inputEl) {
            closeFolderDialog();
            return;
        }
        const fromSelect = selectEl.value || '';
        const fromInput = (inputEl.value || '').trim();
        const effectiveName = fromInput || fromSelect;
        const folderValue = effectiveName ? effectiveName : null;

        if (folderDialogMode === 'move-note' && folderDialogTarget && folderDialogTarget.noteId) {
            const note = notes.find(n => n.id === folderDialogTarget.noteId);
            if (note) {
                note.folder = folderValue;
                note.updated_at = new Date().toLocaleString();
                saveNoteToServer(note);
                currentFolderFilter = folderValue;
            }
        } else if (folderDialogMode === 'rename-folder' && folderDialogTarget && folderDialogTarget.folderKey) {
            const oldName = String(folderDialogTarget.folderKey);
            const newName = effectiveName && effectiveName.trim();
            if (newName && newName.length > 0) {
                notes.forEach(n => {
                    if (!n || typeof n !== 'object') return;
                    if ((n.folder || '') === oldName) {
                        n.folder = newName;
                        n.updated_at = new Date().toLocaleString();
                        saveNoteToServer(n);
                    }
                });
                if (virtualFolders.has(oldName)) {
                    virtualFolders.delete(oldName);
                }
                virtualFolders.add(newName);
                saveVirtualFolders();
                currentFolderFilter = newName;
            }
        } else if (folderDialogMode === 'new-folder') {
            const name = effectiveName && effectiveName.trim();
            if (name && name.length > 0) {
                currentFolderFilter = name;
                virtualFolders.add(name);
                saveVirtualFolders();
            }
        }

        closeFolderDialog();
        render();
    }

    function cleanupCacheOnStartup() {
        try {
            if (!window.localStorage) return;
            const over = window.localStorage.getItem('shakshuka_notes_cache_over_budget');
            if (over === '1') {
                window.localStorage.removeItem(STORAGE_KEY);
                markCacheOverBudget(false);
                debugLog('Cleared oversized notes cache on startup');
            }
        } catch (e) {
            // best-effort only
        }
    }

    function init() {
        const page = document.getElementById('notes-page');
        if (!page) return;
        cleanupCacheOnStartup();
        loadVirtualFolders();
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

    // Keyboard shortcuts for Notes page
    document.addEventListener('keydown', function (e) {
        const notesPage = document.getElementById('notes-page');
        if (!notesPage || !notesPage.classList.contains('active')) return;

        const isMac = navigator.platform && /Mac/i.test(navigator.platform);
        const isMod = isMac ? e.metaKey : e.ctrlKey;

        if (isMod && !e.shiftKey && e.key === 'n') {
            // Ctrl+N / Cmd+N: new note
            e.preventDefault();
            createNewNote();
        } else if (isMod && e.shiftKey && e.key === 'N') {
            // Ctrl+Shift+N / Cmd+Shift+N: new folder
            e.preventDefault();
            openFolderDialog({ mode: 'new-folder' });
        }
    });
})();
