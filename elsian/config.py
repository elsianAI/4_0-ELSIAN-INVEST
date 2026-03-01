"""Configuration loader with per-case override support."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def load_json_config(filename: str, config_dir: Path | None = None) -> dict[str, Any]:
    """Load a JSON config file from the config directory."""
    cdir = config_dir or _DEFAULT_CONFIG_DIR
    path = cdir / filename
    if not path.exists():
        logger.warning("Config file not found: %s", path)
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_field_aliases(config_dir: Path | None = None) -> dict[str, Any]:
    """Load field alias configuration."""
    return load_json_config("field_aliases.json", config_dir)


def load_selection_rules(config_dir: Path | None = None) -> dict[str, Any]:
    """Load selection/priority rules configuration."""
    return load_json_config("selection_rules.json", config_dir)
