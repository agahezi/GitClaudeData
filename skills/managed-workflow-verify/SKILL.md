---
name: managed-workflow-verify
description: Skeptical verification of a completed plan. Dispatches qa_tester agent to audit every task for real bugs. Use after /managed-workflow-execute or manually on any plan.
argument-hint: [plan-file-path]
---

# Managed Workflow — Verify

Skeptical, adversarial verification of a completed implementation plan.
AI-written tests that verify AI-written code are tautological. This skill breaks that loop.

## Progress Tracking Format

The plan file uses a two-column checkbox per task in the `## Progress` section:

```
- [X][V] Task 1 — description    ← executed, verified clean
- [X][F] Task 2 — description    ← executed, bugs found & fixed, needs re-verify
- [X][R] Task 3 — description    ← executed, re-verified after fix — done
- [X][ ] Task 4 — description    ← executed, not yet verified
- [ ][ ] Task 5 — description    ← not yet executed
```

- First column `[X]` / `[ ]` — execution status (owned by executor, do NOT modify)
- Second column `[V]` / `[F]` / `[R]` / `[ ]` — verification status (owned by verifier)

**Verifier only touches the second column.**

## Test Runner Auto-Detection

Detect the project's test runner before running tests:
1. `pyproject.toml` / `pytest.ini` / `setup.cfg` exists -> `pytest tests/ -v --tb=short`
2. `package.json` exists -> read the `test` script, use `npm test` or `yarn test`
3. `go.mod` exists -> `go test ./... -v`
4. `Cargo.toml` exists -> `cargo test`
5. CLAUDE.md specifies a test command -> use that
6. None match -> ask the user

## Invocation

- **Auto:** `managed-workflow-execute` triggers this after all tasks are `[X]`
- **Manual:** `/managed-workflow-verify docs/plans/2026-03-07-some-plan.md`
- **No argument:** Finds the latest fully-completed plan in `docs/plans/` (all first-column checkboxes `[X]`)

## Execution Flow

### Step 1: Load the Plan
- Read the plan file
- Scan the `## Progress` section for tasks where:
  - First column is `[X]` (executed) AND
  - Second column is `[ ]` (unverified) OR `[F]` (needs re-verify)
- These are the tasks to process this session — skip `[V]` and `[R]` tasks entirely
- For each task to process, read its `### Task N` detail section to get:
  - **Files:** created or modified
  - **Step descriptions** (what was implemented)
  - **Whether this is a re-verify pass** (second column was `[F]`)

### Step 2: Pre-Flight Test Check
Before dispatching the QA agent, check whether tests exist for the changed files.

- For each task's `changed_files`, look for corresponding test files using the project's test directory convention (e.g., `tests/`, `__tests__/`, `*_test.go`, etc.).
- Run the full test suite using the auto-detected test runner as a baseline.
- **If no test files exist for a task:** note this explicitly in the dispatch to the QA agent.
  The QA agent's Phase 2 (Coverage Gap Analysis) will write the missing tests before proceeding.
- Do NOT skip tasks that have no tests — missing tests are themselves a finding.

### Step 3: Dispatch QA Agent Per Task
For EACH task identified in Step 1, dispatch the `qa_tester` agent with:
- `plan_file`: The plan file path
- `task_description`: The task's detail section text
- `changed_files`: The files listed in that task's **Files:** section
- `has_existing_tests`: Whether test files were found in Step 2 (true/false)
- `is_reverify`: Whether this is a re-verify pass after bug fixes (true/false)

**For normal verification passes** — the agent runs all 7 phases in strict order:

1. **Phase 1 — Run Tests:** Full test suite baseline. Records exact pass/fail counts. Stops if anything fails.
2. **Phase 2 — Coverage Gap Analysis:** Cross-references plan requirements and domain checklist against existing tests. Writes ALL missing tests before proceeding. Does not defer.
3. **Phase 3 — Test Quality Audit:** Detects tautological tests, over-mocked tests, copied expected values, and trivially-passing tests. Rewrites bad tests before proceeding.
4. **Phase 4 — Mutation Verification:** Temporarily breaks critical functions to prove tests actually catch regressions. Flags ZOMBIE tests that don't fail on mutation.
5. **Phase 5 — Code Review:** Default value mismatches, missing constructor fields, stale derived values, crash-on-first-run, prompt ordering, silent error swallowing.
6. **Phase 6 — Concurrency & Async Audit:** Simultaneous state transitions, duplicate task submission, race between timeout and completion, cache/DB state divergence.
7. **Phase 7 — Integration Gap Analysis:** End-to-end data flow tracing, boundary mismatches between changed and unchanged code.

**For re-verify passes** (`is_reverify: true`) — run only:
1. **Phase 1 — Run Tests:** Confirm full suite is green.
4. **Phase 4 — Mutation Verification:** Confirm fixes didn't produce zombie tests.
5. **Phase 5 — Code Review:** Review only the files modified during the fix — confirm no new bugs introduced.

**All phases are mandatory for their pass type. No phase may be skipped.**

### Step 4: Update Progress After Each Task
Immediately after the QA agent finishes each task — before moving to the next — update the second column in the plan file:

- **No bugs found** → mark `[V]`
- **Bugs found and fixed** → mark `[F]` (will be re-verified in a future session or later this session if context allows)
- **Re-verify passed** → mark `[R]`

Do NOT wait until all tasks are done to update progress. Update after each task so a context interruption doesn't lose track.

### Step 5: Collect and Report Findings
Aggregate findings across all tasks verified this session. Report per task as:
- **BUG (Critical):** Would crash in production
- **BUG (Logic):** Wrong behavior, won't crash
- **BUG (Silent):** Produces wrong results without any error
- **ZOMBIE TEST:** Test exists but would not catch a real regression
- **MISSING COVERAGE:** Plan requirement with no test
- **MISSING DOMAIN TEST:** Domain check with no test
- **SMELL:** Not a bug yet, but fragile
- **OK:** Area reviewed, no issues (list what was checked per phase)

Do NOT report "all clear" without showing work for each phase.

### Step 6: Fix All Bugs
- Fix every bug found (Critical, Logic, Silent)
- Replace all ZOMBIE tests with real ones
- Write regression tests for each bug fixed
- **Re-run Phase 5 (Code Review) on any files modified during fixes**
- Run full test suite to verify all fixes — report exact pass/fail counts as evidence
- Update task second column to `[F]` after fixing

### Step 7: Context-Aware Loop
After each task, check context usage:

- **Below 60%** → immediately start the next unverified task
- **Between 60–75%** → continue only if the next task appears small
- **Above 75%** → STOP

When stopping:
1. Report which tasks were verified this session and their final status
2. Report how many `[F]` tasks remain for re-verify in the next session
3. If all tasks are `[V]` or `[R]` → emit the Final Summary and exit
4. Otherwise → exit and let the next session pick up remaining `[ ]` and `[F]` tasks

### Step 8: Final Summary
Only emit when ALL tasks in the plan have second column `[V]` or `[R]`:

```
## Verification Summary
- Tasks verified: N/N
- Bugs found: X (Y Critical, Z Logic, W Silent)
- Zombie tests replaced: N
- Missing tests written: N
- Bugs fixed: X
- Regression tests added: N
- Final test suite: XXX passed, 0 failed
```

## Rules

- NEVER skip a phase — all mandatory phases for the pass type must run
- NEVER claim "all clear" without evidence from each phase
- NEVER dispatch QA agent without checking for test existence first (Step 2)
- NEVER modify the first column — execution status is owned by the executor
- Update the second column immediately after each task — do not batch updates
- The qa_tester agent is SKEPTICAL by default — assume bugs exist
- Fix bugs inline, don't just report them
- Run the full test suite BEFORE and AFTER fixes
- Re-run Phase 5 code review after any fix — fixes can introduce new bugs
- `[F]` tasks must always be re-verified — one pass is never enough after a bug fix
