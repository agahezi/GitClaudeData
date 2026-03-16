# managed-workflow

Description: A skill to manage planning, execution, and verification across any project.

## /m-plan
Description: Create a plan in docs/plans/ using Superpowers.
Usage: /m-plan <topic>

## /m-run
Description: Execute the next task from the plan in docs/plans/.
Usage: /m-run

**Post-Execution Gate:** After ALL tasks in the plan are marked `[X]` (completed), you MUST
automatically invoke `/m-verify` with the plan file path:

```
All tasks complete. Running verification...
/m-verify docs/plans/<plan-file>.md
```

Do NOT claim the plan is finished without running verification first.

## /m-verify
Description: Skeptical verification of a completed plan. Dispatches the QATester agent to audit every completed task.
Usage: /m-verify <plan-file-path>

Can also be invoked manually on any plan:
```
/m-verify docs/plans/2026-03-07-some-feature-plan.md
```

### How it works

1. **Read the plan file** at the given path.
2. **Extract all completed tasks** — every line matching `- [X][ ] Task N: ...` in the Progress section.
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
   - Phase 5: Code review (find real bugs)
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
- Automatically after `/m-run` completes all plan tasks
- Manually when suspicious about any completed plan
- After major refactors that "pass everything on the first try"
