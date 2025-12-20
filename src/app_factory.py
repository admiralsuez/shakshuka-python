from __future__ import annotations

import os

from flask import Flask

from src.constants import MAX_CONTENT_LENGTH_BYTES
from src.core.config import config
from src.utils.paths import get_user_data_dir


def create_app() -> Flask:
    app = Flask(__name__)

    app.config['DEBUG'] = bool(config.DEBUG)
    app.debug = bool(config.DEBUG)
    app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH_BYTES

    user_data_dir = get_user_data_dir()
    os.makedirs(user_data_dir, exist_ok=True)
    secret_key_file = os.path.join(user_data_dir, '.flask_secret')

    try:
        if os.path.exists(secret_key_file):
            with open(secret_key_file, 'rb') as f:
                secret_key_data = f.read()
                if len(secret_key_data) >= 32:
                    app.secret_key = secret_key_data
                else:
                    raise ValueError('Invalid secret key size')
        else:
            app.secret_key = os.urandom(32)
            with open(secret_key_file, 'wb') as f:
                f.write(app.secret_key)
    except Exception:
        env_key = os.getenv('FLASK_SECRET_KEY')
        if env_key:
            app.secret_key = env_key.encode()
        else:
            app.secret_key = os.urandom(32)

    return app
