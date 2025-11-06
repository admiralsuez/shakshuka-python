"""
Routes package - Contains all Flask route blueprints
"""

from flask import Blueprint

# Import all route blueprints
from .auth_routes import auth_bp
from .task_routes import task_bp
from .settings_routes import settings_bp
from .monitoring_routes import monitoring_bp
from .system_routes import system_bp
from .static_routes import static_bp

def register_routes(app):
    """Register all route blueprints with the Flask app"""
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(task_bp, url_prefix='/api/tasks')
    app.register_blueprint(settings_bp, url_prefix='/api/settings')
    app.register_blueprint(monitoring_bp, url_prefix='/api/monitoring')
    app.register_blueprint(system_bp, url_prefix='/api/system')
    app.register_blueprint(static_bp)  # No prefix for static routes

__all__ = ['register_routes']

