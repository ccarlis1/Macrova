/**
 * One-off: first 5 Hacker News front-page headlines via TinyFish (SSE stream).
 *
 * Usage (from repo root):
 *   export $(grep -v '^#' .env | grep TINYFISH | xargs)
 *   cd packages/tinyfish-client && npx tsx scripts/hn-headlines.ts
 */

import { TinyFishClient } from "../src/index.js";

const goal = `
You are on https://news.ycombinator.com (main "new" list is fine if that's what loads).

1. Find the numbered list of story submissions on the front page.
2. Take the first 5 story **titles** only (the clickable title text next to each number), in order from top to bottom.
3. Ignore: ads, "More" footer, subthreads, Ask HN / Show HN is OK if it's in the first 5 rows.

Return ONLY valid JSON (no markdown fences):
{ "headlines": [ "title1", "title2", "title3", "title4", "title5" ] }
`.trim();

async function main() {
  if (!process.env["TINYFISH_API_KEY"]) {
    console.error("Missing TINYFISH_API_KEY (e.g. export from .env).");
    process.exit(1);
  }

  const client = new TinyFishClient();
  const result = await client.runGoal(
    "https://news.ycombinator.com",
    goal,
    {
      streamOptions: {
        onProgress: (e) => console.error("[TinyFish]", e.purpose),
      },
    },
  );

  console.log(JSON.stringify(result, null, 2));
}

main().catch((err: unknown) => {
  console.error(err);
  process.exit(1);
});
