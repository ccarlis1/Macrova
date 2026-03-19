# System Rules — Meal Planning

This document records product-level rules referenced by `MEALPLAN_SPECIFICATION_v1.md`. It is **normative** for planner behavior where the spec points here.

## Weekly micronutrient minimum (τ)

- **`U.micronutrient_weekly_min_fraction`** (τ) is a float in **(0, 1]**, with default **`1.0`** (strict mode).
- **Strict mode (τ = 1.0):** For each tracked micronutrient `n`, plan completion requires  
  `W.weekly_totals[n] ≥ daily_RDI(n) × D` — i.e. the full **prorated weekly RDI** over the planning horizon `D`.
- **Relaxed mode (τ < 1.0):** The **hard minimum** for acceptance is  
  `W.weekly_totals[n] ≥ τ × daily_RDI(n) × D` for every tracked `n`. This is a **documented product option**; implementations should surface transparency (e.g. warnings when achieved intake is below the full prorated RDI but still above the τ floor). See MEALPLAN Specification Section 6.6 and reporting notes for FM-4.
- **Monotonicity:** Raising τ (e.g. from 0.9 to 1.0) can only shrink the set of acceptable plans; it never relaxes requirements.

## Upper limits (UL)

- **τ does not apply to UL enforcement.** Daily UL checks (HC-4, FC-3, incremental UL validation) use resolved UL values only. A plan must not be accepted solely because τ relaxed the RDI floor while a day still exceeds a non-null UL.

## Sodium advisory vs τ

- The **sodium advisory** threshold (**e.g. 200% of the user’s stated sodium RDI, scaled by `× D` over the horizon**) is evaluated against **`daily_RDI_sodium × D`**, **not** multiplied by τ. The advisory compares the plan to the user’s **goal line**, independent of the relaxed minimum used for hard weekly micronutrient acceptance.

## Preference vs feasibility

- Preference scoring **must not** override nutrition feasibility: if a more-preferred recipe would make the plan unable to satisfy hard constraints or feasibility checks, a less-preferred recipe that preserves feasibility is required (see MEALPLAN Specification Section 5 and scoring notes).
