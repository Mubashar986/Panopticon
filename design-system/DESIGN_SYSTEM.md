# Panopticon Design System Specification (Picasso Standard)

**Version:** 1.0.0  
**Source of Truth:** `design-system/tokens.json` & `frontend/src/styles/tokens.css`  

---

## 1. Color Palette (Dark Theme Deep Nebula)

| Token Name | Hex Value | CSS Variable | Semantic Usage |
| :--- | :--- | :--- | :--- |
| `canvas` | `#090514` | `--color-bg-canvas` | Deep background canvas behind entire dashboard |
| `surface` | `#150E24` | `--color-bg-surface` | Primary container cards, drawers, and modal bodies |
| `surfaceElevated`| `#1E1B3A` | `--color-bg-surface-elevated`| Hover states, elevated pills, input fields |
| `textPrimary` | `#F1F5F9` | `--color-text-primary` | Main titles, headings, active text |
| `textSecondary`| `#94A3B8` | `--color-text-secondary` | Subtitles, metadata labels, timestamps |
| `primary` | `#8B5CF6` | `--color-primary` | Brand violet accent, primary buttons, active tabs |
| `primaryHover` | `#A78BFA` | `--color-primary-hover` | Interactive hover for violet elements |
| `borderSubtle` | `#2E2A4A` | `--color-border` | Subtle hairline dividers and container outlines |
| `drive` | `#4285F4` | `--color-drive` | Google Drive branding, external document links |
| `success` | `#10B981` | `--color-success` | Verified badges, SSE online status, 100% confidence |
| `warning` | `#F59E0B` | `--color-warning` | Partial citations, in-progress sync, warnings |
| `error` | `#F43F5E` | `--color-error` | Hallucination alerts, 404/500 errors, failed sync |

---

## 2. Spacing Scale (4px Base Grid)

- `--space-1` (4px), `--space-2` (8px), `--space-3` (12px), `--space-4` (16px), `--space-6` (24px), `--space-8` (32px), `--space-12` (48px), `--space-16` (64px)

---

## 3. Border Radii

- `--radius-sm` (6px), `--radius-md` (10px), `--radius-lg` (14px), `--radius-xl` (20px), `--radius-full` (9999px)

---

## 4. Interactive State Matrix (Vermeer Requirement)

Every interactive element MUST support all 6 states:
1. `default`: Standard resting state.
2. `hover`: Background shift to `surfaceElevated` or `primaryHover`.
3. `active`: Down-click tactile feedback (`scale(0.98)`).
4. `focus`: `outline: 2px solid var(--color-primary)` with `outline-offset: 2px`.
5. `disabled`: `opacity: 0.5`, `cursor: not-allowed`.
6. `loading`: Animated spinner or pulsing skeleton, interactions blocked.
