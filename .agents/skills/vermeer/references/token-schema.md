# Design Token Schema

This is the complete taxonomy of tokens a design system needs. Picasso fills this out through the interview. Vermeer treats it as the only legal source of visual values when building UI.

Every category below maps to a key in `tokens.json`. Don't skip categories just because the user didn't mention them — infer sensible defaults from what they *did* say (e.g. if they picked a "calm, trustworthy" mood, default spacing/radius toward softer, more generous values) and flag defaults clearly as defaults so the user can override them.

## 1. Color
- `color.primitives` — raw palette, hue + step (e.g. `blue.50` … `blue.900`). Never referenced directly by components.
- `color.semantic` — meaning-based tokens components actually use: `primary`, `primary-hover`, `bg-surface`, `bg-canvas`, `text-primary`, `text-secondary`, `border`, `success`, `warning`, `error`, `info`.
- `color.state` — for each semantic status color, a `-bg`, `-text`, `-border` triplet (e.g. `error-bg`, `error-text`, `error-border`).

## 2. Typography
- `type.family.base`, `type.family.mono`
- `type.scale` — xs/sm/base/lg/xl/2xl/3xl, each with size + line-height
- `type.weight` — regular/medium/semibold/bold

## 3. Spacing
- `space.1` through `space.16` on an 8pt (or 4pt) grid.

## 4. Sizing
- `size.icon.sm/md/lg`, `size.avatar.sm/md/lg`, `size.input.h`, `size.button.h`

## 5. Radius
- `radius.none/sm/md/lg/xl/full`

## 6. Elevation
- `elevation.0` through `elevation.4` — shadow values from flat to modal-level.

## 7. Motion
- `motion.duration.fast/base/slow`
- `motion.easing.standard/decelerate/accelerate`

## 8. Iconography
- `icon.set` — name of the one icon library in use
- `icon.stroke-width`
- `icon.sizes` — maps to `size.icon.*`

## 9. Layout
- `breakpoint.sm/md/lg/xl/2xl`
- `grid.columns`, `grid.gutter`

## 10. Z-index
- `z.base/dropdown/sticky/modal/toast/tooltip`

## 11. Opacity
- `opacity.disabled/hover/overlay`

## 12. Component states (template, not literal values)
Every interactive component needs all of: `default, hover, active, focus, disabled, loading`. Picasso doesn't need to enumerate every component — it establishes the *rule* (e.g. focus ring = `2px solid primary, 2px offset`) that Vermeer applies to whatever it builds.

## 13. Accessibility minimums
- `a11y.focus-ring`
- `a11y.min-tap-target` (44px default)
- `a11y.contrast-text` (4.5:1 default), `a11y.contrast-large-text` (3:1 default)

## 14. Content / voice
- `voice.tone` (e.g. "warm, plain-language, no jargon")
- `voice.capitalization` ("sentence case" or "Title Case" — pick one)
- `voice.error-style` ("plain language + next step, never raw error codes")

## 15. Theming
- If dark mode is in scope, every `color.semantic` token needs both a `light` and `dark` value from the start — not retrofitted later.

---

## JSON shape

```json
{
  "meta": { "project": "string", "created": "ISO date", "last_updated": "ISO date" },
  "color": { "primitives": {}, "semantic": {}, "state": {} },
  "type": { "family": {}, "scale": {}, "weight": {} },
  "space": {},
  "size": {},
  "radius": {},
  "elevation": {},
  "motion": { "duration": {}, "easing": {} },
  "icon": {},
  "layout": { "breakpoint": {}, "grid": {} },
  "z": {},
  "opacity": {},
  "a11y": {},
  "voice": {}
}
```

Keep this file as the single source of truth. Anything not in it doesn't exist yet.
