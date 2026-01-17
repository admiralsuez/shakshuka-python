from __future__ import annotations

import logging
import os
import re
import sys
from datetime import datetime
from typing import Optional

from flask import Flask

from src.exceptions import ConfigurationException


def resolve_root_dir() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)

    try:
        import pkg_resources

        dist = pkg_resources.get_distribution('shakshuka')
        if dist:
            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if not os.path.exists(os.path.join(package_root, 'assets')):
                share_dir = '/usr/share/shakshuka'
                if os.path.exists(share_dir):
                    return share_dir
            return root_dir
    except ImportError:
        logging.getLogger(__name__).debug('pkg_resources not available; using fallback root resolution')
    except Exception:  # noqa: broad-except
        logging.getLogger(__name__).exception('Failed to resolve root directory via pkg_resources')

    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def configure_assets(app: Flask, root_dir: str) -> None:
    static_dir = os.path.join(root_dir, 'assets', 'static')
    template_dir = os.path.join(root_dir, 'assets', 'templates')
    if not os.path.isdir(static_dir):
        raise ConfigurationException(f"Static assets directory missing: {static_dir}")
    if not os.path.isdir(template_dir):
        raise ConfigurationException(f"Templates directory missing: {template_dir}")
    app.static_folder = static_dir
    app.template_folder = template_dir


def configure_working_dir(root_dir: str) -> None:
    try:
        os.chdir(root_dir)
    except Exception:  # noqa: broad-except
        logging.getLogger(__name__).exception('Failed to set working directory')
        raise ConfigurationException(f"Failed to set working directory: {root_dir}")


def configure_logging(user_data_dir: str) -> Optional[str]:
    try:
        from src.core.correlation import init_logging_context

        init_logging_context()
    except Exception:  # noqa: broad-except
        logging.getLogger(__name__).exception('Failed to initialize logging correlation context')

    try:
        logs_dir = os.path.join(user_data_dir, 'logs')
        os.makedirs(logs_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y-%m-%d - %H-%M-%S')
        existing_log_files = [
            f for f in os.listdir(logs_dir)
            if f.lower().endswith('.log') or f.lower().endswith('.txt')
        ]

        next_index = 1
        if existing_log_files:
            pattern = re.compile(rf"^{re.escape(timestamp)} - log #(\d+)\.(?:log|txt)$", re.IGNORECASE)
            for name in existing_log_files:
                m = pattern.match(name)
                if m:
                    try:
                        idx = int(m.group(1))
                        if idx >= next_index:
                            next_index = idx + 1
                    except ValueError:
                        continue

        log_filename = f"{timestamp} - log #{next_index}.log"
        log_file = os.path.join(logs_dir, log_filename)

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(correlation_id)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(),
            ],
        )

        try:
            log_paths = [
                os.path.join(logs_dir, f)
                for f in os.listdir(logs_dir)
                if f.lower().endswith('.log') or f.lower().endswith('.txt')
            ]
            if len(log_paths) > 7:
                log_paths.sort(key=lambda p: os.path.getmtime(p), reverse=True)
                for old_path in log_paths[7:]:
                    try:
                        os.remove(old_path)
                    except Exception:  # noqa: broad-except
                        logging.getLogger(__name__).exception('Failed to delete old log file: %s', old_path)
        except Exception:  # noqa: broad-except
            logging.getLogger(__name__).exception('Failed while pruning old log files')

        return log_file

    except Exception:  # noqa: broad-except
        logging.getLogger(__name__).exception('Failed to configure file logging; falling back to console logging')
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(correlation_id)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()],
        )
        return None
