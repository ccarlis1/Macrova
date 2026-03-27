from __future__ import annotations

from pathlib import Path
import shutil

import pytest


@pytest.fixture(autouse=True, scope="session")
def ensure_default_user_profile_yaml() -> None:
    """Ensure tests have a default CLI profile path available.

    CI environments won't have `config/user_profile.yaml` because it's gitignored.
    Some CLI/API integration tests pass this path explicitly, so copy from the
    checked-in example when needed.
    """

    repo_root = Path(__file__).resolve().parent.parent
    profile_path = repo_root / "config" / "user_profile.yaml"
    example_path = repo_root / "config" / "user_profile.yaml.example"

    created = False
    if not profile_path.exists() and example_path.exists():
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(example_path, profile_path)
        created = True

    try:
        yield
    finally:
        if created and profile_path.exists():
            profile_path.unlink()
