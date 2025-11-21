# Design Summary - Quick Reference

## Architecture Overview

The Nutrition Agent follows a **layered architecture** with 6 main layers:

1. **Data Layer** - Stores ingredients, recipes, nutrition data, user profiles (JSON/YAML)
2. **Ingestion Layer** - Parses ingredients, retrieves recipes (keyword-based), fetches nutrition
3. **Nutrition Layer** - Calculates and aggregates nutrition values (macros/calories)
4. **Scoring & Reasoning Layer** - Evaluates recipes using rule-based scoring (MVP: no LLM)
5. **Planning Layer** - Generates meal plans considering all constraints (daily only for MVP)
6. **Output Layer** - Formats and structures final recommendations (JSON + Markdown)

## MVP Scope (Confirmed Decisions)

**Included:**
- ✅ Basic ingredient parsing (quantity, unit, name)
- ✅ Macro/calorie calculations (no micronutrients)
- ✅ Simple recipe retrieval (keyword-based, no embeddings)
- ✅ Rule-based recipe scoring (no LLM)
- ✅ Daily meal planning (3 meals per day)
- ✅ Structured output (JSON + Markdown)
- ✅ YAML user profile configuration
- ✅ Minimal recipe format (name, ingredients, cooking_time, instructions)

**Excluded (Post-MVP):**
- ❌ Weekly nutrient tracking (Phase 5.3: running totals)
- ❌ Micronutrient calculations (Phase 5.3)
- ❌ LLM reasoning (Phase 5.1)
- ❌ Embedding-based retrieval (Phase 5.2)
- ❌ Meal prep integration (Phase 5.4)
- ❌ Complex satiety calculations (Phase 5.4)

## Key Design Principles

1. **Modularity**: Each component is independent and testable
2. **Local-First**: Minimize external API dependencies for MVP
3. **Extensibility**: Easy to add features (LLM, embeddings, micronutrients)
4. **Data-Driven**: Use structured data (JSON/YAML) for easy updates
5. **Weekly-First Philosophy**: Track weekly totals, allow daily flexibility

## Technology Stack (MVP)

- **Language**: Python 3.9+
- **Data Validation**: Pydantic
- **Config**: PyYAML (for user profiles)
- **Data Storage**: JSON files (recipes, ingredients, nutrition)
- **Testing**: Pytest (unit tests only for MVP)
- **No External APIs**: Fully local for MVP

## Implementation Phases

1. **Phase 1** (Week 1): Foundation - Setup, data models, basic data layer
2. **Phase 2** (Week 2): Core - Parsing, nutrition calculation, recipe retrieval
3. **Phase 3** (Week 3): Planning - Scoring, meal planning, output formatting
4. **Phase 4** (Week 4): Integration - End-to-end testing, user profiles, docs
5. **Phase 5** (Post-MVP): Enhancements - LLM, embeddings, micronutrients

## Key Decisions Made

1. **Recipe Source**: Manual curation (10-20 recipes in JSON) - Option A
2. **Nutrition Source**: Manual entry for MVP, USDA API later - Option B
3. **LLM**: Rule-based scoring for MVP, LLM in Phase 5.1 - Option D
4. **Parsing**: Simple parsing (quantity, unit, name)
5. **Recipe Format**: Minimal (name, ingredients, cooking_time, instructions)
6. **User Profile**: YAML config file
7. **Weekly Tracking**: Running totals (Option C) - Post-MVP
8. **Meal Prep**: Post-MVP feature
9. **Output**: Both JSON and Markdown
10. **Testing**: Unit tests only for MVP

## Next Steps

1. ✅ Review design documents (ARCHITECTURE.md, TECHNICAL_DESIGN.md, IMPLEMENTATION_PLAN.md)
2. ✅ Questions answered - all decisions confirmed
3. **Ready to code!** See NEXT_STEPS.md for immediate actions
4. Start with Phase 1, Step 1.1: Project Setup
5. Build incrementally, test as you go

## File Structure Quick Reference

```
nutrition-agent/
├── config/          # User profiles, nutrition goals, model config
├── data/            # Ingredients, recipes, nutrition databases
├── src/             # Source code (organized by layer)
│   ├── data_layer/  # Database interfaces
│   ├── ingestion/   # Parsing and retrieval
│   ├── nutrition/    # Calculations and aggregation
│   ├── scoring/     # Recipe scoring and reasoning
│   ├── planning/    # Meal planning logic
│   └── output/      # Formatting and output
├── tests/           # Unit tests
├── scripts/         # Setup and maintenance scripts
└── examples/        # Usage examples
```

## Success Criteria

MVP is successful when:
- ✅ Can generate 3 meals for a day
- ✅ Meals meet calorie/macro targets (±10%)
- ✅ Meals respect cooking time constraints
- ✅ Output is structured and readable
- ✅ All components have unit tests
- ✅ Runs locally without external APIs

