from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "validate_contracts.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("validate_contracts", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_validate_all_contracts_passes_for_tracked_repo_artifacts():
    module = _load_module()

    issues = module.validate_all_contracts()

    assert issues == {}


def test_validate_task_manifest_contract_accepts_minimal_sample(tmp_path: Path):
    module = _load_module()
    manifest_path = tmp_path / "task_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "task_id": "BL-059",
                "title": "Contratos versionados",
                "kind": "technical",
                "validation_tier": "shared-core",
                "claimed_bl_status": "none",
                "write_set": [
                    "schemas/v1/case.schema.json",
                    "scripts/validate_contracts.py",
                ],
                "references": ["BL-059"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    issues = module.validate_single_contract("task_manifest", manifest_path)

    assert issues == []


def test_curate_prompt_contract_is_current():
    module = _load_module()

    issues = module.validate_curate_prompt_contract()

    assert issues == []
