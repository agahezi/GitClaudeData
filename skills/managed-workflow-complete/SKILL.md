---
name: managed-workflow-complete
description: Use after every managed-plan task is independently verified to run final integration checks, review whole-plan acceptance, and write the persistent completion summary.
---

# Managed workflow complete

Close an implemented plan with current end-to-end evidence. This stage runs only after the per-task
workflow has finished:

`PLAN -> (EXECUTE one task -> test -> VERIFY that task)* -> COMPLETE`

Do not modify implementation files, task details, Progress checkboxes, prior evidence, commits, or
Git history. The only permitted repository edits are one append-only `FINAL` Evidence Log entry and
the selected plan's `## Completion Summary`. Make both updates in the same repository edit.

## Entry gate

Every Progress entry must be `[X][V]` or `[X][R]`. Stop when a task is unexecuted, awaiting
verification, or `[X][F]`; report the earliest blocking task and return to the owning workflow stage.
Do not infer completion from code or chat when plan state is incomplete.

## Plan format gate

Validate the plan with `<skills-root>/managed-workflow-plan/scripts/validate_plan.py <plan-path>`,
where `<skills-root>` is the folder that contains this skill's folder, using Python 3 (`python3`, or
`python` where it is Python 3). Run it before the entry gate: on `PLAN_FORMAT_INVALID`, stop without
editing and report the errors. Run it again after writing the `FINAL` entry and summary; on failure,
correct only that edit. If the validator is missing, stop and report an incomplete installation.

## Context discipline

Read the plan goal, scope, global constraints, all acceptance criteria, Progress, complete compact
Evidence Log, risks, and the current whole-plan diff once. Inspect changed contracts and direct
integration boundaries. Do not replay conversation history, reread successful command output, or
rediscover completed task internals without a concrete final-risk reason.

## Completion flow

1. Resolve the user-selected plan and enforce the entry gate.
2. Build a concise checklist mapping every plan-level acceptance criterion to task evidence and the
   current implementation. Treat missing evidence as `Not checked`, not success.
3. Select the plan's justified final or integration command. Run it once against the current files,
   read the exit code and failure count, and retain only the output needed to support the result. Do
   not rerun an unchanged successful suite.
4. Inspect the whole-plan diff for approved scope, unintended behavior, integration mismatches,
   generated or secret files, and unresolved risks. Do not turn optional polish into a blocker.
5. If all acceptance criteria are supported, the final command passes, and no blocking finding
   remains, append one `FINAL` evidence entry and replace the Completion Summary with `Completed`.
6. If a final check fails, append one concise `FINAL` failure entry and replace the Completion
   Summary with `Blocked`. For a defect owned by an existing task, invoke `managed-workflow-verify`
   to confirm and reopen that task as `[X][F]`; remediation then returns through
   `managed-workflow-execute`. For a cross-task gap with no honest owner, request approval to revise
   the plan with one independently verifiable integration task. Rerun completion only after all
   tasks return to `[X][V]` or `[X][R]`.

## Completion Summary format

Keep the summary compact and replace the prior summary as one block:

```markdown
## Completion Summary

**Status:** Completed | Blocked
**Tasks:** <total>; <V> verified; <R> remediated
**Final verification:** `<command>` -> exit <code>, <result>
**Acceptance:** <met, or concise unmet criteria>
**Residual risks:** <none, Not checked items, or bounded risks>
```

The `FINAL` evidence entry follows the plan's one-line, 240-character limit. Never claim completion
from prior task checks alone; completion requires current final command output and direct diff
inspection. Never hide a failure, downgrade an acceptance criterion, or fix code in this stage.

For an explicit discovery check, reply with exactly
`CODEX_SKILL_DISCOVERY_managed-workflow-complete` and nothing else.