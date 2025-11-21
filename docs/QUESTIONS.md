# Questions for Clarification

## 1. Recipe Data Source
**Question**: Where will recipes come from initially?
- **Option A**: You manually curate a small set (10-20 recipes) in JSON format
- **Option B**: Scrape/import from a recipe website (e.g., AllRecipes, Food Network)
- **Option C**: Use a recipe API (e.g., Spoonacular, Edamam)

**Recommendation**: Start with Option A for MVP, add API later if needed.

## 2. Nutrition Data Source
**Question**: Which nutrition database should we use?
- **Option A**: USDA FoodData Central API (free, comprehensive)
- **Option B**: Manual entry for MVP (small set of common ingredients)
- **Option C**: Cronometer API (if available)
- **Option D**: Local JSON database you maintain

**Recommendation**: Start with Option B for MVP, integrate USDA API in Phase 5.

## 3. LLM Provider
**Question**: Which LLM will you use for reasoning?
- **Option A**: OpenAI GPT-4/GPT-3.5 (requires API key, costs money)
- **Option B**: Anthropic Claude (requires API key, costs money)
- **Option C**: Local model via Ollama (free, runs locally)
- **Option D**: Skip LLM for MVP, use rule-based scoring

**Recommendation**: Option D for MVP, add LLM in Phase 5.1.

## 4. Ingredient Parsing Complexity
**Question**: How detailed should ingredient parsing be?
- **Simple**: "200g cream of rice" → quantity: 200, unit: g, name: "cream of rice"
- **Complex**: Handle "1 cup (240ml) of milk", "2-3 eggs", "to taste", etc.

**Recommendation**: Start simple, add complexity as needed.

## 5. Recipe Format
**Question**: What format should recipes be stored in?
- **Minimal**: Name, ingredients (list), cooking_time, instructions
- **Rich**: Also include cuisine_type, tags, difficulty, equipment_needed, etc.

**Recommendation**: Start minimal, extend as needed.

## 6. User Profile Format
**Question**: How should user preferences be specified?
- **YAML config file**: Easy to edit, version-controlled
- **JSON file**: Similar to YAML
- **Database**: More complex, but scalable

**Recommendation**: YAML config file for MVP (personal use).

## 7. Weekly Tracking Implementation
**Question**: For weekly nutrient tracking, should we:
- **Option A**: Store daily plans and aggregate at end of week
  - Plan each day independently, then sum up at the end of the week
  - Simple but may miss weekly targets if days are planned in isolation
- **Option B**: Plan entire week at once, ensuring weekly totals
  - Generate all 7 days simultaneously, optimizing for weekly totals
  - More complex, less flexible (can't adjust mid-week easily)
- **Option C**: Track running totals as days are planned
  - Maintain a "weekly accumulator" that updates as each day is planned
  - When planning Day N, the system knows what nutrients have already been consumed in Days 1 through N-1
  - Can adjust remaining days to ensure weekly targets are met

**Recommendation**: Option C for flexibility, but this is post-MVP.

### Detailed Explanation of Option C: "Track Running Totals"

**What it means**: As you plan each day, the system maintains a running total of all nutrients consumed so far in the week. When planning the next day, it considers what's already been consumed and adjusts accordingly.

**Example**:
Let's say your weekly Vitamin E target is 100mg (7 days × ~14.3mg/day).

**Monday (Day 1)**: You plan meals that provide 12mg Vitamin E
- Weekly accumulator: 12mg / 100mg (12% of weekly target)
- Remaining needed: 88mg over 6 days

**Tuesday (Day 2)**: You plan meals that provide 15mg Vitamin E
- Weekly accumulator: 27mg / 100mg (27% of weekly target)
- Remaining needed: 73mg over 5 days

**Wednesday (Day 3)**: You plan meals that provide 18mg Vitamin E
- Weekly accumulator: 45mg / 100mg (45% of weekly target)
- Remaining needed: 55mg over 4 days

**Thursday (Day 4)**: The system sees you're behind (only 45% after 3 days, should be ~43% but you're slightly ahead)
- Weekly accumulator: 45mg / 100mg
- System adjusts: Recommends meals with higher Vitamin E (e.g., 20mg) to catch up
- After planning: 65mg / 100mg (65% of weekly target)
- Remaining needed: 35mg over 3 days

**Friday-Sunday**: System continues tracking and adjusting to ensure you hit 100mg by end of week.

**Benefits**:
- ✅ Flexible: Plan days one at a time (more realistic workflow)
- ✅ Adaptive: Can adjust later days based on earlier consumption
- ✅ Handles mid-week changes: If you skip a meal or eat something unplanned, system adjusts
- ✅ Matches your knowledge.md philosophy: "weekly calculation of micronutrient RDIs are reached" with daily flexibility

**Implementation**:
```python
class WeeklyTracker:
    def __init__(self, weekly_targets):
        self.weekly_targets = weekly_targets  # e.g., {"vitamin_e_mg": 100}
        self.consumed = {}  # Running totals
        self.days_planned = []
    
    def add_day(self, day_nutrition):
        """Add a day's nutrition to running totals"""
        for nutrient, value in day_nutrition.items():
            self.consumed[nutrient] = self.consumed.get(nutrient, 0) + value
        self.days_planned.append(day_nutrition)
    
    def get_remaining_needs(self, days_remaining):
        """Calculate what nutrients are still needed"""
        remaining = {}
        for nutrient, target in self.weekly_targets.items():
            consumed = self.consumed.get(nutrient, 0)
            remaining[nutrient] = max(0, target - consumed)
        return remaining
    
    def get_daily_target_adjustment(self, days_remaining):
        """Get adjusted daily targets based on running totals"""
        remaining = self.get_remaining_needs(days_remaining)
        adjusted = {}
        for nutrient, total_needed in remaining.items():
            adjusted[nutrient] = total_needed / days_remaining  # Distribute evenly
        return adjusted
```

## 8. Meal Prep Integration
**Question**: For meal prep mode, should pre-planned meals:
- Be stored in a separate "meal_prep" section of user profile?
- Be treated as fixed constraints during planning?
- Have their nutrition automatically subtracted from daily/weekly totals?

**Recommendation**: Store in user profile, treat as constraints, auto-subtract nutrition. Post-MVP.

## 9. Output Format
**Question**: What format should the output be?
- **JSON**: Structured, easy to parse programmatically
- **Markdown**: Human-readable, matches your example
- **Both**: Generate JSON and format to Markdown

**Recommendation**: Both - JSON for programmatic use, Markdown for display.

## 10. Testing Strategy
**Question**: How comprehensive should testing be?
- **Unit tests only**: Test individual functions
- **Integration tests**: Test component interactions
- **End-to-end tests**: Test full workflow

**Recommendation**: Start with unit tests for MVP, add integration tests later.

