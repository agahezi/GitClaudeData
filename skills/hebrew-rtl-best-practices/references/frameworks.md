# Framework RTL Setup

Read when the task involves Tailwind classes, Next.js App Router, MUI, Radix, or other portalled UI.

## Tailwind CSS RTL (v4, current; logical utilities since v3.3)

Prefer logical property utilities over `rtl:`/`ltr:` variants:

| Physical class | Logical class | CSS property |
|---------------|--------------|-------------|
| `ml-4` | `ms-4` | `margin-inline-start` |
| `mr-4` | `me-4` | `margin-inline-end` |
| `pl-4` | `ps-4` | `padding-inline-start` |
| `pr-4` | `pe-4` | `padding-inline-end` |
| `left-4` | `inset-s-4` (was `start-4`) | `inset-inline-start` |
| `right-4` | `inset-e-4` (was `end-4`) | `inset-inline-end` |
| `rounded-l-lg` | `rounded-s-lg` | `border-start-start-radius` + `border-end-start-radius` |
| `rounded-r-lg` | `rounded-e-lg` | `border-start-end-radius` + `border-end-end-radius` |

```html
<!-- Bad: requires two classes, breaks without dir attribute -->
<div class="ltr:ml-4 rtl:mr-4">...</div>

<!-- Good: single class, auto-mirrors based on dir -->
<div class="ms-4">...</div>
```

Reserve `rtl:` / `ltr:` variants only for cases logical properties cannot handle (e.g., directional icons, transforms).

Some utilities have no logical form and stay physical in v4: `translate-x-*` (slide-in drawers and sheets), `origin-left` / `origin-right`, and `bg-linear-to-r` / `bg-linear-to-l`. Pair each with an `rtl:` override, for example `-translate-x-full rtl:translate-x-full` for a drawer that enters from the start edge.

**Tailwind v4 note:** v4 (GA since early 2025, currently v4.3) uses CSS-first configuration (`@import "tailwindcss"` in CSS) instead of `tailwind.config.js`. Logical utilities work identically in both v3 and v4. As of v4.2 (February 2026) the logical *inset* utilities `start-*`/`end-*` are deprecated in favor of `inset-s-*`/`inset-e-*` (the old names still work; no removal date has been announced); the margin/padding utilities `ms-*`/`me-*`/`ps-*`/`pe-*` are unaffected.

Scrollbar space in Tailwind v4.3+: `scrollbar-gutter-stable`.

### Example: sidebar on the wrong side

```html
<!-- Bad: sidebar stuck on left -->
<aside class="fixed left-0 w-64">...</aside>

<!-- Good: sidebar auto-mirrors (inset-s-0; start-0 is the deprecated alias) -->
<aside class="fixed inset-s-0 w-64">...</aside>

<!-- Back arrow icon still needs rtl: variant (horizontal flip, not rotate-180 which also flips vertically) -->
<button class="rtl:-scale-x-100">
  <ArrowLeftIcon />
</button>
```

## Next.js App Router

```tsx
// app/[locale]/layout.tsx (a plain app/layout.tsx receives no locale param)
import { Heebo } from 'next/font/google';

const heebo = Heebo({
  subsets: ['hebrew', 'latin'],
  weight: ['400', '500', '700'],
});

export default async function RootLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const isRTL = locale === 'he';

  return (
    <html lang={locale} dir={isRTL ? 'rtl' : 'ltr'}>
      <body className={heebo.className}>{children}</body>
    </html>
  );
}
```

`next/font` self-hosts the font (no external Google Fonts requests, zero layout shift).

## React with MUI

Current MUI (v9 as of 2026) uses the official fork `@mui/stylis-plugin-rtl`, not the older community `stylis-plugin-rtl` package. The official fork fixes CSS-layers issues and supports current Stylis versions; this has been the recommended setup since MUI v6.

```jsx
import { createTheme, ThemeProvider } from '@mui/material/styles';
import { CacheProvider } from '@emotion/react';
import createCache from '@emotion/cache';
import rtlPlugin from '@mui/stylis-plugin-rtl';
import { prefixer } from 'stylis';

const cacheRtl = createCache({
  key: 'muirtl',
  stylisPlugins: [prefixer, rtlPlugin],
});

const theme = createTheme({ direction: 'rtl' });
```

In the Next.js App Router, pass the same options to MUI's `AppRouterCacheProvider` (from `@mui/material-nextjs/v16-appRouter`, matching your Next.js major) instead of building a separate cache: `<AppRouterCacheProvider options={{ key: 'muirtl', stylisPlugins: [prefixer, rtlPlugin] }}>`, with `<ThemeProvider theme={theme}>` inside it. Its `options` prop is passed straight to Emotion's `createCache`.

`@mui/stylis-plugin-rtl` exposes only a **default** export, so a named `import { rtlPlugin }` compiles but yields `undefined`, and Emotion silently skips the plugin: the app looks LTR with no error. Confirm the exact import name and setup against the current MUI RTL guide (https://mui.com/material-ui/customization/right-to-left/) for your MUI version.

## Portalled UI (modals, dropdowns, tooltips, toasts)

Components rendered through a portal (React `createPortal`, Radix, MUI Menu, Floating UI) mount at `document.body` and inherit direction from there, but many libraries assume LTR. Set `dir` on `<html>` AND pass the library's own direction setting: Radix needs a `<DirectionProvider dir="rtl">` wrapper, MUI needs `direction: 'rtl'` in the theme. Otherwise popovers open on the wrong side even when the rest of the page is correct.

## Sources

| Source | URL | What to Check |
|--------|-----|---------------|
| Tailwind CSS RTL Support | https://tailwindcss.com/docs/hover-focus-and-other-states#rtl-support | `rtl:` / `ltr:` variant syntax |
| Tailwind Logical Properties | https://tailwindcss.com/docs/margin | `ms-*`, `me-*`, `ps-*`, `pe-*` utilities |
| MUI Right-to-left | https://mui.com/material-ui/customization/right-to-left/ | `@mui/stylis-plugin-rtl` setup for current MUI |
