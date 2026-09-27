import importlib.util
import json
import os
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
