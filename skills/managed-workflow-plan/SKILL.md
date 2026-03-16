---
name: managed-workflow-plan
description: Create a bulletproof implementation plan saved to docs/plans/. Use before /managed-workflow-execute.
argument-hint: [topic]
---

# Managed Workflow — Plan

This skill creates a persistent, token-saving implementation plan.

- **Objective:** Create a bulletproof implementation plan.
- **Action:** MUST invoke the `superpowers:brainstorming` skill before creating the plan.
- **Output:** Save to `docs/plans/YYYY-MM-DD_HH_MM<topic>-plan.md`.
- **Constraint:** Ensure tasks are granular enough as a flat list for single-session execution.
- **GSD-Ready:** Ensure each task is atomic enough for GSD to implement in one go.

## MANDATORY Format — Overrides ALL Sub-Skills

<HARD-GATE>
Every plan file MUST contain a `## Progress` section with two-column markdown checkboxes listing ALL tasks. This section is the ONLY source of truth for both execution and verification progress. This requirement takes ABSOLUTE PRIORITY over any formatting from sub-skills (including `superpowers:writing-plans`, `superpowers:brainstorming`, or any other skill). If a sub-skill produces a plan without this section, you MUST add it before saving.
</HARD-GATE>

## Two-Column Progress Format

Each task in `## Progress` uses two checkboxes:

```
- [ ][ ] Task N: <description>
  ^   ^
  |   └── Verification status (owned by verifier)
  └─────── Execution status (owned by executor)
```

**Execution status (first column) — set by executor:**
- `[ ]` — not yet executed
- `[X]` — executed

**Verification status (second column) — set by verifier:**
- `[ ]` — not yet verified
- `[V]` — verified clean
- `[F]` — verified, bugs found and fixed → needs re-verify
- `[R]` — re-verified after fix → done

**All new plans initialize every task as `[ ][ ]`.**

Example of a plan in progress:
```
## Progress
- [X][V] Task 1: implement signal handler
- [X][F] Task 2: scoring logic
- [X][ ] Task 3: state transitions
- [ ][ ] Task 4: timeout cleanup
- [ ][ ] Task 5: circuit breaker
```

### Required Structure

Every plan file MUST follow this exact structure:

```markdown
# <Feature Name> Implementation Plan

**Goal:** <one sentence>
**Architecture:** <2-3 sentences>
**Tech Stack:** <key technologies>

## Progress
- [ ][ ] Task 1: <short description>
- [ ][ ] Task 2: <short description>
- [ ][ ] Task 3: <short description>
...

---

### Task 1: <short description>

**Files:**
- Create/Modify: `exact/path/to/file`

**Step 1:** ...
**Step 2:** ...
...

### Task 2: ...
```

### Rules

1. The `## Progress` section MUST appear before any task details
2. Every `### Task N` in the body MUST have a matching `- [ ][ ] Task N` checkbox in Progress
3. All new plans initialize every task as `- [ ][ ]` — never pre-fill either column
4. Task descriptions in checkboxes must be short (under 80 chars)
5. The detailed `### Task N` sections below contain the full implementation steps
6. The executor owns the first column only — never touches the second
7. The verifier owns the second column only — never touches the first
