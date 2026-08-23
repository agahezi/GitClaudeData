#!/usr/bin/env python3
"""Produce a deterministic, non-mutating deployment plan."""

import argparse
import os
import stat
import sys
from pathlib import Path, PurePosixPath


CLAUDE_MAPPINGS = (
    (PurePosixPath("shared-global/skills"), PurePosixPath(".claude/skills")),
    (PurePosixPath("claude-global/skills"), PurePosixPath(".claude/skills")),
    (PurePosixPath("claude-global/commands"), PurePosixPath(".claude/commands")),
    (PurePosixPath("claude-global/agents"), PurePosixPath(".claude/agents")),
    (PurePosixPath("claude-global/legacy/skills"), PurePosixPath(".claude/skills")),
)
CODEX_MAPPING = (
    PurePosixPath("shared-global/skills"),
    PurePosixPath(".agents/skills"),
)


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", nargs="?", default="plan", choices=("plan",))
    parser.add_argument("--target", choices=("claude", "codex"), default="claude")
    parser.add_argument("--home", type=Path, default=Path(os.environ.get("HOME", "")))
    return parser.parse_args(argv)


def display_catalog(relative):
    return (PurePosixPath("catalog") / relative).as_posix()


def rejected(relative):
    for component in relative.parts:
        lowered = component.lower()
        if lowered == ".env" or lowered.startswith(".env."):
            return True
        if "credential" in lowered:
            return True
        if lowered == "settings.local.json" or lowered == "__pycache__":
            return True
        if lowered.endswith((".pyc", ".pyo", ".pyd")):
            return True
    return False


def allowed_layout(relative, roots):
    return any(relative == root or relative.is_relative_to(root) or root.is_relative_to(relative) for root in roots)


def scan_catalog(catalog, roots):
    """Validate catalog layout and return regular files below explicit roots."""
    errors = []
    files = []
    if not catalog.is_dir():
        return files, ["VALIDATION_ERROR unexpected catalog layout: catalog"]

    for current, directory_names, file_names in os.walk(catalog, topdown=True, followlinks=False):
        current_path = Path(current)
        directory_names.sort()
        file_names.sort()
        entries = [(name, True) for name in directory_names] + [(name, False) for name in file_names]
        for name, is_directory in sorted(entries):
            path = current_path / name
            relative = PurePosixPath(path.relative_to(catalog).as_posix())
            shown = display_catalog(relative)
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode):
                errors.append("VALIDATION_ERROR source symlink: " + shown)
                if is_directory:
                    directory_names.remove(name)
                continue
            if not allowed_layout(relative, roots):
                errors.append("VALIDATION_ERROR unexpected catalog layout: " + shown)
                if is_directory:
                    directory_names.remove(name)
                continue
            if rejected(relative):
                errors.append("VALIDATION_ERROR rejected source path: " + shown)
                continue
            if not is_directory:
                if stat.S_ISREG(mode):
                    files.append(relative)
                else:
                    errors.append("VALIDATION_ERROR non-regular source: " + shown)
    return sorted(files, key=lambda item: item.as_posix()), sorted(errors)


def mapped_artifacts(files, mappings):
    artifacts = []
    for source_root, destination_root in mappings:
        for source in files:
            if source.is_relative_to(source_root):
                artifacts.append((source, destination_root / source.relative_to(source_root)))
    return sorted(artifacts, key=lambda item: (item[1].as_posix(), item[0].as_posix()))


def classify(source, destination):
    try:
        mode = destination.lstat().st_mode
    except FileNotFoundError:
        return "CREATE"
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        return "TYPE_COLLISION"
    return "UNCHANGED" if source.read_bytes() == destination.read_bytes() else "COLLISION"


def plan_claude(repo_root, home):
    catalog = repo_root / "catalog"
    roots = tuple(source for source, _ in CLAUDE_MAPPINGS)
    files, errors = scan_catalog(catalog, roots)
    print("TARGET claude")
    for error in errors:
        print(error)

    collision = False
    artifacts = mapped_artifacts(files, CLAUDE_MAPPINGS)
    destinations = {}
    for source_relative, destination_relative in artifacts:
        previous = destinations.get(destination_relative)
        if previous is not None:
            print("VALIDATION_ERROR duplicate destination: " + destination_relative.as_posix())
            errors.append("duplicate destination")
            continue
        destinations[destination_relative] = source_relative
        status = classify(catalog / Path(source_relative), home / Path(destination_relative))
        print(status + " " + destination_relative.as_posix())
        collision = collision or status in ("COLLISION", "TYPE_COLLISION")
    return 1 if errors or collision else 0


def plan_codex(repo_root):
    catalog = repo_root / "catalog"
    source_root, destination_root = CODEX_MAPPING
    validation_roots = tuple(source for source, _ in CLAUDE_MAPPINGS)
    files, errors = scan_catalog(catalog, validation_roots)
    print("TARGET codex")
    print("MAPPING catalog/shared-global/skills/* -> HOME/.agents/skills/*")
    for error in errors:
        print(error)
    for _, destination in mapped_artifacts(files, (CODEX_MAPPING,)):
        print("INELIGIBLE " + destination.as_posix())
    print("INELIGIBLE behavioral compatibility gates have not passed")
    return 1


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = Path(__file__).resolve().parents[1]
    if args.target == "codex":
        return plan_codex(repo_root)
    return plan_claude(repo_root, args.home)


if __name__ == "__main__":
    raise SystemExit(main())
