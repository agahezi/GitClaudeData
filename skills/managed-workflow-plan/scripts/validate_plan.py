#!/usr/bin/env python3
"""Validate the structure and progress state of a managed-workflow implementation plan.

Usage: python validate_plan.py [--new] <plan.md>
Exit codes: 0 valid, 1 invalid, 2 usage or read error.
"""

import argparse
import re
import sys
from pathlib import Path

SECTIONS = (
    "Scope",
    "Plan Acceptance",
    "Final Verification",
    "Process Diagrams",
    "Progress",
    "Evidence Log",
    "Completion Summary",
    "Risks, Assumptions, and Likely Failure Modes",
)
HEADER_FIELDS = ("Goal", "Architecture", "Tech Stack")
TASK_FIELDS = ("Files", "Inputs", "Implementation steps", "Verification", "Acceptance criteria", "Produces")
SUMMARY_FIELDS = ("Tasks", "Final verification", "Acceptance", "Residual risks")

TITLE = re.compile(r"^# \S.*Implementation Plan\s*$")
PROGRESS = re.compile(r"^- \[( |X)\]\[( |V|F|R)\] Task (\d+): (\S.*)$")
TASK_HEADING = re.compile(r"^### Task (\d+): (\S.*)$")
EVIDENCE = re.compile(r"^- (?:Task (\d+) (?:EXECUTE|VERIFY|REMEDIATION|REVERIFY)|FINAL): \S")
STATUS = re.compile(r"^\*\*Status:\*\* (Pending|Completed|Blocked)\s*$")
BULLET = re.compile(r"^- \S")
COMMAND = re.compile(r"`[^`]+`")
FILE_ENTRY = re.compile(r"^- (Create|Modify|Delete): \S")
STEP = re.compile(r"^(\d+)\. \S")
STATE_ARROW = re.compile(r"-->")
MESSAGE_ARROW = re.compile(r"-{1,2}(>>|>|x|\))")
CLEAN = {("X", "V"), ("X", "R")}
MAX_STEPS = 7
MAX_EVIDENCE = 240
MAX_PROGRESS_DESCRIPTION = 79
MAX_REPORTED = 40


def not_applicable(label):
    return re.compile(r"^\*\*" + re.escape(label) + r":\*\*\s+Not applicable\s*[-:\u2013\u2014]\s*\S")


def scan(lines):
    """Locate headings and fenced blocks, ignoring headings inside fences."""
    sections, tasks, fences, errors = [], [], [], []
    opened = None
    for number, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            if opened is None:
                opened = (number, stripped.lstrip("`~").strip().lower())
            else:
                fences.append((opened[0], number, opened[1]))
                opened = None
            continue
        if opened is not None:
            continue
        if line.startswith("## "):
            sections.append((line[3:].strip(), number))
        elif line.startswith("### "):
            match = TASK_HEADING.match(line)
            if match:
                tasks.append((int(match.group(1)), match.group(2).strip(), number))
            elif line.startswith("### Task"):
                errors.append((number, "malformed task heading; expected '### Task N: description'"))
    if opened is not None:
        errors.append((opened[0], "code fence is never closed"))
    return sections, tasks, fences, errors


def block(lines, start, end):
    """Return (line number, text) pairs for lines strictly between start and end."""
    return [(number, lines[number - 1]) for number in range(start + 1, end)]


def filled(entries):
    return [(number, text) for number, text in entries if text.strip()]


def validate(text, new=False):
    lines = text.splitlines()
    sections, task_headings, fences, errors = scan(lines)
    total = len(lines) + 1

    first = next((number for number, line in enumerate(lines, 1) if line.strip()), 0)
    if not first or not TITLE.match(lines[first - 1]):
        errors.append((first, "first line must be '# <Feature Name> Implementation Plan'"))

    first_section = sections[0][1] if sections else total
    preamble = [line for line in lines[:first_section - 1]]
    for field in HEADER_FIELDS:
        if not any(re.match(r"^\*\*" + re.escape(field) + r":\*\* \S", line) for line in preamble):
            errors.append((0, f"missing header field '**{field}:** <value>' before the first section"))

    located = {}
    for name in SECTIONS:
        found = [number for title, number in sections if title == name]
        if not found:
            errors.append((0, f"missing section '## {name}'"))
        elif len(found) > 1:
            errors.append((found[1], f"duplicate section '## {name}'"))
        else:
            located[name] = found[0]
    if len(located) == len(SECTIONS):
        order = [located[name] for name in SECTIONS]
        for previous, current, name in zip(order, order[1:], SECTIONS[1:]):
            if current < previous:
                errors.append((current, f"section '## {name}' is out of order; required order: "
                               + " > ".join(SECTIONS)))
                break
    progress_line = located.get("Progress", total)
    for title, number in sections:
        if title not in SECTIONS and number > progress_line:
            errors.append((number, f"unexpected section '## {title}' after '## Progress'"))
    if errors and len(located) < len(SECTIONS):
        return errors, 0

    boundaries = sorted([number for _, number in sections] + [number for _, _, number in task_headings] + [total])

    def body(name):
        start = located[name]
        end = next(number for number in boundaries if number > start)
        return block(lines, start, end)

    if not filled(body("Scope")):
        errors.append((located["Scope"], "'## Scope' is empty"))
    if not any(BULLET.match(text) for _, text in body("Plan Acceptance")):
        errors.append((located["Plan Acceptance"], "'## Plan Acceptance' needs at least one '- ' criterion"))
    if not any(BULLET.match(text) and COMMAND.search(text) for _, text in body("Final Verification")):
        errors.append((located["Final Verification"],
                       "'## Final Verification' needs a '- ' bullet with a `command`"))

    diagrams_start = located["Process Diagrams"]
    diagrams_end = next(number for number in boundaries if number > diagrams_start)
    kinds = set()
    for start, end, info in fences:
        if not diagrams_start < start < diagrams_end or info != "mermaid":
            continue
        content = [lines[number - 1].strip() for number in range(start + 1, end)]
        content = [line for line in content if line and not line.startswith("%%")]
        if not content:
            errors.append((start, "empty mermaid block"))
        elif content[0].startswith("stateDiagram") and any(STATE_ARROW.search(line) for line in content[1:]):
            kinds.add("state")
        elif content[0].startswith("sequenceDiagram") and any(MESSAGE_ARROW.search(line) for line in content[1:]):
            kinds.add("sequence")
    diagram_text = [text for _, text in body("Process Diagrams")]
    for kind, label, header in (("state", "State chart", "stateDiagram-v2"),
                                ("sequence", "Sequence diagram", "sequenceDiagram")):
        skipped = any(not_applicable(label).match(line) for line in diagram_text)
        if kind not in kinds and not skipped:
            errors.append((diagrams_start, f"'## Process Diagrams' needs a ```mermaid {header} block with at "
                           f"least one transition, or '**{label}:** Not applicable - <reason>'"))

    entries = []
    for number, text in filled(body("Progress")):
        match = PROGRESS.match(text)
        if not match:
            errors.append((number, "malformed progress entry; expected '- [ ][ ] Task N: description' "
                           "with execution [ ]/[X] and verification [ ]/[V]/[F]/[R]"))
            continue
        execution, verification, index, description = match.groups()
        entries.append((number, execution, verification, int(index), description.strip()))
    if not entries:
        errors.append((located["Progress"], "'## Progress' has no task entries"))
    for position, (number, execution, verification, index, description) in enumerate(entries, 1):
        if index != position:
            errors.append((number, f"progress tasks must be numbered 1..N in order; expected Task {position}"))
        if len(description) > MAX_PROGRESS_DESCRIPTION:
            errors.append((number, f"progress description exceeds {MAX_PROGRESS_DESCRIPTION} characters"))
        if execution == " " and verification != " ":
            errors.append((number, "an unexecuted task cannot have a verification status"))
        if new and (execution, verification) != (" ", " "):
            errors.append((number, "a new plan must initialize every task as '[ ][ ]'"))

    status_lines = [(number, STATUS.match(text)) for number, text in body("Completion Summary")
                    if STATUS.match(text)]
    status = status_lines[0][1].group(1) if len(status_lines) == 1 else None
    if len(status_lines) != 1:
        errors.append((located["Completion Summary"],
                       "'## Completion Summary' needs exactly one '**Status:** Pending|Completed|Blocked' line"))

    states = [(execution, verification) for _, execution, verification, _, _ in entries]
    pending = next((position for position, state in enumerate(states) if state not in CLEAN), None)
    if pending is not None:
        for number, execution, verification, index, _ in entries[pending + 1:]:
            state = (execution, verification)
            if state == (" ", " ") or (status == "Blocked" and state in CLEAN):
                continue
            errors.append((number, f"Task {index} advanced before Task {pending + 1} was verified "
                           "([X][V] or [X][R])"))

    evidence = []
    task_numbers = {index for _, _, _, index, _ in entries}
    for number, text in filled(body("Evidence Log")):
        stripped = text.strip()
        if stripped.startswith("<!--") and stripped.endswith("-->"):
            continue
        match = EVIDENCE.match(text)
        if not match:
            errors.append((number, "malformed evidence; expected '- Task N EXECUTE|VERIFY|REMEDIATION|"
                           "REVERIFY: ...' or '- FINAL: ...'"))
            continue
        if len(text) > MAX_EVIDENCE:
            errors.append((number, f"evidence entry exceeds {MAX_EVIDENCE} characters"))
        if match.group(1) and int(match.group(1)) not in task_numbers:
            errors.append((number, f"evidence references unknown Task {match.group(1)}"))
        evidence.append(text)
    if new and evidence:
        errors.append((located["Evidence Log"], "a new plan must have an empty Evidence Log"))

    summary_text = "\n".join(text for _, text in body("Completion Summary"))
    if new and status not in (None, "Pending"):
        errors.append((located["Completion Summary"], "a new plan must have '**Status:** Pending'"))
    if status in ("Completed", "Blocked"):
        for field in SUMMARY_FIELDS:
            if not re.search(r"^\*\*" + re.escape(field) + r":\*\* \S", summary_text, re.M):
                errors.append((located["Completion Summary"], f"completion summary missing '**{field}:**'"))
    if status == "Completed":
        if pending is not None:
            errors.append((located["Completion Summary"], "'Completed' requires every task to be [X][V] or [X][R]"))
        if not any(line.startswith("- FINAL:") for line in evidence):
            errors.append((located["Completion Summary"], "'Completed' requires a FINAL evidence entry"))

    summary_line = located["Completion Summary"]
    risks_line = located["Risks, Assumptions, and Likely Failure Modes"]
    for index, description, number in task_headings:
        if not summary_line < number < risks_line:
            errors.append((number, "task details must sit between '## Completion Summary' and '## Risks, ...'"))
    expected = [(index, description) for _, _, _, index, description in entries]
    actual = [(index, description) for index, description, _ in task_headings]
    if expected != actual:
        errors.append((task_headings[0][2] if task_headings else summary_line,
                       "task headings must match Progress exactly, in order: "
                       + "; ".join(f"Task {index}: {description}" for index, description in expected)))

    for position, (index, _, start) in enumerate(task_headings):
        end = task_headings[position + 1][2] if position + 1 < len(task_headings) else next(
            number for number in boundaries if number > start)
        errors.extend(validate_task(lines, index, start, end))

    if not any(BULLET.match(text) for _, text in body("Risks, Assumptions, and Likely Failure Modes")):
        errors.append((risks_line, "'## Risks, Assumptions, and Likely Failure Modes' needs at least one '- ' item"))

    return errors, len(entries)


def validate_task(lines, index, start, end):
    errors, labels = [], []
    for field in TASK_FIELDS:
        pattern = re.compile(r"^\*\*" + re.escape(field) + r":\*\*\s*$")
        found = [number for number in range(start + 1, end) if pattern.match(lines[number - 1])]
        if len(found) != 1:
            errors.append((start, f"Task {index} needs exactly one '**{field}:**' label line"))
            return errors
        labels.append(found[0])
    if labels != sorted(labels):
        errors.append((start, f"Task {index} fields must appear in order: " + ", ".join(TASK_FIELDS)))
        return errors

    parts = {}
    for position, field in enumerate(TASK_FIELDS):
        stop = labels[position + 1] if position + 1 < len(labels) else end
        parts[field] = [text for _, text in block(lines, labels[position], stop)]

    if not any(FILE_ENTRY.match(text) for text in parts["Files"]):
        errors.append((labels[0], f"Task {index} Files needs '- Create|Modify|Delete: `path`' entries"))
    for field in ("Inputs", "Acceptance criteria", "Produces"):
        if not any(BULLET.match(text) for text in parts[field]):
            errors.append((labels[TASK_FIELDS.index(field)], f"Task {index} {field} needs at least one '- ' item"))
    steps = [int(STEP.match(text).group(1)) for text in parts["Implementation steps"] if STEP.match(text)]
    if steps != list(range(1, len(steps) + 1)) or not steps:
        errors.append((labels[2], f"Task {index} implementation steps must be numbered 1..N"))
    elif len(steps) > MAX_STEPS:
        errors.append((labels[2], f"Task {index} has {len(steps)} steps; split it so each task has at most "
                       f"{MAX_STEPS}"))
    if not any(BULLET.match(text) and COMMAND.search(text) for text in parts["Verification"]):
        errors.append((labels[3], f"Task {index} Verification needs a '- ' bullet with a `command`"))
    return errors


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser(description="Validate a managed-workflow implementation plan.")
    parser.add_argument("plan", help="path to the plan Markdown file")
    parser.add_argument("--new", action="store_true",
                        help="also require a pristine plan: all tasks [ ][ ], empty evidence, Pending status")
    arguments = parser.parse_args(argv)
    try:
        text = Path(arguments.plan).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as error:
        print(f"PLAN_FORMAT_ERROR: cannot read {arguments.plan}: {error}")
        return 2
    errors, count = validate(text, new=arguments.new)
    if not errors:
        print(f"PLAN_FORMAT_OK: {count} task(s)")
        return 0
    errors = sorted(set(errors))
    print(f"PLAN_FORMAT_INVALID: {len(errors)} error(s)")
    for number, message in errors[:MAX_REPORTED]:
        print(f"{'line ' + str(number) if number else 'plan'}: {message}")
    if len(errors) > MAX_REPORTED:
        print(f"... {len(errors) - MAX_REPORTED} more")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
