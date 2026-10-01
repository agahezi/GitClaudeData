---
name: hebrew-rtl-best-practices
description: Implement right-to-left (RTL) layouts and bidirectional (bidi) text for Hebrew web UIs. Use for RTL layout, Hebrew text direction, "right to left", Hebrew CSS or typography, icon mirroring, and Tailwind, React, Next.js, or MUI RTL setup. Not for Arabic-specific RTL unless shared RTL patterns are requested, nor native mobile RTL.
license: MIT
compatibility: Works with Claude Code, Codex, Claude.ai, Cursor. No network required.
---

# Hebrew RTL Best Practices

Apply the core rules to every Hebrew RTL task. Read a reference only when the task needs it:

| Reference | Read when the task involves |
|---|---|
| `references/bidi-text.md` | Mixed Hebrew and Latin text, phone numbers, currency or dates, `Intl` output, Hebrew calendar dates, form inputs, user-generated content |
| `references/frameworks.md` | Tailwind classes, Next.js App Router, MUI, Radix, or other portalled UI (modals, dropdowns, tooltips, toasts) |
| `references/css-logical-properties.md` | Converting a whole stylesheet, the full property map, late-arriving logical values, Hebrew fonts and typography detail |

## Core rules

1. **Set direction in HTML**, not CSS alone: `<html lang="he" dir="rtl">`. Browsers, screen readers, and CSS all key on it.
2. **Never use physical properties for layout.** Use `margin-inline-start`/`-end`, `padding-inline-start`/`-end`, `border-inline-start`/`-end`, `inset-inline-start`/`-end`, `text-align: start`/`end`, and `float: inline-start`/`inline-end` instead of their `left`/`right` forms. The layout then mirrors automatically.
3. **For a genuinely direction-specific rule, use `:dir(rtl)`.** It matches the computed direction, including `dir="auto"` and inherited direction, which `[dir="rtl"]` misses. It is Baseline (Chrome and Edge 120, Safari 16.4, Firefox for years); keep an `[dir="rtl"]` fallback only for older browsers.
4. **Physical values do not flip.** `box-shadow`, `text-shadow`, `linear-gradient` angles, `transform-origin`, `background-position`, and `translateX` animations (drawers, carousels, shimmer) stay fixed; override each with `:dir(rtl)` when its direction is meaningful.
5. **Isolate opposite-direction content.** Use `<bdi>` for user-generated or unknown-direction values, `<span dir="ltr">` for raw LTR values such as phone numbers with spaces or a `+972` prefix, and `dir="auto"` on every `<input>` and `<textarea>` (except `tel`). Never apply `unicode-bidi: bidi-override` to mixed content. Read `references/bidi-text.md` before handling numbers, currency, dates, or form fields.
6. **Keep code LTR.** Set `code, pre, kbd, samp { direction: ltr; unicode-bidi: isolate; }` once in the RTL theme; wrap inline file paths, card numbers, and CLI commands in `<bdo dir="ltr">`.
7. **Mirror only reading-direction icons**: navigation and back/forward arrows, breadcrumb chevrons, send and pagination arrows, indent and reply arrows, forward-progress indicators. Flip with `transform: scaleX(-1)` under `:dir(rtl)` or Tailwind `rtl:-scale-x-100`, never `rotate-180`, which also flips vertically. Do not mirror logos, checkmarks, close icons, media play buttons, clocks, or real-world objects. Prefer an icon set's own RTL variants (for example Material Symbols); a flipped icon can mis-render fine detail or embedded text.
8. **Hebrew typography.** Use `font-family: 'Heebo', 'Assistant', 'Rubik', 'Noto Sans Hebrew', sans-serif;` and `line-height: 1.7` so nikkud is not clipped. Hebrew is caseless: remove `text-transform` and `small-caps` from the RTL theme, because they still uppercase embedded Latin words. Keep running text at `letter-spacing: normal`, but do not reset it globally; Hebrew uses tracking for emphasis.

## Gotchas

- Flexbox `row` already reverses in RTL; adding `row-reverse` double-flips back to LTR order.
- In an RTL scroll container `scrollLeft` is `0` at the start and becomes negative toward the end. Use `el.scrollBy({ left: isRtl ? -300 : 300 })`, not `scrollLeft += 300` or `Math.max(0, ...)` clamps.
- Fixed and sticky chrome (headers, toasts, FABs, drawers) with `left: 0` / `right: 0` does not flip; use `inset-inline-start` / `inset-inline-end`.
- Tables reorder columns automatically, but force numeric, code, and date cells back to LTR with `<td dir="ltr">` and align them consistently; alignment alone does not change direction.
- Charts and SVG have no logical properties, and the x-axis may need to reverse; use the charting library's `reversed` or `rtl` option, not CSS.
- Progress bars fill right to left, slider and carousel swipes reverse, breadcrumb separators reverse, and form labels align right.
- Scrollbars sit on the left in RTL; reserve space with `scrollbar-gutter: stable` to avoid reflow, and use `text-wrap: balance` for Hebrew headings.
- Portalled UI inherits direction from `document.body`, and many libraries assume LTR; also set the library's own direction (see `references/frameworks.md`).

## Verify before shipping

- Flip the whole app to `dir="rtl"` and scan for anything that did not move; it still uses a physical property.
- Put `שלום John +972 50-123-4567 ₪1,234` in every text surface; it exercises Hebrew, Latin, an international phone number, and currency.
- Open every modal, dropdown, tooltip, and toast, then check fixed chrome, charts, and `dir="auto"` fields.
- Automate it: screenshot-diff the same pages under `dir="rtl"` and `dir="ltr"` in Playwright.

## Example: convert an LTR component

```css
/* Before: LTR-only */
.card { margin-left: 16px; padding-right: 12px; text-align: left; border-left: 3px solid blue; }

/* After: mirrors in RTL */
.card { margin-inline-start: 16px; padding-inline-end: 12px; text-align: start; border-inline-start: 3px solid blue; }
```

With Tailwind, replace `ml-4 pr-3 text-left border-l-4` with `ms-4 pe-3 text-start border-s-4`.
