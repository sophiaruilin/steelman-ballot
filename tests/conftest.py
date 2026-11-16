import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest


@pytest.fixture(autouse=True)
def _never_touch_real_usage_totals(monkeypatch):
    """Tests count in memory only, even when .env has Upstash keys (so they can't pollute live stats)."""
    from backend import stats
    monkeypatch.setattr(stats, "URL", "")
    monkeypatch.setattr(stats, "TOKEN", "")
