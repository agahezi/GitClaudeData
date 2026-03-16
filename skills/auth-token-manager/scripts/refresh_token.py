#!/usr/bin/env python3
"""
auth-token-manager — refresh_token.py
Refreshes Claude OAuth token and writes to central tokens.env.

Commands:
  (default)        Check expiry → refresh if needed → write to central env
  --force          Force refresh regardless of expiry
  --status         Print status only, no changes
  --link <dir>     Wire a project directory to the central token store
  --init           First-time setup (called by install.sh)
"""

import json
import os
import sys
import subprocess
import argparse
import time
from datetime import datetime, timezone
from pathlib import Path

# ─── Config ───────────────────────────────────────────────────────────────────

def load_config() -> dict:
    config_file = Path.home() / ".claude" / "skills" / "auth-token-manager" / "config" / "config.env"
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
                            Path.home() / ".claude" / "skills" / "auth-token-manager" / "config" / "tokens.env"))),
        "credentials": Path(os.environ.get("CLAUDE_CREDENTIALS_PATH",
                            cfg.get("CLAUDE_CREDENTIALS_PATH",
                            Path.home() / ".claude" / ".credentials.json"))),
        "refresh_days": int(os.environ.get("AI_AUTH_REFRESH_DAYS",
                            cfg.get("AI_AUTH_REFRESH_DAYS", 7))),
        "proxy_port":   int(cfg.get("AI_PROXY_PORT", 8080)),
    }

# ─── Token Reading ────────────────────────────────────────────────────────────

def read_credentials(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}

def get_status(creds: dict) -> dict:
    oauth = creds.get("claudeAiOauth", {})
    if not oauth or not oauth.get("accessToken"):
        return {"state": "missing"}

    expires_ms = oauth.get("expiresAt", 0)
    expires_at = datetime.fromtimestamp(expires_ms / 1000, tz=timezone.utc)
    days_left  = (expires_at - datetime.now(tz=timezone.utc)).days

    return {
        "state":         "expired" if days_left < 0 else ("expiring_soon" if days_left < 7 else "valid"),
        "token":         oauth["accessToken"],
        "refresh_token": oauth.get("refreshToken"),
        "expires_at":    expires_at.strftime("%Y-%m-%d %H:%M UTC"),
        "days_left":     days_left,
    }

# ─── Token Refresh ────────────────────────────────────────────────────────────

def trigger_refresh() -> bool:
    """Ask Claude CLI to refresh the token by running a lightweight command."""
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True, text=True, timeout=30
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

def get_gemini_token() -> str:
    """Get current Gemini token from gcloud."""
    try:
        result = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True, text=True, timeout=15
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""

# ─── Central env ─────────────────────────────────────────────────────────────

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
    existing.update({k: v for k, v in updates.items() if v})  # skip empty values

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

def notify_proxy_reload(port: int):
    """Signal proxy container to reload token from env."""
    try:
        subprocess.run(
            ["docker", "restart", "ai-proxy"],
            capture_output=True, timeout=15
        )
    except Exception:
        pass  # proxy reload is best-effort

# ─── Project linking ──────────────────────────────────────────────────────────

def link_project(project_dir: str, cfg: dict):
    project = Path(project_dir).resolve()
    if not project.exists():
        print(f"[ERROR] Directory not found: {project}")
        sys.exit(1)

    central_env = cfg["central_env"]
    env_file    = project / ".env"
    gitignore   = project / ".gitignore"

    # Read current token
    creds  = read_credentials(cfg["credentials"])
    status = get_status(creds)
    token  = status.get("token", "")

    # Write or update .env
    marker = "CLAUDE_CODE_OAUTH_TOKEN="
    if env_file.exists():
        lines   = env_file.read_text().splitlines()
        updated = False
        new_lines = []
        for line in lines:
            if line.startswith(marker):
                new_lines.append(f'{marker}"{token}"')
                updated = True
            else:
                new_lines.append(line)
        if not updated:
            new_lines += [
                "",
                f"# AI tokens — central store: {central_env}",
                f'{marker}"{token}"',
                f'AI_PROXY_URL="http://localhost:{cfg["proxy_port"]}/v1"',
            ]
        env_file.write_text("\n".join(new_lines) + "\n")
    else:
        env_file.write_text(
            f"# AI tokens — managed by auth-token-manager\n"
            f"# Central store: {central_env}\n"
            f'{marker}"{token}"\n'
            f'AI_PROXY_URL="http://localhost:{cfg["proxy_port"]}/v1"\n'
        )

    # Ensure .gitignore has .env
    gitignore_content = gitignore.read_text() if gitignore.exists() else ""
    if ".env" not in gitignore_content:
        with gitignore.open("a") as f:
            f.write("\n# AI tokens\n.env\n.env.local\n")
        print(f"[OK] Added .env to .gitignore")

    print(f"[OK] Project linked: {project}")
    print(f"     .env written with current token")
    print(f"     Proxy URL: http://localhost:{cfg['proxy_port']}/v1")
    print(f"\n     Use in code:")
    print(f"       Python:     load_dotenv() then os.environ['CLAUDE_CODE_OAUTH_TOKEN']")
    print(f"       Proxy:      OpenAI(base_url='http://localhost:{cfg['proxy_port']}/v1', api_key='local')")
    print(f"       Docker app: OPENAI_BASE_URL=http://host.docker.internal:{cfg['proxy_port']}/v1")

# ─── Commands ────────────────────────────────────────────────────────────────

def cmd_status(cfg: dict):
    creds  = read_credentials(cfg["credentials"])
    status = get_status(creds)
    central = cfg["central_env"]

    state_icon = {"valid": "✓", "expiring_soon": "⚠", "expired": "✗", "missing": "✗"}

    print(f"\n{'─'*52}")
    print(f"  Auth Token Status")
    print(f"{'─'*52}")
    print(f"  State:        {state_icon.get(status['state'], '?')} {status['state'].upper()}")
    if status.get("days_left") is not None:
        print(f"  Days left:    {status['days_left']}")
        print(f"  Expires:      {status['expires_at']}")
    token = status.get("token", "")
    print(f"  Token:        {'...' + token[-12:] if token else 'NONE'}")
    print(f"  Central env:  {central} ({'✓' if central.exists() else '✗ missing'})")
    print(f"  Proxy:        http://localhost:{cfg['proxy_port']}/v1")
    # Check proxy
    try:
        result = subprocess.run(["docker", "ps", "--filter", "name=ai-proxy", "--format", "{{.Status}}"],
                                capture_output=True, text=True, timeout=5)
        proxy_status = result.stdout.strip() or "not running"
    except Exception:
        proxy_status = "docker not available"
    print(f"  Proxy status: {proxy_status}")
    print(f"{'─'*52}\n")

def cmd_refresh(cfg: dict, force: bool = False):
    creds  = read_credentials(cfg["credentials"])
    status = get_status(creds)

    print(f"[INFO] Token: {status['state']} ({status.get('days_left', '?')} days left)")

    should_refresh = (
        force
        or status["state"] in ("missing", "expired", "expiring_soon")
        or (isinstance(status.get("days_left"), int) and status["days_left"] <= cfg["refresh_days"])
    )

    if not should_refresh:
        print(f"[OK] Token valid for {status['days_left']} more days — no refresh needed.")
        # Ensure central env exists even if no refresh needed
        if not cfg["central_env"].exists() and status.get("token"):
            write_central_env(cfg["central_env"], {"CLAUDE_CODE_OAUTH_TOKEN": status["token"]})
            print(f"[OK] Written to central env (first time).")
        return

    if status["state"] == "missing":
        print("[ERROR] No token found.")
        print("        Run 'claude setup-token' in your terminal to authenticate.")
        sys.exit(1)

    print("[INFO] Refreshing via Claude CLI...")
    ok = trigger_refresh()
    if not ok and status["state"] == "expired":
        print("[ERROR] Token expired and CLI refresh failed.")
        print("        Run 'claude setup-token' to re-authenticate (~5 min).")
        sys.exit(1)

    time.sleep(1)
    fresh_creds = read_credentials(cfg["credentials"])
    fresh_token = fresh_creds.get("claudeAiOauth", {}).get("accessToken", "")

    if not fresh_token:
        print("[ERROR] Could not read refreshed token from credentials file.")
        sys.exit(1)

    # Also try Gemini
    gemini_token = get_gemini_token()

    # Write to central env
    updates = {"CLAUDE_CODE_OAUTH_TOKEN": fresh_token}
    if gemini_token:
        updates["GEMINI_OAUTH_TOKEN"] = gemini_token

    write_central_env(cfg["central_env"], updates)
    print(f"[OK] Token refreshed → written to {cfg['central_env']}")

    # Reload proxy
    notify_proxy_reload(cfg["proxy_port"])
    print(f"[OK] Proxy signaled to reload")
    print(f"\n     Run: source ~/.bashrc  (to reload in current shell)")

# ─── Entry point ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Auth Token Manager")
    parser.add_argument("--force",  action="store_true", help="Force refresh now")
    parser.add_argument("--status", action="store_true", help="Show status only")
    parser.add_argument("--link",   metavar="DIR",       help="Link a project to central store")
    args = parser.parse_args()

    cfg = load_config()

    if args.status:
        cmd_status(cfg)
    elif args.link:
        link_project(args.link, cfg)
    else:
        cmd_refresh(cfg, force=args.force)

if __name__ == "__main__":
    main()
