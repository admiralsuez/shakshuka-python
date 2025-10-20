import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict

from .dirs import get_config_dir, get_data_dir


class Settings:
    def __init__(self, module_name: str = "app", testing: bool = False) -> None:
        filename = "settings-testing.json" if testing else "settings.json"
        self._config_path = Path(get_config_dir(module_name)) / filename
        self._data: Dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        if self._config_path.exists():
            with open(self._config_path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        else:
            self._data = {}

    def save(self) -> None:
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._config_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        if value is None and key in self._data:
            del self._data[key]
        else:
            self._data[key] = value
        self.save()


def get_device_id(module_name: str = "app") -> str:
    path = Path(get_data_dir(module_name)) / "device_id"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    device_id = str(uuid.uuid4())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(device_id, encoding="utf-8")
    return device_id


