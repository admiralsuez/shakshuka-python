import os
import sys
from functools import wraps
from typing import Callable, Optional

import platformdirs


GetDirFunc = Callable[[Optional[str]], str]


def ensure_path_exists(path: str) -> None:
    if not os.path.exists(path):
        os.makedirs(path)


def _ensure_returned_path_exists(f: GetDirFunc) -> GetDirFunc:
    @wraps(f)
    def wrapper(subpath: Optional[str] = None) -> str:
        path = f(subpath)
        ensure_path_exists(path)
        return path

    return wrapper


@_ensure_returned_path_exists
def get_data_dir(module_name: Optional[str] = None) -> str:
    base = platformdirs.user_data_dir("shakshuka")
    return os.path.join(base, module_name) if module_name else base


@_ensure_returned_path_exists
def get_cache_dir(module_name: Optional[str] = None) -> str:
    base = platformdirs.user_cache_dir("shakshuka")
    return os.path.join(base, module_name) if module_name else base


@_ensure_returned_path_exists
def get_config_dir(module_name: Optional[str] = None) -> str:
    base = platformdirs.user_config_dir("shakshuka")
    return os.path.join(base, module_name) if module_name else base


@_ensure_returned_path_exists
def get_log_dir(module_name: Optional[str] = None) -> str:
    if sys.platform.startswith("linux"):
        base = platformdirs.user_cache_path("shakshuka") / "log"
    else:
        base = platformdirs.user_log_dir("shakshuka")
    base_str = str(base)
    return os.path.join(base_str, module_name) if module_name else base_str


