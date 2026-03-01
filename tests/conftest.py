"""Shared fixtures for ELSIAN 4.0 tests."""

import pathlib
import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
CASES_DIR = PROJECT_ROOT / "cases"
CONFIG_DIR = PROJECT_ROOT / "config"


@pytest.fixture
def config_dir() -> pathlib.Path:
    return CONFIG_DIR


@pytest.fixture
def cases_dir() -> pathlib.Path:
    return CASES_DIR
