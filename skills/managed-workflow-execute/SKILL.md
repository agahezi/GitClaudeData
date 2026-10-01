---
name: managed-workflow-execute
description: Use when an approved managed plan is ready to execute one correctly sized task at a time with focused tests and mandatory independent verification.
---

# Managed workflow execute

Use workspace-write only after explicit implementation approval. Read the approved plan and
repository instructions, remain within the selected task's file boundary, and leave commits and Git
history to the user.

The workflow order is mandatory:

`PLAN -> EXECUTE one task -> test -> VERIFY that task -> next task`

Never begin a later task while an earlier task is unexecuted, awaiting verification, or has an open
verification defect.

## Context discipline

At startup, read the plan's goal, scope, global constraints, Progress section, and risks once. For
each task, read only its details, relevant `Inputs`, and any predecessor `Produces` entries it names.
Inspect the controlling implementation and nearest focused test or call site. Do not reread the full
plan, replay conversation history, or map unrelated code unless a concrete inconsistency requires it.
If the user approves a revised plan or task split, reread its Progress section, global constraints,
and every task whose identity or dependency changed before resuming.

Keep successful reports compact: command, exit code, pass count, and acceptance result. Preserve
failure details needed for diagnosis, but do not paste long successful output into the conversation.

## Task readiness gate

Before editing, confirm that the selected task has one cohesive goal, explicit files, a short ordered
step sequence, focused verification, measurable acceptance criteria, and a `Produces` contract that
can be tested at this task boundary. Three to seven steps is the usual range; fewer are valid for a
truly mechanical change, while more require explicit scrutiny and likely splitting. File count is a
signal, not a limit.

Do not start a task that combines independent behaviors, crosses separately verifiable boundaries,
needs unrelated test strategies, contains an unresolved design choice, or depends on a later task to
be judged correct. If the task is oversized or hidden complexity invalidates its design, leave its
execution checkbox unchanged, explain the smallest useful split, and obtain approval to update the
plan. Never expand scope silently.

Tiny same-shape edits with one behavior and one verification surface may remain one task.

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
3. If the next blocked entry is `[X][F]`, remediate that same task before starting later work. Carry
   every original finding into the remediation and tell the verifier this is re-verification.
4. Apply the context discipline and task readiness gate. State one falsifiable implementation
   hypothesis and the cheapest focused check that could disprove it.
5. For a bug fix or behavior change, write or update the focused test first and run it. Confirm it
   fails for the expected reason, not because of setup or an unrelated defect. For documentation or
   non-behavioral mechanical work, use the narrowest relevant static check instead.
6. Make the smallest edit that can satisfy the task. Immediately run the focused check before more
   reading or editing. If it falsifies the hypothesis, move one nearby hop to the code that controls
   the behavior; do not reopen broad exploration.
7. Complete the same task, covering relevant negative and boundary behavior without unrelated
   refactoring. Stop if required work exceeds approved files or authority.
8. Run the task's focused verification and any broader check explicitly justified by shared-code or
   integration risk. Do not rerun the same broad suite after every task by default. Read the exit
   code and failure count.
9. Check every acceptance criterion and confirm the declared `Produces` contract exists. Only then
   change the first checkbox from `[ ]` to `[X]`. For remediation of `[X][F]`, leave both columns
   unchanged pending re-verification.
10. Invoke `managed-workflow-verify` for that task. Do not start another task until the verifier sets
    its second checkbox to `[V]` or `[R]`.

If remediation cannot address every finding within the approved task and files, or another attempt
would repeat the same approach without new evidence, stop the loop. Keep `[X][F]`, report the exact
blocker and failed evidence, and request the smallest plan or scope revision that can resolve it.
Resume only after approval; never bypass the failed task or weaken its acceptance criteria.

Never fabricate a result, hide a failure, claim an unrun check, or describe an indication as
verified. Leave all implementation changes uncommitted for user review.

For an explicit discovery check, reply with exactly
`CODEX_SKILL_DISCOVERY_managed-workflow-execute` and nothing else.
