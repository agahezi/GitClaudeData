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
SKILLS = ("managed-workflow-plan", "managed-workflow-execute", "managed-workflow-verify")


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


def execute_gate(base):
    repo = fixture(base, "execute", ["managed-workflow-execute", "managed-workflow-verify"])
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
    plan.write_text(
        "# Calculator Implementation Plan\n\n"
        "**Goal:** Implement arithmetic addition.\n"
        "**Architecture:** Keep the existing function boundary.\n"
        "**Tech Stack:** Python unittest\n\n"
        "## Scope\n\nModify only calculator.py and this plan's progress status.\n\n"
        "## Progress\n\n- [ ][ ] Task 1: Implement addition\n\n---\n\n"
        "### Task 1: Implement addition\n\n"
        "**Files:**\n\n- Modify: `calculator.py`\n\n"
        "**Inputs:**\n\n- Existing `add(left, right)` function\n\n"
        "**Implementation steps:**\n\n"
        "1. Run the focused test and confirm the expected failure.\n"
        "2. Return the arithmetic sum.\n"
        "3. Run the focused test and check the result.\n\n"
        "**Verification:**\n\n"
        "- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v`\n\n"
        "**Acceptance criteria:**\n\n- `add(2, 3)` returns `5`.\n\n"
        "**Produces:**\n\n- Working arithmetic addition through `add`.\n\n"
        "## Risks, Assumptions, and Likely Failure Modes\n\n- Numeric operands use Python addition.\n",
        encoding="utf-8",
    )
    before = snapshot(repo)
    process, message = codex(
        repo, base, "execute",
        "Use $managed-workflow-execute to execute and independently verify Task 1 from the approved "
        "docs/plans/calculator-plan.md. Both managed workflow skills are installed. Do not commit.",
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
    require("- [X][V] Task 1: Implement addition" in plan.read_text(encoding="utf-8"),
            f"task did not complete execution and verification gates: {plan.read_text(encoding='utf-8')}")
    require(git(repo, "rev-parse", "--verify", "HEAD").returncode != 0, "execute created commit")
    require("pass" in message.lower() or "ok" in message.lower(), "execute omitted test result")
    return "approved files changed; unittest passed; task reached [X][V]; no commit"


def verify_gate(base):
    repo = fixture(base, "verify", ["managed-workflow-verify"])
    defect = repo / "pricing.py"
    defect.write_text("def discount(price, percent):\n    return price + (price * percent / 100)\n", encoding="utf-8")
    before = snapshot(repo)
    process, message = codex(
        repo, base, "verify",
        "Use $managed-workflow-verify to review pricing.py read-only. It contains a known correctness "
        "defect in discount. Identify it with severity and exact file:line evidence. Do not modify files.",
        "read-only",
    )
    require(process.returncode == 0, process.stdout)
    lowered = message.lower()
    require("pricing.py" in lowered and (":2" in lowered or "line 2" in lowered), message)
    require("high" in lowered or "blocker" in lowered, "missing severity")
    require("add" in lowered or "subtract" in lowered or "increase" in lowered, "known defect not identified")
    severities = [lowered.find(word) for word in ("blocker", "high", "medium", "low") if lowered.find(word) >= 0]
    require(severities == sorted(severities), "findings are not severity ordered")
    require(snapshot(repo) == before, "verify mutated repository")
    require(git(repo, "rev-parse", "--verify", "HEAD").returncode != 0, "verify created commit")
    return "known defect found with line and severity; read-only; no commit"


def main():
    results, failures = [], []
    with tempfile.TemporaryDirectory(prefix="codex-compatibility-") as temporary:
        base = Path(temporary)
        gates = [(f"discovery:{name}", lambda name=name: discovery_gate(base, name)) for name in SKILLS]
        gates += [("behavior:plan", lambda: plan_gate(base)),
                  ("behavior:execute", lambda: execute_gate(base)),
                  ("behavior:verify", lambda: verify_gate(base))]
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
