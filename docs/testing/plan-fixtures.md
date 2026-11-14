# Plan response test fixtures

Rules for Flutter (and any client) fixtures that mimic `PlanResponse`.

## Code namespaces

| Field | Allowed values | Role |
| --- | --- | --- |
| `termination_code` | `TC-*` (e.g. `TC-2`) | Telemetry only |
| `report.failures[].code` | `FM-*` | Actionable failure |

**Never** put `FM-*` in `termination_code`. **Never** put `TC-*` in `report.failures[].code`.

## Minimal shapes

### Failed (no usable meals)

```json
{
  "success": false,
  "termination_code": "TC-2",
  "plan_status": "failed",
  "days": 1,
  "daily_plans": [],
  "goals": { "daily_calories": 2000, "daily_protein_g": 120, "daily_fat_g_min": 40, "daily_fat_g_max": 80, "daily_carbs_g": 200 },
  "warnings": [],
  "report": {
    "failures": [
      {
        "code": "FM-MACRO-INFEASIBLE",
        "message": "No feasible plan for macro targets",
        "details": {},
        "fix_hint": "Relax protein or calorie targets"
      }
    ]
  }
}
```

### Partial (meals + failure)

```json
{
  "success": false,
  "termination_code": "TC-2",
  "plan_status": "partial",
  "plan_status_message": "Only day 1 could be filled",
  "days": 1,
  "daily_plans": [ { "day": 1, "meals": [ /* … */ ], "totals": { /* … */ } } ],
  "goals": { /* … */ },
  "warnings": [],
  "report": {
    "failures": [
      {
        "code": "FM-MACRO-INFEASIBLE",
        "message": "…",
        "details": {},
        "fix_hint": "…"
      }
    ]
  }
}
```

### Success with warnings (advisories only)

```json
{
  "success": true,
  "termination_code": "OK",
  "plan_status": "success",
  "days": 1,
  "daily_plans": [ /* … */ ],
  "goals": { /* … */ },
  "warnings": ["Sodium advisory: weekly total high"],
  "report": { "failures": [] }
}
```

## Canonical fixture locations

- `frontend/test/screens/meal_plan_view_screen_test.dart`
- `frontend/test/screens/today_screen_test.dart`
- `frontend/test/providers/meal_plan_provider_cooked_test.dart`

UI expectations: show `FM-*` on `FailurePanel`; do not assert `TC-*` as the user-facing failure code. See [failure-handling.md](../frontend/failure-handling.md).
