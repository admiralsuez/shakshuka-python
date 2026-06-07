"""
Scheduler Service - Handles scheduled tasks and daily resets

This module manages:
- Daily strike resets
- Scheduled task execution
- Missed reset detection and recovery
- Background scheduler thread
"""

import json
import logging
import os
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import schedule

from src.core.correlation import correlation_context
from src.exceptions import DatabaseError, ValidationError
from src.utils.paths import get_user_data_dir

logger = logging.getLogger(__name__)


def _job_correlation_id(job_name: str) -> str:
    # Keep it short (<=64 chars) and regex-safe.
    safe = ''.join(ch if (ch.isalnum() or ch in ('_', '-')) else '_' for ch in str(job_name or 'job'))
    safe = safe.strip('_-') or 'job'
    suffix = uuid.uuid4().hex[:12]
    base = f"job_{safe}_{suffix}"
    return base[:64]


def _run_job_with_correlation(job_name: str, fn, *args, **kwargs):
    cid = _job_correlation_id(job_name)
    with correlation_context(cid):
        return fn(*args, **kwargs)


@dataclass
class _SchedulerState:
    lock: threading.RLock = field(default_factory=threading.RLock)
    schedule_lock: threading.RLock = field(default_factory=threading.RLock)
    app_context: Any = None
    data_manager_getter: Any = None

    scheduler_thread: Optional[threading.Thread] = None
    stop_event: Optional[threading.Event] = None

    job_locks: Dict[str, threading.Lock] = field(default_factory=dict)
    last_run_markers: Dict[str, str] = field(default_factory=dict)
    markers_loaded: bool = False
    markers_path: Optional[str] = None

    last_known_reset_time: str = '08:00'


_STATE = _SchedulerState()


def set_app_context(app_context):
    """Set the app context - call this during app initialization"""
    with _STATE.lock:
        _STATE.app_context = app_context


def set_data_manager_getter(getter_func):
    """Set function to get data manager - call this during app initialization"""
    with _STATE.lock:
        _STATE.data_manager_getter = getter_func


def _get_data_manager():
    """Get the data manager instance"""
    with _STATE.lock:
        getter = _STATE.data_manager_getter
        app_context = _STATE.app_context

    if getter:
        return getter()
    return app_context.data_manager if app_context else None


def _get_job_lock(job_name: str) -> threading.Lock:
    with _STATE.lock:
        lock = _STATE.job_locks.get(job_name)
        if lock is None:
            lock = threading.Lock()
            _STATE.job_locks[job_name] = lock
        return lock


def _get_markers_path() -> str:
    with _STATE.lock:
        if _STATE.markers_path:
            return _STATE.markers_path

    try:
        base_dir = get_user_data_dir()
        os.makedirs(base_dir, exist_ok=True)
    except Exception:  # noqa: broad-except - Background job must handle all exceptions to prevent crash
        logger.exception("Failed to resolve user_data_dir for scheduler markers; falling back to temp dir")
        base_dir = tempfile.gettempdir()

    path = os.path.join(base_dir, 'scheduler_last_run.json')
    with _STATE.lock:
        _STATE.markers_path = path
    return path


def _load_markers() -> None:
    with _STATE.lock:
        if _STATE.markers_loaded:
            return

    path = _get_markers_path()
    markers: Dict[str, str] = {}
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                payload = json.load(f)
            if isinstance(payload, dict):
                for k, v in payload.items():
                    if isinstance(k, str) and isinstance(v, str):
                        markers[k] = v
    except Exception:  # noqa: broad-except - Background job must handle all exceptions to prevent crash
        logger.exception("Failed to load scheduler last-run markers")
        markers = {}

    with _STATE.lock:
        _STATE.last_run_markers = markers
        _STATE.markers_loaded = True


def _flush_markers() -> None:
    path = _get_markers_path()
    with _STATE.lock:
        payload = dict(_STATE.last_run_markers)

    tmp_path = f"{path}.tmp"
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f)
        os.replace(tmp_path, path)
    except Exception:  # noqa: broad-except - Background job must handle all exceptions to prevent crash
        logger.exception("Failed to persist scheduler last-run markers")
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:  # noqa: broad-except - Background job must handle all exceptions to prevent crash
            logger.exception("Failed to remove temp markers file")


def _read_last_run(job_name: str) -> Optional[datetime]:
    _load_markers()
    with _STATE.lock:
        raw = _STATE.last_run_markers.get(job_name)
    if raw is None:
        return None
    try:
        return _parse_iso_datetime(raw)
    except ValidationError:
        logger.exception("Invalid last-run marker for job %s: %r", job_name, raw)
        return None


def _write_last_run(job_name: str, dt: datetime) -> None:
    _load_markers()
    with _STATE.lock:
        _STATE.last_run_markers[job_name] = dt.isoformat()
    _flush_markers()


def _local_day(dt: datetime) -> str:
    try:
        if dt.tzinfo is not None:
            return dt.astimezone().strftime('%Y-%m-%d')
    except Exception:  # noqa: broad-except - Background job must handle all exceptions to prevent crash
        logger.exception("Failed to convert datetime to local day")
    return dt.strftime('%Y-%m-%d')


def _get_user_id():
    """Get the current user ID"""
    from src.constants import DEFAULT_USER_ID
    return DEFAULT_USER_ID


def _validate_and_normalize_reset_time(reset_time_str: str) -> str:
    """
    Validate and normalize reset time format.
    
    Used centrally for all reset time operations.
    
    Args:
        reset_time_str: Time string in HH:MM format
    
    Returns:
        Normalized time string in HH:MM format
    """
    try:
        hour, minute = map(int, reset_time_str.split(':'))

        if not (0 <= hour <= 23):
            logger.warning(f"Invalid hour in reset time: {hour}, using default")
            return "08:00"

        if not (0 <= minute <= 59):
            logger.warning(f"Invalid minute in reset time: {minute}, using default")
            return "08:00"

        return f"{hour:02d}:{minute:02d}"
    except (ValueError, AttributeError) as e:
        logger.warning(f"Invalid reset time format '{reset_time_str}': {e}, using default")
        return "08:00"


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except Exception as e:
        raise ValidationError(message="Invalid ISO datetime", details={'value': value}, cause=e)


def reset_daily_strikes_job(*, replay: bool = False, replay_reason: str = ''):
    """\
    Job to reset daily strikes and clean all scheduled tasks (local time).

    Behavior:
    - Tasks struck TODAY: Clear strike flag AND all scheduling -> move to available tasks
    - Tasks struck FOREVER (completed): Don't show in available tasks
    - All other scheduled tasks: Clear scheduling to return to available pool
    """
    lock = _get_job_lock('daily_reset')
    if not lock.acquire(blocking=False):
        logger.warning("Daily reset job is already running; skipping duplicate execution")
        return

    try:
        if replay:
            logger.info("Starting daily strikes reset job (replay=%s reason=%s)", replay, replay_reason)
        else:
            logger.info("Starting daily strikes reset job")
        
        data_manager = _get_data_manager()
        if not data_manager:
            logger.error("Data manager not available for daily reset")
            return
        
        # Use local time to align with user expectation and scheduler
        now = datetime.now()
        today_str_local = now.strftime('%Y-%m-%d')
        
        # Get user
        user_id = _get_user_id()
        if not user_id:
            logger.warning("No user ID available for daily reset")
            return
        
        # Determine reset-time window for idempotency
        reset_time_str = '08:00'
        settings: Dict[str, Any] = {}
        try:
            settings = data_manager.load_settings(user_id) or {}
            reset_time_str = settings.get('daily_reset_time', '08:00')
        except DatabaseError:
            logger.exception("Database error loading settings for daily reset")
        except Exception:  # noqa: broad-except - Background job must handle all exceptions to prevent crash
            logger.exception("Error loading settings for daily reset")
        reset_time_str = _validate_and_normalize_reset_time(reset_time_str)
        with _STATE.lock:
            _STATE.last_known_reset_time = reset_time_str
        reset_hour, reset_minute = map(int, reset_time_str.split(':'))
        today_reset_time = now.replace(hour=reset_hour, minute=reset_minute, second=0, microsecond=0)

        settings_last_reset: Optional[datetime] = None
        try:
            settings_last_reset = _parse_iso_datetime(settings.get('last_daily_reset_at'))
        except ValidationError:
            logger.exception("Invalid last_daily_reset_at in settings")
        file_last_reset = _read_last_run('daily_reset')
        last_reset_dt = max([d for d in (settings_last_reset, file_last_reset) if d is not None], default=None)
        if last_reset_dt is not None and _local_day(last_reset_dt) == today_str_local:
            logger.info(
                "Daily reset already ran (last_reset=%s); skipping",
                last_reset_dt.isoformat(),
            )
            return

        # Load tasks for the user
        try:
            tasks = data_manager.load_tasks_for_user(user_id)
        except DatabaseError:
            logger.exception("Database error loading tasks for daily reset")
            return
        if not tasks:
            logger.info("No tasks found for daily reset")
            return

        # Clean rolling daily_strikes history (keep only the most recent 7 days).
        try:
            try:
                today_dt = datetime.strptime(today_str_local, '%Y-%m-%d')
            except Exception:
                today_dt = now
            for t in tasks:
                daily_strikes = t.get('daily_strikes')
                if not isinstance(daily_strikes, dict) or not daily_strikes:
                    continue
                cleaned = {}
                for day_str, value in list(daily_strikes.items()):
                    try:
                        day_dt = datetime.strptime(str(day_str), '%Y-%m-%d')
                        if (today_dt - day_dt).days <= 7:
                            cleaned[day_str] = value
                    except Exception:  # noqa: broad-except
                        # Ignore malformed keys
                        continue
                t['daily_strikes'] = cleaned
        except Exception:  # noqa: broad-except - Background job must handle all exceptions to prevent crash
            logger.exception("Failed to clean daily_strikes history during daily reset")

        # Snapshot previous day's planner tasks before we clear scheduling/strike flags.
        try:
            previous_day = (now - timedelta(days=1)).strftime('%Y-%m-%d')
            snapshot_tasks = []
            for t in tasks:
                scheduled_date = t.get('scheduled_date')
                daily_strikes = t.get('daily_strikes') or {}
                strikes_for_day = 0
                try:
                    strikes_for_day = int(daily_strikes.get(previous_day, 0) or 0)
                except Exception:  # noqa: broad-except - Background job must handle all exceptions to prevent crash
                    strikes_for_day = 0

                completed_at = (t.get('completed_at') or '')
                completed_at_day = completed_at[:10] if isinstance(completed_at, str) else ''

                if scheduled_date == previous_day or strikes_for_day > 0 or completed_at_day == previous_day:
                    snapshot_tasks.append(t)

            if snapshot_tasks:
                data_manager.save_planner_history_snapshot(user_id, previous_day, snapshot_tasks)
        except Exception:  # noqa: broad-except - Background job must handle all exceptions to prevent crash
            logger.exception("Failed to capture planner history snapshot")
        
        # 1) Clear today's strike flags and ALL scheduling for struck-today tasks
        reset_count = 0
        reset_timestamp = datetime.now().isoformat()
        reset_tasks_for_log = []
        reset_task_ids = set()
        for task in tasks:
            if task.get('struck_today'):
                struck_date = task.get('struck_date')
                if replay and struck_date == today_str_local:
                    # Don't clear strikes that were legitimately made today after reset time.
                    continue
                # Check if task was struck forever (completed)
                is_struck_forever = task.get('completed', False)

                summary_task_for_log = None
                if not is_struck_forever:
                    summary_task_for_log = {
                        'id': task.get('id'),
                        'title': task.get('title'),
                        'project': task.get('project') or '',
                        'due_date': task.get('due_date'),
                        'scheduled_date': task.get('scheduled_date'),
                        'strike_count': int(task.get('strike_count') or 0),
                        'completed': bool(task.get('completed', False)),
                        'struck_forever': bool(task.get('struck_forever', False)),
                    }

                # If this task has a recurrence rule and was struck today (non-forever),
                # compute the next eligible day and use snoozed_until so the planner
                # and tasks page will hide it until that date.
                if not is_struck_forever:
                    try:
                        recurrence_type = (task.get('recurrence_type') or '').strip().lower()
                        recurrence_param = task.get('recurrence_param')
                        base_str = struck_date or today_str_local
                        next_date = None
                        if recurrence_type == 'every_n_days':
                            try:
                                n = int(recurrence_param or 0)
                            except Exception:  # noqa: broad-except
                                n = 0
                            if n and n > 1:
                                base_dt = datetime.strptime(base_str, '%Y-%m-%d')
                                next_date = base_dt + timedelta(days=n)
                        elif recurrence_type == 'weekly':
                            try:
                                target_wd = int(recurrence_param)
                            except Exception:  # noqa: broad-except
                                target_wd = None
                            if target_wd is not None and 0 <= target_wd <= 6:
                                base_dt = datetime.strptime(base_str, '%Y-%m-%d')
                                current_wd = base_dt.weekday()
                                # Always move to the *next* occurrence of target weekday.
                                days_ahead = (target_wd - current_wd) % 7
                                if days_ahead == 0:
                                    days_ahead = 7
                                next_date = base_dt + timedelta(days=days_ahead)
                        # For 'daily' or empty recurrence_type we rely on the
                        # existing behavior: the task re-enters the pool on the
                        # next day automatically after we clear struck_today.
                        if next_date is not None:
                            task['snoozed_until'] = next_date.strftime('%Y-%m-%d')
                    except Exception:  # noqa: broad-except
                        # Recurrence is best-effort; never break the reset job.
                        logger.exception("Failed to compute recurrence snooze for task during daily reset")
                
                # Clear the today's strike flag
                task['struck_today'] = False
                task['struck_date'] = None
                task['strike_report'] = None
                # Mark task as refreshed so the UI can surface a badge after reset
                task['refreshed_at'] = reset_timestamp
                reset_count += 1
                
                # If struck TODAY (not forever), clear scheduling so it returns to available tasks
                if not is_struck_forever:
                    task['scheduled_hour'] = None
                    task['scheduled_minute'] = None
                    task['scheduled_date'] = None
                    task['scheduled_duration'] = None
                    logger.debug(f"Task '{task.get('title', 'Unknown')}' unscheduled after today's strike reset")
                    if summary_task_for_log and summary_task_for_log.get('id'):
                        reset_tasks_for_log.append(summary_task_for_log)
                        reset_task_ids.add(str(summary_task_for_log['id']))
        
        # 2) Clear remaining scheduled tasks.
        # For missed-reset replay we must be conservative and avoid wiping today's schedule.
        unscheduled = 0
        for t in tasks:
            # Only unschedule if task is not completed (struck forever)
            is_completed = t.get('completed', False)
            is_struck_forever = t.get('struck_forever', False)
            has_schedule = t.get('scheduled_date') is not None
            scheduled_date = t.get('scheduled_date')
            
            if not has_schedule or is_completed or is_struck_forever:
                continue

            if replay and scheduled_date == today_str_local:
                continue

            if has_schedule and not is_completed:
                t['scheduled_hour'] = None
                t['scheduled_minute'] = None
                t['scheduled_date'] = None
                t['scheduled_duration'] = None
                unscheduled += 1
                logger.debug(f"Task '{t.get('title', 'Unknown')}' unscheduled during daily reset")

                # Include unscheduled tasks in the reset log, but avoid
                # duplicating entries already captured from the struck-today
                # pass.
                task_id = str(t.get('id') or '').strip()
                if task_id and task_id not in reset_task_ids:
                    reset_tasks_for_log.append({
                        'id': task_id,
                        'title': t.get('title'),
                        'project': t.get('project') or '',
                        'due_date': t.get('due_date'),
                        'scheduled_date': scheduled_date,
                        'strike_count': int(t.get('strike_count') or 0),
                        'completed': bool(t.get('completed', False)),
                        'struck_forever': bool(t.get('struck_forever', False)),
                    })
                    reset_task_ids.add(task_id)
        
        if reset_count > 0 or unscheduled > 0:
            success = data_manager.save_tasks_for_user(user_id, tasks)
            if success:
                logger.info(f"Daily reset done: {reset_count} strikes cleared, {unscheduled} tasks unscheduled")

                # Persist a compact daily reset log for the UI. This is best-effort
                # and should not cause the job to fail on its own.
                if reset_tasks_for_log:
                    try:
                        data_manager.save_daily_reset_log(
                            user_id=user_id,
                            reset_at_iso=reset_timestamp,
                            tasks=reset_tasks_for_log,
                            reset_reason='replay' if replay else 'scheduled',
                        )
                    except DatabaseError:
                        logger.exception("Failed to save daily reset log")
                    except Exception:  # noqa: broad-except - Background job must handle all exceptions to prevent crash
                        logger.exception("Failed to save daily reset log")

                # Persist last-run markers.
                _write_last_run('daily_reset', datetime.now())

                # Persist last_daily_reset_at and increment daily_reset_count so missed reset
                # detection is reliable even when the user changes daily_reset_time later.
                try:
                    latest_settings = data_manager.load_settings(user_id) or {}
                    latest_settings['last_daily_reset_at'] = datetime.now().isoformat()
                    # Increment daily reset counter for analytics
                    current_count = latest_settings.get('daily_reset_count', 0)
                    latest_settings['daily_reset_count'] = current_count + 1
                    data_manager.save_settings(user_id, latest_settings)
                    logger.info(f"Daily reset count incremented to {current_count + 1}")
                except DatabaseError:
                    logger.exception("Failed to persist last_daily_reset_at and reset count")
                except Exception:  # noqa: broad-except - Background job must handle all exceptions to prevent crash
                    logger.exception("Failed to persist last_daily_reset_at and reset count")
            else:
                logger.error("Failed to save tasks after daily reset")
        else:
            logger.info("Daily reset: no changes needed")
            
    except Exception:  # noqa: broad-except - Background job must handle all exceptions to prevent crash
        logger.exception("Error in daily reset job")
    finally:
        try:
            lock.release()
        except Exception:  # noqa: broad-except - Background job must handle all exceptions to prevent crash
            logger.exception("Failed to release daily reset job lock")


def check_and_run_missed_reset(reset_time_str: str, verbose: bool = True):
    """
    Check if today's reset was missed and run it if needed (uses local time).
    
    Args:
        reset_time_str: Reset time in HH:MM format
        verbose: Whether to log verbose messages
    """
    lock = _get_job_lock('missed_reset_check')
    if not lock.acquire(blocking=False):
        if verbose:
            logger.debug("Missed reset check already running; skipping")
        return

    try:
        # Validate and normalize reset time
        reset_time_str = _validate_and_normalize_reset_time(reset_time_str)
        with _STATE.lock:
            _STATE.last_known_reset_time = reset_time_str
        reset_hour, reset_minute = map(int, reset_time_str.split(':'))
        
        # Use local time so it matches how the scheduler runs
        now = datetime.now()
        today_str_local = now.strftime('%Y-%m-%d')
        
        # Create datetime for today's reset time (local)
        today_reset_time = now.replace(hour=reset_hour, minute=reset_minute, second=0, microsecond=0)
        
        # If current time is past today's reset time, only run a "missed" reset when we detect
        # leftover struck_today flags from *before* today (i.e., struck_date != today).
        #
        # This prevents a restart after reset time from clearing strikes that were legitimately
        # made today after the reset time.
        if now > today_reset_time:
            user_id = _get_user_id()
            if not user_id:
                return
            
            data_manager = _get_data_manager()
            if not data_manager:
                return

            # If we've already run a reset after today's reset time, don't run again.
            # This remains correct even if daily_reset_time changes later, because we compare
            # to the newly computed today_reset_time.
            try:
                settings = data_manager.load_settings(user_id) or {}
            except DatabaseError:
                logger.exception("Database error loading settings for missed reset check")
                return
            except Exception:  # noqa: broad-except - Background job must handle all exceptions to prevent crash
                logger.exception("Error loading settings for missed reset check")
                return

            settings_last_reset: Optional[datetime] = None
            try:
                settings_last_reset = _parse_iso_datetime(settings.get('last_daily_reset_at'))
            except ValidationError:
                logger.exception("Invalid last_daily_reset_at in settings")

            file_last_reset = _read_last_run('daily_reset')
            last_reset_dt = max([d for d in (settings_last_reset, file_last_reset) if d is not None], default=None)

            if last_reset_dt is not None and _local_day(last_reset_dt) == today_str_local:
                if verbose:
                    logger.debug(
                        f"👍 Missed reset check: last_daily_reset_at={settings.get('last_daily_reset_at')} is >= today's reset time; no reset needed"
                    )
                return
            
            try:
                tasks = data_manager.load_tasks_for_user(user_id)
            except DatabaseError:
                logger.exception("Database error loading tasks for missed reset check")
                return
            if not tasks:
                return

            # With last_daily_reset_at in place, the safe behavior is:
            # - if any task is still struck_today after reset time, we missed the reset.
            # This avoids relying on struck_date (which is date-only and can be missing).
            stale_struck_today = []
            for t in tasks:
                if not t.get('struck_today'):
                    continue
                if t.get('struck_date') == today_str_local:
                    continue
                stale_struck_today.append(t)

            needs_reset = len(stale_struck_today) > 0
            if needs_reset:
                logger.warning(
                    "Missed reset replay executing (now=%s reset_time=%s today_reset_time=%s stale_struck_today=%d last_reset=%s)",
                    now.isoformat(),
                    reset_time_str,
                    today_reset_time.isoformat(),
                    len(stale_struck_today),
                    last_reset_dt.isoformat() if last_reset_dt else None,
                )
                reset_daily_strikes_job(replay=True, replay_reason='missed_reset')
            elif verbose:
                logger.debug("👍 No tasks flagged for today; reset not needed")
        elif verbose:
            logger.info(f"⏳ Reset time {reset_time_str} is still upcoming today (current: {now.strftime('%H:%M')})")
            
    except Exception:  # noqa: broad-except - Background job must handle all exceptions to prevent crash
        logger.exception("Error checking for missed reset")
    finally:
        try:
            lock.release()
        except Exception:  # noqa: broad-except - Background job must handle all exceptions to prevent crash
            logger.exception("Failed to release missed reset check lock")


def setup_daily_reset():
    """\
    Setup daily reset schedule with timezone awareness.
    """
    try:
        data_manager = _get_data_manager()
        if not data_manager:
            logger.warning("Data manager not available for daily reset setup")
            return

        # Get user ID for proper settings loading
        user_id = _get_user_id()
        try:
            settings = data_manager.load_settings(user_id) or {}
        except DatabaseError:
            logger.exception("Database error loading settings for daily reset setup")
            return
        reset_time = settings.get('daily_reset_time', '08:00')

        # Validate and normalize reset time
        reset_time = _validate_and_normalize_reset_time(reset_time)
        with _STATE.lock:
            _STATE.last_known_reset_time = reset_time

        # Check if we've already passed today's reset time
        _run_job_with_correlation('missed_reset_check', check_and_run_missed_reset, reset_time)

        with _STATE.schedule_lock:
            schedule.clear('daily_reset')
            schedule.every().day.at(reset_time).do(_run_job_with_correlation, 'daily_reset', reset_daily_strikes_job).tag('daily_reset')

        logger.info(f"✅ Daily reset scheduled for {reset_time} (user: {user_id})")

    except Exception:  # noqa: broad-except - Background job must handle all exceptions to prevent crash
        logger.exception("Error setting up daily reset")


def _is_empty_note_payload(content: Any) -> bool:
    """Return True only for notes that are truly empty.

    We intentionally use a very strict definition so that only notes whose
    stored content is blank/whitespace are removed. Any non-string payload is
    treated as non-empty for safety.
    """
    if not isinstance(content, str):
        return False
    # Treat pure whitespace as empty; anything else is considered real content.
    return content.strip() == ''


def clean_empty_notes_job() -> None:
    """Weekly maintenance job: delete notes that have no contents.

    Safety rules:
    - Only operates on the current user.
    - Only deletes notes whose *stored* content is blank/whitespace.
    - Uses a last-run marker so it will not run more than once per week even if
      the process restarts frequently.
    """
    job_name = 'clean_empty_notes'
    lock = _get_job_lock(job_name)
    if not lock.acquire(blocking=False):
        logger.warning("Empty-notes cleaner is already running; skipping duplicate execution")
        return

    try:
        now = datetime.now()
        last_run = _read_last_run(job_name)
        if last_run is not None and (now - last_run) < timedelta(days=6):
            # Already ran recently; avoid overly aggressive cleanup.
            logger.info("Empty-notes cleaner ran recently (%s); skipping", last_run.isoformat())
            return

        data_manager = _get_data_manager()
        if not data_manager:
            logger.warning("Data manager not available for empty-notes cleaner")
            return

        user_id = _get_user_id()
        if not user_id:
            logger.warning("No user ID available for empty-notes cleaner")
            return

        try:
            notes = data_manager.load_notes_for_user(user_id) or []
        except DatabaseError:
            logger.exception("Database error loading notes for empty-notes cleaner")
            return
        except Exception:  # noqa: broad-except - Background job must handle all exceptions to prevent crash
            logger.exception("Unexpected error loading notes for empty-notes cleaner")
            return

        if not notes:
            logger.info("Empty-notes cleaner: no notes found; nothing to do")
            _write_last_run(job_name, now)
            return

        deleted = 0
        for note in notes:
            try:
                note_id = note.get('id')
                content = note.get('content', '')
                if not note_id or not _is_empty_note_payload(content):
                    continue
                if data_manager.delete_note_for_user(user_id, str(note_id)):
                    deleted += 1
            except Exception:  # noqa: broad-except - Keep cleaning defensive per-note
                logger.exception("Failed to evaluate/delete candidate empty note")
                continue

        logger.info("Empty-notes cleaner finished: deleted %d truly empty notes", deleted)
        _write_last_run(job_name, now)

        # Persist a tiny summary row into daily_reset_log so the UI notifications
        # indicator can show "note cleaner ran - cleaned N empty notes".
        try:
            data_manager = _get_data_manager()
            user_id = _get_user_id()
            if data_manager and user_id:
                summary = [{'id': None, 'title': 'notes_cleaner', 'project': '', 'due_date': None,
                           'scheduled_date': None, 'strike_count': 0, 'completed': False, 'struck_forever': False}]
                # We overload task_count and tasks_json with cleaner metadata.
                # save_daily_reset_log will cap and sanitize this payload.
                data_manager.save_daily_reset_log(
                    user_id=user_id,
                    reset_at_iso=now.isoformat(),
                    tasks=[{'id': 'notes_cleaner', 'title': 'Notes cleaner run', 'project': '', 'due_date': None,
                            'scheduled_date': None, 'strike_count': 0, 'completed': False, 'struck_forever': False,
                            'cleaned_count': int(deleted)}],
                    reset_reason='notes_cleaner',
                )
        except DatabaseError:
            logger.exception("Failed to save notes cleaner status into daily_reset_log")
        except Exception:  # noqa: broad-except
            logger.exception("Failed to persist notes cleaner status for notifications")

    except Exception:  # noqa: broad-except - Background job must handle all exceptions to prevent crash
        logger.exception("Error in empty-notes cleaner job")
    finally:
        try:
            lock.release()
        except Exception:  # noqa: broad-except - Background job must handle all exceptions to prevent crash
            logger.exception("Failed to release empty-notes cleaner job lock")


def export_all_notes_job() -> None:
    """Weekly job: export all notes as .md files into a timestamped subfolder.

    Rules:
    - Exports go to <user_data_dir>/notes_export/<timestamp>/
    - Each note becomes a .md file named after its title
    - Maximum 14 export folders; oldest deleted when limit exceeded
    - Last-run marker prevents running more than once per 6 days
    """
    job_name = 'export_all_notes'
    lock = _get_job_lock(job_name)
    if not lock.acquire(blocking=False):
        logger.warning("Notes export job already running; skipping")
        return

    try:
        now = datetime.now()
        last_run = _read_last_run(job_name)
        if last_run is not None and (now - last_run) < timedelta(days=6):
            logger.info("Notes export ran recently (%s); skipping", last_run.isoformat())
            return

        data_manager = _get_data_manager()
        if not data_manager:
            logger.warning("Data manager not available for notes export")
            return

        user_id = _get_user_id()
        if not user_id:
            return

        try:
            all_notes = data_manager.load_notes_for_user(user_id) or []
        except DatabaseError:
            logger.exception("Database error loading notes for export")
            return

        if not all_notes:
            logger.info("Notes export: no notes to export")
            _write_last_run(job_name, now)
            return

        export_root = os.path.join(get_user_data_dir(), 'notes_export')
        os.makedirs(export_root, exist_ok=True)

        timestamp = now.strftime('%Y%m%d_%H%M%S')
        export_dir = os.path.join(export_root, timestamp)
        os.makedirs(export_dir, exist_ok=True)

        exported = 0
        for note in all_notes:
            try:
                title = (note.get('title') or 'Untitled').strip()
                # Sanitize filename
                safe_title = ''.join(c if (c.isalnum() or c in (' ', '-', '_')) else '_' for c in title).strip()
                if not safe_title:
                    safe_title = 'note'
                # Avoid collisions
                fname = f"{safe_title}.md"
                fpath = os.path.join(export_dir, fname)
                counter = 1
                while os.path.exists(fpath):
                    fname = f"{safe_title}_{counter}.md"
                    fpath = os.path.join(export_dir, fname)
                    counter += 1

                content = note.get('content') or ''
                with open(fpath, 'w', encoding='utf-8') as f:
                    f.write(f"# {title}\n\n{content}")
                exported += 1
            except Exception:  # noqa: broad-except - per-note defensive
                logger.exception("Failed to export note %s", note.get('id'))
                continue

        logger.info("Notes export finished: %d notes exported to %s", exported, export_dir)
        _write_last_run(job_name, now)

        # Enforce max 14 exports — delete oldest
        try:
            _prune_notes_exports(export_root, max_exports=14)
        except Exception:  # noqa: broad-except - pruning is best-effort
            logger.exception("Failed to prune old notes exports")

    except Exception:  # noqa: broad-except - Background job must handle all exceptions to prevent crash
        logger.exception("Error in notes export job")
    finally:
        try:
            lock.release()
        except Exception:  # noqa: broad-except - Background job must handle all exceptions to prevent crash
            logger.exception("Failed to release notes export job lock")


def _prune_notes_exports(export_root: str, max_exports: int = 14) -> None:
    """Keep only the most recent `max_exports` export folders, delete the rest."""
    try:
        if not os.path.isdir(export_root):
            return
        folders = []
        for name in os.listdir(export_root):
            full = os.path.join(export_root, name)
            if os.path.isdir(full):
                folders.append((name, full))
        # Sort by name (timestamp-based, so lexicographic = chronological)
        folders.sort(key=lambda x: x[0])
        while len(folders) > max_exports:
            oldest_name, oldest_path = folders.pop(0)
            try:
                import shutil as _shutil
                _shutil.rmtree(oldest_path)
                logger.info("Pruned old notes export: %s", oldest_name)
            except Exception:  # noqa: broad-except
                logger.exception("Failed to delete old notes export folder: %s", oldest_path)
    except Exception:  # noqa: broad-except
        logger.exception("Failed to prune notes exports")


def get_notes_export_dir() -> str:
    """Return the path to the notes_export root folder."""
    return os.path.join(get_user_data_dir(), 'notes_export')


def _cleanup_mobile_sync_requests_job() -> None:
    """Clean up expired mobile sync requests (TTL: 5 minutes)."""
    try:
        data_manager = _get_data_manager()
        if not data_manager:
            logger.warning("Data manager not available for sync request cleanup")
            return
        
        count = data_manager.cleanup_expired_sync_requests()
        if count > 0:
            logger.info(f"Cleaned up {count} expired mobile sync requests")
    except Exception:  # noqa: broad-except
        logger.exception("Error cleaning up mobile sync requests")


def _cleanup_stale_submissions_job() -> None:
    """Auto-reject mobile inbox submissions older than 24 hours."""
    try:
        data_manager = _get_data_manager()
        if not data_manager:
            logger.warning("Data manager not available for submission cleanup")
            return
        
        count = data_manager.cleanup_stale_submissions(hours_old=24)
        if count > 0:
            logger.info(f"Auto-rejected {count} stale mobile inbox submissions")
    except Exception:  # noqa: broad-except
        logger.exception("Error cleaning up stale submissions")


def _setup_weekly_maintenance_jobs() -> None:
    """Register weekly background maintenance jobs (e.g., empty-notes cleaner, notes export)."""
    try:
        with _STATE.schedule_lock:
            schedule.clear('weekly_maintenance')
            # Run early Sunday morning local time; exact time is not critical
            # because we also enforce a last-run marker.
            schedule.every().sunday.at('03:30').do(
                _run_job_with_correlation,
                'clean_empty_notes',
                clean_empty_notes_job,
            ).tag('weekly_maintenance')
            # Notes export: run every Sunday at 04:00 (after cleaner)
            schedule.every().sunday.at('04:00').do(
                _run_job_with_correlation,
                'export_all_notes',
                export_all_notes_job,
            ).tag('weekly_maintenance')
            # Mobile sync cleanup: run every hour
            schedule.every().hour.do(
                _run_job_with_correlation,
                'cleanup_mobile_sync_requests',
                _cleanup_mobile_sync_requests_job,
            ).tag('weekly_maintenance')
            # Stale submission cleanup: run every 6 hours
            schedule.every(6).hours.do(
                _run_job_with_correlation,
                'cleanup_stale_submissions',
                _cleanup_stale_submissions_job,
            ).tag('weekly_maintenance')
        logger.info("✅ Weekly maintenance jobs scheduled (empty-notes cleaner, notes export, mobile sync cleanup)")
    except Exception:  # noqa: broad-except - Background job must handle all exceptions to prevent crash
        logger.exception("Error setting up weekly maintenance jobs")


def scheduler_worker(stop_event: threading.Event):
    """Robust background thread for scheduled tasks with timezone awareness."""
    logger.info("Scheduler worker started")
    last_missed_check = datetime.now()
    
    while not stop_event.is_set():
        try:
            # Run pending scheduled jobs
            with _STATE.schedule_lock:
                schedule.run_pending()
            
            # Periodically check for missed resets (every 15 minutes)
            now = datetime.now()
            if (now - last_missed_check).total_seconds() >= 900:  # 15 minutes
                data_manager = _get_data_manager()
                if data_manager:
                    user_id = _get_user_id()
                    try:
                        settings = data_manager.load_settings(user_id) or {}
                    except DatabaseError:
                        logger.exception("Database error loading settings for missed reset interval check")
                        settings = None
                    except Exception:  # noqa: broad-except - Background job must handle all exceptions to prevent crash
                        logger.exception("Error loading settings for missed reset interval check")
                        settings = None
                    if settings is None:
                        with _STATE.lock:
                            reset_time = _STATE.last_known_reset_time
                    else:
                        reset_time = settings.get('daily_reset_time', '08:00')
                    _run_job_with_correlation('missed_reset_check', check_and_run_missed_reset, reset_time, verbose=False)  # Quiet mode for intervals
                last_missed_check = now
            
            # Sleep for 60 seconds or until stop requested
            stop_event.wait(timeout=60)
            
        except Exception:  # noqa: broad-except - Background job must handle all exceptions to prevent crash
            logger.exception("Scheduler worker error")
            # Wait a bit before retrying to prevent rapid error loops
            stop_event.wait(timeout=30)


def start_scheduler():
    """Start the scheduler background thread with proper error handling."""
    try:
        with _STATE.lock:
            existing_thread = _STATE.scheduler_thread
        if existing_thread and existing_thread.is_alive():
            logger.info("Scheduler thread already running")
            return

        # Setup daily reset schedule
        setup_daily_reset()

        # Setup weekly maintenance jobs (e.g., empty-notes cleaner)
        _setup_weekly_maintenance_jobs()

        # Start scheduler thread
        stop_event = threading.Event()
        thread = threading.Thread(
            target=scheduler_worker,
            args=(stop_event,),
            daemon=True,
            name="SchedulerWorker",
        )
        with _STATE.lock:
            _STATE.stop_event = stop_event
            _STATE.scheduler_thread = thread

        thread.start()
        
        logger.info("Scheduler thread started successfully")
        
    except Exception:  # noqa: broad-except - Background job must handle all exceptions to prevent crash
        logger.exception("Failed to start scheduler")


def stop_scheduler(timeout: float = 10.0) -> None:
    """Stop the scheduler background thread gracefully if it is running."""
    try:
        with _STATE.lock:
            thread = _STATE.scheduler_thread
            stop_event = _STATE.stop_event

        if not thread or not thread.is_alive():
            return

        if stop_event is None:
            return

        stop_event.set()
        thread.join(timeout=timeout)
    finally:
        with _STATE.lock:
            _STATE.scheduler_thread = None
            _STATE.stop_event = None


class _SchedulerServiceCompat:
    def schedule_job(
        self,
        job_name: str,
        *,
        job_func,
        trigger: str,
        replace_existing: bool = False,
        **kwargs,
    ) -> None:
        if not job_name:
            raise ValidationError(message="Scheduler job name is required")
        if not callable(job_func):
            raise ValidationError(message="Scheduler job function must be callable")

        with _STATE.schedule_lock:
            if replace_existing:
                schedule.clear(job_name)

            if trigger == 'interval':
                hours = kwargs.get('hours')
                minutes = kwargs.get('minutes')
                seconds = kwargs.get('seconds')
                if hours:
                    job = schedule.every(int(hours)).hours
                elif minutes:
                    job = schedule.every(int(minutes)).minutes
                elif seconds:
                    job = schedule.every(int(seconds)).seconds
                else:
                    raise ValidationError(message="Interval scheduler jobs require hours, minutes, or seconds")
                job.do(_run_job_with_correlation, job_name, job_func).tag(job_name)
                return

            if trigger == 'cron':
                day_of_week = str(kwargs.get('day_of_week', '')).lower()
                hour = int(kwargs.get('hour', 0))
                minute = int(kwargs.get('minute', 0))
                at_time = f"{hour:02d}:{minute:02d}"
                weekdays = {
                    'mon': schedule.every().monday,
                    'monday': schedule.every().monday,
                    'tue': schedule.every().tuesday,
                    'tuesday': schedule.every().tuesday,
                    'wed': schedule.every().wednesday,
                    'wednesday': schedule.every().wednesday,
                    'thu': schedule.every().thursday,
                    'thursday': schedule.every().thursday,
                    'fri': schedule.every().friday,
                    'friday': schedule.every().friday,
                    'sat': schedule.every().saturday,
                    'saturday': schedule.every().saturday,
                    'sun': schedule.every().sunday,
                    'sunday': schedule.every().sunday,
                }
                if day_of_week:
                    scheduled_job = weekdays.get(day_of_week)
                    if scheduled_job is None:
                        raise ValidationError(message="Invalid cron day_of_week", details={'day_of_week': day_of_week})
                    scheduled_job.at(at_time).do(_run_job_with_correlation, job_name, job_func).tag(job_name)
                    return
                schedule.every().day.at(at_time).do(_run_job_with_correlation, job_name, job_func).tag(job_name)
                return

            raise ValidationError(message="Unsupported scheduler trigger", details={'trigger': trigger})


scheduler_service = _SchedulerServiceCompat()


# Deprecated: kept for backward compatibility
def validate_reset_time(reset_time_str: str) -> str:
    """Deprecated - use _validate_and_normalize_reset_time instead."""
    return _validate_and_normalize_reset_time(reset_time_str)
