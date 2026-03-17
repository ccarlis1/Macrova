# Next Steps

# 1) Frontend Overhaul Roadmap

## Phase 1 — Environment Setup

### 1. Install Core Tooling

Install the required development tools:

- Flutter SDK
- Dart SDK (included with Flutter)
- Visual Studio Code
- Flutter & Dart VS Code extensions

Verify installation:

```
flutter doctor

```

Resolve any reported issues before continuing.

---

### 2. Create the Project

Create the base Flutter project:

```
flutter create meal_planner_app
cd meal_planner_app

```

Recommended platforms to enable:

```
flutter config --enable-web
flutter config --enable-windows-desktop
flutter config --enable-macos-desktop
flutter config --enable-linux-desktop

```

Run the starter app to confirm setup:

```
flutter run

```

---

## Phase 2 — Core Dependencies

Add the core dependencies required for the architecture.

### State Management

```
riverpod
flutter_riverpod

```

Purpose:

- application state
- reactive UI updates
- dependency injection

---

### Routing

```
go_router

```

Purpose:

- structured navigation between screens
- deep linking support
- cleaner route definitions

---

### Local Database

```
isar
isar_flutter_libs

```

Purpose:

- local ingredient cache
- recipe storage
- meal plan storage
- offline functionality

---

### Networking

```
dio

```

Purpose:

- HTTP client
- backend API communication
- FoodData Central queries

---

### Charts / Visualization

```
fl_chart

```

Purpose:

- macro distribution charts
- micronutrient RDA bars
- daily nutrition visualizations

---

### Dev Tools

```
build_runner
isar_generator
riverpod_generator

```

Purpose:

- code generation
- typed database models
- Riverpod providers

---

## Phase 3 — Project Structure

Create the following project structure:

```
lib/

core/
    api_client.dart
    constants.dart
    nutrition_calculator.dart

models/
    ingredient.dart
    recipe.dart
    recipe_ingredient.dart
    meal_plan.dart
    user_profile.dart

database/
    ingredient_db.dart
    recipe_db.dart
    meal_plan_db.dart

services/
    ingredient_service.dart
    recipe_service.dart
    planner_service.dart

providers/
    ingredient_provider.dart
    recipe_provider.dart
    planner_provider.dart
    profile_provider.dart

screens/
    dashboard_screen.dart
    profile_screen.dart
    ingredient_search_screen.dart
    recipe_builder_screen.dart
    recipe_library_screen.dart
    planner_screen.dart
    meal_plan_view_screen.dart

widgets/
    ingredient_list.dart
    ingredient_search_bar.dart
    nutrition_table.dart
    macro_chart.dart
    recipe_card.dart
    recipe_ingredient_row.dart

```

Goal:

- separate UI, data, services, and state logic.

---

## Phase 4 — Data Models

Define the core domain models.

### UserProfile

Stores:

- calorie targets
- macro ratios
- micronutrient goals
- meal timing preferences
- API keys

---

### Ingredient

Fields:

- id
- name
- nutrient values
- measurement conversions
- source (FoodData Central)

---

### Recipe

Fields:

- id
- name
- servings
- ingredient list
- calculated nutrients

---

### RecipeIngredient

Fields:

- ingredient reference
- quantity
- unit
- converted gram weight

---

### MealPlan

Fields:

- date range
- meals per day
- recipes assigned to meals
- daily nutrient totals

---

## Phase 5 — Local Database Implementation

Initialize the Isar database.

Collections to implement:

```
ingredients
recipes
mealPlans
userProfiles

```

Responsibilities:

Ingredient DB

- store cached USDA ingredients

Recipe DB

- store created recipes

Meal Plan DB

- store generated plans

---

## Phase 6 — API Layer

Create a centralized HTTP client.

File:

```
core/api_client.dart

```

Use the Dio client to implement API services:

Ingredient Service

Responsibilities:

- search FoodData Central
- fetch nutrient data
- convert API responses to Ingredient models

Planner Service

Responsibilities:

- send recipe pool
- send user nutrition targets
- receive generated meal plans

---

## Phase 7 — State Management

Implement Riverpod providers.

Providers should exist for:

IngredientProvider

- ingredient search
- cached ingredients
- ingredient loading state

RecipeProvider

- recipe creation
- recipe editing
- recipe library

PlannerProvider

- generate meal plans
- store planner results

ProfileProvider

- user nutrition settings

---

## Phase 8 — Core Screens

Implement screens in the following order.

---

### 1. Profile Screen

Features:

- editable nutrition targets
- macro ratio configuration
- micronutrient goals
- API key entry
- live calorie calculation

---

### 2. Ingredient Search Screen

Flow:

User searches ingredient  
→ API query  
→ result list  
→ nutrition preview  
→ add to local ingredient cache

Components:

- search bar
- result list
- ingredient preview card

---

### 3. Recipe Builder

Core interactive screen.

Features:

- search cached ingredients
- add ingredients
- choose quantity and units
- live nutrition totals
- set servings

Components:

- ingredient selector
- ingredient rows
- nutrition totals panel

---

### 4. Recipe Library

Features:

- list of created recipes
- recipe cards
- recipe editing
- recipe deletion

---

### 5. Meal Planner Screen

User defines planner parameters:

- number of days
- meals per day
- recipe pool

Planner request is sent to backend.

---

### 6. Meal Plan View Screen

Displays generated plan:

- meals per day
- recipes assigned to each meal
- daily nutrition totals
- weekly totals

Possible views:

- daily list
- calendar-style planner

---

## Phase 9 — Nutrition Visualization

Use fl_chart to display:

Macro Distribution

- protein
- fat
- carbohydrates

Micronutrient Coverage

- % of RDA per nutrient

Calorie Progress

- target vs consumed

---

## Phase 10 — Offline Support

Implement local-first behavior.

Workflow:

Ingredient Search  
→ API request  
→ store ingredient in Isar

Recipe Builder  
→ loads cached ingredients

Meal Planner  
→ runs even if API unavailable (when possible)

---

## Phase 11 — Testing

Test the following flows:

Ingredient caching  
Recipe creation  
Nutrition calculations  
Meal plan generation  
Offline usage



## Phase 12 — Deployment Targets

Build outputs from the same codebase:

Web PWA

```
flutter build web

```

Desktop Apps

```
flutter build windows
flutter build macos
flutter build linux

```

Mobile Apps

```
flutter build apk
flutter build ios

```

---

## Phase 13 — Future Enhancements

Potential improvements:

- AI recipe generation
- automatic grocery list generation
- nutrition optimization planner
- cloud sync
- multi-device support
- user accounts

---

## Development Philosophy

Focus on:

- simple interfaces
- fast data entry
- instant nutrition visibility
- reliable meal plan generation

UI polish can be improved after core functionality is stable.

---

# 3) Proposal: Improve Planner Branching Stability via Range-Based Feasibility (FC-1 Redesign)

## Background

Recent diagnostics of TC-3 revealed that the planner often encounters **branching factor = 1 at the final slot of each day**.

Example constraint funnel:

```
Slot (0,0): 33 → 16 → 15
Slot (0,1): 33 → 29 → 25
Slot (0,2): 33 → 29 → 25
Slot (0,3): 25 → 1

```

The final slot collapses to a **single viable candidate** because **FC-1 (macro feasibility)** enforces an **exact-fit constraint (±10%) at every slot**.

This creates several problems:

```
• Very fragile search trees
• Forced recipe choices at the final slot
• Frequent cross-day backtracking
• High sensitivity to small constraint changes

```

Even though the search algorithm is correct, this constraint design **over-prunes the search space too early**.

---

## Root Cause

The planner currently performs **point feasibility checks**:

```
current_macro + recipe_macro must be within ±10% of target

```

However, early slots should not enforce exact fits because **future slots still exist to adjust totals**.

Constraint solvers normally perform **range feasibility checks** instead of point checks during partial assignments.

---

## Proposed Change

Replace **point-based FC-1 checks** with **range-based feasibility checks** for all non-final slots.

### Current Behavior

```
if current_total + recipe_value not within target ± tolerance:
    reject candidate

```

### Proposed Behavior

Evaluate whether the remaining slots could still correct the totals:

```
current_total + recipe_value + max_remaining ≥ target_min
current_total + recipe_value + min_remaining ≤ target_max

```

Where:

```
max_remaining = best possible nutrients from remaining slots
min_remaining = lowest possible nutrients from remaining slots

```

This ensures that a candidate is rejected **only if the final target is mathematically unreachable**.

---

## Example

Target daily calories:

```
2000 ± 10%  →  [1800, 2200]

```

Current state after lunch:

```
current = 1100
slots remaining = 1
candidate dinner = 900 calories

```

### Current logic

```
1100 + 900 = 2000 → OK

```

But many candidates fail unnecessarily:

```
1100 + 850 = 1950 → OK
1100 + 800 = 1900 → OK
1100 + 700 = 1800 → OK
1100 + 650 = 1750 → REJECT

```

### Proposed logic

Check if the final target range is still reachable:

```
1100 + candidate + remaining_range overlaps [1800,2200]

```

This allows **multiple candidates instead of one**, dramatically improving branching.

---

## Expected Benefits

### Larger Branching Factor

Final slot will no longer collapse to a single candidate.

Typical branching:

```
current: 1 candidate
expected: 4–10 candidates

```

---

### Reduced Backtracking

Because early slots will not over-constrain the day.

Expected improvement:

```
50–90% reduction in backtracking depth

```

---

### Improved Search Stability

The planner will become **less sensitive to small changes in recipe pools** or nutrient targets.

---

## Implementation Outline

1. Modify FC-1 macro feasibility logic.
2. Compute remaining slot bounds:

```
min_remaining
max_remaining

```

1. Replace point checks with range feasibility checks.
2. Preserve the existing **exact-fit validation at day completion**.

Exact-fit validation remains necessary to ensure the final plan respects tolerances.

---

## Alternative / Complementary Improvements

The following improvements may further enhance planner performance:

### Slot Ordering (Fail-First Heuristic)

Schedule the **most constrained slot first**, such as dinner.

```
dinner → lunch → breakfast

```

---

### Recipe Value Ordering

Prioritize recipes that contribute strongly toward remaining nutrient deficits.

Example:

```
iron deficit → try high-iron recipes first

```

---

### Adaptive Tolerance

Allow wider tolerances in early slots:

```
slot 0 → ±40%
slot 1 → ±30%
slot 2 → ±20%
slot 3 → ±10%

```

---

## Risks

Low.

The change **does not weaken final plan correctness**, because final validation still enforces:

```
target ± tolerance

```

The modification only prevents premature pruning.

---

# Success Criteria

The change is successful if:

```
• TC-3 passes consistently
• branching factor at final slots > 1
• backtracking depth decreases significantly
• valid plans remain unchanged

```

---

## Priority

**High**

This change will substantially improve the planner’s robustness and scalability as more recipes and constraints are added.