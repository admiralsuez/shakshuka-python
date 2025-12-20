# Frontend Asset Refactor Summary (JS/CSS Modularization)

## Goal
Reorganize frontend assets into clearer subfolders under `assets/static/js/` and `assets/static/css/` while keeping runtime behavior identical. This included updating all template references (`<script>`, `<link>`), CSS `@import` paths, and ensuring script load order remained correct.

## High-level results
- `assets/static/css/style.css` is now an **imports-only** entrypoint (no large inline blocks), preserving the original cascade order.
- JavaScript files were moved into subfolders (auth/core/utils/pages/app/etc.) and all template references were updated.
- `assets/templates/index.html` was updated to use the canonical scripts partial to prevent missing-global runtime errors.

## CSS changes
### New folder layout
CSS was organized into:
- `assets/static/css/core/`
- `assets/static/css/layout/`
- `assets/static/css/components/`
- `assets/static/css/pages/`
- `assets/static/css/features/`
- `assets/static/css/auth/`

### `style.css` behavior
- `assets/static/css/style.css` remains the main entrypoint.
- It now contains only `@import` rules that point into the subfolders above.
- Imports were ordered to match the prior monolithic cascade (theme/base first, then layout, then components/pages/features).

### Extracted CSS modules
Large blocks were extracted into dedicated files such as:
- Theme variables / dynamic colors → `core/theme.css`
- Layout shell → `layout/layout-shell.css`
- Desktop + responsive shell → `layout/desktop-layout.css`
- Planner + planner v2 → `pages/planner.css`, `pages/planner-v2.css`
- Modals → `components/modals.css`
- Task card design → `components/task-cards.css`
- Notes styles → `pages/notes.css`
- Misc UI / scrollbar / animations / strike visuals → `pages/ui-misc.css`
- Import modal → `features/import-modal.css`
- Quick date / social links / inline quick add → `features/quick-date.css`, `features/social-links.css`, `features/inline-quick-add.css`

## JS changes
### New folder layout
JavaScript was organized into:
- `assets/static/js/auth/`
- `assets/static/js/core/`
- `assets/static/js/utils/`
- `assets/static/js/pages/`
- `assets/static/js/app/`
- (and other existing feature/module folders already in use)

### Script load order (important)
`assets/templates/partials/scripts.html` is the canonical script loader and preserves the dependency order:
- utils first
- core state/init
- auth
- page modules
- app modules

This order matters because multiple files attach globals to `window` and assume earlier modules exist.

## Template updates
### Updated static references
Templates were updated so all `url_for('static', filename=...)` values match the new folder structure.

Key templates involved:
- `assets/templates/layout.html`
- `assets/templates/partials/scripts.html`
- `assets/templates/index.html`

### Runtime fix (missing globals)
`assets/templates/index.html` was updated to include `partials/scripts.html` rather than maintaining a partial/incomplete script list.

This fixed runtime errors like:
- `openLogsModal is not defined`
- `canStrikeTask is not defined`
- `loadUpdateSettings is not available` (previously caused warnings / order issues)

## Changelog update
- Added a new changelog entry at the top of `config/changelog.txt` describing the asset refactor and the script load order fix.

## Follow-up fixes (post-refactor)
### Notes “deleted” / replaced scenario
`assets/static/js/pages/notes.js` loads notes from `/api/notes` first. Previously, if the server returned an empty list, the frontend could create a default “Welcome” note and then save it to localStorage, overwriting cached notes.

Fix applied:
- If `/api/notes` returns empty but localStorage contains `shakshuka_notes_v1`, Notes now prefers localStorage instead of creating a default note.

### Notes API safety
`src/routes/notes_routes.py` previously returned `[]` in some failure cases (e.g., data manager not available). This could be misinterpreted as “no notes exist”.

Fix applied:
- On backend initialization failures, the notes route now returns `503`/`500` with an error payload, so the frontend falls back rather than overwriting.

### Changelog modal sizing + older versions visibility
- Increased changelog modal width to be significantly larger (responsive and capped).
- Increased expanded section max-height so long changelog sections don’t truncate (which can look like older versions are missing).

## Verification performed
- Searched the repo for old JS/CSS paths after moves and updated remaining references.
- Ran `python -m compileall .` successfully.

## Notes about remaining risk areas
- If you previously ran the app in a different mode (dev vs packaged) your SQLite DB location may differ. Notes may appear missing if the app is now pointing at a different DB file.
- If Notes titles show but content is empty, it may indicate that the DB currently being used contains rows with empty `content` (or you are viewing a different DB than before).
