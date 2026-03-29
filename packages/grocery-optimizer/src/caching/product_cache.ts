/**
 * Cache normalized product parses by stable product signature to avoid re-parsing pack sizes.
 */

import type { NormalizedProduct } from "../types.js";

export function productSignature(candidate: {
  storeId: string;
  name: string;
  priceRaw: string | null;
  sizeRaw: string | null;
}): string {
  const norm = (s: string) =>
    s
      .toLowerCase()
      .replace(/[^\p{L}\p{N}.]+/gu, "")
      .trim();
  return [
    candidate.storeId,
    norm(candidate.name),
    norm(candidate.priceRaw ?? ""),
    norm(candidate.sizeRaw ?? ""),
  ].join("|");
}

export class ProductParseCache {
  private readonly map = new Map<string, NormalizedProduct>();

  get(signature: string): NormalizedProduct | undefined {
    return this.map.get(signature);
  }

  set(signature: string, value: NormalizedProduct): void {
    this.map.set(signature, value);
  }

  clear(): void {
    this.map.clear();
  }
}
