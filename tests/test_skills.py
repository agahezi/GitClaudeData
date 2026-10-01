import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "skills.py"
TARGETS = {"codex": ".agents/skills", "claude": ".claude/skills"}
FAKE_CLAUDE = r'''
import json, os, sys
args = sys.argv[1:]
with open(os.environ["FAKE_CLAUDE_LOG"], "a", encoding="utf-8") as log:
    log.write(" ".join(args) + "\n")
record = os.path.join(os.environ["FAKE_CLAUDE_HOME"], ".claude", "plugins", "installed_plugins.json")
if args[:2] == ["plugin", "install"]:
    os.makedirs(os.path.dirname(record), exist_ok=True)
    with open(record, "w", encoding="utf-8") as handle:
        json.dump({"version": 2, "plugins": {args[2]: [{"scope": "user"}]}}, handle)
'''


def skill_text(name, description="Test skill.", extra_frontmatter="", body=""):
    return f"---\nname: {name}\ndescription: {description}\n{extra_frontmatter}---\n\n# {name}\n{body}\n"


def load_module():
    spec = importlib.util.spec_from_file_location("skills_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PLAN_SKILL = ROOT / "skills" / "managed-workflow-plan"
VALIDATOR = PLAN_SKILL / "scripts" / "validate_plan.py"


def load_validator():
    # Bytecode inside skills/ would be rejected by the installer.
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location("validate_plan_under_test", VALIDATOR)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def plan_template():
    text = (PLAN_SKILL / "SKILL.md").read_text(encoding="utf-8")
    return re.search(r"^````markdown\n(.*?)\n````$", text, re.S | re.M).group(1) + "\n"


class PlanValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = load_validator()
        cls.template = plan_template()
        start = cls.template.index("### Task 1:")
        cls.task_block = cls.template[start:cls.template.index("## Risks")]

    def errors(self, text, new=False):
        return [message for _, message in self.validator.validate(text, new=new)[0]]

    def assert_invalid(self, text, fragment, new=False):
        errors = self.errors(text, new)
        self.assertTrue(any(fragment in message for message in errors), errors)

    def two_tasks(self, first, second, status="Pending", evidence=""):
        text = self.template.replace(
            "- [ ][ ] Task 1: <short description>",
            f"- {first} Task 1: First\n- {second} Task 2: Second")
        second_block = self.task_block.replace("### Task 1: <short description>", "### Task 2: Second")
        text = text.replace("### Task 1: <short description>", "### Task 1: First")
        text = text.replace("## Risks", second_block + "## Risks")
        text = text.replace("**Status:** Pending", f"**Status:** {status}")
        return text.replace("<!-- Append-only. One concise line per state transition. -->", evidence)

    def test_skill_template_is_a_valid_new_plan(self):
        self.assertEqual(self.errors(self.template, new=True), [])

    def test_command_line_reports_ok_and_invalid(self):
        with tempfile.TemporaryDirectory() as temporary:
            plan = Path(temporary) / "plan.md"
            plan.write_text(self.template, encoding="utf-8")
            ok = subprocess.run([sys.executable, "-B", str(VALIDATOR), "--new", str(plan)],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
            self.assertEqual((ok.returncode, ok.stdout.strip()), (0, "PLAN_FORMAT_OK: 1 task(s)"))
            plan.write_text(self.template.replace("## Evidence Log", "## Evidence"), encoding="utf-8")
            bad = subprocess.run([sys.executable, "-B", str(VALIDATOR), str(plan)],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
            self.assertEqual(bad.returncode, 1)
            self.assertIn("PLAN_FORMAT_INVALID", bad.stdout)

    def test_rejects_missing_or_misordered_sections(self):
        self.assert_invalid(self.template.replace("## Evidence Log\n", ""), "missing section '## Evidence Log'")
        diagrams = self.template[self.template.index("## Process Diagrams"):self.template.index("## Progress")]
        moved = self.template.replace(diagrams, "").replace("---\n\n### Task 1", diagrams + "---\n\n### Task 1")
        self.assert_invalid(moved, "out of order")

    def test_rejects_malformed_progress_and_mismatched_tasks(self):
        self.assert_invalid(self.template.replace("- [ ][ ] Task 1:", "- [x] Task 1:"), "malformed progress entry")
        self.assert_invalid(self.template.replace("- [ ][ ] Task 1:", "- [ ][V] Task 1:"),
                            "unexecuted task cannot")
        self.assert_invalid(self.template.replace("### Task 1: <short description>", "### Task 1: Other"),
                            "task headings must match Progress")
        self.assert_invalid(self.template.replace("- [ ][ ] Task 1:", "- [X][ ] Task 1:"),
                            "initialize every task", new=True)

    def test_rejects_incomplete_or_oversized_tasks(self):
        self.assert_invalid(self.template.replace("**Produces:**", "**Outputs:**"),
                            "exactly one '**Produces:**'")
        steps = "\n".join(f"{number}. step" for number in range(1, 9))
        self.assert_invalid(self.template.replace("1. <step>", steps), "split it")
        self.assert_invalid(self.template.replace("- `<command>`", "- run the tests"),
                            "Verification needs")

    def test_diagrams_are_required_unless_declared_not_applicable(self):
        start = self.template.index("```mermaid")
        end = self.template.index("## Progress")
        self.assert_invalid(self.template[:start] + self.template[end:], "stateDiagram-v2")
        declared = (self.template[:start]
                    + "**State chart:** Not applicable - stateless formatting change\n\n"
                    + "**Sequence diagram:** Not applicable - single component\n\n"
                    + self.template[end:])
        self.assertEqual(self.errors(declared, new=True), [])

    def test_enforces_task_order_and_completion_evidence(self):
        self.assertEqual(self.errors(self.two_tasks("[X][V]", "[X][ ]")), [])
        self.assert_invalid(self.two_tasks("[X][ ]", "[X][ ]"), "advanced before Task 1")
        completed = self.two_tasks("[X][V]", "[X][R]", status="Completed").replace(
            "**Status:** Completed",
            "**Status:** Completed\n**Tasks:** 2; 1 verified; 1 remediated\n"
            "**Final verification:** `cmd` -> exit 0\n**Acceptance:** met\n**Residual risks:** none")
        self.assert_invalid(completed, "requires a FINAL evidence entry")
        long_entry = "- Task 1 EXECUTE: `cmd` -> exit 0; " + "x" * 240
        self.assert_invalid(self.two_tasks("[X][V]", "[ ][ ]", evidence=long_entry), "exceeds 240")

    def test_live_harness_fixture_plans_are_valid(self):
        spec = importlib.util.spec_from_file_location(
            "harness_under_test", ROOT / "tests" / "run_codex_integration.py")
        harness = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(harness)
        for name, text in harness.fixture_plans().items():
            with self.subTest(plan=name):
                self.assertEqual(self.errors(text, new=name == "calculator"), [])


class ManagedWorkflowContractTests(unittest.TestCase):
    SKILLS = {
        name: ROOT / "skills" / name / "SKILL.md"
        for name in (
            "managed-workflow-plan",
            "managed-workflow-execute",
            "managed-workflow-verify",
            "managed-workflow-debug",
            "managed-workflow-complete",
        )
    }

    def text(self, name):
        return self.SKILLS[name].read_text(encoding="utf-8")

    def test_workflow_skills_have_no_merge_markers(self):
        for name, path in self.SKILLS.items():
            with self.subTest(skill=name):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("<<<<<<<", text)
                self.assertNotIn("=======", text)
                self.assertNotIn(">>>>>>>", text)

    def test_workflow_skill_names_match_their_folders(self):
        for name, path in self.SKILLS.items():
            with self.subTest(skill=name):
                self.assertIn(f"\nname: {name}\n", path.read_text(encoding="utf-8"))

    def test_all_skills_preserve_strict_task_order(self):
        expected = "PLAN -> EXECUTE one task -> test -> VERIFY that task -> next task"
        for name in (
            "managed-workflow-plan",
            "managed-workflow-execute",
            "managed-workflow-verify",
        ):
            with self.subTest(skill=name):
                self.assertIn(expected, self.text(name))

    def test_planner_scales_design_and_enforces_task_sizing(self):
        text = self.text("managed-workflow-plan")
        for requirement in (
            "**Spike:**",
            "**Bounded:**",
            "**Architectural:**",
            "## Task sizing",
            "at most seven numbered implementation steps",
            "## Process Diagrams",
            "stateDiagram-v2",
            "sequenceDiagram",
            "scripts/validate_plan.py --new",
            "PLAN_FORMAT_OK",
            "**Inputs:**",
            "**Produces:**",
            "persistent plan is still",
            "## Evidence Log",
            "## Completion Summary",
            "## Plan Acceptance",
            "## Final Verification",
            "at most 240 characters",
        ):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, text)

    def test_executor_enforces_readiness_tests_and_verification(self):
        text = self.text("managed-workflow-execute")
        for requirement in (
            "## Task readiness gate",
            "## Plan format gate",
            "single entry point after planning",
            "invoke `managed-workflow-verify` for it",
            "execution checkbox unchanged",
            "Immediately run the focused check",
            "change the first checkbox from `[ ]` to `[X]`",
            "Do not start another task until",
            "request the smallest plan or scope revision",
            "If the user approves a revised plan or task split",
            "managed-workflow-debug",
            "managed-workflow-complete",
            "append one `EXECUTE` evidence entry",
            "[X][V]",
            "[X][R]",
        ):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, text)

    def test_verifier_owns_only_verification_status(self):
        text = self.text("managed-workflow-verify")
        for requirement in (
            "Run the task's focused verification",
            "managed-workflow-plan/scripts/validate_plan.py",
            "Update only the selected task's second checkbox",
            "**Verified:**",
            "**Indication:**",
            "**Not checked:**",
            "Recheck every original finding",
            "append evidence in the same repository edit",
            "confirmed final-check failure owned by that task",
            "[X][V]",
            "[X][F]",
            "[X][R]",
        ):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, text)

    def test_debugger_is_root_cause_scoped_and_owns_no_plan_state(self):
        text = self.text("managed-workflow-debug")
        for requirement in (
            "one falsifiable hypothesis at a time",
            "## Debugging flow",
            "**Trace to the controlling boundary.**",
            "**Correct minimally.**",
            "never\nchanges Progress, Evidence Log, Completion Summary",
            "## Escalation",
        ):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, text)

    def test_completer_requires_clean_tasks_and_writes_only_final_state(self):
        text = self.text("managed-workflow-complete")
        for requirement in (
            "Every Progress entry must be `[X][V]` or `[X][R]`",
            "managed-workflow-plan/scripts/validate_plan.py",
            "Do not modify implementation files",
            "one append-only `FINAL` Evidence Log entry",
            "## Completion Summary format",
            "**Status:** Completed | Blocked",
            "managed-workflow-verify",
        ):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, text)

    def test_repository_instructions_define_evidence_ownership(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        for requirement in (
            "executor may update only its execution checkbox and append",
            "verifier may update only its verification checkbox and",
            "completer may update only the completion summary",
            "Evidence is append-only",
        ):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, text)

    def test_planner_evidence_examples_fit_the_context_budget(self):
        text = self.text("managed-workflow-plan")
        examples = [
            line for line in text.splitlines()
            if line.startswith("- Task ") or line.startswith("- FINAL:")
        ]
        self.assertGreaterEqual(len(examples), 5)
        for line in examples:
            with self.subTest(evidence=line):
                self.assertLessEqual(len(line), 240)

    def test_integration_harness_covers_recovery_and_completion(self):
        text = (ROOT / "tests" / "run_codex_integration.py").read_text(encoding="utf-8")
        for requirement in (
            "def require_evidence_append_only",
            "def require_completion_summary",
            "def debug_gate",
            "def complete_block_gate",
            "def remediation_gate",
            "def plan_write_gate",
            "def require_valid_plan",
            '"behavior:plan-write"',
            '"behavior:debug"',
            '"behavior:complete-block"',
            '"behavior:remediation"',
            "CODEX_INTEGRATION_SKIPPED",
        ):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, text)


class Base(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.repo = self.base / "repo"
        (self.repo / "scripts").mkdir(parents=True)
        (self.repo / "skills").mkdir()
        shutil.copyfile(SCRIPT, self.repo / "scripts/skills.py")
        self.home = self.base / "home"
        self.env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"}

    def add_skill(self, name, text=None, extra=None, metadata=None):
        folder = self.repo / "skills" / name
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_bytes((text or skill_text(name)).encode())
        for relative, content in (extra or {}).items():
            path = folder / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        if metadata is not None:
            (folder / ".skill.json").write_bytes(json.dumps(metadata).encode())
        return folder

    def run_script(self, *args, stdin=""):
        if args[0] != "add":
            args = (*args, "--home", str(self.home))
        self.assertNotEqual(os.path.abspath(self.home), os.path.abspath(Path.home()))
        return subprocess.run(
            [sys.executable, str(self.repo / "scripts/skills.py"), *args], input=stdin,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
            env=self.env, cwd=self.base, check=False,
        )

    def installed(self, target, name):
        return self.home / TARGETS[target] / name

    def lines(self, result, status):
        return {line for line in result.stdout.splitlines() if line.startswith(status + " ")}

    def symlink_or_skip(self, link, target):
        try:
            link.symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are not available on this system")

    def git(self, repo, *args):
        return subprocess.run(
            ["git", "-C", str(repo), "-c", "user.name=Test", "-c", "user.email=test@example.com",
             "-c", "core.autocrlf=false", *args],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=True,
        ).stdout.strip()

    def make_upstream(self, files):
        upstream = self.base / "upstream"
        upstream.mkdir()
        self.git(upstream, "init", "--quiet", "-b", "main")
        self.commit(upstream, files)
        return upstream

    def commit(self, upstream, files):
        for relative, content in files.items():
            path = upstream / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content.encode())
        self.git(upstream, "add", "-A")
        self.git(upstream, "commit", "--quiet", "-m", "change")
        return self.git(upstream, "rev-parse", "HEAD")


class CrossToolSupportTests(Base):
    PORTABLE_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}

    def test_every_skill_uses_portable_metadata_for_both_tools(self):
        module = load_module()
        for folder in sorted(path for path in (ROOT / "skills").iterdir() if path.is_dir()):
            with self.subTest(skill=folder.name):
                files, _ = module.read_tree(folder)
                meta = module.frontmatter(files["SKILL.md"][0])
                self.assertLessEqual(set(meta), self.PORTABLE_FIELDS)
                self.assertEqual(meta["name"], folder.name)
                self.assertLessEqual(len(meta["name"]), 64)
                self.assertTrue(0 < len(meta["description"]) <= 1024)
                targets = module.read_metadata(folder).get("targets", list(module.TARGETS))
                self.assertEqual(set(targets), {"codex", "claude"})
                files.pop(module.METADATA, None)
                self.assertEqual(module.claude_only_features(files), [])

    def test_skill_references_and_evidence_locations_exist(self):
        for folder in sorted(path for path in (ROOT / "skills").iterdir() if path.is_dir()):
            text = (folder / "SKILL.md").read_text(encoding="utf-8")
            for reference in sorted(set(re.findall(r"references/[\w./-]+\.md", text))):
                with self.subTest(skill=folder.name, reference=reference):
                    self.assertTrue((folder / reference).is_file())
            evidence = folder / "evidence.json"
            if evidence.is_file():
                for claim in json.loads(evidence.read_text(encoding="utf-8"))["claims"]:
                    for location in claim["appears_in"]:
                        with self.subTest(skill=folder.name, claim=claim["claim_id"], location=location):
                            self.assertTrue((folder / location).is_file())

    def test_install_places_skills_and_working_validator_for_both_tools(self):
        shutil.rmtree(self.repo / "skills")
        shutil.copytree(ROOT / "skills", self.repo / "skills",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        result = self.run_script("install", "--yes")
        self.assertEqual(result.returncode, 0, result.stdout)
        names = sorted(path.name for path in (ROOT / "skills").iterdir() if path.is_dir())
        plan = self.base / "plan.md"
        plan.write_text(plan_template(), encoding="utf-8")
        for target in TARGETS:
            for name in names:
                with self.subTest(target=target, skill=name):
                    self.assertTrue((self.installed(target, name) / "SKILL.md").is_file())
            for consumer in ("managed-workflow-execute", "managed-workflow-verify", "managed-workflow-complete"):
                with self.subTest(target=target, consumer=consumer):
                    validator = (self.installed(target, consumer) / ".." / "managed-workflow-plan"
                                 / "scripts" / "validate_plan.py")
                    checked = subprocess.run([sys.executable, "-B", str(validator), "--new", str(plan)],
                                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                             check=False)
                    self.assertEqual(checked.returncode, 0, checked.stdout)
                    self.assertIn("PLAN_FORMAT_OK", checked.stdout)


class InstallTests(Base):
    def test_plan_lists_both_tools_and_writes_nothing(self):
        self.add_skill("alpha")
        result = self.run_script("plan")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.lines(result, "CREATE"), {"CREATE codex alpha", "CREATE claude alpha"})
        self.assertFalse(self.home.exists())

    def test_install_copies_every_file_to_both_tools_and_verifies(self):
        self.add_skill("alpha", extra={"references/guide.md": b"guide\n"}, metadata={"targets": ["codex", "claude"]})
        result = self.run_script("install", "--yes")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("VERIFIED: codex 1 skills, claude 1 skills", result.stdout)
        for target in TARGETS:
            folder = self.installed(target, "alpha")
            self.assertEqual((folder / "SKILL.md").read_bytes(), skill_text("alpha").encode())
            self.assertEqual((folder / "references/guide.md").read_bytes(), b"guide\n")
            self.assertFalse((folder / ".skill.json").exists())
        verified = self.run_script("verify")
        self.assertEqual(verified.returncode, 0, verified.stdout)
        self.assertEqual(self.lines(verified, "OK"), {"OK codex alpha", "OK claude alpha"})

    def test_second_install_is_unchanged_and_keeps_timestamps(self):
        self.add_skill("alpha")
        self.assertEqual(self.run_script("install", "--yes").returncode, 0)
        path = self.installed("codex", "alpha") / "SKILL.md"
        before = path.stat().st_mtime_ns
        result = self.run_script("install", "--yes")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.lines(result, "UNCHANGED"), {"UNCHANGED codex alpha", "UNCHANGED claude alpha"})
        self.assertEqual(path.stat().st_mtime_ns, before)

    def test_targets_limit_which_tools_get_a_skill(self):
        self.add_skill("alpha", metadata={"targets": ["claude"]})
        self.assertEqual(self.run_script("install", "--yes").returncode, 0)
        self.assertTrue(self.installed("claude", "alpha").is_dir())
        self.assertFalse(self.installed("codex", "alpha").exists())

    def test_repo_change_updates_the_installed_copy(self):
        folder = self.add_skill("alpha")
        self.assertEqual(self.run_script("install", "--yes").returncode, 0)
        (folder / "SKILL.md").write_bytes(skill_text("alpha", body="v2").encode())
        (folder / "new.md").write_bytes(b"new\n")
        result = self.run_script("install", "--yes")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("UPDATE codex alpha", result.stdout)
        self.assertIn(b"v2", (self.installed("codex", "alpha") / "SKILL.md").read_bytes())
        self.assertTrue((self.installed("claude", "alpha") / "new.md").is_file())

    def test_local_edit_is_a_conflict_and_declining_keeps_it(self):
        self.add_skill("alpha")
        self.assertEqual(self.run_script("install", "--yes").returncode, 0)
        edited = self.installed("codex", "alpha") / "SKILL.md"
        edited.write_bytes(b"my edit")
        result = self.run_script("install", stdin="n\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CONFLICT codex alpha", result.stdout)
        self.assertEqual(edited.read_bytes(), b"my edit")

    def test_unmanaged_different_copy_is_backed_up_then_replaced(self):
        self.add_skill("alpha")
        existing = self.installed("codex", "alpha")
        existing.mkdir(parents=True)
        (existing / "SKILL.md").write_bytes(b"old copy")
        result = self.run_script("install", "--yes")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("CONFLICT codex alpha", result.stdout)
        backups = list((self.home / ".skill-manager/backups").glob("*/codex/alpha/SKILL.md"))
        self.assertEqual([path.read_bytes() for path in backups], [b"old copy"])
        self.assertEqual((existing / "SKILL.md").read_bytes(), skill_text("alpha").encode())

    def test_identical_unmanaged_copy_is_adopted(self):
        folder = self.add_skill("alpha")
        existing = self.installed("codex", "alpha")
        existing.mkdir(parents=True)
        (existing / "SKILL.md").write_bytes((folder / "SKILL.md").read_bytes())
        self.assertIn("UNCHANGED codex alpha", self.run_script("install", "--yes").stdout)
        (folder / "SKILL.md").write_bytes(skill_text("alpha", body="v2").encode())
        self.assertIn("UPDATE codex alpha", self.run_script("install", "--yes").stdout)

    def test_skill_removed_from_repo_is_uninstalled_unless_edited(self):
        self.add_skill("alpha")
        self.add_skill("beta")
        self.assertEqual(self.run_script("install", "--yes").returncode, 0)
        (self.installed("codex", "beta") / "SKILL.md").write_bytes(b"edited")
        shutil.rmtree(self.repo / "skills/alpha")
        shutil.rmtree(self.repo / "skills/beta")
        result = self.run_script("install", "--yes")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("REMOVE codex alpha", result.stdout)
        self.assertIn("KEEP codex beta", result.stdout)
        self.assertFalse(self.installed("codex", "alpha").exists())
        self.assertEqual((self.installed("codex", "beta") / "SKILL.md").read_bytes(), b"edited")
        self.assertNotIn("beta", self.run_script("install", "--yes").stdout)

    def test_linked_tool_folder_blocks_all_writes_through_it(self):
        self.add_skill("alpha")
        outside = self.base / "outside"
        outside.mkdir()
        self.home.mkdir()
        self.symlink_or_skip(self.home / ".agents", outside)
        result = self.run_script("install", "--yes")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("BLOCKED codex alpha", result.stdout)
        self.assertEqual(list(outside.iterdir()), [])

    def test_installed_link_is_moved_to_backup_without_touching_its_target(self):
        self.add_skill("alpha")
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "SKILL.md").write_bytes(b"outside")
        self.installed("codex", "alpha").parent.mkdir(parents=True)
        self.symlink_or_skip(self.installed("codex", "alpha"), outside)
        result = self.run_script("install", "--yes")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual((outside / "SKILL.md").read_bytes(), b"outside")
        self.assertFalse(self.installed("codex", "alpha").is_symlink())
        self.assertEqual((self.installed("codex", "alpha") / "SKILL.md").read_bytes(), skill_text("alpha").encode())

    def test_verify_reports_missing_and_different(self):
        self.add_skill("alpha")
        result = self.run_script("verify")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.lines(result, "MISSING"), {"MISSING codex alpha", "MISSING claude alpha"})
        self.assertIn("NOT VERIFIED", result.stdout)
        self.assertEqual(self.run_script("install", "--yes").returncode, 0)
        (self.installed("claude", "alpha") / "extra.md").write_bytes(b"extra")
        result = self.run_script("verify")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DIFFERENT claude alpha", result.stdout)
        self.assertIn("OK codex alpha", result.stdout)

    def test_verify_ignores_python_bytecode_caches(self):
        self.add_skill("alpha", extra={"scripts/tool.py": b"print(1)\n"})
        self.assertEqual(self.run_script("install", "--yes").returncode, 0)
        cache = self.installed("codex", "alpha") / "scripts/__pycache__"
        cache.mkdir()
        (cache / "tool.cpython-312.pyc").write_bytes(b"\0")
        self.assertEqual(self.run_script("verify").returncode, 0)

    @unittest.skipIf(os.name == "nt", "executable bits are a POSIX concept")
    def test_executable_bit_is_installed(self):
        folder = self.add_skill("alpha", extra={"run.sh": b"#!/bin/sh\n"})
        (folder / "run.sh").chmod(0o755)
        self.assertEqual(self.run_script("install", "--yes").returncode, 0)
        self.assertTrue(os.access(self.installed("codex", "alpha") / "run.sh", os.X_OK))


class CatalogTests(Base):
    def test_invalid_catalog_refuses_before_touching_home(self):
        cases = {
            "name mismatch": lambda: self.add_skill("alpha", text=skill_text("other")),
            "no description": lambda: self.add_skill("alpha", text="---\nname: alpha\n---\n"),
            "no front matter": lambda: self.add_skill("alpha", text="# alpha\n"),
            "no SKILL.md": lambda: (self.repo / "skills/alpha").mkdir(),
            "secret file": lambda: self.add_skill("alpha", extra={".env": b"SECRET_SENTINEL"}),
            "bytecode": lambda: self.add_skill("alpha", extra={"x.pyc": b"\0"}),
            "stray file": lambda: (self.repo / "skills/alpha").write_bytes(b"x"),
            "bad targets": lambda: self.add_skill("alpha", metadata={"targets": ["cursor"]}),
            "bad plugins": lambda: (self.repo / "plugins.json").write_bytes(
                b'{"plugins": [{"id": "a@b", "install": [["rm", "-rf", "/"]]}]}'),
        }
        for label, create in cases.items():
            with self.subTest(label):
                create()
                result = self.run_script("install", "--yes")
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("ERROR", result.stdout)
                self.assertNotIn("SECRET_SENTINEL", result.stdout)
                self.assertFalse(self.home.exists())
                target = self.repo / "skills/alpha"
                if target.is_dir():
                    shutil.rmtree(target)
                elif target.exists():
                    target.unlink()
                (self.repo / "plugins.json").unlink(missing_ok=True)

    def test_link_inside_a_skill_is_rejected(self):
        folder = self.add_skill("alpha")
        self.symlink_or_skip(folder / "linked", self.base)
        result = self.run_script("plan")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ERROR skills/alpha: link", result.stdout)

    def test_real_repository_catalog_and_plugins_are_valid(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "plan", "--home", str(self.home)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
            env=self.env, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("ERROR", result.stdout)
        self.assertTrue(self.lines(result, "CREATE"))
        self.assertFalse(self.home.exists())


class AddTests(Base):
    def make_folder(self, name, text=None):
        folder = self.base / "downloads" / name
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_bytes((text or skill_text(name)).encode())
        return folder

    def metadata(self, name):
        return json.loads((self.repo / "skills" / name / ".skill.json").read_text(encoding="utf-8"))

    def test_add_local_folder_copies_skill_for_both_tools(self):
        folder = self.make_folder("alpha")
        (folder / ".DS_Store").write_bytes(b"junk")
        result = self.run_script("add", str(folder), "--yes")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual((self.repo / "skills/alpha/SKILL.md").read_bytes(), (folder / "SKILL.md").read_bytes())
        self.assertFalse((self.repo / "skills/alpha/.DS_Store").exists())
        self.assertEqual(self.metadata("alpha")["targets"], ["claude", "codex"])
        self.assertEqual(self.metadata("alpha")["source"]["kind"], "folder")
        self.assertEqual(self.run_script("install", "--yes").returncode, 0)

    def test_claude_only_features_ask_which_tools(self):
        text = skill_text("alpha", extra_frontmatter="allowed-tools: Read\n")
        folder = self.make_folder("alpha", text)
        result = self.run_script("add", str(folder), stdin="y\n")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("allowed-tools", result.stdout)
        self.assertEqual(self.metadata("alpha")["targets"], ["claude"])
        result = self.run_script("add", str(folder), stdin="n\n")
        self.assertEqual(self.metadata("alpha")["targets"], ["claude", "codex"])

    def test_add_never_overwrites_a_custom_skill(self):
        self.add_skill("alpha", text=skill_text("alpha", body="mine"))
        result = self.run_script("add", str(self.make_folder("alpha")), "--yes")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already exists", result.stdout)
        self.assertIn(b"mine", (self.repo / "skills/alpha/SKILL.md").read_bytes())

    def test_add_plugin_repository_installs_plugin_and_copies_skills_for_codex(self):
        upstream = self.make_upstream({
            "skills/one/SKILL.md": skill_text("one"),
            "skills/two/SKILL.md": skill_text("two"),
            "tests/fixture/SKILL.md": skill_text("fixture"),
            ".claude-plugin/plugin.json": '{"name": "pack"}',
            "README.md": "/plugin marketplace add owner/market\n/plugin install pack@market\n",
        })
        result = self.run_script("add", upstream.as_uri(), "--yes")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(sorted(path.name for path in (self.repo / "skills").iterdir()), ["one", "two"])
        metadata = self.metadata("one")
        self.assertEqual(metadata["targets"], ["codex"])
        self.assertEqual(metadata["source"]["commit"], self.git(upstream, "rev-parse", "HEAD"))
        self.assertEqual(metadata["source"]["path"], "skills/one")
        plugins = json.loads((self.repo / "plugins.json").read_text(encoding="utf-8"))["plugins"]
        self.assertEqual(plugins[0]["id"], "pack@market")
        self.assertIn(["claude", "plugin", "marketplace", "add", "owner/market"], plugins[0]["install"])

    def test_official_marketplace_is_preferred_and_needs_no_marketplace_add(self):
        module = load_module()
        root = self.base / "plugin"
        (root / ".claude-plugin").mkdir(parents=True)
        (root / ".claude-plugin/plugin.json").write_text('{"name": "pack"}', encoding="utf-8")
        (root / "README.md").write_text(
            "/plugin install pack@claude-plugins-official\n"
            "/plugin marketplace add owner/market\n/plugin install pack@market\n", encoding="utf-8")
        entry = module.detect_plugin(root, {})
        self.assertEqual(entry["install"], [["claude", "plugin", "install", "pack@claude-plugins-official"]])

    def test_zip_with_unsafe_path_is_refused(self):
        archive = self.base / "evil.zip"
        with zipfile.ZipFile(archive, "w") as handle:
            handle.writestr("../evil/SKILL.md", skill_text("evil"))
        result = self.run_script("add", str(archive), "--yes")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsafe path", result.stdout)
        self.assertFalse((self.base / "evil").exists())

    def test_zip_with_top_folder_is_imported(self):
        archive = self.base / "pack.zip"
        with zipfile.ZipFile(archive, "w") as handle:
            handle.writestr("pack-main/skills/gamma/SKILL.md", skill_text("gamma"))
        result = self.run_script("add", str(archive), "--yes")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.metadata("gamma")["source"]["kind"], "zip")
        self.assertEqual(self.metadata("gamma")["source"]["path"], "skills/gamma")

    def test_github_links_are_understood(self):
        module = load_module()
        resolve = lambda link: module.resolve_link(link, module.Prompter(True))
        self.assertEqual(resolve("https://github.com/o/r"),
                         ({"kind": "git", "location": "https://github.com/o/r.git", "ref": None}, ""))
        self.assertEqual(resolve("https://github.com/o/r/tree/main/skills/x")[1], "skills/x")
        self.assertEqual(resolve("https://github.com/o/r/blob/v1/skills/x/SKILL.md"),
                         ({"kind": "git", "location": "https://github.com/o/r.git", "ref": "v1"}, "skills/x"))
        with self.assertRaises(module.SkillError):
            resolve("http://example.com/skill")

    def test_links_are_found_on_a_web_page(self):
        module = load_module()
        page = ('<a href="https://github.com/o/r/tree/main/skills/x">code</a>'
                '<code>npx skills add o/other</code>')
        self.assertEqual(module.links_in_page(page),
                         ["https://github.com/o/r/tree/main/skills/x", "https://github.com/o/other"])


class UpdateTests(Base):
    def test_newer_upstream_version_is_offered_and_applied_only_when_accepted(self):
        upstream = self.make_upstream({"skills/one/SKILL.md": skill_text("one")})
        self.assertEqual(self.run_script("add", upstream.as_uri(), "--yes").returncode, 0)
        self.assertEqual(self.run_script("install", "--yes").returncode, 0)
        unchanged = self.run_script("update", stdin="")
        self.assertIn("UP_TO_DATE", unchanged.stdout)
        newer = self.commit(upstream, {"skills/one/SKILL.md": skill_text("one", body="v2")})
        declined = self.run_script("update", stdin="n\n")
        self.assertEqual(declined.returncode, 0, declined.stdout)
        self.assertIn("NEWER", declined.stdout)
        self.assertNotIn(b"v2", (self.repo / "skills/one/SKILL.md").read_bytes())
        accepted = self.run_script("update", stdin="y\n")
        self.assertEqual(accepted.returncode, 0, accepted.stdout)
        self.assertIn(b"v2", (self.repo / "skills/one/SKILL.md").read_bytes())
        self.assertIn(b"v2", (self.installed("codex", "one") / "SKILL.md").read_bytes())
        metadata = json.loads((self.repo / "skills/one/.skill.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["source"]["commit"], newer)

    def test_install_without_yes_offers_newer_version(self):
        upstream = self.make_upstream({"skills/one/SKILL.md": skill_text("one")})
        self.assertEqual(self.run_script("add", upstream.as_uri(), "--yes").returncode, 0)
        self.commit(upstream, {"skills/one/SKILL.md": skill_text("one", body="v2")})
        result = self.run_script("install", stdin="y\n")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn(b"v2", (self.installed("claude", "one") / "SKILL.md").read_bytes())


class PluginTests(Base):
    def setUp(self):
        super().setUp()
        bin_folder = self.base / "bin"
        bin_folder.mkdir()
        fake = bin_folder / "fake_claude.py"
        fake.write_text(FAKE_CLAUDE, encoding="utf-8")
        if os.name == "nt":
            (bin_folder / "claude.cmd").write_text(f'@"{sys.executable}" "{fake}" %*\r\n', encoding="utf-8")
        else:
            launcher = bin_folder / "claude"
            launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{fake}" "$@"\n', encoding="utf-8")
            launcher.chmod(0o755)
        self.log = self.base / "claude.log"
        self.env.update(PATH=str(bin_folder) + os.pathsep + self.env["PATH"],
                        FAKE_CLAUDE_LOG=str(self.log), FAKE_CLAUDE_HOME=str(self.home))
        entry = load_module().plugin_entry("pack@market", "owner/market")
        (self.repo / "plugins.json").write_text(json.dumps({"plugins": [entry]}), encoding="utf-8")

    def calls(self):
        lines = self.log.read_text(encoding="utf-8").splitlines() if self.log.exists() else []
        return [line for line in lines if line != "plugin list"]

    def test_install_adds_plugin_once_and_verifies_it(self):
        result = self.run_script("install", "--yes")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.calls(), ["plugin marketplace add owner/market", "plugin install pack@market"])
        self.assertIn("OK plugin pack@market", result.stdout)
        again = self.run_script("install", "--yes")
        self.assertIn("UNCHANGED plugin pack@market", again.stdout)
        self.assertEqual(len(self.calls()), 2)

    def test_install_asks_before_updating_plugin(self):
        self.assertEqual(self.run_script("install", "--yes").returncode, 0)
        self.run_script("install", stdin="n\n")
        self.assertFalse(any("plugin update" in call for call in self.calls()))
        result = self.run_script("install", stdin="y\n")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("plugin update pack@market", self.calls())
        self.assertIn("plugin marketplace update market", self.calls())

    def test_missing_claude_command_fails_verification(self):
        self.env["PATH"] = os.path.dirname(sys.executable)
        result = self.run_script("install", "--yes")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("MISSING_TOOL", result.stdout)
        self.assertIn("MISSING plugin pack@market", result.stdout)


if __name__ == "__main__":
    unittest.main()
