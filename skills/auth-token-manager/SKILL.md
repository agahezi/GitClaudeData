---
name: auth-token-manager
description: >
  Full lifecycle management of AI provider OAuth tokens (Claude, Gemini) for personal
  use across multiple projects on the same machine — without paid API keys. Covers:
  first-time token creation, centralized storage so all projects share one token,
  automatic daily refresh via cron, Docker-based CLI proxy that exposes an
  OpenAI-compatible endpoint powered by your subscription, and wiring any project
  to use the proxy with minimal config. Use this skill whenever setting up a new
  machine, adding a new project that needs AI access, dealing with token expiry,
  setting up CLAUDE_CODE_OAUTH_TOKEN or GEMINI_OAUTH_TOKEN, running claude setup-token,
  configuring a local LLM proxy, or connecting an app to Claude/Gemini without
  an Anthropic Console API key.
---

# Auth Token Manager

**Goal**: One token per provider, stored centrally, refreshed automatically,
accessible to every project via environment variables or a local HTTP proxy.

---

## ⚡ Entry Point — Always Start Here

When this skill is triggered, run this check first:

```
Is ~/.claude/.credentials.json present AND contains a valid accessToken?
│
├─ NO  → This is a new machine.
│         Run: bash <skill_dir>/scripts/install.sh
│         The wizard will guide the user step by step.
│         Stop here — install.sh handles everything else.
│
└─ YES → Machine is already set up.
          Continue to the relevant section below.
```

**As an agent, execute this check automatically:**

```bash
python3 - << 'PYEOF'
import json, sys
from pathlib import Path
from datetime import datetime, timezone

creds_file = Path.home() / ".claude" / ".credentials.json"
central_env = Path.home() / ".config" / "ai-auth" / "tokens.env"

if not creds_file.exists():
    print("NEW_MACHINE")
    sys.exit()

try:
    d = json.load(open(creds_file))
    token = d.get("claudeAiOauth", {}).get("accessToken", "")
    if not token:
        print("NEW_MACHINE")
        sys.exit()
    expires_ms = d.get("claudeAiOauth", {}).get("expiresAt", 0)
    days_left = (datetime.fromtimestamp(expires_ms/1000, tz=timezone.utc)
                 - datetime.now(tz=timezone.utc)).days
    setup_done = central_env.exists()
    print(f"CONFIGURED days_left={days_left} setup={setup_done}")
except Exception as e:
    print(f"ERROR {e}")
PYEOF
```

**Decision based on output:**

| Output | Action |
|--------|--------|
| `NEW_MACHINE` | Run `install.sh` wizard |
| `CONFIGURED days_left=N setup=True` | Machine ready — proceed to task |
| `CONFIGURED days_left=N setup=False` | Token exists but setup incomplete — run `install.sh` |
| `CONFIGURED days_left<7` | Token expiring soon — run `token-refresh --force` |

---

## Architecture

```
~/.claude/.credentials.json     ← Claude CLI writes token here
         │
         ▼
~/.claude/skills/auth-token-manager/config/tokens.env    ← central store (chmod 600)
         │                         auto-sourced in every shell
         │
         ├── Project A .env     ← linked via token-link
         ├── Project B .env     ← linked via token-link
         │
         ▼
   Docker: ai-proxy             ← localhost:8080
   OpenAI-compatible endpoint
   powered by your subscription
```

---

## New Machine — install.sh

The install wizard runs interactively and handles everything:

```bash
# Locate the skill directory, then:
unzip auth-token-manager.skill -d ~/.claude/skills/
bash ~/.claude/skills/auth-token-manager/scripts/install.sh

# Custom central token path:
AI_AUTH_CENTRAL_ENV=/custom/path/tokens.env bash install.sh
```

**What the wizard does, step by step:**

| Step | What happens | Manual/Auto |
|------|-------------|-------------|
| 1 | Checks python3, Node.js, Claude CLI, Docker. Installs missing ones with your permission. | Semi-auto |
| 2 | Detects existing token or runs `claude setup-token`. Guides browser auth. | Manual (browser) |
| 3 | Optionally sets up Gemini via `gcloud auth login`. | Optional |
| 4 | Creates central env, wires shell, installs cron, starts Docker proxy. | Fully auto |

After the wizard completes, the machine is fully operational.
**No further manual steps needed until token expiry (~1 year).**

---

## Existing Machine — Day-to-Day Operations

### Check status
```bash
token-status
```

### Refresh token manually
```bash
token-refresh --force
```

### Wire a new project
```bash
token-link /path/to/project
```

Adds `CLAUDE_CODE_OAUTH_TOKEN` and `AI_PROXY_URL` to the project `.env`,
adds `.env` to `.gitignore`, and keeps it synced on every refresh.

### Proxy operations
```bash
token-proxy               # start
token-proxy --status      # check
token-proxy --restart     # restart
token-proxy --logs        # tail logs
```

---

## Connecting a Project to the Proxy

**Python / FastAPI:**
```python
from openai import AsyncOpenAI
import os

client = AsyncOpenAI(
    base_url=os.getenv("AI_PROXY_URL", "http://localhost:8080/v1"),
    api_key="local",
)
```

**TypeScript / Node:**
```typescript
import OpenAI from 'openai'
const client = new OpenAI({
  baseURL: process.env.AI_PROXY_URL ?? 'http://localhost:8080/v1',
  apiKey: 'local',
})
```

**Docker project (docker-compose):**
```yaml
services:
  your-app:
    environment:
      - AI_PROXY_URL=http://host.docker.internal:8080/v1
      - OPENAI_API_KEY=local
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

**Available model names via proxy:**

| Name in request | Routes to |
|----------------|-----------|
| `claude` | claude-sonnet-4-6 (alias) |
| `claude-sonnet-4-6` | Claude Sonnet |
| `claude-opus-4-6` | Claude Opus |
| `gemini` | gemini-2.0-flash (alias) |
| `gemini-2.0-flash` | Gemini Flash |

---

## Annual Token Renewal (~once/year)

When `install.sh` is already set up and only the token needs renewal:

```bash
claude setup-token        # browser auth — ~2 min
token-refresh --force     # writes fresh token everywhere + restarts proxy
source ~/.bashrc          # reload current shell
```

That's it. All projects pick up the new token automatically.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `OAuth token revoked` | Expired/revoked | Annual renewal above |
| `Missing state parameter` | Browser flow interrupted | Ctrl+C → retry `claude setup-token` |
| Proxy not responding | Container stopped | `token-proxy --restart` |
| Project missing token after refresh | .env not updated | `token-link /path/to/project` |
| Token stale in current shell | Shell not reloaded | `source ~/.bashrc` |
| `NEW_MACHINE` on existing machine | credentials.json missing | Run `install.sh` |

---

## Reference Files

- `references/cli-proxy.md` — Proxy details, all connection patterns
- `references/claude-oauth.md` — Token internals, edge cases
- `references/gemini-oauth.md` — Gemini flow, auto-refresh
- `scripts/install.sh` — Interactive first-time wizard
- `scripts/refresh_token.py` — Token refresh + central env writer + project linker
- `scripts/proxy_manager.py` — Docker proxy lifecycle
