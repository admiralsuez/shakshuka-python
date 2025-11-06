"""
Application Factory - Creates and configures the Flask application
"""
import os
import logging
from flask import Flask
from flask_cors import CORS

from src.core import config, app_context
from src.security_manager import security_manager
from src.user_manager import user_manager
from src.monitoring import monitor


def setup_logging():
    """Configure application logging"""
    config.ensure_directories()
    logs_dir = config.get_logs_dir()
    log_file = os.path.join(logs_dir, 'shakshuka.log')
    
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL),
        format=config.LOG_FORMAT,
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger(__name__)


def create_app():
    """
    Application factory function.
    Creates and configures the Flask application with all necessary components.
    """
    # Setup logging first
    logger = setup_logging()
    logger.info("Creating Flask application...")
    
    # Create Flask app
    app = Flask(
        __name__,
        static_folder=config.get_static_dir(),
        template_folder=config.get_template_dir()
    )
    
    # Configure secret key
    setup_secret_key(app)
    
    # Configure CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # Load version information
    version_info = config.get_version_info()
    app_context.app_version = version_info['version']
    app_context.build_number = version_info['build']
    
    logger.info(f"Application version: {version_info['version']}-b{version_info['build']}")
    
    # Register routes
    from src.routes_legacy import register_all_routes
    register_all_routes(app)
    
    logger.info("Flask application created successfully")
    return app


def setup_secret_key(app):
    """Setup Flask secret key with persistence"""
    user_data_dir = config.get_user_data_dir()
    os.makedirs(user_data_dir, exist_ok=True)
    secret_key_file = os.path.join(user_data_dir, '.flask_secret')
    
    try:
        if os.path.exists(secret_key_file):
            with open(secret_key_file, 'rb') as f:
                app.secret_key = f.read()
        else:
            app.secret_key = os.urandom(32)
            with open(secret_key_file, 'wb') as f:
                f.write(app.secret_key)
    except Exception as e:
        print(f"Warning: Could not create Flask secret key file: {e}")
        app.secret_key = os.urandom(32)

