---
name: managed-workflow-verify
description: Use after one managed-plan task is executed to independently verify its scope, behavior, tests, and acceptance criteria before later work begins.
---

# Managed workflow verify

Verify independently and skeptically. Do not modify implementation files or Git metadata. The only
permitted repository edits are the selected task's second checkbox and one append-only `VERIFY` or
`REVERIFY` entry in the plan's Evidence Log. Do not commit.

The workflow order is mandatory:

`PLAN -> EXECUTE one task -> test -> VERIFY that task -> next task`

Verification is a task-scoped quality gate, not a broad rediscovery exercise. Start with the changed
contract, task diff, executor's reported test evidence, and current repository state. Run only
non-mutating checks permitted by the environment.

## Plan format gate

Validate the plan with `<skills-root>/managed-workflow-plan/scripts/validate_plan.py <plan-path>`,
where `<skills-root>` is the folder that contains this skill's folder, using Python 3 (`python3`, or
`python` where it is Python 3). Run it before verifying: on `PLAN_FORMAT_INVALID`, stop without
editing and report the errors. Run it again after your checkbox and evidence edit; on failure,
correct only that edit. If the validator is missing, stop and report an incomplete installation.

## Context discipline

Read the plan's goal, scope, global constraints, Progress section, selected task, its `Inputs`, and
its `Produces`. Read only that task's Evidence Log entries. Read predecessor details only when the
selected task consumes their contract. Inspect the task's changed files, nearest tests, and direct
callers where the contract requires them. Do not reread unrelated tasks, conversation history, or
the entire repository.

Treat executor evidence as a starting point, not proof. Run the task's focused verification against
the current files unless the environment makes execution unavailable. Rerun a broader suite only
when its earlier result is missing, stale after later edits, or insufficient for a concrete shared-
code or integration risk. Keep passing output to command, exit code, and pass count; retain enough
failure output to support a finding.

## Progress ownership

The verifier may change only the second column:

- `[X][ ]` to `[X][V]` when the first verification is clean;
- `[X][ ]` to `[X][F]` when verification finds defects;
- `[X][F]` to `[X][R]` when remediation is re-verified clean; or
- `[X][F]` remains `[X][F]` when defects remain;
- `[X][V]` or `[X][R]` to `[X][F]` only when `managed-workflow-complete` supplies a current,
  confirmed final-check failure owned by that task.

Never modify the first column. Do not verify an unexecuted `[ ][ ]` task.

The verifier may append only its own `VERIFY` or `REVERIFY` evidence entry. Never edit prior evidence
or the Completion Summary. Update the checkbox and append evidence in the same repository edit.

## Verification flow

1. Resolve the plan and selected task. If no task is selected, choose the earliest `[X][ ]` or
   `[X][F]` entry. When completion requests reopening, verify the named task and supplied final-check
   evidence rather than selecting another task.
2. Confirm the task is executed and every earlier task is `[X][V]` or `[X][R]`. Do not verify an
   out-of-order task.
3. Apply the context discipline. Compare the implementation with every acceptance criterion and the
   declared `Produces` contract. Check that changes remain within approved files and behavior; flag
   scope growth or unrelated refactoring.
4. Inspect the relevant diff, controlling code, focused tests, and direct contract boundaries. Run
   the focused verification and compare actual output with the plan's expected result.
5. Review correctness, negative and boundary behavior, safety, unintended effects, test quality,
   maintainability, and whether the task remained independently verifiable. Missing behavior,
   assertions that do not prove it, or reliance on a later task are defects.
6. Classify results precisely:
   - **Verified:** direct inspection or current command output proves the claim.
   - **Indication:** evidence suggests a concern but is insufficient to call it a defect.
   - **Not checked:** the environment or scope prevented the check.
7. Report confirmed findings in severity order: BLOCKER, HIGH, MEDIUM, LOW. Every finding includes
   a file and line reference, impact, evidence, and bounded remediation. Do not inflate uncertain
   indications into findings.
8. Update only the selected task's second checkbox according to the verified result and append one
   evidence entry in the same repository edit. For `[F]`, record the highest severity, concise
   finding, and file reference. For `[V]` or `[R]`, record the focused command, exit code, pass count,
   and residual risk. Follow the plan's one-line format and 240-character limit.

When there are no findings, report the inspected contract, focused command, exit code, pass count,
and any residual `Not checked` risk concisely. Never fix defects during verification; return an `[F]`
task to the executor for remediation. Re-verification after remediation is scoped to the original
findings, the fix diff, and regression risk introduced by that fix. Recheck every original finding,
including any the executor did not claim to address; do not repeat broad discovery.

For an explicit discovery check, reply with exactly
`CODEX_SKILL_DISCOVERY_managed-workflow-verify` and nothing else.
