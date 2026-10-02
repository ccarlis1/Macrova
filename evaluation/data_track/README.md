# §4.4 data track (E0 / E1 / E1b)

Measurement harness for nutrition computed the way `/api/v1/plan` does it,
versus stored benchmark nutrition and a hand-drafted reference panel.

**No `src/` changes.** Results answer reconciliation Q1 and inform Q2.
Stop at the decision gate before any fix.

## Commands (from repo root)

```bash
# E0 — reproduce local vs API-cache vs clean checkout (no network)
.venv/bin/python evaluation/data_track/reproduce.py

# Draft panel + fetch raw USDA records (needs USDA_API_KEY / network)
.venv/bin/python evaluation/data_track/draft_panel.py
.venv/bin/python evaluation/data_track/fetch_raw.py
.venv/bin/python evaluation/data_track/fill_panel_nutrition.py

# E1 — four-channel error decomposition
.venv/bin/python evaluation/data_track/decompose.py

# E1b — cache vs current NutrientMapper
.venv/bin/python evaluation/data_track/cache_audit.py
```

## Outputs

`raw/` and `results/*.json` are generated locally and gitignored; re-run the
commands above to rebuild them. `raw/` needs `USDA_API_KEY`; on a fresh clone
`fetch_raw.py` takes FDC IDs from `panel.json` (the local `.cache/ingredients/`
is only needed for `cache_audit.py`). Headline numbers are recorded in
[`results/decision_gate.md`](results/decision_gate.md) and the reports.

| File | Experiment |
|---|---|
| `results/e0.json` | Skip counts and kcal/protein deltas per config × library |
| `panel.json` | Draft reference panel (`review_status: draft`) |
| `raw/<fdc_id>.json` | Raw USDA payloads (offline re-runs) |
| `results/e1.json` | Channel shares of abs kcal / micronutrient error |
| `results/e1b.json` | Cache consistent vs superseded; keep/patch/rebuild |

## Configs (E0)

| Config | Meaning |
|---|---|
| `local-machine` | `data/ingredients/custom_ingredients.json` (untracked, 7 entries here) |
| `local-clean` | `custom_ingredients.json.example` (what a fresh clone gets) |
| `api-cache` | `.cache/ingredients/` with `usda_client=None` (cache only) |
| `api-clean` | Empty temp cache; `resolve_all` hard-fails (API path behaviour) |

## Panel review

`panel.json` was promoted to [`data/reference/ingredient_nutrition.json`](../../data/reference/ingredient_nutrition.json)
after the decision gate (Q2 = d+a). It is still a draft (`review_status: draft`):
the FDC choices have not been human-reviewed yet. Acai fruit has no suitable FDC fruit record
(`ground_truth_unavailable`); the beverage entry is best-effort.

Gate decisions: [`results/decision_gate.md`](results/decision_gate.md).
