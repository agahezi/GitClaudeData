---
name: managed-workflow-execute
description: Execute an approved implementation plan safely, test the result, and leave commits to the user.
---

# Managed workflow execute

Use workspace-write only when implementation has been explicitly approved. Read the approved
plan and repository instructions, confirm its file boundary, and implement the ordered steps.
Stay within approved files; stop and report the blocker when required work would exceed scope or
needs authority that was not granted.

Prefer tests that demonstrate the requested behavior, including negative and boundary cases.
For bug fixes and behavior changes, write or update the test first and confirm it fails for the
expected reason before implementing.
Run the relevant tests and then the appropriate broader suite. After the final edit, rerun the
relevant tests and check the exit code and failure count before reporting. Check each acceptance
criterion from the plan and report whether the evidence shows it is met. Report actual commands
and real output summaries. Never fabricate a successful result, hide a failure, or describe an
indication as verified. Do not assume particular tool names or external workflow dependencies.

Do not commit, amend, tag, push, or otherwise alter repository history. Summarize changed files,
test evidence, blockers, and remaining risks so the user can review and commit manually.

For an explicit discovery check, reply with exactly
`CODEX_SKILL_DISCOVERY_managed-workflow-execute` and nothing else.
