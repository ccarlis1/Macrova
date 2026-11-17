"""Sprint 2 BE-20 (W7): ``config/user_profile.yaml`` is personal and untracked.

A fresh clone doesn't have it. These tests pin what the code already does then:

- the CLI stops with exit 1 and says to copy ``config/user_profile.yaml.example``;
- the server has no saved pins or schedule (reads return empty), plans from the
  request alone, and creates the file on the first pin or schedule write.

They run against a temp path, never the real file.
"""

from __future__ import annotations

import sys

import pytest
from fastapi.testclient import TestClient

from src import cli
from src.api.server import app


def test_cli_without_profile_file_says_to_copy_the_example(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)  # the default --profile, config/user_profile.yaml, doesn't exist here
    monkeypatch.setattr(sys, "argv", ["cli.py"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "User profile file not found: config/user_profile.yaml" in err
    assert "Copy config/user_profile.yaml.example to config/user_profile.yaml" in err


def test_server_without_profile_file_has_no_pins_or_schedule(tmp_path, monkeypatch):
    profile = tmp_path / "missing" / "user_profile.yaml"
    monkeypatch.setenv("NUTRITION_USER_PROFILE_PATH", str(profile))
    client = TestClient(app)

    pins = client.get("/api/v1/profile/pins")
    assert pins.status_code == 200, pins.text
    assert pins.json() == {"pins": []}

    schedule = client.get("/api/v1/profile/schedule")
    assert schedule.status_code == 200, schedule.text
    assert schedule.json() == {"schedule_days": []}
    assert not profile.exists()


def test_server_schedule_write_creates_the_missing_profile_file(tmp_path, monkeypatch):
    profile = tmp_path / "user_profile.yaml"
    monkeypatch.setenv("NUTRITION_USER_PROFILE_PATH", str(profile))
    body = {
        "schedule_days": [
            {"day_index": 1, "meals": [{"index": 1, "busyness_level": 3}], "workouts": []}
        ]
    }
    res = TestClient(app).put("/api/v1/profile/schedule", json=body)
    assert res.status_code == 200, res.text
    assert profile.is_file()
