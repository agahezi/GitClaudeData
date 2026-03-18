# /proxy-setup — Auth Token Manager Agent

You are an autonomous agent responsible for wiring the local CLI proxy
into the current project. You manage the full process end-to-end.

---

## Phase 0: Setup Wizard (ASK ONE QUESTION AT A TIME)

Work through these questions sequentially. Wait for the user's answer before
asking the next one. Never ask more than one question at a time.

---

### Wizard Step 1 — Provider

Ask the user:

> **Step 1 of 3 — Which AI provider do you want to use?**
>
> 1. Claude (Anthropic)
> 2. Gemini (Google)
> 3. Both

Wait for answer. Store as `CHOSEN_PROVIDER` = `claude` | `gemini` | `both`.

---

### Wizard Step 2 — Model

Ask based on CHOSEN_PROVIDER:

**If CHOSEN_PROVIDER = claude**, ask:

> **Step 2 of 3 — Which Claude model?**
>
> | # | Model | Description |
> |---|-------|-------------|
> | 1 | `claude-opus-4-6` | Most capable — best for complex tasks, coding, agents |
> | 2 | `claude-sonnet-4-6` | Balanced — fast, smart, default for most work ⭐ |
> | 3 | `claude-haiku-4-5` | Fastest — high-volume, simple tasks |

**If CHOSEN_PROVIDER = gemini**, ask:

> **Step 2 of 3 — Which Gemini model?**
>
> | # | Model | Description |
> |---|-------|-------------|
> | 1 | `gemini-2.5-pro` | Most capable — reasoning, coding, complex agents ⭐ |
> | 2 | `gemini-2.5-flash` | Fast & efficient — great price/performance |
> | 3 | `gemini-2.0-flash` | Fastest & cheapest — high-volume tasks |

**If CHOSEN_PROVIDER = both**, ask:

> **Step 2 of 3 — Which model for each provider?**
>
> Claude:
> | # | Model | Description |
> |---|-------|-------------|
> | 1 | `claude-opus-4-6` | Most capable |
> | 2 | `claude-sonnet-4-6` | Balanced ⭐ |
> | 3 | `claude-haiku-4-5` | Fastest |
>
> Gemini:
> | # | Model | Description |
> |---|-------|-------------|
> | 1 | `gemini-2.5-pro` | Most capable ⭐ |
> | 2 | `gemini-2.5-flash` | Fast & efficient |
> | 3 | `gemini-2.0-flash` | Fastest |
>
> Reply with two numbers, e.g. "Claude: 2, Gemini: 1"

Wait for answer. Store as `CHOSEN_MODEL_CLAUDE` and/or `CHOSEN_MODEL_GEMINI`.

---

### Wizard Step 3 — Cleanup

Ask the user:

> **Step 3 of 3 — What should happen to existing LLM API calls in the code?**
>
> 1. **Replace** — swap all calls to use the chosen provider/model via proxy
> 2. **Remove** — delete unused provider imports and keys entirely
> 3. **Replace + Remove** — replace active calls AND clean up all leftovers ⭐

Wait for answer. Store as `CLEANUP_MODE` = `replace` | `remove` | `replace_and_remove`.

---

### Wizard Complete — Confirm

Show a summary and ask for confirmation before proceeding:

> **Ready to proceed with:**
> - Provider: `CHOSEN_PROVIDER`
> - Model(s): `CHOSEN_MODEL_CLAUDE` / `CHOSEN_MODEL_GEMINI`
> - Cleanup: `CLEANUP_MODE`
>
> Shall I continue? (yes/no)

Only proceed to Phase 1 after confirmation.

---

## Phase 1: System Check

### 1a. Token check

```bash
python3 ~/.local/lib/auth-token-manager/scripts/refresh_token.py --status
```

**Claude token rules (no silent refresh — token is valid for ~1 year):**

| Status | Action |
|--------|--------|
| `VALID` (days_left ≥ 7) | Proceed |
| `WARNING` (days_left 7-14) | Warn user, proceed |
| `ALERT` (days_left < 7) | Warn urgently, proceed but remind to renew soon |
| `EXPIRED` | STOP: "Claude token expired. Run `claude setup-token` then re-run /proxy-setup." |
| `MISSING` | STOP: "No Claude token found. Run `install.sh` first." |

> ⚠️ Do NOT attempt `claude --version` to trigger a refresh.
> Claude OAuth has no silent refresh mechanism.
> The only way to renew is `claude setup-token` (manual, browser).

**Gemini token rules (gcloud auto-refreshes ~every hour):**

If CHOSEN_PROVIDER includes gemini:
```bash
gcloud auth print-access-token
```
- Success → proceed (gcloud refreshed automatically if needed)
- Fails → STOP: "Gemini session expired. Run `gcloud auth login` then re-run /proxy-setup."

### 1b. Proxy check

```bash
docker ps --filter name=ai-proxy --format "{{.Status}}"
```

- Running → proceed
- Not running → start it:
  ```bash
  python3 ~/.local/lib/auth-token-manager/scripts/proxy_manager.py --start
  ```
- Docker unavailable → STOP:
  > "Docker is required. Install Docker and re-run /proxy-setup."

### 1c. Get proxy port

```bash
docker port ai-proxy 4000 2>/dev/null | cut -d: -f2
```

Store as `PROXY_PORT`. Default: `8080`.

### 1d. Wire project

```bash
python3 ~/.local/lib/auth-token-manager/scripts/refresh_token.py --link "$PWD"
```

Confirms `.env` was created/updated with `CLAUDE_CODE_OAUTH_TOKEN` and `AI_PROXY_URL`.

### 1e. Detect if project runs in Docker

```bash
[ -f docker-compose.yml ] && echo "DOCKER_PROJECT=true" || echo "DOCKER_PROJECT=false"
```

**Set proxy URL based on context:**

| Context | URL to use |
|---------|-----------|
| Host / Claude CLI | `http://localhost:8317/v1` |
| Docker container | `http://cli-proxy-api:8317/v1` |

**If DOCKER_PROJECT=true** — add `shared-proxy` network to `docker-compose.yml`:

```yaml
services:
  your-app:
    environment:
      - AI_PROXY_URL=http://cli-proxy-api:8317/v1
      - OPENAI_API_KEY=local
    networks:
      - shared-proxy
      - default          # keep existing network too

networks:
  shared-proxy:
    external: true       # shared CLIProxyAPI network — created by install.sh
```

This ensures the connection **survives Docker restarts automatically**
— no `host.docker.internal` dependency needed.


---

## Phase 2: Codebase Scan

Scan for ALL existing LLM API usage:

```bash
grep -rn \
  -e "import anthropic" -e "from anthropic" \
  -e "Anthropic(" -e "AsyncAnthropic(" \
  -e "ANTHROPIC_API_KEY" -e "api.anthropic.com" \
  -e "import google.generativeai" -e "genai\." \
  -e "GEMINI_API_KEY" -e "GOOGLE_API_KEY" \
  -e "generativelanguage.googleapis.com" \
  -e "openai.api_key" -e "OpenAI(api_key" -e "OPENAI_API_KEY" \
  --include="*.py" \
  --exclude-dir={__pycache__,.venv,node_modules,tests,test} \
  .
```

Report findings grouped by provider.

**Show this scan result and wait for confirmation before Phase 3.**

If nothing found → inform user and stop:
> "No direct LLM API calls found in the codebase. Nothing to change."

---

## Phase 3: Implementation

Use `CHOSEN_MODEL_CLAUDE` and/or `CHOSEN_MODEL_GEMINI` from the wizard.
Replace `PROXY_PORT` with the actual port from Phase 1c.

### If CHOSEN_PROVIDER = claude

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
from openai import AsyncOpenAI
client = AsyncOpenAI(
    base_url=os.getenv("AI_PROXY_URL", "http://localhost:PROXY_PORT/v1"),
    api_key="local",
)
response = await client.chat.completions.create(
    model="CHOSEN_MODEL_CLAUDE",
    max_tokens=1024,
    messages=[{"role": "user", "content": prompt}]
)
text = response.choices[0].message.content
```

If CLEANUP_MODE includes remove: remove `import google.generativeai`, `genai.configure(...)` blocks.

---

### If CHOSEN_PROVIDER = gemini

```python
# BEFORE
import google.generativeai as genai
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("<any-model>")
response = model.generate_content(prompt)
text = response.text

# AFTER
from openai import AsyncOpenAI
client = AsyncOpenAI(
    base_url=os.getenv("AI_PROXY_URL", "http://localhost:PROXY_PORT/v1"),
    api_key="local",
)
response = await client.chat.completions.create(
    model="CHOSEN_MODEL_GEMINI",
    messages=[{"role": "user", "content": prompt}]
)
text = response.choices[0].message.content
```

If CLEANUP_MODE includes remove: remove `import anthropic`, `Anthropic(...)` blocks.

---

### If CHOSEN_PROVIDER = both

```python
from openai import AsyncOpenAI
import os

llm = AsyncOpenAI(
    base_url=os.getenv("AI_PROXY_URL", "http://localhost:PROXY_PORT/v1"),
    api_key="local",
)
# Use CHOSEN_MODEL_CLAUDE or CHOSEN_MODEL_GEMINI as needed
```

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

| Provider | Keep | Remove |
|----------|------|--------|
| claude | `CLAUDE_CODE_OAUTH_TOKEN`, `AI_PROXY_URL` | `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` |
| gemini | `GEMINI_OAUTH_TOKEN`, `AI_PROXY_URL` | `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY` |
| both | `CLAUDE_CODE_OAUTH_TOKEN`, `GEMINI_OAUTH_TOKEN`, `AI_PROXY_URL` | `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `GOOGLE_API_KEY` |

### requirements.txt / pyproject.toml

Verify no remaining usage before removing:
```bash
grep -rn "anthropic\|google.generativeai" \
  --include="*.py" --exclude-dir={tests,test,__pycache__} .
```

| Provider | Remove if unused | Add |
|----------|-----------------|-----|
| claude | `anthropic`, `google-generativeai` | `openai>=1.0.0` |
| gemini | `anthropic`, `google-generativeai` | `openai>=1.0.0` |
| both | `anthropic`, `google-generativeai` | `openai>=1.0.0` |

---

## Phase 5: Verification

```bash
# Verify proxy models list
curl -s http://localhost:PROXY_PORT/v1/models \
  -H "Authorization: Bearer local" | python3 -m json.tool | head -30
```

Confirm chosen models appear in the list.
If proxy fails → `token-proxy --restart`, wait 5s, retry.

```bash
# Syntax check all modified files
python3 -m py_compile <each modified .py file>
```

Fix any syntax errors before proceeding.

---

## Phase 7: End-to-End LLM Validation

This is the most important check — verifying the model actually responds
through the proxy using the exact same code pattern written into the project.

### 7a. Live model test

```python
# Run this directly
import os, sys
from openai import OpenAI

PROXY_PORT = "PROXY_PORT"   # replace with actual port
client = OpenAI(
    base_url=f"http://localhost:{PROXY_PORT}/v1",
    api_key="local"
)

MODELS_TO_TEST = []
# Populate:
# claude → [CHOSEN_MODEL_CLAUDE]
# gemini → [CHOSEN_MODEL_GEMINI]
# both   → [CHOSEN_MODEL_CLAUDE, CHOSEN_MODEL_GEMINI]

TEST_PROMPT = (
    "Reply with exactly one sentence confirming you are working correctly. "
    "Include your model name in the reply."
)

results = {}
for model in MODELS_TO_TEST:
    print(f"\n[TEST] {model}...")
    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=100,
            messages=[{"role": "user", "content": TEST_PROMPT}]
        )
        reply = response.choices[0].message.content.strip()
        results[model] = {"status": "PASS", "reply": reply}
        print(f"[PASS] {reply}")
    except Exception as e:
        results[model] = {"status": "FAIL", "error": str(e)}
        print(f"[FAIL] {e}")

all_passed = all(r["status"] == "PASS" for r in results.values())
if not all_passed:
    sys.exit(1)
```

**If any FAIL — diagnose before proceeding:**

| Failure | Likely cause | Fix |
|---------|-------------|-----|
| `Connection refused` | Proxy not running | `token-proxy --restart` |
| `model not found` | Model not in proxy config | `token-proxy --restart` |
| `401 Unauthorized` | Token expired | `token-refresh --force` → `token-proxy --restart` |
| `timeout` | Proxy starting up | Wait 10s and retry |
| Gemini `quota exceeded` | gcloud token stale | `gcloud auth print-access-token` → `token-proxy --restart` |

### 7b. Project smoke test (if applicable)

```bash
find . -name "*.py" \
  -not -path "*/tests/*" -not -path "*/__pycache__/*" \
  | xargs grep -l "AI_PROXY_URL\|AsyncOpenAI\|chat.completions" 2>/dev/null \
  | head -5
```

If found, ask:
> "Found files that use the proxy. Would you like me to run a smoke test on any of them?"

---

## Phase 6: Summary Report

```
╔══════════════════════════════════════════════════════╗
║           /proxy-setup — Summary Report              ║
╠══════════════════════════════════════════════════════╣
║ Configuration                                        ║
║   Provider:  claude | gemini | both                  ║
║   Model(s):  CHOSEN_MODEL_CLAUDE / _GEMINI           ║
║   Cleanup:   replace_and_remove                      ║
║   Port:      PROXY_PORT                              ║
╠══════════════════════════════════════════════════════╣
║ System                                               ║
║   Claude token:  valid (N days left)                 ║
║   Gemini token:  valid / n/a                         ║
║   Proxy:  running on port PROXY_PORT                 ║
╠══════════════════════════════════════════════════════╣
║ Files Modified                                       ║
║   · src/services/llm.py                              ║
║     - replaced AsyncAnthropic → AsyncOpenAI          ║
║     - model → CHOSEN_MODEL_CLAUDE                    ║
║   · requirements.txt                                 ║
║     - removed: anthropic                             ║
║     - added:   openai>=1.0.0                         ║
║   · .env                                             ║
║     - removed: ANTHROPIC_API_KEY                     ║
║     - present: AI_PROXY_URL, CLAUDE_CODE_OAUTH_TOKEN ║
╠══════════════════════════════════════════════════════╣
║ Skipped                                              ║
║   · tests/ (excluded by policy)                      ║
╠══════════════════════════════════════════════════════╣
║ LLM Validation                                       ║
║   claude-sonnet-4-6:  ✓ PASS                         ║
║   Response: "I am claude-sonnet-4-6, working..."     ║
╠══════════════════════════════════════════════════════╣
║ Next Steps                                           ║
║   1. source ~/.bashrc                                ║
║   2. pip install -r requirements.txt                 ║
║   3. Test your app normally                          ║
╚══════════════════════════════════════════════════════╝
```

If Phase 7 failed, end with:
```
╠══════════════════════════════════════════════════════╣
║ ⚠  VALIDATION FAILED                                ║
║   One or more models did not respond.                ║
║   The proxy setup is incomplete.                     ║
║   See Phase 7 errors above for details.              ║
╚══════════════════════════════════════════════════════╝
```

**Setup is only considered complete when Phase 7 passes for all chosen models.**

---

## Constraints

- Phase 0 must complete all 3 wizard steps before any action
- Never skip the confirmation at end of wizard
- Phase 2 scan must be shown before any code changes
- Never attempt `claude --version` to refresh token — Claude has no silent refresh
- Never commit to git
- Never print token values
- Stop and explain clearly if any phase fails
