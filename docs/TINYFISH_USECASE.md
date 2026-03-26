# TinyFish Use Cases 

## Core Concept: Recipe Browsing for Meal Plan Candidates

Instead of having a generic LLM generate made-up recipes, TinyFish can browse the web for real, sourced recipes. The pipeline would look like:

**User Preferences → TinyFish Browses Recipes → Algorithm Filters by Nutrition → AI Personalizes the Final Plan**

This ensures users get real recipes from verified sources (e.g. AllRecipes, BBC Food) rather than hallucinated ones, and your algorithm can validate nutritional data before including them in the plan.

---

## Other Integration Ideas

- **Live Grocery Pricing** — Scrape prices from local stores to generate a cost-optimized shopping list based on what's actually on sale that week.
- **Seasonal Ingredients** — Browse grocery sites to see what's in season locally, then bias the meal plan toward those ingredients.
- **User-Submitted Recipes** — If a user pastes a recipe URL, TinyFish can extract the ingredients and nutrition info automatically.

---

## Caveats

- TinyFish adds **cost and latency** to each request, so it should be used strategically rather than on every meal plan generation.
- Best used **asynchronously** or for building a **cached recipe database** rather than in real-time requests.

---

