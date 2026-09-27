---
name: managed-workflow-plan
description: Use when a repository change needs a reviewable design and a two-column implementation plan in docs/plans/.
---

# Managed workflow plan

Create a reviewable design first, then turn the approved design into a persistent implementation
plan. Planning begins read-only. Do not implement, commit, or change Git metadata.

## Design process

1. Inspect the user's request, repository instructions, current Git state, and relevant source,
   tests, and documentation without changing files. State the goal, constraints, and assumptions.
2. Ask only questions needed to resolve material uncertainty. If the existing context answers a
   question, proceed with that answer. Keep questions focused and easy to answer.
3. For a meaningful design choice, describe two or three feasible approaches, their trade-offs,
   and a recommendation. When there is only one reasonable approach, explain it briefly.
4. Present a concise design covering scope, architecture, affected components and interfaces,
   data flow where relevant, verification, risks, and likely failure modes. Match the detail to the
   size of the change.
5. End the design presentation with a direct approval question. Stop there: do not draft the
   implementation plan in chat or write a plan file before design approval. Reuse explicit approval
   already given in the conversation; do not ask for it again. If the user requests changes,
   revise the design before planning.

Do not commit a design or plan. Obtain explicit user approval before writing or overwriting either
artifact. For a change that needs a separate design document, save the approved design as
`docs/plans/YYYY-MM-DD_HH_MM_<topic>-design.md`. Save the corresponding implementation plan with
that timestamp and topic as `docs/plans/YYYY-MM-DD_HH_MM_<topic>-plan.md`. Otherwise save only the
approved plan with the same plan naming pattern.

When the user supplies an existing plan for formatting only, preserve every substantive statement.
Change only Markdown structure and progress tracking unless the user separately approves content
changes.

## Required plan content

The plan must contain:

- the goal, architecture, technology stack, and explicit scope;
- exact files expected to change;
- ordered, atomic implementation steps;
- tests and other verification commands;
- risks, assumptions, and likely failure modes; and
- measurable acceptance criteria.

Use capability-oriented language and do not assume particular tool names. Label unproven
observations as indications, reserve findings for evidence-backed issues, and call results verified
only when supported by real command output.

## Mandatory progress format

Every plan must contain a `## Progress` section before task details. It is the sole progress index.
Every detailed task must have exactly one matching progress entry:

```markdown
## Progress

- [ ][ ] Task 1: short description
- [ ][ ] Task 2: short description
```

The first checkbox is execution status and is owned by `managed-workflow-execute`:

- `[ ]` means not executed;
- `[X]` means executed.

The second checkbox is verification status and is owned by `managed-workflow-verify`:

- `[ ]` means not verified;
- `[V]` means verified clean;
- `[F]` means verification found defects and remediation is required;
- `[R]` means re-verified clean after remediation.

Initialize every new task as `[ ][ ]`. Progress descriptions must be under 80 characters. The
planner never pre-fills either column.

## Required plan structure

```markdown
# <Feature Name> Implementation Plan

**Goal:** <one sentence>
**Architecture:** <two or three sentences>
**Tech Stack:** <key technologies>

## Scope

<in-scope and out-of-scope work>

## Progress

- [ ][ ] Task 1: <short description>

---

### Task 1: <short description>

**Files:**

- Create: `exact/path`
- Modify: `exact/path`

**Implementation steps:**

1. <step>

**Verification:**

- `<command>`

**Acceptance criteria:**

- <measurable result>

## Risks, Assumptions, and Likely Failure Modes

- <item>
```

Each task must be independently implementable and verifiable. Split tasks whose correctness can
only be judged after later work. Every task detail heading and Progress entry must use the same task
number and short description.

For an explicit discovery check, reply with exactly
`CODEX_SKILL_DISCOVERY_managed-workflow-plan` and nothing else.
