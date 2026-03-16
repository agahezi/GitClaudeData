# Gemini OAuth — Reference

## First-time setup

```bash
curl https://sdk.cloud.google.com | bash && exec -l $SHELL
gcloud auth login
gcloud auth application-default login
gcloud auth print-access-token   # verify
```

## Token characteristics

- Valid ~1 hour (short-lived)
- Auto-refreshes via gcloud when you call `gcloud auth print-access-token`
- `refresh_token.py` calls this before writing to `tokens.env`

## In tokens.env

```bash
GEMINI_OAUTH_TOKEN=""   # populated by refresh_token.py if gcloud is available
```

## Troubleshooting

```bash
# Re-authenticate if session expired
gcloud auth revoke
gcloud auth login
gcloud auth application-default login

# Verify
gcloud auth list   # should show ACTIVE account
```
