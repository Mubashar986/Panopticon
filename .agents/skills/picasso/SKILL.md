---
name: picasso
description: Runs a structured design-system intake interview and produces a canonical design tokens file (colors, typography, spacing, radius, shadows, motion, icons, accessibility minimums, voice/tone) for a website or app, grounded in usability heuristics rather than personal taste. Use this whenever a user wants to establish, define, or reset a design system, brand identity, color palette, or visual style BEFORE building any UI — phrases like "let's set up our design system," "help me pick colors and fonts for my site," "define our brand style," "I'm starting a new project and need a look and feel," or "run Picasso." Also trigger this proactively if a user asks to build a UI/frontend/website and no design tokens file exists yet for the project — Picasso should run first so later UI generation (via the Vermeer and Escher skills) has something real to build against instead of guessing.
---

# Picasso — Design System Intake

## Why this skill exists

Left alone, an LLM asked to "build a nice-looking page" will invent a color, a font, and a spacing rhythm on the spot — and invent a *different* one next time it's asked. That's not a style, it's noise. Picasso's job is to have the one conversation where real design decisions get made deliberately, with the user in control, and to write those decisions down permanently so no model — including you — ever has to guess again.

This is the first of three skills that work together:
- **Picasso** (this one) — defines the system, once.
- **Vermeer** — builds visual UI strictly from what Picasso defined.
- **Escher** — wires that UI to real backend data, and flags gaps instead of faking them.
Nothing gets built until Picasso has run at least once for the project.

## Ground every decision in `references/heuristics.md`

Read `references/token-schema.md` (the taxonomy you're filling in) and `references/heuristics.md` (the ten usability rules) before starting the interview. Don't treat the heuristics file as background reading — use it as your actual decision procedure whenever you have to pick a default the user didn't specify. For example: unsure whether to default to icon-only or labeled buttons? That's heuristic #6 (recognition over recall) — for a non-technical audience, default to labeled. Unsure how many colors belong in the palette? That's heuristic #8 (minimalist design) — resist the urge to add "just in case" colors.

## When you run this

1. Check whether a tokens file already exists for this project (common locations: `design-system/tokens.json`, `design-tokens.json`, `.design/tokens.json`, or a `DESIGN_SYSTEM.md`). If one exists, tell the user and ask whether they want to **revise it** or **start fresh** — never silently overwrite an existing system.
2. If none exists, run the interview below.

## The interview

Keep it short and plain-language — this is very likely a non-technical user. Ask about *outcomes and feelings*, not hex codes or CSS. Prefer concrete choices over open questions ("warm or cool palette?" beats "describe your color preferences") — open-ended prompts just push the guessing problem back onto the user, which defeats the point. Where a real elicitation UI is available, use it for the multiple-choice questions instead of writing them as prose — tapping an option is much lower cognitive load than typing an answer (heuristic #7: efficiency without demanding effort from a novice).

Cover, in order, only what's needed to fill the schema — skip anything the user already told you elsewhere in the conversation:

1. **Purpose & audience** — what's the site/app for, who uses it, are they technical or not. This single answer sets your baseline for every heuristic below (a technical/expert audience tolerates more density and fewer guardrails than a non-technical one).
2. **Personality** — 2-3 words the brand should feel like ("calm, trustworthy, minimal" vs "bold, energetic, playful"). Let this drive your default radius (soft vs sharp), motion speed, and color saturation, and briefly explain that connection to the user so the system feels coherent, not arbitrary.
3. **Existing assets** — logo, existing brand colors, or an existing site to match or deliberately break from.
4. **Color** — a primary color (or "surprise me based on personality"), and whether dark mode matters.
5. **Typography** — a general feel (modern/geometric, classic/serif, friendly/rounded) rather than asking them to name fonts — then propose 1-2 real font pairings and let them pick.
6. **Density** — comfortable/spacious vs compact/data-dense. Drives the whole spacing scale.
7. **Voice for errors and empty states** — ask plainly: "when something goes wrong or a screen has no data yet, should it sound formal, friendly, or minimal?" This fills `voice.error-style`, which Escher will later rely on word-for-word to translate raw backend errors (heuristic #9) — don't skip this thinking it's minor; it's the contract between Picasso and Escher.
8. **Accessibility requirements** — ask plainly whether this needs to work well for users with visual impairments or motor difficulties. Default to WCAG AA regardless; ask only if something stricter is needed.

## Producing the output

Fill out the full schema from `references/token-schema.md`, including categories the user didn't explicitly discuss. For anything you're defaulting rather than being told directly, resolve it against `references/heuristics.md` first, then pick a value consistent with their stated personality/density answers, and call it out as a default in your summary so they can correct it.

Write two files:

1. **`design-system/tokens.json`** — the machine-readable source of truth, in the exact shape shown in the reference schema. This is what Vermeer and Escher read.
2. **`design-system/DESIGN_SYSTEM.md`** — a human-readable version of the same data, organized the same way, so a non-technical user can actually look at it and understand what was decided and why.

### Worked example (abridged)

If the user says "calm, trustworthy, minimal" + "comfortable density" + "formal but friendly errors," a reasonable output looks like:

```json
{
  "meta": { "project": "Client Portal", "created": "2026-08-27", "last_updated": "2026-08-27" },
  "color": {
    "semantic": { "primary": "#2563EB", "primary-hover": "#1D4ED8", "bg-surface": "#FFFFFF", "text-primary": "#111827" },
    "state": { "error-bg": "#FEF2F2", "error-text": "#B91C1C", "error-border": "#FCA5A5" }
  },
  "radius": { "sm": "6px", "md": "10px", "lg": "14px" },
  "space": { "4": "16px", "6": "24px" },
  "voice": {
    "tone": "warm, plain-language, no jargon",
    "capitalization": "sentence case",
    "error-style": "plain language + next step, never raw error codes"
  }
}
```
Note the softer radius (10-14px, not sharp 2-4px) following from "calm/trustworthy," and the explicit `error-style` string Escher will later quote back to itself when translating backend failures.

After writing both files, summarize back to the user in plain language: what you set up and why, flagging anything you defaulted rather than were told, and invite corrections before anything gets built against it.

## Updating an existing system

If revising rather than starting fresh: load the existing `tokens.json`, only change the specific values discussed, bump `meta.last_updated`, and leave everything else untouched. Never regenerate the whole file for a small change — that risks silently drifting values nobody asked to change.

## Handing off

Once the tokens file is written, tell the user it's ready to build against — Vermeer handles visual construction, Escher handles wiring it to real data and flagging backend gaps. Neither should freestyle from here.
