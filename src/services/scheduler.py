"""
Scheduler Service - Handles scheduled tasks and daily resets

This module manages:
- Daily strike resets
- Scheduled task execution
- Missed reset detection and recovery
- Background scheduler thread
"""

import logging
import threading
import time
import schedule
from datetime import datetime
from typing import Optional

# These will be injected at runtime
_app_context = None
_data_manager_getter = None

logger = logging.getLogger(__name__)


def set_app_context(app_context):
    """Set the app context - call this during app initialization"""
    global _app_context
    _app_context = app_context


def set_data_manager_getter(getter_func):
    """Set function to get data manager - call this during app initialization"""
    global _data_manager_getter
    _data_manager_getter = getter_func


def _get_data_manager():
    """Get the data manager instance"""
    if _data_manager_getter:
        return _data_manager_getter()
    return _app_context.data_manager if _app_context else None


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
        # Parse the time string
        hour, minute = map(int, reset_time_str.split(':'))
        
        # Validate hour and minute ranges
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


def reset_daily_strikes_job():
    """
    Job to reset daily strikes and clean all scheduled tasks (local time).
    
    Behavior:
    - Tasks struck TODAY: Clear strike flag AND all scheduling -> move to available tasks
    - Tasks struck FOREVER (completed): Don't show in available tasks
    - All other scheduled tasks: Clear scheduling to return to available pool
    """
    try:
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
        
        # Load tasks for the user
        tasks = data_manager.load_tasks_for_user(user_id)
        if not tasks:
            logger.info("No tasks found for daily reset")
            return
        
        # 1) Clear today's strike flags and ALL scheduling for struck-today tasks
        reset_count = 0
        for task in tasks:
            if task.get('struck_today'):
                # Check if task was struck forever (completed)
                is_struck_forever = task.get('completed', False)
                
                # Clear the today's strike flag
                task['struck_today'] = False
                task['struck_date'] = None
                task['strike_report'] = None
                reset_count += 1
                
                # If struck TODAY (not forever), clear scheduling so it returns to available tasks
                if not is_struck_forever:
                    task['scheduled_hour'] = None
                    task['scheduled_minute'] = None
                    task['scheduled_date'] = None
                    task['scheduled_duration'] = None
                    logger.debug(f"Task '{task.get('title', 'Unknown')}' unscheduled after today's strike reset")
        
        # 2) Clear ALL remaining scheduled tasks (from any day, not just previous days)
        # This ensures the planner is clean at the start of each day
        unscheduled = 0
        for t in tasks:
            # Only unschedule if task is not completed (struck forever)
            is_completed = t.get('completed', False)
            has_schedule = t.get('scheduled_date') is not None
            
            if has_schedule and not is_completed:
                t['scheduled_hour'] = None
                t['scheduled_minute'] = None
                t['scheduled_date'] = None
                t['scheduled_duration'] = None
                unscheduled += 1
                logger.debug(f"Task '{t.get('title', 'Unknown')}' unscheduled during daily reset")
        
        if reset_count > 0 or unscheduled > 0:
            success = data_manager.save_tasks_for_user(user_id, tasks)
            if success:
                logger.info(f"Daily reset done: {reset_count} strikes cleared, {unscheduled} tasks unscheduled")
            else:
                logger.error("Failed to save tasks after daily reset")
        else:
            logger.info("Daily reset: no changes needed")
            
    except Exception as e:
        logger.error(f"Error in daily reset job: {e}")
        import traceback
        logger.error(f"Daily reset traceback: {traceback.format_exc()}")


def check_and_run_missed_reset(reset_time_str: str, verbose: bool = True):
    """
    Check if today's reset was missed and run it if needed (uses local time).
    
    Args:
        reset_time_str: Reset time in HH:MM format
        verbose: Whether to log verbose messages
    """
    try:
        # Validate and normalize reset time
        reset_time_str = _validate_and_normalize_reset_time(reset_time_str)
        reset_hour, reset_minute = map(int, reset_time_str.split(':'))
        
        # Use local time so it matches how the scheduler runs
        now = datetime.now()
        
        # Create datetime for today's reset time (local)
        today_reset_time = now.replace(hour=reset_hour, minute=reset_minute, second=0, microsecond=0)
        
        # If current time is past today's reset time and any task is still flagged struck_today, run reset
        if now > today_reset_time:
            user_id = _get_user_id()
            if not user_id:
                return
            
            data_manager = _get_data_manager()
            if not data_manager:
                return
            
            tasks = data_manager.load_tasks_for_user(user_id)
            if not tasks:
                return
            
            needs_reset = any(task.get('struck_today') for task in tasks)
            if needs_reset:
                logger.info(f"⏰ Missed reset detected! Current time {now.strftime('%H:%M')} is past reset time {reset_time_str}. Running reset now...")
                reset_daily_strikes_job()
            elif verbose:
                logger.debug("👍 No tasks flagged for today; reset not needed")
        elif verbose:
            logger.info(f"⏳ Reset time {reset_time_str} is still upcoming today (current: {now.strftime('%H:%M')})")
            
    except Exception as e:
        logger.error(f"Error checking for missed reset: {e}")


def setup_daily_reset():
    """
    Setup daily reset schedule with timezone awareness.
    """
    try:
        data_manager = _get_data_manager()
        if not data_manager:
            logger.warning("Data manager not available for daily reset setup")
            return
        
        # Get user ID for proper settings loading
        user_id = _get_user_id()
        settings = data_manager.load_settings(user_id) or {}
        reset_time = settings.get('daily_reset_time', '08:00')
        
        # Validate and normalize reset time
        reset_time = _validate_and_normalize_reset_time(reset_time)
        
        # Check if we've already passed today's reset time
        check_and_run_missed_reset(reset_time)
        
        # Clear any existing daily reset jobs
        schedule.clear('daily_reset')
        
        # Schedule the daily reset with proper timezone handling
        schedule.every().day.at(reset_time).do(reset_daily_strikes_job).tag('daily_reset')
        
        logger.info(f"✅ Daily reset scheduled for {reset_time} (user: {user_id})")
        
    except Exception as e:
        logger.error(f"Error setting up daily reset: {e}")


def scheduler_worker():
    """Robust background thread for scheduled tasks with timezone awareness."""
    logger.info("Scheduler worker started")
    last_missed_check = datetime.utcnow()
    
    while True:
        try:
            # Run pending scheduled jobs
            schedule.run_pending()
            
            # Periodically check for missed resets (every 15 minutes)
            now = datetime.utcnow()
            if (now - last_missed_check).total_seconds() >= 900:  # 15 minutes
                data_manager = _get_data_manager()
                if data_manager:
                    user_id = _get_user_id()
                    settings = data_manager.load_settings(user_id) or {}
                    reset_time = settings.get('daily_reset_time', '08:00')
                    check_and_run_missed_reset(reset_time, verbose=False)  # Quiet mode for intervals
                last_missed_check = now
            
            # Sleep for 60 seconds
            time.sleep(60)
            
        except Exception as e:
            logger.error(f"Scheduler worker error: {e}")
            # Wait a bit before retrying to prevent rapid error loops
            time.sleep(30)


def start_scheduler():
    """Start the scheduler background thread with proper error handling."""
    try:
        # Setup daily reset schedule
        setup_daily_reset()
        
        # Start scheduler thread
        scheduler_thread = threading.Thread(target=scheduler_worker, daemon=True, name="SchedulerWorker")
        scheduler_thread.start()
        
        logger.info("Scheduler thread started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")


# Deprecated: kept for backward compatibility
def validate_reset_time(reset_time_str: str) -> str:
    """Deprecated - use _validate_and_normalize_reset_time instead."""
    return _validate_and_normalize_reset_time(reset_time_str)
