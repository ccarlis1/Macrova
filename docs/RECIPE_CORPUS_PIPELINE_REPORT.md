# Recipe corpus pipeline report

## Ingredient extraction

- Total ingredient lines: 200
- Unique candidates (before atomic filter): 79
- Unique candidates (after atomic filter): 76

## USDA caching

- Successfully cached: 14
- Skipped (ambiguous match): 22
- Skipped (no USDA entry / error): 33

### Skipped — ambiguous match

- 175204 beans white mature seeds: Mung beans, mature seeds, raw
- blueberries unsweetened: Blueberries, raw
- 173439 cheddar cheese natural 50% reduced fat: Crackers, cheese, reduced fat
- 171249 cheese pecorino style: Restaurant, family style, macaroni & cheese, from kids' menu
- 173800 chickpeas drained: Chickpea flour (besan)
- 173417 cottage cheese 1% fat: Cheese, cottage, with vegetables
- 173900 cream of rice dry: Rice noodles, dry
- 174030 hamburger or beef 90%: McDONALD'S, Hamburger
- 173110 hamburger or beef 95%: McDONALD'S, Hamburger
- light mayo store bought: Salad dressing, KRAFT Mayo Light Mayonnaise
- parmesan cheese dry grated: Cheese, parmesan, grated
- 170848 parmesan cheese hard: Candies, hard
- red bell peppers: Peppers, sweet, red, raw
- 174570 roast beef lunchmeat: Roast beef spread
- salmon sockeye (red) drained: Fish, salmon, sockeye, raw
- 171016 sesame oil: Oil, canola
- 170903 low fat greek yogurt
- 173177 whey protein powder 24 grams of protein per scoop: Beverages, Protein powder soy based

### Skipped — no USDA entry / error

- 173175 acai berry: USDA API returned status 400
- 168588 almond butter unsalted: USDA API returned status 400
- 171705 avocado black skin: USDA API returned status 400
- 175238 black beans drained: USDA API returned status 400
- 171710 blackberries unsweetened: USDA API returned status 400
- butter unsalted: USDA API returned status 400
- 170393 carrots: USDA API returned status 400
- 169986 cauliflower: USDA API returned status 400
- 170554chia seeds: USDA API returned status 400
- chicken breast: USDA API returned status 400
- 173627 chicken thigh skin removed: USDA API returned status 400
- 170273 chocolate dark 70-85% cacao solids: USDA API returned status 40
- 168411 edamame beans: USDA API returned status 400
- 173420 feta cheese reduced fat: USDA API returned status 400
- 170894 greek yogurt plain nonfat: USDA API returned status 400
- 168932 jasmine rice in unsalted water: USDA API returned status 400
- 169687 kellogg's rice krispies treats original: USDA API returned status 400
- 2710831 kiwi fruit green: USDA API returned status 400
- 167747 lemon juice bottled or boxed: USDA API returned status 400
- 170416 parsley: USDA API returned status 400
- 174524 salsa ready-to-serve: USDA API returned status 400
- 172475 tofu not silken firm: USDA API returned status 400
- 167535 tortillas corn: USDA API returned status 400
- 175159 tuna sashimi: USDA API returned status 400
- 172941 turkey breast lunchmeat reduced fat: USDA API returned status 400
- 171413 olive oil

---

### Missed Ingredients

- 2346404 sweet potato
- 2727579 spaghetti squash
- 169279 sauerkraut
- 174278 soy sauce
- 168462 spinach
- 173573 avocado oil
- 169736 pasta
- 171711 blueberries
- 172184 egg yolk
- 170567 almonds
- 175174 salmon canned
- 171247 parmesan grated
- 2685581 tomato

## Recipe reconstruction

- Recipes processed: 20
- Recipes in output: 20
- Ingredients per recipe (min/avg/max): 0 / 1.9 / 4

