# Quick Start: Testing the Meal Planner

## ✅ Your Setup Status

- ✅ **15 recipes** loaded from `data/recipes/recipes.json`
- ✅ **45 ingredients** loaded from `data/ingredients/custom_ingredients.json`
- ✅ **User profile** created at `config/user_profile.yaml`

## 🚀 Run the Meal Planner

### Basic Command (Markdown output)
```bash
python3 plan_meals.py
```

This will:
1. Load your user profile (nutrition goals, schedule, preferences)
2. Load all recipes and ingredients
3. Generate a daily meal plan (breakfast, lunch, dinner)
4. Display the plan in Markdown format

### Save Output to File
```bash
python3 plan_meals.py --output-file my_meal_plan.md
```

### Get JSON Output (for API/programmatic use)
```bash
python3 plan_meals.py --output json
```

### Get Both Formats
```bash
python3 plan_meals.py --output both --output-file meal_plan
# Creates: meal_plan.md and meal_plan.json
```

## 📋 What the Output Includes

Each meal plan includes:
- **3 meals** (breakfast, lunch, dinner)
- **Meal details**: Name, type, cooking time
- **Ingredients list**: With quantities and units
- **Instructions**: Step-by-step cooking instructions
- **Nutrition breakdown**: Calories, protein, fat, carbs per meal
- **Daily totals**: Aggregated nutrition for the day
- **Goals & adherence**: How well the plan meets your targets
- **Warnings**: Any issues (e.g., calories below target)

## ⚙️ Customize Your Profile

Edit `config/user_profile.yaml` to adjust:
- **Nutrition goals**: Calories, protein, fat range, carbs
- **Schedule**: Meal times and busyness levels (1-4)
- **Preferences**: Liked foods, disliked foods, allergies

### Schedule Busyness Levels
- `1` = Snack (< 5 minutes)
- `2` = Quick meal (≤ 15 minutes)
- `3` = Weeknight meal (≤ 30 minutes)
- `4` = Weekend/meal prep (30+ minutes)

### Example Schedule
```yaml
schedule:
  "07:00": 2  # Breakfast: quick meal
  "12:00": 3  # Lunch: weeknight meal
  "18:00": 3  # Dinner: weeknight meal
  "19:00": 1  # Optional: workout time
```

## 🔍 Understanding Warnings

If you see warnings like:
```
⚠️ Calories below target: 1900 / 2400 (79.2%)
```

This means:
- The planner couldn't find recipes that exactly match your targets
- The plan is still valid, just slightly under/over your goals
- You may need to:
  - Add more recipes to your database
  - Adjust your nutrition goals
  - Add more high-calorie/high-carb recipes

## 🎯 Next Steps

1. **Test with your data**: Run `python3 plan_meals.py` and review the output
2. **Customize your profile**: Edit `config/user_profile.yaml` to match your needs
3. **Add more recipes**: Populate `data/recipes/recipes.json` with more options
4. **Refine ingredients**: Ensure `data/ingredients/custom_ingredients.json` has nutrition data for all recipe ingredients

## 📚 Full Documentation

See `USAGE.md` for complete documentation and advanced options.

