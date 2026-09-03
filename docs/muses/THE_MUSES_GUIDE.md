# The Muses: Complete Frontend & Design System Engineering Guide

---

## 1. Executive Summary & Philosophy

**The Muses** is a three-stage frontend discipline that guarantees enterprise-grade consistency, zero style drift, 100% heuristic usability, and flawless data contracts between modern web frontends and backend APIs.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           THE MUSES SEQUENCE                            │
│                                                                         │
│  STAGE 1: PICASSO (Design System Intake)                                │
│  • Conducts structured brand & usability intake                         │
│  • Produces canonical design-system/tokens.json & DESIGN_SYSTEM.md      │
│                                                                         │
│                                 ▼                                       │
│                                                                         │
│  STAGE 2: ESCHER (Backend-Aware Data Wiring)                            │
│  • Inspects real FastAPI/OpenAPI schemas & endpoints before building    │
│  • Flags missing backend fields in design-system/backend-requirements.md│
│  • Translates raw HTTP error codes to plain-language recovery voice     │
│                                                                         │
│                                 ▼                                       │
│                                                                         │
│  STAGE 3: VERMEER (Visual & Heuristic Enforcement)                      │
│  • Enforces 100% token discipline (zero raw hex, zero arbitrary px)     │
│  • Implements all 6 interactive component states                        │
│  • Audits against the 10 Nielsen Norman Usability Heuristics            │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Directory Structure of The Muses Specification

```
Panopticon Project Root
├── design-system/
│   ├── tokens.json                   # Machine-readable token source of truth
│   ├── DESIGN_SYSTEM.md              # Human-readable design system specification
│   └── backend-requirements.md       # Authoritative backend gap register
│
├── docs/muses/
│   ├── THE_MUSES_GUIDE.md            # This overarching guide
│   ├── PICASSO.md                    # Picasso skill & intake specification
│   ├── ESCHER.md                     # Escher backend wiring & gap protocol
│   └── VERMEER.md                    # Vermeer heuristic & token builder
│
└── .agents/skills/The Muses/
    ├── frontend-workflow-agent-instructions.md
    ├── picasso.skill / picasso.md
    ├── escher.skill / escher.md
    └── vermeer.skill / vermeer.md
```

---

## 3. Standing Operating Rule for AI Frontend Agents

When delegating frontend tasks to a frontend agent, copy and paste this exact block into its system prompt or project instructions:

```markdown
### STANDING RULE — Design System & Backend Data Workflow (The Muses)

Before starting ANY frontend/UI task — building a new component, search bar, result card, modal, or page:

1. STEP 1 (Check Tokens): Inspect `design-system/tokens.json`.
   - If missing: STOP immediately. Do NOT invent colors, fonts, or margins. Run the Picasso intake interview to establish tokens first.
   - If found: Load the full token set.

2. STEP 2 (Inspect Backend Contract): If the component touches data:
   - Run Escher: Read the real backend API route handlers (`app/api/routes/`) and Pydantic schemas (`app/api/schemas/`).
   - If the UI needs a field or endpoint the backend does not provide: NEVER silently invent fake mock data. Record the gap in `design-system/backend-requirements.md`, notify the user, and use a tagged temporary mock (`// TODO: backend-requirements.md REQ-X`).

3. STEP 3 (Visual Construction with Vermeer):
   - Every color, font, space, radius, and shadow must trace to a token (zero raw hex codes, zero arbitrary px).
   - Every interactive element must implement all 6 states (`default, hover, active, focus, disabled, loading`).
   - Audit the component against the 10 Nielsen Usability Heuristics.

4. STEP 4 (Self-Audit):
   - Scan modified code for hardcoded `#hex` codes or untokenized pixel values before marking complete.
```

---

## 4. Summary Matrix of The Three Muses

| Capability / Responsibility | Picasso 🎨 | Escher 📐 | Vermeer 🖼️ |
|---|---|---|---|
| **Primary Domain** | Design Tokens & Brand System | API Contracts & Data Truth | Visuals, Layout & Micro-interactions |
| **Key Artifact Produced** | `design-system/tokens.json`<br>`design-system/DESIGN_SYSTEM.md` | `design-system/backend-requirements.md` | Tokenized React UI Components |
| **Usability Rules Enforced** | Brand personality, voice/tone, accessibility baseline | Heuristic #1 (Status), #5 (Error Prevention), #9 (Error Recovery) | 10 Nielsen Heuristics, 6 Component States |
| **Zero Tolerance Rule** | Never invent tokens without user intake | Never silently invent fake mock data | Zero raw hex codes or arbitrary px |
