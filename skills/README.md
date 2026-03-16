# auth-token-manager

Manages Claude and Gemini OAuth tokens for personal use across multiple projects —
without paid API keys. One token, stored centrally, refreshed automatically, accessible
to every project via environment variables or a local HTTP proxy.

---

## What It Does

```
claude setup-token  (once, manual)
        │
        ▼
~/.claude/skills/auth-token-manager/config/tokens.env   ← single source of truth
        │
        ├── auto-loaded in every terminal session
        ├── cron refreshes daily (silent, automatic)
        │
        ▼
Docker container: ai-proxy  →  http://localhost:8090/v1
        │
        ├── Project A  →  OpenAI SDK pointing at proxy
        ├── Project B  →  env var CLAUDE_CODE_OAUTH_TOKEN
        └── Project N  →  docker-compose env injection
```

---

## Directory Structure

```
auth-token-manager/
├── README.md                   ← this file
├── SKILL.md                    ← AI agent instructions (do not edit manually)
├── config/                     ← created on first install
│   ├── config.env              ← skill configuration (port, paths, refresh days)
│   ├── tokens.env              ← active tokens (auto-updated, chmod 600)
│   └── litellm_config.yaml     ← proxy model routing (auto-generated)
├── scripts/
│   ├── install.sh              ← first-time setup wizard
│   ├── refresh_token.py        ← token refresh + central env writer
│   └── proxy_manager.py        ← Docker proxy lifecycle manager
└── references/
    ├── claude-oauth.md         ← Claude token internals, edge cases
    ├── gemini-oauth.md         ← Gemini OAuth flow and auto-refresh
    └── cli-proxy.md            ← Proxy connection patterns for all project types
```

---

## Scripts

### `install.sh` — First-Time Setup Wizard

Interactive wizard that sets up everything on a new machine.
Run once after `claude setup-token`.

```bash
bash ~/.claude/skills/auth-token-manager/scripts/install.sh

# Custom token storage path:
AI_AUTH_CENTRAL_ENV=/custom/path/tokens.env bash install.sh
```

**What it does:**
1. Checks and optionally installs: python3, Node.js, Claude CLI, Docker
2. Detects existing Claude token or runs `claude setup-token` with browser guidance
3. Optionally sets up Gemini via `gcloud auth login`
4. Creates `config/tokens.env` with current tokens
5. Wires tokens into shell profile (auto-loaded on every login)
6. Installs cron job (daily refresh at 06:00)
7. Starts the CLI proxy Docker container

---

### `refresh_token.py` — Token Refresh & Distribution

Checks token expiry and refreshes if needed. Writes fresh token to `config/tokens.env`.
Called automatically by cron daily, or manually via alias.

```bash
# Via alias (after install):
token-status              # show expiry, days left, proxy status
token-refresh             # refresh if within 7 days of expiry
token-refresh --force     # force refresh now
token-link /path/project  # wire a project .env to central store

# Direct:
python3 scripts/refresh_token.py --status
python3 scripts/refresh_token.py --force
python3 scripts/refresh_token.py --link /path/to/project
```

**What `--link` does to a project:**
- Adds `CLAUDE_CODE_OAUTH_TOKEN` and `AI_PROXY_URL` to project `.env`
- Adds `.env` to `.gitignore`
- Keeps the project `.env` in sync on every future refresh

---

### `proxy_manager.py` — CLI Proxy Lifecycle

Manages the LiteLLM Docker container that exposes an OpenAI-compatible endpoint
powered by your Claude/Gemini subscription.

```bash
# Via alias:
token-proxy               # start proxy (default)
token-proxy --start       # start proxy
token-proxy --stop        # stop proxy
token-proxy --restart     # restart proxy
token-proxy --status      # show running status
token-proxy --logs        # tail live logs
token-proxy --port 8090   # start on custom port

# Direct:
python3 scripts/proxy_manager.py --start --port 8090
python3 scripts/proxy_manager.py --status
```

---

## All Commands (Quick Reference)

| Command | Description |
|---------|-------------|
| `token-status` | Show token expiry, days left, proxy status |
| `token-refresh` | Refresh token if near expiry |
| `token-refresh --force` | Force refresh now, write to all locations |
| `token-link /path` | Wire a project directory to central token store |
| `token-proxy` | Start the CLI proxy container |
| `token-proxy --stop` | Stop the CLI proxy container |
| `token-proxy --restart` | Restart the CLI proxy container |
| `token-proxy --status` | Show proxy container status |
| `token-proxy --logs` | Tail proxy logs |
| `token-proxy --port N` | Start proxy on custom port |

---

## Configuration

`config/config.env` — edit to change defaults:

```bash
AI_AUTH_CENTRAL_ENV="~/.claude/skills/auth-token-manager/config/tokens.env"
AI_AUTH_REFRESH_DAYS="7"        # refresh this many days before expiry
AI_PROXY_PORT="8090"            # proxy port (8080 may conflict with pihole)
CLAUDE_CREDENTIALS_PATH="~/.claude/.credentials.json"
```

---

## Connecting a Project to the Proxy

### Python / FastAPI
```python
from openai import AsyncOpenAI
import os

llm = AsyncOpenAI(
    base_url=os.getenv("AI_PROXY_URL", "http://localhost:8090/v1"),
    api_key="local",
)
```

### Docker Compose
```yaml
services:
  your-app:
    env_file: .env
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      - OPENAI_BASE_URL=http://host.docker.internal:8090/v1
      - OPENAI_API_KEY=local
```

### Available Model Names
| Request as | Routes to |
|-----------|-----------|
| `claude` | claude-sonnet-4-6 (alias) |
| `claude-sonnet-4-6` | Claude Sonnet |
| `claude-opus-4-6` | Claude Opus |
| `gemini` | gemini-2.0-flash (alias) |
| `gemini-2.0-flash` | Gemini Flash |

---

## Maintenance

**~Once per year** (when token expires):
```bash
claude setup-token      # browser auth, ~2 min
token-refresh --force   # writes fresh token everywhere
source ~/.bashrc        # reload current shell
```

**Cron log:**
```bash
tail -f /tmp/ai-token-refresh.log
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `OAuth token revoked` | `claude setup-token` then `token-refresh --force` |
| Proxy not responding | `token-proxy --restart` |
| Port already in use | `token-proxy --start --port 8091` |
| Token stale in shell | `source ~/.bashrc` |
| Project missing token | `token-link /path/to/project` |
| Docker pull timeout | `docker pull ghcr.io/berriai/litellm:main-latest` then retry |
