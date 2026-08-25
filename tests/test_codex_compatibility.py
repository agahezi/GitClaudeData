import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog" / "codex-global"
SKILLS = CATALOG / "skills"
EXPECTED = {
    "managed-workflow-plan",
    "managed-workflow-execute",
    "managed-workflow-verify",
}
PROHIBITED = (
    "cl" + "aude",
    ".cl" + "aude",
    "CL".lower() + "AUDE".lower() + ".md",
    "superpowers:brainstorming",
    "superpowers:writing-plans",
    "gsd-code-reviewer",
)


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return {}, text
    try:
        end = lines.index("---", 1)
    except ValueError:
        return {}, text
    values = {}
    for line in lines[1:end]:
        match = re.fullmatch(r"([a-z][a-z0-9_-]*):\s*(.+)", line)
        if not match:
            return {}, text
        values[match.group(1)] = match.group(2).strip().strip('"\'')
    return values, text


class CodexCompatibilityTests(unittest.TestCase):
    def test_exactly_intended_skills_exist_with_valid_unique_metadata(self):
        skill_files = sorted(SKILLS.glob("*/SKILL.md")) if SKILLS.exists() else []
        self.assertEqual({path.parent.name for path in skill_files}, EXPECTED)
        self.assertEqual(len(skill_files), 3)
        names = []
        for path in skill_files:
            metadata, _ = frontmatter(path)
            self.assertEqual(metadata.get("name"), path.parent.name, path)
            self.assertTrue(metadata.get("description"), path)
            self.assertEqual(set(metadata), {"name", "description"}, path)
            names.append(metadata["name"])
        self.assertEqual(len(names), len(set(names)))

    def test_active_tree_has_no_prohibited_client_or_dependency_references(self):
        roots = [ROOT / "AGENTS.md", ROOT / "catalog", ROOT / "scripts", ROOT / "tests", ROOT / "docs"]
        excluded = {ROOT / "docs" / "migration.md", Path(__file__).resolve()}
        for root in roots:
            paths = [root] if root.is_file() else sorted(root.rglob("*")) if root.exists() else []
            for path in paths:
                if not path.is_file() or path in excluded:
                    continue
                text = path.read_text(encoding="utf-8", errors="replace").lower()
                for needle in PROHIBITED:
                    self.assertNotIn(needle, text, f"{needle!r} in {path.relative_to(ROOT)}")

    def test_removed_legacy_paths_are_absent(self):
        self.assertFalse((ROOT / "catalog" / ("cl" + "aude-global")).exists())
        self.assertFalse(any(ROOT.rglob("format-stream.py")))

    def test_deployable_catalog_is_safe_and_contains_no_symlinks(self):
        self.assertTrue(CATALOG.is_dir())
        for path in sorted(CATALOG.rglob("*")):
            relative = path.relative_to(CATALOG)
            lowered = [part.lower() for part in relative.parts]
            self.assertFalse(path.is_symlink(), relative)
            self.assertNotIn("__pycache__", lowered, relative)
            self.assertNotIn("settings.local.json", lowered, relative)
            self.assertFalse(any("credential" in part for part in lowered), relative)
            self.assertFalse(any(part == ".env" or part.startswith(".env.") for part in lowered), relative)
            self.assertFalse(path.suffix.lower() in {".pyc", ".pyo", ".pyd"}, relative)

    def test_agents_is_codex_only_authority(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("Codex is the only supported coding-agent client", text)
        self.assertIn("instruction authority", text)

    def test_compatibility_matrix_has_no_unresolved_review(self):
        text = (ROOT / "docs" / "compatibility-matrix.md").read_text(encoding="utf-8")
        unresolved = [line for line in text.splitlines() if re.search(r"\|\s*REVIEW\s*\|", line)]
        self.assertEqual(unresolved, [])


if __name__ == "__main__":
    unittest.main()
