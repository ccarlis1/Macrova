"""Shared pytest setup so CI and local runs behave like a clean checkout.

GitHub Actions runs from the repo root with ``pip install -r requirements.txt`` and:

- ``python -m pytest tests/ -q`` (needs ``httpx`` for FastAPI TestClient)
- ``python scripts/export_openapi.py --check`` (OpenAPI snapshot must match the app)

``config/user_profile.yaml`` is gitignored; CLI/API tests reference it by path.
"""

import shutil

import pytest
import yaml
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session", autouse=True)
def setup_test_config():
    """Ensure ``config/user_profile.yaml`` exists and has a valid schedule.

    Copies from ``user_profile.yaml.example`` when the file is missing or when
    YAML has no usable ``schedule_days`` or legacy ``schedule`` (avoids CLI
    crashes on empty/commented-out schedules). Paths are anchored to the repo
    root so this works regardless of pytest's current working directory.
    """
    config_dir = _REPO_ROOT / "config"
    config_dir.mkdir(parents=True, exist_ok=True)

    profile_file = config_dir / "user_profile.yaml"
    example_file = config_dir / "user_profile.yaml.example"

    needs_copy = not profile_file.exists()
    if not needs_copy and profile_file.exists():
        try:
            data = yaml.safe_load(profile_file.read_text(encoding="utf-8")) or {}
            schedule_days = data.get("schedule_days")
            schedule = data.get("schedule")
            has_valid_schedule_days = isinstance(schedule_days, list) and len(schedule_days) > 0
            has_valid_legacy_schedule = isinstance(schedule, dict) and len(schedule) > 0
            needs_copy = not (has_valid_schedule_days or has_valid_legacy_schedule)
        except Exception:
            needs_copy = True

    if needs_copy and example_file.exists():
        shutil.copy(example_file, profile_file)
