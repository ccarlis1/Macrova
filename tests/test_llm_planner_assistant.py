from src.llm.planner_assistant import suggest_targeted_recipe_drafts
from src.llm.schemas import RecipeDraft, RecipeIngredientDraft
from src.llm.client import LLMClient


def test_suggest_targeted_recipe_drafts_uses_recipe_generator(monkeypatch):
    draft = RecipeDraft(
        name="LLM Recipe",
        ingredients=[RecipeIngredientDraft(name="chicken breast", quantity=200.0, unit="g")],
        instructions=["Cook it."],
    )

    captured = {}

    def _fake_generate_recipe_drafts(*, client, context, count):
        captured["client"] = client
        captured["context"] = context
        captured["count"] = count
        return [draft]

    monkeypatch.setattr(
        "src.llm.planner_assistant.generate_recipe_drafts",
        _fake_generate_recipe_drafts,
    )

    dummy_client = object()  # only forwarded, not used in the fake
    ctx = {"failure_type": "FM-4"}
    out = suggest_targeted_recipe_drafts(
        client=dummy_client,  # type: ignore[arg-type]
        context=ctx,
        count=1,
    )
    assert out == [draft]
    assert captured["context"] == ctx
    assert captured["count"] == 1

