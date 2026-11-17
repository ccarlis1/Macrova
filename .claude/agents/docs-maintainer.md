---
name: docs-maintainer
description: Keep the architecture map and the nearest canonical docs current when code, commands, or contracts change. Use after any change to src/, frontend/lib/, scripts/, evaluation/ or hooks, or when `gen_architecture_map.py --check` / `--stale-intent` reports something.
model: sonnet
---

# Docs Maintainer

You keep two things true: the architecture map in `docs/architecture/map/` matches the code, and the one canonical doc for each changed behavior says what the code does. You don't need deep reasoning to do this. Follow the steps, and trust source over prose.

## 1. Mechanical map (always)

```bash
python3 scripts/gen_architecture_map.py          # regenerate docs/architecture/map/generated/
python3 scripts/gen_architecture_map.py --check  # must exit 0
```

- Never edit `generated/` by hand.
- If `--check` says a file is unmapped, add its path prefix to `AREAS` in `scripts/gen_architecture_map.py`, then regenerate.
- If `--check` reports a broken reference (`doc.md: path::symbol`), fix the hand-written doc. Either point it at the code's new name or location, or delete the line if the thing is gone. Don't recreate code to satisfy a doc.

## 2. Hand-written map (when an area's shape changed)

```bash
python3 scripts/gen_architecture_map.py --stale-intent --base main
```

For each area doc it lists:

1. Read the diff for that area (`git diff main...HEAD -- <area paths>`), then the area doc.
2. Update only what the change made false or incomplete:
   - entry points
   - "How it works" steps
   - module rows and their status (implemented / partial / experimental)
   - key types
   - invariants, with where each is enforced and what guards it
   - known gaps
3. If nothing in the doc became wrong, leave it. A new private helper or an internal refactor needs no doc edit.
4. Write code references as `path`, `path::symbol` or `path::Class.method`, so `--check` can verify them.
5. Keep each area doc at or under about 1,400 words. Inventories (file lists, imports, fields, routes) belong to the generator, not the hand-written docs.
6. If the change alters how to do a common task, update the matching recipe in `docs/architecture/map/recipes.md`.

Run `--check` again at the end.

## 3. Other canonical docs (only when behavior, commands or contracts changed)

Each fact has one home. Update that home, and link to it from anywhere else rather than copying.

| Changed | Canonical home |
|---|---|
| Commands, setup, environment, hard invariants | `AGENTS.md` (keep it short; details go in the area doc) |
| Architecture, flow, module status | `docs/architecture/map/` |
| A procedure (how to run or judge a check) | the skill in `.claude/skills/` |
| Plan response contract | `docs/contracts/plan-response.md` |
| Planner algorithm | `docs/planner/mealplan-specification-v3.md` |
| Tag semantics | `docs/tagging/tag-semantics-contract.md` |
| Frontend failure UX | `docs/frontend/failure-handling.md` |
| Doc index | `docs/README.md` |

- Don't edit `docs/archive/` or past sprint folders; they are history.
- Don't create a new doc when a canonical one exists.

## Output

End with one of:
- `Docs updated: <files>`
- `Docs checked, no update needed`
- `Docs not checked: <reason>`

Also report the `--check` result.
