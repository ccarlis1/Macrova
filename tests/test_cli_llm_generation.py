import json
import re
import sys
from pathlib import Path
import tempfile

import pytest

import src.cli as cli
from src.config.llm_settings import LLMSettings, LLMSettingsError
from src.providers.ingredient_provider import IngredientDataProvider


def _write_recipes_file(path: Path) -> None:
    path.write_text(json.dumps({"recipes": []}), encoding="utf-8")


class DummyLLMClient:
    """Mock LLM boundary for CLI tests."""

    def __init__(self, settings: LLMSettings):
        self._settings = settings

    def generate_json(self, *, system_prompt, user_prompt, schema_name, temperature=0.0):
        assert schema_name == "RecipeDraftEnvelope"
        assert temperature == 0.0

        m = re.search(r"generate exactly (\d+) recipe drafts", user_prompt)
        count = int(m.group(1)) if m else 1

        drafts = [
            {
                "name": f"LLM Recipe {i}",
                "ingredients": [
                    {"name": "chicken breast", "quantity": 200.0, "unit": "g"},
                    {"name": "white rice", "quantity": 250.0, "unit": "g"},
                ],
                "instructions": ["Cook it.", "Serve it."],
            }
            for i in range(count)
        ]

        return {"drafts": drafts}


class FakeUSDAProvider(IngredientDataProvider):
    usda_capable = True

    def __init__(self, *, per_100g_by_name):
        self._per_100g_by_name = per_100g_by_name

    def get_ingredient_info(self, name: str):
        key = str(name).lower().strip()
        if key not in self._per_100g_by_name:
            return None
        return {"name": key, "per_100g": self._per_100g_by_name[key]}

    def resolve_all(self, ingredient_names):
        return None


def test_cli_llm_generate_validated_success(monkeypatch, capsys):
    with tempfile.TemporaryDirectory() as td:
        recipes_path = Path(td) / "recipes.json"
        _write_recipes_file(recipes_path)

        # Patch settings + LLM + USDA provider wiring.
        monkeypatch.setattr(
            "src.cli.load_llm_settings",
            lambda: LLMSettings(
                api_key="dummy",
                model="dummy-model",
                timeout_seconds=1.0,
                max_retries=0,
                rate_limit_qps=1.0,
                enabled=True,
            ),
        )
        monkeypatch.setattr("src.cli.LLMClient", DummyLLMClient)

        monkeypatch.setattr("src.cli.USDAClient.from_env", classmethod(lambda cls: object()))
        monkeypatch.setattr("src.cli.CachedIngredientLookup", lambda usda_client: object())

        provider = FakeUSDAProvider(
            per_100g_by_name={
                "chicken breast": {"calories": 165.0, "protein_g": 31.0, "fat_g": 3.6, "carbs_g": 0.0},
                "white rice": {"calories": 130.0, "protein_g": 2.7, "fat_g": 0.3, "carbs_g": 28.0},
            }
        )
        monkeypatch.setattr("src.cli.APIIngredientProvider", lambda cached_lookup: provider)

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "cli.py",
                "--profile",
                "config/user_profile.yaml",
                "--recipes",
                str(recipes_path),
                "--llm-generate-validated",
                "--count",
                "1",
                "--context-json",
                "{}",
            ],
        )

        cli.main()

        out = capsys.readouterr()
        summary = json.loads(out.out.strip())

        assert summary["requested"] == 1
        assert summary["generated"] == 1
        assert summary["accepted"] == 1
        assert len(summary["persisted_ids"]) == 1

        data = json.loads(recipes_path.read_text(encoding="utf-8"))
        assert len(data["recipes"]) == 1


def test_cli_llm_generate_validated_missing_settings(monkeypatch, capsys):
    with tempfile.TemporaryDirectory() as td:
        recipes_path = Path(td) / "recipes.json"
        _write_recipes_file(recipes_path)

        monkeypatch.setattr(
            "src.cli.load_llm_settings",
            lambda: (_ for _ in ()).throw(LLMSettingsError("bad config")),
        )

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "cli.py",
                "--profile",
                "config/user_profile.yaml",
                "--recipes",
                str(recipes_path),
                "--llm-generate-validated",
                "--count",
                "1",
                "--context-json",
                "{}",
            ],
        )

        with pytest.raises(SystemExit):
            cli.main()


def test_cli_llm_generate_validated_invalid_context(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        recipes_path = Path(td) / "recipes.json"
        _write_recipes_file(recipes_path)

        # Settings/LLM wiring can be present, but context parsing should fail first.
        monkeypatch.setattr(
            "src.cli.load_llm_settings",
            lambda: LLMSettings(
                api_key="dummy",
                model="dummy-model",
                timeout_seconds=1.0,
                max_retries=0,
                rate_limit_qps=1.0,
                enabled=True,
            ),
        )

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "cli.py",
                "--profile",
                "config/user_profile.yaml",
                "--recipes",
                str(recipes_path),
                "--llm-generate-validated",
                "--count",
                "1",
                "--context-json",
                "{not-json",
            ],
        )

        with pytest.raises(SystemExit):
            cli.main()


def test_cli_llm_generate_validated_deterministic_ids(monkeypatch):
    # Run twice with fresh empty recipe stores and ensure the persisted ID is stable.
    # This is determinism for the persistence boundary (fingerprint->id).
    monkeypatch.setattr(
        "src.cli.load_llm_settings",
        lambda: LLMSettings(
            api_key="dummy",
            model="dummy-model",
            timeout_seconds=1.0,
            max_retries=0,
            rate_limit_qps=1.0,
            enabled=True,
        ),
    )
    monkeypatch.setattr("src.cli.LLMClient", DummyLLMClient)
    monkeypatch.setattr("src.cli.USDAClient.from_env", classmethod(lambda cls: object()))
    monkeypatch.setattr("src.cli.CachedIngredientLookup", lambda usda_client: object())

    provider = FakeUSDAProvider(
        per_100g_by_name={
            "chicken breast": {"calories": 165.0, "protein_g": 31.0, "fat_g": 3.6, "carbs_g": 0.0},
            "white rice": {"calories": 130.0, "protein_g": 2.7, "fat_g": 0.3, "carbs_g": 28.0},
        }
    )
    monkeypatch.setattr("src.cli.APIIngredientProvider", lambda cached_lookup: provider)

    ids = []
    for _ in range(2):
        with tempfile.TemporaryDirectory() as td:
            recipes_path = Path(td) / "recipes.json"
            _write_recipes_file(recipes_path)
            sys_argv = [
                "cli.py",
                "--profile",
                "config/user_profile.yaml",
                "--recipes",
                str(recipes_path),
                "--llm-generate-validated",
                "--count",
                "1",
                "--context-json",
                "{}",
            ]
            with pytest.MonkeyPatch.context() as mp:
                mp.setattr(sys, "argv", sys_argv)
                mp.setattr("src.cli.APIIngredientProvider", lambda cached_lookup: provider)
                mp.setattr("src.cli.LLMClient", DummyLLMClient)
                # Capture stdout deterministically.
                from io import StringIO

                buf = StringIO()
                monkeypatch_stdout = mp.setattr(sys, "stdout", buf, raising=False)
                cli.main()
                ids.append(json.loads(buf.getvalue().strip())["persisted_ids"][0])

    assert ids[0] == ids[1]

