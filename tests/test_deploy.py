import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEPLOY_SOURCE = PROJECT_ROOT / "scripts" / "deploy.py"


class DeployPlanTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.repo = self.root / "repo"
        self.home = self.root / "fake-home"
        (self.repo / "scripts").mkdir(parents=True)
        if DEPLOY_SOURCE.exists():
            shutil.copyfile(DEPLOY_SOURCE, self.repo / "scripts" / "deploy.py")
        self.write_source("shared-global/skills/shared/SKILL.md", b"shared\n")
        self.write_source("claude-global/skills/claude/SKILL.md", b"claude\n")
        self.write_source("claude-global/commands/tool/run.md", b"command\n")
        self.write_source("claude-global/agents/reviewer.md", b"agent\n")
        self.write_source("claude-global/legacy/skills/legacy.md", b"legacy\n")

    def write_source(self, relative, content):
        path = self.repo / "catalog" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def run_deploy(self, *args, cwd=None):
        command = [sys.executable, str(self.repo / "scripts" / "deploy.py"), *args]
        return subprocess.run(
            command,
            cwd=cwd or self.repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            check=False,
        )

    def claude_plan(self, *extra, cwd=None):
        return self.run_deploy("plan", "--target", "claude", "--home", str(self.home), *extra, cwd=cwd)

    def test_default_operation_equals_explicit_plan_and_default_target_is_claude(self):
        implicit = self.run_deploy("--home", str(self.home))
        explicit = self.run_deploy("plan", "--home", str(self.home))
        self.assertEqual(implicit.returncode, 0)
        self.assertEqual(implicit.stdout, explicit.stdout)
        self.assertIn("TARGET claude", implicit.stdout)

    def test_empty_home_reports_expected_create_files(self):
        result = self.claude_plan()
        self.assertEqual(result.returncode, 0, result.stdout)
        expected = {
            "CREATE .claude/skills/shared/SKILL.md",
            "CREATE .claude/skills/claude/SKILL.md",
            "CREATE .claude/commands/tool/run.md",
            "CREATE .claude/agents/reviewer.md",
            "CREATE .claude/skills/legacy.md",
        }
        self.assertEqual({line for line in result.stdout.splitlines() if line.startswith("CREATE ")}, expected)

    def test_plan_does_not_create_fake_home(self):
        result = self.claude_plan()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse(self.home.exists())

    def test_identical_destination_is_unchanged(self):
        destination = self.home / ".claude/skills/shared/SKILL.md"
        destination.parent.mkdir(parents=True)
        destination.write_bytes(b"shared\n")
        result = self.claude_plan()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("UNCHANGED .claude/skills/shared/SKILL.md", result.stdout)

    def test_differing_destination_is_collision_and_nonzero(self):
        destination = self.home / ".claude/skills/shared/SKILL.md"
        destination.parent.mkdir(parents=True)
        destination.write_bytes(b"different\n")
        result = self.claude_plan()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("COLLISION .claude/skills/shared/SKILL.md", result.stdout)

    def test_destination_directory_is_type_collision(self):
        (self.home / ".claude/skills/shared/SKILL.md").mkdir(parents=True)
        result = self.claude_plan()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TYPE_COLLISION .claude/skills/shared/SKILL.md", result.stdout)

    def test_destination_symlink_is_type_collision(self):
        destination = self.home / ".claude/skills/shared/SKILL.md"
        destination.parent.mkdir(parents=True)
        destination.symlink_to(self.root / "nowhere")
        result = self.claude_plan()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TYPE_COLLISION .claude/skills/shared/SKILL.md", result.stdout)

    def test_output_order_is_deterministic_and_uses_relative_destinations(self):
        first = self.claude_plan()
        second = self.claude_plan()
        self.assertEqual(first.stdout, second.stdout)
        artifact_lines = [line for line in first.stdout.splitlines() if line.startswith(("CREATE ", "UNCHANGED ", "COLLISION ", "TYPE_COLLISION "))]
        self.assertEqual(artifact_lines, sorted(artifact_lines, key=lambda line: line.split(" ", 1)[1]))
        self.assertNotIn(str(self.root), first.stdout)

    def test_calling_from_outside_repository_finds_catalog(self):
        outside = self.root / "outside"
        outside.mkdir()
        result = self.claude_plan(cwd=outside)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("CREATE .claude/skills/shared/SKILL.md", result.stdout)

    def test_codex_marks_shared_candidates_ineligible_and_excludes_claude_only(self):
        result = self.run_deploy("plan", "--target", "codex", "--home", str(self.home))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("MAPPING catalog/shared-global/skills/* -> HOME/.agents/skills/*", result.stdout)
        self.assertIn("INELIGIBLE .agents/skills/shared/SKILL.md", result.stdout)
        self.assertIn("behavioral compatibility gates have not passed", result.stdout)
        self.assertNotIn("claude/SKILL.md", result.stdout)
        self.assertNotIn("reviewer.md", result.stdout)
        self.assertFalse(self.home.exists())

    def test_unexpected_catalog_layout_is_rejected(self):
        self.write_source("surprise.txt", b"ordinary unknown data\n")
        result = self.claude_plan()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("VALIDATION_ERROR unexpected catalog layout: catalog/surprise.txt", result.stdout)

    def test_secret_like_and_generated_sources_are_rejected_without_contents(self):
        fixtures = {
            "shared-global/skills/shared/.env": b"ENV_SECRET_SENTINEL",
            "shared-global/skills/shared/.env.prod": b"ENV_PROD_SENTINEL",
            "shared-global/skills/shared/Credentials.txt": b"CREDENTIAL_SENTINEL",
            "shared-global/skills/shared/settings.local.json": b"SETTINGS_SENTINEL",
            "shared-global/skills/shared/__pycache__/module.pyc": b"BYTECODE_SENTINEL",
            "shared-global/skills/shared/module.pyo": b"PYO_SENTINEL",
            "shared-global/skills/shared/native.pyd": b"PYD_SENTINEL",
        }
        for relative, content in fixtures.items():
            self.write_source(relative, content)
        result = self.claude_plan()
        self.assertNotEqual(result.returncode, 0)
        for relative in fixtures:
            self.assertIn("VALIDATION_ERROR rejected source path: catalog/" + relative, result.stdout)
        for content in fixtures.values():
            self.assertNotIn(content.decode(), result.stdout)

    def test_source_symlink_is_rejected(self):
        link = self.repo / "catalog/shared-global/skills/shared/link.md"
        link.symlink_to(self.root / "outside-secret")
        result = self.claude_plan()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("VALIDATION_ERROR source symlink: catalog/shared-global/skills/shared/link.md", result.stdout)

    def test_every_invocation_uses_explicit_fake_home(self):
        result = self.claude_plan()
        self.assertNotEqual(self.home, Path.home())
        self.assertNotIn(str(Path.home()), result.stdout)


if __name__ == "__main__":
    unittest.main()
