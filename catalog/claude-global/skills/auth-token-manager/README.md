# auth-token-manager

Manages Claude OAuth tokens for personal use — no paid API keys needed.

---

## The Problem & Solution

**Problem:** Claude Code CLI OAuth tokens in `~/.claude.json` expire every few hours → 401 errors.

**Solution:** CLIProxyAPI — Docker service on port 8317 that intercepts CLI requests
and auto-refreshes tokens permanently.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Your Machine                        │
│                                                             │
│  ~/proxy-stack/                                             │
│  ├── docker-compose.yml                                     │
│  ├── cli-proxy-api/config.yaml                              │
│  ├── claude-login.sh          ← one-time OAuth              │
│  └── check_proxy_health.sh   ← hourly cron                 │
│                                                             │
│  ┌──────────────────────────────────┐                       │
│  │  CLIProxyAPI (cli-proxy-api)     │                       │
│  │  localhost:8317                  │                       │
│  │  volume: proxy-stack_cli_proxy_auth                      │
│  └──────────────────────────────────┘                       │
│         ↑                                                   │
│  Claude Code CLI                                            │
│  (ANTHROPIC_BASE_URL=http://localhost:8317)                 │
│  (ANTHROPIC_API_KEY=dummy)                                  │
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
│   ├── cliproxyapi_manager.sh            ← thin docker-compose wrapper
│   └── refresh_token.py                  ← daily cron + project migration
└── references/
    ├── cliproxyapi.md                    ← CLIProxyAPI full guide
    └── claude-oauth.md                   ← Claude token internals

commands/proxy-setup/
└── proxy-setup.md                        ← agent for project integration
```

---

## Quick Start — New Machine

```bash
# 1. Run wizard (sets up everything)
bash ~/.claude/skills/auth-token-manager/scripts/install.sh

# 2. Reload shell
source ~/.bashrc

# 3. One-time OAuth login
bash ~/proxy-stack/claude-login.sh
```

**For remote/SSH (Termux, PC → server):**
```bash
# On your LOCAL machine first:
ssh -L 54545:127.0.0.1:54545 user@<TAILSCALE_IP>

# Then on the server:
bash ~/proxy-stack/claude-login.sh
# Open the URL in your LOCAL browser
```

---

## All Commands

### CLIProxyAPI management
```bash
cliproxy start
cliproxy stop
cliproxy restart
cliproxy status    # shows container + health + ANTHROPIC_BASE_URL
cliproxy logs
```

### Token management
```bash
token-status                    # Claude + CLIProxy status
token-refresh                   # update central env
token-refresh --force
token-link /path/to/project     # wire a project to CLIProxyAPI
```

### Project migration
```bash
token-refresh --migrate-project /path/to/project
token-refresh --migrate-project .   # current directory
```

---

## Token Lifecycle

| Token | Stored | Expires | Refresh |
|-------|--------|---------|---------|
| Claude Code CLI OAuth | Docker volume `proxy-stack_cli_proxy_auth` | hours | CLIProxyAPI auto |
| Claude credentials | `~/.claude/.credentials.json` | ~1 year | manual yearly |

---

## Connecting a Project

```python
import os
import anthropic

def get_anthropic_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY", "dummy"),
        base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
    )

client = get_anthropic_client()
```

```yaml
# docker-compose.yml (project using CLIProxyAPI)
services:
  your-app:
    environment:
      - ANTHROPIC_BASE_URL=http://cli-proxy-api:8317
      - ANTHROPIC_API_KEY=dummy
    networks:
      - shared-proxy
      - default

networks:
  shared-proxy:
    external: true
```

---

## Security

- `tokens.env` is `chmod 600` — owner-only
- CLIProxyAPI tokens in Docker volume — not on host filesystem
- `.env` files auto-added to `.gitignore` by `token-link`
- CLIProxyAPI listens on localhost only — not exposed externally
