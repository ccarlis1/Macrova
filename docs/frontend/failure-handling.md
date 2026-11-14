# Frontend plan failure handling

How Flutter surfaces planner outcomes. Backend contracts are unchanged; the UI consumes existing `PlanResponse` fields.

**Source:** `frontend/lib/models/models.dart`, `frontend/lib/widgets/failure_view_model.dart`, `frontend/lib/screens/today_screen.dart`, `frontend/lib/screens/meal_plan_view_screen.dart`. Contract detail: [plan-response.md](../contracts/plan-response.md).

## Branch key: `plan_status`

UX branching uses **`plan_status`** (`success` | `partial` | `failed`), not `success` and not `termination_code`.

| `plan_status` | UI |
| --- | --- |
| `success` | Meals + optional advisories from `warnings` |
| `partial` | Meals **and** `FailurePanel` |
| `failed` | `FailurePanel` (meals usually empty) |

## Actionable failures: `report.failures[]`

`report.failures[]` (`PlanFailure`) is the source of truth for actionable planner failures.

`FailureViewModel` maps the first failure → `FailurePanel`:

| `PlanFailure` | `FailurePanel` |
| --- | --- |
| `code` | `terminationCode` |
| `message` | `cause` |
| `fix_hint` | `fixHint` |

If `plan_status != success` but `failures` is empty, use incomplete messaging from `plan_status_message` (label `Incomplete plan`).

## Warnings ≠ failures

- **Failures** → `FailurePanel` (user must act).
- **Warnings** → `AdvisoryCard` advisories **only when** `plan_status == success`.
- Do not treat success-with-warnings as a failure.

## HTTP `ApiException` (no in-body plan)

When the provider has an error and no plan:

- If `errorCode` starts with `FM-` → `FailurePanel`.
- Else → `AdvisoryCard` (generic planning error).

Planner `FM-*` outcomes normally arrive as **HTTP 200** with `report.failures[]` (see contract doc). HTTP-mapped `FM-*` is the exception path.

## Do not

- Parse `termination_code` for UI branching (`TC-*` is telemetry only).
- Regex or scrape strings like `"Planner ended with…"`.
- Invent failure codes or fix hints not present on `PlanFailure`.
