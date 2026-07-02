"""Scheduler initialization service for Shakshuka.

Manages background scheduler thread setup and teardown.
Delegates to the core scheduler implementation in src.services.scheduler.
"""

import logging
from typing import Callable, Optional

from src.services import scheduler as scheduler_service

logger = logging.getLogger(__name__)


def start_scheduler(app_context: Optional[object] = None) -> None:
    """Start the scheduler background thread.
    
    Args:
        app_context: Optional application context. If provided, will be set
                    before starting the scheduler.
    """
    try:
        if app_context:
            scheduler_service.set_app_context(app_context)
            if hasattr(app_context, 'data_manager'):
                scheduler_service.set_data_manager_getter(
                    lambda: app_context.data_manager
                )
        
        scheduler_service.start_scheduler()
        logger.info("Scheduler thread started successfully")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")
        raise


def stop_scheduler(timeout: float = 10.0) -> None:
    """Stop the scheduler background thread gracefully.
    
    Args:
        timeout: Maximum time in seconds to wait for scheduler to stop
    """
    try:
        logger.info("Stopping scheduler thread...")
        scheduler_service.stop_scheduler(timeout=timeout)
        logger.info("Scheduler thread stopped successfully")
    except Exception as e:
        logger.error(f"Error stopping scheduler: {e}")
        raise


def is_scheduler_running() -> bool:
    """Check if scheduler is currently running.
    
    Returns:
        True if scheduler thread is active, False otherwise
    """
    try:
        return scheduler_service.is_scheduler_running()
    except Exception as e:
        logger.error(f"Error checking scheduler status: {e}")
        return False


def setup_daily_reset() -> None:
    """Setup or reschedule the daily reset job.
    
    Called when user changes their daily reset time via settings.
    """
    try:
        scheduler_service.setup_daily_reset()
        logger.info("Daily reset job reconfigured")
    except Exception as e:
        logger.error(f"Failed to setup daily reset: {e}")
        raise
