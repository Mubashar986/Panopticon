# Vermeer — Design System & Usability Heuristics Enforcement

---

## 1. Overview & Purpose

**Vermeer** is the visual and interaction builder in The Muses suite. It enforces 100% adherence to the canonical design tokens file (`design-system/tokens.json`) and the **10 Nielsen Norman Group Usability Heuristics** across every React component, page, layout, modal, and drawer.

### The Problem Vermeer Solves
Vermeer was famously exacting—using the same pigments, precise geometric perspective, and consistent light across every masterpiece. In software engineering, without strict enforcement, frontends rapidly accumulate 8 shades of almost-identical blue, arbitrary 13px/17px padding, inconsistent modal behavior, and missing focus/loading states. Vermeer guarantees that **every visual value traces to a token and every interaction traces to a usability heuristic**.

### The Muses Division of Labor
- **Picasso:** Defines the tokens and brand parameters once.
- **Escher:** Maps real backend schemas and handles data flow.
- **Vermeer (This Skill):** Constructs the visual layout, styles, micro-interactions, accessibility attributes, and component states.

---

## 2. Step 1: Strict Token Discipline

When writing CSS, Tailwind classes, or React styles, Vermeer strictly prohibits inventing raw values on the fly:

```
┌─────────────────────────────────────────────────────────────┐
│                 VERMEER TOKEN MAPPING RULES                 │
│                                                             │
│  ❌ NEVER:  style={{ backgroundColor: '#2563EB' }}          │
│  ✅ ALWAYS: style={{ backgroundColor: 'var(--color-primary)'}} │
│             OR class="bg-[var(--color-primary)]"            │
│                                                             │
│  ❌ NEVER:  padding: '17px 23px'                            │
│  ✅ ALWAYS: padding: 'var(--space-4) var(--space-6)'        │
│                                                             │
│  ❌ NEVER:  borderRadius: '7px'                             │
│  ✅ ALWAYS: borderRadius: 'var(--radius-md)'                │
│                                                             │
│  ❌ NEVER:  fontFamily: 'Roboto, sans-serif'                │
│  ✅ ALWAYS: fontFamily: 'var(--font-base)'                  │
└─────────────────────────────────────────────────────────────┘
```

### Token Category Mapping Table

| Property Area | Disallowed Practice | Mandatory Token Source |
|---|---|---|
| **Colors** | Raw `#hex`, `rgb()`, `hsl()` | `color.semantic.*`, `color.state.*` |
| **Typography** | Arbitrary `font-size: 15px` | `type.scale.*` (`xs`, `sm`, `base`, `lg`, `xl`, `2xl`) |
| **Font Weights** | Random `font-weight: 550` | `type.weight.*` (`regular`, `medium`, `semibold`, `bold`) |
| **Spacing & Gaps**| `margin: 11px`, `gap: 18px` | `space.*` (`1`=4px, `2`=8px, `3`=12px, `4`=16px, `6`=24px, `8`=32px) |
| **Border Radius** | `border-radius: 9px` | `radius.*` (`none`, `sm`, `md`, `lg`, `xl`, `full`) |
| **Shadows** | Custom box-shadow strings | `elevation.*` (`0` to `4`) |
| **Transitions** | Random `transition: all 0.2s`| `motion.duration.*` + `motion.easing.*` |
| **Z-Index** | `z-index: 99999` | `z.*` (`base`, `dropdown`, `sticky`, `modal`, `toast`, `tooltip`) |

---

## 3. Step 2: The 10 Usability Heuristics Checklist

Every component must pass the 10-heuristic audit before it is considered ready:

| # | Usability Heuristic | Vermeer Implementation Standard | Verification Check |
|---|---|---|---|
| **1** | **Visibility of System Status** | Every async action (search keystroke, sync trigger, auth check) displays a visual indicator within <150ms. | Loading spinners, skeletons, or progress bars are rendered while requests are in flight. |
| **2** | **Match Between System & Real World** | Uses clear user terminology (e.g. *"View in Google Drive"*, *"Governed Tag"*), conventional icons (folder, spreadsheet, document), and zero internal database jargon. | Icons and labels match standard Google Workspace mental models. |
| **3** | **User Control & Freedom** | Destructive or long-running actions have clear cancel, close, or back options (e.g. Esc closes drawers, modals have cancel buttons). | Modal overlays close on Backdrop Click & `Escape` keypress. |
| **4** | **Consistency & Standards** | Badges, buttons, cards, and inputs look and behave identically across all pages. | Tag badges (`[TAG:HIGH]`) use the exact same purple token styling across all cards. |
| **5** | **Error Prevention** | Disables invalid submit actions, provides input constraints, and debounces search input (250ms) to prevent query spam. | Search input auto-debounces; upload buttons validate `.json` extensions before sending. |
| **6** | **Recognition Over Recall** | Search results clearly display highlighted match terms (`<mark>`), primary owner email, and last modified date so users don't have to guess. | Hit highlights are rendered prominently with contrasting background token. |
| **7** | **Flexibility & Efficiency** | Keyboard shortcuts (`/` to focus search bar, `Cmd/Ctrl+K`, `Esc` to clear), filter pills for quick 1-click filtering. | Power users can navigate entirely via keyboard without mouse dependency. |
| **8** | **Aesthetic & Minimalist Design** | High-signal, low-clutter interface. Only essential document metadata is shown on result cards. | No redundant borders, unnecessary decorations, or competing visual weights. |
| **9** | **Help Users Recover from Errors** | Error banners explain *what happened in plain language* and provide an *immediate recovery action* (e.g. *"Reconnect Google Account"*). | Zero raw HTTP codes (`500`, `404`) or raw stack traces shown to the user. |
| **10**| **Help & Documentation** | First-run and empty search states display suggested sample queries (e.g. *"Try searching for 'Falcon' or 'Architecture'"*). | Empty states are actionable guides, not dead ends. |

---

## 4. Step 3: The 6 Mandatory Interactive Component States

Every interactive element (buttons, input fields, result cards, filter pills, dropdown items, switches) must implement all 6 states:

```
┌─────────────────────────────────────────────────────────────┐
│               THE 6 INTERACTION STATES                      │
│                                                             │
│  1. default   ──► Base token appearance                     │
│  2. hover     ──► Subtle background shift / primary-hover   │
│  3. active    ──► Subtle pressed scale (0.98) or darker fill│
│  4. focus     ──► 2px solid primary ring with 2px offset    │
│  5. disabled  ──► opacity: 0.5, cursor: not-allowed         │
│  6. loading   ──► Spinner / skeleton animation, pointer-none│
└─────────────────────────────────────────────────────────────┘
```

---

## 5. Step 4: Token Extension Protocol

If a component genuinely requires a value not present in `design-system/tokens.json`:
1. **Never Invent Inline:** Do not hardcode a one-off value in the component.
2. **Consult Heuristics:** Determine if existing tokens can satisfy the need.
3. **Ask & Update:** If a new token is necessary, add it to `tokens.json`, increment `meta.last_updated`, and document it in `DESIGN_SYSTEM.md`.

---

## 6. Step 5: Self-Audit Grep Verification

Before completing any frontend task, run a self-audit over modified files:

```bash
# Grep for illegal hardcoded hex codes in frontend source
grep -rnE "#[0-9a-fA-F]{3,8}" frontend/src/

# Grep for arbitrary pixel dimensions in Tailwind classnames
grep -rnE "\[[0-9]+px\]" frontend/src/
```

Any detected raw values must be replaced with the matching semantic token variable.
