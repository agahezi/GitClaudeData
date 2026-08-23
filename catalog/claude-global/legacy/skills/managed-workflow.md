# managed-workflow

Description: A skill to manage planning, execution, and verification across any project.

## /m-plan
Description: Create a plan in docs/plans/ using Superpowers.
Usage: /m-plan <topic>

## /m-run
Description: Execute the next task from the plan in docs/plans/, verifying each task before the next.
Usage: /m-run

**Per-Task Verify Gate:** Tasks are strictly serial — **execute task N → verify task N → only
then execute task N+1.** Immediately after EACH task is implemented and marked `[X]`, you MUST
invoke `/m-verify` scoped to that single task:

```
Task N implemented. Verifying before continuing...
/m-verify docs/plans/<plan-file>.md --task N
```

A task may not start until the previous task's verification column is `[V]` (clean) or `[R]`
(re-verified after a fix). If verification finds bugs (`[F]`), they are fixed and re-verified to
`[R]` before the gate opens. Do NOT batch all execution and verify at the end, and do NOT claim
the plan is finished without every task verified.

## /m-verify
Description: Skeptical verification. Dispatches the `qa_tester` agent (which delegates code review to `gsd-code-reviewer`) to audit task(s).
Usage: /m-verify <plan-file-path> [--task N]

- **Per-task (used by the verify gate):** `--task N` verifies exactly one task and returns.
- **Whole-plan / manual:** omit `--task` to verify every executed-but-unverified task:
```
/m-verify docs/plans/2026-03-07-some-feature-plan.md
```

### How it works

1. **Read the plan file** at the given path.
2. **Select tasks to verify** — if `--task N` was passed, just task N; otherwise every line
   matching `- [X][ ] Task N: ...` (or `[X][F]`, needs re-verify) in the Progress section.
3. **For each task**, read the task's detail section to find:
   - **Files:** created or modified
   - **What the task does** (the step descriptions)
4. **Dispatch the `qa_tester` agent** with:
   - The plan file path
   - The task description
   - The list of changed files for that task
   - Whether test files exist for changed files
   - Whether this is a re-verify pass
5. The agent runs the full **7-phase verification protocol**:
   - Phase 1: Run tests (baseline)
   - Phase 2: Coverage gap analysis
   - Phase 3: Test quality audit (are tests tautological?)
   - Phase 4: Mutation verification
   - Phase 5: Code review (find real bugs) — **delegated to the `gsd-code-reviewer` agent**
   - Phase 6: Concurrency & async audit
   - Phase 7: Integration gap analysis
6. **Collect findings** across all tasks.
7. **Fix all bugs found** — write regression tests, verify fixes pass.
8. **Report final status** with evidence (test counts, bugs found/fixed).

### Output expectations

The verification produces an inline report:
- Per-task findings: `BUG (Critical/Logic/Silent)`, `ZOMBIE TEST`, `MISSING COVERAGE`, `SMELL`, or `OK`
- Summary: total bugs found, total fixed, regression tests added
- Final test suite pass/fail counts as proof

### When to use
- Automatically by `/m-run`'s Per-Task Verify Gate — once per task, right after it is implemented
- Manually (whole-plan) when suspicious about any completed plan
- After major refactors that "pass everything on the first try"
