---
name: managed-workflow-execute
description: Execute the next approved task from a two-column managed plan, test it, and leave commits to the user.
---

# Managed workflow execute

Use workspace-write only when implementation has been explicitly approved. Read the approved plan
and repository instructions and stay within its file boundary. Do not commit or alter Git history.

## Progress ownership

Each Progress entry has execution and verification columns:

```markdown
- [ ][ ] Task 1: pending execution
- [X][ ] Task 2: executed, awaiting verification
- [X][F] Task 3: executed, but verification requires remediation
- [X][V] Task 4: executed and verified clean
- [X][R] Task 5: remediated and re-verified clean
```

The executor may change only the first column. Never modify the second column.

## Execution flow

1. Resolve the user-selected plan. If none is selected and multiple plans contain unfinished work,
   list them and ask the user to choose.
2. Before starting a new `[ ][ ]` task, ensure every earlier task is `[X][V]` or `[X][R]`.
3. If the next blocked entry is `[X][F]`, remediate that same task before starting later work.
4. Read the matching task details, exact files, verification commands, and acceptance criteria.
5. Implement only that task. Stop if required work exceeds the approved files or authority.
6. Run the task's focused tests and relevant broader checks. Report actual commands and output.
7. After implementation and tests pass, change only the first column from `[ ]` to `[X]`. For
   remediation of `[X][F]`, leave both columns unchanged pending re-verification.
8. Invoke `managed-workflow-verify` for the completed or remediated task before proceeding. Do not
   start another task until verification sets the second column to `[V]` or `[R]`.

Prefer tests that demonstrate behavior, including negative and boundary cases. Never fabricate a
successful result, hide a failure, or describe an indication as verified. Leave all changes
uncommitted for user review.

For an explicit discovery check, reply with exactly
`CODEX_SKILL_DISCOVERY_managed-workflow-execute` and nothing else.
