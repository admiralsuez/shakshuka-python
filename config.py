"""
Configuration management for Shakshuka application
"""
import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Base configuration class"""
    # Security
    SECRET_KEY = os.getenv('SECRET_KEY', os.urandom(32).hex())
    
    # Server settings
    HOST = os.getenv('HOST', '127.0.0.1')
    PORT = int(os.getenv('PORT', 8989))
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
    
    # Data settings
    DATA_DIR = os.getenv('DATA_DIR', 'data')
    MAX_UPLOAD_SIZE = int(os.getenv('MAX_UPLOAD_SIZE', 16 * 1024 * 1024))  # 16MB
    
    # Rate limiting
    RATE_LIMIT = os.getenv('RATE_LIMIT', '200 per hour')
    RATE_LIMIT_AUTH = os.getenv('RATE_LIMIT_AUTH', '5 per minute')
    
    # Session settings
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = int(os.getenv('SESSION_LIFETIME', 86400))  # 24 hours
    
    # CSRF settings
    CSRF_TOKEN_EXPIRY = int(os.getenv('CSRF_TOKEN_EXPIRY', 3600))  # 1 hour
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'logs/shakshuka.log')
    LOG_MAX_SIZE = int(os.getenv('LOG_MAX_SIZE', 10 * 1024 * 1024))  # 10MB
    LOG_BACKUP_COUNT = int(os.getenv('LOG_BACKUP_COUNT', 10))
    
    # Cache settings
    CACHE_TTL = int(os.getenv('CACHE_TTL', 60))  # seconds
    
    # Default password (should be changed in production)
    DEFAULT_PASSWORD = os.getenv('DEFAULT_PASSWORD', 'shakshuka2024')

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    LOG_LEVEL = 'DEBUG'

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    LOG_LEVEL = 'WARNING'
    # Additional security settings for production
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DEBUG = True
    DATA_DIR = 'test_data'
    LOG_LEVEL = 'DEBUG'

# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig
}

def get_config() -> Config:
    """Get configuration based on environment"""
    env = os.getenv('FLASK_ENV', 'production')
    return config.get(env, ProductionConfig)

