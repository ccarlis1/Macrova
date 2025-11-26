# Implementation Plan

## MVP (Minimum Viable Product) Scope

**Goal**: Generate a single day of meals that meet basic nutrition goals and schedule constraints.

### MVP Features:
1. ✅ Parse ingredients from recipes
2. ✅ Calculate basic nutrition (calories, macros) for recipes
3. ✅ Retrieve recipes from a small local database
4. ✅ Score recipes based on simple rules (calories, macros, cooking time)
5. ✅ Generate 3 meals for a day
6. ✅ Display structured output

### MVP Exclusions (Future):
- ❌ Weekly nutrient tracking
- ❌ Micronutrient calculations
- ❌ LLM-based reasoning (use rule-based scoring)
- ❌ Embedding-based retrieval (use keyword matching)
- ❌ Meal prep integration
- ❌ Complex satiety calculations

## Phase 1: Foundation (Week 1)

### Step 1.1: Project Setup
- [ ] Initialize Python project structure
- [ ] Create virtual environment
- [ ] Set up `requirements.txt` with core dependencies
- [ ] Create directory structure
- [ ] Set up `.gitignore` and basic config files

### Step 1.2: Data Models
- [ ] Define `Ingredient` data class
- [ ] Define `Recipe` data class
- [ ] Define `NutritionProfile` data class
- [ ] Define `Meal` data class
- [ ] Define `UserProfile` data class

### Step 1.3: Basic Data Layer
- [ ] Create simple JSON-based ingredient database
- [ ] Create simple JSON-based recipe database (10-20 recipes)
- [ ] Implement basic CRUD operations for databases
- [ ] Create sample data files

## Phase 2: Core Functionality (Week 2)

### Step 2.1: Ingredient Parsing
- [ ] Implement ingredient parser (extract quantities, units, names)
- [ ] Normalize ingredient names (e.g., "eggs" → "egg")
- [ ] Handle common units (g, oz, cup, tsp, tbsp)
- [ ] **Detect and handle "to taste" ingredients**:
  - Parse ingredients with "to taste" pattern
  - Mark with `is_to_taste=True` flag
  - Include in recipe display but exclude from nutrition calculations
- [ ] Write unit tests (including "to taste" cases)

### Step 2.2: Nutrition Calculation
- [ ] Implement nutrition calculator for individual ingredients
- [ ] Implement nutrition calculator for recipes (sum ingredients)
  - **Filter out "to taste" ingredients** before calculation (per KNOWLEDGE.md)
  - Only calculate nutrition for measured ingredients
- [ ] Implement daily aggregator (sum meals)
- [ ] Write unit tests (verify "to taste" ingredients are excluded)

### Step 2.3: Recipe Retrieval
- [ ] Implement keyword-based recipe search
- [ ] Filter recipes by cooking time
- [ ] Filter recipes by ingredient availability
- [ ] Write unit tests

## Phase 3: Scoring & Planning (Week 3)

### Step 3.1: Rule-Based Scoring
- [ ] Implement recipe scorer with rules:
  - Calories match target range
  - Macros match target ranges
  - Cooking time matches schedule constraint
  - Basic preference matching
- [ ] Write unit tests

### Step 3.2: Meal Planning
- [ ] Implement basic meal planner:
  - Select 3 meals for a day
  - Ensure total calories/macros meet goals
  - Respect cooking time constraints
- [ ] Write unit tests

### Step 3.3: Output Formatting
- [ ] Implement meal formatter (human-readable)
- [ ] Implement structured JSON output
- [ ] Create example output

## Phase 4: Integration & Testing (Week 4)

### Step 4.1: End-to-End Integration
- [ ] Create main entry point (`main.py` or CLI)
- [ ] Integrate all components
- [ ] Test full workflow with sample data

### Step 4.2: User Profile
- [ ] Implement user profile loader from YAML
- [ ] Support basic preferences (likes/dislikes)
- [ ] Support schedule constraints (busyness scale)

### Step 4.3: Documentation & Examples
- [ ] Write usage examples
- [ ] Document configuration files
- [ ] Create sample outputs

## Phase 5: LLM Integration & Creativity (End Game Vision)

### Phase 5.1: LLM-Enhanced Reasoning
- [ ] Integrate LLM API (OpenAI, Anthropic, or local)
- [ ] Replace rule-based scoring with LLM reasoning
- [ ] Add contextual meal explanations and reasoning
- [ ] Implement natural language query parsing (basic)

### Phase 5.2: Cultural Recipe Database
- [ ] Expand recipe database with multi-cultural recipes
- [ ] Implement recipe categorization by cuisine type
- [ ] Add cultural authenticity scoring
- [ ] Generate recipe embeddings for semantic search
- [ ] Improve recipe matching with cultural preferences

### Phase 5.3: Advanced Nutrition & Weekly Tracking
- [ ] Add comprehensive micronutrient database
- [ ] Implement micronutrient calculations and tracking
- [ ] Add weekly running totals (Option C from design)
- [ ] Implement nutrient carryover logic
- [ ] Add RDI validation and weekly balancing

### Phase 5.4: Natural Language Interface
- [ ] Implement complex natural language query processing
- [ ] Add meal prep integration and coordination
- [ ] Support flexible scheduling constraints
- [ ] Handle multi-constraint queries (e.g., "salmon 2 days + chili meal prep + flexible Sunday")
- [ ] Add conversational meal planning interface

### Phase 5.5: Advanced Customization
- [ ] Implement ingredient-driven meal planning
- [ ] Add cultural fusion recipe generation
- [ ] Support regional ingredient constraints
- [ ] Add advanced satiety calculations
- [ ] Implement specialized dietary pattern support (Mediterranean, Asian, etc.)

### Phase 6: Interface Evolution
- [ ] Develop GUI prototype (drag-and-drop meal planning)
- [ ] Implement hybrid interface (structured + natural language)
- [ ] Add visual nutrition tracking
- [ ] Create meal prep planning interface
- [ ] Support multiple interaction paradigms

## Dependencies

### Core Dependencies (MVP):
```txt
python>=3.9
pyyaml>=6.0          # Config file parsing
pydantic>=2.0        # Data validation and models
```

### Future Dependencies:
```txt
openai>=1.0          # LLM API (or anthropic, ollama)
sentence-transformers>=2.0  # Embeddings
numpy>=1.24          # Numerical operations
pandas>=2.0          # Data manipulation (if needed)
```

### Development Dependencies:
```txt
pytest>=7.0          # Testing
pytest-cov>=4.0     # Coverage
black>=23.0          # Code formatting
mypy>=1.0            # Type checking
```

## Implementation Order Summary

1. **Setup** → Project structure, dependencies, data models
2. **Data Layer** → Simple JSON databases, basic operations
3. **Parsing** → Ingredient parsing and normalization
4. **Nutrition** → Calculate macros/calories for recipes and days
5. **Retrieval** → Keyword-based recipe search
6. **Scoring** → Rule-based recipe scoring
7. **Planning** → Generate daily meal plan
8. **Output** → Format and display results
9. **Integration** → End-to-end testing and CLI
10. **Enhancement** → LLM, embeddings, micronutrients

## Success Criteria for MVP

- ✅ Can generate 3 meals for a day
- ✅ Meals meet calorie and macro targets (within 10% tolerance)
- ✅ Meals respect cooking time constraints
- ✅ Output is structured and readable
- ✅ All core components have unit tests
- ✅ Can run locally without external API calls
- ✅ **Foundation Priority**: Accurate nutrition calculations above all else
- ✅ Modular architecture supports future LLM integration

## Success Criteria for End Game

### Technical Capabilities
- Natural language query understanding (>90% accuracy)
- Support for complex multi-constraint meal planning
- Cultural recipe diversity (recipes from 10+ cultures)
- Seamless meal prep integration and coordination
- Weekly nutrition balancing with daily flexibility

### User Experience
- Intuitive natural language interface
- Cultural authenticity in recipe recommendations
- Flexible interaction paradigms (structured + conversational)
- Advanced customization without complexity
- Taste + nutrition optimization (never compromise either)

### System Performance
- LLM-enhanced reasoning with technical precision
- Real-time meal plan generation for complex queries
- Scalable recipe database with cultural categorization
- Robust nutrition calculations with micronutrient tracking

