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

---

## 🔒 IMPLEMENTATION CONTRACT

**Files to inspect before writing any code:**
- `frontend/lib/screens/recipe_builder_screen.dart` (FE-4 output) — `LlmSuggestSheet` is opened from the "LLM assist" button here; the sheet hands a recipe draft back to the builder on "Use this"
- `frontend/lib/services/api_service.dart` — add `suggestRecipes(query, k, seed?)` (`POST /api/v1/llm/suggest`) and `generateRecipe(suggestionId)` (`POST /api/v1/llm/generate`) here; do not make HTTP calls from inside the widget
- `frontend/lib/features/agent/agent_pane_screen.dart` — existing LLM flow screen; use its loading/error state patterns as a reference

**Backend dependency:** `POST /api/v1/llm/suggest` (AI-1) and `POST /api/v1/llm/generate` (AI-2) must exist before this widget can be tested end-to-end.

**Do NOT create:**
- Direct HTTP calls inside `LlmSuggestSheet` — use service methods
- A multi-turn refinement loop
- Suggestion persistence (ephemeral; the backend cache handles 30 min TTL)

---

## 🧠 PRE-IMPLEMENTATION ANALYSIS

Before writing any code, perform the following in order:

1. **Read `frontend/lib/screens/recipe_builder_screen.dart` (FE-4 output).** Find the "LLM assist" button stub and confirm the callback/navigation used to open `LlmSuggestSheet` and receive the recipe draft back.
2. **Read `frontend/lib/services/api_service.dart`.** Note the pattern for existing LLM calls (e.g., `agent_api.dart`); add `suggestRecipes()` and `generateRecipe()` following the same pattern.
3. **Read `frontend/lib/features/agent/agent_pane_screen.dart`.** Note how loading spinners, error toasts, and empty states are handled — replicate these patterns in `LlmSuggestSheet`.
4. **Decide viewport-responsive layout:** `Drawer`-style side sheet on wide viewports, bottom sheet on narrow. Confirm the Flutter approach (e.g., `DraggableScrollableSheet` vs. `Drawer`) before writing the scaffold.
5. State the `LlmSuggestSheet` API (how it receives the query, how it hands back a recipe draft) before writing code.

---

## ✅ POST-IMPLEMENTATION VALIDATION

After implementation, verify each of the following:

- [ ] `LlmSuggestSheet` makes no direct HTTP calls — all calls go through `api_service.dart` methods
- [ ] Loading state shows skeleton cards while `POST /api/v1/llm/suggest` is in flight; "Suggest" button is debounced 350 ms
- [ ] Each `SuggestionCard` shows name, one-liner, hero ingredients as chips, est. macros labeled "approx.", and "Use this" CTA
- [ ] "Use this" triggers `POST /api/v1/llm/generate` with a progress indicator; on success, sheet closes and Recipe Builder is populated with the draft (not yet saved)
- [ ] Duplicate response (`duplicate_of` in response) shows confirmation: "Open existing?" / "Regenerate anyway"
- [ ] `LLM_SCHEMA_ERROR` → toast + sheet stays open; `INGREDIENT_UNRESOLVED` → inline banner with ingredient name + "Retry without it" CTA
- [ ] Max one retry per suggest stage; second reject-all closes sheet with tooltip
- [ ] Wide viewport: `Drawer`-style; narrow: bottom sheet
- [ ] Widget tests pass: happy path, reject-all, duplicate handling, error surfaces
