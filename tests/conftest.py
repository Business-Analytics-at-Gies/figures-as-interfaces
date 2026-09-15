"""Keep all temporary test files local and provider selection deterministic."""
import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def local_environment(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("TMPDIR", str(root / ".scratch"))
    monkeypatch.delenv("FIGUREFLOW_PLANNER", raising=False)
