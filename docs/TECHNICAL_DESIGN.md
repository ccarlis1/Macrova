# Technical Design Document

## Data Models

### Ingredient Model
```python
@dataclass
class Ingredient:
    name: str                    # Normalized name (e.g., "egg", "cream of rice")
    quantity: float              # Amount (e.g., 200.0, or 0.0 for "to taste")
    unit: str                    # Unit (e.g., "g", "oz", "cup", "tsp", "tbsp", "to taste")
    is_to_taste: bool = False    # True if ingredient is "to taste" (excluded from nutrition)
    normalized_unit: str         # Converted to base unit (e.g., "g" for grams)
    normalized_quantity: float   # Quantity in base unit
```

### Nutrition Profile Model
```python
@dataclass
class NutritionProfile:
    calories: float
    protein_g: float
    fat_g: float
    carbs_g: float
    # Micronutrients (post-MVP)
    # fiber_g: float
    # vitamin_e_mg: float
    # etc.
```

### Recipe Model (Minimal Format)
```python
@dataclass
class Recipe:
    id: str                      # Unique identifier
    name: str                    # Recipe name
    ingredients: List[Ingredient] # List of ingredients
    cooking_time_minutes: int     # Total cooking time
    instructions: List[str]       # Step-by-step instructions
    # Future fields (post-MVP):
    # cuisine_type: Optional[str]
    # tags: List[str]
    # difficulty: Optional[str]
```

### Meal Model
```python
@dataclass
class Meal:
    recipe: Recipe
    nutrition: NutritionProfile   # Calculated nutrition for this meal
    meal_type: str               # "breakfast", "lunch", "dinner", "snack"
    scheduled_time: Optional[str] # When to eat (optional)
    busyness_level: int          # 1-4 scale (1=snack, 2=15min, 3=30min, 4=30+min)
```

### Daily Meal Plan Model
```python
@dataclass
class DailyMealPlan:
    date: str                    # ISO date format
    meals: List[Meal]            # List of meals for the day
    total_nutrition: NutritionProfile  # Aggregated nutrition
    goals: NutritionGoals        # Target nutrition for the day
    meets_goals: bool            # Whether goals are met
```

### User Profile Model
```python
@dataclass
class UserProfile:
    # Nutrition Goals
    daily_calories: int
    daily_protein_g: float
    daily_fat_g: Tuple[float, float]  # (min, max) range
    daily_carbs_g: float              # Calculated from remaining calories
    
    # Schedule Constraints
    schedule: Dict[str, int]     # {"08:00": 2, "12:00": 3, "18:00": 3}
                                 # Time -> busyness level (1-4)
    
    # Preferences
    liked_foods: List[str]       # Foods to prefer
    disliked_foods: List[str]    # Foods to avoid
    allergies: List[str]         # Allergens to avoid
    
    # Future (post-MVP)
    # meal_prep_meals: List[Meal]
    # weekly_targets: Dict[str, float]
```

## Data Storage Formats

### Recipe JSON Format
```json
{
  "recipes": [
    {
      "id": "recipe_001",
      "name": "Preworkout Meal",
      "ingredients": [
        {"quantity": 200, "unit": "g", "name": "cream of rice"},
        {"quantity": 1, "unit": "scoop", "name": "whey protein powder"},
        {"quantity": 1, "unit": "tsp", "name": "almond butter"},
        {"quantity": 50, "unit": "g", "name": "blueberries"}
      ],
      "cooking_time_minutes": 5,
      "instructions": [
        "Cook cream of rice according to package directions",
        "Mix in protein powder",
        "Top with almond butter and blueberries"
      ]
    }
  ]
}
```

### Ingredient Nutrition JSON Format
```json
{
  "ingredients": [
    {
      "name": "cream of rice",
      "per_100g": {
        "calories": 370,
        "protein_g": 7.5,
        "fat_g": 0.5,
        "carbs_g": 82.0
      },
      "aliases": ["cream of rice", "rice cereal"]
    },
    {
      "name": "whey protein powder",
      "per_scoop": {
        "calories": 120,
        "protein_g": 24.0,
        "fat_g": 1.0,
        "carbs_g": 3.0
      },
      "scoop_size_g": 30,
      "aliases": ["protein powder", "whey", "protein"]
    }
  ]
}
```

### User Profile YAML Format
```yaml
# User Profile Configuration
nutrition_goals:
  daily_calories: 2400
  daily_protein_g: 150  # 0.7g per lb bodyweight (example)
  daily_fat_g:
    min: 50
    max: 100
  # Carbs calculated automatically: (calories - protein*4 - fat*9) / 4

schedule:
  # Format: "HH:MM": busyness_level
  # 1 = snack (< 5 min)
  # 2 = quick meal (≤ 15 min)
  # 3 = weeknight meal (≤ 30 min)
  # 4 = weekend/meal prep (30+ min)
  "07:00": 2  # Morning: quick meal
  "12:00": 3  # Lunch: weeknight meal
  "18:00": 3  # Dinner: weeknight meal

preferences:
  liked_foods:
    - "salmon"
    - "eggs"
    - "rice"
    - "potatoes"
  disliked_foods:
    - "brussels sprouts"
    - "liver"
  allergies:
    - "shellfish"
    - "peanuts"
```

## Component Specifications

### Ingredient Parser
**Input**: `"200g cream of rice"` or `"salt to taste"`  
**Output**: `Ingredient(name="cream of rice", quantity=200.0, unit="g")` or `Ingredient(name="salt", quantity=0.0, unit="to taste", is_to_taste=True)`

**Simple Parsing Rules**:
- Extract number (quantity) - if present
- Extract unit (g, oz, cup, tsp, tbsp, scoop, etc.) - if present
- Extract name (everything else)
- Detect "to taste" pattern: if unit is "to taste" or phrase contains "to taste", mark as `is_to_taste=True`
- Normalize ingredient name using aliases from nutrition DB

**Special Handling for "To Taste" Ingredients**:
- Ingredients marked as "to taste" (e.g., "salt to taste", "green onion to taste", "salsa to taste") are:
  - **Included** in recipe display and instructions
  - **Excluded** from nutrition calculations (per KNOWLEDGE.md line 17)
  - Rationale: These ingredients have negligible nutritional value and vary too much by personal preference (e.g., salt, garnishes like green onion)

**Limitations (MVP)**:
- No handling of ranges ("2-3 eggs")
- No handling of parenthetical conversions ("1 cup (240ml)")

### Nutrition Calculator
**Input**: `Recipe` with list of `Ingredient`  
**Output**: `NutritionProfile`

**Calculation Logic**:
1. **Filter out "to taste" ingredients** - Skip ingredients where `is_to_taste=True` (per KNOWLEDGE.md: these have negligible nutritional value)
2. For each remaining ingredient, look up nutrition per unit in nutrition DB
3. Convert quantity to match unit in DB (e.g., oz → g)
4. Calculate: `nutrition = (per_unit_nutrition * quantity) / unit_size`
5. Sum all ingredient nutrition values

**Example**:
- 200g cream of rice: 200g × (370 cal/100g) = 740 calories
- 1 scoop protein: 1 × 120 cal = 120 calories
- Salsa to taste: **SKIPPED** (is_to_taste=True)
- Green onion to taste: **SKIPPED** (is_to_taste=True)
- Total: 860 calories (only calculated ingredients)

**Rationale**: Per KNOWLEDGE.md line 17, ingredients added "to taste" (salt, garnishes, etc.) are excluded from nutrition totals because:
- Their nutritional contribution is negligible
- Amounts vary too much by personal preference
- Simplifies calculations while maintaining accuracy for measured ingredients

### Recipe Retriever (Keyword-Based)
**Input**: Query string, filters (cooking_time, preferences)  
**Output**: List of `Recipe`

**Search Logic**:
1. Filter recipes by cooking_time ≤ schedule constraint
2. Filter recipes by excluded ingredients (allergies, dislikes)
3. Score recipes by keyword matches in name/ingredients
4. Return top N candidates

**Example Query**: "quick breakfast protein"  
- Matches recipes with "breakfast" in name
- Matches recipes with protein-rich ingredients
- Filters to cooking_time ≤ 15 minutes

### Recipe Scorer (Rule-Based)
**Input**: `Recipe`, `UserProfile`, `DailyMealPlan` (partial)  
**Output**: Score (0-100)

**Scoring Rules**:
1. **Nutrition Match** (40 points):
   - Calories within target range: +20 points
   - Protein within target range: +10 points
   - Fat within target range: +10 points

2. **Schedule Match** (30 points):
   - Cooking time matches busyness level: +30 points
   - Cooking time slightly over: +15 points
   - Cooking time way over: 0 points

3. **Preference Match** (20 points):
   - Contains liked foods: +2 points each (max 10)
   - Avoids disliked foods: +10 points if none present
   - Avoids allergens: +10 points if none present

4. **Balance** (10 points):
   - Complements other meals in day: +10 points
   - Avoids nutrient overlap: +5 points

### Meal Planner
**Input**: `UserProfile`, available `Recipe` list  
**Output**: `DailyMealPlan`

**Planning Algorithm** (Greedy + Backtracking):
1. Sort recipes by score (highest first)
2. For each meal slot (breakfast, lunch, dinner):
   - Select top-scoring recipe that fits schedule
   - Calculate running nutrition totals
   - If nutrition exceeds targets, backtrack and try next recipe
3. Validate final plan meets all goals
4. If no valid plan found, relax constraints and retry

### Output Formatter
**JSON Output**:
```json
{
  "date": "2024-01-15",
  "meals": [
    {
      "name": "Preworkout Meal",
      "meal_type": "breakfast",
      "ingredients": [...],
      "instructions": [...],
      "nutrition": {
        "calories": 860,
        "protein_g": 31.5,
        "fat_g": 6.0,
        "carbs_g": 167.0
      }
    }
  ],
  "total_nutrition": {...},
  "goals": {...},
  "meets_goals": true
}
```

**Markdown Output**:
```markdown
## Daily Meal Plan - 2024-01-15

### Meal 1: Preworkout Meal
- Quick to make but will still give you enough carbs for your workout
- 200g cream of rice
- 1 scoop whey protein powder
- 1 tsp almond butter
- 50g blueberries

**Instructions:**
1. Cook cream of rice according to package directions
2. Mix in protein powder
3. Top with almond butter and blueberries

**Nutrition Breakdown:**
- Calories: 860
- Protein: 31.5g
- Fat: 6.0g
- Carbs: 167.0g

[... more meals ...]

### Total Daily Nutrition
- Calories: 2400 / 2400
- Protein: 150g / 150g
- Fat: 75g (within 50-100g range)
- Carbs: 300g
```

## Error Handling

### Common Errors:
1. **Missing Ingredient in DB**: Log warning, skip ingredient, continue
2. **No Recipes Match Constraints**: Relax constraints, retry with warnings
3. **Cannot Meet Nutrition Goals**: Return partial plan with warnings
4. **Invalid User Profile**: Raise validation error with clear message

### Validation:
- User profile must have valid nutrition goals
- Recipes must have valid ingredients
- Nutrition DB must have entries for all recipe ingredients
- Schedule must have valid time format and busyness levels

## Testing Strategy

### Unit Tests (MVP):
- `test_ingredient_parser.py`: Test parsing various ingredient formats
- `test_nutrition_calculator.py`: Test nutrition calculations
- `test_recipe_scorer.py`: Test scoring rules
- `test_meal_planner.py`: Test meal planning logic
- `test_output_formatter.py`: Test JSON and Markdown output

### Test Fixtures:
- Sample recipes (5-10 recipes)
- Sample nutrition data (20-30 common ingredients)
- Sample user profiles (different goal configurations)

## Performance Considerations

### MVP:
- Small dataset (10-20 recipes, 30-50 ingredients)
- No performance optimization needed
- Simple linear search is sufficient

### Future Optimizations:
- Index recipes by cooking time
- Cache nutrition calculations
- Pre-compute recipe scores for common queries
- Use embeddings for faster semantic search

