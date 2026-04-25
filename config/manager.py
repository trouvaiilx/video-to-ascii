"""
Configuration Manager — persists user settings, custom presets, and app state.
Uses JSON storage in the user's home directory.
"""

import json
import os
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".ascii_video_converter"
CONFIG_FILE = CONFIG_DIR / "config.json"
CUSTOM_PRESETS_FILE = CONFIG_DIR / "custom_presets.json"
RECENT_FILES_FILE = CONFIG_DIR / "recent_files.json"

MAX_RECENT_FILES = 20


class ConfigManager:
    """
    Manages application configuration with auto-save/load semantics.
    Thread-safe via file-level operations (single-writer assumption for config).
    """

    _defaults: dict = {
        "last_input_dir": str(Path.home()),
        "last_output_dir": str(Path.home()),
        "active_preset": "medium_quality",
        "window_width": 1400,
        "window_height": 900,
        "window_maximized": False,
        "theme": "dark",
        "preview_fps": 10,
        "show_comparison": True,
        "show_debug_panel": False,
        "worker_threads": 0,
        "gpu_enabled": False,
        "benchmark_mode": False,
        "batch_output_dir": str(Path.home() / "ascii_output"),
    }

    def __init__(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self._data: dict = dict(self._defaults)
        self._custom_presets: dict = {}
        self._recent_files: list = []
        self._load()

    def _load(self) -> None:
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self._data.update(saved)
            except Exception as e:
                logger.warning("Could not load config: %s", e)

        if CUSTOM_PRESETS_FILE.exists():
            try:
                with open(CUSTOM_PRESETS_FILE, "r", encoding="utf-8") as f:
                    self._custom_presets = json.load(f)
            except Exception as e:
                logger.warning("Could not load custom presets: %s", e)

        if RECENT_FILES_FILE.exists():
            try:
                with open(RECENT_FILES_FILE, "r", encoding="utf-8") as f:
                    self._recent_files = json.load(f)
                self._recent_files = [f for f in self._recent_files if os.path.exists(f)]
            except Exception as e:
                logger.warning("Could not load recent files: %s", e)

    def save(self) -> None:
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except OSError as e:
            logger.error("Failed to save config: %s", e)

    def save_custom_presets(self) -> None:
        try:
            with open(CUSTOM_PRESETS_FILE, "w", encoding="utf-8") as f:
                json.dump(self._custom_presets, f, indent=2)
        except OSError as e:
            logger.error("Failed to save custom presets: %s", e)

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        self._data[key] = value

    def get_all_presets(self) -> dict:
        from presets.profiles import PRESETS, RenderProfile
        result = dict(PRESETS)
        for key, d in self._custom_presets.items():
            try:
                result[key] = RenderProfile.from_dict(d)
            except Exception as e:
                logger.warning("Skipping invalid custom preset '%s': %s", key, e)
        return result

    def save_custom_preset(self, key: str, profile) -> None:
        self._custom_presets[key] = profile.to_dict()
        self.save_custom_presets()

    def delete_custom_preset(self, key: str) -> bool:
        if key in self._custom_presets:
            del self._custom_presets[key]
            self.save_custom_presets()
            return True
        return False

    def get_active_profile(self):
        from presets.profiles import PRESETS, RenderProfile
        key = self._data.get("active_preset", "medium_quality")
        return self.get_all_presets().get(key, PRESETS["medium_quality"])

    def add_recent_file(self, path: str) -> None:
        if path in self._recent_files:
            self._recent_files.remove(path)
        self._recent_files.insert(0, path)
        self._recent_files = self._recent_files[:MAX_RECENT_FILES]
        try:
            with open(RECENT_FILES_FILE, "w", encoding="utf-8") as f:
                json.dump(self._recent_files, f, indent=2)
        except OSError:
            pass

    def get_recent_files(self) -> list:
        return [f for f in self._recent_files if os.path.exists(f)]
