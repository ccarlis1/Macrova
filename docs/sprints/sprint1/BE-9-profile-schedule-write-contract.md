# BE-9 — Profile schedule write contract

**Status:** implemented  ·  **Complexity:** S  ·  **Depends on:** DM-4

## Endpoint

- `PUT /api/v1/profile/schedule`
- Request body is canonical `schedule_days` and fully replaces persisted `schedule_days`.
- Writes to existing profile path (`config/user_profile.yaml` by default; override via `NUTRITION_USER_PROFILE_PATH`).
- Response returns normalized persisted `schedule_days`.

## Request Schema

```json
{
  "schedule_days": [
    {
      "day_index": 1,
      "meals": [
        {
          "index": 1,
          "busyness_level": 2,
          "preferred_time": "07:30",
          "required_tag_slugs": ["high-protein"],
          "preferred_tag_slugs": ["quick-meal"]
        }
      ],
      "workouts": [
        {
          "after_meal_index": 1,
          "type": "PM",
          "intensity": "moderate"
        }
      ]
    }
  ]
}
```

Supported fields:

- `MealSlot`: `index`, `busyness_level`, `preferred_time`, `required_tag_slugs`, `preferred_tag_slugs` (plus optional canonical `tags` passthrough).
- `WorkoutSlot`: `after_meal_index`, `type`, `intensity`.
- `DaySchedule`: `meals`, `workouts` (with `day_index`).

## Response Schema

```json
{
  "schedule_days": [
    {
      "day_index": 1,
      "meals": [
        {
          "index": 1,
          "busyness_level": 2,
          "preferred_time": "07:30",
          "required_tag_slugs": ["high-protein"],
          "preferred_tag_slugs": ["quick-meal"]
        }
      ],
      "workouts": [
        {
          "after_meal_index": 1,
          "type": "PM",
          "intensity": "moderate"
        }
      ]
    }
  ]
}
```

Normalization guarantees:

- `schedule_days` sorted by `day_index`
- `meals` sorted by `index`
- `workouts` sorted by (`after_meal_index`, `type`)
- optional `None` fields omitted from persisted/returned payload

## Validation Errors

Stable 400 error envelope:

```json
{
  "error": {
    "code": "PROFILE_SCHEDULE_INVALID",
    "message": "Invalid profile schedule.",
    "details": {
      "field_errors": [
        {
          "code": "INVALID_FIELD",
          "field_path": "schedule_days.0.meals.1.index",
          "message": "Meal indices must be contiguous 1..2; got [1, 1]"
        }
      ]
    }
  }
}
```

Validation rules enforced:

- reject duplicate/non-contiguous `MealSlot.index` within a day
- reject non-1-based meal indexes and `busyness_level=0`
- reject unknown fields (`extra="forbid"` stays enforced)
- reject invalid `required_tag_slugs` / `preferred_tag_slugs` shapes or unknown slugs
- reject missing/empty/invalid `schedule_days`
- reject non-contiguous `day_index` sequence in submitted `schedule_days`

## Workout Modeling Rule

Workouts must be represented only with canonical `WorkoutSlot` entries under `schedule_days[].workouts[]`.
Do not encode workouts as `MealSlot.busyness_level=0`. Legacy top-level `schedule` is removed on write.

## Idempotency

Equivalent payloads are persisted to the same normalized shape and repeated `PUT` requests return the same response body.

## Out of Scope

- Frontend editor implementation (FE-8)
- Planner behavior changes
