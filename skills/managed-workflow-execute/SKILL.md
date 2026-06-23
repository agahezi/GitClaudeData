---
name: managed-workflow-execute
description: Execute the next available task from the latest plan in docs/plans/. Use after /managed-workflow-plan.
---

# Managed Workflow — Execute

This skill executes tasks from an existing plan continuously until context runs low.

## Progress Tracking Format

The plan file uses a two-column checkbox per task in the `## Progress` section:

```
- [X][ ] Task 1 — description    ← executed, not yet verified
- [ ][ ] Task 2 — description    ← not yet executed
```

- First column `[X]` / `[ ]` — execution status (owned by executor)
- Second column `[V]` / `[F]` / `[R]` / `[ ]` — verification status (owned by verifier)

**Executor only touches the first column. Never modify the second column.**

## Test Runner Auto-Detection

Detect the project's test runner before running tests:
1. `pyproject.toml` / `pytest.ini` / `setup.cfg` exists -> `pytest tests/ -v --tb=short`
2. `package.json` exists -> read the `test` script, use `npm test` or `yarn test`
3. `go.mod` exists -> `go test ./... -v`
4. `Cargo.toml` exists -> `cargo test`
5. CLAUDE.md specifies a test command -> use that
6. None match -> ask the user

## Execution Flow

- **Step 1:** Locate the latest unfinished plan in `docs/plans/`. If more than one plan has tasks where the first column is `[ ]`, show each plan's filename and ask user to choose. If none found, say no unfinished plans exist.
- **Step 2:** **BYPASS** internal GSD planning. Use the file checkboxes as the only plan.
- **Step 3:** Identify the first task where the first column is `[ ]`.
- **Step 4:** **Write tests first (TDD), then implement.**

  <HARD-GATE>
  Before writing any implementation code:

  1. Read the task description carefully — understand the REQUIRED BEHAVIOR from the plan, not from any existing code.
  2. Write failing tests that verify the required behavior described in the plan:
     - At least one test per acceptance criterion or described behavior
     - At least one negative test (wrong input, error path, boundary condition)
     - Tests must be based on the PLAN REQUIREMENTS — do NOT look at implementation code first
     - Expected values must be calculated independently — do NOT derive them from implementation logic
  3. Run the tests — they MUST fail at this point. If they pass before implementation exists, the tests are tautological. Delete and rewrite them.
  4. Now implement the task until all written tests pass.
  5. Run the full test suite using the auto-detected test runner to confirm no regressions.
  6. If the full suite has failures unrelated to this task — stop and report. Do not continue.
  </HARD-GATE>

- **Step 5:** **State Update:** Change `[ ][ ]` → `[X][ ]` in the plan file on disk — first column only. Never touch the second column.
- **Step 6:** **Per-Task Verify Gate (HARD-GATE)** — verify THIS task before doing anything else.
  See the Per-Task Verify Gate section below. Do not start, plan, or read ahead to the next task
  until this task's second column is `[V]` or `[R]`.
- **Step 7:** **Continue or Stop** — only after the gate passes, follow the Context-Aware Loop below.

## Per-Task Verify Gate

<HARD-GATE>
This is the core of the managed workflow: **a task is not "done" when it is implemented — it is
done when it is verified.** After Step 5 marks a task `[X][ ]`, you MUST verify that single task
and drive it to a clean verification state BEFORE starting the next task.

For the task just completed (call it task N):

1. **Invoke `managed-workflow-verify` scoped to this one task:**
   `/managed-workflow-verify docs/plans/<current-plan-file>.md --task N`
   This dispatches the `qa_tester` agent for task N (which in turn delegates code review to
   `gsd-code-reviewer`). Do NOT verify the whole plan here — only task N.
2. **Read the resulting second-column state for task N from the plan file:**
   - `[V]` — verified clean → the gate passes; proceed to the Context-Aware Loop.
   - `[F]` — bugs were found and fixed; verification is NOT yet clean. The verify skill will run
     a re-verify pass to drive it to `[R]`. Wait for that — do NOT advance on `[F]`.
   - `[R]` — re-verified clean after a fix → the gate passes; proceed.
3. **GATE RULE:** You may start the next `[ ]` task ONLY when task N's second column is `[V]` or
   `[R]`. If it is `[ ]` or `[F]`, the gate is CLOSED — do not pick the next task. Fix and
   re-verify (via the verify skill) until task N is `[V]`/`[R]`, or stop and report if blocked.
4. Never read ahead, scaffold, or write tests for task N+1 while task N's gate is closed. Tasks
   are strictly serial: execute N → verify N → (clean) → execute N+1.

This means the executor DOES inspect the second column to read the gate — but still never
*writes* it (the verifier owns writes to the second column).
</HARD-GATE>

## Context-Aware Continuous Execution

<HARD-GATE>
Reach this only AFTER the Per-Task Verify Gate for the current task has passed (`[V]`/`[R]`).
Then check the context usage from the CONTEXT MONITOR system reminder and follow this logic:

- **Below 60% usage** → Immediately start the next task where first column is `[ ]`. Do NOT ask the user. Do NOT `/exit`.
- **Between 60-75% usage** → Continue only if the next task appears small/simple. Otherwise, stop.
- **Above 75% usage** → STOP. Do not start another task.

When stopping (any reason — context limit, all tasks done, or error):
1. Report which tasks were completed AND verified this session
2. **Because each task is verified inline at its gate, a fully-executed plan is already verified.**
   If any task somehow remains `[X][ ]` or `[X][F]` (e.g. a prior session stopped mid-gate), run
   `/managed-workflow-verify docs/plans/<current-plan-file>.md` (no `--task`) to finish verifying
   the stragglers before considering the plan done.
3. **Detect automation mode from the user's prompt:**
   - If the user's prompt contains `WORKFLOW_MODE` with value `auto` or `hybrid` → **Do NOT commit. Do NOT ask any questions. Just report completed tasks and exit immediately.**
   - Otherwise (interactive session, manual `/managed-workflow-execute` invocation) → Ask the user if they want to commit all changes. If approved, create ONE commit covering all completed tasks.
4. Then `/exit`
</HARD-GATE>

## Commit Strategy

<HARD-GATE>
Do NOT commit after each individual task. All changes accumulate unstaged throughout the session. Only when execution stops (context limit reached, all tasks done, or user interrupts):

**If the user's prompt contains `WORKFLOW_MODE` with value `auto` or `hybrid`:**
- Do NOT commit files. Do NOT ask any questions. Just exit immediately so the wrapping script can handle the next session.

**Otherwise (interactive session):**
1. Show a summary of all completed tasks
2. Ask user: "Commit all changes?"
3. If yes — stage relevant files and create a single commit
4. If no — leave changes unstaged for user to handle
</HARD-GATE>

## Rules

- The plan file checkboxes are the ONLY source of truth for progress
- **Only WRITE the first column** — the second column belongs to the verifier. You may READ the
  second column to evaluate the Per-Task Verify Gate, but never write to it.
- Tests MUST be written before implementation — no exceptions
- Tests MUST fail before implementation exists — if they pass, rewrite them
- Expected values in tests must be derived from plan requirements, not from implementation code
- Always update `[ ][ ]` → `[X][ ]` on disk immediately after each task completes
- **Verify each task before starting the next** — a task may not begin until the previous task's
  second column is `[V]` or `[R]` (Per-Task Verify Gate). Execute N → verify N → (clean) → N+1.
- Never skip a task — execute in order
- If a task fails, stop and report the failure (do not continue to next task)
- If a task's verify gate cannot reach `[V]`/`[R]` (verification keeps finding bugs), stop and
  report — do not advance past a task that will not verify clean
- Strip commit steps from individual tasks in the plan — they are handled by the commit strategy above
