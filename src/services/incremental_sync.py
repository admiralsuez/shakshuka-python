"""
Incremental Sync Service - Only sync changed items
"""

from typing import Dict, List, Set, Any, Optional, Tuple
from datetime import datetime, timedelta
import json
import logging


logger = logging.getLogger(__name__)


class IncrementalSyncTracker:
    """Tracks which items have been synced to avoid redundant uploads"""
    
    def __init__(self, storage_key: str = 'incremental_sync_state'):
        """
        Args:
            storage_key: Key for persistent storage
        """
        self.storage_key = storage_key
        self.sync_state: Dict[str, Dict[str, Any]] = {}
    
    def load_sync_state(self, user_id: str) -> Dict[str, Any]:
        """Load sync state for user
        
        Args:
            user_id: User ID
        
        Returns:
            Sync state dict with synced items and timestamps
        """
        if user_id not in self.sync_state:
            self.sync_state[user_id] = {
                'synced_task_ids': set(),
                'synced_note_ids': set(),
                'last_sync_time': None,
                'task_hashes': {},  # task_id -> hash of last synced version
                'note_hashes': {},  # note_id -> hash of last synced version
            }
        return self.sync_state[user_id]
    
    def _hash_item(self, item: Dict[str, Any]) -> str:
        """Generate hash of item for change detection
        
        Args:
            item: Item dict
        
        Returns:
            Hash string
        """
        # Create hashable version (exclude timestamps and internal fields)
        hashable = {
            k: v for k, v in item.items()
            if k not in ['updated_at', 'created_at', 'synced_at']
        }
        try:
            return hash(json.dumps(hashable, sort_keys=True, default=str))
        except Exception:
            return hash(str(item))
    
    def get_changed_tasks(self, user_id: str, current_tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get only tasks that have changed since last sync
        
        Args:
            user_id: User ID
            current_tasks: Current list of all tasks
        
        Returns:
            List of changed tasks only
        """
        state = self.load_sync_state(user_id)
        changed_tasks = []
        
        for task in current_tasks:
            task_id = task.get('id')
            if not task_id:
                continue
            
            # New task (never synced)
            if task_id not in state['synced_task_ids']:
                changed_tasks.append(task)
                continue
            
            # Check if task has changed
            current_hash = self._hash_item(task)
            previous_hash = state['task_hashes'].get(task_id)
            
            if current_hash != previous_hash:
                changed_tasks.append(task)
        
        return changed_tasks
    
    def get_changed_notes(self, user_id: str, current_notes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get only notes that have changed since last sync
        
        Args:
            user_id: User ID
            current_notes: Current list of all notes
        
        Returns:
            List of changed notes only
        """
        state = self.load_sync_state(user_id)
        changed_notes = []
        
        for note in current_notes:
            note_id = note.get('id')
            if not note_id:
                continue
            
            # New note (never synced)
            if note_id not in state['synced_note_ids']:
                changed_notes.append(note)
                continue
            
            # Check if note has changed
            current_hash = self._hash_item(note)
            previous_hash = state['note_hashes'].get(note_id)
            
            if current_hash != previous_hash:
                changed_notes.append(note)
        
        return changed_notes
    
    def mark_tasks_synced(self, user_id: str, synced_tasks: List[Dict[str, Any]]) -> None:
        """Mark tasks as synced
        
        Args:
            user_id: User ID
            synced_tasks: List of synced tasks
        """
        state = self.load_sync_state(user_id)
        
        for task in synced_tasks:
            task_id = task.get('id')
            if task_id:
                state['synced_task_ids'].add(task_id)
                state['task_hashes'][task_id] = self._hash_item(task)
        
        state['last_sync_time'] = datetime.now().isoformat()
        logger.info(f"Marked {len(synced_tasks)} tasks as synced for user {user_id}")
    
    def mark_notes_synced(self, user_id: str, synced_notes: List[Dict[str, Any]]) -> None:
        """Mark notes as synced
        
        Args:
            user_id: User ID
            synced_notes: List of synced notes
        """
        state = self.load_sync_state(user_id)
        
        for note in synced_notes:
            note_id = note.get('id')
            if note_id:
                state['synced_note_ids'].add(note_id)
                state['note_hashes'][note_id] = self._hash_item(note)
        
        state['last_sync_time'] = datetime.now().isoformat()
        logger.info(f"Marked {len(synced_notes)} notes as synced for user {user_id}")
    
    def get_sync_stats(self, user_id: str) -> Dict[str, Any]:
        """Get sync statistics for user
        
        Args:
            user_id: User ID
        
        Returns:
            Stats dict
        """
        state = self.load_sync_state(user_id)
        return {
            'synced_tasks': len(state['synced_task_ids']),
            'synced_notes': len(state['synced_note_ids']),
            'last_sync_time': state['last_sync_time'],
        }
    
    def reset_sync_state(self, user_id: str) -> None:
        """Reset sync state for user (full sync on next request)
        
        Args:
            user_id: User ID
        """
        if user_id in self.sync_state:
            del self.sync_state[user_id]
        logger.info(f"Reset sync state for user {user_id}")


# Global tracker instance
_tracker = IncrementalSyncTracker()


def get_tracker() -> IncrementalSyncTracker:
    """Get global sync tracker instance"""
    return _tracker


def calculate_sync_savings(total_items: int, changed_items: int) -> Dict[str, Any]:
    """Calculate bandwidth savings from incremental sync
    
    Args:
        total_items: Total number of items
        changed_items: Number of changed items
    
    Returns:
        Savings stats
    """
    if total_items == 0:
        return {'reduction': 0, 'items_skipped': 0}
    
    reduction = ((total_items - changed_items) / total_items) * 100
    return {
        'reduction': round(reduction, 1),
        'items_skipped': total_items - changed_items,
        'items_synced': changed_items,
    }
