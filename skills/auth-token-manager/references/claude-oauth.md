# Claude OAuth — Reference

## Token types

| Command | Token validity | Use case |
|---------|---------------|----------|
| `claude auth login` | 8-12 hours | Interactive CLI sessions |
| `claude setup-token` | ~1 year | Automated/headless use ← use this |

Always use `claude setup-token` for the auth-token-manager flow.

## First-time on remote machine (no browser)

```bash
claude setup-token
# Prints URL → open in your LOCAL browser → authorize
# Terminal polls → token printed automatically (wait ~10s)

# If terminal exits before printing:
python3 -c "
import json
d = json.load(open('/root/.claude/.credentials.json'))
print(d['claudeAiOauth']['accessToken'])
"
```

## credentials.json structure

```json
{
  "claudeAiOauth": {
    "accessToken":  "sk-ant-oat01-...",   // valid ~1 year
    "refreshToken": "sk-ant-ort01-...",   // used for silent refresh
    "expiresAt":    1748658860401          // Unix ms
  }
}
```

## Silent refresh mechanism

Claude CLI auto-refreshes the accessToken before any command if it's
near expiry, using the refreshToken. This is what `refresh_token.py`
exploits by running `claude --version` as a no-op trigger.

When the refreshToken itself expires (~1 year+), silent refresh fails
and `claude setup-token` must be run manually again.

## Common errors

| Error | Fix |
|-------|-----|
| `OAuth token revoked` | `token-refresh --force` or re-run `claude setup-token` |
| `Missing state parameter` | Ctrl+C, retry — URL was opened twice |
| `403: scope requirement` | Used wrong token — must be `setup-token` |
| Token wraps in terminal | Paste to editor, remove newlines |
