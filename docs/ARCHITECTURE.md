# Nutrition Agent - Architecture Design

## System Overview

The Nutrition Agent is a modular system that generates personalized meal recommendations based on nutrition goals, schedule constraints, and user preferences. It combines LLM reasoning with structured nutrition calculations to produce balanced daily and weekly meal plans.

## Core Architecture

### 1. Data Layer
**Purpose**: Store and manage all data sources

- **Ingredient Database**: Structured ingredient data with nutrition profiles
- **Recipe Database**: Recipe collection with ingredients, instructions, cooking times
- **Nutrition Database**: Comprehensive nutrition values (macros + micros) per ingredient/recipe
- **User Profile**: Personal preferences, goals, constraints, meal prep plans

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
- **LLM Reasoner**: Use LLM to understand context and make nuanced decisions (Phase 5.1: post-MVP)
- **Constraint Checker**: Validate recipes against cooking time, satiety, taste preferences

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
- LLM Reasoner (enhanced scoring)
- Embedding-based retrieval (semantic search)
- Micronutrient calculations

## Key Design Decisions (Based on User Requirements)

1. **Modular Components**: Each layer is independent and testable
2. **Rule-Based MVP**: Use rule-based scoring for MVP, add LLM reasoning in Phase 5.1
3. **Local Data Sources**: Manual JSON databases for MVP (recipes, ingredients, nutrition)
4. **Simple Parsing**: Basic ingredient parsing (quantity, unit, name) - expand complexity later
5. **Minimal Recipe Format**: Name, ingredients, cooking_time, instructions - extend as needed
6. **YAML User Profile**: Easy-to-edit YAML config for preferences and goals
7. **Dual Output**: Both JSON (programmatic) and Markdown (human-readable)
8. **Weekly Tracking (Post-MVP)**: Track running totals as days are planned (Option C)
9. **Local-First**: No external API dependencies for MVP
10. **Unit Tests First**: Comprehensive unit tests for MVP, integration tests later

