"""
Note repository for note CRUD and version control operations.
Extracted from sqlite_data_manager.py for modularity and testing.
"""

import logging
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.exceptions import DatabaseError


logger = logging.getLogger(__name__)


class NoteRepository:
    """
    Repository for note operations.
    Handles creation, updates, deletion, and version history of notes.
    """

    def __init__(self, get_connection, ensure_user_exists, logger=None):
        """
        Initialize repository with database connection.
        
        Args:
            get_connection: Function to get a database connection
            ensure_user_exists: Function to ensure user exists
            logger: Logger instance (optional)
        """
        self.get_connection = get_connection
        self.ensure_user_exists = ensure_user_exists
        self.logger = logger or globals()["logger"]

    def load_notes_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Load non-trashed notes for a specific user from database."""
        try:
            self.ensure_user_exists(user_id)
            with self.get_connection() as conn:
                cursor = conn.execute(
                    """SELECT * FROM notes
                       WHERE user_id = ? AND (deleted_at IS NULL OR deleted_at = '')
                       ORDER BY updated_at DESC""",
                    (user_id,),
                )
                rows = cursor.fetchall()
                return [self._row_to_note_dict(row) for row in rows]
        except Exception as e:
            self.logger.exception("Error loading notes for user %s", user_id)
            raise DatabaseError(
                message=f"Error loading notes for user {user_id}", cause=e
            )

    def load_trashed_notes_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Load soft-deleted (trashed) notes for a user."""
        try:
            self.ensure_user_exists(user_id)
            with self.get_connection() as conn:
                cursor = conn.execute(
                    """SELECT * FROM notes
                       WHERE user_id = ? AND deleted_at IS NOT NULL AND deleted_at != ''
                       ORDER BY deleted_at DESC""",
                    (user_id,),
                )
                return [self._row_to_note_dict(row) for row in cursor.fetchall()]
        except Exception as e:
            self.logger.exception("Error loading trashed notes for user %s", user_id)
            raise DatabaseError(
                message=f"Error loading trashed notes for user {user_id}", cause=e
            )

    def create_note_for_user(
        self, user_id: str, note_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Create a single note for a user.

        Supports optional pinned/archived flags. These are stored as
        INTEGER 0/1 in SQLite but exposed as booleans in the returned dict.
        """
        try:
            self.ensure_user_exists(user_id)
            if "id" not in note_data:
                note_data["id"] = str(uuid.uuid4())
            
            title = (note_data.get("title") or "").strip() or "Untitled"
            content = note_data.get("content", "")
            folder_raw = note_data.get("folder")
            folder = (folder_raw or "").strip() if isinstance(folder_raw, str) else None
            if folder == "":
                folder = None
            
            pinned_flag = 1 if bool(note_data.get("pinned")) else 0
            archived_flag = 1 if bool(note_data.get("archived")) else 0
            now = datetime.now().isoformat()
            
            with self.get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")
                try:
                    # Newer schema with pinned/archived columns.
                    conn.execute(
                        """INSERT INTO notes (id, user_id, title, content, folder, pinned, archived, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            note_data["id"],
                            user_id,
                            title,
                            content,
                            folder,
                            pinned_flag,
                            archived_flag,
                            now,
                            now,
                        ),
                    )
                except sqlite3.OperationalError:
                    # Backward-compatible fallback for older schemas
                    conn.execute(
                        """INSERT INTO notes (id, user_id, title, content, folder, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (note_data["id"], user_id, title, content, folder, now, now),
                    )
                conn.commit()
            
            return {
                "id": note_data["id"],
                "title": title,
                "content": content,
                "folder": folder,
                "pinned": bool(pinned_flag),
                "archived": bool(archived_flag),
                "created_at": now,
                "updated_at": now,
            }
        except Exception as e:
            self.logger.error("Error creating note for user %s: %s", user_id, e)
            return None

    def update_note_for_user(
        self, user_id: str, note_id: str, note_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Update title/content/folder/pin/archive state of a note.

        Also snapshots the previous version into note_versions for history.
        """
        try:
            title = (note_data.get("title") or "").strip() or "Untitled"
            content = note_data.get("content", "")
            folder_raw = note_data.get("folder")
            folder = (folder_raw or "").strip() if isinstance(folder_raw, str) else None
            if folder == "":
                folder = None
            
            now = datetime.now().isoformat()
            
            with self.get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")
                cursor = conn.execute(
                    "SELECT * FROM notes WHERE id = ? AND user_id = ?",
                    (note_id, user_id),
                )
                existing = cursor.fetchone()
                if not existing:
                    conn.rollback()
                    return None

                keys = existing.keys()
                current_pinned = existing["pinned"] if "pinned" in keys else 0
                current_archived = existing["archived"] if "archived" in keys else 0
                pinned_flag = (
                    1 if bool(note_data.get("pinned", bool(current_pinned))) else 0
                )
                archived_flag = (
                    1 if bool(note_data.get("archived", bool(current_archived))) else 0
                )

                # Snapshot previous version for history (best-effort)
                try:
                    old_content = existing["content"] or ""
                    old_title = existing["title"] or ""
                    if old_content.strip() or old_title.strip():
                        conn.execute(
                            """INSERT INTO note_versions (note_id, user_id, title, content, saved_at)
                               VALUES (?, ?, ?, ?, ?)""",
                            (note_id, user_id, old_title, old_content, now),
                        )
                        # Cap versions at 50 per note
                        conn.execute(
                            """DELETE FROM note_versions WHERE id IN (
                                SELECT id FROM note_versions
                                WHERE note_id = ? AND user_id = ?
                                ORDER BY saved_at DESC
                                LIMIT -1 OFFSET 50
                            )""",
                            (note_id, user_id),
                        )
                except Exception:
                    self.logger.exception(
                        "Failed to snapshot note version for note %s", note_id
                    )

                try:
                    conn.execute(
                        """UPDATE notes
                           SET title = ?, content = ?, folder = ?, pinned = ?, archived = ?, updated_at = ?
                           WHERE id = ? AND user_id = ?""",
                        (
                            title,
                            content,
                            folder,
                            pinned_flag,
                            archived_flag,
                            now,
                            note_id,
                            user_id,
                        ),
                    )
                except sqlite3.OperationalError:
                    # Fallback for schemas without pinned/archived.
                    conn.execute(
                        """UPDATE notes
                           SET title = ?, content = ?, folder = ?, updated_at = ?
                           WHERE id = ? AND user_id = ?""",
                        (title, content, folder, now, note_id, user_id),
                    )
                conn.commit()
            
            return {
                "id": note_id,
                "title": title,
                "content": content,
                "folder": folder,
                "pinned": bool(pinned_flag),
                "archived": bool(archived_flag),
                "updated_at": now,
            }
        except Exception as e:
            self.logger.error(
                "Error updating note %s for user %s: %s", note_id, user_id, e
            )
            return None

    def delete_note_for_user(self, user_id: str, note_id: str) -> bool:
        """Soft-delete a note (move to trash) by setting deleted_at."""
        try:
            now = datetime.now().isoformat()
            with self.get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")
                try:
                    cursor = conn.execute(
                        """UPDATE notes SET deleted_at = ? WHERE id = ? AND user_id = ?
                           AND (deleted_at IS NULL OR deleted_at = '')""",
                        (now, note_id, user_id),
                    )
                    conn.commit()
                    return cursor.rowcount > 0
                except sqlite3.OperationalError:
                    # Fallback: schema may not have deleted_at yet; hard delete
                    conn.rollback()
                    conn.execute("BEGIN IMMEDIATE TRANSACTION")
                    cursor = conn.execute(
                        "DELETE FROM notes WHERE id = ? AND user_id = ?",
                        (note_id, user_id),
                    )
                    conn.commit()
                    return cursor.rowcount > 0
        except Exception as e:
            self.logger.error(
                "Error soft-deleting note %s for user %s: %s", note_id, user_id, e
            )
            return False

    def restore_note_for_user(self, user_id: str, note_id: str) -> bool:
        """Restore a trashed note by clearing deleted_at."""
        try:
            with self.get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")
                cursor = conn.execute(
                    """UPDATE notes SET deleted_at = NULL WHERE id = ? AND user_id = ?
                       AND deleted_at IS NOT NULL AND deleted_at != '' """,
                    (note_id, user_id),
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            self.logger.error(
                "Error restoring note %s for user %s: %s", note_id, user_id, e
            )
            return False

    def hard_delete_note_for_user(self, user_id: str, note_id: str) -> bool:
        """Permanently delete a note and its version history."""
        try:
            with self.get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")
                try:
                    conn.execute(
                        "DELETE FROM note_versions WHERE note_id = ? AND user_id = ?",
                        (note_id, user_id),
                    )
                except sqlite3.OperationalError:
                    pass  # note_versions table may not exist on very old schemas
                
                cursor = conn.execute(
                    "DELETE FROM notes WHERE id = ? AND user_id = ?",
                    (note_id, user_id),
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            self.logger.error(
                "Error hard-deleting note %s for user %s: %s", note_id, user_id, e
            )
            return False

    def load_note_versions(
        self, user_id: str, note_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Load version history for a note, newest first."""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    """SELECT id, title, content, saved_at FROM note_versions
                       WHERE note_id = ? AND user_id = ?
                       ORDER BY saved_at DESC LIMIT ?""",
                    (note_id, user_id, int(limit)),
                )
                return [
                    {
                        "id": row["id"],
                        "title": row["title"] or "",
                        "content": row["content"] or "",
                        "saved_at": row["saved_at"],
                    }
                    for row in cursor.fetchall()
                ]
        except Exception as e:
            self.logger.exception("Error loading note versions for note %s", note_id)
            raise DatabaseError(message="Error loading note versions", cause=e)

    def restore_note_version(
        self, user_id: str, note_id: str, version_id: int
    ) -> Optional[Dict[str, Any]]:
        """Restore a note to a previous version. Returns updated note dict or None."""
        try:
            with self.get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")
                ver_cur = conn.execute(
                    "SELECT title, content FROM note_versions WHERE id = ? AND note_id = ? AND user_id = ?",
                    (version_id, note_id, user_id),
                )
                ver_row = ver_cur.fetchone()
                if not ver_row:
                    conn.rollback()
                    return None

                # Snapshot current state before restoring
                cur_cur = conn.execute(
                    "SELECT title, content FROM notes WHERE id = ? AND user_id = ?",
                    (note_id, user_id),
                )
                cur_row = cur_cur.fetchone()
                now = datetime.now().isoformat()
                if cur_row:
                    conn.execute(
                        """INSERT INTO note_versions (note_id, user_id, title, content, saved_at)
                           VALUES (?, ?, ?, ?, ?)""",
                        (
                            note_id,
                            user_id,
                            cur_row["title"] or "",
                            cur_row["content"] or "",
                            now,
                        ),
                    )

                conn.execute(
                    """UPDATE notes SET title = ?, content = ?, updated_at = ?
                       WHERE id = ? AND user_id = ?""",
                    (ver_row["title"], ver_row["content"], now, note_id, user_id),
                )
                conn.commit()
            
            return {
                "id": note_id,
                "title": ver_row["title"] or "",
                "content": ver_row["content"] or "",
                "updated_at": now,
            }
        except Exception as e:
            self.logger.error(
                "Error restoring note version %s for note %s: %s",
                version_id,
                note_id,
                e,
            )
            return None

    def duplicate_note_for_user(
        self, user_id: str, note_id: str
    ) -> Optional[Dict[str, Any]]:
        """Duplicate an existing note with a new ID and '(Copy)' title suffix."""
        try:
            self.ensure_user_exists(user_id)
            with self.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM notes WHERE id = ? AND user_id = ?",
                    (note_id, user_id),
                )
                row = cursor.fetchone()
                if not row:
                    return None

            keys = row.keys()
            original_title = row["title"] or "Untitled"
            new_title = original_title + " (Copy)"
            new_data = {
                "title": new_title,
                "content": row["content"] or "",
                "folder": row["folder"] if "folder" in keys else None,
                "pinned": False,
                "archived": False,
            }
            return self.create_note_for_user(user_id, new_data)
        except Exception as e:
            self.logger.error(
                "Error duplicating note %s for user %s: %s", note_id, user_id, e
            )
            return None

    # Helper methods
    def _row_to_note_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert database row to note dict"""
        keys = row.keys()
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "title": row["title"] or "Untitled",
            "content": row["content"] or "",
            "folder": row["folder"] if "folder" in keys else None,
            "pinned": bool(row["pinned"] if "pinned" in keys else False),
            "archived": bool(row["archived"] if "archived" in keys else False),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "deleted_at": row["deleted_at"] if "deleted_at" in keys else None,
        }
