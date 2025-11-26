# Nutriton Agent
An agent designed to generate healthy meals based on a users schedule and nutrition goals. Currently designed for personal use

## Purpose
### Experience
- Gain experience with working with LLMs and agents. This project will be open-source and is a good resume project

### Current Usage (MVP)
The agent currently recommends recipes based on a user's schedule and nutrition goals, using structured nutrition calculations and rule-based meal selection. It solves the problem of constantly thinking about what meals to make, drastically decreasing the time needed to plan meals while ensuring optimal nutrition.

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
- *Total Micronutrient breakdown goes here*


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


## Development Roadmap

### Phase 1-4: MVP Foundation (Current)
- ✅ Accurate nutrition calculations and meal balancing
- ✅ Rule-based recipe scoring and selection
- ✅ Local recipe and nutrition databases
- ✅ Basic user preferences and scheduling

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

**Current Priority**: Nail the foundational nutrition logic and meal balancing before adding creative AI features.
