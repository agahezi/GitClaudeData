#!/usr/bin/env python3
"""Manage every skill for Claude Code and Codex from this repository.

commands:
  add <link>   copy a downloaded skill into skills/ (GitHub link, web page, zip, or local folder)
  install      install all skills and plugins into both tools, verify, then offer newer versions
  update       check downloaded skills and plugins for newer versions and apply the ones you accept
  verify       check that every skill and plugin is installed correctly in both tools
  plan         show what install would change, without changing anything
"""

import argparse
import datetime
import hashlib
import html
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILLS_DIR = "skills"
PLUGINS_FILE = "plugins.json"
METADATA = ".skill.json"
MANAGER_DIR = ".skill-manager"
TARGETS = {"codex": ".agents/skills", "claude": ".claude/skills"}
NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PLUGIN_ID = re.compile(r"^[\w.-]+@[\w.-]+$")
MARKETPLACE = re.compile(r"^[\w./:@-]+$")
GITHUB_LINK = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+(?:/(?:tree|blob)/[^\s\"'<>#?]+)?")
NPX_SKILLS = re.compile(r"npx\s+(?:-y\s+)?skills(?:@[\w.-]+)?\s+add\s+(?:https://github\.com/)?([\w.-]+/[\w.-]+)")
CLAUDE_ONLY_FRONTMATTER = ("allowed-tools", "model", "hooks", "context", "agent")
CLAUDE_ONLY_TEXT = ("CLAUDE_PLUGIN_ROOT", "CLAUDE_SKILL_DIR", "TodoWrite", "AskUserQuestion", "Task tool")
MAX_DOWNLOAD = 100 * 1024 * 1024
OFFICIAL_MARKETPLACE = "claude-plugins-official"
REPARSE_POINT = 0x400
NOTES = {
    "CONFLICT": " (exists but was changed locally or is not managed by this repo)",
    "BLOCKED": " (a parent folder is a link or a file; fix it manually)",
    "REMOVE": " (no longer in the repo)",
    "KEEP": " (no longer in the repo but changed locally; left in place)",
}


class SkillError(Exception):
    pass


class Prompter:
    def __init__(self, assume_defaults):
        self.assume_defaults = assume_defaults

    def confirm(self, question, default):
        hint = "[Y/n]" if default else "[y/N]"
        if self.assume_defaults:
            print(f"{question} {hint} {'y' if default else 'n'} (default)")
            return default
        try:
            answer = input(f"{question} {hint} ").strip().lower()
        except EOFError:
            print()
            return default
        return default if not answer else answer in ("y", "yes")

    def choose(self, question, options):
        if len(options) == 1:
            print(f"Using {options[0]}")
            return options[0]
        for index, option in enumerate(options, 1):
            print(f"  {index}. {option}")
        if self.assume_defaults:
            raise SkillError("several links found; run again without --yes and pick one")
        try:
            answer = input(f"{question} [1-{len(options)}] ").strip()
        except EOFError:
            answer = ""
        if answer.isdigit() and 1 <= int(answer) <= len(options):
            return options[int(answer) - 1]
        raise SkillError("no link selected")


class Skill:
    def __init__(self, name, files, targets, metadata):
        self.name, self.files, self.targets, self.metadata = name, files, targets, metadata


# ---------- files ----------

def is_link(path):
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & REPARSE_POINT)


def rejected(name):
    lowered = name.lower()
    return (lowered in {".env", "settings.local.json", "__pycache__", ".git", ".ds_store"}
            or lowered.startswith(".env.") or "credential" in lowered
            or lowered.endswith((".pyc", ".pyo", ".pyd")))


def read_tree(root, policy="strict"):
    """Return ({posix path: (bytes, executable)}, skipped paths).

    strict: unsafe entries raise; skip: unsafe entries are dropped (imports);
    installed: bytecode caches are ignored, links raise.
    """
    files, skipped = {}, []

    def refuse(path, reason):
        relative = path.relative_to(root).as_posix()
        if policy != "skip":
            raise SkillError(f"{reason}: {relative}")
        skipped.append(relative)

    for current, directories, names in os.walk(root):
        base = Path(current)
        for name in sorted(directories):
            path = base / name
            generated = policy == "installed" and name == "__pycache__"
            if generated or is_link(path) or (policy != "installed" and rejected(name)):
                directories.remove(name)
                if not generated:
                    refuse(path, "link not allowed" if is_link(path) else "file not allowed")
        for name in sorted(names):
            path = base / name
            info = os.lstat(path)
            if policy == "installed" and name.lower().endswith((".pyc", ".pyo")):
                continue
            if is_link(path) or not stat.S_ISREG(info.st_mode):
                refuse(path, "link or special file not allowed")
            elif policy != "installed" and rejected(name):
                refuse(path, "file not allowed")
            else:
                executable = os.name != "nt" and bool(info.st_mode & 0o111)
                files[path.relative_to(root).as_posix()] = (path.read_bytes(), executable)
    return files, skipped


def write_files(folder, files):
    for relative, (data, executable) in files.items():
        path = folder.joinpath(*relative.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        if executable:
            path.chmod(0o755)


def fingerprint(files):
    return {relative: hashlib.sha256(data).hexdigest() + ("+x" if executable else "")
            for relative, (data, executable) in files.items()}


def blocked_path(home, relative):
    """Return the first existing path below home that is a link or not a folder."""
    current = home
    for part in Path(relative).parts:
        current = current / part
        if is_link(current) or (current.exists() and not current.is_dir()):
            return current
        if not current.exists():
            return None
    return None


def ensure_folder(home, relative):
    blocked = blocked_path(home, relative)
    if blocked is not None:
        raise OSError(f"refusing to write through {blocked}")
    (home / relative).mkdir(parents=True, exist_ok=True)


def write_json(path, data):
    path.write_bytes((json.dumps(data, indent=2, sort_keys=True) + "\n").encode("utf-8"))


# ---------- repository catalog ----------

def frontmatter(data):
    lines = data.decode("utf-8", "replace").lstrip("\ufeff").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    values = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return values
        match = re.match(r"([A-Za-z][\w-]*):\s*(.*)$", line)
        if match:
            values[match.group(1)] = match.group(2).strip().strip("\"'")
    return None


def skill_name(files, fallback):
    if "SKILL.md" not in files:
        raise SkillError("SKILL.md is missing")
    meta = frontmatter(files["SKILL.md"][0])
    if meta is None:
        raise SkillError("SKILL.md has no front matter")
    name = meta.get("name") or fallback
    if not NAME.match(name) or len(name) > 64:
        raise SkillError(f"invalid skill name {name!r}; use lowercase letters, digits, and hyphens")
    if not meta.get("description"):
        raise SkillError("SKILL.md front matter needs a description")
    return name


def claude_only_features(files):
    meta = frontmatter(files["SKILL.md"][0]) or {}
    found = [f"front matter '{key}'" for key in CLAUDE_ONLY_FRONTMATTER if key in meta]
    text = b"\n".join(data for relative, (data, _) in files.items()
                      if relative.lower().endswith(".md")).decode("utf-8", "replace")
    return found + [f"'{marker}'" for marker in CLAUDE_ONLY_TEXT if marker in text]


def read_metadata(folder):
    path = folder / METADATA
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise SkillError(f"{METADATA} is not valid JSON")
    if not isinstance(data, dict):
        raise SkillError(f"{METADATA} must contain a JSON object")
    return data


def load_catalog(repo):
    root = repo / SKILLS_DIR
    if is_link(root) or not root.is_dir():
        return [], [f"ERROR {SKILLS_DIR}/ folder is missing"]
    skills, errors = [], []
    for entry in sorted(os.scandir(root), key=lambda item: item.name):
        path = Path(entry.path)
        if entry.name.startswith(".") and entry.is_file(follow_symlinks=False):
            continue
        try:
            if is_link(path) or not entry.is_dir(follow_symlinks=False):
                raise SkillError("only skill folders belong in skills/")
            files, _ = read_tree(path)
            metadata = read_metadata(path)
            files.pop(METADATA, None)
            name = skill_name(files, entry.name)
            if name != entry.name:
                raise SkillError(f"folder name must match the SKILL.md name {name!r}")
            targets = metadata.get("targets", list(TARGETS))
            if not isinstance(targets, list) or not targets or not set(targets) <= set(TARGETS):
                raise SkillError(f"targets must be a non-empty list of: {', '.join(TARGETS)}")
            skills.append(Skill(name, files, sorted(set(targets)), metadata))
        except SkillError as error:
            errors.append(f"ERROR {SKILLS_DIR}/{entry.name}: {error}")
    return skills, errors


def load_plugins(repo):
    path = repo / PLUGINS_FILE
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise SkillError(f"{PLUGINS_FILE} is not valid JSON")
    plugins = data.get("plugins") if isinstance(data, dict) else None
    if not isinstance(plugins, list):
        raise SkillError(f"{PLUGINS_FILE} needs a \"plugins\" list")
    for plugin in plugins:
        if not isinstance(plugin, dict) or not PLUGIN_ID.match(str(plugin.get("id", ""))):
            raise SkillError(f"{PLUGINS_FILE}: every plugin needs an id like name@marketplace")
        commands = list(plugin.get("install", [])) + list(plugin.get("update", []))
        commands += [plugin["check"]] if plugin.get("check") else []
        for command in commands:
            if not (isinstance(command, list) and command and command[0] == "claude"
                    and all(isinstance(part, str) for part in command)):
                raise SkillError(f"{PLUGINS_FILE}: commands must be lists that start with \"claude\"")
    return plugins


def load_all(repo):
    skills, errors = load_catalog(repo)
    try:
        plugins = load_plugins(repo)
    except SkillError as error:
        plugins, errors = [], errors + [f"ERROR {error}"]
    for error in errors:
        print(error)
    return skills, plugins, not errors


# ---------- installed state ----------

def load_state(home):
    path = home / MANAGER_DIR / "state.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except ValueError:
        raise SkillError(f"{path} is corrupt; move it away to start fresh")
    return data.get("installed", {})


def save_state(home, installed):
    ensure_folder(home, MANAGER_DIR)
    temporary = home / MANAGER_DIR / "state.json.tmp"
    write_json(temporary, {"installed": installed})
    os.replace(temporary, home / MANAGER_DIR / "state.json")


def classify(home, target, skill, installed):
    relative = f"{TARGETS[target]}/{skill.name}"
    destination = home / relative
    blocked = blocked_path(home, relative)
    if blocked is not None and blocked != destination:
        return "BLOCKED"
    if not os.path.lexists(destination):
        return "CREATE"
    if blocked is not None:
        return "CONFLICT"
    try:
        actual, _ = read_tree(destination, "installed")
    except SkillError:
        return "CONFLICT"
    if actual == skill.files:
        return "UNCHANGED"
    if fingerprint(actual) == installed.get(target, {}).get(skill.name):
        return "UPDATE"
    return "CONFLICT"


def classify_orphan(home, target, name, recorded):
    relative = f"{TARGETS[target]}/{name}"
    if blocked_path(home, relative) is not None:
        return "KEEP"
    if not os.path.lexists(home / relative):
        return "FORGET"
    try:
        actual, _ = read_tree(home / relative, "installed")
    except SkillError:
        return "KEEP"
    return "REMOVE" if fingerprint(actual) == recorded else "KEEP"


def plan_actions(home, skills, installed):
    actions, wanted = [], set()
    for skill in skills:
        for target in skill.targets:
            wanted.add((target, skill.name))
            actions.append((classify(home, target, skill, installed), target, skill.name, skill))
    for target in sorted(installed):
        for name, recorded in sorted(installed[target].items()):
            if (target, name) not in wanted:
                actions.append((classify_orphan(home, target, name, recorded), target, name, None))
    return actions


def write_skill(home, target, skill, backup_folder):
    ensure_folder(home, TARGETS[target])
    root = home / TARGETS[target]
    staging = Path(tempfile.mkdtemp(prefix=".skill-manager-", dir=root.parent))
    try:
        write_files(staging, skill.files)
        destination = root / skill.name
        displaced = None
        if os.path.lexists(destination):
            if backup_folder is None:
                displaced = staging.with_name(staging.name + "-old")
            else:
                ensure_folder(home, backup_folder.relative_to(home))
                displaced = backup_folder / skill.name
            shutil.move(str(destination), str(displaced))
        try:
            os.rename(staging, destination)
        except OSError:
            if displaced is not None:
                shutil.move(str(displaced), str(destination))
            raise
        staging = None
        if displaced is not None and backup_folder is None:
            shutil.rmtree(displaced)
        elif displaced is not None:
            print(f"BACKUP {target} {skill.name} -> {displaced}")
    finally:
        if staging is not None and staging.exists():
            shutil.rmtree(staging)


def sync(home, skills, prompter, dry_run=False):
    installed = load_state(home)
    backups = home / MANAGER_DIR / "backups" / datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    ok = True
    for status, target, name, skill in plan_actions(home, skills, installed):
        if status != "FORGET":
            print(f"{status} {target} {name}{NOTES.get(status, '')}")
        if status == "BLOCKED":
            ok = False
        if dry_run or status == "BLOCKED":
            continue
        try:
            if status == "CONFLICT":
                if not prompter.confirm(f"  Back up {target} {name} and replace it with the repo version?", True):
                    ok = False
                    continue
                write_skill(home, target, skill, backups / target)
            elif status in ("CREATE", "UPDATE"):
                write_skill(home, target, skill, None)
            elif status == "REMOVE":
                if not prompter.confirm(f"  Uninstall {target} {name}?", True):
                    continue
                shutil.rmtree(home / TARGETS[target] / name)
            if skill is None:
                installed[target].pop(name, None)
            else:
                installed.setdefault(target, {})[name] = fingerprint(skill.files)
            save_state(home, installed)
        except OSError as error:
            print(f"FAILED {target} {name}: {error}")
            ok = False
    return ok


def verify(home, skills, plugins):
    good, counts = True, {target: 0 for target in TARGETS}
    for skill in skills:
        for target in skill.targets:
            relative = f"{TARGETS[target]}/{skill.name}"
            if blocked_path(home, relative) is not None:
                status = "TYPE_MISMATCH"
            elif not (home / relative).exists():
                status = "MISSING"
            else:
                try:
                    actual, _ = read_tree(home / relative, "installed")
                    status = "OK" if actual == skill.files else "DIFFERENT"
                except SkillError:
                    status = "TYPE_MISMATCH"
            print(f"{status} {target} {skill.name}")
            if status == "OK":
                counts[target] += 1
            else:
                good = False
    plugin_count = 0
    for plugin in plugins:
        if plugin_installed(home, plugin):
            print(f"OK plugin {plugin['id']}")
            plugin_count += 1
        else:
            print(f"MISSING plugin {plugin['id']}")
            good = False
    for tool in TARGETS:
        if shutil.which(tool) is None:
            print(f"NOTE '{tool}' command not found on PATH; files are in place for it")
    summary = ", ".join(f"{target} {count} skills" for target, count in counts.items())
    print(f"{'VERIFIED' if good else 'NOT VERIFIED'}: {summary}, claude {plugin_count} plugins")
    return good


# ---------- Claude Code plugins ----------

def run_claude(command):
    executable = shutil.which(command[0])
    if executable is None:
        return None
    return subprocess.run([executable, *command[1:]], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, encoding="utf-8", errors="replace", check=False)


def plugin_installed(home, plugin):
    try:
        record = json.loads((home / ".claude/plugins/installed_plugins.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        record = {}
    if isinstance(record, dict) and plugin["id"] in (record.get("plugins") or {}):
        return True
    if plugin.get("check"):
        result = run_claude(plugin["check"])
        return bool(result and result.returncode == 0 and plugin["id"] in result.stdout)
    return False


def run_steps(plugin, key):
    succeeded = False
    for command in plugin.get(key, []):
        print(f"  $ {' '.join(command)}")
        result = run_claude(command)
        if result is None:
            print("MISSING_TOOL 'claude' command not found; install Claude Code, then run install again")
            return False
        succeeded = result.returncode == 0
        if not succeeded:
            print("  " + result.stdout.strip().replace("\n", "\n  "))
    return succeeded


def install_plugins(home, plugins, dry_run=False):
    ok = True
    for plugin in plugins:
        if plugin_installed(home, plugin):
            print(f"UNCHANGED plugin {plugin['id']}")
            continue
        print(f"INSTALL plugin {plugin['id']}")
        if dry_run:
            continue
        run_steps(plugin, "install")
        if not plugin_installed(home, plugin):
            print(f"FAILED plugin {plugin['id']} could not be confirmed; check the commands in {PLUGINS_FILE}")
            ok = False
    return ok


def update_plugins(home, plugins, prompter):
    for plugin in plugins:
        if plugin_installed(home, plugin) and prompter.confirm(
                f"Update Claude Code plugin {plugin['id']} to its newest version?", False):
            print(f"{'UPDATED' if run_steps(plugin, 'update') else 'FAILED'} plugin {plugin['id']}")


def plugin_entry(plugin_id, marketplace=None):
    """marketplace is the source to add first; None for Claude Code's built-in official marketplace."""
    if not PLUGIN_ID.match(plugin_id) or (marketplace is not None and not MARKETPLACE.match(marketplace)):
        raise SkillError(f"unexpected plugin id or marketplace: {plugin_id} {marketplace}")
    marketplace_name = plugin_id.split("@", 1)[1]
    install = [["claude", "plugin", "install", plugin_id]]
    if marketplace is not None:
        install.insert(0, ["claude", "plugin", "marketplace", "add", marketplace])
    return {
        "id": plugin_id,
        "install": install,
        "update": [["claude", "plugin", "marketplace", "update", marketplace_name],
                   ["claude", "plugin", "update", plugin_id]],
        "check": ["claude", "plugin", "list"],
    }


def detect_plugin(root, source):
    if not (root / ".claude-plugin/plugin.json").is_file():
        return None
    readme = "\n".join(path.read_text(encoding="utf-8", errors="replace")
                       for path in sorted(root.glob("README*")) if path.is_file())
    installs = re.findall(r"/plugin install\s+([\w.-]+@[\w.-]+)", readme)
    markets = re.findall(r"/plugin marketplace add\s+(\S+)", readme)
    for plugin_id in installs:
        if plugin_id.endswith("@" + OFFICIAL_MARKETPLACE):
            return plugin_entry(plugin_id)
    for plugin_id in installs:
        for market in markets:
            if re.sub(r"\.git$", "", market.rstrip("/").split("/")[-1]) == plugin_id.split("@", 1)[1]:
                return plugin_entry(plugin_id, market)
    try:
        plugin = json.loads((root / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
        market = json.loads((root / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    github = re.match(r"https://github\.com/([\w.-]+/[\w.-]+?)(?:\.git)?$", source.get("location", ""))
    if github and isinstance(plugin, dict) and isinstance(market, dict):
        return plugin_entry(f"{plugin.get('name')}@{market.get('name')}", github.group(1))
    return None


def save_plugin(repo, entry):
    path = repo / PLUGINS_FILE
    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"plugins": []}
    data["plugins"] = [plugin for plugin in data.get("plugins", []) if plugin.get("id") != entry["id"]]
    data["plugins"].append(entry)
    data["plugins"].sort(key=lambda plugin: plugin["id"])
    write_json(path, data)


# ---------- downloading ----------

def run_git(command):
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace", check=False, timeout=600,
                                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    except FileNotFoundError:
        raise SkillError("git is not installed")
    if result.returncode:
        lines = result.stdout.strip().splitlines()
        raise SkillError(lines[-1] if lines else "git failed")
    return result.stdout


def check_location(location):
    if not location.startswith(("https://", "file://")):
        raise SkillError(f"only https:// sources are supported: {location}")


def download(url):
    check_location(url)
    request = urllib.request.Request(url, headers={"User-Agent": "skill-manager"})
    with urllib.request.urlopen(request, timeout=60) as response:
        if not response.geturl().startswith("https://"):
            raise SkillError(f"refusing a redirect away from https: {response.geturl()}")
        data = response.read(MAX_DOWNLOAD + 1)
    if len(data) > MAX_DOWNLOAD:
        raise SkillError("download is too large")
    return data


def extract_zip(data, destination):
    destination.mkdir(parents=True)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if sum(member.file_size for member in archive.infolist()) > 5 * MAX_DOWNLOAD:
            raise SkillError("zip content is too large")
        for member in archive.infolist():
            parts = [part for part in member.filename.replace("\\", "/").split("/") if part]
            if member.filename.startswith(("/", "\\")) or ".." in parts or (parts and ":" in parts[0]):
                raise SkillError(f"unsafe path in zip: {member.filename}")
            mode = member.external_attr >> 16
            if not parts or stat.S_ISLNK(mode):
                continue
            target = destination.joinpath(*parts)
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, open(target, "wb") as output:
                shutil.copyfileobj(source, output)
            if mode & 0o111:
                target.chmod(0o755)
    entries = list(destination.iterdir())
    return entries[0] if len(entries) == 1 and entries[0].is_dir() else destination


def fetch(source, workdir):
    """Download source into workdir; return (root folder, version fields)."""
    kind, location = source.get("kind"), source.get("location", "")
    if kind == "folder":
        root = Path(location)
        if not root.is_dir():
            raise SkillError(f"source folder is not on this machine: {location}")
        return root, {}
    if kind == "zip":
        data = download(location) if "://" in location else Path(location).read_bytes()
        return extract_zip(data, workdir / "zip"), {"sha256": hashlib.sha256(data).hexdigest()}
    if kind != "git":
        raise SkillError(f"unknown source kind: {kind}")
    check_location(location)
    checkout = workdir / "git"
    command = ["git", "-c", "core.autocrlf=false", "clone", "--quiet", "--depth", "1"]
    if source.get("ref"):
        command += ["--branch", source["ref"]]
    run_git(command + ["--", location, str(checkout)])
    for entry in run_git(["git", "-C", str(checkout), "ls-files", "-s", "-z"]).split("\0"):
        if entry.startswith("120000 "):
            os.remove(checkout / entry.split("\t", 1)[1])
    commit = run_git(["git", "-C", str(checkout), "rev-parse", "HEAD"]).strip()
    return checkout, {"commit": commit}


def remote_commit(location, ref):
    check_location(location)
    rows = [line.split("\t") for line in run_git(["git", "ls-remote", location]).splitlines() if "\t" in line]
    wanted = [f"refs/heads/{ref}", f"refs/tags/{ref}^{{}}", f"refs/tags/{ref}"] if ref else ["HEAD"]
    for name in wanted:
        for sha, reference in rows:
            if reference == name:
                return sha
    raise SkillError(f"{ref or 'HEAD'} not found at {location}")


def links_in_page(text):
    found = [match.group(0).rstrip(".,;)") for match in GITHUB_LINK.finditer(text)]
    found += ["https://github.com/" + match.group(1) for match in NPX_SKILLS.finditer(text)]
    return list(dict.fromkeys(found))


def resolve_link(link, prompter):
    """Return (source, path inside the source) for a link, zip, or local folder."""
    if "://" not in link:
        path = Path(link).expanduser()
        if path.is_dir():
            return {"kind": "folder", "location": str(path.resolve())}, ""
        if path.is_file() and path.suffix.lower() == ".zip":
            return {"kind": "zip", "location": str(path.resolve())}, ""
        raise SkillError(f"not a folder, zip file, or link: {link}")
    parsed = urllib.parse.urlparse(link)
    if parsed.scheme == "file":
        return {"kind": "git", "location": link, "ref": None}, ""
    if parsed.scheme != "https":
        raise SkillError("only https links are supported")
    parts = [urllib.parse.unquote(part) for part in parsed.path.split("/") if part]
    if parsed.netloc.lower() in ("github.com", "www.github.com"):
        if len(parts) < 2:
            raise SkillError("GitHub link must point to a repository")
        name = parts[1][:-4] if parts[1].endswith(".git") else parts[1]
        ref, inside = None, []
        if len(parts) >= 4 and parts[2] in ("tree", "blob"):
            ref, inside = parts[3], parts[4:]
            if inside and inside[-1].lower() == "skill.md":
                inside = inside[:-1]
        return {"kind": "git", "location": f"https://github.com/{parts[0]}/{name}.git", "ref": ref}, "/".join(inside)
    if parsed.path.endswith(".git"):
        return {"kind": "git", "location": link, "ref": None}, ""
    if parsed.path.lower().endswith(".zip"):
        return {"kind": "zip", "location": link}, ""
    candidates = links_in_page(html.unescape(download(link).decode("utf-8", "replace")))
    if not candidates:
        raise SkillError("no GitHub link found on that page; pass the GitHub or zip link directly")
    source, inside = resolve_link(prompter.choose("Which link holds the skill?", candidates), prompter)
    source["page"] = link
    return source, inside


def find_skill_folders(root, inside):
    base = root.joinpath(*inside.split("/")) if inside else root
    if not base.is_dir():
        raise SkillError(f"path not found in the download: {inside}")
    if (base / "SKILL.md").is_file():
        return [base]
    if not inside and (root / SKILLS_DIR).is_dir():
        base = root / SKILLS_DIR
    found = []
    for current, directories, names in os.walk(base):
        directories[:] = sorted(name for name in directories
                                if name not in (".git", "node_modules") and not is_link(Path(current) / name))
        if "SKILL.md" in names:
            found.append(Path(current))
            directories[:] = []
    return found


def write_repo_skill(repo, name, files, metadata):
    destination = repo / SKILLS_DIR / name
    if destination.exists():
        shutil.rmtree(destination)
    write_files(destination, files)
    write_json(destination / METADATA, metadata)


# ---------- commands ----------

def cmd_add(args, prompter):
    source, inside = resolve_link(args.link, prompter)
    with tempfile.TemporaryDirectory() as work:
        root, version = fetch(source, Path(work))
        folders = find_skill_folders(root, inside)
        if not folders:
            raise SkillError("no SKILL.md found at that link")
        plugin = detect_plugin(root, source) if source["kind"] != "folder" and not inside else None
        as_plugin = False
        if plugin:
            print(f"This is a Claude Code plugin: {plugin['id']}")
            as_plugin = prompter.confirm("Install it as a Claude Code plugin, and copy its skills for Codex only?", True)
        if len(folders) > 1:
            print(f"Found {len(folders)} skills: {', '.join(folder.name for folder in folders)}")
            if not prompter.confirm(f"Import all {len(folders)} skills?", True):
                raise SkillError("cancelled")
        planned = []
        for folder in folders:
            files, skipped = read_tree(folder, "skip")
            files.pop(METADATA, None)
            for relative in skipped:
                print(f"SKIPPED {folder.name}/{relative} (link or disallowed file)")
            name = skill_name(files, folder.name)
            repo_skill = REPO / SKILLS_DIR / name
            if repo_skill.exists():
                existing = read_metadata(repo_skill).get("source", {})
                if existing.get("location") != source["location"]:
                    raise SkillError(f"skills/{name} already exists and did not come from this link")
            targets = ["codex"] if as_plugin else sorted(TARGETS)
            features = [] if as_plugin else claude_only_features(files)
            if features:
                print(f"{name} uses Claude Code-only features: {', '.join(features)}")
                if prompter.confirm(f"Install {name} for Claude Code only?", True):
                    targets = ["claude"]
            relative = folder.relative_to(root).as_posix()
            origin = dict(source, path="" if relative == "." else relative, **version)
            planned.append((name, files, {"targets": targets, "source": origin}))
        names = [name for name, _, _ in planned]
        if len(names) != len(set(names)):
            raise SkillError("the download contains two skills with the same name")
    for name, files, metadata in planned:
        write_repo_skill(REPO, name, files, metadata)
        print(f"ADDED skills/{name} -> {', '.join(metadata['targets'])}")
    if as_plugin:
        save_plugin(REPO, plugin)
        print(f"ADDED plugin {plugin['id']} to {PLUGINS_FILE}")
    print("Review the changes with 'git status', commit them, then run: python scripts/skills.py install")
    return 0


def check_updates(repo, skills, prompter):
    """Offer newer versions of downloaded skills; return True if the repo changed."""
    groups = {}
    for skill in skills:
        source = skill.metadata.get("source")
        # Local-folder copies have no upstream to check; add them from their web link to get updates.
        if isinstance(source, dict) and source.get("kind") in ("git", "zip"):
            key = (source["kind"], source.get("location"), source.get("ref"))
            groups.setdefault(key, []).append(skill)
    changed = False
    for (kind, location, ref), members in sorted(groups.items(), key=lambda item: str(item[0])):
        label = location + (f" ({ref})" if ref else "")
        try:
            recorded = {member.metadata["source"].get("commit") for member in members}
            if kind == "git" and recorded == {remote_commit(location, ref)}:
                print(f"UP_TO_DATE {label}")
                continue
            with tempfile.TemporaryDirectory() as work:
                root, version = fetch(members[0].metadata["source"], Path(work))
                updates = []
                for member in members:
                    inside = member.metadata["source"].get("path", "")
                    folder = root.joinpath(*inside.split("/")) if inside else root
                    if not (folder / "SKILL.md").is_file():
                        print(f"GONE {member.name} is no longer in {label}; delete skills/{member.name} to stop installing it")
                        continue
                    files, _ = read_tree(folder, "skip")
                    files.pop(METADATA, None)
                    updates.append((member, files))
                different = [member.name for member, files in updates if files != member.files]
                if different:
                    old = "/".join(sorted(str(value)[:7] for value in recorded if value)) or "recorded"
                    new = version.get("commit", version.get("sha256", "new"))[:7]
                    print(f"NEWER {label} {old} -> {new}: {', '.join(different)}")
                    if not prompter.confirm("Update these skills in the repo to the newer version?", False):
                        print(f"KEPT {label}")
                        continue
                else:
                    print(f"UP_TO_DATE {label}")
                for member, files in updates:
                    metadata = dict(member.metadata, source=dict(member.metadata["source"], **version))
                    if files != member.files or metadata != member.metadata:
                        write_repo_skill(repo, member.name, files, metadata)
                        changed = True
                        if files != member.files:
                            print(f"UPDATED skills/{member.name}")
        except (SkillError, OSError, subprocess.SubprocessError) as error:
            print(f"CHECK_FAILED {label}: {error}")
    if changed:
        print("The repo changed: review with 'git diff' and commit.")
    return changed


def cmd_plan(args, prompter):
    skills, plugins, ok = load_all(REPO)
    if not ok:
        return 1
    ok = sync(args.home, skills, prompter, dry_run=True)
    install_plugins(args.home, plugins, dry_run=True)
    return 0 if ok else 1


def cmd_install(args, prompter):
    skills, plugins, ok = load_all(REPO)
    if not ok:
        return 1
    ok = sync(args.home, skills, prompter)
    ok = install_plugins(args.home, plugins) and ok
    if not prompter.assume_defaults:
        print("Checking for newer versions...")
        if check_updates(REPO, skills, prompter):
            skills, plugins, _ = load_all(REPO)
            ok = sync(args.home, skills, prompter) and ok
        update_plugins(args.home, plugins, prompter)
    print("Verifying...")
    return 0 if verify(args.home, skills, plugins) and ok else 1


def cmd_update(args, prompter):
    skills, plugins, ok = load_all(REPO)
    if not ok:
        return 1
    if check_updates(REPO, skills, prompter):
        skills, plugins, ok = load_all(REPO)
        if not ok:
            return 1
    update_plugins(args.home, plugins, prompter)
    ok = sync(args.home, skills, prompter)
    print("Verifying...")
    return 0 if verify(args.home, skills, plugins) and ok else 1


def cmd_verify(args, prompter):
    skills, plugins, ok = load_all(REPO)
    return 0 if ok and verify(args.home, skills, plugins) else 1


COMMANDS = {"add": cmd_add, "install": cmd_install, "update": cmd_update, "verify": cmd_verify, "plan": cmd_plan}


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add", help="copy a downloaded skill into skills/")
    add.add_argument("link", help="GitHub link, web page, zip link or file, or local folder")
    for name in ("install", "update", "verify", "plan"):
        command = commands.add_parser(name)
        command.add_argument("--home", type=Path, default=Path.home(), help=argparse.SUPPRESS)
        if name in ("install", "update"):
            command.add_argument("--yes", action="store_true", help="answer every question with its default")
    add.add_argument("--yes", action="store_true", help="answer every question with its default")
    args = parser.parse_args(argv)
    try:
        return COMMANDS[args.command](args, Prompter(getattr(args, "yes", False)))
    except SkillError as error:
        print(f"ERROR {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
