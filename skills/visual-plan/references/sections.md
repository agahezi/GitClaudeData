# Sections

The page is a list of blocks in this order. Core blocks are always present. Extras are dropped when they
would be empty; a dropped core block is a lint error, a dropped extra is silent.

**One fact, one place.** Each rule lives in the one block or zoom that owns it, and no other block restates
it: a zoom note is not repeated as a settled decision, a goal, a scope line, or a risk. A page that says the
same thing four times reads as scattered, however short each line is.

Every block holds only what this plan does. A related thing appears only when the plan depends on it, and
only the part it uses (the ACP method it calls, the limit its new code must obey). A neighbour the plan does
not change, a term it does not add, and a behaviour that stays as it is all stay off the page.

For each block: what it holds, and the mistake it exists to prevent.

## Core

### opening
What: the name of the change and the place, 3 to 7 words, as the title. Then 2 to 4 sentences: what the
system does, what was selected or decided before this page, what this page is. When the code is new,
say "from scratch" and what it is not a refactor of.
Prevents: a reader who takes a rebuild for a port, or a port for a refactor.

### problem
What: two cards. *Problem*: what breaks, for whom, why now. *Current state*: only the parts this plan
replaces, in 5 lines at most, each with a file reference, labelled "for reference, not for reuse" when the
new code is new.
Prevents: a design with no stated reason, and a map that cannot be read as "what changes".

### map
What: one overview diagram of the proposed design, as a node tree (see `nodes.md`): the top node is the
map; each box zooms into a node with its purpose, its ports, its inside and one real example; a part of
the inside can open a third-level node. A box is a part the plan adds or changes; an unchanged neighbour
is a labelled arrow at the edge, with no box and no zoom. Under the map, two lines of plain walkthrough.
The map is the spine of the page: it shows the target state, and every other block describes that state
or bears on it.
Prevents: a design described only in prose, nuance that has no layer to live in, a map that reads as
an architecture tour, and a page organized around its decisions instead of the design.

### decisions
What: (a) the settled table: only the decisions that had a real alternative: decision · follows from ·
considered (the library, SDK or pattern adopted or rejected). A design fact with no alternative is a zoom
note, not a decision, and a choice the person made on a design reference is shown there, not listed
again. (b) the open decisions, each one with context (the problem, why now, what is known with file
references, who is affected), then its options one line each, recommended first and badged, none
preselected, each option opening a panel with How · Gains · Costs · Effort / risk · Reversible. A hint
under the options: "Click an option to see its details". Open questions and open decisions are one list.
A closed decision moves into the settled table with its reason. The lock is offered only when the open
list is empty.
Prevents: a decision taken on the person's behalf, a fork hidden in prose, a question outside the list.

### goal
What: 3 to 5 acceptance statements that can each be true or false when the change is done. Each one names
an outcome a person can observe, not a part of the map.
Prevents: a goal that cannot be checked, and a goal that restates the map.

### scope
What: the list "not in this plan", complete, no "etc.". A thing that is deferred names what will do it
later. The map shows what is in; an "in this plan" list is added only for work the map does not show
(copy, docs, fixtures), in one line each.
Prevents: a boundary that the reader must guess.

## Extras

### examples
What: a strip under the opening: the 2 or 3 real cases the page uses throughout, one line each, named so
every example on the page can say which case it is. The cases come from the product's own users
(PRODUCT.md or its equivalent), never from the domain of the products studied for reference.
Prevents: examples that drift between cases.

### design reference
What: the visual design the person locked, as its own file (the approved mockup with the rejected options
removed), named by a `design` block and kept beside the plan as the visual spec; the pack inlines it.
Never screenshots: a screenshot drifts from its source and cannot be inspected. The mockup shows only what
the source of truth sends: read what the provider gives for each field before you draw it.
Prevents: two copies of the design that disagree, and a builder who cannot read the spacing or the markup.

### terms
What: only the domain words this plan adds or renames, in the vocabulary of the source of truth (the
schema, the file format, the API that the change reads). One card per word with its meaning and a real
example. One card named "older words" when a name changed during the work, mapping each old name to the
current one. No generic words of the platform (workflow, queue, row, table).
Dropped when the plan adds and renames no word.
Prevents: two vocabularies for one thing, and a reader who must decode a name.

### traces
What: one real run as a call tree (`calls` view): one call per line, the name, a short note of what it
does or returns, a location. No new / changed marks when all the code is new. Then cards, each with a
badge, for the cases where the plan's behaviour differs: a withheld feature, a round trip, each failure,
each recovery. A case the plan leaves as it is gets no card. Drop the block when its call tree only walks
the boxes of the map again and no card shows a case the zooms do not already state.
Prevents: rules that are stated but never seen in action.

### constraints
What: a table of every numeric setting or limit the plan sets, or that its new code must obey: the
value, who applies it, and
a keep or flag badge with the reason. A mechanism that improves quality is described as a mechanism with
the failure it prevents, never as a leftover. A limit that silently drops data is flagged as a bug.
Prevents: an inherited number nobody can justify, and a quality mechanism dropped as noise.

### data
What: only the important data models: the persisted record, the return value, one migration as SQL in
the project's own language. What does not change, in one sentence. No column-by-column lists.
Prevents: a schema dump that nobody reads.

### risks
What: two lists. *Risks*: what production will meet that the experiment or the prototype never did.
*Behaviour changes*: what a reader of the data, the logs or the tests sees differently after the change.
Prevents: a surprise that was knowable.

### reused
What: the parts of the existing system the new code calls, and the reference material it borrows (prompts,
measured rules) without importing.
Prevents: a false claim of reuse, or of novelty.

## What no block holds

- Code sketches, classes, function signatures, file:line for code that does not exist yet.
- Task lists, slices, who does what, test matrices. Those are the implementation plan, after the lock.
- History: "was", "dropped", "previously", dates, who asked for what.
- Explanations of generic platform concepts.
