---
name: auth-token-manager
description: >
  Full lifecycle management of Claude OAuth tokens for personal use across
  multiple projects on the same machine — without paid API keys. Covers:
  first-time machine setup via interactive wizard, centralized token storage,
  automatic daily refresh via cron, and a CLIProxyAPI Docker service that
  permanently fixes Claude Code CLI OAuth 401 errors. Use this skill whenever:
  setting up a new machine, fixing OAuth 401 errors in Claude Code CLI,
  adding Claude to an existing project, dealing with token expiry, setting up
  ANTHROPIC_BASE_URL, configuring CLIProxyAPI, or connecting any app to Claude
  without a paid API key.
---

# Auth Token Manager

**Problem:** Claude Code CLI tokens expire every few hours → 401 errors.
**Solution:** CLIProxyAPI — persistent Docker proxy on port 8317 that auto-refreshes tokens.

```
Claude Code CLI
  (ANTHROPIC_BASE_URL=http://localhost:8317)
        ↓
  cli-proxy-api container (always running, ~/proxy-stack/)
  └── auto-refreshes tokens in Docker volume proxy-stack_cli_proxy_auth
        ↓
  Anthropic API ✓  (no more 401 errors)
```

---

## Entry Point — Always Start Here

```bash
python3 - << 'PYEOF'
import json, subprocess, os
from pathlib import Path
from datetime import datetime, timezone

results = {}

# 1. Claude Code CLI credentials
creds = Path.home() / ".claude" / ".credentials.json"
if not creds.exists():
    results["machine"] = "NEW"
else:
    try:
        d = json.load(open(creds))
        token = d.get("claudeAiOauth", {}).get("accessToken", "")
        ms = d.get("claudeAiOauth", {}).get("expiresAt", 0)
        days = (datetime.fromtimestamp(ms/1000, tz=timezone.utc)
                - datetime.now(tz=timezone.utc)).days
        results["machine"] = f"CONFIGURED days_left={days}"
    except:
        results["machine"] = "ERROR"

# 2. CLIProxyAPI status
try:
    r = subprocess.run(["docker","ps","--filter","name=cli-proxy-api",
                        "--format","{{.Names}}"],
                       capture_output=True, text=True, timeout=5)
    results["cliproxy"] = "RUNNING" if "cli-proxy-api" in r.stdout else "STOPPED"
except:
    results["cliproxy"] = "UNAVAILABLE"

# 3. ANTHROPIC_BASE_URL
base_url = os.environ.get("ANTHROPIC_BASE_URL", "not_set")
results["base_url"] = base_url

# 4. Central env
central = Path.home() / ".config" / "ai-auth" / "tokens.env"
results["central_env"] = "OK" if central.exists() else "MISSING"

for k, v in results.items():
    print(f"{k}={v}")
PYEOF
```

**Decision table:**

| Output | Action |
|--------|--------|
| `machine=NEW` | Run `bash ~/.claude/skills/auth-token-manager/scripts/install.sh` |
| `cliproxy=STOPPED` | Run `cliproxy start` |
| `cliproxy=RUNNING` but 401 errors | Run `bash ~/proxy-stack/claude-login.sh` |
| `base_url=not_set` | Run `source ~/.bashrc` or add `ANTHROPIC_BASE_URL=http://localhost:8317` |
| Everything OK | Machine ready |

---

## New Machine — install.sh

```bash
bash ~/.claude/skills/auth-token-manager/scripts/install.sh
```

Sets up everything: Claude token, central env, cron, CLIProxyAPI (8317).
After install, run `bash ~/proxy-stack/claude-login.sh` once for OAuth.

---

## SSH / Headless Login

```bash
# Step 1 — On your LOCAL machine:
ssh -L 54545:127.0.0.1:54545 user@<TAILSCALE_IP>

# Step 2 — On the REMOTE machine:
bash ~/proxy-stack/claude-login.sh
# Opens http://localhost:54545/... → open in your LOCAL browser
```

---

## Token Lifecycle

| Token type | Stored in | Expires | Auto-refresh |
|------------|-----------|---------|--------------|
| Claude Code CLI OAuth | Docker volume `proxy-stack_cli_proxy_auth` | hours | CLIProxyAPI auto |
| Claude credentials | `~/.claude/.credentials.json` | ~1 year | manual yearly |

---

## All Commands

```bash
# CLIProxyAPI management
cliproxy start
cliproxy stop
cliproxy restart
cliproxy status
cliproxy logs

# Token management
token-status             # Claude + CLIProxy status
token-refresh
token-refresh --force
token-link /path/to/project

# Project migration to centralized proxy
token-refresh --migrate-project /path/to/project
token-refresh --migrate-project .   # current directory
```

---

## --migrate-project <dir>

Migrates an existing or new project to use the centralized CLIProxyAPI proxy.

**Usage:**
```bash
python3 ~/.claude/skills/auth-token-manager/scripts/refresh_token.py --migrate-project /path/to/project
python3 ~/.claude/skills/auth-token-manager/scripts/refresh_token.py --migrate-project .
```

**What it does:**
- Removes local `cli-proxy-api` Docker service from docker-compose if present
- Updates `.env` files to point to `http://localhost:8317`
- Updates all Anthropic client instantiations to use `get_anthropic_client()`
- Validates `docker-compose.yml` syntax after changes
- Creates `.backup` files before modifying anything

**Requirements:**
- CLIProxyAPI proxy-stack must be running: `docker ps | grep cli-proxy-api`
- OAuth login must be complete: `bash ~/proxy-stack/claude-login.sh`

**Idempotent:** Running twice on the same project produces the same result without errors.

---

## Reference Files

- `references/cliproxyapi.md` — CLIProxyAPI full setup, SSH tunnel, troubleshooting
- `references/claude-oauth.md` — Claude token internals
- `scripts/install.sh` — first-time machine wizard
- `scripts/cliproxyapi_manager.sh` — CLIProxyAPI wrapper (start/stop/restart/status/logs)
- `scripts/refresh_token.py` — daily cron + project migration
- `commands/proxy-setup/proxy-setup.md` — agent for project integration
