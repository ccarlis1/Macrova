# Sprint discussion

These are **future features, ideas, and follow-ups** to bring up in upcoming sprints, log so nothing gets lost.

**Keep in mind:** Whenever you notice something worth doing later—new features, bugs, refactors, copy or marketing angles, or any other general note—add it here (short bullet is enough). Review this file when planning the next sprint.

---

*Add items below as you discover them.*

- **Reject unconvertible units at recipe save (U1 c).** Today an unknown unit drops the recipe from the planning pool with `warnings.nutrition`. Also reject at `/api/v1/recipes/sync` and in the Flutter recipe editor so bad units never persist.
- **Send Flutter `unitConversions` to the backend.** Ingredient Hub collects grams-per-cup / grams-per-tbsp, but sync still sends raw `quantity`/`unit` and the server returns `"unit_conversions": {}`. Merge custom conversions into `grams_per_unit`.
- **Make Flutter `Ingredient.toGrams` fail closed.** It currently returns the raw quantity when a unit has no conversion (same silent fallback the backend had).
- **Map USDA `foodPortions` to `grams_per_unit`.** API-mode ingredients have no `grams_per_unit`, so volume units on USDA-only names leave the pool until portions are mapped.