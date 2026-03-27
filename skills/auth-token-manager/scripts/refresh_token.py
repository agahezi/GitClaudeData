#!/usr/bin/env python3
"""
auth-token-manager — refresh_token.py

Claude OAuth:
  - accessToken valid ~1 year, no silent refresh
  - Reads existing token, warns before expiry, writes to central env
  - Does NOT attempt auto-renewal — renewal requires browser auth via CLIProxyAPI

Commands:
  (default)     Check + write to central env
  --force       Write immediately even if everything OK
  --status      Show status without changes
  --link <dir>  Link project directory to central store
  --migrate-project <dir>  Migrate project to centralized CLIProxyAPI proxy
"""

import json
import os
import re
import sys
import shutil
import subprocess
import argparse
from datetime import datetime, timezone
from pathlib import Path

WARN_DAYS  = 14
ALERT_DAYS = 7

# ─── Config ───────────────────────────────────────────────────

def load_config() -> dict:
    config_file = Path.home() / ".config" / "ai-auth" / "config.env"
    cfg = {}
    if config_file.exists():
        for line in config_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                cfg[k.strip()] = v.strip().strip('"').strip("'")
    return {
        "central_env": Path(os.environ.get("AI_AUTH_CENTRAL_ENV",
                            cfg.get("AI_AUTH_CENTRAL_ENV",
                            Path.home() / ".config" / "ai-auth" / "tokens.env"))),
        "credentials": Path(os.environ.get("CLAUDE_CREDENTIALS_PATH",
                            cfg.get("CLAUDE_CREDENTIALS_PATH",
                            Path.home() / ".claude" / ".credentials.json"))),
        "proxy_port":  int(cfg.get("AI_PROXY_PORT", 8317)),
    }

# ─── Claude ───────────────────────────────────────────────────

def get_claude_status(credentials_path: Path) -> dict:
    """
    Reads existing token and calculates days until expiry.
    Does NOT attempt silent refresh — Claude OAuth has no such mechanism.
    """
    if not credentials_path.exists():
        return {"state": "missing", "token": None, "days_left": None, "expires_at": None}
    try:
        d     = json.loads(credentials_path.read_text())
        oauth = d.get("claudeAiOauth", {})
        token = oauth.get("accessToken")
        if not token:
            return {"state": "missing", "token": None, "days_left": None, "expires_at": None}

        expires_ms = oauth.get("expiresAt", 0)
        expires_at = datetime.fromtimestamp(expires_ms / 1000, tz=timezone.utc)
        days_left  = (expires_at - datetime.now(tz=timezone.utc)).days

        if days_left < 0:
            state = "expired"
        elif days_left <= ALERT_DAYS:
            state = "alert"
        elif days_left <= WARN_DAYS:
            state = "warning"
        else:
            state = "valid"

        return {
            "state":      state,
            "token":      token,
            "expires_at": expires_at.strftime("%Y-%m-%d"),
            "days_left":  days_left,
        }
    except Exception as e:
        return {"state": "error", "token": None, "days_left": None, "error": str(e)}

def print_claude_warning(status: dict):
    days = status.get("days_left", "?")
    exp  = status.get("expires_at", "?")
    if status["state"] == "expired":
        print("")
        print("╔══════════════════════════════════════════════════════╗")
        print("║         ✗  CLAUDE TOKEN EXPIRED                      ║")
        print("╠══════════════════════════════════════════════════════╣")
        print("║  Run:                                                 ║")
        print("║    bash ~/proxy-stack/claude-login.sh                 ║")
        print("║    token-refresh --force                              ║")
        print("╚══════════════════════════════════════════════════════╝")
    elif status["state"] == "alert":
        print(f"  ⚠  CLAUDE TOKEN — {days} days until expiry ({exp})")
        print(f"     Action required soon: bash ~/proxy-stack/claude-login.sh && token-refresh --force")
    elif status["state"] == "warning":
        print(f"  ·  CLAUDE TOKEN — {days} days until expiry ({exp})")
        print(f"     Reminder: manual renewal required before {exp}")

# ─── CLIProxy ────────────────────────────────────────────────

def check_cliproxy_health() -> dict:
    """
    Checks that CLIProxyAPI responds and has auth clients loaded.
    Returns healthy only if at least one client is loaded.
    """
    import urllib.request
    import urllib.error
    try:
        req = urllib.request.urlopen(
            "http://localhost:8317/v1/models", timeout=5)
        import json as _json
        data = _json.loads(req.read().decode())
        clients = len(data.get("data", []))
        if clients > 0:
            return {"state": "healthy", "clients": clients}
        else:
            return {"state": "no_auth", "clients": 0}
    except urllib.error.URLError:
        return {"state": "unavailable", "error": "connection refused"}
    except Exception as e:
        return {"state": "unavailable", "error": str(e)}

# ─── Central env ─────────────────────────────────────────────

def read_env_file(path: Path) -> dict:
    if not path.exists():
        return {}
    result = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            result[k.strip()] = v.strip().strip('"').strip("'")
    return result

def write_central_env(path: Path, updates: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = read_env_file(path)
    existing.update({k: v for k, v in updates.items() if v})
    lines = [
        "# AI Provider Tokens — managed by auth-token-manager",
        f"# Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "# DO NOT commit this file to git.",
        "",
    ]
    for k, v in existing.items():
        lines.append(f'{k}="{v}"')
    path.write_text("\n".join(lines) + "\n")
    path.chmod(0o600)

# ─── Project linking ──────────────────────────────────────────

def link_project(project_dir: str, cfg: dict):
    project  = Path(project_dir).resolve()
    if not project.exists():
        print(f"[ERROR] Directory not found: {project}")
        sys.exit(1)

    env_file  = project / ".env"
    gitignore = project / ".gitignore"

    new_lines = []
    if env_file.exists():
        found_base_url = False
        found_api_key  = False
        for line in env_file.read_text().splitlines():
            if line.startswith("ANTHROPIC_BASE_URL="):
                new_lines.append("ANTHROPIC_BASE_URL=http://localhost:8317")
                found_base_url = True
            elif line.startswith("ANTHROPIC_API_KEY="):
                new_lines.append("ANTHROPIC_API_KEY=dummy")
                found_api_key = True
            else:
                new_lines.append(line)
        if not found_base_url:
            new_lines += ["", "ANTHROPIC_BASE_URL=http://localhost:8317"]
        if not found_api_key:
            new_lines += ["ANTHROPIC_API_KEY=dummy"]
    else:
        new_lines = [
            "# CLIProxyAPI — managed by auth-token-manager",
            "ANTHROPIC_BASE_URL=http://localhost:8317",
            "ANTHROPIC_API_KEY=dummy",
        ]

    env_file.write_text("\n".join(new_lines) + "\n")

    gi_content = gitignore.read_text() if gitignore.exists() else ""
    if ".env" not in gi_content:
        with gitignore.open("a") as f:
            f.write("\n# AI tokens\n.env\n.env.local\n")
        print("[OK] .env added to .gitignore")

    print(f"[OK] Project linked: {project.name}")
    print(f"     ANTHROPIC_BASE_URL + ANTHROPIC_API_KEY written to .env")
    print(f"\n     Python:  get_anthropic_client()  (see proxy-setup docs)")
    print(f"     Docker:  ANTHROPIC_BASE_URL=http://cli-proxy-api:8317")

# ─── Commands ────────────────────────────────────────────────

def cmd_status(cfg: dict):
    claude_s = get_claude_status(cfg["credentials"])
    central  = cfg["central_env"]

    icon = {"valid": "✓", "warning": "·", "alert": "⚠", "expired": "✗",
            "missing": "✗", "error": "✗"}

    print(f"\n{'─'*56}")
    print(f"  Auth Token Status")
    print(f"{'─'*56}")

    ci = icon.get(claude_s["state"], "?")
    print(f"  Claude:  {ci} {claude_s['state'].upper()}", end="")
    if claude_s.get("days_left") is not None:
        print(f"  ({claude_s['days_left']} days — expires {claude_s['expires_at']})", end="")
    print()
    t = claude_s.get("token") or ""
    print(f"           token: {'...' + t[-12:] if t else 'NONE'}")

    proxy_s = check_cliproxy_health()
    pi = "✓" if proxy_s["state"] == "healthy" else "✗"
    print(f"  CLIProxy: {pi} {proxy_s['state'].upper()}", end="")
    if proxy_s.get("clients"):
        print(f"  ({proxy_s['clients']} auth clients loaded)", end="")
    if proxy_s.get("error"):
        print(f"  ({proxy_s['error']})", end="")
    print(f"  → http://localhost:8317")

    print(f"  Central: {'✓' if central.exists() else '✗ missing'}  {central}")
    print(f"{'─'*56}\n")

    if claude_s["state"] not in ("valid", "warning"):
        print_claude_warning(claude_s)
    elif claude_s["state"] == "warning":
        print_claude_warning(claude_s)

def cmd_refresh(cfg: dict, force: bool = False):
    claude_s = get_claude_status(cfg["credentials"])
    central  = cfg["central_env"]

    # ── Claude ────────────────────────────────────────────────
    print(f"[Claude] {claude_s['state'].upper()}", end="")
    if claude_s.get("days_left") is not None:
        print(f" — {claude_s['days_left']} days left", end="")
    print()

    if claude_s["state"] in ("missing", "expired"):
        proxy_s = check_cliproxy_health()
        if proxy_s["state"] == "healthy":
            print(f"[WARNING] Claude credentials {claude_s['state']} — but CLIProxy healthy ({proxy_s['clients']} clients), continuing")
        else:
            print_claude_warning(claude_s)
            print(f"[ERROR] CLIProxy also unavailable — {proxy_s.get('error', proxy_s['state'])}")
            sys.exit(1)

    if claude_s["state"] in ("warning", "alert"):
        print_claude_warning(claude_s)

    # ── Write ─────────────────────────────────────────────────
    updates = {}
    if claude_s.get("token"):
        updates["CLAUDE_CREDENTIAL_TOKEN"] = claude_s["token"]
    write_central_env(central, updates)
    print(f"[OK] Written to {central}")

    # ── CLIProxy ──────────────────────────────────────────────
    proxy_s = check_cliproxy_health()
    if proxy_s["state"] == "healthy":
        print(f"[CLIProxy] healthy — {proxy_s['clients']} auth clients loaded")
    elif proxy_s["state"] == "no_auth":
        print("[CLIProxy] WARNING — proxy running but no auth loaded")
        print("           Run: bash ~/proxy-stack/claude-login.sh")
    else:
        print(f"[CLIProxy] ERROR — {proxy_s.get('error', 'unavailable')}")
        print("           Run: cd ~/proxy-stack && docker compose up -d cli-proxy-api")
        print("           If issue persists: bash ~/proxy-stack/claude-login.sh")

    print(f"\n     source ~/.bashrc  (to reload in current shell)")

# ─── Project migration ───────────────────────────────────────

GET_ANTHROPIC_CLIENT_FUNC = '''
def get_anthropic_client() -> anthropic.Anthropic:
    """
    Returns Anthropic client configured to use centralized CLIProxyAPI proxy.
    Routes through localhost:8317 — no direct API key required.
    Uses Claude OAuth subscription via proxy-stack container.
    """
    return anthropic.Anthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY", "dummy"),
        base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
    )
'''.strip()

def _find_project_files(project: Path) -> dict:
    result = {
        "docker_compose": None,
        "env_files": [],
        "python_files": [],
    }
    for name in ("docker-compose.yml", "docker-compose.yaml"):
        f = project / name
        if f.exists():
            result["docker_compose"] = f
            break

    for name in (".env", ".env.example", ".env.production", ".env.local"):
        f = project / name
        if f.exists():
            result["env_files"].append(f)

    for pyf in project.rglob("*.py"):
        parts = pyf.parts
        if any(skip in parts for skip in ("venv", ".venv", "node_modules", "__pycache__", ".git")):
            continue
        try:
            content = pyf.read_text(errors="ignore")
            if "anthropic.Anthropic(" in content or "ANTHROPIC_API_KEY" in content:
                result["python_files"].append(pyf)
        except Exception:
            pass

    return result

def _migrate_docker_compose(dc_file: Path) -> str:
    if dc_file is None:
        return "no docker-compose found"

    shutil.copy(dc_file, str(dc_file) + ".backup")
    content = dc_file.read_text()
    original = content

    pattern = re.compile(
        r'^  cli-proxy-api:\s*\n(?:    .*\n|  \n)*',
        re.MULTILINE
    )
    content = pattern.sub('', content)
    content = re.sub(r'^\s*cli_proxy_auth:.*\n', '', content, flags=re.MULTILINE)

    if content != original:
        dc_file.write_text(content)
        print(f"[REMOVED] cli-proxy-api service from {dc_file.name}")
        return "cli-proxy-api service removed"
    else:
        return "no changes needed"

def _migrate_env_file(env_file: Path) -> bool:
    shutil.copy(env_file, str(env_file) + ".backup")
    lines = env_file.read_text().splitlines()
    new_lines = []
    found_base_url = False
    found_api_key = False
    changed = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("CLI_PROXY_API_KEY=") or "cli_proxy_auth" in stripped:
            changed = True
            continue

        if stripped.startswith("ANTHROPIC_BASE_URL="):
            found_base_url = True
            val = stripped.split("=", 1)[1].strip().strip('"').strip("'")
            if val != "http://localhost:8317":
                new_lines.append("ANTHROPIC_BASE_URL=http://localhost:8317")
                changed = True
            else:
                new_lines.append(line)
            continue

        if stripped.startswith("ANTHROPIC_API_KEY="):
            found_api_key = True
            val = stripped.split("=", 1)[1].strip().strip('"').strip("'")
            if val != "dummy":
                new_lines.append("ANTHROPIC_API_KEY=dummy")
                changed = True
            else:
                new_lines.append(line)
            continue

        new_lines.append(line)

    if not found_base_url:
        new_lines.append("ANTHROPIC_BASE_URL=http://localhost:8317")
        changed = True
    if not found_api_key:
        new_lines.append("ANTHROPIC_API_KEY=dummy")
        changed = True

    if changed:
        env_file.write_text("\n".join(new_lines) + "\n")
        print(f"[UPDATED] {env_file.name} — ANTHROPIC_BASE_URL + ANTHROPIC_API_KEY")
    return changed

def _migrate_python_file(pyf: Path) -> int:
    shutil.copy(pyf, str(pyf) + ".backup")
    content = pyf.read_text()
    original = content
    replacements = 0

    if "def get_anthropic_client(" not in content:
        lines = content.split("\n")
        insert_idx = 0
        for i, line in enumerate(lines):
            if line.startswith("import ") or line.startswith("from ") or line == "":
                insert_idx = i + 1
            elif insert_idx > 0 and line.strip() and not line.startswith("#"):
                break

        lines.insert(insert_idx, "")
        lines.insert(insert_idx + 1, GET_ANTHROPIC_CLIENT_FUNC)
        lines.insert(insert_idx + 2, "")
        content = "\n".join(lines)

    if "import os" not in content:
        content = "import os\n" + content
    if "import anthropic" not in content:
        content = "import anthropic\n" + content

    pattern_with_args = re.compile(r'anthropic\.Anthropic\([^)]*\)')
    def replace_match(m):
        nonlocal replacements
        start = m.start()
        line_start = content.rfind("\n", 0, start) + 1
        line = content[line_start:start]
        if "return " in line:
            return m.group()
        replacements += 1
        return "get_anthropic_client()"

    content = pattern_with_args.sub(replace_match, content)

    if content != original:
        pyf.write_text(content)
        try:
            subprocess.run(
                ["python3", "-c", f"import py_compile; py_compile.compile('{pyf}')"],
                capture_output=True, text=True, timeout=10
            )
        except Exception:
            pass
        print(f"[UPDATED] {pyf.name} — Anthropic client updated")

    return replacements

def _validate_docker_compose(project: Path) -> bool:
    try:
        r = subprocess.run(
            ["docker", "compose", "config"],
            capture_output=True, text=True, timeout=15,
            cwd=str(project)
        )
        if r.returncode == 0:
            print("[OK] docker-compose.yml is valid")
            return True
        else:
            print("[ERROR] docker-compose.yml has syntax errors — manual review needed")
            return False
    except FileNotFoundError:
        print("[SKIP] docker compose not available — skipping validation")
        return True
    except Exception:
        print("[SKIP] docker compose validation skipped")
        return True

def cmd_migrate_project(project_dir: str):
    project = Path(project_dir).resolve()
    if not project.exists():
        print(f"[ERROR] Directory not found: {project}")
        sys.exit(1)

    project_name = project.name
    print(f"\n{'='*42}")
    print(f"  Migrating: {project_name}")
    print(f"{'='*42}\n")

    files = _find_project_files(project)
    print(f"[SCAN] docker-compose: {'found' if files['docker_compose'] else 'not found'}")
    print(f"[SCAN] .env files: {len(files['env_files'])} found")
    print(f"[SCAN] Python files with Anthropic: {len(files['python_files'])} found\n")

    dc_result = _migrate_docker_compose(files["docker_compose"])

    env_updated = []
    for ef in files["env_files"]:
        if _migrate_env_file(ef):
            env_updated.append(ef.name)

    py_updated = []
    total_replacements = 0
    for pyf in files["python_files"]:
        count = _migrate_python_file(pyf)
        if count > 0:
            py_updated.append(pyf.name)
            total_replacements += count

    if files["docker_compose"]:
        print()
        _validate_docker_compose(project)

    print(f"\n{'='*42}")
    print(f"  Migration Summary: {project_name}")
    print(f"{'='*42}")
    print(f"  docker-compose.yml:    {dc_result}")
    print(f"  .env files updated:    {', '.join(env_updated) if env_updated else 'no changes needed'}")
    print(f"  Python files updated:  {', '.join(py_updated) if py_updated else 'no changes needed'}")
    print(f"  Anthropic clients replaced: {total_replacements}")
    print()
    print("  Next steps:")
    print("  1. source ~/.bashrc")
    print("  2. docker compose up -d")
    print('  3. claude "hello"  — verify proxy works')
    print(f"{'='*42}\n")

# ─── Entry point ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Auth Token Manager")
    parser.add_argument("--force",  action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--link",   metavar="DIR")
    parser.add_argument("--migrate-project", metavar="DIR",
                        help="Migrate a project to use centralized CLIProxyAPI proxy")
    args = parser.parse_args()

    cfg = load_config()

    if args.status:
        cmd_status(cfg)
    elif args.link:
        link_project(args.link, cfg)
    elif args.migrate_project:
        cmd_migrate_project(args.migrate_project)
    else:
        cmd_refresh(cfg, force=args.force)

if __name__ == "__main__":
    main()
