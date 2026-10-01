#!/usr/bin/env python3
"""Live, explicit Codex compatibility gates using only temporary Git repositories."""

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills"
SKILLS = (
    "managed-workflow-plan",
    "managed-workflow-execute",
    "managed-workflow-verify",
    "managed-workflow-debug",
    "managed-workflow-complete",
)


def snapshot(repo):
    result = {}
    for path in sorted(repo.rglob("*")):
        relative = path.relative_to(repo)
        if ".git" in relative.parts or not path.is_file():
            continue
        result[relative.as_posix()] = (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mode & 0o111)
    return result


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)


def fixture(base, name, skills):
    repo = base / name
    repo.mkdir()
    initialized = git(repo, "init", "--quiet")
    if initialized.returncode:
        raise RuntimeError(initialized.stdout)
    for skill in skills:
        destination = repo / ".agents/skills" / skill
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(SKILL_ROOT / skill, destination)
    return repo


def codex(repo, base, label, prompt, sandbox):
    output = base / f"{label}.txt"
    command = [
        "codex", "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
        "--sandbox", sandbox, "--cd", str(repo), "--output-last-message", str(output),
        "-c", "sandbox_workspace_write.network_access=false", prompt,
    ]
    process = subprocess.run(
        command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, check=False,
    )
    message = output.read_text(encoding="utf-8") if output.exists() else ""
    return process, message


def require(condition, detail):
    if not condition:
        raise AssertionError(detail)


def evidence_lines(plan_text):
    section = plan_text.split("## Evidence Log", 1)[1].split("## Completion Summary", 1)[0]
    return [line for line in section.splitlines() if line.startswith("- ")]


def require_evidence_append_only(before, after):
    previous = evidence_lines(before)
    current = evidence_lines(after)
    position = 0
    for line in previous:
        try:
            position = current.index(line, position) + 1
        except ValueError as error:
            raise AssertionError(f"prior evidence changed or was deleted: {line}") from error
    require(all(len(line) <= 240 for line in current), f"evidence exceeds 240 characters: {current}")


def require_completion_summary(plan_text, status):
    summary = plan_text.split("## Completion Summary", 1)[1]
    for field in ("**Status:**", "**Tasks:**", "**Final verification:**", "**Acceptance:**",
                  "**Residual risks:**"):
        require(field in summary, f"completion summary missing {field}: {summary}")
    require(f"**Status:** {status}" in summary, f"expected completion status {status}: {summary}")


def build_plan(title, goal, scope, acceptance, task, state, evidence=(), status="Pending"):
    steps = "\n".join(f"{number}. {step}" for number, step in enumerate(task["steps"], 1))
    files = "\n".join(f"- Modify: `{path}`" for path in task["files"])
    log = "\n".join(evidence) or "<!-- Append-only. One concise line per state transition. -->"
    return (
        f"# {title} Implementation Plan\n\n"
        f"**Goal:** {goal}\n**Architecture:** Keep the existing function boundary.\n"
        "**Tech Stack:** Python unittest\n\n"
        f"## Scope\n\n{scope}\n\n"
        f"## Plan Acceptance\n\n- {acceptance}\n\n"
        "## Final Verification\n\n- `python -m unittest -v` covers the complete behavior.\n\n"
        "## Process Diagrams\n\n"
        "**State chart:** Not applicable - a stateless single-function change\n\n"
        "**Sequence diagram:** Not applicable - one caller and one function\n\n"
        f"## Progress\n\n- {state} Task 1: {task['description']}\n\n"
        f"## Evidence Log\n\n{log}\n\n"
        f"## Completion Summary\n\n**Status:** {status}\n\n---\n\n"
        f"### Task 1: {task['description']}\n\n"
        f"**Files:**\n\n{files}\n\n"
        f"**Inputs:**\n\n- {task['inputs']}\n\n"
        f"**Implementation steps:**\n\n{steps}\n\n"
        "**Verification:**\n\n- `python -m unittest -v`\n\n"
        f"**Acceptance criteria:**\n\n- {acceptance}\n\n"
        f"**Produces:**\n\n- {task['produces']}\n\n"
        "## Risks, Assumptions, and Likely Failure Modes\n\n- Operands are valid Python values.\n"
    )


def fixture_plans():
    steps = ["Run the focused test and confirm the expected failure.", "Make the smallest correction.",
             "Run the focused test and check the result."]

    def task(description, files, inputs, produces):
        return {"description": description, "files": files, "inputs": inputs, "steps": steps,
                "produces": produces}

    return {
        "calculator": build_plan(
            "Calculator", "Implement arithmetic addition.", "Modify only calculator.py and managed plan state.",
            "`add(2, 3)` returns `5`.",
            task("Implement addition", ["calculator.py"], "Existing `add(left, right)` function",
                 "Working arithmetic addition through `add`."), "[ ][ ]"),
        "pricing": build_plan(
            "Pricing", "Apply percentage discounts.", "Modify only pricing.py, its test, and plan state.",
            "A 20 percent discount on 100 returns 80.",
            task("Apply discounts", ["pricing.py", "test_pricing.py"], "Numeric price and percentage",
                 "Correct `discount` behavior."), "[X][ ]",
            ["- Task 1 EXECUTE: `python -m py_compile pricing.py` -> exit 0; reported complete"]),
        "normalizer": build_plan(
            "Normalizer", "Trim and lowercase text values.", "Modify only normalizer.py and plan state.",
            "`normalize('  Mixed  ')` returns `'mixed'`.",
            task("Normalize values", ["normalizer.py"], "String values", "Normalized text through `normalize`."),
            "[X][F]", ["- Task 1 VERIFY: HIGH at `normalizer.py:2`; case normalization missing; [F]"]),
        "blocked": build_plan(
            "Blocked", "Correct application behavior.", "Modify only app.py and plan state.",
            "The application behavior is correct.",
            task("Broken behavior", ["app.py"], "Existing application entry point", "Correct behavior."),
            "[X][F]", ["- Task 1 VERIFY: HIGH at `app.py:1`; behavior incorrect; [F]"]),
        "math": build_plan(
            "Math Remediation", "Implement subtraction.", "Modify math_ops.py and managed plan state.",
            "`subtract(7, 2)` returns `5`.",
            task("Implement subtraction", ["math_ops.py"], "Numeric operands", "Correct subtraction behavior."),
            "[X][F]", ["- Task 1 EXECUTE: `python -m py_compile math_ops.py` -> exit 0; syntax accepted",
                       "- Task 1 VERIFY: `python -m unittest -v` -> exit 1, 1 failed; HIGH at `math_ops.py:2`; [F]"]),
    }


def require_valid_plan(repo, plan, new=False):
    validator = repo / ".agents/skills/managed-workflow-plan/scripts/validate_plan.py"
    command = [sys.executable, "-B", str(validator)] + (["--new"] if new else []) + [str(plan)]
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0, f"plan format invalid: {result.stdout}")


def discovery_gate(base, skill):
    repo = fixture(base, "discover-" + skill, [skill])
    sentinel = "CODEX_SKILL_DISCOVERY_" + skill
    process, message = codex(
        repo, base, "discover-" + skill,
        f"Explicitly use ${skill}. Perform its explicit discovery check now.",
        "read-only",
    )
    require(process.returncode == 0, process.stdout)
    require(message.strip() == sentinel, f"expected exact {sentinel!r}, got {message!r}")
    return sentinel


def plan_gate(base):
    repo = fixture(base, "plan", ["managed-workflow-plan"])
    (repo / "app.py").write_text("def greet(name):\n    return name\n", encoding="utf-8")
    before, head_before = snapshot(repo), git(repo, "rev-parse", "--verify", "HEAD").returncode
    process, message = codex(
        repo, base, "plan",
        "Use $managed-workflow-plan to plan adding validated title-case greeting output to app.py. "
        "Do not modify anything.",
        "read-only",
    )
    require(process.returncode == 0, process.stdout)
    lowered = message.lower()
    require("superpowers" not in lowered and "missing dependency" not in lowered,
            f"planner still requires external dependency: {message}")
    require("design" in lowered and "test" in lowered, f"design or test approach missing: {message}")
    require("approv" in lowered or "confirm" in lowered, f"design approval not requested: {message}")
    require("## progress" not in lowered and "**implementation steps:**" not in lowered,
            f"implementation plan drafted before design approval: {message}")
    require(snapshot(repo) == before, "plan mutated repository")
    require(git(repo, "rev-parse", "--verify", "HEAD").returncode == head_before != 0, "plan created commit")
    return "standalone design and approval requested; read-only; no commit"


def plan_write_gate(base):
    repo = fixture(base, "plan-write", ["managed-workflow-plan"])
    (repo / "app.py").write_text("def greet(name):\n    return name\n", encoding="utf-8")
    before = snapshot(repo)
    process, message = codex(
        repo, base, "plan-write",
        "Use $managed-workflow-plan. The bounded design is approved: greet(name) in app.py returns "
        "'Hello, <Name>!' with the name stripped and title-cased, and raises ValueError for a blank name; "
        "prove it with a new unittest file. Write the implementation plan under docs/plans/ now and "
        "validate its format. Do not implement or commit.",
        "workspace-write",
    )
    require(process.returncode == 0, process.stdout)
    after = snapshot(repo)
    changed = sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))
    plans = [path for path in changed if path.endswith("-plan.md")]
    require(len(plans) == 1 and all(path.startswith("docs/plans/") for path in changed),
            f"planner changed unexpected files: {changed}")
    require_valid_plan(repo, repo / plans[0], new=True)
    require("PLAN_FORMAT_OK" in message, f"planner did not report the validator result: {message}")
    require(git(repo, "rev-parse", "--verify", "HEAD").returncode != 0, "planner created commit")
    return "approved design produced one plan that passes the format validator; no commit"


def execute_gate(base):
    repo = fixture(base, "execute", [
        "managed-workflow-plan",
        "managed-workflow-execute",
        "managed-workflow-verify",
        "managed-workflow-debug",
        "managed-workflow-complete",
    ])
    source = repo / "calculator.py"
    source.write_text("def add(left, right):\n    raise NotImplementedError\n", encoding="utf-8")
    test = repo / "test_calculator.py"
    test.write_text(
        "import unittest\nfrom calculator import add\n\n"
        "class TestAdd(unittest.TestCase):\n"
        "    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n\n"
        "if __name__ == '__main__':\n    unittest.main()\n", encoding="utf-8")
    plan = repo / "docs" / "plans" / "calculator-plan.md"
    plan.parent.mkdir(parents=True)
    plan.write_text(fixture_plans()["calculator"], encoding="utf-8")
    plan_before = plan.read_text(encoding="utf-8")
    before = snapshot(repo)
    process, message = codex(
        repo, base, "execute",
        "Use $managed-workflow-execute to execute Task 1 from the approved "
        "docs/plans/calculator-plan.md, independently verify it, and complete the plan end to end. "
        "All managed workflow skills are installed. Do not commit.",
        "workspace-write",
    )
    require(process.returncode == 0, process.stdout)
    after = snapshot(repo)
    changed = {path for path in set(before) | set(after) if before.get(path) != after.get(path)}
    require(changed == {"calculator.py", "docs/plans/calculator-plan.md"},
            f"files outside approved scope changed: {sorted(changed)}")
    test_result = subprocess.run(
        [sys.executable, "-m", "unittest", "-v"], cwd=repo, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, check=False,
    )
    require(test_result.returncode == 0, test_result.stdout)
    plan_text = plan.read_text(encoding="utf-8")
    require("- [X][V] Task 1: Implement addition" in plan_text,
            f"task did not complete execution and verification gates: {plan_text}")
    for evidence in ("Task 1 EXECUTE:", "Task 1 VERIFY:", "- FINAL:"):
        require(evidence in plan_text, f"missing {evidence} evidence: {plan_text}")
    require_evidence_append_only(plan_before, plan_text)
    require_completion_summary(plan_text, "Completed")
    require_valid_plan(repo, plan)
    require(git(repo, "rev-parse", "--verify", "HEAD").returncode != 0, "execute created commit")
    require("pass" in message.lower() or "ok" in message.lower(), "execute omitted test result")
    return "approved files changed; evidence recorded; task reached [X][V]; plan completed; no commit"


def verify_gate(base):
    repo = fixture(base, "verify", ["managed-workflow-plan", "managed-workflow-verify"])
    defect = repo / "pricing.py"
    defect.write_text("def discount(price, percent):\n    return price + (price * percent / 100)\n", encoding="utf-8")
    test = repo / "test_pricing.py"
    test.write_text(
        "import unittest\nfrom pricing import discount\n\n"
        "class TestDiscount(unittest.TestCase):\n"
        "    def test_discount(self):\n        self.assertEqual(discount(100, 20), 80)\n\n"
        "if __name__ == '__main__':\n    unittest.main()\n", encoding="utf-8")
    plan = repo / "docs" / "plans" / "pricing-plan.md"
    plan.parent.mkdir(parents=True)
    plan.write_text(fixture_plans()["pricing"], encoding="utf-8")
    plan_before = plan.read_text(encoding="utf-8")
    before = snapshot(repo)
    process, message = codex(
        repo, base, "verify",
        "Use $managed-workflow-verify to verify Task 1 in docs/plans/pricing-plan.md. The known "
        "discount defect must be reported with severity and exact file:line evidence. Update only "
        "the verifier-owned plan state and evidence. Do not modify implementation files or commit.",
        "workspace-write",
    )
    require(process.returncode == 0, process.stdout)
    lowered = message.lower()
    require("pricing.py" in lowered and (":2" in lowered or "line 2" in lowered), message)
    require("high" in lowered or "blocker" in lowered, "missing severity")
    require("add" in lowered or "subtract" in lowered or "increase" in lowered, "known defect not identified")
    severities = [lowered.find(word) for word in ("blocker", "high", "medium", "low") if lowered.find(word) >= 0]
    require(severities == sorted(severities), "findings are not severity ordered")
    after = snapshot(repo)
    changed = {path for path in set(before) | set(after) if before.get(path) != after.get(path)}
    require(changed == {"docs/plans/pricing-plan.md"},
            f"verifier changed files outside its plan ownership: {sorted(changed)}")
    plan_text = plan.read_text(encoding="utf-8")
    require("- [X][F] Task 1: Apply discounts" in plan_text, f"task was not failed: {plan_text}")
    require("Task 1 VERIFY:" in plan_text, f"verification evidence missing: {plan_text}")
    require_evidence_append_only(plan_before, plan_text)
    require_valid_plan(repo, plan)
    require(git(repo, "rev-parse", "--verify", "HEAD").returncode != 0, "verify created commit")
    return "known defect found; only verifier plan state changed; task reached [X][F]; no commit"


def debug_gate(base):
    repo = fixture(base, "debug", ["managed-workflow-debug"])
    source = repo / "normalizer.py"
    source.write_text("def normalize(value):\n    return value.strip()\n", encoding="utf-8")
    test = repo / "test_normalizer.py"
    test.write_text(
        "import unittest\nfrom normalizer import normalize\n\n"
        "class TestNormalize(unittest.TestCase):\n"
        "    def test_normalize(self):\n        self.assertEqual(normalize('  Mixed  '), 'mixed')\n\n"
        "if __name__ == '__main__':\n    unittest.main()\n", encoding="utf-8")
    plan = repo / "docs" / "plans" / "normalizer-plan.md"
    plan.parent.mkdir(parents=True)
    plan.write_text(fixture_plans()["normalizer"], encoding="utf-8")
    before = snapshot(repo)
    process, message = codex(
        repo, base, "debug",
        "Use $managed-workflow-debug inside approved Task 1 of docs/plans/normalizer-plan.md. "
        "Reproduce the failing unittest, identify and report the root cause, make the smallest "
        "in-scope correction, and rerun the test. Do not modify plan state or commit.",
        "workspace-write",
    )
    require(process.returncode == 0, process.stdout)
    after = snapshot(repo)
    changed = {path for path in set(before) | set(after) if before.get(path) != after.get(path)}
    require(changed == {"normalizer.py"}, f"debugger changed unowned files: {sorted(changed)}")
    test_result = subprocess.run(
        [sys.executable, "-m", "unittest", "-v"], cwd=repo, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, check=False,
    )
    require(test_result.returncode == 0, test_result.stdout)
    require("root cause" in message.lower() or "cause" in message.lower(), "debugger omitted root cause")
    require(git(repo, "rev-parse", "--verify", "HEAD").returncode != 0, "debugger created commit")
    return "root cause corrected; focused test passed; plan state unchanged; no commit"


def complete_block_gate(base):
    repo = fixture(base, "complete-block", ["managed-workflow-plan", "managed-workflow-complete"])
    plan = repo / "docs" / "plans" / "blocked-plan.md"
    plan.parent.mkdir(parents=True)
    plan.write_text(fixture_plans()["blocked"], encoding="utf-8")
    before = snapshot(repo)
    process, message = codex(
        repo, base, "complete-block",
        "Use $managed-workflow-complete on docs/plans/blocked-plan.md. Enforce its entry gate and "
        "report the blocking task. Do not modify files or commit.",
        "workspace-write",
    )
    require(process.returncode == 0, process.stdout)
    require(snapshot(repo) == before, "completer mutated a plan that failed its entry gate")
    lowered = message.lower()
    require("task 1" in lowered and ("block" in lowered or "[x][f]" in lowered),
            f"completer did not report the blocking task: {message}")
    require(git(repo, "rev-parse", "--verify", "HEAD").returncode != 0, "completer created commit")
    return "[X][F] blocked completion; no files changed; no commit"


def remediation_gate(base):
    repo = fixture(base, "remediation", [
        "managed-workflow-plan",
        "managed-workflow-execute",
        "managed-workflow-verify",
        "managed-workflow-debug",
        "managed-workflow-complete",
    ])
    source = repo / "math_ops.py"
    source.write_text("def subtract(left, right):\n    return left + right\n", encoding="utf-8")
    test = repo / "test_math_ops.py"
    test.write_text(
        "import unittest\nfrom math_ops import subtract\n\n"
        "class TestSubtract(unittest.TestCase):\n"
        "    def test_subtract(self):\n        self.assertEqual(subtract(7, 2), 5)\n\n"
        "if __name__ == '__main__':\n    unittest.main()\n", encoding="utf-8")
    plan = repo / "docs" / "plans" / "math-plan.md"
    plan.parent.mkdir(parents=True)
    plan.write_text(fixture_plans()["math"], encoding="utf-8")
    plan_before = plan.read_text(encoding="utf-8")
    before = snapshot(repo)
    process, message = codex(
        repo, base, "remediation",
        "Use $managed-workflow-execute to remediate Task 1 in approved docs/plans/math-plan.md, "
        "independently re-verify every original finding, and complete the plan. All managed workflow "
        "skills are installed. Do not commit.",
        "workspace-write",
    )
    require(process.returncode == 0, process.stdout)
    after = snapshot(repo)
    changed = {path for path in set(before) | set(after) if before.get(path) != after.get(path)}
    require(changed == {"math_ops.py", "docs/plans/math-plan.md"},
            f"remediation changed files outside approved scope: {sorted(changed)}")
    test_result = subprocess.run(
        [sys.executable, "-m", "unittest", "-v"], cwd=repo, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, check=False,
    )
    require(test_result.returncode == 0, test_result.stdout)
    plan_text = plan.read_text(encoding="utf-8")
    require("- [X][R] Task 1: Implement subtraction" in plan_text,
            f"remediated task did not reach [X][R]: {plan_text}")
    for evidence in ("Task 1 REMEDIATION:", "Task 1 REVERIFY:", "- FINAL:"):
        require(evidence in plan_text, f"missing {evidence} evidence: {plan_text}")
    require_evidence_append_only(plan_before, plan_text)
    require_completion_summary(plan_text, "Completed")
    require_valid_plan(repo, plan)
    require("pass" in message.lower() or "complete" in message.lower(), "remediation omitted result")
    require(git(repo, "rev-parse", "--verify", "HEAD").returncode != 0, "remediation created commit")
    return "finding remediated; task reached [X][R]; plan completed; prior evidence preserved"


def main():
    if shutil.which("codex") is None:
        print("CODEX_INTEGRATION_SKIPPED: 'codex' command not found on PATH")
        return 0

    results, failures = [], []
    with tempfile.TemporaryDirectory(prefix="codex-compatibility-") as temporary:
        base = Path(temporary)
        gates = [(f"discovery:{name}", lambda name=name: discovery_gate(base, name)) for name in SKILLS]
        gates += [("behavior:plan", lambda: plan_gate(base)),
                  ("behavior:plan-write", lambda: plan_write_gate(base)),
                  ("behavior:execute", lambda: execute_gate(base)),
                  ("behavior:verify", lambda: verify_gate(base)),
                  ("behavior:debug", lambda: debug_gate(base)),
                  ("behavior:complete-block", lambda: complete_block_gate(base)),
                  ("behavior:remediation", lambda: remediation_gate(base))]
        for label, gate in gates:
            try:
                detail = gate()
                results.append((label, "PASS", detail))
            except Exception as error:
                failures.append(label)
                results.append((label, "FAIL", str(error).replace("\n", " ")[:1000]))
    print("CODEX_INTEGRATION_SUMMARY")
    for label, status, detail in results:
        print(f"{status} {label} :: {detail}")
    print(f"TOTAL {len(results)} PASS {len(results) - len(failures)} FAIL {len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
