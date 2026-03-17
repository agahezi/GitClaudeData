# Claude OAuth — Reference

## מהות הטוקן

`claude setup-token` מייצר `accessToken` בתוקף ~שנה.
**אין silent refresh** — כשפג, חייב `claude setup-token` ידני שוב.

Token format: `sk-ant-oat01-...`
נשמר ב: `~/.claude/.credentials.json`

## הבדל מ-`claude auth login`

| פקודה | תוקף | שימוש |
|-------|------|-------|
| `claude setup-token` | ~שנה | headless / אוטומציה ← **זה מה שאנחנו משתמשים** |
| `claude auth login` | 8-12 שעות | sessions אינטראקטיביות בלבד |

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

> ⚠️ `refreshToken` קיים בקובץ אבל **לא פונקציונלי לחידוש שקט**.
> Anthropic לא חשפה API לחידוש ללא browser interaction.

## מה הcron עושה בפועל

```
כל יום 06:00 — refresh_token.py
  → קורא accessToken הקיים מcredentials.json
  → מחשב ימים לפקיעה (expiresAt)
  → days_left ≥ 14   → כותב לcentral env, שקט
  → days_left 7-13   → כותב + התראה בלוג
  → days_left < 7    → כותב + התראה דחופה
  → days_left < 0    → עוצר + הנחיות לחידוש ידני
```

## חידוש שנתי

```bash
claude setup-token          # browser auth (~2 דקות)
token-refresh --force       # כותב טוקן חדש לכל .env
source ~/.bashrc            # טעינה בshell הנוכחי
```

## שגיאות נפוצות

| שגיאה | סיבה | פתרון |
|-------|------|--------|
| `OAuth token revoked` | פג/בוטל | חידוש שנתי |
| `Missing state parameter` | URL נפתח פעמיים | Ctrl+C → retry |
| `403 scope error` | שימוש ב-`auth login` במקום `setup-token` | הרץ `claude setup-token` |
