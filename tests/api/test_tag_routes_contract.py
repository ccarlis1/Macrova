"""BE-15: ``/api/v1/tags`` HTTP contracts; registry seeded from DM-7 ``recipe_tags.json`` copy."""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from src.api.server import app

_ROOT = Path(__file__).resolve().parents[2]


def _client(tmp_path, monkeypatch) -> TestClient:
    dst = tmp_path / "recipe_tags.json"
    shutil.copyfile(_ROOT / "data/recipes/recipe_tags.json", dst)
    monkeypatch.setattr("src.api.tag_routes.DEFAULT_TAG_PATH", str(dst))
    return TestClient(app)


def test_create_tag_returns_slug_type_display(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    res = c.post(
        "/api/v1/tags",
        json={
            "display": "BE15 Contract Tag",
            "type": "nutrition",
            "slug": "be15-contract-tag",
        },
    )
    assert res.status_code == 200
    tag = res.json()["tag"]
    assert tag["slug"] == "be15-contract-tag"
    assert tag["type"] == "nutrition"
    assert tag["display"] == "BE15 Contract Tag"


def test_create_duplicate_slug_returns_tag_conflict(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    body = {
        "display": "First",
        "type": "nutrition",
        "slug": "be15-dup-slug",
    }
    assert c.post("/api/v1/tags", json=body).status_code == 200
    dup = c.post(
        "/api/v1/tags",
        json={"display": "Second Label", "type": "nutrition", "slug": "be15-dup-slug"},
    )
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "TAG_CONFLICT"


def test_add_alias_normalizes_input(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    alias_raw = "  High   Fiber   Alias   Token  "
    res = c.post(
        "/api/v1/tags/high-fiber/alias",
        json={"alias_slug": alias_raw},
    )
    assert res.status_code == 200
    listed = c.get("/api/v1/tags").json()["tags"]
    hi = next(t for t in listed if t["slug"] == "high-fiber")
    normalized = "high-fiber-alias-token"
    assert normalized in hi["aliases"]


def test_merge_src_into_dst_updates_registry(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert (
        c.post(
            "/api/v1/tags",
            json={
                "display": "Merge Src BE15",
                "type": "nutrition",
                "slug": "be15-merge-src",
            },
        ).status_code
        == 200
    )
    assert (
        c.post(
            "/api/v1/tags",
            json={
                "display": "Merge Dst BE15",
                "type": "nutrition",
                "slug": "be15-merge-dst",
            },
        ).status_code
        == 200
    )
    merged = c.post("/api/v1/tags/be15-merge-src/merge_into/be15-merge-dst")
    assert merged.status_code == 200
    assert merged.json()["tag"]["slug"] == "be15-merge-dst"

    slugs = {t["slug"] for t in c.get("/api/v1/tags").json()["tags"]}
    assert "be15-merge-src" not in slugs
    assert "be15-merge-dst" in slugs


def test_list_tags_includes_dm7_seed_slugs(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    slugs = {t["slug"] for t in c.get("/api/v1/tags").json()["tags"]}
    for expected in ("meal-prep", "time-0", "time-1", "high-fiber"):
        assert expected in slugs
