---
name: auth-token-manager
description: >
  Full lifecycle management of AI provider OAuth tokens (Claude, Gemini) for personal
  use across multiple projects on the same machine — without paid API keys. Covers:
  first-time machine setup via interactive wizard, centralized token storage, automatic
  daily refresh via cron, Docker-based CLI proxy exposing an OpenAI-compatible endpoint,
  and wiring any project to use the proxy. Use this skill whenever: setting up a new
  machine, adding Claude/Gemini to an existing project, dealing with token expiry,
  setting up CLAUDE_CODE_OAUTH_TOKEN or AI_PROXY_URL, running claude setup-token,
  configuring a local LLM proxy, integrating proxy-setup into a project, or connecting
  any app to Claude/Gemini without a paid API key.
---

# Auth Token Manager

**שני שלבים, שני כלים:**

| שלב | כלי | מתי |
|-----|-----|-----|
| התקנה ראשונית למחשב | `scripts/install.sh` | פעם אחת לכל מחשב |
| שילוב בפרויקט | `commands/proxy-setup.md` | לכל פרויקט בנפרד |

---

## ⚡ Entry Point — תמיד התחל כאן

הרץ בדיקה זו:

```bash
python3 - << 'PYEOF'
import json, subprocess
from pathlib import Path
from datetime import datetime, timezone

creds   = Path.home() / ".claude" / ".credentials.json"
central = Path.home() / ".config" / "ai-auth" / "tokens.env"

if not creds.exists():
    print("STATE=NEW_MACHINE"); exit()

try:
    d     = json.load(open(creds))
    token = d.get("claudeAiOauth", {}).get("accessToken", "")
    if not token:
        print("STATE=NEW_MACHINE"); exit()
    ms        = d.get("claudeAiOauth", {}).get("expiresAt", 0)
    days_left = (datetime.fromtimestamp(ms/1000, tz=timezone.utc)
                 - datetime.now(tz=timezone.utc)).days
    setup     = "YES" if central.exists() else "NO"
    print(f"STATE=CONFIGURED DAYS_LEFT={days_left} SETUP_DONE={setup}")
except Exception as e:
    print(f"STATE=ERROR MSG={e}")
PYEOF
```

**החלטה:**

| תוצאה | פעולה |
|-------|--------|
| `STATE=NEW_MACHINE` | הרץ `scripts/install.sh` |
| `STATE=CONFIGURED SETUP_DONE=NO` | הרץ `scripts/install.sh` |
| `STATE=CONFIGURED DAYS_LEFT<7` | הרץ `token-status` + הצג התראה דחופה |
| `STATE=CONFIGURED DAYS_LEFT>=7` | המחשב מוכן — המשך לפעולה המבוקשת |

---

## מחשב חדש — install.sh

```bash
bash ~/.claude/skills/auth-token-manager/scripts/install.sh
# Custom path: AI_AUTH_CENTRAL_ENV=/custom/path bash install.sh
```

ה-wizard מטפל בהכל: תלויות, טוקן, Gemini (אופציונלי), central env, cron, proxy Docker.
**לאחר ה-wizard: המחשב מוכן. הכל אוטומטי עד פקיעה (~שנה).**

---

## שילוב פרויקט קיים — proxy-setup

כאשר המשתמש מבקש לחבר פרויקט לClaude/Gemini:

```
"שלב את הproxy בפרויקט"
"חבר את הפרויקט לClaude"
"/proxy-setup"
"עדכן את הקוד לעבוד עם הproxy"
"integrate proxy into my project"
```

קרא את `commands/proxy-setup.md` ובצע את כל ה-phases לפי הסדר.

---

## מחזור חיים של טוקנים

| | Claude OAuth | Gemini OAuth |
|--|--|--|
| תוקף | ~שנה | ~שעה |
| silent refresh | ❌ לא קיים | ✅ gcloud אוטומטי |
| מה הcron עושה | קורא קיים + מתריע | gcloud מחדש + proxy restart |
| ידני נדרש | ~פעם בשנה | רק אם session פג |

**חידוש שנתי:**
```bash
claude setup-token
token-refresh --force
source ~/.bashrc
```

---

## פקודות זמינות (לאחר install.sh)

```bash
token-status                    # סטטוס מלא
token-refresh                   # cron logic ידני
token-refresh --force           # כתיבה מיידית
token-link /path/to/project     # קישור פרויקט
token-proxy                     # start proxy
token-proxy --stop
token-proxy --restart
token-proxy --status
token-proxy --logs
```

---

## Troubleshooting

| תסמין | סיבה | פתרון |
|-------|------|--------|
| `OAuth token revoked` | פג/בוטל | חידוש שנתי |
| `Missing state parameter` | browser flow הופסק | Ctrl+C → retry |
| Proxy לא עונה | container נפל | `token-proxy --restart` |
| פרויקט לא מקבל טוקן | לא קושר | `token-link /path` |
| טוקן ישן בshell | shell לא נטען | `source ~/.bashrc` |

---

## Reference Files

- `references/claude-oauth.md` — Claude token internals
- `references/gemini-oauth.md` — Gemini flow, auto-refresh
- `references/cli-proxy.md` — חיבור פרויקטים לproxy
- `scripts/install.sh` — wizard התקנה ראשונית
- `scripts/refresh_token.py` — cron יומי
- `scripts/proxy_manager.py` — Docker proxy lifecycle
- `commands/proxy-setup.md` — agent לשילוב פרויקט
