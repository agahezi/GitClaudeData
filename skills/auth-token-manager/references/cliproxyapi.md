# CLIProxyAPI — Reference

## What problem does it solve?

Claude Code CLI authenticates via OAuth tokens stored in `~/.claude.json`.
These tokens expire every few hours, causing 401 errors in any remote/SSH session.

CLIProxyAPI is a persistent Docker service that:
- Intercepts all Claude Code CLI requests on `localhost:8317`
- Manages its own OAuth tokens in `~/.cli-proxy-api/` (separate from Claude CLI)
- Auto-refreshes tokens silently before they expire
- Exposes the native Anthropic `/v1/messages` format — no translation needed

## Architecture

```
[Before — broken every few hours]
Claude Code CLI → ~/.claude.json (expires) → Anthropic API → 401

[After — permanent fix]
Claude Code CLI
  ANTHROPIC_BASE_URL=http://localhost:8317
        ↓
  CLIProxyAPI (Docker, always running)
  ├── auth stored in ~/.cli-proxy-api/ (Docker volume)
  └── auto-refreshes tokens
        ↓
  Anthropic API ✓
```

## Docker service

```yaml
# docker-compose.yml
services:
  cliproxyapi:
    image: eceasy/cli-proxy-api:latest
    container_name: cliproxyapi
    restart: unless-stopped
    pull_policy: always
    ports:
      - "8317:8317"     # Main API — Claude Code CLI points here
      - "54545:54545"   # OAuth callback — needed only during --claude-login
    volumes:
      - ~/.config/ai-auth/cliproxyapi/config.yaml:/CLIProxyAPI/config.yaml
      - ~/.config/ai-auth/cliproxyapi/tokens:/root/.cli-proxy-api
```

## config.yaml

```yaml
# ~/.config/ai-auth/cliproxyapi/config.yaml
port: 8317
auth-dir: "~/.cli-proxy-api"
request-retry: 3
debug: false
logging-to-file: false
auth:
  providers: []   # No API key protection needed — localhost only
```

## One-time login (run once per machine)

### On a machine with a browser
```bash
docker exec -it cliproxyapi ./CLIProxyAPI --claude-login
# Browser opens → sign in to claude.ai → authorize
```

### On a headless/remote server (SSH from Termux or PC)

Step 1 — On your LOCAL machine (iPhone Termux or PC), open an SSH tunnel:
```bash
ssh -L 54545:127.0.0.1:54545 user@remote-host
```

Step 2 — On the REMOTE machine, trigger login:
```bash
docker exec -it cliproxyapi ./CLIProxyAPI --claude-login
# It prints a URL like: http://localhost:54545/...
```

Step 3 — On your LOCAL browser, open:
```
http://localhost:54545/...
```

Step 4 — Sign in to claude.ai and authorize.
Token is saved automatically to `~/.config/ai-auth/cliproxyapi/tokens/`.

## Claude Code CLI configuration

Set this permanently in `~/.bashrc` or `~/.zshrc`:

```bash
# CLIProxyAPI — prevents OAuth 401 errors
export ANTHROPIC_BASE_URL=http://localhost:8317
export ANTHROPIC_AUTH_TOKEN=sk-dummy   # Required by CLI, ignored by proxy
```

After setting, reload:
```bash
source ~/.bashrc
```

Verify:
```bash
echo $ANTHROPIC_BASE_URL   # should print http://localhost:8317
claude --version            # should work without 401
```

## Token storage

CLIProxyAPI stores its own tokens separately from Claude Code CLI:

```
~/.config/ai-auth/cliproxyapi/tokens/
└── claude-*.json    ← CLIProxyAPI manages these, auto-refreshes
```

`~/.claude.json` and `~/.claude/.credentials.json` are no longer used
for authentication when `ANTHROPIC_BASE_URL` points to the proxy.

## Managing the service

```bash
# Status
docker ps --filter name=cliproxyapi

# Logs
docker logs -f --tail 50 cliproxyapi

# Restart
docker restart cliproxyapi

# Re-authenticate (only needed if token is manually revoked)
docker exec -it cliproxyapi ./CLIProxyAPI --claude-login
```

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `401 OAuth token expired` | Not using proxy | Check `ANTHROPIC_BASE_URL=http://localhost:8317` is set |
| `connection refused :8317` | Container not running | `docker start cliproxyapi` |
| `54545: address already in use` | Port conflict during login | Kill process: `lsof -ti:54545 \| xargs kill` |
| Login URL not reachable | SSH tunnel not set up | Use `ssh -L 54545:127.0.0.1:54545 user@host` |
| Token unavailable after restart | Volume not mounted | Check volume in docker-compose.yml |
