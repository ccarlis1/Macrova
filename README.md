# Macrova (nutrition-agent)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-pytest-green.svg)](tests/)

**Version: v0.1.0**

A meal planner that generates daily meal plans (breakfast, lunch, dinner) from your schedule and nutrition goals. The current MVP uses **rule-based recipe scoring** and **structured nutrition calculations**. LLM integration is coming soon.

---

## Getting started

### Install

```bash
git clone <repository-url>
cd nutrition-agent
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```
Replace `<repository-url>` with your clone URL (e.g. from GitHub). The folder name after clone is `nutrition-agent`.

### Quick run (local mode)

After copying the example config and data files (see below), run:

```bash
python3 plan_meals.py
```

This uses the bundled ingredient database (no API key). For USDA API mode, see [USAGE.md](USAGE.md#api-mode-setup).

### Configure and run

1. **Copy example config and data** (recipe/ingredient data are not in the repo):
   ```bash
   cp config/user_profile.yaml.example config/user_profile.yaml
   cp data/recipes/recipes.json.example data/recipes/recipes.json
   cp data/ingredients/custom_ingredients.json.example data/ingredients/custom_ingredients.json
   ```
2. Edit `config/user_profile.yaml` with your goals, schedule, and preferences.
3. **Run the planner:**
   ```bash
   python3 plan_meals.py
   ```
   Output is Markdown by default. Use `--output json` for JSON, or see below for more options.

**More detail:** [QUICK_START.md](QUICK_START.md) for a short run-through; [USAGE.md](USAGE.md) for all CLI options, API mode, and the REST API.

### Run tests

```bash
pytest tests/
```

No API key or network access is required; USDA-dependent tests use mocks.

**Environment variables:** None for local mode. For USDA API mode, copy `.env.example` to `.env` and set `USDA_API_KEY`; see [USAGE.md](USAGE.md#api-mode-setup).

---

## Current state (MVP)

The app recommends **three meals per day** (breakfast, lunch, dinner) from your recipe list. Ingredient nutrition is provided by a **provider abstraction** (local JSON or USDA API). In practice:

- **User profile:** Daily calories, protein, fat range, carbs, meal times, and busyness (cooking-time limits).
- **Recipe scoring:** Nutrition fit, cooking time vs schedule, preferences (likes/dislikes/allergies), and simple micronutrient scoring.
- **Ingredient nutrition:** Either a **local JSON** ingredient DB (default) or the **USDA FoodData Central API** (optional, `--ingredient-source api` and `USDA_API_KEY`).
- **Output:** Structured daily plan with per-meal and daily nutrition, adherence to goals, and warnings.

**Interfaces:** CLI (`plan_meals.py` / `python3 -m src.cli`) and an optional **REST API** (FastAPI server in `src/api/server.py`) for programmatic use.

### End Game Vision
The ultimate goal is to create an **all-purpose nutritious meals generator** that combines:
- **LLM Creativity**: Leveraging AI to understand natural language queries and user preferences
- **Technical Precision**: Accurate nutrition calculations and meal balancing
- **Cultural Diversity**: Recipes from different cultures that taste good and meet nutrition goals
- **Advanced Customization**: Complex meal planning with constraints like meal prep, specific ingredients, and flexible scheduling

**Example End Game Query:**
> "I want a set of meals generated for the week. I want salmon 2 of these days, and I want to make 4 servings my weekly meal prep chili recipe. I also want sunday to be a more flexible day so don't plan out lunch and dinner, just plan out one meal for sunday."

The system will intelligently parse this request, account for the chili's nutrition across the week, ensure salmon appears twice, and provide flexible Sunday planning - all while maintaining optimal nutrition balance.

## Goals

### Current MVP Goals
- Recommend recipes based on user preferences and goals
- Calculate and display accurate nutrition for selected recipes
- Ensure multiple meals fit principles of a balanced diet
- Be deployable locally for personal use
- **Foundation Priority**: Accurate nutrition calculations and meal balancing above all else

### End Game Goals
- **LLM-Powered Creativity**: Combine technical nutrition precision with AI creativity for meal selection
- **Multi-Cultural Recipe Database**: Incorporate recipes from different cultures while maintaining nutrition goals
- **Natural Language Interface**: Accept complex, natural language meal planning requests
- **Advanced Meal Prep Integration**: Plan meals around pre-made components and batch cooking
- **Flexible Scheduling**: Handle complex scheduling constraints and preferences
- **Specialized Agent Training**: Train on recipe databases and up-to-date nutrition principles

## Example: Full Day of Meals

### **Output**
- **Meal 1:** Preworkout Meal
	- Given that you train 2 hours after waking up, this is a meal that is quick to make but will still give you enough carbs for your workout
	- 200g cream of rice
	- 1 scoop whey protein powder
	- 1 tsp almond butter
	- 50g blueberries
	- *Meal instructions*
	- Nutrition Breakdown: *full micro/macro calculation goes here*
- **Meal 2:** Mexican-Style Breakfast Scramble
	- This meal will take less than 30 minutes to make, is highly satiating with fiber and protein, packed with micronutrients, and incredibly tasty!
	- 5 large eggs
	- 175g potatoes
	- 50g red peppers
	- 40g raw spinach
	- 1oz sharp cheddar cheese
	- 3oz lean turkey sausage
	- 50g pinto
	- 2 tsp olive oil
	- Salsa and green onion to taste
	- *Meal Instructions go here*
	- Nutrition Breakdown: *full micro/macro calculation goes here*
- **Meal 3:** Hot Honey Salmon with rice
	- This meal will take less than 30 minutes to make, and will cover the majority of the rest of your nutrition needs!
	- 4 oz salmon
	- 1 cup jasmine rice
	- 1 tbsp honey
	- 1 tsp chili crisp
	- *Meal Instructions go here*
	- Nutrition Breakdown: *full micro/macro calculation goes here*
- *Micronutrient Breakdown*


## Functional Requirements

- Must parse a list of ingredients
    
- Must retrieve relevant recipes
    
- Must compute or retrieve nutrition values
    
- Must score recipes based on nutrition goals
    
- Must return structured output
    

## Non-Functional Requirements

- Runs locally or within low-latency API
    
- Easy to update recipes/preferences
    
- Minimal dependencies


## Project structure

```
config/          # User profile (YAML); copy from .example
data/            # Recipes and ingredients JSON; copy from .example
src/
  cli.py         # CLI entrypoint
  api/           # Optional REST API (FastAPI)
  providers/     # Ingredient data (local JSON or USDA API)
  nutrition/     # Nutrition calculator and aggregation
  planning/      # Meal planner
  scoring/       # Recipe scorer
  ingestion/     # Recipe retrieval, USDA client, ingredient cache
  data_layer/    # Models, recipe/ingredient DBs, user profile loader
  output/        # Markdown/JSON formatters
tests/           # Pytest suite (no network required)
```

## Development roadmap

### Phase 1–4: MVP foundation (current)
- ✅ Accurate nutrition calculations and meal balancing
- ✅ Rule-based recipe scoring and selection
- ✅ Local ingredient database (JSON)
- ✅ Optional USDA API ingredient source (`--ingredient-source api`; requires `USDA_API_KEY`)
- ✅ User profile, schedule, and preferences (likes, dislikes, allergies)
- ✅ CLI and optional REST API

### Phase 5+: LLM Integration & Creativity
- **LLM-Enhanced Reasoning**: Replace rule-based scoring with intelligent AI reasoning
- **Natural Language Queries**: Accept complex meal planning requests in natural language
- **Recipe Creativity**: AI-generated recipe variations and cultural fusion
- **Specialized Training**: Train agent on comprehensive recipe databases and nutrition science

### Future Extensions
- **Multi-User Support**: Expand beyond personal use
- **Advanced Interfaces**: GUI for meal selection, scheduling, and preferences
- **Recipe Database Expansion**: Incorporate diverse cultural recipes
- **Maintenance Calorie Calculator**: Automated TDEE calculation
- **Dynamic RDI Calculation**: Personalized micronutrient targets based on individual needs

### Interface Evolution Options
The final product may feature:
- Natural language prompts for complex meal planning
- GUI with drag-and-drop meal scheduling
- Hybrid approach combining structured inputs with AI flexibility

**Current priority:** Nail the foundational nutrition logic and meal balancing before adding creative AI features.

---

## License

This project is licensed under the MIT License—see [LICENSE](LICENSE).
