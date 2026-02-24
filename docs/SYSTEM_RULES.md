# Nutrition Agent – Hard Constraints

## Ingredient Parsing Strategy (AUTHORITATIVE)

### MVP Constraint: Simple, Deterministic Parsing Only
- The system uses a **SIMPLE, DETERMINISTIC** ingredient parser in the MVP
- Ingredient input is expected to be **STRUCTURED** (explicit name, quantity, unit)
- **NO** probabilistic, NLP-based, or heuristic ingredient parsing is allowed
- **NO** third-party open-source ingredient parsers may be integrated in MVP

### Rationale (DO NOT OVERRIDE)
- Nutritional accuracy, especially for micronutrients and UL enforcement, requires deterministic inputs
- Silent parsing errors are **unacceptable** for this system
- USDA FoodData Central is the authoritative source of nutrition data, not free-text parsing heuristics
- "Smart" parsing (LLM-based or NLP-assisted) will be added later as a separate, opt-in layer

### Implementation Requirements
- Parse only concrete, explicit data (name, amount, unit)
- Validate inputs strictly
- **Fail fast** on ambiguous or unsupported units
- Prefer user correction over guessing
- All parsing behavior MUST be testable and deterministic

### Future Extension (DO NOT IMPLEMENT NOW)
- A separate parsing adapter layer may be introduced post-MVP
- That layer may suggest parsed ingredients but MUST NEVER silently override structured input
- That layer will be implemented only after LLM integration

### USDA API Integration Assumptions
- Accepts **structured inputs only** (normalized ingredient name, quantity in base units)
- Requires exact or aliased ingredient names (no fuzzy matching in MVP)
- Returns nutrition data for deterministic lookup
- Fails explicitly if ingredient not found (no silent fallbacks)

---

## Ingredient Handling
- Ingredients marked "to taste" MUST:
  - Appear in recipe output
  - Be excluded from all macro and micronutrient calculations
  - Be flagged as is_to_taste = true in parsed output

## Nutrition Calculation
- Only ingredients with explicit quantities contribute to nutrition totals
- Daily totals are the sum of meal totals
- Weekly micronutrient logic may allow daily variance but MUST meet weekly RDI

## Calorie Deficit Mode (Hard Constraint)
- When `max_daily_calories` is set in user profile:
  - Any meal plan exceeding this limit MUST be rejected (score = 0.0)
  - This is a HARD constraint, not a soft preference
  - Enforced in both `RecipeScorer._score_balance_match()` and `MealPlanner._validate_daily_plan()`

## Upper Tolerable Intake (UL) Validation (Hard Constraint)
- ULs are **DAILY** limits — enforced per-day, NEVER averaged over the week
- Weekly tracking does NOT weaken daily UL enforcement
- No implicit weekly ULs exist — only daily limits
- Intake exactly at UL (==) is valid; only strict excess (>) triggers violation
- Reference ULs loaded from `data/reference/ul_by_demographic.json`
- User overrides from `upper_limits` section in `user_profile.yaml` replace reference values

## Meal Planning
- A recipe may not appear more than once in a single day
- Meal slots are ordered and deterministic
- Tests define expected behavior over prose examples

## Scoring
- Low-fat meals are allowed when explicitly tagged as pre-workout
- Preference scoring MUST NOT override nutrition feasibility
