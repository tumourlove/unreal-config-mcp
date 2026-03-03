"""Configuration for unreal-config-mcp."""

import os
from pathlib import Path

UE_PROJECT_PATH = os.environ.get("UE_PROJECT_PATH", "")
UE_ENGINE_PATH = os.environ.get("UE_ENGINE_PATH", "")
UE_SOURCE_DB_PATH = os.environ.get("UE_SOURCE_DB_PATH", "")
UE_EDITOR_PYTHON_PORT = int(os.environ.get("UE_EDITOR_PYTHON_PORT", "6776"))
UE_MULTICAST_GROUP = os.environ.get("UE_MULTICAST_GROUP", "239.0.0.1")
UE_MULTICAST_PORT = int(os.environ.get("UE_MULTICAST_PORT", "6766"))
UE_MULTICAST_BIND = os.environ.get("UE_MULTICAST_BIND", "127.0.0.1")


def get_project_config_dir() -> Path:
    """Return {UE_PROJECT_PATH}/Config."""
    return Path(UE_PROJECT_PATH) / "Config"


def get_engine_config_dir() -> Path | None:
    """Return {UE_ENGINE_PATH}/Config, or None if not set."""
    if not UE_ENGINE_PATH:
        return None
    return Path(UE_ENGINE_PATH) / "Config"


def get_saved_config_dir() -> Path:
    """Return {UE_PROJECT_PATH}/Saved/Config/Windows."""
    return Path(UE_PROJECT_PATH) / "Saved" / "Config" / "Windows"
