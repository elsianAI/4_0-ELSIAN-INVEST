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


def load_extraction_rules(config_dir: Path | None = None) -> dict[str, Any]:
    """Load extraction policy packs configuration."""
    return load_json_config("extraction_rules.json", config_dir)


def resolve_extraction_pack(
    extraction_rules: dict[str, Any],
    pack_name: str,
    case_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge base ← pack ← case extraction_overrides.

    Deep merge at context_bonus and html sub-keys: pack/case values
    replace the corresponding base sub-key entries. List values are
    replaced, not concatenated (override semantics, not extend).

    Args:
        extraction_rules: Full extraction_rules.json dict.
        pack_name: Named pack to apply (e.g. 'sec_html', 'pdf_ifrs').
        case_overrides: Optional per-case config_overrides from case.json.

    Returns:
        Resolved dict with base merged with pack and case overrides.
    """
    import copy

    result: dict[str, Any] = copy.deepcopy(extraction_rules.get("base", {}))
    pack_data = extraction_rules.get("packs", {}).get(pack_name, {})
    for section_key, section_val in pack_data.items():
        if isinstance(section_val, dict) and isinstance(result.get(section_key), dict):
            result[section_key].update(section_val)
        else:
            result[section_key] = copy.deepcopy(section_val)
    if case_overrides:
        for section_key, section_val in case_overrides.items():
            if isinstance(section_val, dict) and isinstance(result.get(section_key), dict):
                result[section_key].update(section_val)
            else:
                result[section_key] = copy.deepcopy(section_val)
    return result
