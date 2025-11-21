# Knowledge

Here I am going to go off the top of my head for everything by nutrition bot needs to generate me meals.

## Calories
- Maintenance calories are hard to calculate. My nutrition bot can give a rough estimate by querying my height, weight, and activity level, and give a rough estimate for what my maintenance calories are. This feature would be nice to have for other users, but currently, I can just feed a value to the agent because maintenance calories are the most accurate by tracking your calories and tracking your bodyweight. If your bodyweight does not change, those are your maintenance calories. Currently, my maintenance calories are roughly 2800. So this is the constant I will use if I want to eat at maintenance. However, I want to be in a slight calorie deficit currently. This is because I am able to maximize muscle growth on a slight calorie deficit, as there are no direct studies currently disproving this. The only other factor I will consider is a weekly cheat meal I like to have, which may put me in a calorie surplus for one of the days of the week. To allow for this, I will eat slightly less calories during the non cheat days to allow for this cheat meal. In a totally science-backed calculation, I will aim to eat 2400 calories per day for 6 out of the 7 days of the week. 
## Macronutrients
- This one is fun. Lets first talk about protein, the macro everyone likes to talk about the most. This macronutrient is dependent on the users body composition and body weight. The general recommendation for strength training individuals is 0.6g-1g of protein per pound of body weight. This is a good starting range to work with. Now we can narrow down this value further based on the body composition of the individual. For myself, I am not a very lean individual, but not too overweight either. Protein intake is dependent more so on the amount of lean mass on the individual. If someone is extremely lean, they should consider a protein intake closer to the upper limit of this range. For less lean individuals, they should consider more towards that lower end of that range. What does this mean for me? I am looking for a daily protein intake anywhere from 0.6g-0.9g of protein per pound of bodyweight per day, with a weekly total closer to 0.7g-0.8g per pound of bodyweight. 
- On to fats, this one is interesting. Fats are simple and can be summarized into one sentence: The least amount of fats intake possible such that every micronutrient RDI is be fulfilled, as well as the minimum fat required to retain hormone health. When I say micronutrients, this includes monounsaturated fats as well as saturated fat intake RDIs. This should land myself in a daily fat intake range of 50-100g, with a weekly median hovering around 75g, or a normal distribution for that matter. Given that fats have less of a room for error I will say carefully, or are more (valuable), we really want to make sure we are getting a proper fat diversity and consuming mostly healthy fats. An example is that we do not want all of our fat intake going exclusively to beef and eggs, or to a large amount of cooking oils, having no room for other types of fats. We want to pritoritize a diverse range of fat types.
- Carbohydrate intake is simply the rest of the calories subtracted from the previous two macronutrients. Because I partake in high intensity training, I want to time certain carbohydrates at certain times. For example, consuming easily digestable carbs close to a workout, a good amount of carbohydrates after a workout, or having more complex carbs later in the day to stay satiated overnight. Thats pretty much it, and of course, we want to prioritize consuming carb sources rich in micronutrients.
## Micronutrients
- The thing the least amount of people care about, but arguably the most important of all. This one is quite simple. Again, if I were to expand the user base, I would create a custom calculation that takes the users maintenance calories, then calculates the RDI for every nutrient based on those calories. This is ideal, but currently, I can just input my calories into cronometer, and have them calculate every nutrient RDI for me, and input it in the knowledge base. Some important factors to consider: nutrient RDIs are held constant no matter the calories. So if I want to be in a deficit, the micronutients are still calculated based on maintenance calories. Next, it is not absolutely mandatory to have every micronutrient accounted for each day. I say this because I do not want the agent giving random ingredients to meals just for the sake of adding a certain micronutrient. A complete day of meals should give the user a considerable amount of micronutrients, but what is absolutely paramount is that the weekly calculation of micronutrient RDIs are reached. For example, lets say that for 5 days, 100% RDI for Vitamin E is reached, but for one of the days, only 75% is reached. This is acceptable, but it is not negotiable that for the next day of meals, 125% of the RDI for Vitamin E is reached. This is just an example, and I accept values that are not exact, but favour going over the weekly RDI rather than under the weekly RDI for each micronutrient.
## Generating Meals
Now that nutrition is covered, lets go over factors in the users schedule that might influence meal generation.
- Time to make the meal: Lets say that the user is busy throughout the day, and does not have time to make a meal that takes too long. The agent must generate a meal for during that time that takes less time to make. When the user has more free time, they are free to generate a meal that might take longer to make. This should all be user specified, possibly with a busyness scale from 1 to 4, 1 being a snack, 2 taking 15 minutes or less to make, 3 taking 30 minutes or less to make (weeknight meal) and 4 taking 30+ minutes (weekend/meal prep). 
- Satiety: Again, this is a factor that must be user specified. Lets say that the user does not prefer to eat for 12 hours overnight. Then the agent must generate a meal that will keep the user more satiated, such as including more fiber, protein, adding volume to the meal (low calorie density), or even referring to the satiety index for certain foods. The vice versa rule applies, if the user likes to eat more frequent meals, it has to balance out the satiety to be an even spread throughout the day.
- Taste preference: A huge factor, and one difficult to implement. The user can specify certain foods they prefer or do not like to eat. For example, if someone is greek, the user properly specifies that they are on a mediterranean diet, the agent must try its best to generate meals that are mediterranean, but it first must prioritize micronutrients. It also must blacklist certain foods if the user is allergic or really does not like that food. I am still thinking on what to do exactly for this. Maybe the user can implement custom regions? Such as "only use ingredients relatively common in an American grocery store" or "I really like salmon. I want to eat salmon every day" *One thing to note:* There are certain ingredients in a recipe that are almost neglegible in a recipe in terms of nutritional value. When the agent is listing a recipe and refers to an ingredient to be added "to taste" We will NOT calculate that in the final nutritional total for that meal. An example of this is salt. The difference in sodium when salted to taste is not a value worth noting, as the difference between how salty one likes there food is not going to be a huge dealbreaker in their sodium total. Another example is garnishing with green onion. Sure that might provide a miniscule amount of vitamins such as Vitamin K, but for the sake of simplicity, we will leave it out of the total micronutrient calculation, and only calculate measured values in the nutrition total for each meal.
- Meal prep mode: A more advanced feature and not a huge priority right away, the user should be able to specify something like: I want to meal prep 5 servings of chili this week. Can you generate meals for the week AROUND the chili?" Let me explain. The agent must factor this in, the fact that the user wants a serving of chili 5 times this week. The agent must generate foods AROUND that fact. So, for example, chili is high in fiber, it must adjust the meals around that week to include LESS fiber so that the RDI for fiber is accurately reached for the week. This is a bit of an extension to the previous point on user preference for meals. 

## Day of Eating Example - A Human's thought process for a nutrient-dense full day of eating
### Meal 1: 6 Egg Scramble
- Reason: Lets say I am going to work during the day, and to the gym after work. I need a large meal early to fuel my day and keep me satiated for a long time, and I do not need many carbohydrates because I am not going to me moving around much, I also don't want to spike my blood sugar and crash early in the day.
- Ingredients:
    - 6 large eggs
    - 1oz reduced fat cheddar cheese
    - 1 meji cano fiber tortilla
    - Salt to taste
    - 2 large kiwi
    - Salsa to taste
- Instructions: Soft Scramble your eggs by pre salting them and cooking on a low heat. Once the eggs are cooked 75% of the way through, add your grated cheddar, combine with a high fiber wrap and wrap tightly. Dip in salsa for extra flavour. Serve with sliced kiwi on the side.
- Total Calories: 667kcal
- Macronutrients: 48g protein, 29g carbs, 37g fat

### Meal 2: Roast beef sandwich w/ sourdough bread
- Reason: Vitamin C, A, and K are high from the previous meal, not needed for the next meal. We are missing a lot from the minerals such as manganese, calcium, and zinc. Beef is a good choice to hit some of those targets. For macros, I am going to be working out soon, so we will need some slower digesting carbs to help fuel my workout. I want a quick meal to prepare, so roast beef is a solid choice. We can combine it in a sandwich with sourdough bread as it is a bread type lower on the glycemic index. Serve with cheese to hit calcium micronutrient targets further.
- Ingredients:
    - 4oz roast beef rump
    - 2x 40g slices sourdough bread
    - 1oz reduced fat cheese slice
    - 40g avocado
    - sliced tomato to taste
    - arugula to taste
    - sourkraut to taste
- Instructions: Lightly toast sourdough bread. Assemble sandwice in your desired order. Cut down the middle for a nice cross-section.
- Total Calories: 560kcal
- Macronutrients: 51g protein, 45g carbs, 18g fat

### Snack: Preworkout Meal: 2 Bananas
- Calories: 208
- Macronutrients: 2g protein, 50g carbs, 1g fat

- ### Meal 3: Hot Honey Salmon with baked potatoes and vegetables
- Reason: I need a solid satiating source of carbohydrates to recover from my workout, and to keep me full through the evening. I also want a good amount of protein to synthesize, as I will not be eating for many hours overnight. I am in need of Omega-3 fatty acids, Vitamin A, E, K, Calcium, folate, potassium, magnesium, etc. This meal will ensure every micronutrient target is largely hit.
- Ingredients:
    - 225g skin on salmon filet
    - 175g potatoes
    - 1.5 cup 1% milk
    - 1 cup broccoli
    - 50g spinach
    - 1 tsp olive oil
    - 1 tbsp mikes hot honey
- Instructions: Place salmon on cold pan skin side down in your oil. Turn pan to low heat and leave it until it is 90% cooked, basted in the oil and salmon fat. While that is going, cube potatoes, use spray oil to season them and put them in the air fryer for 20-25 minutes. With 7 minutes remaining, add broccoli. In the leftover salmon fat, cook down spinach lightly. Drizzle your hot honey on top of the filet, and serve with a glass of milk on the side.
- Calories: 738kcal
- Macronutrients: 62g protein, 74g carbs, 19g fat

## Total Nutrient Breakdown

## **Macronutrients**

* **Calories:** 2263 kcal — within the target range (<2400 kcal) ✔️
* **Protein:** 166.4 g — upper end but still optimal ✔️
* **Fat:** 78.6 g — upper end of target range ✔️
* **Carbs:** 204.6 g — well-timed carbohydrate intake ✔️

---

## **Micronutrients**

### **General**

* **Fiber:** 104% RDI
* **Omega-3:** 124% RDI
* **Omega-6:** 47% RDI *(still optimal)*
* **Omega-3 : Omega-6 Ratio:** **2 g : 8 g = 1 : 4** — more important than Omega-6 RDI

---

### **Vitamins**

* **Vitamin B1 (Thiamine):** 133% RDI
* **Vitamin B2 (Riboflavin):** 272% RDI
* **Vitamin B3 (Niacin):** 192% RDI
* **Vitamin B5 (Pantothenic Acid):** 233% RDI
* **Vitamin B6 (Pyridoxine):** 293% RDI
* **Vitamin B12 (Cobalamin):** 664% RDI
* **Folate:** 160% RDI
* **Vitamin A:** 126% RDI
* **Vitamin C:** 355% RDI
* **Vitamin D:** 88% RDI **THE ONLY VITAMIN I DO NOT CARE ABOUT. THIS VITAMIN IS LARGELY OBTAINED FROM THE SUN, OTHERWISE SUPPLEMENTED. THIS VITAMIN DOES NOT MATTER**
* **Vitamin E:** 96% RDI **CARRY INTO NEXT DAY FOR WEEKLY CALCULATION**
* **Vitamin K:** 440% RDI

---

### **Minerals**

* **Calcium:** 133% RDI
* **Copper:** 184% RDI
* **Iron:** 211% RDI
* **Magnesium:** 99% RDI **CARRY INTO NEXT DAY FOR WEEKLY CALCULATION**
* **Manganese:** 99% RDI **CARRY INTO NEXT DAY FOR WEEKLY CALCULATION**
* **Phosphorus:** 322% RDI
* **Potassium:** 149% RDI
* **Selenium:** 443% RDI
* **Sodium:** 217% RDI ⚠️ *(high — worth monitoring)*
* **Zinc:** 139% RDI

---

**Note:** This is not how the bot should reason or format the output exactly. The output format has not yet been decided, and it does not matter much for the MVP. This is just an example of how I personally would construct a full day of eating under these circumstances, which can hopefully help to translate algorithmically.