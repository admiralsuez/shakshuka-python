from __future__ import annotations

import logging
import os

from flask import Flask

from src.constants import MAX_CONTENT_LENGTH_BYTES
from src.core.config import config
from src.core.correlation import init_flask_middleware
from src.exceptions import ConfigurationException
from src.utils.paths import get_user_data_dir


def create_app() -> Flask:
    app = Flask(__name__)

    logger = logging.getLogger(__name__)

    app.config['DEBUG'] = bool(config.DEBUG)
    app.debug = bool(config.DEBUG)
    app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH_BYTES

    user_data_dir = get_user_data_dir()
    try:
        os.makedirs(user_data_dir, exist_ok=True)
    except Exception as e:
        logger.exception('Failed to create user data directory')
        raise ConfigurationException('Failed to create user data directory', cause=e)
    secret_key_file = os.path.join(user_data_dir, '.flask_secret')

    try:
        if os.path.exists(secret_key_file):
            with open(secret_key_file, 'rb') as f:
                secret_key_data = f.read()
            if len(secret_key_data) < 32:
                raise ConfigurationException('Invalid secret key size')
            app.secret_key = secret_key_data
        else:
            app.secret_key = os.urandom(32)
            with open(secret_key_file, 'wb') as f:
                f.write(app.secret_key)
    except Exception as e:
        logger.exception('Failed to load or create secret key')
        env_key = os.getenv('FLASK_SECRET_KEY')
        if env_key and isinstance(env_key, str) and len(env_key.encode()) >= 32:
            app.secret_key = env_key.encode()
        else:
            raise ConfigurationException('Failed to initialize Flask secret key', cause=e)

    try:
        init_flask_middleware(app)
    except Exception as e:
        logger.exception('Failed to initialize correlation ID middleware')
        raise ConfigurationException('Failed to initialize correlation ID middleware', cause=e)

    return app
