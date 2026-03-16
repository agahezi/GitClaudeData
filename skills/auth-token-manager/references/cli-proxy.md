# CLI Proxy — Reference

## What it does

Runs a LiteLLM container on `localhost:8080` that:
- Accepts OpenAI-compatible HTTP requests
- Authenticates with Claude/Gemini using your OAuth token
- Returns standard OpenAI-format responses

Any project can use Claude or Gemini without touching tokens directly.

## Managed by

```bash
token-proxy             # start (default)
token-proxy --stop
token-proxy --restart
token-proxy --status
token-proxy --logs
token-proxy --port 9090  # custom port
```

## Connecting a project

### Python
```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:8080/v1", api_key="local")
response = client.chat.completions.create(
    model="claude",   # or "gemini", "claude-sonnet-4-6", etc.
    messages=[{"role": "user", "content": "hello"}]
)
```

### TypeScript / Node
```typescript
import OpenAI from 'openai'
const client = new OpenAI({ baseURL: 'http://localhost:8080/v1', apiKey: 'local' })
```

### FastAPI (your trading system)
```python
# In your LLM adapter (hexagonal architecture — infra layer)
import os
from openai import AsyncOpenAI

class ClaudeAdapter:
    def __init__(self):
        self._client = AsyncOpenAI(
            base_url=os.getenv("AI_PROXY_URL", "http://localhost:8080/v1"),
            api_key="local",
        )
```

### Docker app connecting to proxy
```yaml
# docker-compose.yml
services:
  your-app:
    environment:
      - AI_PROXY_URL=http://host.docker.internal:8080/v1
      - OPENAI_API_KEY=local
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

### OpenClaw routing through proxy
```yaml
# openclaw config
providers:
  anthropic:
    baseUrl: "http://host.docker.internal:8080"
    apiKey: "local"
```

## Available models

| Request model name | Routes to |
|-------------------|-----------|
| `claude` | claude-sonnet-4-6 (alias) |
| `claude-sonnet-4-6` | Claude Sonnet via OAuth |
| `claude-opus-4-6` | Claude Opus via OAuth |
| `gemini` | gemini-2.0-flash (alias) |
| `gemini-2.0-flash` | Gemini Flash via gcloud |

## Token reload

When `refresh_token.py` runs (daily cron), it:
1. Writes fresh token to `~/.config/ai-auth/tokens.env`
2. Calls `docker restart ai-proxy`
3. Proxy picks up new token from the YAML config

No manual intervention needed.

## Troubleshooting

```bash
# Proxy not responding
token-proxy --status
token-proxy --restart

# See what's happening
token-proxy --logs

# Port conflict
token-proxy --stop
token-proxy --port 9090 --start
# Update AI_PROXY_PORT in ~/.config/ai-auth/config.env

# Token changed but proxy using old one
token-refresh --force   # writes new token + restarts proxy
```
