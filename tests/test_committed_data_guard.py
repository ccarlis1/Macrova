"""The session guard in conftest.py notices writes to the committed recipe/tag stores."""

from conftest import (
    GUARDED_DATA_FILES,
    _REPO_ROOT,
    changed_files,
    committed_data_changed_message,
    hash_files,
)


def test_guard_covers_recipes_and_tag_store():
    assert {p.relative_to(_REPO_ROOT).as_posix() for p in GUARDED_DATA_FILES} == {
        "data/recipes/recipes.json",
        "data/recipes/recipe_tags.json",
    }


def test_unchanged_files_are_not_reported(tmp_path):
    recipes = tmp_path / "recipes.json"
    recipes.write_text('{"recipes": []}', encoding="utf-8")
    missing = tmp_path / "recipe_tags.json"
    before = hash_files([recipes, missing])
    assert changed_files(before, hash_files([recipes, missing])) == []


def test_modified_or_created_files_are_reported(tmp_path):
    recipes = tmp_path / "recipes.json"
    recipes.write_text('{"recipes": []}', encoding="utf-8")
    tags = tmp_path / "recipe_tags.json"
    before = hash_files([recipes, tags])

    recipes.write_text('{"recipes": [{"id": "leak"}]}', encoding="utf-8")
    tags.write_text("{}", encoding="utf-8")
    assert changed_files(before, hash_files([recipes, tags])) == sorted([str(recipes), str(tags)])


def test_failure_message_names_repo_relative_file_and_remedy():
    msg = committed_data_changed_message([str(_REPO_ROOT / "data" / "recipes" / "recipe_tags.json")])
    assert "data/recipes/recipe_tags.json" in msg
    assert "tmp_path" in msg and "recipes path" in msg and "tag path" in msg
