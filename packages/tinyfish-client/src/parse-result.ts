import type { ProductCandidate, ProductSearchResult } from "./types.js";

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

/** Best-effort: unwrap common `{ products: [...] }` or top-level array shapes. */
export function extractProductArray(raw: Record<string, unknown>): unknown[] {
  const products = raw["products"];
  if (Array.isArray(products)) {
    return products;
  }
  const items = raw["items"];
  if (Array.isArray(items)) {
    return items;
  }
  const results = raw["results"];
  if (Array.isArray(results)) {
    return results;
  }
  return [];
}

export function normalizeProductCandidate(row: unknown): ProductCandidate | null {
  if (!isRecord(row)) {
    return null;
  }
  const name = row["name"] ?? row["title"] ?? row["product_name"];
  if (typeof name !== "string" || name.trim() === "") {
    return null;
  }
  const price =
    typeof row["price"] === "string"
      ? row["price"]
      : typeof row["price"] === "number"
        ? String(row["price"])
        : null;
  const quantity_or_size =
    typeof row["quantity_or_size"] === "string"
      ? row["quantity_or_size"]
      : typeof row["size"] === "string"
        ? row["size"]
        : typeof row["quantity"] === "string"
          ? row["quantity"]
          : null;
  const unit_price =
    typeof row["unit_price"] === "string"
      ? row["unit_price"]
      : typeof row["unitPrice"] === "string"
        ? row["unitPrice"]
        : null;
  return {
    name: name.trim(),
    price,
    quantity_or_size,
    unit_price,
    raw: row,
  };
}

export function toProductSearchResult(
  ingredient_query: string,
  store_url: string,
  raw_result: Record<string, unknown>,
): ProductSearchResult {
  const arr = extractProductArray(raw_result);
  const products: ProductCandidate[] = [];
  for (const row of arr) {
    const c = normalizeProductCandidate(row);
    if (c) {
      products.push(c);
    }
  }
  return { ingredient_query, store_url, products, raw_result };
}
