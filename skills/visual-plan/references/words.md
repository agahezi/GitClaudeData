# Words

## Simplified Technical English

All prose on the page is ASD-STE100 Simplified Technical English. This covers the opening, every card,
every note in a zoom, every option field, every caption. Code, quoted words of the person, and the text
inside an example are exempt.

- **Approved words only.** Use a word only with its approved meaning. When unsure, use the most common
  short word with the same meaning.
- **Technical names are permitted.** Names from the code and the source of truth, product names, units.
  Use the same name for the same thing every time.
- **Short sentences.** One topic per sentence. 20 words for an instruction, 25 for a description, 6
  sentences per paragraph.
- **Active voice, simple tenses.** "The worker deletes the folder." Not "the folder is deleted". Present,
  past, future; no *has done*, no *is doing*.
- **No -ing forms** outside technical names. "the clone" not "cloning"; "to delete" not "deleting".
- **must and can.** *must* for a rule, *can* for a possibility. Not *should*, *may*, *might*.
- **Noun groups of 3 words at most.**
- **No contractions, idioms, metaphors, jokes.** No "the bill", "for good", "wires crossed", "the whole
  story", "a voice".
- **No shorthand or lifecycle vocabulary** the reader must decode: no "impl", "PoC-ism", "red-capable".
  Say "a test that fails before the change".

| Do not write | Write |
|---|---|
| utilize, leverage | use |
| perform, carry out | do |
| ensure, verify, check (verb) | make sure |
| demonstrate, indicate | show |
| commence, terminate | start, stop |
| obtain, provide | get, give |
| prior to, in order to | before, to |
| however, additionally | but, also |
| etc. | (list the items) |
| whatever, for good, the bill | (say the thing) |

## Names

- Every component, field and role takes the name of the **source of truth**: the schema, the file format
  or the API the change reads. A name from a prototype, a slide deck or a conversation that differs from
  it is a defect.
- A new name for an existing thing reads as a new thing. A borrowed name with a different meaning is
  worse. When a name changed during the work, add an "older words" card.
- Say what a thing **is** before what it **does**: "submit is one tool that does three things", then the
  three things.
- Numbers belong in tables and examples. A number in prose must change what the reader does.

## Badges

Every tag on the page is a badge, never a bold word with a colon.

| Badge | Meaning | Where |
|---|---|---|
| `recommended` | the option the author would build; first in its list | options |
| `keep` | a constraint kept, with its reason | constraints |
| `flag` | a constraint that needs a test or a decision | constraints |
| `exists` | a thing that exists today and is reused | data, map parts |
| `new` | a thing this change adds | data, map parts |
| `open` | a decision the person has not taken | decisions |
| `settled` | the table of decisions taken | decisions |
| `withheld` · `round trip` · `failed` · `recovered` | the variant a trace card shows | traces |

## Consistency

After every change, grep the page for every retired term and value, and fix every hit. The page head
lists the retired terms (`retired: [...]` in the plan data); the pack fails on a hit in the body.
