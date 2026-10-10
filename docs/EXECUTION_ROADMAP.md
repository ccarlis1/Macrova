# Execution Roadmap — audit findings and ranked moves

**Written:** 2026-07-06. **Audience:** Anthony + any model executing on his behalf.
**Companion docs:** `CLAUDE.md` (how to work in this repo), `.claude/skills/` (sprint-task,
verify-stack, api-contract). Every brief below assumes the executor has read CLAUDE.md first.

---

## Part 1 — What the audit found

### The project in one paragraph

Macrova has a genuinely differentiated core: a **deterministic, test-hardened constraint
solver** for nutrition (953 tests, seeded search, per-day UL enforcement, τ-relaxed weekly RDI
floors) in a market where every competitor either hand-waves nutrition or lets an LLM
hallucinate it. It also has a two-person team, **zero users (including its builders), zero
deployment, zero distribution**, and no activity since May 3 — two months as of today.

### Where the time actually went (from git + docs forensics)

| Bucket | Evidence | Verdict |
|---|---|---|
| Foundation engineering | Planner phases 0–10, provider abstraction, error envelope, OpenAPI drift gate, 953 fast tests | **Excellent.** This is the asset. |
| Specification & planning | 637-line SPRINT_1.md + 30 agent-contract stubs (~2,500 lines of task spec) + spec v2 + 4 vision docs | **Over-invested.** Sprint labeled "Week 1 + buffer"; after 10 weeks, 3 of 30 tasks are done (DM-1, BE-1, AI-5) — and DM-1 still has an unchecked acceptance box. |
| Integration/parity debugging | `DEBUG_PLANNER_PARITY.md` exists because CLI and Flutter drifted; branches `phase-3-debug`, `mealplan-debug-dashboard` | Real time sink; the root cause (two clients, one hand-synced contract) is addressed by BE-6 + the api-contract skill. |
| Meta/tooling work | 2 of 3 open PRs are "development environment setup" (March, still open); figma MCP configured with an empty key; generic skills that don't match the repo | Procrastination-shaped work. |
| Momentum gaps | Commits: Nov 10 → Jan 15 → Feb 49 → Mar 59 → Apr 11 → May 1 → June/July 0. The venv had rotted by July (49 collection errors from a missing dep) | Every gap charges a re-entry tax. The tax is now paid (venv fixed, CLAUDE.md + skills written 2026-07-06). |

### The "offers and pricing" audit — the honest version

There are no offers and there is no pricing, anywhere: no landing page, no deploy, no license
beyond MIT, no waitlist, no user-facing install. **Your current offer is "clone the repo and
copy three example YAML/JSON files," and your current price is $0 — an offer only a developer
can accept, and so far zero have.** Pricing work now would be theater.

The audit's actual finding: **you have two possible buyers, and neither is a dieter today.**

1. **A hiring manager / internship recruiter.** You're a CS student (course folders, hackathon
   repos, a portfolio site next to this repo). For that buyer, this repo is a top-1% artifact
   *if packaged*: a real constraint solver, contract-checked API, agent-orchestrated
   development with written execution contracts. That story is worth more than any plausible
   first-year revenue from a meal-planning app, and it pays out on a much shorter timeline.
2. **A future paying user** — only reachable after the loop *use it weekly → log friction →
   fix friction* has run for months. Consumer nutrition is a graveyard of well-built apps;
   the only defensible wedge you have is "plans that are actually correct and actually match
   your real week," which is exactly the deterministic core plus the tag/slot work already
   specced in Sprint 1.

The roadmap below serves buyer 1 immediately and keeps buyer 2 alive cheaply.

### Structural problems found (feeding the moves)

- **Sprint 1 is scoped for a 6-person team.** 30 interdependent tasks, 4 tracks, a critical
  path where one stall blocks everything. The 3 finished tasks are precisely the ones with no
  unfinished dependencies. The plan isn't wrong — the batch size is.
- **The Flutter app is ahead of its user.** P4 in your own PRD: "User reads CLI markdown
  output instead of using the Flutter screens." The most expensive sprint tasks (FE-1, FE-2,
  FE-4 — the L-complexity rebuild/drag-and-drop) serve users who don't exist yet.
- **The API has no authentication.** `server.py` has CORS `*` and zero auth. Fine on
  localhost; deploying it publicly with `LLM_API_KEY` set hands strangers your LLM budget via
  the `/api/v1/llm/*` endpoints. Any deploy must add a shared-secret check first.
- **Attribution is fragmented.** Commits under four identities (Anthony / sle / Sleev + the
  repo living under ccarlis1). If GitHub doesn't map all three emails to your account, your
  contribution graph — which recruiters do look at — is silently undercounting your largest
  project.
- **Docs contain dead load-bearing references** (spec v1, `planner_architecture.md`,
  `architecture.json`) — already flagged in CLAUDE.md §4; cleanup is folded into Move 5.

---

## Part 2 — Ranked moves (highest expected return first)

> Execution notes for every move: one move at a time; a move is not started until the prior
> one hits "done looks like" or is explicitly parked. Weaker-model briefs are written to be
> pasted verbatim as the session's opening instruction.

### Move 1 — Ship the tag-constrained planner as a 9-task agent-executed slice

**Why.** This converts ~2,500 lines of sunk planning cost into the capability that makes the
product usable for its own builders: slots that express real intent ("portable", "quick",
"high-protein") instead of fighting reality. It's the sprint's own critical path with the
other 21 tasks cut. Marginal execution cost is now low: the stubs are agent contracts, and
CLAUDE.md + the sprint-task skill exist precisely to let a weaker model execute them safely.
Everything downstream (daily use, demo, portfolio story) needs this shipped first.

**The slice (in dependency order — this is the whole scope):**
`DM-2 → DM-4 → DM-6 → DM-5 → BE-3 → BE-8 → BE-4 → BE-6 → BE-7`

Scope amendment to record in the stub: BE-8 lists BE-2 (meal-prep batch locks) as a
dependency, but the sprint README's own critical path runs BE-3 → BE-8 without it. Implement
BE-8 to enforce **pins + required/preferred tags** now, with a documented seam (a
locked-assignments input already shaped like `pinned_assignments`) where batch locks plug in
later. Note the deviation in the stub file when closing it.

Explicitly cut from this slice: all meal prep (DM-3, BE-2, BE-5, FE-3, FE-7), all LLM tasks
(AI-1..AI-4), all Flutter tasks. Tags are usable from `config/user_profile.yaml` + CLI with
zero frontend work — which is how you actually consume plans today anyway (PRD P4).

**Exact steps.**
1. Update `docs/sprint1/README.md`: mark the 9 tasks as the active slice; move everything else
   under a "Parked until the slice ships + is used" heading.
2. Execute one task per session with the sprint-task skill, in the order above.
3. After BE-7, run the verify-stack skill end-to-end, including generating a real plan from
   your real profile with a required tag on at least one slot.
4. Tag the repo `v0.2.0-tags` and merge to main.

**Done looks like.**
- [ ] All 9 stubs `Status: done`, every checked acceptance box backed by a named test.
- [ ] `python -m pytest tests/ -q` green; `export_openapi.py --check` green.
- [ ] A 7-day plan generated from *your real* `user_profile.yaml` where a slot with
      `required_tag_slugs: [portable]` received only recipes carrying that tag, and an
      impossible tag yields the structured empty-candidate failure code (not a crash).
- [ ] Precedence test exists: pin beats required tag on the same slot.

**Brief for the weaker model (paste per session, one task ID at a time):**
> Read CLAUDE.md in full. Then invoke the sprint-task skill for task **<ID>** in
> `docs/sprint1/`. Scope amendment on file: BE-8 is implemented for pins + required/preferred
> tag slugs only; meal-prep batch locks are out of scope — leave a documented seam and note
> the deviation in the stub. Do not touch any FE-*, AI-*, DM-3, BE-2, or BE-5 files. When the
> task is done, run the full test suite and the OpenAPI check, update the stub's status and
> checkboxes per the skill, and stop — do not start the next task in the same session.

### Move 2 — Become user #1: a weekly planning ritual with a friction log

**Why.** Seven months in, nobody — including you — has eaten a week of this planner's output.
That is the single largest risk in the project: every design decision is currently speculative.
A weekly ritual converts you from architect to user, produces an evidence-backed backlog
(replacing vision documents), and is the difference between the portfolio story "I built a
meal planner" and "I've eaten from my own constraint solver since July." It also fixes the
momentum problem structurally: a standing 30-minute Sunday session is easier to keep than
"work on the app sometime."

**Exact steps.**
1. Repurpose `docs/SPRINT_DISCUSSION.md` (currently empty, already designated as the idea log)
   as the **friction log**: date, what you tried, what fought you, one-line severity.
2. Every Sunday: generate the week (`python3 plan_meals.py --days 7`), adjust profile/tags
   until the plan is one you'll actually eat, shop from it, and log every friction point —
   including "I ignored the plan Wednesday because X." Ten minutes of logging, max.
3. After 4 weeks, sort the log by frequency. The top 3 items are the next slice. (Prediction
   to check against reality: meal prep — DM-3/BE-2/BE-5 — will top the list, because eating
   distinct cooked meals 21 times a week is not a real life. If so, that's your Wave B.)
4. Get Campbell running the same ritual — second data point, and it forces Move 4's question
   (he can't use your laptop's localhost).

**Done looks like.**
- [ ] 4 consecutive weekly entries in the friction log, ≥10 total friction items.
- [ ] The next work slice is chosen *from the log*, cited by entry, not from vision docs.

**Brief for the weaker model (run each Sunday):**
> Read CLAUDE.md. Use the verify-stack skill's Step 2 to generate a 7-day plan from
> `config/user_profile.yaml`. Present the plan as a readable week table with per-day macro
> totals and any warnings/failure codes explained in plain language. Ask me what I'd change;
> apply profile edits I approve (schedule, tags, exclusions — never invent nutrition values)
> and regenerate until I accept. Then append a dated entry to `docs/SPRINT_DISCUSSION.md`
> recording: settings used, plan accepted or not, and every friction point I mentioned,
> verbatim where possible. Do not implement fixes for the friction — log only.

### Move 3 — Cash the career-capital check: case study, README demo, attribution fix

**Why.** You're a student; the highest-EV buyer of this work is a recruiter, and that market
pays out in months, not years. The rare, differentiating story here is not "meal planner" —
it's (a) a deterministic constraint solver with real domain rules (daily ULs, τ-relaxed weekly
floors, precedence semantics) and (b) **a documented method for making less-capable agents
execute reliably** (contract stubs, CLAUDE.md-as-operating-manual, checkable quality bars).
(b) is exactly what every engineering org is trying to figure out right now. Total cost is a
weekend; the amplification from Moves 1–2 ("in weekly use since July") is why this is ranked
third rather than first.

**Exact steps.**
1. Fix attribution first (10 minutes): `git config user.name` / `user.email` set consistently,
   and add the sle/Sleev commit emails to your GitHub account's email list so the existing
   history counts toward your graph.
2. Rewrite README top: 3 sentences on what it is, an animated GIF of plan generation
   (CLI or app), a "how this is built" section linking the sprint-contract method.
3. Write the case study (~1,200 words) for the portfolio site. Structure: the problem
   (LLMs can't be trusted with nutrition) → the solve (deterministic search + LLM confined to
   recipe acquisition) → the method (agent contracts, with a real stub excerpt) → results
   (953 tests, seconds-fast suite, OpenAPI-gated contract).
4. Cross-link: portfolio → repo → case study. If Move 4 is done, add the live demo link.

**Done looks like.**
- [ ] All historical commits attribute to your GitHub account (check the contribution graph).
- [ ] README has the GIF + method section; no dead doc references above the fold.
- [ ] Case study live on the portfolio site; one peer has read it and can repeat the story
      back accurately.

**Brief for the weaker model:**
> Read CLAUDE.md and `docs/EXECUTION_ROADMAP.md` Move 3. Draft the case study described in
> step 3 in my voice, plain prose, no marketing adjectives. Source every claim from the repo
> (test counts, file paths, real stub excerpts — quote DM-1's contract sections) and flag
> anything you couldn't verify. Then draft the README rewrite as a diff for my review. Do not
> push, publish, or change git config yourself — hand me the exact commands instead.

### Move 4 — Deploy one persistent, authenticated instance

**Why.** Localhost is a usage tax: the ritual (Move 2) dies the first busy Sunday, Campbell
can't participate, and Move 3 has no demo link. One small always-on instance removes all
three blockers. At n=2 users, JSON-files-on-a-volume is genuinely fine — resist any urge to
"do storage properly" first. The blocking issue is auth (see audit): the server currently has
none.

**Exact steps.**
1. Add a minimal shared-secret auth layer: require `X-Api-Token` (from env) on all `/api/v1/*`
   mutating and LLM routes; additive, via the api-contract skill; Flutter's `ApiService` sends
   it from config.
2. Containerize: one image — `pip install`, copy `src/ scripts/ data/*.example`, run uvicorn;
   build Flutter web (`flutter build web`) and serve the static bundle from FastAPI or a tiny
   static route. Volume-mount `data/` and `config/`.
3. Deploy to one small always-on host (Fly.io/Railway/Render class; pick whichever you already
   have an account on — the choice is not worth research time). Set `USDA_API_KEY`,
   `LLM_API_KEY`, `API_TOKEN` as secrets. Single instance, volume attached.
4. Smoke-test remotely with the verify-stack skill's curl flow + the deployed Flutter web UI;
   confirm an unauthenticated LLM-route request is rejected.

**Done looks like.**
- [ ] You and Campbell both generate a plan from your phones/laptops without this Mac running.
- [ ] Unauthenticated `POST /api/v1/llm/*` and `/api/v1/plan` return 401 with the standard
      error envelope; authenticated requests succeed.
- [ ] Data survives a redeploy (volume verified).
- [ ] URL is in the README (and case study, if Move 3 is done).

**Brief for the weaker model:**
> Read CLAUDE.md. First implement the auth layer per `docs/EXECUTION_ROADMAP.md` Move 4 step 1
> using the api-contract skill — additive only, envelope-compliant 401s, tests for both
> accept and reject paths, OpenAPI snapshot regenerated. Then write the Dockerfile and deploy
> config for <platform>, but stop before any command that creates cloud resources or costs
> money — print those commands with an explanation and let me run them. Never print or commit
> secret values; reference env var names only.

### Move 5 — Close the loops: PR/branch triage, DM-1's loose end, doc truth pass

**Why.** Lowest single payoff, but cheap (one session) and it compounds: 20+ dead branches
and three March-dated open PRs make every future session — human or agent — re-derive "what's
real?"; recruiters opening the repo (Move 3) see the same mess. One of the open PRs
(`#14`, assisted_live USDA post-processing fix) may contain a real bug fix worth salvaging
before it rots further.

**Exact steps.**
1. PR triage: for #11, #13, #14 — merge (rebased + green), or close with a one-line reason.
   #14 gets an actual read before deciding; #11/#13 (environment setup) are near-certain closes
   given AGENTS/CLAUDE tooling has moved on.
2. Delete every remote branch fully merged into main; list survivors with one-line purpose
   or delete those too.
3. Finish DM-1's unchecked acceptance box (planner reads only the unified registry) or
   re-status the stub honestly to reflect the gap — no silent half-done "done".
4. Doc truth pass: fix README's dead references (spec v1 → v2, remove
   `planner_architecture.md`), delete or truthfully re-label anything else CLAUDE.md §4 lists
   as dead.

**Done looks like.**
- [ ] Zero open PRs older than 30 days; every surviving branch has a stated purpose.
- [ ] Every `Status: done` stub has all validation boxes genuinely checked.
- [ ] Grep proof: no doc references a file that doesn't exist.

**Brief for the weaker model:**
> Read CLAUDE.md. Execute `docs/EXECUTION_ROADMAP.md` Move 5. For each open PR, summarize the
> diff, whether it still applies to main, and recommend merge/close with reasoning — but take
> no merge/close/delete action without my per-item confirmation. For the doc pass, produce
> the full list of dead references with proposed fixes before editing.

---

## Part 3 — The three things to stop doing

### Stop 1 — Stop specifying beyond your execution horizon

The evidence: SPRINT_1.md is a 637-line PRD with a reconciled architecture section, success
metrics with numeric targets, and 30 execution-contract stubs — labeled "Week 1 (5 working
days) + Week 2 buffer." Ten weeks later, three tasks are done and the repo has been silent
for nine of those weeks. Meanwhile the specs themselves have started rotting the way all
unexecuted plans do: SPRINT_1 references an `architecture.json` that doesn't exist, README
points to a spec version that was replaced, and the "done" task DM-1 has an acceptance box
that was never closed.

Why this happens and why it's expensive: planning is the most pleasant form of work on a
project like this — it feels like progress, it's intellectually rewarding, and nothing can
fail during it. But specs are inventory, and inventory depreciates: every week a stub sits
unexecuted, the code drifts under it (the stubs' own `REQUIRES_VERIFICATION` markers are an
admission of this), and the eventual executor pays a reconciliation tax on top of the
implementation. You wrote ~2,500 lines of task spec to get ~1,275 lines of shipped diff. The
irony is that your stub format is *genuinely excellent* — the problem was never quality, it
was batch size: you built a quarter's worth of contracts for a team that ships a week's worth
per quarter.

The rule: **spec at most the next 5 tasks, and never write a new sprint doc while any stub
from the previous batch is still `todo`.** A stub not started within two weeks of writing gets
parked or deleted. Keep the planning-to-execution ratio visible: if the diff you shipped this
month is smaller than the specs you wrote this month, the next session must be an execution
session. Move 1 exists to burn down the inventory you already have.

### Stop 2 — Stop building for the end-game user while user #1 doesn't exist

The evidence: four vision documents describe natural-language planning, cultural recipe
databases, "specialized agent training," fusion creativity, and TinyFish web-agent
integrations. The sprint allocates its largest line items (FE-1, FE-4 at L complexity, plus
FE-2's drag-and-drop) to a card-based UI rebuild. And your own PRD documents, in writing, that
the app's one real user prefers reading CLI markdown (P4) — then schedules a UI rebuild for
him anyway. Meanwhile the behavior that would validate any of it — someone eating a week of
planned meals — has never happened.

Why this is the expensive one: every hour spent on breadth for imaginary users carries a
double cost. First, the direct cost — drag-and-drop for zero weekly actives is polish on an
empty room. Second, the deferred-learning cost — the friction log you'd get from four weeks of
real use (Move 2) would re-rank the entire backlog with evidence, and every feature built
before that log exists has a meaningful chance of being the wrong feature built well. The
deterministic core is your moat precisely because you resisted this everywhere else in the
architecture; the discipline that kept LLMs out of the nutrition math is the same discipline
that should keep vision features out of the sprint until usage demands them.

The rule: **no feature enters the active slice unless it's on the critical path to "we two
eat from this weekly" or is cited by a friction-log entry.** Vision docs are fine as parking
lots — but they get review dates, not engineering tasks. TinyFish, cultural databases, and the
UI rebuild all wait behind the friction log's verdict.

### Stop 3 — Stop the meta-work spiral: tooling, environments, and long-lived parallel branches

The evidence: of the repo's three open PRs, two are "development environment setup" (both
sitting in draft/open since March — meta-work that itself wasn't finished); branches named
`mealplan-debug-dashboard` and `phase-3-debug` mark whole excursions into building
*instrumentation for* the product instead of the product; a figma MCP server is configured
with an empty API key (a tool integrated but never used); and 20+ branches accumulated with
long-lived lanes (`frontend`, `integration/backend-llm`) whose eventual merges produced
exactly the CLI-vs-Flutter parity drift that then consumed its own debugging doc and debug
branches. The venv rotting to the point of 49 phantom test failures is the same pattern's
passive form: environment entropy nobody owned.

Why this happens: meta-work is seductive for the same reason planning is — it's real
engineering, it's clearly "for" the project, and it never risks the ego the way shipping a
feature that might be wrong does. But it's almost always a response to friction that should
have been solved by *shortening the loop* rather than instrumenting it: the parity dashboard
exists because two clients evolved on parallel branches for weeks; had integration happened
per-task on main, there'd be nothing to dashboard. You now have the antidote installed — the
skills and CLAUDE.md make correct execution the default — so additional tooling investment
has sharply diminishing returns.

The rule: **meta-work gets a hard budget: one timeboxed session, only in direct service of the
active move, and it merges or dies the same week.** No branch lives longer than one task
(the sprint-task skill's one-task-per-session structure enforces this naturally). If you
notice friction twice, fix the loop (merge more often, delete the stale thing) before you
build an observer for it. The three open PRs are Move 5's first casualty of this rule.

---

## Sequencing at a glance

```
Week 1–3   Move 1 (9 tasks, ~2–3 per week via sprint-task skill)
Week 1+    Move 2 starts immediately (Sundays, in parallel — CLI is usable today)
Week 3–4   Move 3 (weekend project once "in weekly use" is true)
Week 4–5   Move 4 (auth → container → deploy)
Week 5     Move 5 (one cleanup session)
Week 6+    Wave B chosen from the friction log — predicted: meal prep (DM-3, BE-2, BE-5)
```

Re-audit trigger: if by four weeks from today the friction log has fewer than 4 entries,
the honest conversation isn't about roadmap — it's about whether this project is a product or
a portfolio piece, and Move 3 becomes the whole strategy.
