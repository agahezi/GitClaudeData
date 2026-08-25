#!/usr/bin/env python3
"""Plan, apply, or verify the repository's create-only Codex skill deployment."""

import argparse
import os
import stat
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

SKILL_NAMES = ("managed-workflow-execute", "managed-workflow-plan", "managed-workflow-verify")
SOURCE_PREFIX = PurePosixPath("codex-global/skills")
DESTINATION_PREFIX = PurePosixPath(".agents/skills")


@dataclass(frozen=True)
class Artifact:
    source: Path
    destination_relative: PurePosixPath


class RollbackFailed(Exception):
    def __init__(self, destination_relative):
        self.destination_relative = destination_relative
        super().__init__(destination_relative.as_posix())


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", nargs="?", default="plan", choices=("plan", "apply", "verify"))
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--allow-real-home", action="store_true")
    return parser.parse_args(argv)


def _rejected(relative):
    for component in relative.parts:
        lowered = component.lower()
        if lowered == ".env" or lowered.startswith(".env.") or "credential" in lowered:
            return True
        if lowered in {"settings.local.json", "__pycache__"}:
            return True
        if lowered.endswith((".pyc", ".pyo", ".pyd")):
            return True
    return False


def scan_source(repo_root):
    catalog = repo_root / "catalog"
    source_root = catalog / Path(SOURCE_PREFIX)
    errors, artifacts = [], []
    expected_directories = {PurePosixPath(name) for name in SKILL_NAMES}
    chain = (catalog, catalog / "codex-global", source_root)
    try:
        chain_modes = [path.lstat().st_mode for path in chain]
    except FileNotFoundError:
        return [], ["VALIDATION_ERROR unexpected catalog layout"]
    if any(stat.S_ISLNK(mode) for mode in chain_modes):
        return [], ["VALIDATION_ERROR source symlink: catalog/codex-global/skills"]
    if any(not stat.S_ISDIR(mode) for mode in chain_modes):
        return [], ["VALIDATION_ERROR unexpected catalog layout"]

    allowed = {
        catalog: {"codex-global"},
        catalog / "codex-global": {"skills"},
        source_root: set(SKILL_NAMES),
    }
    for directory, expected in allowed.items():
        try:
            names = {entry.name for entry in os.scandir(directory)}
        except OSError:
            return [], ["VALIDATION_ERROR unexpected catalog layout"]
        for name in sorted(names | expected):
            path = directory / name
            shown = path.relative_to(repo_root).as_posix()
            if name not in expected:
                try:
                    is_link = stat.S_ISLNK(path.lstat().st_mode)
                except OSError:
                    is_link = False
                kind = "source symlink" if is_link else "unexpected catalog layout"
                errors.append(f"VALIDATION_ERROR {kind}: {shown}")
            elif name not in names:
                errors.append(f"VALIDATION_ERROR unexpected catalog layout: missing {shown}")

    for name in SKILL_NAMES:
        skill = source_root / name
        try:
            entries = list(os.scandir(skill))
        except OSError:
            continue
        for entry in sorted(entries, key=lambda item: item.name):
            if entry.name != "SKILL.md":
                shown = (skill / entry.name).relative_to(repo_root).as_posix()
                kind = "source symlink" if entry.is_symlink() else "unexpected catalog layout"
                errors.append(f"VALIDATION_ERROR {kind}: {shown}")

    seen_directories = set()
    for current, directory_names, file_names in os.walk(source_root, topdown=True, followlinks=False):
        current_path = Path(current)
        directory_names.sort()
        file_names.sort()
        for name in list(directory_names):
            path = current_path / name
            relative = PurePosixPath(path.relative_to(source_root).as_posix())
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode):
                errors.append(f"VALIDATION_ERROR source symlink: catalog/{SOURCE_PREFIX / relative}")
                directory_names.remove(name)
            elif not stat.S_ISDIR(mode) or relative not in expected_directories:
                errors.append(f"VALIDATION_ERROR unexpected catalog layout: catalog/{SOURCE_PREFIX / relative}")
                directory_names.remove(name)
            else:
                seen_directories.add(relative)
        for name in file_names:
            path = current_path / name
            relative = PurePosixPath(path.relative_to(source_root).as_posix())
            shown = SOURCE_PREFIX / relative
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode):
                errors.append(f"VALIDATION_ERROR source symlink: catalog/{shown}")
            elif _rejected(relative):
                errors.append(f"VALIDATION_ERROR rejected source path: catalog/{shown}")
            elif not stat.S_ISREG(mode):
                errors.append(f"VALIDATION_ERROR non-regular source: catalog/{shown}")
            elif len(relative.parts) != 2 or relative.parts[0] not in SKILL_NAMES or relative.name != "SKILL.md":
                errors.append(f"VALIDATION_ERROR unexpected catalog layout: catalog/{shown}")
            else:
                artifacts.append(Artifact(path, DESTINATION_PREFIX / relative))
    if seen_directories != expected_directories:
        errors.append("VALIDATION_ERROR unexpected catalog layout: missing skill directory")
    if {item.destination_relative.parts[-2] for item in artifacts} != set(SKILL_NAMES):
        errors.append("VALIDATION_ERROR unexpected catalog layout: missing SKILL.md")
    return sorted(artifacts, key=lambda item: item.destination_relative.as_posix()), sorted(set(errors))


def _regular_signature(path):
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as stream:
        mode = os.fstat(stream.fileno()).st_mode
        if not stat.S_ISREG(mode):
            raise OSError("non-regular file")
        return stream.read(), bool(mode & 0o111)


def _same_file(source, destination):
    return _regular_signature(source) == _regular_signature(destination)


def _home_problem(home):
    absolute = Path(os.path.abspath(os.fspath(home)))
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            return None
        if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
            return current
    return None


def _ancestor_problem(home, relative):
    problem = _home_problem(home)
    if problem is not None:
        return problem
    current = home
    for part in relative.parts[:-1]:
        current = current / part
        try:
            mode = current.lstat().st_mode
        except (FileNotFoundError, NotADirectoryError):
            return None
        if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
            return current
    return None


def classify(source, home, relative, verify=False):
    if _ancestor_problem(home, relative) is not None:
        return "TYPE_MISMATCH" if verify else "TYPE_COLLISION"
    destination = home / Path(relative)
    try:
        mode = destination.lstat().st_mode
    except FileNotFoundError:
        return "MISSING" if verify else "CREATE"
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        return "TYPE_MISMATCH" if verify else "TYPE_COLLISION"
    same = _same_file(source, destination)
    return ("OK" if same else "DIFFERENT") if verify else ("UNCHANGED" if same else "COLLISION")


def _load(repo_root):
    artifacts, errors = scan_source(repo_root)
    for error in errors:
        print(error)
    return artifacts, errors


def plan(repo_root, home):
    artifacts, errors = _load(repo_root)
    statuses = []
    for item in artifacts:
        status = classify(item.source, home, item.destination_relative)
        statuses.append(status)
        print(f"{status} {item.destination_relative.as_posix()}")
    return int(bool(errors or any(status in {"COLLISION", "TYPE_COLLISION"} for status in statuses)))


def _descriptor_platform_supported():
    required = (os.open, os.mkdir, os.unlink, os.rmdir, os.stat)
    return (
        hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY")
        and all(operation in os.supports_dir_fd for operation in required)
        and os.link in os.supports_dir_fd and os.chmod in os.supports_fd
    )


def _directory_flags():
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def _open_component(parent_fd, name, created_directories):
    try:
        return os.open(name, _directory_flags(), dir_fd=parent_fd)
    except FileNotFoundError:
        os.mkdir(name, 0o755, dir_fd=parent_fd)
        cleanup_parent = os.dup(parent_fd)
        created_directories.append((cleanup_parent, name))
        try:
            return os.open(name, _directory_flags(), dir_fd=parent_fd)
        except Exception:
            os.rmdir(name, dir_fd=parent_fd)
            os.close(cleanup_parent)
            created_directories.pop()
            raise


def _open_home_anchor(home, created_directories=None):
    created_directories = [] if created_directories is None else created_directories
    absolute = Path(os.path.abspath(os.fspath(home)))
    descriptor = os.open(absolute.anchor, _directory_flags())
    try:
        for part in absolute.parts[1:]:
            child = _open_component(descriptor, part, created_directories)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _open_parent(home_fd, relative, created_directories):
    descriptor = os.dup(home_fd)
    try:
        for part in relative.parts[:-1]:
            child = _open_component(descriptor, part, created_directories)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _parent_is_attached(home_fd, parts, parent_fd):
    descriptor = os.dup(home_fd)
    try:
        for part in parts:
            child = os.open(part, _directory_flags(), dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        left, right = os.fstat(descriptor), os.fstat(parent_fd)
        return (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)
    except OSError:
        return False
    finally:
        os.close(descriptor)


def _publish(source, home_fd, parent_fd, parent_parts, final_name):
    if not _parent_is_attached(home_fd, parent_parts, parent_fd):
        raise OSError("destination parent changed")
    descriptor = None
    temporary = None
    published = False
    staged_identity = None
    try:
        for candidate in tempfile._get_candidate_names():
            temporary = ".codex-deploy-" + candidate
            try:
                descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                     0o600, dir_fd=parent_fd)
                break
            except FileExistsError:
                continue
        if descriptor is None:
            raise OSError("unable to create staging file")
        source_bytes, source_executable = _regular_signature(source)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(source_bytes)
            stream.flush()
            os.fchmod(stream.fileno(), 0o755 if source_executable else 0o644)
            os.fsync(stream.fileno())
            staged = os.fstat(stream.fileno())
            staged_identity = (staged.st_dev, staged.st_ino)
        if not _parent_is_attached(home_fd, parent_parts, parent_fd):
            raise OSError("destination parent changed")
        os.link(temporary, final_name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd,
                follow_symlinks=False)
        published = True
        try:
            if not _parent_is_attached(home_fd, parent_parts, parent_fd):
                raise OSError("destination parent changed")
            os.unlink(temporary, dir_fd=parent_fd)
            temporary = None
            os.fsync(parent_fd)
        except Exception as error:
            rollback_failed = False
            try:
                final = os.stat(final_name, dir_fd=parent_fd, follow_symlinks=False)
                if (final.st_dev, final.st_ino) != staged_identity:
                    raise OSError("published destination identity changed")
                os.unlink(final_name, dir_fd=parent_fd)
                published = False
                os.fsync(parent_fd)
            except OSError:
                rollback_failed = True
            if temporary is not None:
                try:
                    os.unlink(temporary, dir_fd=parent_fd)
                    temporary = None
                    os.fsync(parent_fd)
                except OSError:
                    rollback_failed = True
            if rollback_failed:
                relative = PurePosixPath(*parent_parts, final_name)
                raise RollbackFailed(relative) from error
            raise
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary is not None and not published:
            try:
                os.unlink(temporary, dir_fd=parent_fd)
            finally:
                os.fsync(parent_fd)
    return published


def apply(repo_root, home):
    if not _descriptor_platform_supported():
        print("REFUSED platform lacks safe descriptor-relative deployment support")
        return 1
    artifacts, errors = _load(repo_root)
    classified = [(item, classify(item.source, home, item.destination_relative)) for item in artifacts]
    for item, status in classified:
        print(f"{status} {item.destination_relative.as_posix()}")
    if errors or any(status in {"COLLISION", "TYPE_COLLISION"} for _, status in classified):
        print("REFUSED deployment preflight failed")
        return 1
    created_files, created_directories = [], []
    home_fd = None
    try:
        home_fd = _open_home_anchor(home, created_directories)
        for item, status in classified:
            if status == "UNCHANGED":
                continue
            parent_fd = _open_parent(home_fd, item.destination_relative, created_directories)
            try:
                parent_parts = item.destination_relative.parts[:-1]
                _publish(item.source, home_fd, parent_fd, parent_parts,
                         item.destination_relative.name)
                created_files.append((os.dup(parent_fd), item.destination_relative.name))
            finally:
                os.close(parent_fd)
    except Exception as error:
        for parent_fd, name in reversed(created_files):
            try:
                os.unlink(name, dir_fd=parent_fd)
                os.fsync(parent_fd)
            except FileNotFoundError:
                pass
            finally:
                os.close(parent_fd)
        for parent_fd, name in reversed(created_directories):
            try:
                os.rmdir(name, dir_fd=parent_fd)
                os.fsync(parent_fd)
            except OSError:
                pass
            finally:
                os.close(parent_fd)
        if isinstance(error, RollbackFailed):
            print(f"ROLLBACK_FAILED {error.destination_relative.as_posix()}")
        else:
            print(f"REFUSED runtime failure: {type(error).__name__}")
        return 1
    finally:
        if home_fd is not None:
            os.close(home_fd)
    for parent_fd, _ in created_files:
        os.close(parent_fd)
    for parent_fd, _ in created_directories:
        os.close(parent_fd)
    return 0


def verify(repo_root, home):
    artifacts, errors = _load(repo_root)
    statuses = []
    for item in artifacts:
        status = classify(item.source, home, item.destination_relative, verify=True)
        statuses.append(status)
        print(f"{status} {item.destination_relative.as_posix()}")
    return 0 if not errors and statuses and all(status == "OK" for status in statuses) else 1


def _same_lexical_path(left, right):
    return os.path.abspath(os.fspath(left)) == os.path.abspath(os.fspath(right))


def _is_real_home(home):
    real_home = Path.home()
    if _same_lexical_path(home, real_home):
        return True
    try:
        if Path(home).resolve(strict=False) == real_home.resolve(strict=False):
            return True
    except (PermissionError, RuntimeError):
        return True
    except OSError:
        return True
    try:
        return os.path.samefile(home, real_home)
    except FileNotFoundError:
        return False
    except (PermissionError, OSError):
        return True


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = Path(__file__).resolve().parents[1]
    if args.operation == "apply" and _is_real_home(args.home) and not args.allow_real_home:
        print("REFUSED real home requires --allow-real-home")
        return 1
    return {"plan": plan, "apply": apply, "verify": verify}[args.operation](repo_root, args.home)


if __name__ == "__main__":
    raise SystemExit(main())
