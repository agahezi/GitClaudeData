# Fluid Design Tokens

Read when the project has no fluid scale yet, or when adding or changing tokens.

Detect the stack first (`package.json` for `tailwindcss` ≥ 4, a CSS entry with `@import "tailwindcss"`). Use the Tailwind block if present, otherwise the plain CSS block. Both define the same token names so examples stay interchangeable.

## Recommended fluid scale (320px → 1280px)

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

## Tailwind CSS v4

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

Tailwind v4 variant note: `@md/card:` matches the named container's min-width (`@md` = 28rem by default); arbitrary sizes use `@min-[30rem]/card:`.

Built-in v4 utilities to prefer: `min-h-svh`, `h-dvh`, `h-lvh`, `text-balance`, `text-pretty`, `@container`, `@container/name`, `@sm:` … `@7xl:`, `@min-[30rem]:`, `@max-[20rem]:`, logical props (`ps-*`, `pe-*`, `ms-*`, `me-*`, `start-*`, `end-*`).

Avoid in layout code: `sm:`, `md:`, `lg:`, `xl:` for column counts, flex direction, or font-size jumps. If you find yourself writing `text-3xl md:text-5xl`, replace it with one fluid token.

## Plain CSS (no Tailwind; works with CSS Modules, Sass, styled-components, vanilla)

```css
:root {
  --text-fluid-sm: clamp(0.875rem, 0.833rem + 0.208vw, 1rem);
  --text-fluid-base: clamp(1rem, 0.92rem + 0.42vw, 1.25rem);
  --text-fluid-lg: clamp(1.125rem, 1rem + 0.63vw, 1.5rem);
  --text-fluid-xl: clamp(1.375rem, 1.17rem + 1.04vw, 2rem);
  --text-fluid-2xl: clamp(1.75rem, 1.417rem + 1.667vw, 2.75rem);
  --text-fluid-3xl: clamp(2.25rem, 1.75rem + 2.5vw, 3.75rem);

  --spacing-fluid-xs: clamp(0.5rem, 0.42rem + 0.42vw, 0.75rem);
  --spacing-fluid-sm: clamp(0.75rem, 0.625rem + 0.625vw, 1.125rem);
  --spacing-fluid-md: clamp(1rem, 0.75rem + 1.25vw, 1.75rem);
  --spacing-fluid-lg: clamp(1.5rem, 1rem + 2.5vw, 3rem);
  --spacing-fluid-xl: clamp(2.5rem, 1.67rem + 4.17vw, 5rem);
  --spacing-fluid-2xl: clamp(3.5rem, 2.17rem + 6.67vw, 7.5rem);

  --spacing-touch: 2.75rem;
  --spacing-hero: min(100svh, 60rem);
}

body { font-size: var(--text-fluid-base); line-height: 1.65; }
h1 { font-size: var(--text-fluid-3xl); line-height: 1.1; text-wrap: balance; }
h2 { font-size: var(--text-fluid-2xl); line-height: 1.15; text-wrap: balance; }
h3 { font-size: var(--text-fluid-xl); line-height: 1.3; text-wrap: balance; }
p, li, figcaption { text-wrap: pretty; }

.grid-auto-fit {
  display: grid;
  gap: var(--spacing-fluid-md);
  grid-template-columns: repeat(auto-fit, minmax(min(var(--grid-min, 18rem), 100%), 1fr));
}

.touch-target,
button, select, textarea, summary, [role="button"],
input:not([type="checkbox"], [type="radio"], [type="hidden"]) {
  min-block-size: var(--spacing-touch);
  min-inline-size: var(--spacing-touch);
}
```

Checkboxes/radios: keep the native control size and make the wrapping `<label>` the 44px hit area (`display: inline-flex; align-items: center; min-block-size: var(--spacing-touch);`).

Usage: `<ul class="grid-auto-fit" style="--grid-min: 16rem">`. In CSS Modules, keep `:root` tokens in a global stylesheet and reference them with `var()` inside module files.
