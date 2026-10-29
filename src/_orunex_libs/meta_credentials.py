"""Single source of truth for Meta API credentials in the desktop app.

The desktop UI is often started with ``pythonw.exe src\\main.py`` from a
shortcut, a scheduled task or Explorer.  Those launches do **not** inherit
variables that were set in a previous PowerShell session, so a key that works
in the terminal can be invisible to the real Orunex process.  This module
resolves the key from every supported location, in order:

1. the current process environment;
2. the repository ``.env`` file;
3. the Windows *user* environment (``HKCU\\Environment``);
4. ``orunex_config.json`` through :mod:`config_manager`.

It only reads credentials.  The key is never logged or written anywhere.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

_KEY_VARS = ("META_API_KEY", "MODEL_API_KEY", "META_AI_API_KEY")
_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
_ENV_CACHE: tuple[float, dict[str, str]] = (-1.0, {})


def _clean(value: object) -> str:
    text = str(value or "").strip().strip('"').strip("'").strip()
    if text.lower().startswith("bearer "):
        text = text[7:].strip()
    return text


def _env_file_values() -> dict[str, str]:
    """Parse ``.env`` once per modification, without requiring dotenv."""
    global _ENV_CACHE
    try:
        mtime = _ENV_PATH.stat().st_mtime
    except OSError:
        return {}
    cached_mtime, cached_values = _ENV_CACHE
    if mtime == cached_mtime:
        return cached_values

    values: dict[str, str] = {}
    try:
        for raw in _ENV_PATH.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            name = name.strip()
            if name.startswith("export "):
                name = name[7:].strip()
            if not name:
                continue
            values[name] = _clean(value)
    except OSError:
        values = {}
    _ENV_CACHE = (mtime, values)
    return values


def _windows_user_env(name: str) -> str:
    """Read a variable from the Windows user environment (not the process)."""
    if os.name != "nt":
        return ""
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, _ = winreg.QueryValueEx(key, name)
        return _clean(value)
    except Exception:
        return ""


def _config_value(name: str) -> str:
    try:
        from _orunex_libs import config_manager

        value = config_manager.get_val(name)
        return _clean(value)
    except Exception:
        return ""


def _first_from(mapping: dict[str, str]) -> str:
    for name in _KEY_VARS:
        value = _clean(mapping.get(name))
        if value:
            return value
    return ""


def get_api_key() -> str:
    """Return the first usable Meta key without exposing it."""
    for name in _KEY_VARS:
        value = _clean(os.environ.get(name))
        if value:
            return value

    value = _first_from(_env_file_values())
    if value:
        return value

    for name in _KEY_VARS:
        value = _windows_user_env(name)
        if value:
            return value

    for name in _KEY_VARS:
        value = _config_value(name)
        if value:
            return value
    return _config_value("meta_api_key")


def get_api_key_source() -> str:
    """Human-readable origin of the key, safe to print in diagnostics."""
    for name in _KEY_VARS:
        if _clean(os.environ.get(name)):
            return "process-environment"
    if _first_from(_env_file_values()):
        return ".env"
    for name in _KEY_VARS:
        if _windows_user_env(name):
            return "windows-user-environment"
    for name in _KEY_VARS:
        if _config_value(name):
            return "orunex_config.json"
    if _config_value("meta_api_key"):
        return "orunex_config.json"
    return "missing"


def has_api_key() -> bool:
    return bool(get_api_key())
