---
name: managed-workflow-verify
description: Perform skeptical read-only verification with severity-ordered, evidence-backed findings.
---

# Managed workflow verify

Work in a read-only sandbox and do not modify files or Git metadata. Inspect the requested diff,
the surrounding code, repository instructions, and relevant tests. Run only non-mutating tests
that are permitted in the review environment.

Review independently and skeptically:

1. correctness and contract behavior, including negative and boundary cases;
2. safety, path boundaries, permissions, failure cleanup, and unintended side effects;
3. test quality, looking for missing coverage, tautological assertions, and tests that do not
   prove their stated claims; and
4. maintainability, including unnecessary complexity and hidden dependencies.

Order findings by severity: BLOCKER, HIGH, MEDIUM, then LOW. Every finding must include a file
and line reference, impact, evidence, and a bounded remediation. Distinguish confirmed findings
from indications that need more evidence. Call a result verified only when real test output or
direct inspection proves it. If there are no findings, say so and list the checks and actual test
results that support the conclusion. Do not fix issues during review and do not commit; the user
reviews and commits manually.

For an explicit discovery check, reply with exactly
`CODEX_SKILL_DISCOVERY_managed-workflow-verify` and nothing else.
