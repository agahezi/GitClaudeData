---
name: managed-workflow-verify
description: Skeptically verify one executed managed-plan task and update only its verification checkbox.
---

# Managed workflow verify

Verify independently and skeptically. Do not modify implementation files or Git metadata. The only
permitted repository edit is the selected task's second checkbox in the plan's `## Progress`
section. Do not commit.

## Progress ownership

The verifier may change only the second column:

- `[X][ ]` to `[X][V]` when the first verification is clean;
- `[X][ ]` to `[X][F]` when verification finds defects;
- `[X][F]` to `[X][R]` when remediation is re-verified clean; or
- `[X][F]` remains `[X][F]` when defects remain.

Never modify the first column. Do not verify an unexecuted `[ ][ ]` task.

## Verification flow

1. Resolve the plan and selected task. If no task is selected, choose the earliest `[X][ ]` or
   `[X][F]` entry.
2. Read its detailed scope, files, verification commands, and acceptance criteria.
3. Inspect the relevant diff and surrounding code. Run permitted non-mutating tests.
4. Review correctness, negative and boundary behavior, safety, unintended effects, test quality,
   and maintainability.
5. Report findings in severity order: BLOCKER, HIGH, MEDIUM, LOW. Every finding includes a file and
   line reference, impact, evidence, and bounded remediation.
6. Update only the selected task's second checkbox according to the verified result.

Distinguish confirmed findings from indications needing evidence. Call a result verified only when
real test output or direct inspection proves it. When there are no findings, list the checks and
actual test results supporting the clean result. Never fix defects during verification; return an
`[F]` task to the executor for remediation.

For an explicit discovery check, reply with exactly
`CODEX_SKILL_DISCOVERY_managed-workflow-verify` and nothing else.
