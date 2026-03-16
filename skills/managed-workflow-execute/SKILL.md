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
- **Step 6:** **Continue or Stop** — follow the Context-Aware Loop below.

## Context-Aware Continuous Execution

<HARD-GATE>
After completing each task, check the context usage from the CONTEXT MONITOR system reminder. Follow this logic:

- **Below 60% usage** → Immediately start the next task where first column is `[ ]`. Do NOT ask the user. Do NOT `/exit`.
- **Between 60-75% usage** → Continue only if the next task appears small/simple. Otherwise, stop.
- **Above 75% usage** → STOP. Do not start another task.

When stopping (any reason — context limit, all tasks done, or error):
1. Report which tasks were completed this session
2. **If ALL tasks in the plan now have first column `[X]`:** Invoke `managed-workflow-verify` by passing the current plan file path as an argument: `/managed-workflow-verify docs/plans/<current-plan-file>.md`. Verification must pass before the plan is considered done.
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
- **Only touch the first column** — the second column belongs to the verifier
- Tests MUST be written before implementation — no exceptions
- Tests MUST fail before implementation exists — if they pass, rewrite them
- Expected values in tests must be derived from plan requirements, not from implementation code
- Always update `[ ][ ]` → `[X][ ]` on disk immediately after each task completes
- Never skip a task — execute in order
- If a task fails, stop and report the failure (do not continue to next task)
- Strip commit steps from individual tasks in the plan — they are handled by the commit strategy above
