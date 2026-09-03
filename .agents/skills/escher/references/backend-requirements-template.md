# backend-requirements.md — format

Escher writes to `design-system/backend-requirements.md` (creating it if absent) whenever a frontend task needs something the backend doesn't currently provide. This file is the canonical, tool-agnostic handoff to whoever builds the backend — human or agent. If a real issue tracker is connected (Jira/Linear/GitHub Issues), file it there too, but still record it here so the frontend's dependencies are visible in one place without needing tracker access.

## Entry template

```markdown
## [OPEN] REQ-<sequential-number>: <short title>

- **Needed for:** <component/page that depends on this>
- **What's missing:** <endpoint / field / computed value / real-time update / permission check — be specific>
- **Expected shape:** <request method + path, and response shape if it's an endpoint; field name + type if it's data>
- **Why the UI needs it:** <one sentence — ties back to the actual user-facing behavior blocked without it>
- **Current workaround:** <"none — feature blocked" OR "temporary mock in place, marked TODO in <file>">
- **Flagged:** <date>
```

## Status values
- `[OPEN]` — not yet available, UI is blocked or running on a marked mock.
- `[IN PROGRESS]` — backend work has started (update manually or when told).
- `[RESOLVED]` — backend now provides this; note the date resolved and remove any temporary mock.

## Rules for Escher when writing entries
- One entry per distinct gap — don't bundle unrelated needs into one item.
- Never leave a mock silently in place without a matching OPEN entry here. A mock with no flag is indistinguishable from a real bug six months later.
- When a user says the backend now supports something, find the matching entry, mark it `[RESOLVED]`, and remove the temporary mock from the code.
