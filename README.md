# Nutriton Agent
An agent designed to generate healthy meals based on a users schedule and nutrition goals. Currently designed for personal use

## Purpose
### Experience
- Gain experience with working with LLMs and agents. This project will be open-source and is a good resume project

### Usage
The purpose of the agent is to recommend recipes based on a users schedule and nutrition goals, using up to date knowledge and principles of nutrition and health. The agent will be initially designed for personal use, but may later expand to fit other users. This solves the problem of constantly thinking about what meals to make, where I can drastically decrease the time needed to make and keep track of meals, as well as making sure I am eating as healthy as possible, and hopefully will gain some cooking experience overall.

## Goals

- Recommend recipes based on a user preferences and goals
- Calculate and display nutrition for selected recipes
- If multiple meals are recommended, ensure they fit the principles of a balanced diet
- Be deployable locally for personal use

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


## Future Extensions
- Expand to multiple users
    - Starting point maintenance calories calculator
    - Calculator for micronutrient RDIs
