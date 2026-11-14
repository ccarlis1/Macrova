# Visual Language Extraction

> Source of truth for **visual language and UI composition only**. Extracted from the
> Claude design prototype in `docs/frontend/design/` (`styles.css`, `*.jsx`, `data.js`).
> This document does **not** define data models, API contracts, or backend behavior.
> Anything inferred rather than directly observed is labeled **(assumption)**.

---

## Executive Summary

The prototype is a **card-first, mobile-first nutrition app** with a calm editorial feel:
near-white surfaces, hairline borders, one warm rose accent, generous padding, and soft
shadows reserved for elevation moments. It is built around stacked white cards on a soft
grey canvas, full-screen "sheets" for tasks (planner config, recipe builder, agent,
failure), and a bottom tab bar for primary navigation.

The most important translation facts for Flutter:

1. **The prototype is a polished visual layer, not a data spec.** Reuse its tokens,
  spacing, shapes, and component shapes. Keep all existing Macrova providers, DTOs, and
   screen logic exactly as they are.
2. **The prototype's navigation (5 mobile tabs) differs from the current app (7-item
  desktop sidebar + `IndexedStack`).** Do **not** silently restructure modules. Adopt the
   *visual* shell language while preserving the current module set and routing. The IA gap
   is the single biggest open question (see Open Questions).
3. **The prototype encodes Macrova's real concepts faithfully**: deterministic vs assisted
  planning modes, local-JSON vs USDA ingredient source, busyness bands, workouts between
   meals, pinned meals, server-calculated nutrition, micronutrient tracking, and structured
   infeasibility/failure reporting. The visual components map cleanly onto existing screens.
4. **It already models honesty states** (`wire` / `partial` / `mock` readiness chips). That
  maps directly to the repo's "Known Partial or Mock Areas" discipline — keep it.

The current Flutter theme is a default Material 3 blue seed (`theme.dart`). Adopting this
visual language is mostly **additive**: a token file + a small set of shared widgets +
incremental screen restyling, with no required changes to state or contracts.

---

## Visual Identity


| Trait                      | Concrete evidence in the prototype                                                                                                                                                                                                                                                                                           |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Personality**            | Calm, premium, "quiet utility." Feels like a well-made consumer health app, not a dashboard.                                                                                                                                                                                                                                 |
| **Mood**                   | Warm-neutral and editorial. Soft grey canvas (`#f7f7f7`), white cards, a single warm rose accent (`#c44a4a`), food-photo gradients as the only saturated color.                                                                                                                                                              |
| **Density**                | Comfortable, not dense. 20px screen gutters, 24px section tops, 14–22px card padding, 8–14px between cards. Touch targets ≥ 36–44px.                                                                                                                                                                                         |
| **Polish level**           | High. Hairline 1px borders everywhere, layered shadow scale, `backdrop-filter: blur(14px)` on sticky bars, tabular-nums for all stats, `letter-spacing` tightening on large type, `text-wrap: pretty` on headings, slide-up sheet animation.                                                                                 |
| **Inspiration pattern**    | Mobile recipe/commerce card UIs (explicitly noted in `styles.css` header: "Inspired by mobile card patterns: rounded corners, soft shadows, spacious padding, sticky CTAs, minimal palette with one accent").                                                                                                                |
| **What makes it cohesive** | (1) One accent color used sparingly; (2) one font family (Inter) across the whole app; (3) a single radius scale and shadow scale applied consistently; (4) repeated "white card on grey, hairline border, optional hover lift" motif; (5) macro colors (`pro/carb/fat`) reused identically in every chart, bar, and legend. |


Concrete traits behind "feels modern": tight negative letter-spacing on display/title type,
generous whitespace, hairline borders instead of heavy dividers, pill-shaped chips and
search, food-gradient thumbnails that supply all the visual warmth, and blurred translucent
sticky surfaces.

---

## Design Tokens

All values below are read directly from `styles.css` `:root` and inline styles. Token names
are a **proposal** for the Flutter implementation; the hex/size values are observed.

### Colors


| Proposed token             | Value                                   | Prototype source           | Notes                                                 |
| -------------------------- | --------------------------------------- | -------------------------- | ----------------------------------------------------- |
| `color.background.canvas`  | `#f7f7f7`                               | `--bg-soft`                | App/body background behind cards                      |
| `color.background.primary` | `#ffffff`                               | `--bg`                     | App column / page background                          |
| `color.surface.card`       | `#ffffff`                               | `.card`                    | Default card fill                                     |
| `color.surface.tint`       | `#fafafa`                               | `--bg-tint`                | Inset surfaces (macro cells, meal slots, attribution) |
| `color.surface.soft`       | `#f7f7f7`                               | `--bg-soft`                | Chips, segmented control track, hover fills           |
| `color.line.default`       | `#ebebeb`                               | `--line`                   | Card / divider borders                                |
| `color.line.soft`          | `#f0f0f0`                               | `--line-soft`              | Inner row separators                                  |
| `color.line.strong`        | `#ddd` *(approx)*                       | `--line-strong` fallback   | Input borders (declared only as fallback)             |
| `color.text.primary`       | `#222222`                               | `--ink-1`                  | Headings, primary text                                |
| `color.text.secondary`     | `#555555`                               | `--ink-2`                  | Body copy                                             |
| `color.text.tertiary`      | `#767676`                               | `--ink-3`                  | Metadata, captions, sublabels                         |
| `color.text.quaternary`    | `#b0b0b0`                               | `--ink-4`                  | Chevrons, faint dots, placeholders                    |
| `color.accent`             | `#c44a4a`                               | `--accent`                 | Primary actions, brand, active nav                    |
| `color.accent.deep`        | `#a43a3a`                               | `--accent-deep`            | Pressed/hover accent, accent text on tint             |
| `color.accent.soft`        | `#fdf3f0`                               | `--accent-soft`            | Accent chip/banner fill                               |
| `color.accent.tint`        | `#faeeea`                               | `--accent-tint`            | Accent banner border                                  |
| `color.pinned`             | `#4a3a2e`                               | `--pinned`                 | Pinned/batch signal (warm brown, neutral)             |
| `color.pinned.soft`        | `#f5efe7`                               | `--pinned-soft`            | Pinned slot/chip fill                                 |
| `color.macro.protein`      | `#5a7a8a`                               | `--m-pro`                  | Protein bars/legends                                  |
| `color.macro.carb`         | `#c69a4a`                               | `--m-carb`                 | Carb bars/legends                                     |
| `color.macro.fat`          | `#b56b5a`                               | `--m-fat`                  | Fat bars/legends                                      |
| `color.semantic.success`   | `#5fa874` / text `#2f7d4f` on `#e8f3ec` | `.ready.wire`, `.conf.hi`  | Resolved/high-confidence/"wired"                      |
| `color.semantic.warning`   | `#d4a850` / text `#9a6a1a` on `#fbf2e2` | `.ready.part`, `.conf.mid` | Partial / mid-confidence                              |
| `color.semantic.error`     | uses `--accent` family                  | `.conf.none`, `.fail-hero` | Errors reuse the rose accent, not a separate red      |
| `color.semantic.mock`      | `#a8a4b8`                               | `.ready.mock`, `.mock-tag` | "Visual only / no backend" muted lavender             |


Gradients / overlays:

- **Food thumbnails** are 135° two/three-stop gradients keyed by a recipe "theme"
(`salmon`, `bowl`, `greens`, `warm`, `cool`, `cream`, `berry`) — see `THEME` map in
`ui.jsx`. These stand in for photography. **(assumption)** In production these become real
recipe images with the gradient as the loading/empty fallback.
- **Accent banner** gradient: `linear-gradient(135deg, #fdf3f0, #fae8e2)` (Today hero, agent
prompt, fail hero use accent-soft family).
- **Grain overlay** on hero images: radial dotted texture + corner highlight (decorative).
- **Translucency**: sticky bars use `rgba(255,255,255,0.94–0.97)` + `blur(14px)`; scrim is
`rgba(0,0,0,0.4)`.

### Typography

Font family: **Inter** (`--font`), with system fallbacks; weights 400/500/600/700 loaded.
Base size 15px, line-height 1.45, antialiased. No separate display face — Inter does
everything, tightened with negative letter-spacing at large sizes.


| Proposed role | Size / weight / spacing                           | Prototype source                                                  |
| ------------- | ------------------------------------------------- | ----------------------------------------------------------------- |
| `display`     | 28px / 600 / `-0.022em`                           | `.greet .name` (greeting)                                         |
| `headline`    | 24px / 600 / `-0.018em`                           | `.sheet-body h1`, recipe detail title                             |
| `title`       | 22px / 600 / `-0.018em`                           | `.section-title`                                                  |
| `title.sm`    | 17–18px / 600 / `-0.01em`                         | section titles inside flows, `.sec-h`, card titles                |
| `subtitle`    | 16px / 600 / `-0.01em`                            | `.day-head h4`, `.dc-head .t`                                     |
| `body`        | 14–15px / 400–500 / 1.45–1.55                     | `.section-sub`, `.desc`, `.step p`                                |
| `label`       | 14px / 600 / `-0.005em`                           | `.btn`, list row labels                                           |
| `label.caps`  | 11px / 600 / `0.06em` / UPPERCASE                 | `.f-label`, `.banner .stat .l`, macro tile labels                 |
| `caption`     | 12–13px / 400–500                                 | `.muted`, `.sub`, `.fc-k`                                         |
| `metric`      | 18–32px / 600 / `-0.01..-0.02em` + `tabular-nums` | `.banner .stat .v`, `.macro-cell .v`, builder calorie tile (32px) |
| `metric.unit` | 11–13px / 400 / tertiary                          | the `<span class="u">` after metric values                        |
| `mono`        | 11px / `tabular`/monospace                        | `.trace` (solver trace block)                                     |


Conventions to carry over:

- **Tabular numerals** everywhere numbers align or update live (macros, quantities,
percentages, kcal). In Flutter: `FontFeature.tabularFigures()`.
- **Negative letter spacing** scales with size (bigger = tighter).
- **Uppercase micro-labels** (11px, 0.06em tracking) for stat captions and field labels.

### Spacing

Observed rhythm (px). Token scale is a **proposal** fitted to the observed values:


| Proposed token | px    | Typical use                                                      |
| -------------- | ----- | ---------------------------------------------------------------- |
| `space.xs`     | 4     | icon gaps, progress segment gaps, tight stacks                   |
| `space.sm`     | 8     | chip gaps, intra-card small gaps, meal-slot list gap             |
| `space.md`     | 12    | card-to-card gaps, control gaps, row gaps                        |
| `space.lg`     | 16–18 | card padding, section internal spacing                           |
| `space.xl`     | 20–24 | screen gutters (20), section top (24), banner padding            |
| `space.2xl`    | 32+   | hero spacing, sheet body bottom padding (120–130 for sticky CTA) |


Fixed structural values: screen horizontal gutter **20px**; section top **24px**; card
padding **14–22px** (commonly 18); sheet body bottom padding **~120px** to clear the sticky
CTA; mobile column **max-width 480px**.

### Radius


| Proposed token | Value | Source      | Use                                                 |
| -------------- | ----- | ----------- | --------------------------------------------------- |
| `radius.sm`    | 8px   | `--r-1`     | Buttons, thumbnails, small chips, inputs            |
| `radius.md`    | 12px  | `--r-2`     | Cards, rows, fields, segmented (when not pill)      |
| `radius.lg`    | 16px  | `--r-3`     | Hero cards, day cards, banners, large containers    |
| `radius.xl`    | 24px  | `--r-4`     | Reserved / extra-large (declared, sparingly used)   |
| `radius.pill`  | 999px | inline      | Chips, tags, pills, search bar, num-pill, segmented |
| `radius.frame` | 28px  | media query | Outer device frame on wide viewports (preview only) |


### Elevation

A 4-step soft shadow scale; shadows are **subtle and reserved for interaction/lift**, not
default-on for every card (cards rely on borders).


| Proposed token  | Value                          | Source         | Use                                            |
| --------------- | ------------------------------ | -------------- | ---------------------------------------------- |
| `elevation.0`   | none (1px border)              | `.card`        | Default resting cards                          |
| `elevation.1`   | `0 1px 2px rgba(0,0,0,0.04)`   | `--shadow-1`   | Row hover, segmented active thumb, field hover |
| `elevation.2`   | `0 2px 8px rgba(0,0,0,0.06)`   | `--shadow-2`   | Card hover lift (`.card-hover`)                |
| `elevation.3`   | `0 6px 20px rgba(0,0,0,0.08)`  | `--shadow-3`   | Floating device frame                          |
| `elevation.cta` | `0 -4px 16px rgba(0,0,0,0.04)` | `--shadow-cta` | Upward shadow on sticky bottom bar             |


### Borders

- Default border: **1px solid `color.line.default`** on essentially every card, row, chip,
and input. This is the primary separation mechanism (more than shadow).
- Inner separators: **1px solid `color.line.soft`** between rows inside a list/card.
- Inputs/strong: **1px solid `color.line.strong` (~#ddd)**.
- Dashed borders signal **"empty / add"**: empty meal slot, "Add ingredient", "+ Add"
chips (`border-style: dashed`).
- Selected state often = **border becomes `color.text.primary`** (pool row, focused
textarea uses ink-1 border + 3px soft focus ring `rgba(34,34,34,0.06)`).
- Focus ring: `box-shadow: 0 0 0 3px rgba(34,34,34,0.06)` with ink-1 border.

---

## Reusable Component System

Each component below lists: **Purpose · Visual traits · States · Reusable props ·
Macrova screens · Implementation notes.** "Macrova screens" uses the **current** module
names (Profile, Ingredient Hub, Recipe Builder, Recipe Library, Planner Config, Meal Plan
View, Agent Pane).

### Navigation & chrome

**App shell / navigation**

- Purpose: top-level navigation between modules.
- Visual: prototype uses a **bottom tab bar** (5 tabs, icon + 11px label, accent on active,
translucent blurred surface, top hairline). Current app uses a **left sidebar**.
- States: active (accent, heavier icon stroke) / inactive (tertiary).
- Props: `items[]` (icon, label, id), `activeId`, `onChange`.
- Screens: all.
- Notes: **Keep the current sidebar/`IndexedStack` structure.** Restyle the existing
`SidebarNav` with the new tokens (accent active state, hairline divider, icon set). Do not
swap to a bottom bar on desktop. **(assumption)** If a mobile build is targeted later, a
bottom `NavigationBar` variant can reuse the same item model.

**Page header / TopBar**

- Purpose: screen title + one trailing action.
- Visual: sticky, translucent blur, 14×20 padding, hairline bottom border. Either brand mark
  - wordmark (rose) or a 17/600 title; trailing 36px circular icon button.
- States: scrolled (blur over content), with/without action.
- Props: `title?`, `brand?`, `trailing?` (icon button).
- Screens: all.
- Notes: maps to a custom header widget or themed `AppBar` (flat, hairline divider, no
Material elevation).

**Section header**

- Purpose: titled group with optional subtitle and trailing text link.
- Visual: 22/600 title, 14px tertiary subtitle, optional underlined text link ("Edit",
"See all") that turns accent on hover.
- States: with/without subtitle, with/without link.
- Props: `title`, `subtitle?`, `linkLabel?`, `onLink?`.
- Screens: all. **There is already `widgets/section_header.dart`** — extend it, don't add a
second one.

**Sticky CTA bar**

- Purpose: persistent primary action(s) at screen/sheet bottom.
- Visual: fixed, translucent blur, top hairline + upward shadow, left "label + bold detail"
summary, right button(s). Safe-area aware.
- States: 1 primary, or secondary + primary, or up to 3 equal `flex-1` buttons (detail
sheet).
- Props: `label`, `detail`, `actions[]`.
- Screens: Recipe Builder, Planner Config, Agent, Meal Plan View, Recipe detail.
- Notes: Flutter `bottomNavigationBar`/`bottomSheet` slot or a `Stack`-pinned bar.

**Full-screen sheet / flow**

- Purpose: focused task surfaces (config, builder, agent, failure, recipe detail).
- Visual: full-height white surface over a 0.4 black scrim, **slide-up** animation
(`cubic-bezier(0.2,0.8,0.2,1)`, 0.3s), `flow-head` (back button + title + small subtitle +
optional right action), body, sticky CTA.
- States: open/closed; optional multi-step progress segments (`steps-prog`).
- Props: `title`, `subtitle?`, `onClose`, `trailing?`, `progress?`, `children`, `cta`.
- Screens: Planner Config, Recipe Builder, Agent, Recipe/Meal detail, failure.
- Notes: Flutter `showModalBottomSheet(isScrollControlled: true)` full-height, or routed
page with slide transition. On desktop these are currently full screens in the
`IndexedStack`; **(assumption)** keep them as screens/dialogs as appropriate per
breakpoint.

### Cards & content

**Stat / metric card** (`banner .stat`, `macro-cell`)

- Purpose: show a value vs target.
- Visual: tint surface, 11px uppercase tertiary label, large tabular metric with a small
unit span, optional 4px progress bar (macro-colored).
- States: default / low / over (bar color shifts to fat color); optional `pro/carb/fat`
variant.
- Props: `label`, `value`, `unit?`, `progress?`, `variant?`.
- Screens: Profile (daily targets), Meal Plan View (weekly totals), Recipe Builder (live
nutrition), recipe detail.
- Notes: pairs well with the existing `macro_display.dart` / `nutrition_totals_panel.dart`.

**Recipe hero card** (`recipe-hero`)

- Purpose: featured/"up next" recipe.
- Visual: 16:10 gradient image with badge + heart, body with meta row (time · servings ·
cuisine), 18/600 title, description, macro footer separated by hairline.
- States: hover lift, generated/pinned badge variants, favorite toggle.
- Props: `recipe`, `badge?`, `onTap`, `onFavorite?`.
- Screens: Recipe Library (featured), Meal Plan View / Today-equivalent (up next).
- Notes: extends `widgets/recipe_card.dart`.

**Recipe row** (`recipe-row`) & **recipe mini** (`recipe-mini`)

- Purpose: compact list item / horizontal carousel item.
- Visual: row = 64px thumb + name + sub + right-aligned kcal/protein; mini = 4:3 thumb +
name + sub, 240px wide, scroll-snap carousel.
- States: hover shadow (row), tap.
- Props: `recipe`, `onTap`, `trailing?`.
- Screens: Recipe Library (list + carousels), Planner Config (pool, as selectable variant),
Meal Plan View (suggestions).

**Day card** (`day-card`) + **meal slot** (`meal-slot`)

- Purpose: a planned day and its meal slots.
- Visual: card with tappable `day-head` (day + date, meal/workout count, right kcal/protein),
expandable `day-meals` list of slots. Slot = time + 44px thumb + name/sub + optional pin
dot, on a tint surface.
- States: slot `ok` / `pinned` (warm tint + pin dot) / `empty` (dashed, centered "+ Add") /
`warn` (inline ⚠ in sub) / workout (dashed, workout icon). Day open/closed.
- Props: `day`, `meals[]`, `expanded`, `onToggle`, `onOpenMeal`, `onAddSlot`.
- Screens: Meal Plan View (primary), Profile (schedule template uses slot styling).
- Notes: This is the core planner surface. Preserve real states: pinned, empty, warn, and
workout placement between meals. Maps to `widgets/meal_card.dart` (extend).

**Constraint / tag chip** (`tag`, `pill`, `wo-chip`, `chip-pick`)

- Purpose: tags, filters, selectable options, workouts, day counts.
- Visual: pill (999px), 12–13px, soft fill + hairline. Variants: default, `accent` (soft
rose), `dark` (ink fill, white), `pinned` (warm), dashed `add`.
- States: default / selected (`on` → ink-1 fill white text, or accent) / add (dashed) /
removable (× affordance).
- Props: `label`, `selected?`, `variant?`, `leadingIcon?`, `onTap?`, `onRemove?`.
- Screens: Recipe Library (filters), Profile (allergies/likes/dislikes), Planner Config
(day count, workouts), Agent (parsed constraints), recipe detail (tags).
- Notes: **One chip widget with variants**, not many. Keep "required vs preferred" tag
semantics in data, not in chip styling (chip is presentation only).

### Forms & inputs

**Field card** (`field-card`) / **settings row** (`settings-list .row`)

- Purpose: tappable labeled value that opens a deeper editor.
- Visual: white card/row, key (12px tertiary) over value (15/600), trailing chevron.
- States: hover (subtle border/shadow), pressed.
- Props: `label`, `value`, `onTap`, `trailing?`.
- Screens: Profile (planner engine settings), Planner Config.

**Numeric pill** (`num-pill`) / **qty input** (`qty-input`)

- Purpose: increment/decrement (servings) and number+unit entry (ingredient qty).
- Visual: pill with − / value / + (38px tap targets, tabular value); qty input = number
field + unit `select`, hairline divider between.
- States: focus, min-clamped.
- Props: `value`, `onChange`, `min?`, `step?`, `unit?`, `units[]?`.
- Screens: Recipe Builder (servings, ingredient qty).

**Segmented control** (`segmented`) / **busyness segment** (`busy-seg`)

- Purpose: 2–3 way exclusive choice; 1–4 busyness band.
- Visual: pill track (soft) with active = white pill + shadow-1; busyness = boxed 1–4 with
ink-1 active.
- States: each option on/off.
- Props: `options[]`, `value`, `onChange`.
- Screens: Profile (deficit on/off), Planner Config (planning mode, ingredient source,
deficit), Recipe Builder (per-serving vs total).

**Search field** (`search-bar`)

- Purpose: search entry.
- Visual: pill, search icon, placeholder text, trailing `⌘K` kbd hint.
- States: idle/focused.
- Props: `placeholder`, `onTap`/`onChanged`, `shortcutHint?`.
- Screens: Ingredient Hub.

**Ingredient editor row** (`ing-edit`) / **step editor** (`step-edit`)

- Purpose: editable ingredient (name, source, per-100g kcal, computed kcal, qty+unit,
delete) and numbered instruction textarea.
- Visual: white card; live computed kcal in accent-deep; numbered circle (accent-soft) for
steps; dashed "Add ingredient / Add step" affordance.
- States: editing, focus ring, removable.
- Screens: Recipe Builder.

### Specialized

**Resolve / match card** (`resolve-card`, `match-card`, `custom-list .ci`)

- Purpose: ingredient resolution review (USDA match confidence + accept/override/create).
- Visual: white card, warning icon, query, confidence chip (`hi/mid/none` color-coded),
match description, macro chips, action buttons.
- States: high / mid / no-match confidence; pending.
- Screens: Ingredient Hub (needs-review), Agent (matched).
- Notes: confidence colors reuse semantic success/warning/error tokens.

**Macro split bar + legend** (`macro-split`, `split-legend`) and **micro rows** (`micro-r`,
`plan-micro`)

- Purpose: macro distribution and per-nutrient progress vs target.
- Visual: 7px stacked bar (pro/carb/fat) + legend; micro rows = name + 4px bar + percent,
grouped by category, `low`/`over` color shifts.
- Screens: Recipe Builder (live), Meal Plan View (weekly micros), recipe detail.
- Notes: maps to existing `micronutrient_bar.dart` — extend with the macro split.

**Agent prompt + parse/generate rows** (`agent-prompt`, `parse-row`, `gen-row`, `spinner`)

- Purpose: NL prompt echo, parsed constraint list, matched recipes, generating-gaps with
spinner/done states.
- Visual: accent-gradient prompt card; parse rows (key + value chip); gen rows with spinner
/ done badge / queued (dimmed).
- States: queued / running (spinner) / done (check). 
- Screens: Agent Pane.
- Notes: states must reflect real pipeline phases (parse → match → generate → validate),
never fake progress.

**Advisory / warning** (`advisory`) and **failure hero + fix rows + trace**
(`fail-hero`, `fix-row`, `trace`)

- Purpose: success-with-warnings advisories and structured infeasibility diagnosis.
- Visual: advisory = circular `!`/`i` badge + title + description. Failure = accent-soft hero
with uppercase "Infeasible" kicker, plain-language cause (emphasized number), "hardest
constraint" card with bar, suggested-fix rows, collapsible monospace solver trace.
- States: warn vs info; trace open/closed.
- Screens: Meal Plan View ("things to know"), failure flow.
- Notes: This is the visual home for the backend's structured failure codes
(`FM-`*, `fix_hint`). Keep the distinction between **success-with-warnings** and
**actionable failure** — the prototype already separates them.

**Readiness chip** (`ready` wire/part/mock) / **mock tag** (`mock-tag`)

- Purpose: honestly label backend-backed vs partial vs visual-only UI.
- Visual: tiny dotted chip; green=wired, amber=partial, lavender=mock; dashed `mock-tag`.
- Screens: cross-cutting (dev/QA affordance).
- Notes: Strongly recommended to keep as a **debug/dev-only** overlay aligning with AGENTS.md
"Known Partial or Mock Areas." **(assumption)** hide in production builds.

**Empty / loading / error states**

- Empty: dashed-border slot/affordance with centered muted "+ Add…" text (meal slot empty,
ingredient add, USDA empty card with cloud icon).
- Loading: `spinner` (2.5px ring, accent top, 0.8s spin); skeleton not explicitly present —
**(assumption)** add gradient-thumb placeholders as skeletons.
- Error: accent-soft hero/cards with kicker + plain-language message + fixes; never a raw
exception string.

---

## Interaction Patterns

Only patterns visible or strongly implied by the prototype:

- **Card tap → open sheet.** Recipe cards/rows/minis open the detail sheet; day-head toggles
expand/collapse; settings/field rows open editors. Cursor pointer + hairline/shadow hover.
- **Hover lift.** `.card-hover` raises to shadow-2 + `translateY(-1px)`; rows go to shadow-1.
(Desktop-relevant; on touch this is just a pressed state.)
- **Pressed.** Buttons `transform: scale(0.99)` on `:active`.
- **Chip / pill selection.** Tap toggles `on` (ink-1 fill, white text) for filters and day
counts; accent variant for constraints; dashed "add" chips create.
- **Segmented switch.** Tapping an option slides the active white pill (mode, source,
deficit, per-serving/total).
- **Expand/collapse.** Day cards expand inline; `disclose`/`details` rotate a chevron 90°;
micronutrients toggle open with a rotating chevron; solver trace expands.
- **Pool / checkbox rows.** Tap toggles a checkbox (transparent→ink fill check) and the row
border/background; multi-select.
- **Planner slot interaction.** Tap filled slot → meal detail; tap empty slot → add flow;
pin via detail sheet ("Pin meal"/"Unpin"); swap / mark cooked actions in the slot's detail
CTA.
- **Numeric steppers.** −/+ clamp to a minimum; qty fields accept typed numbers and a unit
select; nutrition recomputes live (server-calculated label).
- **Agent panel.** Prompt echo with Edit/Re-record; parsed rows are read-back; generating
rows animate spinner→done; Cancel on running; Apply commits to a plan.
- **Sheet dismissal.** Tap scrim or back button closes; sheets slide up on open.
- **Favorite/heart.** Toggle affordance on hero/detail images (visual only in prototype).

Do not invent business logic beyond these. Where the prototype shows an action with no
backend (e.g., heart, swap), wire it only if a real endpoint exists; otherwise show an honest
placeholder.

---

## Screen Translation Map

Current module names are authoritative. The prototype's 5 tabs + flows map onto the 7
current modules as follows.

> **Prototype → current module key:** Today (no current equivalent; a dashboard concept) ·
> Plan → **Meal Plan View** · Recipes → **Recipe Library** · Pantry → **Ingredient Hub** ·
> You → **Profile** · config flow → **Planner Config** · builder flow → **Recipe Builder** ·
> agent flow → **Agent Pane** · detail/failure → shared sheets.

### Profile (prototype: "You" + parts of config "01 Targets")

- **Reuse:** profile summary card (avatar + name + meta + Edit), daily-targets stat grid,
deficit segmented toggle, schedule-template list (meal-slot styling), allergies/likes/
dislikes chip groups, planner-engine settings list, "coming soon" mock list.
- **Preserve:** all existing `ProfileProvider` fields, profile load/merge logic, LLM
credential state and the LLM-ready gate.
- **Share:** stat card, segmented control, chip group, settings row, section header.
- **Don't copy:** the prototype's invented profile numbers; keep real profile data.

### Ingredient Hub (prototype: "Pantry")

- **Reuse:** search bar (pill + ⌘K hint), counts summary line, filter pills (review/custom/
recent/USDA), resolve cards with confidence chips, custom-ingredient list, USDA empty
state.
- **Preserve:** existing `IngredientProvider`, ingredient search/resolve/match wiring, the
"add to recipe → use Recipe Builder" behavior (currently a snackbar; keep honest until a
real path exists), local-vs-USDA source handling.
- **Share:** search field, resolve/match card, confidence chip, chip, section header,
empty-state card.
- **Don't copy:** the prototype's fabricated USDA matches; keep real provider results and
honest "no match → create custom" flows.

### Recipe Builder (prototype: builder flow)

- **Reuse:** flow header with live "server-calculated" subtitle, name/servings/cook-time
fields, **live nutrition card** (dark calorie tile + macro tiles + macro split + collapsible
micros + per-serving/total segmented), ingredient editor rows (computed kcal), step editor,
"generate variations on the server" accent card.
- **Preserve:** `RecipeBuilderCoordinator`/`RecipeProvider` logic, server-calculated
nutrition, LLM generation pipeline gating (validate-before-persist), unit handling.
- **Share:** stat/metric tiles, macro split, micro rows, num-pill, qty input, segmented,
section header, sticky CTA.
- **Don't copy:** client-side fake nutrition math as the source of truth — the prototype
computes locally for preview, but production must keep server calculation authoritative
(it even labels the source).

### Recipe Library (prototype: "Recipes")

- **Reuse:** featured hero card, filter scroll-row of pills, themed carousels by group,
full "all recipes" list (recipe rows), "+ New recipe" CTA.
- **Preserve:** `RecipeProvider` data, real tag filtering (respect required vs preferred tag
semantics; don't hard-filter on legacy `Recipe.tags`), library sync state.
- **Share:** recipe hero, recipe row, recipe mini/carousel, filter chip, section header,
sticky CTA.
- **Don't copy:** hardcoded group membership; derive groups from real tags/queries.

### Planner Config (prototype: config flow)

- **Reuse:** multi-step progress segments, numbered sections (01 Targets … 05 Pool), horizon
chip row (1–7), planning-mode + ingredient-source segmented controls with help text,
per-day schedule blocks (meals-per-day chips, per-meal busyness 1–4, workouts-between-meals
chips), recipe-pool selectable rows, generate CTA.
- **Preserve:** real planner contract — deterministic vs assisted modes, local vs USDA
source, 1–7 day horizon, busyness bands, workout placement, pool selection; **the LLM-ready
gate that falls back to deterministic** when not ready.
- **Share:** segmented, chip-pick, busyness segment, workout chip, pool row, field help,
section header, sticky CTA, progress segments.
- **Don't copy:** any config field not backed by the planner config contract; confirm field
names against backend before wiring.

### Meal Plan View (prototype: "Plan" + "Today")

- **Reuse:** week summary header (date range + on-target percentages), status chips
(generated/pinned/leftover-batch), expandable day cards with meal slots (incl. empty/warn/
workout states), weekly macro grid, weekly micronutrient grid, advisories ("things to
know"), entry into failure diagnosis.
- **Preserve:** `MealPlanProvider`, real plan results (`MealPlanResult`: success,
termination_code, warnings, report), the success-with-warnings vs failure distinction,
per-day UL enforcement semantics, the calendar toggle currently rendering a placeholder
(keep honest).
- **Share:** day card, meal slot, stat card, macro/micro bars, advisory, failure hero/fix/
trace, chip, section header, sticky CTA.
- **Don't copy:** fabricated weekly totals; bind to real plan + tracker data. The "Today"
dashboard is a **new concept** — see Open Questions before adding a module.

### Agent Pane (prototype: agent flow)

- **Reuse:** accent prompt card (You said + Edit/Re-record), parsed-constraints list,
matched-recipes cards, generating-gaps rows (spinner/done/queued), apply CTA.
- **Preserve:** `LlmConfigProvider` gate (Agent vs Setup screen), the real plan-from-text /
constraint-parsing pipeline, validate-before-use, honest progress tied to pipeline phases.
- **Share:** agent prompt, parse row, match card, gen row, spinner, section header,
sticky CTA.
- **Don't copy:** simulated confidence scores or fake generation timing; reflect real
pipeline output.

---

## Flutter Implementation Recommendations

> Implementation guidance only — **do not write production code yet** (per task and repo
> "preserve functionality before visual polish").

### Where visual tokens live

- Add a `frontend/lib/theme/` directory (or extend the single `theme.dart`):
  - `tokens.dart` — raw constants: `MacrovaColors`, `MacrovaSpacing`, `MacrovaRadius`,
  `MacrovaElevation`, `MacrovaTypography` (mirrors the token tables above).
  - `app_theme.dart` — builds `ThemeData` from tokens: `ColorScheme` (light), `TextTheme`
  mapped to the type roles, `CardThemeData`, `ChipThemeData`, `InputDecorationTheme`,
  `FilledButton`/`OutlinedButton` themes, `SegmentedButton` theme.
  - Optionally a `ThemeExtension<MacrovaTokens>` for non-Material tokens (macro colors,
  pinned, semantic mock, line.soft, etc.) so widgets read them via
  `Theme.of(context).extension<MacrovaTokens>()`.
- Replace `colorSchemeSeed: Colors.blue` with an explicit scheme seeded/overridden to the
rose accent + neutral surfaces. Keep `useMaterial3: true`.

### Component folder structure

```text
frontend/lib/
  theme/            # tokens + ThemeData + ThemeExtension
  widgets/          # extend existing shared widgets, add new shared ones
    section_header.dart      (exists — extend)
    recipe_card.dart         (exists — extend: hero/row/mini variants)
    meal_card.dart           (exists — extend: slot states)
    macro_display.dart       (exists — extend)
    micronutrient_bar.dart   (exists — extend: macro split)
    nutrition_totals_panel.dart (exists)
    macrova_chip.dart        (new: tag/pill/filter/workout variants)
    stat_card.dart           (new)
    segmented_control.dart   (new, or theme SegmentedButton)
    num_pill.dart            (new)
    sticky_cta.dart          (new)
    macrova_sheet.dart       (new: flow scaffold + slide-up + header + CTA)
    confidence_chip.dart     (new)
    advisory_card.dart       (new)
    failure_panel.dart       (new: hero + fix rows + trace)
    readiness_chip.dart      (new, dev-only)
    empty_state.dart         (new)
```

### Naming

- Prefix shared visual widgets with `Macrova…` only where a Material name would collide
(e.g. `MacrovaChip`, `MacrovaSheet`); otherwise use plain descriptive names (`StatCard`,
`StickyCta`, `NumPill`). Stay consistent with the existing `*_card.dart` / `*_bar.dart`
naming.

### Avoiding duplicate models & keeping visuals separate from contracts

- **Visual widgets take view-model/primitive props, never raw DTOs by reference for new
models.** Reuse existing `models/` (`recipe.dart`, `ingredient.dart`, `user_profile.dart`,
`nutrition_summary.dart`, `models.dart`, agent models). Do **not** create parallel models
to match the prototype's `data.js`.
- Map existing DTOs → widget props in the screen/provider layer (or small private mappers),
so the design system stays presentation-only and contract-agnostic.
- The prototype's `data.js` is **fixture data**, not a schema. Ignore its shapes; bind
widgets to real provider state.
- Keep tag styling decoupled from tag semantics: chips render a label + variant; "required
vs preferred / approved vs proposed" stays in data/provider logic.

### Migration order (screen-by-screen, low risk)

1. **Tokens + theme** first (additive; no behavior change). Verify `flutter analyze` and
  visual smoke.
2. **Shared widgets** next, extending existing ones (`section_header`, `recipe_card`,
  `meal_card`, `micronutrient_bar`), then new primitives.
3. Restyle screens in this order (least to most stateful):
  **Profile → Recipe Library → Ingredient Hub → Recipe Builder → Planner Config →
   Meal Plan View → Agent Pane.**
4. For each screen: swap visuals only, keep provider calls/state intact, run
  `cd frontend && flutter analyze && flutter test` after each.
5. Defer any IA change (sidebar→tabs, adding a "Today" dashboard) until after the restyle is
  stable and the IIA question is answered.

### Validation

- `cd frontend && flutter analyze && flutter test` after each step (per `frontend.mdc` and
task-router `flutter-ui-redesign`).
- No backend/OpenAPI changes expected from a pure visual pass; if any DTO field is touched,
re-run `python3 scripts/run_export_openapi.py --check`.

---

## Risks / Anti-Patterns

- **IA drift:** Adopting the bottom-tab/Today-dashboard structure would change navigation and
add a module. Restyle first; treat structure change as a separate, explicit decision.
- **Treating `data.js` as a contract:** it is fixture data. Binding new models to it would
create duplicate/parallel models — forbidden by repo rules.
- **Client-side nutrition becoming authoritative:** the builder computes locally for preview;
production must keep server-calculated nutrition as the source of truth (the prototype even
labels the source).
- **Faking pipeline/progress:** agent generating rows and confidence scores must reflect real
pipeline phases and provider results, not animations.
- **Hiding planner failures:** preserve structured failure reporting and the
success-with-warnings vs actionable-failure split; don't collapse into generic errors.
- **Over-shadowing:** the design relies on hairline borders; defaulting every card to a drop
shadow breaks the calm aesthetic. Reserve shadow for hover/lift/floating.
- **Hardcoded gradients/images:** food gradients are placeholders; wire real images with the
gradient as fallback, not as permanent art.
- **Chip variant sprawl:** build one chip widget with variants, not many near-duplicates.
- **Accent overuse:** rose is a single, sparing accent; spreading it across surfaces dilutes
the identity.
- **Shipping the readiness/mock chips to production** unless intentionally kept as a dev
overlay.

---

## Open Questions

1. **Navigation model:** Keep the desktop sidebar + `IndexedStack` (7 modules), or move
  toward the prototype's bottom tabs? Is a responsive shell (sidebar on wide, bottom bar on  narrow) desired? **(assumption: keep current sidebar; restyle only.) Affirmative.**
2. **"Today" dashboard:** The prototype's strongest screen is a "Today" home (greeting,
  progress banner, up-next, agent entry, today's plan, suggestions). It has **no current
   module**. Add as a new module, fold into Meal Plan View, or skip? Needs product decision. **Add as a new module.**
3. **Food imagery:** Are real recipe images planned, or do gradients become the permanent
  visual? Affects card design and asset pipeline. **Real recipe images are planned.**
4. **Mobile vs desktop target:** Prototype is 480px mobile; current app is desktop-first.
  Which form factors are in scope determines breakpoints and shell behavior. **Both are in scope correct? I want both mobile and desktop support. Use your best judgement in terms of resolution.**
5. **Favorites / swap / mark-cooked:** prototype shows these actions — are there (or will
  there be) backend endpoints, or should they be hidden until supported? **Favourites can be integrated as a tag with special behaviour. Swap is not needed. Mark cooked can be a visual action for now, just for the user to keep track of the meals that have been cooked. No functional importance planned.**
6. **Calendar view:** Meal Plan View currently has a placeholder calendar toggle. Should the
  redesign build it, or keep the honest placeholder? **Build it.**
7. **Readiness chips in production:** keep as a dev-only overlay, or drop entirely? **Drop entirely.**
8. **Dark mode:** prototype is light-only. Is dark mode in scope (would need a second token
  set)? **Yes.**

---

## Next Agent Handoff

For the implementing agent (route as `flutter-ui-redesign`; specialists: flutter-wiring-agent
to preserve behavior, test-coverage-agent):

1. **Read first:** this doc, `AGENTS.md` (Frontend Architecture Rules), `frontend.mdc`,
  `frontend/lib/theme.dart`, `frontend/lib/widgets/app_shell.dart`, and the target screen +
   its provider before editing.
2. **Start with tokens:** implement `theme/tokens.dart` + `theme/app_theme.dart` from the
  token tables here. Pure addition; run `flutter analyze`.
3. **Extend existing shared widgets** before adding new ones; do not duplicate
  `section_header`, `recipe_card`, `meal_card`, `micronutrient_bar`.
4. **Restyle one screen at a time** in the migration order above; keep all provider/state/
  contract code unchanged; run `flutter analyze && flutter test` after each.
5. **Do not** create models from `data.js`, invent API fields, change navigation/IA, or wire
  unsupported actions without confirming a backend endpoint exists.
6. **Resolve Open Questions 1 & 2 with the user** before any structural/navigation change.
7. **Report** what changed, what was run, and update `docs/usage/flutter-setup.md` only if
  workflow/setup changes (otherwise note "Docs checked, no update needed").

```

```

