# Domain Checklist: Hebrew RTL for web apps

Anchor for Expert Review. Scope: right-to-left layout and bidirectional text for Hebrew web UIs (HTML/CSS, Tailwind, React/Next.js, MUI). Each row names where it is covered: a numbered core rule, a core section, or a reference file.

## Must cover (core)
| Item | Covered in | Basis |
|---|---|---|
| `lang="he"` + `dir="rtl"` on `<html>`, not CSS `direction` alone | core rules 1 | HTML spec directionality; W3C i18n inline-bidi-markup |
| Physical-to-logical property mapping (margin, padding, border, inset, text-align, float) | core rules 2, css-logical-properties | MDN CSS logical properties |
| `:dir()` vs `[dir]` selectors, with support versions | core rules 3, css-logical-properties | MDN `:dir()`, caniuse |
| Bidi isolation: `<bdi>`, `<bdo>`, `dir`, `unicode-bidi` values, and when NOT to use `bidi-override` | core rules 5, bidi-text | MDN unicode-bidi, UAX #9 |
| Phone numbers: which formats actually reorder (spaces, `+972`) vs which do not (hyphen-only) | bidi-text | UAX #9 rule W4, browser render |
| Formatting vs isolation: `Intl` he-IL currency/date output, do not force LTR on RLM-marked output | bidi-text | CLDR he currency pattern |
| Hebrew calendar dates via `-u-ca-hebrew` | bidi-text | MDN Intl.DateTimeFormat |
| Form inputs: `dir="auto"`; tel is LTR by default; email/url deliberate LTR with the Hebrew-IDN caveat | core rules 5, bidi-text | HTML spec directionality; IANA `.ישראל` |
| Icon mirroring: which icons flip, which do not, horizontal flip not rotate | core rules 7 | practice |
| Hebrew typography: caselessness, nikkud vertical room, letter-spacing used for emphasis | core rules 8, css-logical-properties | Unicode case FAQ, W3C hlreq |
| Tailwind v4 logical utilities, the v4.2 inset rename, physical-only utilities needing `rtl:` | frameworks | Tailwind release notes, local compile |
| Next.js App Router locale layout (`app/[locale]/layout.tsx`) setting `lang`/`dir` | frameworks | Next.js layout docs |
| MUI RTL: default-export plugin, theme direction, App Router cache options | frameworks | MUI RTL and Next.js integration docs |
| Portalled UI direction (Radix DirectionProvider, MUI theme) | core gotchas, frameworks | Radix / MUI docs |
| RTL scroll coordinates (`scrollLeft` 0 to negative) | core gotchas | MDN Element.scrollLeft |
| Flex/Grid mirror automatically; `row-reverse` double-flips | core gotchas, css-logical-properties | MDN flex-direction, MDN grid logical values |
| Verification: flip the app, canonical mixed test string, portals, screenshot diff | core verify | practice |

## Should cover (advanced)
| Item | Covered in | Basis |
|---|---|---|
| Code, pre, kbd, file paths stay LTR | core rules 6 | practice; UAX #9 neutrals |
| Tables with numeric/code/date cells | core gotchas | practice |
| Charts/SVG have no logical properties | core gotchas | practice |
| Scrollbar side and `scrollbar-gutter` | core gotchas, frameworks | web.dev Baseline; Tailwind v4.3 |
| `lang` on embedded opposite-language runs | bidi-text | W3C "Why use the language attribute" |
| Late-arriving logical values (`float`/`clear` inline-*, `resize`, `overflow-inline`) | css-logical-properties | MDN browser-compat-data |
| Hebrew fonts with a Hebrew subset, incl. monospace | core rules 8, css-logical-properties | Google Fonts css2 API |
| Arrow-key semantics reverse in RTL (tabs, sliders, radio groups) | NOT YET: open lesson | needs a WAI-ARIA APG / Radix passage before encoding |
| Carousel libraries' own RTL flags (Embla, Swiper) | NOT YET: open lesson | not verified against their docs |

## Out of scope (explicit)
Rationale refreshed 2026-09-26.
- Arabic shaping and Arabic typography: different script behaviour; the description routes it away unless shared patterns are asked for.
- Native mobile RTL (React Native I18nManager, SwiftUI, Android): excluded by the description.
- Hebrew punctuation and quotation marks (geresh, gershayim, Hebrew quotes): copy-level concern, not layout.
- Hebrew search normalisation (nikkud stripping, final-letter forms): text processing, belongs to NLP skills.
- i18n routing, locale detection and hreflang: general internationalisation; the skill assumes a locale segment exists.
- Full design-system tokens: `israeli-ui-design-system`; Tailwind presets in depth: `hebrew-tailwind-preset`.

## Authoritative sources
MDN (CSS logical properties, `:dir()`, unicode-bidi, flex-direction, grid logical values, Element.scrollLeft, Intl), MDN browser-compat-data, WHATWG HTML (dom.html directionality, rendering 15.3.5), Unicode UAX #9, CLDR `he.xml`, W3C hlreq and W3C i18n articles, Tailwind CSS docs and GitHub releases, MUI docs, Next.js docs, Google Fonts css2 API, IANA root zone database.
