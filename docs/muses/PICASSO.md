# Picasso — Design System Intake & Token Definition

---

## 1. Overview & Purpose

**Picasso** runs a structured, usability-grounded design system intake interview and produces a canonical **design tokens specification** (`design-system/tokens.json` and `design-system/DESIGN_SYSTEM.md`) before any frontend code is written.

### The Problem Picasso Solves
Left alone, an AI coding agent asked to "build a nice-looking page" will invent random hex colors, arbitrary pixel paddings, and arbitrary font sizes—and invent *different* ones in every session. That creates design drift, inconsistent UX, and mounting technical debt. Picasso eliminates guessing by conducting a deliberate intake interview, grounding every decision in usability heuristics (Nielsen Norman Group HCI rules), and writing them down permanently as machine-readable design tokens.

### The Muses Ecosystem
- **Picasso (This Skill):** Conducts intake and defines canonical tokens once.
- **Escher:** Inspects real backend API contracts and wires real data into components.
- **Vermeer:** Builds the visual and interactive UI strictly from Picasso's tokens.

---

## 2. When to Run Picasso

1. **New UI Task:** Any request to build a UI, page, component, or mockup when `design-system/tokens.json` does not exist.
2. **Design Reset / Rebranding:** When the user explicitly requests to change the color palette, typography, brand identity, or layout density.
3. **Existing Token Check:** If `design-system/tokens.json` already exists, Picasso asks whether the user wants to **revise specific tokens** or **start fresh**—never silently overwriting existing systems.

---

## 3. The Intake Interview Protocol

Picasso conducts a structured, plain-language interview covering 8 core dimensions. It asks about *outcomes and feelings*, not CSS syntax or raw hex codes.

```
┌─────────────────────────────────────────────────────────────┐
│                 PICASSO INTAKE SEQUENCE                     │
│                                                             │
│  1. Purpose & Audience ───► Technical vs. Non-Technical     │
│  2. Brand Personality  ───► 2-3 Descriptors (Calm/Bold)     │
│  3. Existing Assets    ───► Logos, Brand Colors, URLs       │
│  4. Color & Dark Mode  ───► Primary Accent & Theme Scope    │
│  5. Typography         ───► Geometric / Serif / Monospace   │
│  6. Spacing Density    ───► Comfortable vs. Compact/Dense   │
│  7. Voice & Error Tone ───► Formal vs. Friendly vs. Minimal │
│  8. Accessibility      ───► WCAG AA / AAA Requirements      │
└─────────────────────────────────────────────────────────────┘
```

### Interview Step-by-Step

| Step | Topic | What to Ask the User | How it Maps to Tokens & Heuristics |
|---|---|---|---|
| **1** | **Purpose & Audience** | "What is this application for, who will use it, and are they technical or non-technical?" | Sets the baseline for UI density and complexity tolerance (Heuristic #7 & #8). |
| **2** | **Brand Personality** | "What 2-3 words describe how this brand should feel? (e.g. *calm & trustworthy*, *bold & modern*, *minimal & high-density*)" | Drives border radius (soft vs. sharp), motion easing, and color saturation. |
| **3** | **Existing Assets** | "Do you have existing brand colors, logos, or reference sites you want to match or avoid?" | Ingests existing palette primitives; prevents brand divergence. |
| **4** | **Color & Theming** | "What is your primary brand color preference, and is dark mode required?" | Populates `color.semantic` (light + dark mode variants from day 1). |
| **5** | **Typography** | "What typographic feel fits best: modern geometric, classic editorial, or technical monospace?" | Proposes 1-2 curated font pairings (`Inter`, `JetBrains Mono`, etc.). |
| **6** | **Density** | "Do you prefer a spacious/comfortable layout or a high-density, data-heavy dashboard?" | Establishes the 4px/8px modular spacing scale (`space.1` to `space.16`). |
| **7** | **Voice & Tone** | "When an error occurs or a screen has no data, should messages sound formal, friendly, or minimal?" | Defines `voice.error-style` and `voice.tone` (critical contract for Escher). |
| **8** | **Accessibility** | "Are there specific visual or motor accessibility requirements?" | Defaults to WCAG AA (4.5:1 text contrast, 44px tap targets, focus rings). |

---

## 4. Complete Design Token Schema (`token-schema.md`)

Picasso produces tokens adhering to this comprehensive schema in `design-system/tokens.json`:

```json
{
  "meta": {
    "project": "Panopticon Document Search",
    "created": "2026-08-29",
    "last_updated": "2026-08-29"
  },
  "color": {
    "primitives": {
      "slate-50": "#F8FAFC",
      "slate-100": "#F1F5F9",
      "slate-800": "#1E293B",
      "slate-900": "#0F172A",
      "blue-600": "#2563EB",
      "purple-700": "#7E22CE",
      "emerald-600": "#059669",
      "amber-600": "#D97706",
      "rose-600": "#E11D48"
    },
    "semantic": {
      "bg-canvas": { "light": "#F8FAFC", "dark": "#0F172A" },
      "bg-surface": { "light": "#FFFFFF", "dark": "#1E293B" },
      "bg-surface-elevated": { "light": "#FFFFFF", "dark": "#334155" },
      "text-primary": { "light": "#0F172A", "dark": "#F8FAFC" },
      "text-secondary": { "light": "#475569", "dark": "#CBD5E1" },
      "primary": { "light": "#2563EB", "dark": "#3B82F6" },
      "primary-hover": { "light": "#1D4ED8", "dark": "#60A5FA" },
      "border": { "light": "#E2E8F0", "dark": "#334155" },
      "tag-match": { "light": "#7E22CE", "dark": "#A855F7" },
      "success": { "light": "#059669", "dark": "#10B981" },
      "warning": { "light": "#D97706", "dark": "#F59E0B" },
      "error": { "light": "#E11D48", "dark": "#F43F5E" }
    },
    "state": {
      "error-bg": "#FEF2F2",
      "error-text": "#B91C1C",
      "error-border": "#FCA5A5",
      "warning-bg": "#FFFBEB",
      "warning-text": "#B45309",
      "warning-border": "#FDE68A",
      "success-bg": "#ECFDF5",
      "success-text": "#047857",
      "success-border": "#A7F3D0"
    }
  },
  "type": {
    "family": {
      "base": "Inter, system-ui, -apple-system, sans-serif",
      "mono": "JetBrains Mono, 'Fira Code', monospace"
    },
    "scale": {
      "xs": { "size": "12px", "lineHeight": "16px" },
      "sm": { "size": "14px", "lineHeight": "20px" },
      "base": { "size": "16px", "lineHeight": "24px" },
      "lg": { "size": "18px", "lineHeight": "28px" },
      "xl": { "size": "20px", "lineHeight": "28px" },
      "2xl": { "size": "24px", "lineHeight": "32px" }
    },
    "weight": {
      "regular": "400",
      "medium": "500",
      "semibold": "600",
      "bold": "700"
    }
  },
  "space": {
    "1": "4px",
    "2": "8px",
    "3": "12px",
    "4": "16px",
    "6": "24px",
    "8": "32px",
    "12": "48px",
    "16": "64px"
  },
  "radius": {
    "none": "0px",
    "sm": "4px",
    "md": "8px",
    "lg": "12px",
    "xl": "16px",
    "full": "9999px"
  },
  "elevation": {
    "0": "none",
    "1": "0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1)",
    "2": "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)",
    "3": "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)",
    "4": "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)"
  },
  "motion": {
    "duration": {
      "fast": "150ms",
      "base": "250ms",
      "slow": "350ms"
    },
    "easing": {
      "standard": "cubic-bezier(0.4, 0.0, 0.2, 1)",
      "decelerate": "cubic-bezier(0.0, 0.0, 0.2, 1)",
      "accelerate": "cubic-bezier(0.4, 0.0, 1, 1)"
    }
  },
  "a11y": {
    "focus-ring": "2px solid #2563EB",
    "focus-offset": "2px",
    "min-tap-target": "44px",
    "contrast-text": "4.5:1",
    "contrast-large-text": "3.0:1"
  },
  "voice": {
    "tone": "direct, precise, engineer-focused, zero fluff",
    "capitalization": "sentence case",
    "error-style": "plain language explanation + immediate actionable recovery step"
  }
}
```

---

## 5. Required Output Files

Upon concluding the intake interview, Picasso generates two files:

1. **`design-system/tokens.json`:** Machine-readable single source of truth for Vermeer and Escher.
2. **`design-system/DESIGN_SYSTEM.md`:** Human-readable specification explaining color roles, typography, component states, and accessibility standards.

---

## 6. Handoff Protocol

Once Picasso writes the tokens:
- **Handoff to Escher:** For components that touch backend data (Search, Sync, Auth), Escher verifies API contracts and maps data models before building UI.
- **Handoff to Vermeer:** Vermeer builds components adhering 100% to tokens and the 10 HCI usability heuristics (zero invented hex codes, zero arbitrary px).
