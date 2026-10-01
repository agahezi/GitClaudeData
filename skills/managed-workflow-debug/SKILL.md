---
name: managed-workflow-debug
description: Use inside an approved managed-workflow task when a check fails unexpectedly, a defect is intermittent, or a verifier finding needs root-cause isolation before remediation.
---

# Managed workflow debug

Find the root cause of one observed failure, prove it with a discriminating check, and return the
smallest verified correction to `managed-workflow-execute`. An expected RED test written before a
behavior change is not a debugging incident.

This skill inherits the selected task's scope and approval. It may change implementation or test
files only after evidence identifies the cause and only within the task's approved files. It never
changes Progress, Evidence Log, Completion Summary, commits, or Git history. The executor owns the
eventual state transition and evidence entry.

## Context budget

Read the failing command and relevant output, the selected task, its task-specific evidence, the
changed contract, and the nearest controlling code. Do not load the full conversation, unrelated
tasks, broad logs, or the whole repository. Extract only output lines that distinguish hypotheses.

Investigate one falsifiable hypothesis at a time. Prefer the cheapest check that can prove it wrong.
Do not make speculative fixes, stack several guesses into one edit, or rerun an unchanged command
without new evidence.

## Debugging flow

1. **Capture the symptom.** Record the exact command, observed result, expected result, and the
   smallest relevant error excerpt. Confirm whether the failure is deterministic. For intermittent
   behavior, establish a bounded reproduction that exposes frequency or triggering conditions.
2. **Reproduce narrowly.** Run the smallest existing test or probe that demonstrates the failure.
   If it does not reproduce, check environment and test assumptions before reading more code.
3. **Trace to the controlling boundary.** Follow the incorrect value or state backward through direct
   callers and interfaces until locating the first boundary where actual and expected behavior
   diverge. Distinguish cause from downstream symptoms.
4. **State one hypothesis.** Name the suspected cause, the evidence supporting it, and one cheap
   result that would falsify it.
5. **Run the discriminating check.** If falsified, discard the hypothesis and form the next one from
   the new evidence. If supported, demonstrate why the identified boundary controls the symptom.
6. **Correct minimally.** Add or retain a focused regression test that fails for the demonstrated
   cause, make the smallest in-scope correction, and run that test to green. Avoid unrelated cleanup.
7. **Check collateral risk.** Run the task's focused verification and only the broader check justified
   by the changed boundary. Read the exit code and failure count.
8. **Return evidence.** Report root cause, changed files, regression test, commands, exit codes,
   concise results, and residual risk. The executor decides whether acceptance criteria are met and
   writes the plan evidence.

## Escalation

Stop and return control to the executor when reproduction requires unavailable credentials or an
unsafe external side effect, when evidence points outside approved files, when observability is
insufficient to distinguish causes, or when a correction changes the approved design. State the
missing evidence or smallest scope revision needed. Never weaken a test to hide the symptom.

For an explicit discovery check, reply with exactly
`CODEX_SKILL_DISCOVERY_managed-workflow-debug` and nothing else.