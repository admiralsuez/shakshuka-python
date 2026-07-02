"""Route registration service for Shakshuka Flask application.

Centralizes blueprint registration and initialization to keep app.py clean.
"""

import logging
from typing import Callable, Any

from src.routes.task_routes import task_bp, init_task_routes
from src.routes.notes_routes import notes_bp, init_notes_routes
from src.routes.pin_routes import pin_bp, init_pin_routes
from src.routes.planner_routes import planner_bp, init_planner_routes
from src.routes.monitoring_routes import monitoring_bp, init_monitoring_routes
from src.routes.updates_routes import updates_bp, init_updates_routes
from src.routes.backups_routes import backups_bp, init_backups_routes
from src.routes.github_update_routes import github_update_bp, init_github_update_routes
from src.routes.mobile_routes import mobile_bp, init_mobile_routes
from src.routes.core_routes import core_bp, init_core_routes

logger = logging.getLogger(__name__)


def register_blueprints(
    app: Any,
    app_context: Any,
    get_user_id_func: Callable[[], str],
    ensure_data_manager_func: Callable[[], bool],
    sanitize_input_func: Callable[[Any], Any],
    validate_task_data_func: Callable[[Any], bool],
    rate_limit_decorator: Callable,
    root_dir: str,
    config: Any,
    get_app_version_func: Callable[[], str],
    setup_daily_reset_func: Callable,
    stop_system_tray_func: Callable,
    UpdateManager: type,
    get_user_data_dir_func: Callable[[], str],
    monitor: Any,
    security_manager: Any,
) -> None:
    """Register all Flask blueprints with their initializers.
    
    Args:
        app: Flask application instance
        app_context: Application context with data manager and other state
        get_user_id_func: Function to get current user ID
        ensure_data_manager_func: Function to ensure data manager is initialized
        sanitize_input_func: Function to sanitize input data
        validate_task_data_func: Function to validate task data
        rate_limit_decorator: Decorator for rate limiting
        root_dir: Root application directory
        config: Application configuration
        get_app_version_func: Function to get application version
        setup_daily_reset_func: Function to setup daily reset
        stop_system_tray_func: Function to stop system tray
        UpdateManager: UpdateManager class
        get_user_data_dir_func: Function to get user data directory
        monitor: Monitoring instance
        security_manager: Security manager instance
    """
    try:
        # Initialize and register core routes
        logger.info("Registering core routes...")
        init_core_routes(
            app_context=app_context,
            get_user_id_func=get_user_id_func,
            ensure_data_manager_func=ensure_data_manager_func,
            root_dir=root_dir,
            config=config,
            get_app_version_func=get_app_version_func,
            setup_daily_reset_func=setup_daily_reset_func,
            stop_system_tray_func=stop_system_tray_func,
        )
        app.register_blueprint(core_bp)
        logger.info("Core routes registered")

        # Initialize and register task routes
        logger.info("Registering task routes...")
        init_task_routes(
            app_context=app_context,
            get_user_id_func=get_user_id_func,
            ensure_data_manager_func=ensure_data_manager_func,
            sanitize_input_func=sanitize_input_func,
            validate_task_data_func=validate_task_data_func,
            rate_limit_decorator=rate_limit_decorator,
        )
        app.register_blueprint(task_bp)
        logger.info("Task routes registered")

        # Initialize and register notes routes
        logger.info("Registering notes routes...")
        init_notes_routes(
            app_context=app_context,
            get_user_id_func=get_user_id_func,
            ensure_data_manager_func=ensure_data_manager_func,
            sanitize_input_func=sanitize_input_func,
        )
        app.register_blueprint(notes_bp)
        logger.info("Notes routes registered")

        # Initialize and register PIN routes
        logger.info("Registering PIN routes...")
        init_pin_routes(app_context=app_context)
        app.register_blueprint(pin_bp)
        logger.info("PIN routes registered")

        # Initialize and register mobile routes
        logger.info("Registering mobile routes...")
        init_mobile_routes(
            app_context=app_context,
            get_user_id_func=get_user_id_func,
            ensure_data_manager_func=ensure_data_manager_func,
        )
        app.register_blueprint(mobile_bp)
        logger.info("Mobile routes registered")

        # Initialize and register planner routes
        logger.info("Registering planner routes...")
        init_planner_routes(
            app_context=app_context,
            get_user_id_func=get_user_id_func,
            ensure_data_manager_func=ensure_data_manager_func,
        )
        app.register_blueprint(planner_bp)
        logger.info("Planner routes registered")

        # Initialize and register monitoring routes
        logger.info("Registering monitoring routes...")
        init_monitoring_routes(
            monitor=monitor,
            security_manager=security_manager,
            get_user_id_func=get_user_id_func,
            get_user_data_dir_func=get_user_data_dir_func,
        )
        app.register_blueprint(monitoring_bp)
        logger.info("Monitoring routes registered")

        # Initialize and register updates routes
        logger.info("Registering updates routes...")
        init_updates_routes(
            app_context=app_context,
            update_manager_cls=UpdateManager,
            get_user_data_dir_func=get_user_data_dir_func,
        )
        app.register_blueprint(updates_bp)
        logger.info("Updates routes registered")

        # Initialize and register backups routes
        logger.info("Registering backups routes...")
        init_backups_routes(
            app_context=app_context,
            update_manager_cls=UpdateManager,
            get_user_data_dir_func=get_user_data_dir_func,
        )
        app.register_blueprint(backups_bp)
        logger.info("Backups routes registered")

        # Initialize and register GitHub update routes
        logger.info("Registering GitHub update routes...")
        init_github_update_routes(
            get_app_version_func=get_app_version_func,
            is_newer_version_func=_is_newer_version,
            repo_owner="vibin23",
            repo_name="shakshuka-python",
        )
        app.register_blueprint(github_update_bp)
        logger.info("GitHub update routes registered")

        logger.info("All blueprints registered successfully")

    except Exception as e:
        logger.exception("Failed to register blueprints")
        raise


def _is_newer_version(new_version: str, current_version: str) -> bool:
    """Check if new_version is newer than current_version.
    
    Args:
        new_version: Version string to check (e.g., "1.2.3")
        current_version: Current version string (e.g., "1.2.0")
    
    Returns:
        True if new_version > current_version, False otherwise
    """
    try:
        new_parts = [int(x) for x in str(new_version).split(".")]
        cur_parts = [int(x) for x in str(current_version).split(".")]
        max_len = max(len(new_parts), len(cur_parts))
        new_parts += [0] * (max_len - len(new_parts))
        cur_parts += [0] * (max_len - len(cur_parts))
        return new_parts > cur_parts
    except (TypeError, ValueError):
        logger.exception("Error comparing versions: %r vs %r", new_version, current_version)
        return False
