---
name: managed-workflow-verify
description: Skeptically verify one executed managed-plan task and update only its verification checkbox.
---

# Managed workflow verify

<<<<<<< HEAD
Work in a read-only sandbox and do not modify files or Git metadata. Inspect the requested diff,
the surrounding code, repository instructions, and relevant tests. Run only non-mutating tests
that are permitted in the review environment.
Start with the changed contracts and the implementation's test evidence. Independently assess
whether the evidence is current and covers the risks; run focused checks for gaps or changed
conditions, and rerun a broader suite only when its prior result is missing, stale, or insufficient
for the risk. Do not claim unrun checks as independently verified.
=======
Verify independently and skeptically. Do not modify implementation files or Git metadata. The only
permitted repository edit is the selected task's second checkbox in the plan's `## Progress`
section. Do not commit.
>>>>>>> f9c362eebb040ba3be441cc89ceb4ec77696fad0

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
