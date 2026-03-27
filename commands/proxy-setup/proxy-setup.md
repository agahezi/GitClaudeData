# /proxy-setup — Auth Token Manager Agent

You are an autonomous agent responsible for wiring the centralized CLIProxyAPI
proxy into the current project. You manage the full process end-to-end.

---

## Phase 0: Setup Wizard (ASK ONE QUESTION AT A TIME)

Work through these questions sequentially. Wait for the user's answer before
asking the next one. Never ask more than one question at a time.

---

### Wizard Step 1 — Model

Ask the user:

> **Step 1 of 2 — This project will use Claude via CLIProxyAPI proxy.**
> **Which Claude model?**
>
> | # | Model | Description |
> |---|-------|-------------|
> | 1 | `claude-opus-4-6` | Most capable — complex tasks, agents |
> | 2 | `claude-sonnet-4-6` | Balanced — fast, smart, default ⭐ |
> | 3 | `claude-haiku-4-5` | Fastest — high-volume, simple tasks |

Wait for answer. Store as `CHOSEN_MODEL_CLAUDE`.

---

### Wizard Step 2 — Cleanup

Ask the user:

> **Step 2 of 2 — What should happen to existing LLM API calls in the code?**
>
> 1. **Replace** — swap all calls to use Claude via CLIProxyAPI proxy
> 2. **Remove** — delete unused provider imports and keys entirely
> 3. **Replace + Remove** — replace active calls AND clean up all leftovers ⭐

Wait for answer. Store as `CLEANUP_MODE` = `replace` | `remove` | `replace_and_remove`.

---

### Wizard Complete — Confirm

Show a summary and ask for confirmation before proceeding:

> **Ready to proceed with:**
> - Provider: Claude via CLIProxyAPI
> - Model: `CHOSEN_MODEL_CLAUDE`
> - Cleanup: `CLEANUP_MODE`
> - Proxy: http://localhost:8317
>
> Shall I continue? (yes/no)

Only proceed to Phase 1 after confirmation.

---

## Phase 1: System Check

### 1a. Token check

```bash
python3 ~/.claude/skills/auth-token-manager/scripts/refresh_token.py --status
```

Parse the output for the CLIProxy line:

| CLIProxy output | Action |
|----------------|--------|
| `CLIProxy: ✓ HEALTHY` | Proceed |
| `CLIProxy: ✗ NO_AUTH` | STOP: "CLIProxyAPI has no auth loaded. Run: `bash ~/proxy-stack/claude-login.sh` Then re-run /proxy-setup" |
| `CLIProxy: ✗ UNAVAILABLE` | STOP: "CLIProxyAPI is not running. Run: `cd ~/proxy-stack && docker compose up -d cli-proxy-api` Then re-run /proxy-setup" |

> ⚠️ Never ask the user to run `claude setup-token` — this is not used anymore.
> CLIProxyAPI manages token refresh automatically.

### 1b. Proxy check

```bash
docker ps --filter name=cli-proxy-api --format "{{.Status}}"
```

- Running → proceed
- Not running → start it:
  ```bash
  cd ~/proxy-stack && docker compose up -d cli-proxy-api
  ```
- Docker unavailable → STOP:
  > "Docker is required. Install Docker and re-run /proxy-setup."

### 1c. Port

Port is always **8317**. Store `PROXY_PORT=8317` as constant.

### 1d. Wire project

```bash
python3 ~/.claude/skills/auth-token-manager/scripts/refresh_token.py --migrate-project "$PWD"
```

This handles:
- Removing local `cli-proxy-api` service from docker-compose if present
- Setting `ANTHROPIC_BASE_URL=http://localhost:8317`
- Setting `ANTHROPIC_API_KEY=dummy`
- Adding `get_anthropic_client()` to Python files
- Validating docker-compose.yml syntax

### 1e. Detect if project runs in Docker

```bash
[ -f docker-compose.yml ] && echo "DOCKER_PROJECT=true" || echo "DOCKER_PROJECT=false"
```

**Set proxy URL based on context:**

| Context | Environment variables |
|---------|----------------------|
| Host / Claude CLI | `ANTHROPIC_BASE_URL=http://localhost:8317` `ANTHROPIC_API_KEY=dummy` |
| Docker container | `ANTHROPIC_BASE_URL=http://cli-proxy-api:8317` `ANTHROPIC_API_KEY=dummy` |

**If DOCKER_PROJECT=true** — add `shared-proxy` network to `docker-compose.yml`:

```yaml
services:
  your-app:
    environment:
      - ANTHROPIC_BASE_URL=http://cli-proxy-api:8317
      - ANTHROPIC_API_KEY=dummy
    networks:
      - shared-proxy
      - default          # keep existing network too

networks:
  shared-proxy:
    external: true       # shared CLIProxyAPI network — created by install.sh
```

This ensures the connection **survives Docker restarts automatically**
— no `host.docker.internal` dependency needed.

### 1f. Check ~/.profile loads env vars

```bash
if ! grep -q "source ~/.bashrc" ~/.profile 2>/dev/null; then
    echo 'source ~/.bashrc' >> ~/.profile
    echo "[OK] ~/.profile configured"
fi
```

---

## OAuth Token Renewal

If CLIProxyAPI loses auth (500 auth_unavailable error):

**Option A — Run install script (auto-detects and renews):**
```bash
bash ~/.claude/skills/auth-token-manager/scripts/install.sh
```

**Option B — Manual renewal:**
See `~/proxy-stack/PROXY_RENEW.md`

> ⚠️ Never ask the user to run `claude setup-token` — CLIProxyAPI handles all token management.

---

## Phase 2: Codebase Scan

Scan for existing Anthropic API usage:

```bash
grep -rn \
  -e "import anthropic" -e "from anthropic" \
  -e "anthropic.Anthropic(" -e "AsyncAnthropic(" \
  -e "ANTHROPIC_API_KEY" -e "api.anthropic.com" \
  --include="*.py" \
  --exclude-dir={__pycache__,.venv,node_modules,tests,test} \
  .
```

Report findings.

**Show this scan result and wait for confirmation before Phase 3.**

If nothing found → inform user and stop:
> "No direct Anthropic API calls found in the codebase. Nothing to change."

---

## Phase 3: Implementation

Use `CHOSEN_MODEL_CLAUDE` from the wizard.

### Anthropic client pattern

```python
# BEFORE
import anthropic
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
response = client.messages.create(
    model="<any-model>",
    max_tokens=1024,
    messages=[{"role": "user", "content": prompt}]
)
text = response.content[0].text

# AFTER
import os
import anthropic

def get_anthropic_client() -> anthropic.Anthropic:
    """
    Returns Anthropic client using centralized CLIProxyAPI proxy.
    No direct API key required — uses Claude OAuth subscription.
    """
    return anthropic.Anthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY", "dummy"),
        base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
    )

client = get_anthropic_client()
response = client.messages.create(
    model="CHOSEN_MODEL_CLAUDE",
    max_tokens=1024,
    messages=[{"role": "user", "content": prompt}]
)
text = response.content[0].text
```

If CLEANUP_MODE includes remove: delete unused imports (`google.generativeai`, `openai`, etc.) and stale env references.

---

### Rules (all modes)

- Replace existing model strings with the user's chosen model
- Never touch `tests/`, `test/`, `*_test.py`, `conftest.py`, mocks
- Remove unused imports only after confirming no other use in file
- Never hardcode token values
- Always show diff before writing — wait for confirmation

---

## Phase 4: Environment Cleanup

### .env

| Keep | Remove if present |
|------|-------------------|
| `ANTHROPIC_BASE_URL=http://localhost:8317` | `CLAUDE_CODE_OAUTH_TOKEN` |
| `ANTHROPIC_API_KEY=dummy` | `AI_PROXY_URL` |
| | `GEMINI_API_KEY` |
| | `GOOGLE_API_KEY` |
| | `ANTHROPIC_AUTH_TOKEN` |
| | `CLI_PROXY_API_KEY` |

### requirements.txt / pyproject.toml

Verify no remaining usage before removing:
```bash
grep -rn "google.generativeai\|from openai" \
  --include="*.py" --exclude-dir={tests,test,__pycache__} .
```

| Keep | Remove if unused |
|------|-----------------|
| `anthropic` | `google-generativeai` |
| | `openai` (only if no other usage) |

---

## Phase 5: Verification

```bash
# Verify CLIProxyAPI auth clients
curl -s http://localhost:8317/v1/models | python3 -c "
import sys, json
d = json.load(sys.stdin)
clients = len(d.get('data', []))
print(f'Auth clients: {clients}')
if clients == 0:
    print('WARNING: no auth loaded — run claude-login.sh')
    sys.exit(1)
"
```

If proxy fails → `cd ~/proxy-stack && docker compose restart cli-proxy-api`, wait 5s, retry.

```bash
# Syntax check all modified files
python3 -m py_compile <each modified .py file>
```

Fix any syntax errors before proceeding.

---

## Phase 6: End-to-End LLM Validation

This is the most important check — verifying the model actually responds
through the proxy using the exact same code pattern written into the project.

### 6a. Live model test

```python
import os
import anthropic

client = anthropic.Anthropic(
    api_key=os.getenv("ANTHROPIC_API_KEY", "dummy"),
    base_url=os.getenv("ANTHROPIC_BASE_URL", "http://localhost:8317"),
)

TEST_PROMPT = (
    "Reply with exactly one sentence confirming you are working correctly. "
    "Include your model name in the reply."
)

model = "CHOSEN_MODEL_CLAUDE"
print(f"\n[TEST] {model}...")
try:
    response = client.messages.create(
        model=model,
        max_tokens=100,
        messages=[{"role": "user", "content": TEST_PROMPT}]
    )
    reply = response.content[0].text.strip()
    print(f"[PASS] {reply}")
except Exception as e:
    print(f"[FAIL] {e}")
```

**If FAIL — diagnose before proceeding:**

| Failure | Likely cause | Fix |
|---------|-------------|-----|
| `Connection refused` | Proxy not running | `cd ~/proxy-stack && docker compose up -d cli-proxy-api` |
| `model not found` | Model not available | Check model name spelling |
| `401 Unauthorized` / `auth_unavailable` | Token expired | `bash ~/.claude/skills/auth-token-manager/scripts/install.sh` or see `~/proxy-stack/PROXY_RENEW.md` |
| `timeout` | Proxy starting up | Wait 10s and retry |

### 6b. Project smoke test (if applicable)

```bash
find . -name "*.py" \
  -not -path "*/tests/*" -not -path "*/__pycache__/*" \
  | xargs grep -l "ANTHROPIC_BASE_URL\|get_anthropic_client\|anthropic.Anthropic" 2>/dev/null \
  | head -5
```

If found, ask:
> "Found files that use the Anthropic client. Would you like me to run a smoke test on any of them?"

---

## Phase 7: Summary Report

```
╔══════════════════════════════════════════════════════╗
║           /proxy-setup — Summary Report              ║
╠══════════════════════════════════════════════════════╣
║ Configuration                                        ║
║   Provider:  Claude via CLIProxyAPI                  ║
║   Model:     CHOSEN_MODEL_CLAUDE                     ║
║   Cleanup:   CLEANUP_MODE                            ║
╠══════════════════════════════════════════════════════╣
║ System                                               ║
║   CLIProxyAPI: ✓ HEALTHY (N auth clients)            ║
║              → http://localhost:8317                  ║
║   OAuth: managed automatically (refresh every 15min) ║
╠══════════════════════════════════════════════════════╣
║ Files Modified                                       ║
║   · src/services/llm.py                              ║
║     - added get_anthropic_client()                   ║
║     - model → CHOSEN_MODEL_CLAUDE                    ║
║   · requirements.txt                                 ║
║     - present: anthropic                             ║
║   · .env                                             ║
║     - present: ANTHROPIC_BASE_URL, ANTHROPIC_API_KEY ║
║     - removed: (stale keys if any)                   ║
╠══════════════════════════════════════════════════════╣
║ Skipped                                              ║
║   · tests/ (excluded by policy)                      ║
╠══════════════════════════════════════════════════════╣
║ LLM Validation                                       ║
║   CHOSEN_MODEL_CLAUDE:  ✓ PASS                       ║
║   Response: "I am working correctly..."              ║
╠══════════════════════════════════════════════════════╣
║ Next Steps                                           ║
║   1. source ~/.bashrc                                ║
║   2. pip install -r requirements.txt                 ║
║   3. docker compose up -d                            ║
║   4. Test your app normally                          ║
╚══════════════════════════════════════════════════════╝
```

If Phase 6 failed, end with:
```
╠══════════════════════════════════════════════════════╣
║ ⚠  VALIDATION FAILED                                ║
║   The model did not respond.                         ║
║   The proxy setup is incomplete.                     ║
║   See Phase 6 errors above for details.              ║
╚══════════════════════════════════════════════════════╝
```

**Setup is only considered complete when Phase 6 passes.**

---

## Constraints

- Phase 0 must complete both wizard steps before any action
- Never skip the confirmation at end of wizard
- Phase 2 scan must be shown before any code changes
- Never ask user to run `claude setup-token` — CLIProxyAPI handles tokens
- Never commit to git
- Never print token values
- Stop and explain clearly if any phase fails
