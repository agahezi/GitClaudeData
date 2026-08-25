import contextlib
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "scripts" / "deploy.py"
SKILLS = ("managed-workflow-execute", "managed-workflow-plan", "managed-workflow-verify")


class DeployTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.repo = self.base / "repo"
        self.home = self.base / "fake-home"
        (self.repo / "scripts").mkdir(parents=True)
        shutil.copyfile(DEPLOY, self.repo / "scripts/deploy.py")
        for name in SKILLS:
            path = self.repo / "catalog/codex-global/skills" / name / "SKILL.md"
            path.parent.mkdir(parents=True)
            path.write_bytes((name + "\n").encode())

    def run_deploy(self, *args, cwd=None):
        if "--home" in args:
            supplied = Path(args[args.index("--home") + 1])
            self.assertNotEqual(os.path.abspath(supplied), os.path.abspath(Path.home()))
        return subprocess.run(
            [sys.executable, str(self.repo / "scripts/deploy.py"), *args],
            cwd=cwd or self.repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, check=False,
        )

    def load_deploy(self, name):
        spec = importlib.util.spec_from_file_location(name, self.repo / "scripts/deploy.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        self.addCleanup(sys.modules.pop, spec.name, None)
        spec.loader.exec_module(module)
        return module

    def plan(self):
        return self.run_deploy("plan", "--home", str(self.home))

    def apply(self):
        return self.run_deploy("apply", "--home", str(self.home))

    def verify(self):
        return self.run_deploy("verify", "--home", str(self.home))

    def expected(self, status):
        return {f"{status} .agents/skills/{name}/SKILL.md" for name in SKILLS}

    def status_lines(self, result, *statuses):
        prefixes = tuple(status + " " for status in statuses)
        return {line for line in result.stdout.splitlines() if line.startswith(prefixes)}

    def test_default_equals_explicit_plan(self):
        implicit = self.run_deploy("--home", str(self.home))
        explicit = self.plan()
        self.assertEqual((implicit.returncode, implicit.stdout), (explicit.returncode, explicit.stdout))

    def test_empty_home_plan_lists_create_without_creating_home(self):
        result = self.plan()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.status_lines(result, "CREATE"), self.expected("CREATE"))
        self.assertFalse(self.home.exists())

    def test_apply_creates_expected_bytes_and_modes_then_verify_succeeds(self):
        executable = self.repo / "catalog/codex-global/skills/managed-workflow-execute/SKILL.md"
        executable.chmod(0o755)
        result = self.apply()
        self.assertEqual(result.returncode, 0, result.stdout)
        for name in SKILLS:
            source = self.repo / "catalog/codex-global/skills" / name / "SKILL.md"
            destination = self.home / ".agents/skills" / name / "SKILL.md"
            self.assertEqual(destination.read_bytes(), source.read_bytes())
            self.assertEqual(bool(destination.stat().st_mode & 0o111), bool(source.stat().st_mode & 0o111))
        verified = self.verify()
        self.assertEqual(verified.returncode, 0, verified.stdout)
        self.assertEqual(self.status_lines(verified, "OK"), self.expected("OK"))

    def test_second_apply_is_idempotent_and_preserves_timestamps(self):
        self.assertEqual(self.apply().returncode, 0)
        paths = sorted((self.home / ".agents/skills").glob("*/SKILL.md"))
        before = {path: path.stat().st_mtime_ns for path in paths}
        time.sleep(0.01)
        result = self.apply()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.status_lines(result, "UNCHANGED"), self.expected("UNCHANGED"))
        self.assertEqual({path: path.stat().st_mtime_ns for path in paths}, before)

    def _collision_refuses_all(self, kind):
        target = self.home / ".agents/skills/managed-workflow-plan/SKILL.md"
        target.parent.mkdir(parents=True)
        if kind == "file":
            target.write_bytes(b"different")
        elif kind == "directory":
            target.mkdir()
        else:
            target.symlink_to(self.base / "absent")
        result = self.apply()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TYPE_COLLISION" if kind != "file" else "COLLISION", result.stdout)
        self.assertIn("REFUSED", result.stdout)
        self.assertFalse((self.home / ".agents/skills/managed-workflow-execute/SKILL.md").exists())

    def test_differing_file_collision_refuses_all_writes(self):
        self._collision_refuses_all("file")

    def test_directory_collision_refuses_all_writes(self):
        self._collision_refuses_all("directory")

    def test_symlink_collision_refuses_all_writes(self):
        self._collision_refuses_all("symlink")

    def test_symlink_destination_ancestor_refuses_all_writes(self):
        self.home.mkdir()
        (self.home / ".agents").symlink_to(self.base / "elsewhere")
        result = self.apply()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TYPE_COLLISION", result.stdout)
        self.assertFalse((self.base / "elsewhere").exists())

    def test_symlink_home_refuses_without_writing_through_it(self):
        elsewhere = self.base / "elsewhere"
        elsewhere.mkdir()
        self.home.symlink_to(elsewhere, target_is_directory=True)
        result = self.apply()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TYPE_COLLISION", result.stdout)
        self.assertEqual(list(elsewhere.iterdir()), [])

    def test_non_directory_home_is_type_collision_not_a_crash(self):
        self.home.write_bytes(b"pre-existing")
        result = self.apply()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TYPE_COLLISION", result.stdout)
        self.assertEqual(self.home.read_bytes(), b"pre-existing")

    def test_symlink_in_source_root_chain_is_rejected(self):
        original = self.repo / "catalog/codex-global"
        moved = self.repo / "catalog/actual-codex-global"
        original.rename(moved)
        original.symlink_to(moved, target_is_directory=True)
        result = self.plan()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("VALIDATION_ERROR source symlink", result.stdout)

    def test_source_symlink_is_rejected(self):
        link = self.repo / "catalog/codex-global/skills/managed-workflow-plan/link"
        link.symlink_to(self.base / "outside")
        result = self.plan()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("VALIDATION_ERROR source symlink", result.stdout)

    def test_secret_like_and_generated_sources_rejected_without_contents(self):
        cases = {
            ".env": b"ENV_SENTINEL", ".env.prod": b"PROD_SENTINEL",
            "credentials.txt": b"CRED_SENTINEL", "settings.local.json": b"SETTINGS_SENTINEL",
            "__pycache__": None, "module.pyc": b"PYC_SENTINEL", "module.pyo": b"PYO_SENTINEL",
            "module.pyd": b"PYD_SENTINEL",
        }
        skill = self.repo / "catalog/codex-global/skills/managed-workflow-plan"
        for name, content in cases.items():
            path = skill / name
            if content is None:
                path.mkdir()
                (path / "x").write_bytes(b"CACHE_SENTINEL")
            else:
                path.write_bytes(content)
        result = self.plan()
        self.assertNotEqual(result.returncode, 0)
        for sentinel in ("ENV_SENTINEL", "PROD_SENTINEL", "CRED_SENTINEL", "SETTINGS_SENTINEL",
                         "CACHE_SENTINEL", "PYC_SENTINEL", "PYO_SENTINEL", "PYD_SENTINEL"):
            self.assertNotIn(sentinel, result.stdout)

    def test_unexpected_source_layout_is_rejected(self):
        (self.repo / "catalog/codex-global/skills/extra").mkdir()
        result = self.plan()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("VALIDATION_ERROR unexpected catalog layout", result.stdout)

    def test_exact_catalog_allowlist_rejects_entries_before_home_creation(self):
        cases = (
            ("catalog/sibling.txt", "file"),
            ("catalog/sibling", "directory"),
            ("catalog/codex-global/extra", "file"),
            ("catalog/codex-global/skills/extra", "directory"),
            ("catalog/codex-global/skills/managed-workflow-plan/extra.txt", "file"),
        )
        for index, (relative, kind) in enumerate(cases):
            with self.subTest(relative=relative):
                path = self.repo / relative
                if kind == "directory":
                    path.mkdir()
                else:
                    path.write_bytes(b"unexpected")
                result = self.apply()
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("VALIDATION_ERROR", result.stdout)
                self.assertFalse(self.home.exists())
                if kind == "directory":
                    path.rmdir()
                else:
                    path.unlink()

    def test_catalog_symlinks_at_every_level_refuse_before_home_creation(self):
        targets = (
            "catalog/sibling",
            "catalog/codex-global/extra",
            "catalog/codex-global/skills/extra",
            "catalog/codex-global/skills/managed-workflow-plan/extra",
        )
        for relative in targets:
            with self.subTest(relative=relative):
                link = self.repo / relative
                link.symlink_to(self.base / "outside")
                result = self.apply()
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("VALIDATION_ERROR", result.stdout)
                self.assertFalse(self.home.exists())
                link.unlink()

    def test_active_catalog_chain_and_skill_symlinks_refuse_before_home_creation(self):
        relatives = (
            "catalog",
            "catalog/codex-global/skills",
            "catalog/codex-global/skills/managed-workflow-plan",
        )
        for index, relative in enumerate(relatives):
            with self.subTest(relative=relative):
                path = self.repo / relative
                held = path.with_name(path.name + f"-held-{index}")
                path.rename(held)
                path.symlink_to(held, target_is_directory=True)
                try:
                    result = self.apply()
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn("VALIDATION_ERROR", result.stdout)
                    self.assertFalse(self.home.exists())
                finally:
                    path.unlink()
                    held.rename(path)

    def test_verify_reports_missing(self):
        result = self.verify()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.status_lines(result, "MISSING"), self.expected("MISSING"))
        self.assertFalse(self.home.exists())

    def test_verify_reports_different_bytes(self):
        self.assertEqual(self.apply().returncode, 0)
        target = self.home / ".agents/skills/managed-workflow-plan/SKILL.md"
        target.write_bytes(b"different")
        result = self.verify()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DIFFERENT .agents/skills/managed-workflow-plan/SKILL.md", result.stdout)

    def test_verify_reports_different_executable_state(self):
        self.assertEqual(self.apply().returncode, 0)
        target = self.home / ".agents/skills/managed-workflow-plan/SKILL.md"
        target.chmod(target.stat().st_mode | 0o111)
        result = self.verify()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DIFFERENT .agents/skills/managed-workflow-plan/SKILL.md", result.stdout)

    def test_verify_reports_type_mismatch_for_directory_and_symlink(self):
        target = self.home / ".agents/skills/managed-workflow-plan/SKILL.md"
        target.mkdir(parents=True)
        result = self.verify()
        self.assertIn("TYPE_MISMATCH .agents/skills/managed-workflow-plan/SKILL.md", result.stdout)
        shutil.rmtree(target)
        target.symlink_to(self.base / "absent")
        result = self.verify()
        self.assertIn("TYPE_MISMATCH .agents/skills/managed-workflow-plan/SKILL.md", result.stdout)

    def test_verify_ignores_unrelated_files(self):
        self.assertEqual(self.apply().returncode, 0)
        extra = self.home / ".agents/skills/unrelated.txt"
        extra.write_bytes(b"keep")
        result = self.verify()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(extra.read_bytes(), b"keep")

    def test_real_home_apply_refuses_before_deployment_function(self):
        module = self.load_deploy("fixture_deploy_guard")
        with mock.patch.object(module, "apply") as deployment:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = module.main(["apply", "--home", str(Path.home())])
        self.assertEqual(result, 1)
        self.assertIn("REFUSED", output.getvalue())
        deployment.assert_not_called()

    def test_real_home_aliases_refuse_before_deployment_function(self):
        module = self.load_deploy("fixture_deploy_alias_guard")
        alias = self.base / "home-alias"
        alias.symlink_to(Path.home(), target_is_directory=True)
        candidates = (alias, Path.home().resolve())
        for candidate in candidates:
            with self.subTest(candidate=candidate), mock.patch.object(module, "apply") as deployment:
                with contextlib.redirect_stdout(io.StringIO()):
                    result = module.main(["apply", "--home", str(candidate)])
                self.assertEqual(result, 1)
                deployment.assert_not_called()

    def test_normal_fake_home_is_not_real_home_identity(self):
        module = self.load_deploy("fixture_deploy_fake_guard")
        self.assertFalse(module._is_real_home(self.home))

    def test_physical_path_of_symlinked_path_home_is_real_home(self):
        module = self.load_deploy("fixture_deploy_physical_guard")
        physical = self.base / "physical-home"
        physical.mkdir()
        linked_home = self.base / "linked-home"
        linked_home.symlink_to(physical, target_is_directory=True)
        with mock.patch.object(module.Path, "home", return_value=linked_home):
            self.assertTrue(module._is_real_home(physical))

    def test_calling_outside_repository_finds_catalog(self):
        outside = self.base / "outside"
        outside.mkdir()
        result = self.run_deploy("plan", "--home", str(self.home), cwd=outside)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.status_lines(result, "CREATE"), self.expected("CREATE"))

    def test_output_order_is_deterministic_and_relative(self):
        first, second = self.plan(), self.plan()
        self.assertEqual(first.stdout, second.stdout)
        lines = sorted(self.status_lines(first, "CREATE"))
        self.assertEqual(first.stdout.splitlines(), lines)
        self.assertNotIn(str(self.base), first.stdout)

    def test_no_legacy_client_directory_is_created_or_named(self):
        result = self.apply()
        self.assertEqual(result.returncode, 0, result.stdout)
        forbidden = ".cl" + "aude"
        self.assertNotIn(forbidden, result.stdout.lower())
        self.assertFalse((self.home / forbidden).exists())

    def test_runtime_failure_rolls_back_transaction_files(self):
        module = self.load_deploy("fixture_deploy_failure")
        original = module._publish
        count = 0
        preserved = self.home / ".agents/skills/pre-existing.txt"
        preserved.parent.mkdir(parents=True)
        preserved.write_bytes(b"keep")
        def fail_second(source, home_fd, parent_fd, parent_parts, final_name):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError("simulated")
            original(source, home_fd, parent_fd, parent_parts, final_name)
        with mock.patch.object(module, "_publish", side_effect=fail_second):
            with contextlib.redirect_stdout(io.StringIO()):
                result = module.apply(self.repo, self.home)
        self.assertEqual(result, 1)
        self.assertFalse(any(self.home.rglob("SKILL.md")) if self.home.exists() else False)
        self.assertEqual(preserved.read_bytes(), b"keep")
        self.assertFalse(any(self.base.rglob(".codex-deploy-*")))

    def test_unsupported_descriptor_platform_refuses_before_mutation(self):
        module = self.load_deploy("fixture_deploy_capability")
        with mock.patch.object(module, "_descriptor_platform_supported", return_value=False):
            with contextlib.redirect_stdout(io.StringIO()):
                result = module.apply(self.repo, self.home)
        self.assertEqual(result, 1)
        self.assertFalse(self.home.exists())

    def test_home_ancestor_swap_after_preflight_cannot_escape(self):
        module = self.load_deploy("fixture_deploy_home_swap")
        self.home.mkdir()
        agents = self.home / ".agents"
        agents.mkdir()
        outside = self.base / "outside"
        outside.mkdir()
        original = module._open_home_anchor
        def swap_then_open(home, created_directories):
            agents.rmdir()
            agents.symlink_to(outside, target_is_directory=True)
            return original(home, created_directories)
        with mock.patch.object(module, "_open_home_anchor", side_effect=swap_then_open):
            with contextlib.redirect_stdout(io.StringIO()):
                result = module.apply(self.repo, self.home)
        self.assertEqual(result, 1)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse(any(self.base.rglob(".codex-deploy-*")))

    def test_parent_swap_immediately_before_publication_cannot_escape(self):
        module = self.load_deploy("fixture_deploy_parent_swap")
        outside = self.base / "outside"
        outside.mkdir()
        original = module._publish
        swapped = False
        def swap_then_publish(source, home_fd, parent_fd, parent_parts, final_name):
            nonlocal swapped
            if not swapped:
                skills = self.home / ".agents/skills"
                moved = self.home / ".agents/held-skills"
                skills.rename(moved)
                skills.symlink_to(outside, target_is_directory=True)
                swapped = True
            return original(source, home_fd, parent_fd, parent_parts, final_name)
        with mock.patch.object(module, "_publish", side_effect=swap_then_publish):
            with contextlib.redirect_stdout(io.StringIO()):
                result = module.apply(self.repo, self.home)
        self.assertEqual(result, 1)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse(any(self.base.rglob(".codex-deploy-*")))

    def test_concurrent_final_file_is_preserved_and_apply_refuses(self):
        module = self.load_deploy("fixture_deploy_final_race")
        original = module._publish
        injected = False
        concurrent = b"concurrent"
        def create_then_publish(source, home_fd, parent_fd, parent_parts, final_name):
            nonlocal injected
            if not injected:
                descriptor = os.open(final_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600,
                                     dir_fd=parent_fd)
                os.write(descriptor, concurrent)
                os.close(descriptor)
                injected = True
            return original(source, home_fd, parent_fd, parent_parts, final_name)
        with mock.patch.object(module, "_publish", side_effect=create_then_publish):
            with contextlib.redirect_stdout(io.StringIO()):
                result = module.apply(self.repo, self.home)
        target = self.home / ".agents/skills/managed-workflow-execute/SKILL.md"
        self.assertEqual(result, 1)
        self.assertEqual(target.read_bytes(), concurrent)
        self.assertFalse(any(self.base.rglob(".codex-deploy-*")))

    def test_no_staging_files_remain_after_success_or_collision(self):
        self.assertEqual(self.apply().returncode, 0)
        self.assertFalse(any(self.home.rglob(".codex-deploy-*")))
        target = self.home / ".agents/skills/managed-workflow-plan/SKILL.md"
        target.write_bytes(b"collision")
        self.assertNotEqual(self.apply().returncode, 0)
        self.assertFalse(any(self.home.rglob(".codex-deploy-*")))

    def test_publish_staging_unlink_failure_removes_final_and_staging(self):
        module = self.load_deploy("fixture_deploy_staging_unlink_failure")
        preserved = self.home / ".agents/skills/pre-existing.txt"
        preserved.parent.mkdir(parents=True)
        preserved.write_bytes(b"keep")
        original_unlink = module.os.unlink
        failed = False

        def fail_staging_once(path, *args, **kwargs):
            nonlocal failed
            if not failed and os.fspath(path).startswith(".codex-deploy-"):
                failed = True
                raise OSError("simulated staging cleanup failure")
            return original_unlink(path, *args, **kwargs)

        with mock.patch.object(module, "_descriptor_platform_supported", return_value=True), \
                mock.patch.object(module.os, "unlink", side_effect=fail_staging_once):
            with contextlib.redirect_stdout(io.StringIO()):
                result = module.apply(self.repo, self.home)
        self.assertEqual(result, 1)
        self.assertTrue(failed)
        self.assertFalse(any(self.home.rglob("SKILL.md")))
        self.assertFalse(any(self.home.rglob(".codex-deploy-*")))
        self.assertEqual(preserved.read_bytes(), b"keep")

    def test_publish_parent_fsync_failure_removes_final(self):
        module = self.load_deploy("fixture_deploy_parent_fsync_failure")
        preserved = self.home / ".agents/skills/pre-existing.txt"
        preserved.parent.mkdir(parents=True)
        preserved.write_bytes(b"keep")
        original_fsync = module.os.fsync
        calls = 0

        def fail_post_publication_once(descriptor):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated parent fsync failure")
            return original_fsync(descriptor)

        with mock.patch.object(module.os, "fsync", side_effect=fail_post_publication_once):
            with contextlib.redirect_stdout(io.StringIO()):
                result = module.apply(self.repo, self.home)
        self.assertEqual(result, 1)
        self.assertFalse(any(self.home.rglob("SKILL.md")))
        self.assertEqual(preserved.read_bytes(), b"keep")

    def test_publish_cleanup_failure_reports_relative_rollback_failure(self):
        module = self.load_deploy("fixture_deploy_publish_rollback_failure")
        original_unlink = module.os.unlink
        staging_failed = False

        def fail_staging_and_final(path, *args, **kwargs):
            nonlocal staging_failed
            shown = os.fspath(path)
            if shown.startswith(".codex-deploy-") and not staging_failed:
                staging_failed = True
                raise OSError("simulated staging cleanup failure")
            if shown == "SKILL.md":
                raise OSError("simulated final cleanup failure")
            return original_unlink(path, *args, **kwargs)

        output = io.StringIO()
        with mock.patch.object(module, "_descriptor_platform_supported", return_value=True), \
                mock.patch.object(module.os, "unlink", side_effect=fail_staging_and_final):
            with contextlib.redirect_stdout(output):
                result = module.apply(self.repo, self.home)
        managed = ".agents/skills/managed-workflow-execute/SKILL.md"
        self.assertEqual(result, 1)
        self.assertIn(f"ROLLBACK_FAILED {managed}", output.getvalue())
        self.assertNotIn(str(self.home), output.getvalue())
        self.assertNotIn("managed-workflow-execute\n", output.getvalue())
        self.assertTrue((self.home / managed).exists())  # Rollback failed, so publication may remain.

    def test_successful_apply_has_all_destinations_and_no_staging(self):
        result = self.apply()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(
            {path.relative_to(self.home).as_posix() for path in self.home.rglob("SKILL.md")},
            {f".agents/skills/{name}/SKILL.md" for name in SKILLS},
        )
        self.assertFalse(any(self.home.rglob(".codex-deploy-*")))


if __name__ == "__main__":
    unittest.main()
