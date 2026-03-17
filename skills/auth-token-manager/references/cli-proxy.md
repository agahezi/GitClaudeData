# CLI Proxy — Reference

## מה הוא עושה

Docker container (LiteLLM) שמאזין על `localhost:8080`.
מקבל OpenAI-compatible requests ומעביר לClaude/Gemini עם הטוקנים שלך.

```
הקוד שלך
  POST localhost:8080/v1/chat/completions
  Authorization: Bearer local
        ↓
  LiteLLM (ai-proxy container)
        ↓
  Anthropic API / Google API
  (עם OAuth token שלך)
```

## ניהול

```bash
token-proxy               # start
token-proxy --stop
token-proxy --restart
token-proxy --status
token-proxy --logs
token-proxy --port 9090   # custom port
```

## מודלים זמינים

| שם בבקשה | מפנה ל |
|----------|--------|
| `claude` | claude-sonnet-4-6 (alias) |
| `claude-sonnet-4-6` | Claude Sonnet |
| `claude-opus-4-6` | Claude Opus |
| `claude-haiku-4-5` | Claude Haiku |
| `gemini` | gemini-2.0-flash (alias) |
| `gemini-2.0-flash` | Gemini Flash |
| `gemini-2.5-pro` | Gemini Pro |
| `gemini-2.5-flash` | Gemini Flash 2.5 |

## חיבור פרויקטים

### Python / FastAPI
```python
from openai import AsyncOpenAI
import os

llm = AsyncOpenAI(
    base_url=os.getenv("AI_PROXY_URL", "http://localhost:8080/v1"),
    api_key="local",
)
```

### TypeScript / Node
```typescript
import OpenAI from 'openai'
const llm = new OpenAI({
  baseURL: process.env.AI_PROXY_URL ?? 'http://localhost:8080/v1',
  apiKey: 'local',
})
```

### Docker project
```yaml
services:
  your-app:
    env_file: .env
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      - OPENAI_BASE_URL=http://host.docker.internal:8080/v1
      - OPENAI_API_KEY=local
```

### curl
```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer local" \
  -d '{"model":"claude","messages":[{"role":"user","content":"hello"}]}'
```

## Proxy restart — מתי ולמה

| מצב | restart? | סיבה |
|-----|----------|------|
| Claude token חודש (שנתי) | ✅ | config נכתב מחדש עם token חדש |
| Gemini token השתנה (יומי) | ✅ | LiteLLM צריך לטעון config מחדש |
| Claude בתוקף, Gemini זהה | ❌ | מיותר |

## Troubleshooting

```bash
# Proxy לא עונה
token-proxy --restart

# לראות שגיאות
token-proxy --logs

# Port תפוס
token-proxy --stop
token-proxy --port 9090 --start

# טוקן ישן בproxy אחרי חידוש שנתי
token-refresh --force   # כותב טוקן חדש → proxy restart אוטומטי
```
