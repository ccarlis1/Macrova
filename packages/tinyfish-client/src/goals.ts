/** Natural-language goals: keep steps explicit; ask for JSON the optimizer can parse. */

export function buildProductSearchGoal(
  ingredient: string,
  maxResults: number,
): string {
  const n = Math.max(1, Math.min(20, maxResults));
  return `
You are automating a grocery website that is already loaded.

1. Search the site for: ${JSON.stringify(ingredient)}
2. From the search results, pick the ${n} most relevant distinct products (skip unrelated categories).
3. For each product, open its detail or listing row if needed to read price and pack size.
4. Return ONLY valid JSON (no markdown fences) with this shape:
{
  "products": [
    {
      "name": string,
      "price": string | null,
      "quantity_or_size": string | null,
      "unit_price": string | null
    }
  ]
}

Use null when a field cannot be determined. Prefer explicit pack sizes (e.g. "2 lb", "1 gal") in quantity_or_size.
`.trim();
}

export function buildRecipeExtractionGoal(
  includeNutritionHints: boolean,
): string {
  const nutrition = includeNutritionHints
    ? `
If a nutrition facts panel is visible, capture calories per serving as a single string in "nutrition_calories_hint" (else null).
`.trim()
    : "";

  return `
You are on a recipe page.

1. Read the recipe title (or H1) if present.
2. Extract the ingredient list with amounts and units as written.
3. If servings/yields are shown, capture them as a short string.

Return ONLY valid JSON (no markdown fences) with this shape:
{
  "title": string | null,
  "servings": string | null,
  "ingredients": [
    {
      "name": string,
      "quantity": string | null,
      "unit": string | null,
      "notes": string | null
    }
  ],
  "nutrition_calories_hint": string | null
}

${nutrition}
Rules:
- One object per ingredient line; split combined lines like "salt and pepper" into two entries if clearly two items.
- Preserve fractions and ranges as strings (e.g. "1 1/2", "2-3").
`.trim();
}

export function buildAddToCartGoal(
  items: ReadonlyArray<{
    searchQuery: string;
    quantity?: number;
    preferCheapest?: boolean;
    notes?: string;
  }>,
  confirmInCart: boolean,
): string {
  const lines = items.map((it, i) => {
    const qty = it.quantity ?? 1;
    const cheap = it.preferCheapest !== false;
    const notes = it.notes ? ` Notes: ${it.notes}` : "";
    return `${i + 1}. Search for ${JSON.stringify(it.searchQuery)}. Add ${qty} unit(s). ${
      cheap ? "Prefer the cheapest reasonable match for the pack size." : "Pick the closest match to the search text."
    }${notes}`;
  });

  const confirm = confirmInCart
    ? `

Finally: open the cart page and list the line items you see. Return ONLY valid JSON (no markdown fences):
{
  "ok": true,
  "cart_items": [ { "name": string, "qty": number | null, "price": string | null } ]
}
`
    : `

Return ONLY valid JSON (no markdown fences):
{ "ok": true, "added": [ { "searchQuery": string, "selected_name": string | null } ] }
`;

  return `
You are on a grocery storefront.

${lines.join("\n")}

If login or zip/location is required to see prices or add to cart, follow the minimal prompts to continue.
Handle cookie/consent banners if they block interaction.

${confirm.trim()}
`.trim();
}
