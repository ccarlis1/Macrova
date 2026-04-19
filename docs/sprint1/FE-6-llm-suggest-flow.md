# FE-6 — LLM suggest → approve flow

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** AI-1, AI-2, FE-4

## Summary

Side sheet opened from the Recipe Builder's "LLM assist" button. Takes a free-text query, displays 3–5 suggestion cards, and routes the approved one into full generation.

## Context

Implements F4 in the UI. Keeps the LLM path opt-in (R3) and visible to the user before cost is paid.

## Acceptance criteria

- [ ] Side sheet widget `LlmSuggestSheet`:
  - Header: query text field + "Suggest" button.
  - Body: grid/stack of up to 5 `SuggestionCard`s.
  - Each card shows: name, one-liner, hero ingredients (chips), est. macros (labeled "approx."), "Use this" CTA.
  - Loading state with skeleton cards.
  - Empty state after reject-all: "Try a different query" + CTA.
- [ ] On "Use this": POST `/api/v1/llm/generate`, show a progress indicator until the recipe is returned, then close the sheet and hand the recipe draft to the Recipe Builder (populated, not yet saved).
- [ ] Duplicate response (AI-5) surfaces a confirmation: "This recipe already exists in your bank — open it?" with "Open" / "Regenerate anyway".
- [ ] Errors:
  - `LLM_SCHEMA_ERROR` → toast + keep sheet open.
  - `INGREDIENT_UNRESOLVED` → inline banner naming the ingredient, with a "Retry without it" CTA (re-runs generate with a refined suggestion_id comment; if backend doesn't support that, fall back to a fresh suggest).
- [ ] Max one retry per suggest stage; second reject-all closes the sheet with a tooltip ("Run again from the LLM assist button.").
- [ ] Widget tests cover suggest happy path, reject-all, duplicate handling, error surfaces.

## Implementation notes

- Use a `Drawer`-style side sheet on wide viewports, a bottom sheet on narrow.
- Debounce the "Suggest" button (350 ms); show button spinner while loading.
- Do not persist the suggestion list; it's ephemeral. The backend cache holds it for 30 min (AI-1).

## Out of scope

- Image display beyond a URL if the backend provides one.
- Multi-turn refinement.
