import pytest
from pathlib import Path
import shutil
import yaml


@pytest.fixture(scope="session", autouse=True)
def setup_test_config():
    """Ensure test configuration files exist."""
    config_dir = Path("config")
    config_dir.mkdir(exist_ok=True)

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
