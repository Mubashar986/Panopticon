# HCI Decision Rules (Nielsen's 10 Heuristics, applied)

This isn't a list to skim — it's the decision procedure. When Picasso, Vermeer, or Escher hit a judgment call (what should this default to, what state does this need, how should this error read), consult the relevant rule below instead of guessing from taste. Each heuristic has a concrete rule for *this workflow specifically*, not just the general principle.

## 1. Visibility of system status
**Principle:** the user should always know what's happening.
**Rule:** every async action (fetch, save, submit, delete) shows a `loading` state from the token system within the perceived-latency window; every state change either visibly confirms or visibly errors — never leaves the screen looking unchanged when something happened underneath it.
**Mainly enforced by:** Vermeer (renders the state), Escher (wires it to real backend timing — a fake instant "success" when the request is still in flight is a status-visibility bug, not a style choice).

## 2. Match between system and the real world
**Principle:** speak the user's language; follow real-world conventions, not internal/database logic.
**Rule:** field order, grouping, and labels follow how the *user* thinks about the task, not the shape of the backend schema. Icons keep their conventional meaning (trash = delete, always). Voice/tone tokens are written in plain words, never internal jargon.
**Mainly enforced by:** Picasso (voice tokens), Escher (don't just render a form in the order fields appear in the database).

## 3. User control and freedom
**Principle:** users need an "emergency exit" for actions taken by mistake.
**Rule:** any destructive or hard-to-reverse action needs a visible undo/confirm path, defined once as a token pattern and reused everywhere — never a one-off. If the UI implies an undo is possible ("Deleted — Undo"), Escher must confirm the backend actually supports reversing it before that promise ships; if it doesn't, that's a backend gap to flag, not a UI detail to fake.
**Mainly enforced by:** Vermeer (the pattern), Escher (verifying the backend honors it).

## 4. Consistency and standards
**Principle:** don't make users guess whether different words, icons, or layouts mean the same thing.
**Rule:** this is the entire reason `tokens.json` exists. No value, pattern, or layout gets invented twice.
**Mainly enforced by:** all three, especially Vermeer.

## 5. Error prevention
**Principle:** a good design prevents the error before it happens — better than a good error message after.
**Rule:** whatever validation constraints the backend enforces (required fields, formats, length limits, permissions), the frontend mirrors *before* the round-trip — so the user finds out at the input, not after a failed submit. Escher is responsible for pulling these constraints from the actual backend contract, not guessing plausible ones.
**Mainly enforced by:** Escher.

## 6. Recognition rather than recall
**Principle:** minimize what the user has to remember; make options and state visible.
**Rule:** for the *system*, this is why `tokens.json` + `DESIGN_SYSTEM.md` exist — nobody re-derives a color from memory. For the *UI*, prefer visible labels and persistent navigation over hidden gestures or icon-only controls, especially for a non-technical audience.
**Mainly enforced by:** Picasso (persistent memory of decisions), Vermeer (visible-over-hidden UI patterns).

## 7. Flexibility and efficiency of use
**Principle:** accelerators for experienced users, but never required for novices.
**Rule:** the default path must work with zero configuration for a non-technical user. Shortcuts, bulk actions, or power-user features layer on top without becoming the primary or only path.
**Mainly enforced by:** Vermeer.

## 8. Aesthetic and minimalist design
**Principle:** every element on screen should earn its place; nothing irrelevant or rarely needed competes for attention.
**Rule:** Picasso's intake produces only the tokens actually needed for this project — no bloated palette "just in case." Vermeer doesn't add decoration that isn't tied to a token or a purpose. If you can't explain why an element is on screen, it shouldn't be.
**Mainly enforced by:** Picasso, Vermeer.

## 9. Help users recognize, diagnose, and recover from errors
**Principle:** error messages in plain language, precisely naming the problem, with a concrete next step — never a code or stack trace.
**Rule:** `voice.error-style` (set by Picasso) is not a suggestion — it's the literal translation layer. When a backend call fails, Escher translates the raw response (`500`, `ECONNREFUSED`, a validation error object) into that plain-language pattern before it ever reaches the screen. A raw status code or stack trace reaching the user is always a bug.
**Mainly enforced by:** Escher.

## 10. Help and documentation
**Principle:** ideally the system needs no explanation — but when help is needed, it should be concrete, task-focused, and easy to find.
**Rule:** empty states and first-run screens include example content or example prompts (the NotebookLM pattern) instead of assuming the user knows what to type or click first. This is a design decision, made once, in the token system's component-state rules — not improvised per screen.
**Mainly enforced by:** Vermeer.

---

Use this file actively: when a build decision isn't obviously covered by an existing token, check whether one of these ten rules resolves it before asking the user or inventing something. Most "small" UX judgment calls are actually one of these ten in disguise.
