#!/usr/bin/env python3
"""
auth-token-manager — refresh_token.py

Claude OAuth:
  - accessToken תקף ~שנה, אין silent refresh
  - קורא טוקן קיים, מתריע לפני פקיעה, כותב לcentral env
  - לא מנסה לחדש אוטומטית — חידוש דורש claude setup-token ידני

Gemini OAuth:
  - accessToken תקף ~שעה, gcloud מחדש אוטומטית
  - מריץ gcloud auth print-access-token בכל ריצה
  - מבצע docker restart רק אם הטוקן השתנה

Commands:
  (default)     בדיקה + כתיבה לcentral env
  --force       כתיבה מיידית גם אם הכל תקין
  --status      הצגת סטטוס בלי שינויים
  --link <dir>  קישור תיקיית פרויקט לcentral store
"""

import json
import os
import sys
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
        "proxy_port":  int(cfg.get("AI_PROXY_PORT", 8080)),
    }

# ─── Claude ───────────────────────────────────────────────────

def get_claude_status(credentials_path: Path) -> dict:
    """
    קורא את הטוקן הקיים ומחשב ימים לפקיעה.
    לא מנסה silent refresh — Claude OAuth אין מנגנון כזה.
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
        print("║  הרץ:                                                 ║")
        print("║    claude setup-token                                 ║")
        print("║    token-refresh --force                              ║")
        print("╚══════════════════════════════════════════════════════╝")
    elif status["state"] == "alert":
        print(f"  ⚠  CLAUDE TOKEN — {days} ימים לפקיעה ({exp})")
        print(f"     פעולה נדרשת בקרוב: claude setup-token && token-refresh --force")
    elif status["state"] == "warning":
        print(f"  ·  CLAUDE TOKEN — {days} ימים לפקיעה ({exp})")
        print(f"     תזכורת: חידוש ידני נדרש לפני {exp}")

# ─── Gemini ───────────────────────────────────────────────────

def get_gemini_token() -> dict:
    """
    מקבל טוקן Gemini טרי דרך gcloud.
    gcloud מחדש אוטומטית אם הטוקן הנוכחי פג.
    """
    try:
        r = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode == 0 and r.stdout.strip():
            return {"state": "valid", "token": r.stdout.strip()}
        return {"state": "session_expired", "error": r.stderr.strip()}
    except FileNotFoundError:
        return {"state": "not_installed"}
    except subprocess.TimeoutExpired:
        return {"state": "timeout"}

def print_gemini_warning(g: dict):
    if g["state"] == "session_expired":
        print("  ⚠  GEMINI SESSION פג — הרץ: gcloud auth login")
    elif g["state"] == "not_installed":
        print("  ·  gcloud לא מותקן — Gemini לא זמין")
    elif g["state"] == "timeout":
        print("  ⚠  gcloud timeout — Gemini לא עודכן בריצה זו")

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

def restart_proxy_if_gemini_changed(port: int, old_token: str, new_token: str):
    """מריץ docker restart רק אם טוקן Gemini השתנה."""
    if not new_token or old_token == new_token:
        return
    try:
        subprocess.run(["docker", "restart", "ai-proxy"],
                       capture_output=True, timeout=15)
        print("[OK] Proxy restarted — Gemini token updated")
    except Exception:
        pass

# ─── Project linking ──────────────────────────────────────────

def link_project(project_dir: str, cfg: dict):
    project  = Path(project_dir).resolve()
    if not project.exists():
        print(f"[ERROR] Directory not found: {project}")
        sys.exit(1)

    env_file  = project / ".env"
    gitignore = project / ".gitignore"
    port      = cfg["proxy_port"]

    claude_s = get_claude_status(cfg["credentials"])
    token    = claude_s.get("token", "")

    new_lines = []
    if env_file.exists():
        found_claude = False
        found_proxy  = False
        for line in env_file.read_text().splitlines():
            if line.startswith("CLAUDE_CODE_OAUTH_TOKEN="):
                new_lines.append(f'CLAUDE_CODE_OAUTH_TOKEN="{token}"')
                found_claude = True
            elif line.startswith("AI_PROXY_URL="):
                new_lines.append(f'AI_PROXY_URL="http://localhost:{port}/v1"')
                found_proxy = True
            else:
                new_lines.append(line)
        if not found_claude:
            new_lines += ["", f'CLAUDE_CODE_OAUTH_TOKEN="{token}"']
        if not found_proxy:
            new_lines += [f'AI_PROXY_URL="http://localhost:{port}/v1"']
    else:
        new_lines = [
            "# AI tokens — managed by auth-token-manager",
            f"# Central store: {cfg['central_env']}",
            f'CLAUDE_CODE_OAUTH_TOKEN="{token}"',
            f'AI_PROXY_URL="http://localhost:{port}/v1"',
        ]

    env_file.write_text("\n".join(new_lines) + "\n")

    gi_content = gitignore.read_text() if gitignore.exists() else ""
    if ".env" not in gi_content:
        with gitignore.open("a") as f:
            f.write("\n# AI tokens\n.env\n.env.local\n")
        print("[OK] .env added to .gitignore")

    print(f"[OK] Project linked: {project.name}")
    print(f"     CLAUDE_CODE_OAUTH_TOKEN + AI_PROXY_URL written to .env")
    print(f"\n     Python:  AsyncOpenAI(base_url=os.getenv('AI_PROXY_URL'), api_key='local')")
    print(f"     Docker:  http://host.docker.internal:{port}/v1")

# ─── Commands ────────────────────────────────────────────────

def cmd_status(cfg: dict):
    claude_s = get_claude_status(cfg["credentials"])
    gemini_s = get_gemini_token()
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

    gi = "✓" if gemini_s["state"] == "valid" else "✗"
    gt = gemini_s.get("token", "")
    print(f"  Gemini:  {gi} {gemini_s['state'].upper()}", end="")
    if gt:
        print(f"  (...{gt[-8:]})", end="")
    print()

    print(f"  Central: {'✓' if central.exists() else '✗ missing'}  {central}")

    try:
        r = subprocess.run(
            ["docker", "ps", "--filter", "name=ai-proxy", "--format", "{{.Status}}"],
            capture_output=True, text=True, timeout=5)
        proxy_s = r.stdout.strip() or "not running"
    except Exception:
        proxy_s = "docker unavailable"
    print(f"  Proxy:   {proxy_s}  → http://localhost:{cfg['proxy_port']}/v1")
    print(f"{'─'*56}\n")

    if claude_s["state"] not in ("valid", "warning"):
        print_claude_warning(claude_s)
    elif claude_s["state"] == "warning":
        print_claude_warning(claude_s)
    if gemini_s["state"] != "valid":
        print_gemini_warning(gemini_s)

def cmd_refresh(cfg: dict, force: bool = False):
    claude_s = get_claude_status(cfg["credentials"])
    central  = cfg["central_env"]

    # ── Claude ────────────────────────────────────────────────
    print(f"[Claude] {claude_s['state'].upper()}", end="")
    if claude_s.get("days_left") is not None:
        print(f" — {claude_s['days_left']} days left", end="")
    print()

    if claude_s["state"] == "missing":
        print("[ERROR] אין טוקן Claude. הרץ: claude setup-token")
        sys.exit(1)

    if claude_s["state"] == "expired":
        print_claude_warning(claude_s)
        sys.exit(1)

    if claude_s["state"] in ("warning", "alert"):
        print_claude_warning(claude_s)

    # ── Gemini ────────────────────────────────────────────────
    old_env    = read_env_file(central)
    old_gemini = old_env.get("GEMINI_OAUTH_TOKEN", "")

    gemini_s = get_gemini_token()
    updates  = {"CLAUDE_CODE_OAUTH_TOKEN": claude_s["token"]}

    if gemini_s["state"] == "valid":
        updates["GEMINI_OAUTH_TOKEN"] = gemini_s["token"]
        changed = gemini_s["token"] != old_gemini
        print(f"[Gemini] valid — token {'changed' if changed else 'unchanged'}")
    else:
        print_gemini_warning(gemini_s)

    # ── Write ─────────────────────────────────────────────────
    write_central_env(central, updates)
    print(f"[OK] Written to {central}")

    restart_proxy_if_gemini_changed(
        cfg["proxy_port"], old_gemini,
        updates.get("GEMINI_OAUTH_TOKEN", "")
    )

    print(f"\n     source ~/.bashrc  (לטעינה בshell הנוכחי)")

# ─── Entry point ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Auth Token Manager")
    parser.add_argument("--force",  action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--link",   metavar="DIR")
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
