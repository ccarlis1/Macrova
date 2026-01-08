# Usage Guide: Testing the Meal Planner

## Quick Start

### 1. Set Up Your User Profile

First, create your user profile file:

```bash
cp config/user_profile.yaml.example config/user_profile.yaml
```

Then edit `config/user_profile.yaml` with your nutrition goals, schedule, and preferences.

### 2. Ensure Data Files Are Populated

Make sure you have:
- `data/recipes/recipes.json` - Your recipe database
- `data/ingredients/custom_ingredients.json` - Your ingredient nutrition database

### 3. Run the Meal Planner

**Basic usage (Markdown output to console):**
```bash
python3 plan_meals.py
```

**Save output to file:**
```bash
python3 plan_meals.py --output-file meal_plan.md
```

**Get JSON output:**
```bash
python3 plan_meals.py --output json
```

**Get both formats:**
```bash
python3 plan_meals.py --output both --output-file meal_plan
# Creates meal_plan.md and meal_plan.json
```

**Use custom file paths:**
```bash
python3 plan_meals.py \
  --profile config/my_profile.yaml \
  --recipes data/recipes/my_recipes.json \
  --ingredients data/ingredients/my_ingredients.json
```

## Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--profile` | Path to user profile YAML file | `config/user_profile.yaml` |
| `--recipes` | Path to recipes JSON file | `data/recipes/recipes.json` |
| `--ingredients` | Path to ingredients JSON file | `data/ingredients/custom_ingredients.json` |
| `--output` | Output format: `markdown`, `json`, or `both` | `markdown` |
| `--output-file` | Optional file path to save output | (prints to stdout) |

## Example Output

The meal planner will:
1. Load your user profile (nutrition goals, schedule, preferences)
2. Load all recipes and ingredients
3. Plan 3 meals (breakfast, lunch, dinner) based on:
   - Your nutrition goals
   - Your schedule (cooking time constraints)
   - Your preferences (liked/disliked foods, allergies)
   - Workout timing (if specified)
4. Output a meal plan with:
   - Meal names and types
   - Ingredients lists
   - Cooking times
   - Nutrition breakdowns
   - Daily totals
   - Goals and adherence percentages
   - Warnings (if any)

## Troubleshooting

**Error: User profile file not found**
- Make sure you've created `config/user_profile.yaml` from the example file

**Error: Recipes/Ingredients file not found**
- Check that your data files exist in the expected locations
- Use `--recipes` and `--ingredients` flags to specify custom paths

**No recipes found / Empty meal plan**
- Make sure your recipes JSON file is properly formatted
- Check that recipes have valid ingredients that exist in your ingredients database

**Meal plan has warnings**
- The planner will still generate a plan, but may not meet all targets
- Check the warnings section for details
- You may need to add more recipes or adjust your nutrition goals

## Advanced Usage

**View help:**
```bash
python3 plan_meals.py --help
```

**Pipe output to a file:**
```bash
python3 plan_meals.py > my_meal_plan.md
```

**Combine with other tools:**
```bash
python3 plan_meals.py --output json | jq '.meals[0].recipe.name'
```

