# Research Alignment Audit and Long-Term Roadmap

**Status:** Proposed (architectural planning document)
**Basis:** *Adaptive, Low-Effort Meal Planning as a Human-Centered Sequential Decision Problem* (conceptual paper, `nutri-research/planner_problem_v2.md`) audited against Macrova as of v0.1.0.
**Audience:** Maintainers making multi-quarter architectural decisions. This is not a sprint plan.

---

## 1. Framing

The research paper reformulates meal planning: the value of a plan is not its offline score, but the **expected value of what the household actually executes** — `Pr(exec | P, s) · V(P, s) − C_interaction` — under a state that includes inventory, prices, schedule, health constraints, preferences, and *behavioral state* (habit, trust, receptivity, cumulative choice burden), all with transition dynamics.

Macrova today solves a different, narrower problem: **deterministic constrained feasibility search over a static recipe pool against a static profile**. That narrower problem corresponds to the paper's "constrained decision-making" layer only, evaluated purely offline. This is not a defect — it is the correct foundation per the paper's own architecture (verified data + constrained optimization for safety comes first). But it means most of the formulated problem is currently out of scope of the implementation, and some current design decisions will actively resist the evolution the paper calls for. Both are documented below.

Verdict in one sentence: **Macrova has built a credible safety kernel and feasibility solver, a correctly bounded LLM layer, and almost none of the state estimation, closed-loop, repair, or behavioral machinery that the problem formulation says determines real-world value.**

---

## 2. System Alignment Audit

### 2.1 Mapping to the paper's four coupled layers

| Paper layer | Macrova status | Evidence |
| --- | --- | --- |
| 1. State estimation | **Largely absent.** State = user-authored YAML profile + recipe JSON. No inventory `I_t`, no prices `p_t`, no behavioral state `b_t`, no feedback history `h_t`. Nothing is estimated; everything is declared. | `src/data_layer/user_profile.py`, `src/planning/converters.py` |
| 2. Constrained decision-making | **Substantially implemented, offline-only.** Hard constraints, forward checks, per-day ULs, multi-day RDI carryover, deterministic backtracking. Scores candidates by offline composite, not expected executed value. | `src/planning/phase2_constraints.py`–`phase7_search.py` |
| 3. Interaction and control | **Minimal.** Structured config forms + optional NL parsing. No value-of-information question selection, no burden budget, no decision about when to explain or ask. | `src/llm/constraint_parser.py`, Flutter screens |
| 4. Behavior and learning | **Absent.** No consumption/skip/substitution logging, no preference update, no adherence signal of any kind. The loop is open. | (no corresponding module exists) |

### 2.2 Mapping to the paper's reference architecture (Design Implications, items 1–7)

**(1) Provenance-aware data layer — partial, with a real gap.**
The provider abstraction (local JSON / USDA FDC) and up-front ingredient resolution are correct structure. But `source_metadata` captured in `src/ingestion/usda_client.py` is effectively dropped: values are collapsed into exact `NutritionProfile` numbers with no source, version, serving-basis, or uncertainty retained downstream. The paper is explicit that Branded-vs-Foundation provenance and label rounding introduce material uncertainty; Macrova currently presents false precision. Missing values and unresolved ingredients are handled strictly (fail loudly, not silently-as-zero), which is aligned — the "silent infeasibility" failure mode is partially mitigated.

**(2) Safety kernel — the strongest area, correctly separated.**
Typed hard constraints (allergen/ingredient exclusions, `max_daily_calories`, per-day ULs never averaged), constraint precedence (batch lock → pin → required tags → preferred scoring), structured failure modes (`FM-1`…`FM-5`, `FM-TAG-EMPTY`, `FM-BATCH-CONFLICT`, `FM-MACRO-INFEASIBLE`) with stable `fix_hint`s, and the rule that LLM output never bypasses validation (`src/llm/pipeline.py`: generate → parse strict schema → resolve → recompute nutrition → persist only if validated). This directly implements the paper's demands that safety constraints be separated from preferences, that infeasibility be reported rather than papered over, and that LLMs be interface components, not sources of truth. The tag lifecycle (`proposed` → validated → `approved`; only approved tags may act as hard constraints) is a textbook instance of "safety-constraint leakage" prevention.

Gap within the strength: safety constraints are all *exclusion-shaped*. There is no typed distinction between a dislike, an allergy, and a clinical restriction (renal, diabetes, pregnancy, interactions), no escalation path, and no severity-weighted violation reporting. The paper treats these as different objects with different relaxation semantics; Macrova encodes them all as the same exclusion list.

**(3) Multi-objective planner exposing trade-offs — misaligned by construction.**
`phase4_scoring.composite_score` collapses nutrition fit, time fit, variety penalty, and balance into a single scalar, and `phase7_search` returns the **first complete valid assignment** under that ordering. This is a satisficing solver presenting a "falsely authoritative single optimum" — the exact anti-pattern named in the paper. There is no objective vector `f(P)` reported per plan, no Pareto frontier, no way for a user (or a future ranker) to see that plan A trades variety for time against plan B. Cost (money), effort (beyond cooking-time-vs-slot heuristics), and waste are not objectives at all — they cannot be, because prices and inventory don't exist in the state.

**(4) Execution-aware ranker — absent.**
No `Pr(exec)` model, no random-utility layer, nothing that discounts a nutritionally perfect but high-effort plan. The composite score is implicitly a proxy for "good plan," with no adherence grounding. Nothing shapes ranking by what the household has historically actually cooked.

**(5) Repair controller — absent, and the current architecture resists it.**
Planning is a stateless function call: profile + pool → `MealPlanResult`. There is no persisted plan identity, no diff between a previous accepted plan and a new one, no stability distance `D(P_t, P_{t-1})`, and no repair-vs-replan decision. Any disturbance (a skipped meal, a missing ingredient, a schedule change) can only be handled by full replanning from scratch — which, because search order is score-driven, may reshuffle meals the user had already committed to. This is the paper's "plan thrashing" failure mode built into the API contract. Pins and meal-prep batch locks are the embryo of a stability mechanism (they can freeze parts of a plan), but nothing generates them automatically from a prior plan.

**(6) Low-burden interaction layer — partial.**
NL config parsing maps text to explicit planner config before planning (correct direction: elicitation → typed constraints, never LLM → plan). Planner feedback (`orchestrator.plan_with_llm_feedback`) explains failures and suggests targeted changes rather than silently mutating constraints — aligned with the override-visibility principle. But there is no notion of interaction cost anywhere: no burden budget, no VOI-gated questions, no measurement of prompts/choices/corrections. The current UX assumption (user hand-authors recipes, profile, and tags) is exactly the "burden inversion" risk the paper warns about: setup cost currently exceeds what unaided planning would cost most households.

**(7) Evaluation and audit layer — stage 1 only.**
The pytest suite, contract tests, and OpenAPI snapshot discipline satisfy the paper's "verification and stress testing" stage well. `scripts/benchmark_meal_plan_search.py` measures runtime, not plan quality. There is no offline benchmark suite with disturbance injection, no override/decision audit log, no instrumentation for adherence or workload, and obviously no field-trial machinery. Model/data versioning of plans (which recipe DB version, which provider, which tag registry produced this plan) is not recorded on results.

### 2.3 Failure-mode scorecard (paper §Failure Modes)

| Failure mode | Covered? |
| --- | --- |
| 1. Feasible but unfollowed | ✗ — no execution model; this is the roadmap's center of gravity |
| 2. Proxy optimization | ✗ (not yet applicable — no learning loop to misalign; becomes live at Horizon 3) |
| 3. Silent infeasibility | ◐ — strict up-front resolution and structured failures; provenance/units uncertainty still collapsed |
| 4. Safety-constraint leakage | ✓ — validation pipeline + tag lifecycle are genuinely strong here |
| 5. Monotony collapse | ◐ — variety penalty and HC-8 repetition constraint exist; no sensory/temporal model, no staple designation |
| 6. Plan thrashing | ✗ — full replan is the only mechanism |
| 7. Burden inversion | ✗ — high-effort manual data entry, unmeasured |
| 8. Cold-start exclusion | ◐ — rule-based core has no learning cold-start, but small hand-built recipe pools produce brittle/failed plans for exactly the users with least capacity to author data |
| 9. False clinical authority | ◐ — no clinical claims made, but also no typed clinical boundary or escalation; ULs are the only clinical-grade mechanism |

### 2.4 What is correctly implemented (keep, do not churn)

- Deterministic, auditable feasibility core with structured, user-actionable failure reporting.
- Safety/preference separation and constraint precedence.
- The LLM containment contract (validate-before-persist, NL → typed config, proposed-tag lifecycle).
- Provider abstraction with no network calls during planning.
- Per-day UL enforcement (never averaged) and weekly deficit carryover — a defensible nutrient-adequacy averaging policy of the kind the paper says must be made explicit.
- Meal-prep batches and pins — these become the substrate for plan stability later.

These map cleanly onto the paper's hybrid-architecture recommendation ("verified data and constrained optimization for safety"). The roadmap below *adds layers around* this core; nothing in it requires making the core nondeterministic.

---

## 3. Roadmap

Ordering principle: each horizon makes the *next* horizon's problem well-posed. You cannot model execution probability (H3) without execution observations (H2); you cannot observe execution against a plan that has no persistent identity (H1); you cannot rank by expected executed value if the planner emits a single scalar-scored optimum (H1). Cost/waste objectives are meaningless without inventory and price state (H2).

### Horizon 0 — Make the current core honest about what it knows (foundation hardening)

*Goal: eliminate false precision and false authority without changing planner behavior.*

1. **Typed constraint taxonomy.** Split the flat exclusion list into typed classes: `allergen`, `clinical`, `dislike`, `preference`, each with declared relaxation semantics (never / escalate / soft-penalize). Failure reports gain severity: an infeasibility caused by an allergen constraint is not the same object as one caused by a dislike. This is a data-model and reporting change, not a search change.
2. **Provenance and uncertainty propagation.** Carry `source`, `data_type` (Foundation/Branded/local), `fdc_version`, and serving-basis metadata from `usda_client` through `NutritionProfile` into `MealPlanResult.report`. Initially display-only ("this plan's iron total is based on 3 branded-label values"). No robust optimization yet — just stop discarding the information robust methods will later need.
3. **Objective vector reporting.** Compute and attach the paper's `f(P)` vector (nutrient deviation, time/effort, variety, monotony; cost/waste as placeholders) to every result alongside the composite score. The composite still drives search ordering; the vector makes trade-offs visible and gives later horizons a stable interface.
4. **Plan provenance stamping.** Every `MealPlanResult` records recipe-DB hash, tag-registry version, provider identity, and planner version. Prerequisite for any longitudinal comparison and for the audit layer.
5. **Offline benchmark harness.** Standardized planning instances (varied pool sizes, tight/loose macros, adversarial safety cases) measuring feasibility rate, failure-mode distribution, objective-vector quality, and runtime — not just runtime. Includes the FC-1 range-feasibility redesign already proposed in `future-plans.md` (branching-factor collapse is a robustness problem this harness should measure before/after).

*Exit criteria:* constraint classes are typed end-to-end; every plan carries provenance and an objective vector; benchmark suite runs in CI.

### Horizon 1 — Plans as persistent, repairable objects

*Goal: kill "full replan is the only operation." This is the highest-leverage architectural change in the roadmap.*

1. **Persistent plan store.** Plans get identity, lifecycle state (`draft` / `accepted` / `in-progress` / `completed`), and per-slot status. The API grows from "generate" to "generate / accept / amend."
2. **Stability distance.** Implement `D(P_t, P_{t-1})` = weighted count of changed meals + invalidated sunk commitments (meal-prep batches already cooked, shopped items once inventory exists) + new decisions imposed. Report it on every regeneration.
3. **Repair as constrained replan.** Implement repair *on top of the existing solver*, not beside it: given an accepted plan and a disturbance, auto-pin all unaffected slots (the pin mechanism already exists), re-search only the affected region, and expand the unpinned region iteratively if infeasible. Escalation ladder per the paper: single-slot substitution → bounded-region repair → full replan, each step reported with its stability distance. Deterministic throughout — repair here is search-space restriction, not a new algorithm.
4. **Disturbance vocabulary.** Typed disturbances as API inputs: `slot_skipped`, `recipe_unavailable`, `schedule_changed`, `ingredient_missing`, `constraint_changed(structural)`. Structural changes (new allergy, household change) route directly to full replan — matching the paper's controller sketch.
5. **Frontier exposure (bounded).** Return top-k *meaningfully different* feasible plans (differing in objective-vector profile, not near-duplicates) instead of one. This is the "expose trade-offs" requirement in its cheapest form and gives H3's ranker something to rank.

*Exit criteria:* a mid-week disturbance produces a repaired plan with minimal stability distance and an explicit report of what changed and why; benchmark harness measures repair success rate and stability under injected disturbances (paper Table 2, "Adaptation quality" row).

### Horizon 2 — Household state: inventory, cost, and waste

*Goal: extend the state vector from (profile, recipes) toward (I_t, p_t, …) so that cost, effort, and waste become real objectives.*

1. **Pantry/inventory model.** Ingredient-level stock with quantities, package sizes, and optional perishability windows. Update sources, in order of ambition: plan acceptance (decrement on completion), shopping-list confirmation, and only later any manual logging — every logging touchpoint is interaction burden and must be optional (burden-inversion guardrail: the planner must degrade gracefully to "no inventory known" rather than demand data entry).
2. **Shopping-list generation.** Plan → aggregate ingredient needs − inventory → list with package-size rounding. The rounding residual *is* the waste signal: purchased-minus-needed for perishables becomes `f_waste`.
3. **Price data.** Static per-ingredient price table first (user- or region-supplied), API sources later. Enables `f_cost` and a hard budget constraint `C(P) ≤ B_t` in the existing constraint framework.
4. **Leftovers and batch cooking as planner-native.** Extend the meal-prep batch mechanism into general leftover allocation: cooking 4 servings on Monday makes Tuesday's slot a near-zero-effort candidate. This changes candidate generation (a slot candidate can be "leftover of assignment (d′, s′)") and is the single biggest lever on the *effort* objective.
5. **Vulnerable-inventory scoring.** Soft objective preferring recipes that consume expiring stock (the paper's use-up-day evidence), gated by feasibility as always.

*Exit criteria:* a plan for a user with inventory + prices reports cost, projected waste, and a shopping list; benchmark instances cover inventory-constrained planning.

### Horizon 3 — Closing the loop: observation, preference learning, execution-aware ranking

*Goal: move plan value from offline score toward expected executed value. This horizon introduces learning, and therefore introduces the paper's proxy-optimization and preference-manipulation risks — the guardrails are part of the horizon, not an afterthought.*

1. **Low-burden execution feedback.** Per-slot: eaten / skipped / substituted-with-X, one tap, always skippable. Missing data ≠ non-adherence (paper Table 2, Behavior row); model it as missing.
2. **Preference state `θ_t` with cautious updates.** Learn recipe/ingredient/cuisine affinities from execution and substitution history — but never auto-promote an inference to a hard constraint, and never interpret a single skip as dislike (the paper: skips confound time, inventory, illness, circumstance). Inferred preferences are visible and user-editable; hard exclusions remain user-declared only. The safety kernel is untouched by learning, structurally.
3. **Execution-probability model.** Start with a calibrated logistic/discrete-choice model over interpretable features (effort vs. slot busyness, recipe familiarity/repetition, past execution rate for similar slots, plan-change recency). No RL. Report calibration (predicted vs. observed execution) as a first-class metric.
4. **Execution-aware ranking layer.** Architecture becomes: **deterministic solver generates the feasible top-k frontier (H1.5) → ranker orders by `Pr(exec)·V − burden`**. Feasibility and safety stay deterministic and auditable; only *ordering among safe plans* becomes model-informed. This preserves the repo's core invariant (deterministic planner, validated assistants) while implementing the paper's Equation 10.
5. **Welfare guardrails from day one of learning.** Variety floor that `Pr(exec)` optimization cannot erode (anti-monotony-collapse: the ranker must not learn to serve the same three easy meals), preference-shift audit (distribution of served cuisines/ingredients over time vs. baseline), and logging of every override.

*Exit criteria:* ranking is measurably better-calibrated than the offline composite at predicting what gets cooked; variety and preference-shift audits run automatically; all learning-derived influence on plans is inspectable.

### Horizon 4 — Behavioral state and adaptive interaction

*Goal: the remaining paper machinery — behavioral state transitions and burden-budgeted interaction. Deliberately last: it depends on longitudinal per-user data H3 only starts collecting, and the paper itself flags much of the underlying science as contested.*

1. **Behavioral state variables.** Habit strength per routine slot (schematic acquisition/decay per Equation 7), trust proxy (override and regeneration-abandonment rates), and cumulative interaction burden (prompts, choices, corrections per week — all directly measurable). Treat all three as *hypotheses with instrumentation*, per the paper's own caution about decision-fatigue and notification-churn claims.
2. **Burden budget.** A per-week interaction budget consumed by questions, confirmations, and prompts. Elicitation questions gated by expected decision value vs. interruption cost (VOI): the system asks about a dislike only when that answer would actually change the selected plan region.
3. **Repair controller uses behavioral state.** The H1 repair ladder's thresholds become functions of trust and habit state (Equation 13): protect habitual slots from churn; when trust is low (recent overrides), prefer minimal-change repairs and offer user control affordances rather than confident replans.
4. **Evaluation upgrade.** Instrumentation sufficient for microrandomized-style within-user comparisons of adaptation decisions (e.g., randomize repair-vs-replan at the margin and measure subsequent execution). This is the point where the paper's "adaptation quality" and "behavior" evaluation rows become causally interpretable rather than observational.

*Exit criteria:* repair/replan and ask/don't-ask decisions are driven by measured state under an explicit budget, and their effect on execution is estimated from designed variation, not anecdote.

### Explicit non-goals (from the paper's safety boundaries)

- **No medical nutrition therapy.** Clinical constraint types (H0.1) get conservative handling and "consult a professional" escalation, never automated management of renal/diabetic/pregnancy nutrition.
- **No end-to-end RL over plan generation.** The feasible set is always produced by the deterministic, auditable solver; learning only ever reorders and parameterizes within it.
- **No engagement maximization.** Retention/engagement are never optimization targets, only diagnostics — the paper's proxy-optimization warning is a standing constraint on every learning component.
- **No LLM authority expansion.** The existing containment contract extends unchanged to new surfaces (e.g., an LLM may *explain* a repair or draft a disturbance interpretation, but typed disturbances and the repair search stay deterministic).

---

## 4. Evaluation program mapping (paper Table 2 → repo)

| Construct | Exists today | Roadmap owner |
| --- | --- | --- |
| Safety & feasibility | pytest + contract tests, FM codes | H0.5 benchmark harness adds violation-severity and worst-case reporting |
| Plan quality | composite score (opaque) | H0.3 objective vector; H2 adds cost/waste terms |
| Interaction burden | none | H4.1 burden instrumentation (counts, time, corrections) |
| Adaptation quality | none (no repair exists) | H1 exit criteria: repair success, stability distance, time-to-repair under injected disturbances |
| Behavior | none | H2/H3 execution logging; predicted-vs-observed calibration |
| Longitudinal outcomes | none | Out of scope until a real user base exists; H4.4 provides the instrumentation prerequisite |
| Equity & accessibility | none | Standing benchmark dimension from H0.5: measure feasibility/quality gaps across small recipe pools, restrictive diets, and low-budget instances |

## 5. Known tensions to resolve deliberately

1. **Satisficing vs. frontier.** Moving from first-feasible to top-k meaningfully-diverse solutions (H1.5) has real search-cost implications; the FC-1 range-feasibility redesign should land first, and the benchmark harness must gate the change.
2. **Determinism vs. learned ranking.** The H3 architecture keeps the *solver* deterministic while the *ranking among safe plans* becomes personalized. AGENTS.md's "deterministic by default" invariant should be amended at that point to name this boundary precisely, rather than being silently reinterpreted.
3. **Data entry vs. state fidelity.** Every horizon-2 state variable (inventory, prices) is optional context, never a prerequisite. The system's floor behavior must remain "works like today with zero extra input."
4. **Single-user YAML vs. household.** The paper's unit is the household (shared meals, negotiation, sunk commitments imposed on others). The current single-profile model is fine through H2; H3's preference learning should decide explicitly whether `θ_t` is per-person or per-household before data starts accumulating in the wrong shape.
