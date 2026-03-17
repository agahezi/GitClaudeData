# auth-token-manager

Manages AI provider OAuth tokens for personal use — no paid API keys needed.
Solves two distinct problems with two dedicated solutions.

---

## The Two Problems & Solutions

### Problem A: Claude Code CLI gets 401 every few hours
**Cause:** CLI OAuth tokens in `~/.claude.json` expire after a few hours.
**Fix:** CLIProxyAPI — Docker service on port 8317 that intercepts CLI requests
and auto-refreshes tokens.

### Problem B: Other apps need Claude/Gemini without API key
**Fix:** LiteLLM proxy — Docker service on port 8080 with OpenAI-compatible API.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Your Machine                        │
│                                                             │
│  ~/.config/ai-auth/tokens.env   ← central token store      │
│                                                             │
│  ┌──────────────────────┐   ┌─────────────────────────┐    │
│  │  CLIProxyAPI         │   │  LiteLLM proxy          │    │
│  │  localhost:8317      │   │  localhost:8080         │    │
│  │  fixes CLI 401s      │   │  for your apps          │    │
│  └──────────────────────┘   └─────────────────────────┘    │
│         ↑                             ↑                     │
│  Claude Code CLI            Project A, B, N                 │
│  (ANTHROPIC_BASE_URL)       (AI_PROXY_URL)                  │
└─────────────────────────────────────────────────────────────┘
```

---

## File Structure

```
auth-token-manager/
├── README.md
├── SKILL.md                              ← AI agent entry point
├── scripts/
│   ├── install.sh                        ← first-time machine wizard
│   ├── cliproxyapi_manager.sh            ← CLIProxyAPI lifecycle (NEW)
│   ├── refresh_token.py                  ← daily cron
│   └── proxy_manager.py                  ← LiteLLM lifecycle
├── commands/
│   └── proxy-setup/
│       └── proxy-setup.md               ← agent for project integration
└── references/
    ├── cliproxyapi.md                    ← CLIProxyAPI full guide (NEW)
    ├── cli-proxy.md                      ← LiteLLM connection patterns
    ├── claude-oauth.md                   ← claude setup-token internals
    └── gemini-oauth.md                   ← Gemini gcloud flow
```

---

## Quick Start — New Machine

```bash
# 1. Run wizard (sets up everything)
bash ~/.claude/skills/auth-token-manager/scripts/install.sh

# 2. Reload shell
source ~/.bashrc

# 3. Fix 401 errors permanently (one-time login)
cliproxy login
```

**For remote/SSH (Termux, PC → server):**
```bash
# On your LOCAL machine first:
ssh -L 54545:127.0.0.1:54545 user@your-server

# Then on the server:
cliproxy login
# Open the URL in your LOCAL browser
```

---

## All Commands

### CLIProxyAPI — fixes Claude Code CLI 401 errors
```bash
cliproxy setup     # first-time setup
cliproxy login     # one-time OAuth authentication
cliproxy start
cliproxy stop
cliproxy restart
cliproxy status    # shows container + token + ANTHROPIC_BASE_URL
cliproxy logs
```

### LiteLLM proxy — for your apps
```bash
token-proxy               # start
token-proxy --stop
token-proxy --restart
token-proxy --status
token-proxy --logs
token-proxy --port 9090   # custom port
```

### Token management
```bash
token-status                    # full status: Claude + Gemini + both proxies
token-refresh                   # update central env
token-refresh --force
token-link /path/to/project     # wire a project to LiteLLM proxy
```

---

## Token Lifecycle

| Token | Stored | Expires | Refresh |
|-------|--------|---------|---------|
| Claude Code CLI OAuth | `~/.claude.json` | hours | ✅ CLIProxyAPI auto |
| claude setup-token | `~/.claude/.credentials.json` | ~1 year | ❌ manual yearly |
| Gemini gcloud | `~/.config/gcloud/` | ~1 hour | ✅ gcloud auto |

---

## Connecting a Project (LiteLLM proxy)

```python
# Python / FastAPI
from openai import AsyncOpenAI
import os

llm = AsyncOpenAI(
    base_url=os.getenv("AI_PROXY_URL", "http://localhost:8080/v1"),
    api_key="local",
)
```

```yaml
# docker-compose.yml
services:
  your-app:
    env_file: .env
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      - OPENAI_BASE_URL=http://host.docker.internal:8080/v1
      - OPENAI_API_KEY=local
```

---

## Security

- `tokens.env` is `chmod 600` — owner-only
- CLIProxyAPI tokens in `~/.config/ai-auth/cliproxyapi/tokens/` — owner-only
- `.env` files auto-added to `.gitignore` by `token-link`
- CLIProxyAPI listens on localhost only — not exposed externally
