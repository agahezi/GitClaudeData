---
name: managed-workflow-plan
description: Use when a repository change needs an approved design and a reviewable, task-sized implementation plan with separate execution and verification tracking.
---

# Managed workflow plan

Turn a requested repository change into an approved design and a persistent implementation plan.
Planning is read-only until the user explicitly approves writing the plan artifact. Do not implement,
commit, or change Git metadata.

The workflow order is fixed:

`PLAN -> EXECUTE one task -> test -> VERIFY that task -> next task`

Every implementation task must appear in the plan and receive separate execution and verification
status. Scope classification changes the depth of planning, never the execution and verification
gates.

## Design process

1. Inspect the request, repository instructions, current Git state, the controlling implementation,
   and the nearest relevant test or call site without changing files. State the intended outcome,
   users, success criteria, constraints, assumptions, and non-goals. Distinguish requirements from
   assumptions.
2. Classify the work and state the classification so the user can correct it:
   - **Spike:** a feasibility question whose output is a recommendation, not production code.
   - **Bounded:** a focused change to an existing behavior or flow.
   - **Architectural:** a new subsystem, cross-boundary interface, or structural change.
3. Ask only questions that resolve material uncertainty. Do not ask for information already present
   in the request or repository. Prefer one focused question at a time.
4. For a meaningful design choice, lead with the recommended approach, then describe up to two
   alternatives and their trade-offs. Do not invent alternatives for an obvious local change.
5. Present a design proportional to the classification:
   - Spike: the question, probe, evidence needed, and stopping condition.
   - Bounded: a short design covering behavior, affected files or interfaces, and testing.
   - Architectural: scope, components, interfaces, data flow, error handling, testing, risks, and
     likely failure modes.
6. End with a direct approval question. Stop there. Do not draft or write an implementation plan
   before design approval. Reuse explicit approval already given; do not ask twice.

Start exploration from one concrete anchor and follow only the path that controls the behavior.
Take another read only when it can distinguish between plausible designs or identify a focused test.
Do not map unrelated repository surfaces.

A spike ends with findings and a recommendation. Bounded and architectural changes continue to an
implementation plan after design approval. Hidden complexity upgrades bounded work to architectural;
stop and obtain approval for the revised design rather than silently expanding scope.

Do not commit a design or plan. Obtain explicit user approval before writing or overwriting either
artifact. For a change that needs a separate design document, save the approved design as
`docs/plans/YYYY-MM-DD_HH_MM_<topic>-design.md`. Save the corresponding implementation plan with
that timestamp and topic as `docs/plans/YYYY-MM-DD_HH_MM_<topic>-plan.md`. Otherwise save only the
approved plan with the same plan naming pattern.

For bounded work, the approved in-chat design is sufficient, but the persistent plan is still
required before `managed-workflow-execute` begins. After writing any plan, request explicit
implementation approval. Planning approval is not implementation approval.

When the user supplies an existing plan for formatting only, preserve every substantive statement.
Change only Markdown structure and progress tracking unless the user separately approves content
changes.

## Task sizing

Each task delivers one observable behavior or one independently verifiable enabling capability. A
task is correctly sized when an implementer can understand it from the task plus global constraints,
change it without unrelated repository exploration, and prove it with focused verification.

Prefer tasks that:

- have one goal and one cohesive acceptance boundary;
- touch a small set of tightly related files, without treating file count as a hard limit;
- usually contain three to seven ordered implementation steps, with fewer allowed for a truly
   mechanical change;
- name one focused verification command and its expected result;
- define the inputs they consume and the interface or behavior they produce; and
- include relevant negative and boundary behavior.

Split a task when it combines independent behaviors, crosses boundaries that can be verified
separately, needs unrelated verification strategies, contains an unresolved design choice, or cannot
be summarized without joining goals with "and". Prefer vertical, working slices over file-layer
tasks. Do not split tiny same-shape edits that share one behavior and one verification surface.

If correct completion depends on a later task, either combine the work into one cohesive task or
redefine the first task around an independently testable contract. Never create a task that can only
be declared correct by assumption.

## Required plan content

The plan must contain:

- the goal, architecture, technology stack, and explicit scope;
- exact files expected to change;
- ordered implementation steps sized by the task rules above;
- tests and other verification commands;
- risks, assumptions, and likely failure modes; and
- measurable acceptance criteria.

For each task, identify the cheapest focused test that can disprove its behavior, including relevant
negative and boundary cases. Use test-first ordering for bug fixes and behavior changes. Do not force
a failing-test ceremony for documentation or non-behavioral mechanical changes. Specify a broader
suite only at a justified integration point or final task, and state what risk it covers.

Keep the plan as a coordination artifact, not a source-code copy. Reference exact files, symbols,
interfaces, commands, and expected behavior. Include code only when an exact literal or signature is
part of the contract. Do not paste repository history, long command output, or implementation code
that the executor can read locally.

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

**Inputs:**

- <existing interface or output from an earlier task>

**Implementation steps:**

1. <step>

**Verification:**

- `<command>`

**Acceptance criteria:**

- <measurable result>

**Produces:**

- <interface or behavior available to later tasks>

## Risks, Assumptions, and Likely Failure Modes

- <item>
```

Each task must be independently implementable and verifiable. Every task detail heading and Progress
entry must use the same task number and short description. Order tasks so each consumes only explicit
outputs from completed predecessors.

For an explicit discovery check, reply with exactly
`CODEX_SKILL_DISCOVERY_managed-workflow-plan` and nothing else.
