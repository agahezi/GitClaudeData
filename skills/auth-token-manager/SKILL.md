---
name: auth-token-manager
description: >
  Full lifecycle management of AI provider OAuth tokens (Claude, Gemini) for personal
  use across multiple projects on the same machine — without paid API keys. Covers:
  first-time machine setup via interactive wizard, centralized token storage, automatic
  daily refresh via cron, Docker-based CLI proxy exposing an OpenAI-compatible endpoint,
  and a CLIProxyAPI service that permanently fixes Claude Code CLI OAuth 401 errors.
  Use this skill whenever: setting up a new machine, fixing OAuth 401 errors in Claude
  Code CLI, adding Claude/Gemini to an existing project, dealing with token expiry,
  setting up CLAUDE_CODE_OAUTH_TOKEN or AI_PROXY_URL or ANTHROPIC_BASE_URL, running
  claude setup-token, configuring a local LLM proxy, or connecting any app to
  Claude/Gemini without a paid API key.
---

# Auth Token Manager

**Two distinct problems, two distinct solutions:**

| Problem | Solution | Port |
|---------|----------|------|
| Claude Code CLI gets 401 every few hours | CLIProxyAPI | 8317 |
| Other apps need Claude/Gemini without API key | LiteLLM proxy | 8080 |

---

## ⚡ Entry Point — Always Start Here

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
    r = subprocess.run(["docker","ps","--filter","name=cliproxyapi",
                        "--format","{{.Names}}"],
                       capture_output=True, text=True, timeout=5)
    results["cliproxy"] = "RUNNING" if "cliproxyapi" in r.stdout else "STOPPED"
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
| `machine=NEW` | Run `scripts/install.sh` |
| `cliproxy=STOPPED` | Run `cliproxy start` |
| `cliproxy=RUNNING` but 401 errors | Run `cliproxy login` |
| `base_url=not_set` | Run `source ~/.bashrc` or add `ANTHROPIC_BASE_URL=http://localhost:8317` |
| Everything OK | Machine ready |

---

## Problem A: Claude Code CLI OAuth 401 errors

**Root cause:** Claude Code CLI tokens in `~/.claude.json` expire every few hours.

**Fix:** CLIProxyAPI — a persistent Docker service that intercepts CLI requests
and handles token refresh automatically.

```
Claude Code CLI
  (ANTHROPIC_BASE_URL=http://localhost:8317)
        ↓
  cliproxyapi container (always running)
  └── auto-refreshes tokens in ~/.config/ai-auth/cliproxyapi/tokens/
        ↓
  Anthropic API ✓  (no more 401 errors)
```

**Setup (first time):**
```bash
bash ~/.claude/skills/auth-token-manager/scripts/cliproxyapi_manager.sh setup
cliproxy login   # one-time browser auth — see SSH tunnel instructions below
```

**SSH / headless login (Termux, PC → remote server):**
```bash
# Step 1 — On your LOCAL machine:
ssh -L 54545:127.0.0.1:54545 user@remote-host

# Step 2 — On the REMOTE machine:
cliproxy login
# Opens http://localhost:54545/... → open in your LOCAL browser
```

**Daily operations:**
```bash
cliproxy status    # check container + token + ANTHROPIC_BASE_URL
cliproxy logs      # debug issues
cliproxy restart   # if container stopped
cliproxy login     # only if token manually revoked
```

See `references/cliproxyapi.md` for full details.

---

## Problem B: Other apps need Claude/Gemini without API key

**Fix:** LiteLLM proxy on port 8080 — exposes OpenAI-compatible endpoint.

```bash
token-proxy          # start
token-proxy --status
token-proxy --restart
token-link /path/to/project   # wire a project
```

See `references/cli-proxy.md` for connection patterns.

---

## New Machine — install.sh

```bash
bash ~/.claude/skills/auth-token-manager/scripts/install.sh
```

Sets up everything: Claude token, central env, cron, LiteLLM proxy (8080),
CLIProxyAPI (8317). After install, run `cliproxy login` once.

---

## Token Lifecycle

| Token type | Stored in | Expires | Auto-refresh |
|------------|-----------|---------|--------------|
| Claude Code CLI OAuth | `~/.claude.json` | hours | ✅ via CLIProxyAPI |
| claude setup-token | `~/.claude/.credentials.json` | ~1 year | ❌ manual yearly |
| Gemini gcloud | `~/.config/gcloud/` | ~1 hour | ✅ gcloud auto |

---

## All Commands

```bash
# CLIProxyAPI (fixes 401 errors)
cliproxy setup     # first-time setup
cliproxy login     # one-time auth
cliproxy start
cliproxy stop
cliproxy restart
cliproxy status
cliproxy logs

# LiteLLM proxy (other apps)
token-proxy
token-proxy --stop
token-proxy --restart
token-proxy --status
token-proxy --logs

# Token management
token-status             # Claude + Gemini + both proxies
token-refresh
token-refresh --force
token-link /path/to/project
```

---

## Reference Files

- `references/cliproxyapi.md` — CLIProxyAPI full setup, SSH tunnel, troubleshooting
- `references/cli-proxy.md` — LiteLLM proxy connection patterns
- `references/claude-oauth.md` — claude setup-token internals
- `references/gemini-oauth.md` — Gemini gcloud flow
- `scripts/install.sh` — first-time machine wizard
- `scripts/cliproxyapi_manager.sh` — CLIProxyAPI lifecycle
- `scripts/refresh_token.py` — daily cron
- `scripts/proxy_manager.py` — LiteLLM lifecycle
- `commands/proxy-setup/proxy-setup.md` — agent for project integration
