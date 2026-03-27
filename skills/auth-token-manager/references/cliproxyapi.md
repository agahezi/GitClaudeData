# CLIProxyAPI — Reference

## What problem does it solve?

Claude Code CLI authenticates via OAuth tokens stored in `~/.claude.json`.
These tokens expire every few hours, causing 401 errors in any remote/SSH session.

CLIProxyAPI is a persistent Docker service that:
- Intercepts all Claude Code CLI requests on `localhost:8317`
- Manages its own OAuth tokens in a Docker volume (separate from Claude CLI)
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
  ├── auth stored in Docker volume proxy-stack_cli_proxy_auth
  └── auto-refreshes tokens
        ↓
  Anthropic API ✓
```

## Docker service

```yaml
# ~/proxy-stack/docker-compose.yml
services:
  cli-proxy-api:
    image: eceasy/cli-proxy-api:latest
    container_name: cli-proxy-api
    restart: unless-stopped
    ports:
      - "8317:8317"
    volumes:
      - ./cli-proxy-api/config.yaml:/CLIProxyAPI/config.yaml
      - cli_proxy_auth:/root/.cli-proxy-api

volumes:
  cli_proxy_auth:
    external: true
    name: proxy-stack_cli_proxy_auth
```

## config.yaml

```yaml
# ~/proxy-stack/cli-proxy-api/config.yaml
port: 8317
auth-dir: "/root/.cli-proxy-api"
debug: false
logging-to-file: false
usage-statistics-enabled: false
request-retry: 3
quota-exceeded:
  switch-project: true
  switch-preview-model: true
auth:
  providers: []
oauth-model-alias:
  claude:
    - name: "claude-opus-4-6"
      alias: "claude-sonnet-4-5-20250929"
    - name: "claude-sonnet-4-6"
      alias: "claude-sonnet-4-5-20250929"
    - name: "claude-opus-4-5"
      alias: "claude-sonnet-4-5-20250929"
```

## One-time login (run once per machine)

### On a machine with a browser
```bash
bash ~/proxy-stack/claude-login.sh
```

### On a headless/remote server (SSH from Termux or PC)

Step 1 — On your LOCAL machine, open an SSH tunnel:
```bash
ssh -L 54545:127.0.0.1:54545 user@<TAILSCALE_IP>
```

Step 2 — On the REMOTE machine, run the login script:
```bash
bash ~/proxy-stack/claude-login.sh
# Follow the prompts — it handles the Docker login flow
```

Step 3 — Open the URL printed in your LOCAL browser, sign in to claude.ai.
Token is saved automatically to the Docker volume.

## Claude Code CLI configuration

Set permanently in `~/.bashrc` or `~/.zshrc`:

```bash
export ANTHROPIC_BASE_URL=http://localhost:8317
export ANTHROPIC_API_KEY=dummy
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

CLIProxyAPI stores its own tokens in Docker volume `proxy-stack_cli_proxy_auth`,
mapped to `/root/.cli-proxy-api` inside the container.

`~/.claude.json` and `~/.claude/.credentials.json` are no longer used
for authentication when `ANTHROPIC_BASE_URL` points to the proxy.

## Managing the service

```bash
# Using the wrapper
cliproxy status
cliproxy start
cliproxy stop
cliproxy restart
cliproxy logs

# Or directly via docker compose
cd ~/proxy-stack
docker compose ps
docker compose logs -f cli-proxy-api
docker compose restart cli-proxy-api
```

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `401 OAuth token expired` | Not using proxy | Check `ANTHROPIC_BASE_URL=http://localhost:8317` is set |
| `connection refused :8317` | Container not running | `cliproxy start` or `cd ~/proxy-stack && docker compose up -d cli-proxy-api` |
| `54545: address already in use` | Port conflict during login | Kill process: `lsof -ti:54545 \| xargs kill` |
| Login URL not reachable | SSH tunnel not set up | Use `ssh -L 54545:127.0.0.1:54545 user@host` |
| Token unavailable after restart | Volume not mounted | Check volume in docker-compose.yml |
