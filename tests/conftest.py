"""Keep all temporary test files local and provider selection deterministic."""
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def ensure_scratch_dirs():
    (ROOT / ".scratch" / "pytest").mkdir(parents=True, exist_ok=True)


@pytest.fixture(autouse=True)
def local_environment(monkeypatch):
    monkeypatch.setenv("TMPDIR", str(ROOT / ".scratch"))
    monkeypatch.delenv("FIGUREFLOW_PLANNER", raising=False)
    monkeypatch.setenv("PYTHONPATH", str(ROOT / "tests/network_guard"))
