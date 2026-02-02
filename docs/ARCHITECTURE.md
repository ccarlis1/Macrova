# Nutrition Agent - Architecture Design

## System Overview

The Nutrition Agent is a modular system that generates personalized meal recommendations based on nutrition goals, schedule constraints, and user preferences. 

**Current MVP**: Focuses on structured nutrition calculations with rule-based meal selection to establish a solid foundation.

**End Game Vision**: An all-purpose nutritious meals generator that combines LLM creativity with technical precision, supporting natural language queries, cultural recipe diversity, and advanced meal planning features like meal prep integration and flexible scheduling.

## Core Architecture

### 1. Data Layer
**Purpose**: Store and manage all data sources

- **Ingredient Database**: Structured ingredient data with nutrition profiles
- **Recipe Database**: Recipe collection with ingredients, instructions, cooking times
- **Nutrition Database**: Comprehensive nutrition values (macros + micros) per ingredient/recipe
- **User Profile**: Personal preferences, goals, constraints, meal prep plans
  - Includes optional `max_daily_calories` for Calorie Deficit Mode (hard constraint)
  - Includes optional `demographic` for UL lookup (e.g., `adult_male`)
  - Includes optional `upper_limits` overrides for clinician-specified limits
- **Upper Limits Reference**: Daily tolerable upper intake limits by demographic
  - Stored in `data/reference/ul_by_demographic.json`
  - Field names match `MicronutrientProfile` exactly
  - `null` = no UL established for that nutrient
  - ULs are DAILY limits (not weekly) — enforced per-day, never averaged

### 2. Ingestion Layer
**Purpose**: Parse and retrieve data from various sources

- **Ingredient Parser**: Extract and normalize ingredients from recipes/user input (simple parsing: quantity, unit, name)
- **Recipe Retriever**: Fetch recipes from local JSON database using keyword-based search (MVP: no embeddings)
- **Nutrition Fetcher**: Retrieve nutrition data from local JSON database (MVP: manual entry, USDA API later)

### 3. Nutrition Calculation Layer
**Purpose**: Compute and aggregate nutrition values

- **Nutrition Calculator**: Calculate macros/micros for recipes and meal combinations
- **Daily Aggregator**: Sum nutrition values for a day of meals
- **Weekly Aggregator**: Track weekly totals and ensure RDI compliance
- **Macro Allocator**: Distribute macros based on user goals (protein/fat/carb logic)

### 4. Scoring & Reasoning Layer
**Purpose**: Evaluate and rank recipes using rule-based scoring (MVP: no LLM)

- **Recipe Scorer**: Score recipes based on nutrition goals, schedule, preferences (rule-based for MVP)
  - Enforces hard constraints (allergens, max_daily_calories) with 0.0 score exclusion
- **LLM Reasoner**: Use LLM to understand context and make nuanced decisions (Phase 5.1: post-MVP)
- **Constraint Checker**: Validate recipes against cooking time, satiety, taste preferences, calorie limits
- **UL Validator**: Post-plan validation of daily micronutrient intake against upper tolerable limits
  - Loads reference ULs from `data/reference/ul_by_demographic.json`
  - Merges with user overrides from `upper_limits` in user profile
  - Enforced per-day (not averaged over week) — exceeding any daily UL marks plan invalid

### 5. Planning Layer
**Purpose**: Generate meal plans considering all constraints

- **Meal Planner**: Orchestrate meal generation for a day (MVP: daily only, weekly post-MVP)
- **Schedule Handler**: Process time constraints and busyness levels (1-4 scale)
- **Satiety Calculator**: Ensure appropriate satiety distribution throughout day (basic for MVP)
- **Meal Prep Integrator**: Factor in pre-planned meals (Phase 5.4: post-MVP)
- **Weekly Tracker**: Track running totals as days are planned (Phase 5.3: post-MVP)

### 6. Output Layer
**Purpose**: Format and structure final recommendations

- **Meal Formatter**: Format individual meals with ingredients, instructions, nutrition
- **Structured Output Generator**: Create JSON format for programmatic consumption
- **Report Generator**: Generate human-readable Markdown summaries (matches README example format)

## Data Flow (MVP)

```
User Profile (YAML) + Recipe DB (JSON) + Nutrition DB (JSON)
    ↓
Planning Layer (Meal Planner)
    ↓
Recipe Retriever (keyword-based search from local JSON)
    ↓
Nutrition Calculator (compute macros/calories from local DB)
    ↓
Recipe Scorer (rule-based scoring: calories, macros, cooking time, preferences)
    ↓
Meal Planner (select best 3-meal combination for day)
    ↓
Daily Aggregator (validate daily nutrition goals)
    ↓
Output Formatter (generate JSON + Markdown output)
```

**Post-MVP Flow** (adds):
- Weekly Tracker (running totals)
- LLM Reasoner (enhanced scoring and natural language understanding)
- Embedding-based retrieval (semantic search)
- Micronutrient calculations
- Cultural Recipe Integration (diverse recipe database)
- Natural Language Query Processing
- Advanced Meal Prep Coordination

## Key Design Decisions (Based on User Requirements)

### MVP Foundation Principles
1. **Modular Components**: Each layer is independent and testable
2. **Nutrition Accuracy First**: Prioritize accurate nutrition calculations over creative features
3. **Rule-Based MVP**: Use rule-based scoring for MVP, add LLM reasoning in Phase 5.1
4. **Local Data Sources**: Manual JSON databases for MVP (recipes, ingredients, nutrition)
5. **Simple Parsing**: Basic ingredient parsing (quantity, unit, name) - expand complexity later
6. **Minimal Recipe Format**: Name, ingredients, cooking_time, instructions - extend as needed
7. **YAML User Profile**: Easy-to-edit YAML config for preferences and goals
8. **Dual Output**: Both JSON (programmatic) and Markdown (human-readable)
9. **Weekly Tracking (Post-MVP)**: Track running totals as days are planned (Option C)
10. **Local-First**: No external API dependencies for MVP
11. **Unit Tests First**: Comprehensive unit tests for MVP, integration tests later

### End Game Architecture Principles
12. **LLM Integration**: Combine AI creativity with technical nutrition precision
13. **Cultural Recipe Diversity**: Support recipes from multiple cultures while maintaining nutrition goals
14. **Natural Language Processing**: Accept complex meal planning queries in natural language
15. **Advanced Customization**: Support meal prep integration, flexible scheduling, and complex constraints
16. **Specialized Training**: Train agent on comprehensive recipe databases and nutrition science
17. **Interface Flexibility**: Support both structured inputs (GUI) and natural language prompts

