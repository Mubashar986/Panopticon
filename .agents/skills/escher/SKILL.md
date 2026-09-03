---
name: escher
description: Builds frontend components and pages wired to REAL backend data and behavior — reads the actual API contract, database schema, or backend code before building, mirrors its constraints in the UI, and explicitly flags anything the frontend needs that the backend doesn't yet provide instead of silently faking it with mock data. Use this whenever a user asks to build a component/page/feature that displays, submits, or depends on real data ("build a dashboard showing our orders," "add a form to update the user's profile," "show the latest results from the API," "wire this component up to the backend"), whenever a frontend task references an API, database, endpoint, or backend service, or whenever building UI reveals that a needed field, action, or real-time update doesn't exist yet on the backend. Works together with Picasso (defines the design system) and Vermeer (enforces it visually) — Escher owns the data/backend side of the same components.
---

# Escher — Backend-Aware Frontend Building

## Why this skill exists

Escher's lithographs are famous for interlocking perfectly — staircases that loop back on themselves, tessellations where every tile's edge is another tile's edge, with no gaps and no impossible seams (well — the *point* of some of his work is impossible geometry, but the technique that makes it convincing is that every edge matches its neighbor exactly). That precision is the model here: a frontend component and the backend it depends on have to fit together with no gap between what the UI expects and what the API actually returns. Left unchecked, an LLM asked to "build a dashboard" will happily invent plausible-looking mock data, ship it, and the seam — the exact place where the UI's assumptions and the backend's reality diverge — becomes invisible until a real user hits it.

This is the third of three skills:
- **Picasso** defines the design system once.
- **Vermeer** enforces it visually — every component's look and interaction pattern.
- **Escher** (this one) enforces it *factually* — every component's data is real, or explicitly flagged as not-yet-real.

For a purely static, no-data component, only Vermeer is needed. The moment a component displays, submits, or reacts to real data, Escher runs alongside Vermeer: Escher decides *what data flows through it and whether that data actually exists*; Vermeer decides *how it looks and behaves* once it does.

## Step 1 — Find the actual backend contract

Before writing a line of UI code that touches data, find the real source of truth. Look for (in rough priority order):
- An OpenAPI/Swagger spec or GraphQL schema file in the project
- Backend route/controller files (Express, FastAPI, Rails, etc.) that define real endpoints
- ORM models / database schema / migrations that define real fields and types
- Existing frontend API client code that already calls real endpoints (a good sign of the actual current contract)
- If none of these are accessible (e.g. backend is a separate service you can't read), ask the user directly for the endpoint shape rather than guessing plausible field names — a guessed field name that happens to be wrong is worse than an honest "I don't know this yet."

Never infer a data shape purely from what would look good in the UI. The UI's needs come second; the backend's actual shape comes first.

## Step 2 — Build against the real contract, not a convenient one

- Use the field names, types, and nesting the backend actually returns — don't rename or restructure them into something tidier for the frontend without a real transformation layer that's clearly labeled as such.
- Respect real constraints: if the backend paginates 20 items at a time, don't build infinite-scroll UI that assumes all data arrives at once; if a field is nullable, the component must handle its absence, not assume it's always present.
- Mirror backend validation in the frontend (heuristic #5, error prevention) — required fields, format rules, permission checks — so users learn about a problem before submitting, not only after a failed round-trip.
- Distinguish real async states precisely: `loading` (request in flight), `empty` (request succeeded, zero results), `error` (request failed) are three different states with three different backend signals — never collapse them into one generic "nothing here" UI. This is heuristic #1 applied honestly, not just cosmetically.
- Translate raw backend errors into the plain-language pattern Picasso defined in `voice.error-style` — a raw `500`, a stack trace, or an internal error code reaching the user is always a bug (heuristic #9). Read `references/heuristics.md` for the full rule set; read `references/token-schema.md` for how `voice.*` tokens are structured.

## Step 3 — When the backend doesn't have what the UI needs

This is the core job of this skill, not an edge case. When you discover the frontend needs a field, endpoint, computed value, permission check, or real-time update that doesn't currently exist:

1. **Don't silently invent mock data and move on.** Say so, plainly, to the user in the moment: "The backend doesn't currently return `order.estimatedDelivery` — I can build this with a placeholder for now, or hold off. Which do you want?"
2. **Write the gap to `design-system/backend-requirements.md`**, using the format in `references/backend-requirements-template.md`. Create the file if it doesn't exist yet. This is the same pattern as `tokens.json` — a canonical, accumulating record, not a one-off comment buried in code.
3. **If the user wants to proceed anyway,** build against a clearly labeled temporary mock (e.g. a function named `mockEstimatedDelivery()` with a `// TODO: backend-requirements.md REQ-4` comment) so the frontend isn't fully blocked — but the flag in `backend-requirements.md` is what keeps this from becoming an invisible, permanent fake.
4. **If a connected tool can file a real backend ticket** (an issue tracker, project board), offer to file it there too — but still record it in `backend-requirements.md` regardless, since the frontend's dependency list should be readable without needing tracker access.

## Step 4 — Keep resolved gaps closed out

When the user says a backend capability now exists, find the matching entry in `backend-requirements.md`, mark it `[RESOLVED]`, and remove the temporary mock from the actual code — a resolved requirement with a mock still silently in place is worse than never having built the mock at all, because now nobody has a reason to check.

## Handing off to / working with Vermeer

Escher doesn't own visual styling — once the data contract and states are settled, hand the "how does this look" decisions to Vermeer's token/heuristic discipline. In practice this usually means: figure out the data shape and states here, then style the result the way Vermeer's checklist requires. Don't let data-shape convenience quietly override a token — if the backend returns a color or a display value, it still gets mapped through `tokens.json`, not used raw.
