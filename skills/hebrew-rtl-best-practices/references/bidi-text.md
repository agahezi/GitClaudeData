# Bidirectional Text in Hebrew UIs

Read when content mixes Hebrew with Latin, numbers, phone numbers, currency, dates, URLs, or user input.

## Isolation

```css
/* Isolate embedded LTR content */
.ltr-content {
  unicode-bidi: isolate;
  direction: ltr;
}

/* Mixed or unknown-direction content: each paragraph picks its own base direction */
.user-content {
  unicode-bidi: plaintext;
}
```

Do not use `unicode-bidi: bidi-override` for mixed content. It switches off the implicit part of the bidi algorithm and lays every character out strictly in the `direction` value, so English inside an RTL override renders letter-reversed. Reserve it (or `<bdo>`) for deliberately forcing a known visual order.

**`<bdi>` vs `<bdo>`:** use `<bdo dir="ltr">` only when you want to *force* a direction (it overrides the bidi algorithm). For user-generated or unknown-direction content, prefer `<bdi>`, which *isolates* the content so its direction is auto-detected and cannot leak into the surrounding text:

```html
<!-- User name could be Hebrew or Latin; bdi isolates it either way -->
<p>שלום, <bdi>{{ userName }}</bdi>, ברוך הבא</p>
```

**Pair `dir` with `lang` on embedded runs.** `dir` only fixes visual order. Mark an English term inside Hebrew prose as `<span lang="en" dir="ltr">`: speech synthesizers and Braille translators use the language tag to switch language mode, and `:lang()` font and hyphenation rules key on it. Without it, assistive tech has no signal to leave Hebrew mode for that run.

For free-text fields, `dir="auto"` (or `unicode-bidi: plaintext` in CSS) lets the browser pick the base direction per value, which is the correct default for comments, names, and search queries where you do not know the language in advance.

Common bidi issues:
- Phone numbers written with spaces (`050 321 4450`) or a `+972` prefix appearing scrambled: wrap in `<bdo dir="ltr">`. A plain hyphenated `050-321-4450` already stays intact, because a single hyphen between two numbers joins them into one number run.
- Punctuation at wrong end of sentence: Use `unicode-bidi: isolate`
- URLs/emails in Hebrew text: Wrap in `<span dir="ltr">`

## Numbers, currency, and dates

**Numbers and dates:** Standalone numbers and DD/MM/YYYY dates inside Hebrew text usually render fine because digits are weak-LTR, but a number that is immediately followed by a sign, currency, or a second number can flip. When a value must keep a fixed visual order, isolate it with `<span dir="ltr">` or `unicode-bidi: isolate` rather than trusting the default bidi resolution.

**Format the value, then isolate it.** Bidi isolation only stops a *correct* string from flipping; it does not produce the right string. Use `Intl` to format, then isolate: `Intl.NumberFormat('he-IL', { style: 'currency', currency: 'ILS' })` for shekel amounts and `Intl.DateTimeFormat('he-IL')` for dates, and wrap the output in `<bdi>` (or `unicode-bidi: isolate`) if it sits inline in Hebrew prose. Do not force `dir="ltr"` on `he-IL` output: the currency string carries its own right-to-left marks (U+200F) and is laid out for an RTL context, so forcing LTR moves the ₪ to the other side of the number. The distinction: force `dir="ltr"` on raw digit strings such as phone numbers, which carry no direction marks, and only isolate Intl output, which does. Devs commonly conflate the two and apply bidi fixes to a formatting bug (or vice versa).

**Hebrew dates need the calendar extension.** `Intl.DateTimeFormat('he-IL')` resolves to the Gregorian calendar (`resolvedOptions().calendar === 'gregory'`), so a Hebrew locale alone will not give you a Hebrew date. Request the calendar through the `-u-ca-` Unicode extension: `Intl.DateTimeFormat('he-IL-u-ca-hebrew')` formats 20 September 2026 as `9 בתשרי 5787`. Use it for holiday, yahrzeit, and dual-date displays, and keep the Gregorian format for anything users file with an authority.

### Example: numbers showing backwards

```html
<!-- Wrong: space-separated groups render in reverse order (4450 321 050) -->
<p>התקשרו אלינו: 050 321 4450</p>

<!-- Wrong: the +972 prefix jumps to the far end (50-321-4450 972+) -->
<p>התקשרו אלינו: +972 50-321-4450</p>

<!-- Correct: isolate the LTR content -->
<p>התקשרו אלינו: <span dir="ltr">+972 50-321-4450</span></p>
```

A hyphen-only number such as `050-321-4450` renders correctly without help, so check the actual format before blaming bidi. Use `unicode-bidi: isolate` with `direction: ltr` on the containing span for CSS-only solutions.

## Form inputs

**Form inputs need `dir="auto"`.** Put `dir="auto"` on every `<input>` and `<textarea>` so each value resolves its own base direction. This is the most visible end-user RTL bug: an email or an English word typed into a Hebrew form jumps to the wrong side without it. Note that the placeholder does not trigger auto-detection, so set the resting direction with CSS if the empty-field look matters. Two exceptions. A `type="tel"` input is already LTR by default (the HTML spec gives a tel input without `dir` an LTR directionality), so leave `dir` off it. For `email` and `url` fields most values are Latin, so set `dir="ltr"` deliberately: with `dir="auto"` a value that starts with Hebrew, such as an address on the Hebrew-script domain `.ישראל`, flips the field to RTL mid-typing. Weigh that against the cost: `dir="ltr"` also left-aligns a Hebrew placeholder.

## Sources

| Source | URL | What to Check |
|--------|-----|---------------|
| MDN `<bdi>` element | https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/bdi | Isolating user-generated bidi content |
| W3C Internationalization | https://www.w3.org/International/articles/inline-bidi-markup/ | Unicode bidi algorithm, markup best practices |
