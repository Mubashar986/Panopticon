# Frontend Workflow: Design System Enforcement (Picasso + Vermeer + Escher)

Hand this whole file to another agent — paste it into its system prompt, project instructions, or `CLAUDE.md`. It tells the agent when to use **Picasso** (design-intake), **Escher** (backend-aware data wiring, flags backend gaps), and **Vermeer** (visual/heuristic build-enforcement), so no frontend work happens off-system and no UI silently pretends data exists that the backend doesn't provide.

**Division of labor:** Picasso decides the system once. For components with real data, Escher runs first to nail down the actual data contract and flag anything the backend is missing. Vermeer then builds the visual/interaction layer strictly from tokens and the heuristic checklist, for every component regardless of whether it touches data.

---

## Part 1 — The standing rule (paste this into the other agent)

```
STANDING RULE — Design System Workflow

Before starting ANY frontend/UI task — a new page, component, mockup,
styling change, "build me a website/app UI," "add a button/card/form,"
or anything visual — follow this sequence. Do not skip it for small
tasks; a "quick" component built off-system is exactly how design
drift starts, and it costs more to unwind later than to do right now.

STEP 1 — Check for a design system
Look for design-system/tokens.json (or design-tokens.json,
.design/tokens.json, design-system/DESIGN_SYSTEM.md) in the project.

- Found it -> go to Step 2.
- Not found -> do NOT invent colors, fonts, or spacing. Tell the user
  no design system is defined yet, and run the Picasso skill (design
  intake interview) before writing any UI code. Only proceed without
  one if the user explicitly says they want a throwaway/one-off with
  no system — and even then, say plainly that nothing built now will
  be reusable as a baseline later.

STEP 2 — Does this component touch real data?
- No (purely static/presentational) -> go straight to Step 3 (Vermeer).
- Yes (displays, submits, or reacts to backend data) -> run Escher
  FIRST to establish the real data contract:
    - read the actual API/schema/backend code, don't guess field shapes
    - mirror real backend validation constraints in the frontend
    - if the frontend needs something the backend doesn't provide yet,
      STOP inventing mock data silently. Flag it in
      design-system/backend-requirements.md (create if absent), tell
      the user plainly, and only build a mock if the user explicitly
      agrees to one — clearly marked as temporary in the code.
  Then proceed to Step 3 for the visual/interaction layer.

STEP 3 — Build with the Vermeer discipline
Load the tokens file fully, then:
- every color/font/spacing/radius/shadow/motion value must trace to
  a token — never a raw invented value
- every interactive element gets its full state set (default, hover,
  active, focus, disabled, loading)
- run the heuristic checklist (visibility of status, error prevention,
  consistency, etc. — see Vermeer's SKILL.md for the full table) on
  every component, not just the token values
- if something needed isn't in the tokens file, STOP and ask the user
  rather than guessing — then write the accepted answer back into
  tokens.json so it's captured for next time
- before presenting output, self-audit: scan for stray hex codes,
  arbitrary px values, off-system font names, or interaction patterns
  that skip a heuristic check

STEP 4 — Keep the system in sync
If tokens.json changed during Step 3, bump meta.last_updated and
briefly tell the user what was added and why. If backend-requirements.md
changed during Step 2, make sure every entry is either OPEN with a
flagged mock, or RESOLVED with the mock removed — never a mock with
no matching flag.

NON-NEGOTIABLE: repeat this check every session. An agent with no
memory of past sessions must re-check for the tokens file (and any
open backend requirements) every time — skipping the check is, from
the user's perspective, indistinguishable from silently reintroducing
drift.
```

---

## Part 2 — Getting the actual skill files to the other agent

The rule above only works if the agent can actually load Picasso and Vermeer's full instructions when it needs them. How you deliver that depends on what the other agent is:

### If it's Claude Code
Claude Code skills live as a folder containing `SKILL.md`, placed at:
- **Project-level** (shared with your team via git): `.claude/skills/<skill-name>/SKILL.md`
- **User-level** (available across all your projects): `~/.claude/skills/<skill-name>/SKILL.md`

```bash
mkdir -p .claude/skills
cd .claude/skills
unzip /path/to/picasso.skill -d picasso
unzip /path/to/vermeer.skill -d vermeer
unzip /path/to/escher.skill -d escher
```

Then add the standing rule from Part 1 to your project's `CLAUDE.md` so it's loaded automatically every session — Claude Code skills are triggered by their `description` matching the task, but the standing rule makes the *sequence* (check tokens → Picasso if missing → Vermeer to build) explicit rather than left to chance.

*(Claude Code's skill conventions have moved fast — if `.claude/skills/` doesn't pick them up, run `claude --help` or check Anthropic's current docs to confirm the path hasn't changed.)*

### If it's Claude.ai or Cowork
Upload `picasso.skill`, `vermeer.skill`, and `escher.skill` directly — in Settings, find the Skills section and use "Add skill" / "Upload skill," or click the **Save skill** button on the file card if the .skill file is shared in a conversation. Then paste the Part 1 rule into that agent's custom instructions / project instructions so it applies automatically rather than only when you remember to ask for it.

### If it's some other agent (Cursor, a custom system prompt, a different LLM entirely)
It likely doesn't understand "skills" as a concept — so don't rely on the trigger mechanism at all. Instead:
1. Paste the Part 1 rule into its system prompt / rules file as-is.
2. Also paste the **full contents** of `picasso/SKILL.md`, `vermeer/SKILL.md`, and `escher/SKILL.md` (plus their `references/` files — `token-schema.md`, `heuristics.md`, and Escher's `backend-requirements-template.md`) directly into its instructions or a file it reads on startup, since it has no separate skill-loading mechanism to fall back on — the standing rule references all three by name, so the agent needs their actual content available to follow through.

---

## Part 3 — Sanity check

However you deliver it, confirm the other agent actually picked it up with two quick tests in a project that has no `tokens.json` yet:

1. Ask for something small and frontend-shaped ("add a save button to the settings page"). It should stop and flag that no design system exists rather than just building the button.
2. Once a design system exists, ask for something that needs real data ("show the user's recent orders on the dashboard"). It should check the actual backend/API before building — and if the data isn't available yet, it should say so and write an entry to `design-system/backend-requirements.md` rather than quietly rendering plausible-looking fake orders.

If either check doesn't happen, the corresponding rule isn't wired in yet.
