# CSS Logical Properties Quick Reference for Hebrew RTL

## Property Mapping Table

### Margin
| Physical | Logical | Notes |
|----------|---------|-------|
| `margin-left` | `margin-inline-start` | Start of reading direction |
| `margin-right` | `margin-inline-end` | End of reading direction |
| `margin-top` | `margin-block-start` | Top in both LTR and RTL |
| `margin-bottom` | `margin-block-end` | Bottom in both LTR and RTL |

### Padding
| Physical | Logical |
|----------|---------|
| `padding-left` | `padding-inline-start` |
| `padding-right` | `padding-inline-end` |
| `padding-top` | `padding-block-start` |
| `padding-bottom` | `padding-block-end` |

### Border
| Physical | Logical |
|----------|---------|
| `border-left` | `border-inline-start` |
| `border-right` | `border-inline-end` |
| `border-top` | `border-block-start` |
| `border-bottom` | `border-block-end` |

### Positioning
| Physical | Logical |
|----------|---------|
| `left` | `inset-inline-start` |
| `right` | `inset-inline-end` |
| `top` | `inset-block-start` |
| `bottom` | `inset-block-end` |

### Text and Alignment
| Physical | Logical |
|----------|---------|
| `text-align: left` | `text-align: start` |
| `text-align: right` | `text-align: end` |
| `float: left` | `float: inline-start` |
| `float: right` | `float: inline-end` |

### Sizing
| Physical | Logical |
|----------|---------|
| `width` | `inline-size` |
| `height` | `block-size` |
| `min-width` | `min-inline-size` |
| `max-width` | `max-inline-size` |

## Hebrew Font Stack Recommendations

### Sans-Serif (recommended for web)
```css
font-family: 'Heebo', 'Assistant', 'Rubik', 'Noto Sans Hebrew', 'Arial Hebrew', sans-serif;
```

### Serif (for formal/print-style content)
```css
font-family: 'Frank Ruhl Libre', 'David Libre', 'Noto Serif Hebrew', serif;
```

### Monospace (for code with Hebrew comments)
```css
font-family: 'Cousine', monospace;
```
Cousine ships a Hebrew subset on Google Fonts. Not every monospace family has one, so check a replacement family's subsets before adding it, or Hebrew comments will silently fall back to a system font.

## Browser Support Notes
- CSS Logical Properties are supported in all modern browsers (Chrome 89+, Firefox 66+, Safari 15+, Edge 89+), but a few logical values arrived much later: `float: inline-start` / `inline-end` and `clear: inline-start` / `inline-end` only in Chrome and Edge 118 (Firefox 55, Safari 15), `resize: inline` / `block` in Chrome and Edge 118 (Firefox 63, Safari 16), and the `overflow-inline` / `overflow-block` properties only in Chrome and Edge 135 and Safari 26 (Firefox 69). Keep a physical fallback for these if you support older browsers.
- For older browser support, use PostCSS plugin `postcss-logical` as a fallback
- Flexbox and Grid automatically respect `dir="rtl"` -- no additional CSS needed for basic layout reversal. This includes line-based Grid placement: in an RTL grid, line 1 is the right-hand edge and line -1 the left, so `grid-column: 1 / 3` mirrors without any override.

## Direction-Specific Rules

When you genuinely need a direction-specific rule that logical properties cannot express, prefer the `:dir()` pseudo-class over `[dir="rtl"]` attribute selectors:

```css
/* Modern: matches the resolved direction, including dir="auto" and inheritance */
.chevron:dir(rtl) { transform: scaleX(-1); }

/* Older approach: only matches an explicit dir attribute on/above the element */
[dir="rtl"] .chevron { transform: scaleX(-1); }
```

`:dir()` is part of Selectors Level 4 and resolves the *computed* direction, so it also works for elements whose direction comes from `dir="auto"` or from an ancestor, where an attribute selector would miss them. Browser support: Chrome and Edge shipped it in version 120 (late 2023), Firefox has supported it for years, and Safari added it in 16.4, so it is now Baseline (widely available). For older-browser support, keep an `[dir="rtl"]` fallback rule or use a logical property instead. Check current support at https://caniuse.com/css-dir-pseudo.

**Shadows and gradients do not auto-flip.** CSS logical properties mirror layout, but `box-shadow`, `text-shadow`, and `linear-gradient` offsets/angles are physical and stay fixed when direction flips. A shadow offset of `4px 4px` that looks correct in LTR will point the "wrong" way relative to an RTL layout. The same physical-not-logical trap applies to `transform-origin`, `background-position`, and `translateX`-based keyframe animations (slide-in drawers, carousels, progress shimmer). Flip each explicitly with a `:dir(rtl)` (or `[dir="rtl"]`) override when its direction is meaningful.

## Hebrew Typography

```css
html[dir="rtl"] body {
  line-height: 1.7;
  letter-spacing: normal; /* no tracking on running text */
}
```

**Letter-spacing is a Hebrew emphasis device, so do not ban it globally.** Keep running text at `letter-spacing: normal`, but Hebrew typography deliberately uses letter-spacing (tracking) to emphasise names, terms, and concepts. A blanket `letter-spacing: 0 !important` reset in an RTL theme strips that legitimate emphasis.

**Hebrew has no letter case.** The widely used modern scripts with case are Latin, Greek, Armenian, and Cyrillic, Hebrew is not among them, so `text-transform: uppercase` / `capitalize` and `font-variant: small-caps` are no-ops on Hebrew letters. They are *not* no-ops on the Latin words embedded in the same element: a shared design-system button or heading that uppercases its label leaves the Hebrew untouched while shouting "GMAIL" or "PDF" beside it. Remove case transforms from the RTL theme rather than assuming they do nothing.

**Nikkud and cantillation marks need vertical room.** Vowel points are combining marks that sit below or above the base letter and enlarge the effective glyph box. A tight `line-height` (1.2 or less) clips them or collides them with the line above, which is the practical reason for the 1.7 recommended here. Some Latin-first webfonts also ship Hebrew letters without the nikkud glyphs, so test any pointed text (liturgy, children's content, dictionaries) in the actual font before shipping.

## Sources

| Source | URL | What to Check |
|--------|-----|---------------|
| MDN CSS Logical Properties | https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Logical_properties_and_values | Full property list, browser support tables |
| MDN `:dir()` pseudo-class | https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Selectors/:dir | Syntax, behavior vs `[dir]` attribute selectors |
| Can I use: `:dir()` | https://caniuse.com/css-dir-pseudo | Current browser support table |
| Google Fonts Hebrew | https://fonts.google.com/?lang=he_Hebr | Available Hebrew font families |
