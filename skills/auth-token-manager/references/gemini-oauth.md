# Gemini OAuth — Reference

## מהות הטוקן

Google OAuth סטנדרטי דרך gcloud CLI.
**gcloud מחדש אוטומטית** בכל קריאה ל-`gcloud auth print-access-token`.

Token format: `ya29...` | תוקף: ~שעה | חידוש: אוטומטי

## הבדל מClaude

| | Claude | Gemini |
|--|--------|--------|
| תוקף | ~שנה | ~שעה |
| silent refresh | ❌ | ✅ gcloud |
| מה הcron עושה | קורא קיים | מייצר טרי |
| proxy restart | לא (טוקן לא משתנה תדיר) | רק אם השתנה |

## הגדרה ראשונית

```bash
curl https://sdk.cloud.google.com | bash && exec -l $SHELL
gcloud auth login
gcloud auth application-default login
gcloud auth print-access-token   # אימות
```

## מה הcron עושה

```
כל יום 06:00
  → gcloud auth print-access-token  (מחדש אוטומטית אם פג)
  → השווה לטוקן הנוכחי בcentral env
  → השתנה → כותב + docker restart
  → לא השתנה → כלום
  → gcloud נכשל → התראה בלוג, לא עוצר
```

## שחזור session פג

```bash
gcloud auth revoke
gcloud auth login
gcloud auth application-default login
```

## שגיאות נפוצות

| שגיאה בסטטוס | סיבה | פתרון |
|--------------|------|--------|
| `session_expired` | session Google פג | `gcloud auth login` |
| `not_installed` | gcloud לא מותקן | התקנה מחדש |
| `timeout` | בעיית רשת | בדוק חיבור |
