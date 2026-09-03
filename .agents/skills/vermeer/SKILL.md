---
name: vermeer
description: Enforces an existing design tokens file AND usability heuristics when building, editing, or reviewing any UI, component, page, or frontend code — never inventing colors, fonts, spacing, or interaction patterns on its own. Use this whenever a user asks to build a website, component, page, mockup, or any frontend UI for a project that has (or should have) a design system, or says things like "build this using our design system," "make sure it matches our brand," "add a new button/card/page," or "check this against our tokens." If no tokens file exists yet for the project, this skill's first job is to say so and point the user to the Picasso skill rather than inventing a design system on the spot. For UI that needs real backend data, hand off to (or run alongside) the Escher skill — Vermeer owns visual/interaction consistency, Escher owns the data contract.
---

# Vermeer — Design System & Heuristic Enforcement

## Why this skill exists

Vermeer was famously exacting — the same light, the same handful of pigments, the same precise geometry, painting after painting, nothing freehanded. That's the standard here: every color, font, spacing value, radius, shadow, and *interaction pattern* in generated UI must trace back to something defined, either in `tokens.json` or in the ten heuristic rules — never invented in the moment. "Invented in the moment" is exactly how a codebase ends up with six shades of almost-the-same blue, or a delete button with no confirmation on one page and a full modal on another.

Vermeer is the middle of three skills: **Picasso** decides the system once; **Vermeer** (this one) builds the visual/interaction layer strictly from it; **Escher** wires whatever Vermeer builds to real backend data and flags what's missing. For a purely static component, Vermeer alone is enough. For anything that touches real data, Vermeer and Escher operate together — Vermeer owns *how it looks and behaves*, Escher owns *whether the data behind it actually exists*.

## Step 1 — Find the tokens file

Look for `design-system/tokens.json`, `design-tokens.json`, `.design/tokens.json`, or `design-system/DESIGN_SYSTEM.md`.

**Found one:** read it fully before generating anything. `references/token-schema.md` documents what each category means if an entry needs interpreting.

**Not found:** stop before writing UI code. Tell the user plainly there's no design system yet, and recommend running Picasso first — guessing now just means redoing everything once real choices are made. If the user insists on a one-off with no system, that's their explicit call, not one you make for them.

## Step 2 — Build against tokens AND heuristics

Every visual value must trace to a token (Step 2a). Every interaction pattern must trace to a heuristic rule in `references/heuristics.md` (Step 2b) — most "how should this behave" judgment calls are one of the ten in disguise, not a matter of taste.

### 2a — Token discipline
- Colors → `color.semantic` / `color.state` tokens only, never a raw hex invented for the occasion.
- Font size/weight → `type.scale` / `type.weight` only.
- Gaps/padding/margin → `space.*` only.
- Radius, shadow, motion timing, icon size → the matching token category, always.

### 2b — Heuristic-driven interaction checklist
Run every component you build through this before considering it done:

| Check | Heuristic | What "done" looks like |
|---|---|---|
| Async actions show progress | #1 Visibility of status | Loading state present, wired to real timing (coordinate with Escher) |
| Labels/icons match user's mental model | #2 Match with real world | No internal jargon, conventional icon meanings only |
| Destructive actions are reversible or confirmed | #3 User control & freedom | Confirm step or undo pattern present, reused from an existing token pattern if one exists |
| Same action looks/behaves the same everywhere | #4 Consistency | No one-off variants of a pattern used elsewhere |
| Obvious mistakes are hard to make | #5 Error prevention | Constraints enforced at input, not just on submit (coordinate with Escher for real backend constraints) |
| User isn't forced to remember things | #6 Recognition > recall | Labeled controls preferred over icon-only / hidden gestures for non-technical audiences |
| Novice path is the default | #7 Flexibility | Zero-config default flow works; shortcuts are additive, not required |
| Nothing on screen is unexplained | #8 Minimalism | Every element ties to a token or a stated purpose |
| Errors are plain-language with a next step | #9 Error recovery | Uses `voice.error-style` verbatim in pattern, never a raw code |
| First-run/empty states help, don't just inform | #10 Help & docs | Example content/prompts present, not just "No data" |

Every interactive component (buttons, inputs, cards, toggles) needs its full state set: `default, hover, active, focus, disabled, loading`, styled consistently with how other components already express those same states — don't design a component's hover state from scratch if `color.primary-hover` already implies one.

## Step 3 — When you need something that isn't in the file

Stop and ask, in plain language, rather than picking a value yourself — frame it with the closest existing options as candidates. Once answered, write the new value back into `tokens.json` (bump `meta.last_updated`) so the decision is captured, not a one-off that quietly drifts. Never silently extend the system — a token that exists only inside one component's code isn't a token, it's exactly the drift this skill exists to prevent.

## Step 4 — Self-audit before presenting output

Re-check what you generated for:
- raw hex codes, rgb() values, or named CSS colors not traced to a token
- arbitrary px/rem values for spacing, font-size, or radius not traced to a token
- font names other than `type.family`
- any interaction pattern (confirmation, error copy, loading behavior) that doesn't match the checklist above

With real file access (e.g. Claude Code on an actual repo), do this as a literal search over the files you just touched — grep for hex patterns, arbitrary bracket values, etc. — and fix any hit before finishing, not just note it. Inline in chat, re-read your own output and correct anything that snuck in.

Report what you found and fixed — this is heuristic #9 applied to your own process, not just the UI's.

## A note on tone

None of this should feel like red tape to the user. Frame constraints as what's *saving* them time and inconsistency. If they push back on a rule, explain the "why" — usually one of the ten heuristics — rather than just citing the rule.
