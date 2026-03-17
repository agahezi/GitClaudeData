# auth-token-manager

ניהול מלא של טוקני AI (Claude OAuth, Gemini OAuth) לשימוש אישי על מספר פרויקטים
במחשב אחד — ללא API key בתשלום.

---

## עקרון הפעולה

```
claude setup-token  ←  פעם אחת ידני לכל מחשב
        │
        ▼
~/.claude/.credentials.json        ← Claude CLI כותב לכאן
        │
        │  cron יומי (refresh_token.py)
        ▼
~/.config/ai-auth/tokens.env       ← מקור אמת מרכזי (chmod 600)
        │
        ├── auto-sourced בכל shell פתוח
        ├── Project A / .env
        ├── Project B / .env
        │
        ▼
Docker: ai-proxy → localhost:8080   ← OpenAI-compatible endpoint
                                       מנוהל על ידי proxy_manager.py
```

---

## מבנה הקבצים

```
auth-token-manager/
│
├── README.md                   ← המסמך הזה
├── SKILL.md                    ← entry point לAI agent
│
├── scripts/                    ← כלים להרצה על המחשב
│   ├── install.sh              ← wizard התקנה ראשונית (פעם אחת למחשב)
│   ├── refresh_token.py        ← cron יומי + כתיבה לcentral env + קישור פרויקטים
│   └── proxy_manager.py        ← ניהול Docker proxy lifecycle
│
├── commands/                   ← הוראות לAI agent לפי פעולה
│   └── proxy-setup.md          ← agent לשילוב proxy בפרויקט קיים
│
└── references/                 ← תיעוד טכני מפורט
    ├── claude-oauth.md         ← מחזור חיים של Claude token
    ├── gemini-oauth.md         ← מחזור חיים של Gemini token
    └── cli-proxy.md            ← חיבור סוגי פרויקטים לproxy
```

---

## שני שלבים — שני כלים שונים

### שלב א: התקנה ראשונית על מחשב חדש → `install.sh`

מופעל **פעם אחת** על כל מחשב.

```bash
bash ~/.claude/skills/auth-token-manager/scripts/install.sh

# Custom path לtokens:
AI_AUTH_CENTRAL_ENV=/custom/path/tokens.env bash install.sh
```

**מה ה-wizard עושה:**
1. בדיקת תלויות — python3, Node.js, Claude CLI, Docker (מציע להתקין חסרים)
2. יצירת Claude OAuth token — מוביל דרך browser auth
3. הגדרת Gemini OAuth — אופציונלי, דרך `gcloud auth login`
4. יצירת `~/.config/ai-auth/tokens.env` — מקור אמת מרכזי
5. הוספת sourcing ל-`~/.bashrc` / `~/.zshrc`
6. התקנת cron יומי ב-06:00
7. הפעלת Docker proxy ראשונית

**לאחר ה-wizard:** המחשב מוכן. אין צורך בשום פעולה עד לפקיעת הטוקן (~שנה).

---

### שלב ב: שילוב פרויקט קיים → `/proxy-setup` (agent command)

מופעל על **כל פרויקט** שרוצים לחבר לproxy.

**הפעלה:** שלח לagent פרומפט כגון:
```
/proxy-setup
שלב את הproxy בפרויקט הנוכחי
חבר את הפרויקט ל-Claude
```

**מה ה-agent עושה (7 phases):**
1. **Wizard** — שואל provider (Claude/Gemini/שניהם), model, ומצב cleanup
2. **System check** — בודק token, מעלה proxy אם נפל
3. **Codebase scan** — מאתר כל קריאות LLM קיימות בקוד
4. **Implementation** — מחליף קריאות ישנות לOpenAI SDK דרך proxy
5. **Env cleanup** — מנקה API keys ישנים, מעדכן requirements.txt
6. **Verification** — בדיקת syntax + proxy models
7. **LLM Validation** — שאילתא אמיתית לכל מודל שנבחר ← הכי חשוב
8. **Summary Report** — דוח מלא של מה בוצע

---

## מחזור חיים של טוקנים

| Provider | תוקף | רענון | מה הcron עושה |
|----------|------|-------|----------------|
| Claude OAuth | ~שנה | ❌ אין silent refresh | קורא טוקן קיים, מתריע לפני פקיעה |
| Gemini OAuth | ~שעה | ✅ gcloud אוטומטי | מריץ gcloud לטוקן טרי, proxy restart אם השתנה |

**התראות Claude לפי ימים:**
```
≥ 14 ימים   → שקט, כותב טוקן לcentral env
7-14 ימים   → התראה בלוג: "N days left, action needed soon"
< 7 ימים    → התראה דחופה: "URGENT: run claude setup-token"
< 0 ימים    → קריטי: עוצר, לא כותב טוקן פג
```

**חידוש שנתי (~פעם בשנה, ~5 דקות):**
```bash
claude setup-token        # browser auth
token-refresh --force     # כותב טוקן חדש + proxy restart
source ~/.bashrc
```

---

## פקודות זמינות לאחר install.sh

```bash
# בדיקת סטטוס מלא (token Claude + Gemini + proxy)
token-status

# רענון ידני של central env
token-refresh
token-refresh --force     # כופה כתיבה גם אם הכל תקין

# קישור פרויקט למקור האמת
token-link /path/to/project

# ניהול proxy
token-proxy               # start (default)
token-proxy --stop
token-proxy --restart
token-proxy --status
token-proxy --logs
token-proxy --port 9090   # custom port
```

---

## חיבור פרויקט לproxy (לאחר token-link)

### Python / FastAPI
```python
from openai import AsyncOpenAI
import os

llm = AsyncOpenAI(
    base_url=os.getenv("AI_PROXY_URL", "http://localhost:8080/v1"),
    api_key="local",
)
response = await llm.chat.completions.create(
    model="claude-sonnet-4-6",
    messages=[{"role": "user", "content": "hello"}]
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

---

## מודלים זמינים דרך הproxy

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

---

## קבצים שנוצרים על המחשב

```
~/.config/ai-auth/
├── config.env          ← הגדרות (paths, port)
├── tokens.env          ← הטוקנים עצמם (chmod 600)
└── litellm_config.yaml ← config לDocker proxy

~/.local/lib/auth-token-manager/
└── scripts/            ← עותק של הסקריפטים להרצה מcron
```

---

## אבטחה

- `tokens.env` הוא `chmod 600` — רק המשתמש שלך יכול לקרוא
- `.env` בפרויקטים מתווסף אוטומטית ל-`.gitignore`
- הטוקן קשור לחשבון האישי שלך — אל תשתף
- אם הטוקן דלף: בטל ב-claude.ai → Settings → Security, ואז `claude setup-token`
