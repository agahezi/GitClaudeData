# Claude OAuth — Reference

## Token Basics

Claude Code CLI uses OAuth tokens stored in `~/.claude/.credentials.json`.
These tokens are valid for ~1 year. **No silent refresh** — when expired,
renewal requires browser auth via CLIProxyAPI.

Token format: `sk-ant-oat01-...`
Stored in: `~/.claude/.credentials.json`

## credentials.json

```json
{
  "claudeAiOauth": {
    "accessToken":  "sk-ant-oat01-...",
    "refreshToken": "sk-ant-ort01-...",
    "expiresAt":    1748658860401
  }
}
```

> `refreshToken` exists in the file but **is not functional for silent refresh**.
> Anthropic has not exposed an API for renewal without browser interaction.

## What the cron does

```
Daily at 06:00 — refresh_token.py
  → Reads existing accessToken from credentials.json
  → Calculates days until expiry (expiresAt)
  → days_left >= 14  → writes to central env, silent
  → days_left 7-13   → writes + warning in log
  → days_left < 7    → writes + urgent warning
  → days_left < 0    → stops + instructions for renewal
```

## Token Renewal

When the token expires or CLIProxyAPI loses auth:

```bash
bash ~/proxy-stack/claude-login.sh    # browser auth via SSH tunnel
token-refresh --force                 # write new token to central env
source ~/.bashrc                      # reload in current shell
```

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `OAuth token revoked` | Expired/revoked | Run `bash ~/proxy-stack/claude-login.sh` |
| `Missing state parameter` | URL opened twice | Ctrl+C, retry |
| `401 auth_unavailable` | CLIProxyAPI has no auth | Run `bash ~/proxy-stack/claude-login.sh` |
