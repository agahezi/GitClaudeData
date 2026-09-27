---
name: fluid-responsive-design
description: Build or refactor web UIs to be fully fluid across any screen width, resolution, and orientation without device breakpoints. Use when the user asks for responsive, fluid, adaptive, or mobile-friendly layouts, fluid typography/spacing, clamp(), container queries (@container, cqi/cqw), auto-fit grids, svh/dvh/lvh viewport units, orientation/rotation issues, split-screen breakage, or touch-target sizing. Covers plain modern CSS, Tailwind CSS v4 (@theme, @utility, @container variants), and React 19 component patterns. Do NOT use for native mobile (React Native, SwiftUI, Android) or email HTML (no clamp/container query support).
license: MIT
compatibility: Framework-agnostic CSS; Tailwind v4+ sections require Tailwind 4. No network required.
---

# Fluid Responsive Design

Goal: layouts that scale continuously with available space, not jump between device sizes. Apply these rules when building from scratch; when given existing code, refactor it toward them.

## Core Rules

1. **Fluid sizing** – no static `px` for font-size, padding, margin, gap, or heights. Use `clamp()` with `rem + vw` (or `cqi`) terms.
2. **Intrinsic layouts** – no breakpoint-driven column counts. Use auto-fit grids and wrapping flex.
3. **Container over viewport** – components respond to their parent's size (`@container`, `cqi`), not the window.
4. **Accessible touch & text** – every interactive element ≥ 44×44 CSS px; headings `text-wrap: balance`, body `text-wrap: pretty`.

Allowed `px`: borders/hairlines, shadows, the 44px touch floor, and SVG/icon stroke widths.
Allowed media queries: user preferences (`prefers-reduced-motion`, `prefers-color-scheme`, `prefers-contrast`), `hover`/`pointer` capability, and `print`. Not for width-based layout switching.

## Step 1: Fluid Typography & Spacing

### The clamp formula
```
clamp(MIN, calc(INTERCEPT + SLOPE * 100vw), MAX)
SLOPE     = (MAX - MIN) / (VW_MAX - VW_MIN)
INTERCEPT = MIN - SLOPE * VW_MIN
```
Example: 16px (1rem) at 320px → 20px (1.25rem) at 1280px:
slope = 4px / 960px = 0.004167 → `0.417vw`; intercept = 16px − 0.004167 × 320px = 14.67px → `0.917rem`.
Result: `clamp(1rem, 0.917rem + 0.417vw, 1.25rem)`.

**Always combine `rem` + `vw`** in the preferred value. Pure `vw` breaks browser zoom (WCAG 1.4.4 Resize Text). Keep MIN/MAX in `rem` so user font-size preferences are respected.

### Recommended fluid scale (320px → 1280px)
| Token | Value |
|---|---|
| `--text-fluid-xs` | `clamp(0.75rem, 0.708rem + 0.208vw, 0.875rem)` |
| `--text-fluid-sm` | `clamp(0.875rem, 0.833rem + 0.208vw, 1rem)` |
| `--text-fluid-base` | `clamp(1rem, 0.92rem + 0.42vw, 1.25rem)` |
| `--text-fluid-lg` | `clamp(1.125rem, 1rem + 0.63vw, 1.5rem)` |
| `--text-fluid-xl` | `clamp(1.375rem, 1.17rem + 1.04vw, 2rem)` |
| `--text-fluid-2xl` | `clamp(1.75rem, 1.417rem + 1.667vw, 2.75rem)` |
| `--text-fluid-3xl` | `clamp(2.25rem, 1.75rem + 2.5vw, 3.75rem)` |
| `--spacing-fluid-2xs` | `clamp(0.25rem, 0.2rem + 0.21vw, 0.375rem)` |
| `--spacing-fluid-xs` | `clamp(0.5rem, 0.42rem + 0.42vw, 0.75rem)` |
| `--spacing-fluid-sm` | `clamp(0.75rem, 0.625rem + 0.625vw, 1.125rem)` |
| `--spacing-fluid-md` | `clamp(1rem, 0.75rem + 1.25vw, 1.75rem)` |
| `--spacing-fluid-lg` | `clamp(1.5rem, 1rem + 2.5vw, 3rem)` |
| `--spacing-fluid-xl` | `clamp(2.5rem, 1.67rem + 4.17vw, 5rem)` |
| `--spacing-fluid-2xl` | `clamp(3.5rem, 2.17rem + 6.67vw, 7.5rem)` |

Line height: use unitless values (`1.1` for display, `1.5`–`1.7` for body) so they scale with the font.

### Viewport height units
| Unit | Use for |
|---|---|
| `svh` | Hero/min-heights that must fit fully when mobile browser chrome is visible (safe default). |
| `lvh` | Backgrounds/decor that should cover the screen when chrome is collapsed. |
| `dvh` | Full-screen app shells/modals that must track chrome changes live (can cause reflow jank on scroll; use sparingly). |

Never use bare `100vh` for mobile layouts. Pair tall sections with a cap so landscape phones don't get absurd heights: `min-height: min(100svh, 60rem)`.

## Step 2: Tailwind CSS v4 Setup

Put tokens in `@theme` so Tailwind generates utilities automatically (`--text-*` → `text-*`, `--spacing-*` → `p-*`, `m-*`, `gap-*`, `w-*`, `h-*`, `size-*`, `--container-*` → `max-w-*` and `@*` variants).

```css
@import "tailwindcss";

@theme {
  --text-fluid-sm: clamp(0.875rem, 0.833rem + 0.208vw, 1rem);
  --text-fluid-sm--line-height: 1.5;
  --text-fluid-base: clamp(1rem, 0.92rem + 0.42vw, 1.25rem);
  --text-fluid-base--line-height: 1.65;
  --text-fluid-lg: clamp(1.125rem, 1rem + 0.63vw, 1.5rem);
  --text-fluid-lg--line-height: 1.5;
  --text-fluid-xl: clamp(1.375rem, 1.17rem + 1.04vw, 2rem);
  --text-fluid-xl--line-height: 1.3;
  --text-fluid-2xl: clamp(1.75rem, 1.417rem + 1.667vw, 2.75rem);
  --text-fluid-2xl--line-height: 1.15;
  --text-fluid-3xl: clamp(2.25rem, 1.75rem + 2.5vw, 3.75rem);
  --text-fluid-3xl--line-height: 1.1;

  --spacing-fluid-xs: clamp(0.5rem, 0.42rem + 0.42vw, 0.75rem);
  --spacing-fluid-sm: clamp(0.75rem, 0.625rem + 0.625vw, 1.125rem);
  --spacing-fluid-md: clamp(1rem, 0.75rem + 1.25vw, 1.75rem);
  --spacing-fluid-lg: clamp(1.5rem, 1rem + 2.5vw, 3rem);
  --spacing-fluid-xl: clamp(2.5rem, 1.67rem + 4.17vw, 5rem);
  --spacing-fluid-2xl: clamp(3.5rem, 2.17rem + 6.67vw, 7.5rem);

  --spacing-touch: 2.75rem; /* 44px floor for hit areas */
  --spacing-hero: min(100svh, 60rem);
  --spacing-screen-large: 100lvh;
}

/* Reusable intrinsic grid; override the min track with --grid-min. */
@utility grid-auto-fit {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(var(--grid-min, 18rem), 100%), 1fr));
}

@utility touch-target {
  min-block-size: var(--spacing-touch);
  min-inline-size: var(--spacing-touch);
}
```

Usage: `text-fluid-2xl`, `px-fluid-md py-fluid-xl`, `gap-fluid-sm`, `min-h-hero`, `grid-auto-fit [--grid-min:16rem]`, `touch-target`.

Built-in v4 utilities to prefer: `min-h-svh`, `h-dvh`, `h-lvh`, `text-balance`, `text-pretty`, `@container`, `@container/name`, `@sm:` … `@7xl:`, `@min-[30rem]:`, `@max-[20rem]:`, logical props (`ps-*`, `pe-*`, `ms-*`, `me-*`, `start-*`, `end-*`).

Avoid in layout code: `sm:`, `md:`, `lg:`, `xl:` for column counts, flex direction, or font-size jumps. If you find yourself writing `text-3xl md:text-5xl`, replace it with one fluid token.

## Step 3: Intrinsic Layouts

### Auto-fit grid (1 → N columns, no breakpoints)
```css
.cards {
  display: grid;
  gap: var(--spacing-fluid-md);
  grid-template-columns: repeat(auto-fit, minmax(min(18rem, 100%), 1fr));
}
```
- `min(18rem, 100%)` prevents overflow when the container is narrower than the track.
- `auto-fit` stretches items when few; `auto-fill` keeps empty tracks (use for fixed-width galleries).
- Tailwind: `grid grid-cols-[repeat(auto-fit,minmax(min(18rem,100%),1fr))] gap-fluid-md` or the `grid-auto-fit` utility above.

### Wrapping flex (sidebar / media-object / button rows)
```css
.cluster { display: flex; flex-wrap: wrap; gap: var(--spacing-fluid-sm); }
.cluster > * { flex: 1 1 12rem; }            /* equal items that wrap */

.with-sidebar { display: flex; flex-wrap: wrap; gap: var(--spacing-fluid-md); }
.with-sidebar > :first-child { flex: 1 1 16rem; }          /* sidebar */
.with-sidebar > :last-child  { flex: 999 1 0; min-inline-size: 55%; } /* main; wraps below when < 55% */
```

### Width constraints
- Readable text: `max-inline-size: 65ch` (Tailwind `max-w-[65ch]` or `max-w-prose`).
- Page gutters: `padding-inline: max(var(--spacing-fluid-md), env(safe-area-inset-left))` for notched landscape phones (use `-right` for the other side, or logical equivalents per direction).
- Centered wrapper: `inline-size: min(100% - 2 * var(--spacing-fluid-md), 72rem); margin-inline: auto;`.

### Media
- Images/video: `max-inline-size: 100%; block-size: auto;` plus `aspect-ratio` to prevent layout shift.
- Use `object-fit: cover` for cropped hero media; `srcset` + `sizes` for resolution.

## Step 4: Container Queries

Make every reusable component its own sizing context. Its parent declares the container; the component styles itself from that.

```css
.card-host { container-type: inline-size; container-name: card; }

.card { display: grid; gap: var(--spacing-fluid-sm); padding: clamp(1rem, 4cqi, 2rem); }
.card__title { font-size: clamp(1.125rem, 0.9rem + 3cqi, 1.75rem); }

@container card (min-width: 32rem) {
  .card { grid-template-columns: auto 1fr; }
}
```

Tailwind v4:
```jsx
<div className="@container/card">
  <article className="grid gap-fluid-sm p-[clamp(1rem,4cqi,2rem)] @lg/card:grid-cols-[auto_1fr]">
    <h3 className="text-[clamp(1.125rem,0.9rem+3cqi,1.75rem)] text-balance">…</h3>
  </article>
</div>
```

Guidelines:
- Prefer `cqi` (inline axis, direction-safe) over `cqw`. Use `cqb` only with `container-type: size` (requires an explicit block size).
- Always mix `rem + cqi` inside `clamp()` for the same zoom reason as `vw`.
- `container-type: inline-size` establishes containment: the container can't size itself from its children's width. Put it on a wrapper whose width comes from the parent (grid cell, flex item with basis, block element), not on shrink-to-fit elements.
- Container query variants (`@md:`) are acceptable because they're component-scoped; still prefer intrinsic grid/flex first, and use container queries only for real structural changes (e.g., stacked → side-by-side media object, hiding secondary text in a tiny tab).
- Use viewport `vw` only for page-level concerns (root typography scale, page gutters, hero).

## Step 5: Touch Targets & Text Wrapping

### 44×44 minimum
```css
button, [role="button"], a.btn, input, select, textarea, summary {
  min-block-size: 2.75rem;
  min-inline-size: 2.75rem;
}
```
- Tailwind: `min-h-11 min-w-11` (2.75rem) or the `touch-target` utility.
- Scale up, never below: `min-block-size: max(2.75rem, 2.2rem + 1vw)`.
- Small visual icons: keep the icon small but pad the hit area (`grid place-items-center size-11` around a `size-5` icon), or extend with a pseudo-element: `position: relative` + `::after { content:""; position:absolute; inset:-0.5rem; }`.
- Inline text links inside paragraphs are exempt (WCAG 2.5.8 inline exception) but give them `padding-block: 0.25em` where practical.
- Keep ≥ 0.5rem gap between adjacent targets.
- Inputs: font-size ≥ 1rem to prevent iOS auto-zoom on focus.
- Gate hover-only effects: `@media (hover: hover) { … }` (Tailwind v4 `hover:` already does this).

### Text distribution
- Headings, short labels, card titles: `text-wrap: balance` (`text-balance`).
- Paragraphs, list items, captions: `text-wrap: pretty` (`text-pretty`).
- Long unbreakable strings (URLs, IDs): `overflow-wrap: anywhere` (`wrap-anywhere`) or `break-words`.
- Allow flex/grid children to shrink: `min-inline-size: 0` (`min-w-0`) on items containing text.

## Step 6: React 19 Patterns

- Components must not read `window.innerWidth` or use `matchMedia` for layout. Render one DOM and let CSS adapt. JS width checks cause hydration mismatches and break in split-screen.
- Wrap reusable components with their own `@container` root (or document that the parent must provide one).
- Accept a `className` prop for layout overrides; don't hard-code outer margins inside components (the parent owns spacing via `gap`).
- Use `ResizeObserver` only for non-layout needs (charts/canvas redraw), never to toggle CSS classes that a container query could handle.

## Refactor Workflow (existing code)

1. **Audit** – search for: `sm:|md:|lg:|xl:|2xl:`, `@media \(min-width|max-width`, `\d+px` in font/padding/margin/gap/height, `100vh`, `h-screen`, `grid-cols-\d` with breakpoint variants, `window.innerWidth`, `matchMedia`.
2. **Tokens** – add the fluid scale to `@theme` (Tailwind) or `:root` custom properties (plain CSS).
3. **Typography** – replace breakpoint font ladders (`text-3xl sm:text-4xl md:text-5xl`) with one fluid token.
4. **Spacing** – replace `py-16 sm:py-20` style ladders with `py-fluid-xl`, etc.
5. **Layouts** – replace `grid-cols-1 md:grid-cols-2` with auto-fit grids; `flex-col sm:flex-row` with `flex flex-wrap` + `flex-basis`.
6. **Components** – wrap reusable blocks in `@container`; convert remaining structural breakpoints to container variants.
7. **Heights** – `min-h-screen`/`100vh` → `min-h-svh` or `min(100svh, Xrem)`.
8. **Touch & text** – add 44px minimums to all interactive elements; `text-balance` on headings, `text-pretty` on body.
9. **Preserve** – keep `prefers-reduced-motion` and other preference queries; keep existing logical properties and RTL behavior.

## Verification Checklist

- [ ] Drag viewport from 280px to 2560px: no horizontal scroll, no sudden jumps, no overlapping text.
- [ ] Portrait ↔ landscape on a phone-sized viewport (e.g., 390×844 ↔ 844×390): hero fits, nothing clipped behind browser chrome.
- [ ] Browser zoom 200% and root font-size 20px: text grows, layout reflows, nothing overflows (WCAG 1.4.4 / 1.4.10 at 320 CSS px).
- [ ] Place a component in a narrow sidebar and a wide main column: it adapts to each independently.
- [ ] Every button/link/input measures ≥ 44×44 in DevTools.
- [ ] Grep shows no width breakpoint utilities used for layout and no `px` font/spacing values.
- [ ] Build passes and no console errors.

## Anti-Patterns

| Avoid | Use instead |
|---|---|
| `text-2xl md:text-4xl lg:text-5xl` | `text-fluid-2xl` |
| `font-size: 4vw` | `clamp(1.5rem, 1rem + 2.5vw, 3rem)` |
| `grid-cols-1 md:grid-cols-3` | `grid-cols-[repeat(auto-fit,minmax(min(18rem,100%),1fr))]` |
| `flex-col md:flex-row` | `flex flex-wrap` + `basis-*`/`flex: 1 1 Xrem` |
| `h-screen` / `100vh` | `min-h-svh` / `min(100svh, 60rem)` |
| `@media (max-width: 768px)` inside a component | `@container (max-width: 30rem)` |
| `hidden sm:block` for content | Container variant, or let text wrap/clamp (`line-clamp-*`) |
| `px-3 py-1` tiny chip buttons | `min-h-11 px-fluid-sm` |
| `useState(window.innerWidth)` | CSS container queries |
