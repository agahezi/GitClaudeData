---
name: managed-workflow-plan
description: Inspect a repository without mutation and produce a concrete, reviewable implementation plan.
---

# Managed workflow plan

Work in a read-only sandbox. Inspect the request, repository instructions, relevant source,
tests, and current Git state without changing repository files or Git metadata. If the user asks
only for planning, make no repository mutation.

If the request is ambiguous in a way that would change the plan, ask the clarifying questions
first. When more than one reasonable approach exists, briefly note the alternatives and why you
chose this one.

Return a concrete plan containing:

- the goal and explicit scope;
- exact files expected to change;
- ordered implementation steps;
- tests and other verification commands;
- risks, assumptions, and likely failure modes; and
- measurable acceptance criteria.

For each step, identify the focused tests that demonstrate its behavior, including relevant
negative and boundary cases. Specify when a broader suite is warranted (such as after changes
to shared code or at integration) and which acceptance criteria it covers. Do not schedule the
same broad suite after every step without a change that justifies rerunning it.

Use capability-oriented language and do not assume particular tool names. Label unproven
observations as indications, reserve findings for evidence-backed issues, and call results
verified only when supported by real command output. Do not commit. The user reviews the plan
and manually commits any later implementation.

For an explicit discovery check, reply with exactly
`CODEX_SKILL_DISCOVERY_managed-workflow-plan` and nothing else.
