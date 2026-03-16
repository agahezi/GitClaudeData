#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# auth-token-manager — install.sh
# Interactive first-time setup wizard + fully automated install.
#
# Usage:
#   bash install.sh
#   AI_AUTH_CENTRAL_ENV=/custom/path/tokens.env bash install.sh
# ═══════════════════════════════════════════════════════════════
set -e

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CENTRAL_ENV="${AI_AUTH_CENTRAL_ENV:-$SKILL_DIR/config/tokens.env}"
CONFIG_DIR="$SKILL_DIR/config"
PROXY_PORT="${AI_PROXY_PORT:-8080}"
LOG_FILE="/tmp/ai-token-refresh.log"
CREDS_FILE="$HOME/.claude/.credentials.json"

if [ -f "$HOME/.zshrc" ] && [ "$(basename "$SHELL")" = "zsh" ]; then
  SHELL_RC="$HOME/.zshrc"
else
  SHELL_RC="$HOME/.bashrc"
fi

# ─── UI helpers ───────────────────────────────────────────────
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
CYAN='\033[0;36m'; BOLD='\033[1m'; DIM='\033[2m'; RESET='\033[0m'

ok()      { echo -e "  ${GREEN}✓${RESET} $*"; }
info()    { echo -e "  ${CYAN}·${RESET} $*"; }
warn()    { echo -e "  ${YELLOW}⚠${RESET} $*"; }
fail()    { echo -e "  ${RED}✗${RESET} $*"; exit 1; }
step()    { echo -e "\n${BOLD}${CYAN}┌─ Step $1 of $TOTAL_STEPS — $2 ${RESET}"; }
auto()    { echo -e "\n${BOLD}┌─ $1 ${RESET}${DIM}(automatic)${RESET}"; }
divider() { echo -e "${DIM}────────────────────────────────────────────────────${RESET}"; }

pause() {
  echo ""
  echo -e "  ${DIM}Press Enter to continue...${RESET}"
  read -r
}

confirm() {
  # $1 = question, returns 0 for yes
  echo -e "  ${BOLD}$1${RESET} ${DIM}[Y/n]${RESET} "
  read -r answer
  [[ "$answer" =~ ^[Nn]$ ]] && return 1 || return 0
}

wait_for_token() {
  # Poll credentials file until token appears, with timeout
  local timeout=120
  local elapsed=0
  echo -ne "  ${DIM}Waiting for token"
  while [ $elapsed -lt $timeout ]; do
    TOKEN=$(python3 -c "
import json, sys
try:
    d = json.load(open('$CREDS_FILE'))
    t = d.get('claudeAiOauth', {}).get('accessToken', '')
    print(t)
except: print('')
" 2>/dev/null)
    if [ -n "$TOKEN" ]; then
      echo -e "${RESET}"
      return 0
    fi
    echo -ne "."
    sleep 2
    elapsed=$((elapsed + 2))
  done
  echo -e "${RESET}"
  return 1
}

TOTAL_STEPS=4

# ══════════════════════════════════════════════════════════════
#   WELCOME
# ══════════════════════════════════════════════════════════════
clear
echo ""
echo -e "${BOLD}  auth-token-manager — First-Time Setup${RESET}"
divider
echo ""
echo "  This wizard will set up AI provider authentication"
echo "  on this machine. Here's what we'll do:"
echo ""
echo -e "  ${CYAN}Step 1${RESET}  Check prerequisites"
echo -e "  ${CYAN}Step 2${RESET}  Create your Claude OAuth token  ${DIM}(needs browser, ~2 min)${RESET}"
echo -e "  ${CYAN}Step 3${RESET}  Optional: Add Gemini token       ${DIM}(needs Google account)${RESET}"
echo -e "  ${CYAN}Step 4${RESET}  Automated setup                  ${DIM}(scripts, cron, proxy)${RESET}"
echo ""
echo -e "  ${DIM}After this setup, everything runs automatically.${RESET}"
echo -e "  ${DIM}You will only need to repeat Step 2 ~once per year.${RESET}"
echo ""
divider
pause

# ══════════════════════════════════════════════════════════════
#   STEP 1 — Prerequisites
# ══════════════════════════════════════════════════════════════
step 1 "Checking prerequisites"
echo ""

# python3
if command -v python3 >/dev/null 2>&1; then
  ok "Python 3 found: $(python3 --version)"
else
  fail "Python 3 is required but not found.\n  Install: sudo apt install python3  (or brew install python3)"
fi

# Node / npm (for claude CLI)
if command -v node >/dev/null 2>&1; then
  ok "Node.js found: $(node --version)"
else
  warn "Node.js not found — needed to install the Claude CLI."
  echo ""
  echo -e "  ${BOLD}Install Node.js now?${RESET}"
  echo -e "  ${DIM}We'll use nvm (recommended) — installs to your home directory.${RESET}"
  echo ""
  if confirm "Install Node.js via nvm?"; then
    echo ""
    info "Installing nvm..."
    curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
    export NVM_DIR="$HOME/.nvm"
    # shellcheck disable=SC1091
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    nvm install --lts
    nvm use --lts
    ok "Node.js installed: $(node --version)"
  else
    fail "Node.js is required. Install it manually and re-run this script."
  fi
fi

# claude CLI
if command -v claude >/dev/null 2>&1; then
  ok "Claude CLI found: $(claude --version 2>/dev/null | head -1)"
else
  warn "Claude CLI not found."
  echo ""
  if confirm "Install Claude CLI now?  (npm install -g @anthropic-ai/claude-code)"; then
    echo ""
    info "Installing Claude CLI..."
    npm install -g @anthropic-ai/claude-code
    ok "Claude CLI installed: $(claude --version 2>/dev/null | head -1)"
  else
    fail "Claude CLI is required. Install it with:\n  npm install -g @anthropic-ai/claude-code"
  fi
fi

# docker
if command -v docker >/dev/null 2>&1; then
  ok "Docker found: $(docker --version)"
  HAS_DOCKER=true
else
  warn "Docker not found — the CLI proxy will be skipped."
  info "You can still use tokens directly via environment variables."
  info "Install Docker later and run: token-proxy --start"
  HAS_DOCKER=false
fi

echo ""
ok "Prerequisites check complete."
pause

# ══════════════════════════════════════════════════════════════
#   STEP 2 — Claude OAuth Token
# ══════════════════════════════════════════════════════════════
step 2 "Create your Claude OAuth token"
echo ""

# Check if already exists
EXISTING_TOKEN=""
if [ -f "$CREDS_FILE" ]; then
  EXISTING_TOKEN=$(python3 -c "
import json
try:
    d = json.load(open('$CREDS_FILE'))
    print(d.get('claudeAiOauth', {}).get('accessToken', ''))
except: print('')
" 2>/dev/null)
fi

if [ -n "$EXISTING_TOKEN" ]; then
  EXPIRES=$(python3 -c "
import json
from datetime import datetime, timezone
try:
    d = json.load(open('$CREDS_FILE'))
    ms = d.get('claudeAiOauth', {}).get('expiresAt', 0)
    dt = datetime.fromtimestamp(ms/1000, tz=timezone.utc)
    days = (dt - datetime.now(tz=timezone.utc)).days
    print(f'{dt.strftime(\"%Y-%m-%d\")} ({days} days left)')
except: print('unknown')
" 2>/dev/null)
  ok "Existing token found — expires: $EXPIRES"
  TOKEN="$EXISTING_TOKEN"
  echo ""
  if ! confirm "Use existing token? (No = create a fresh one)"; then
    EXISTING_TOKEN=""
  fi
fi

if [ -z "$EXISTING_TOKEN" ]; then
  echo ""
  echo -e "  ${BOLD}What is a Claude OAuth token?${RESET}"
  echo ""
  echo "  It's a credential that links this machine to your Claude.ai"
  echo "  subscription (Pro or Max). Once created, it's valid for ~1 year"
  echo "  and auto-refreshes silently. You won't need to redo this often."
  echo ""
  divider
  echo ""
  echo -e "  ${BOLD}How it works:${RESET}"
  echo ""
  echo -e "  1. We run ${CYAN}claude setup-token${RESET}"
  echo "  2. It prints a URL in this terminal"
  echo "  3. You open that URL in your browser (any browser, any machine)"
  echo "  4. You sign in with your Claude.ai account and click Authorize"
  echo "  5. This terminal receives the token automatically"
  echo ""
  echo -e "  ${DIM}No copy-pasting needed — the browser and terminal sync automatically.${RESET}"
  echo ""
  divider
  pause

  echo ""
  info "Running: claude setup-token"
  echo ""
  echo -e "  ${YELLOW}→ A URL will appear below. Open it in your browser.${RESET}"
  echo -e "  ${YELLOW}→ Sign in to claude.ai and click Authorize.${RESET}"
  echo ""
  divider
  echo ""

  # Remove stale credentials so we can detect fresh token
  [ -f "$CREDS_FILE" ] && mv "$CREDS_FILE" "${CREDS_FILE}.bak" 2>/dev/null || true

  # Run setup-token in background so we can poll for the result
  claude setup-token &
  CLAUDE_PID=$!

  # Poll for token with animated dots
  if wait_for_token; then
    wait $CLAUDE_PID 2>/dev/null || true
    echo ""
    ok "Token received successfully!"
  else
    # Maybe user copy-pasted token manually — check one more time
    TOKEN=$(python3 -c "
import json
try:
    d = json.load(open('$CREDS_FILE'))
    print(d.get('claudeAiOauth', {}).get('accessToken', ''))
except: print('')
" 2>/dev/null)
    if [ -z "$TOKEN" ]; then
      kill $CLAUDE_PID 2>/dev/null || true
      echo ""
      echo -e "  ${RED}Token not detected after 2 minutes.${RESET}"
      echo ""
      echo "  Possible reasons:"
      echo "  · Browser auth was not completed"
      echo "  · Network issue prevented sync"
      echo ""
      echo "  Please try again:"
      echo -e "    ${CYAN}claude setup-token${RESET}"
      echo "  Then re-run this script."
      exit 1
    fi
  fi
fi

# Final token read
TOKEN=$(python3 -c "
import json
try:
    d = json.load(open('$CREDS_FILE'))
    print(d.get('claudeAiOauth', {}).get('accessToken', ''))
except: print('')
" 2>/dev/null)

[ -z "$TOKEN" ] && fail "Token not found. Please run 'claude setup-token' manually and retry."

echo ""
info "Token: ...${TOKEN: -16}"
pause

# ══════════════════════════════════════════════════════════════
#   STEP 3 — Gemini OAuth (Optional)
# ══════════════════════════════════════════════════════════════
step 3 "Gemini OAuth token  (optional)"
echo ""
echo "  Gemini OAuth lets you use Gemini models through your Google"
echo "  account — no separate billing needed."
echo ""
echo -e "  ${DIM}Requires: Google account with Gemini subscription${RESET}"
echo -e "  ${DIM}Token validity: ~1 hour (auto-refreshes via gcloud)${RESET}"
echo ""

GEMINI_TOKEN=""

if confirm "Set up Gemini OAuth now?"; then
  echo ""

  if command -v gcloud >/dev/null 2>&1; then
    ok "gcloud CLI already installed."
  else
    echo ""
    info "gcloud CLI not found — installing..."
    curl https://sdk.cloud.google.com | bash
    # shellcheck disable=SC1091
    source "$HOME/.bashrc" 2>/dev/null || true
    exec -l "$SHELL" &
    info "gcloud installed. You may need to open a new terminal if this fails."
  fi

  echo ""
  echo -e "  ${BOLD}→ A browser window will open.${RESET}"
  echo -e "  ${BOLD}→ Sign in with your Google account and click Allow.${RESET}"
  echo ""
  pause

  gcloud auth login --quiet || warn "gcloud auth login failed — skipping Gemini."
  gcloud auth application-default login --quiet || true

  GEMINI_TOKEN=$(gcloud auth print-access-token 2>/dev/null || echo "")

  if [ -n "$GEMINI_TOKEN" ]; then
    ok "Gemini token received."
  else
    warn "Could not get Gemini token — skipping. Run 'gcloud auth login' later."
  fi
else
  info "Skipping Gemini. You can add it later by running: gcloud auth login"
fi

pause

# ══════════════════════════════════════════════════════════════
#   STEP 4 — Automated setup
# ══════════════════════════════════════════════════════════════
step 4 "Automated setup"
echo ""
echo "  From this point on, everything is automatic."
echo "  Sit back — this takes about 30 seconds."
echo ""
pause

# ── 4a: Install scripts ──────────────────────────────────────
auto "Installing scripts"
mkdir -p "$SKILL_DIR/config"
chmod +x "$SKILL_DIR/scripts/"*.py
ok "Scripts ready at $SKILL_DIR/scripts/"

# ── 4b: Central token store ──────────────────────────────────
auto "Creating central token store"
mkdir -p "$CONFIG_DIR"
chmod 700 "$CONFIG_DIR"

cat > "$CONFIG_DIR/config.env" << EOF
AI_AUTH_CENTRAL_ENV="$CENTRAL_ENV"
AI_AUTH_REFRESH_DAYS="7"
AI_PROXY_PORT="$PROXY_PORT"
CLAUDE_CREDENTIALS_PATH="$CREDS_FILE"
EOF

mkdir -p "$(dirname "$CENTRAL_ENV")"
cat > "$CENTRAL_ENV" << EOF
# AI Provider Tokens — managed by auth-token-manager
# Last updated: $(date '+%Y-%m-%d %H:%M:%S')
# DO NOT commit this file to git.

CLAUDE_CODE_OAUTH_TOKEN="$TOKEN"
GEMINI_OAUTH_TOKEN="$GEMINI_TOKEN"
AI_PROXY_URL="http://localhost:$PROXY_PORT/v1"
EOF
chmod 600 "$CENTRAL_ENV"
ok "Tokens → $CENTRAL_ENV"

# ── 4c: Shell integration ─────────────────────────────────────
auto "Wiring into shell ($SHELL_RC)"
SOURCE_BLOCK="
# ── auth-token-manager ──────────────────────────────────────
[ -f \"$CENTRAL_ENV\" ] && set -a && source \"$CENTRAL_ENV\" && set +a
alias token-status='python3 $SKILL_DIR/scripts/refresh_token.py --status'
alias token-refresh='python3 $SKILL_DIR/scripts/refresh_token.py'
alias token-link='python3 $SKILL_DIR/scripts/refresh_token.py --link'
alias token-proxy='python3 $SKILL_DIR/scripts/proxy_manager.py'
# ────────────────────────────────────────────────────────────"

if ! grep -q "auth-token-manager" "$SHELL_RC" 2>/dev/null; then
  echo "$SOURCE_BLOCK" >> "$SHELL_RC"
  ok "Added to $SHELL_RC"
else
  ok "Already in $SHELL_RC"
fi

# ── 4d: Cron ─────────────────────────────────────────────────
auto "Installing daily cron job"
CRON_LINE="0 6 * * * python3 $SKILL_DIR/scripts/refresh_token.py >> $LOG_FILE 2>&1"
EXISTING_CRON=$(crontab -l 2>/dev/null || echo "")
if ! echo "$EXISTING_CRON" | grep -q "auth-token-manager"; then
  (echo "$EXISTING_CRON"; echo "# auth-token-manager — daily token refresh"; echo "$CRON_LINE") | crontab -
  ok "Cron installed — runs daily at 06:00 → $LOG_FILE"
else
  ok "Cron already installed"
fi

# ── 4e: CLI Proxy ────────────────────────────────────────────
auto "Starting CLI Proxy (Docker)"
if [ "$HAS_DOCKER" = true ]; then
  python3 "$SKILL_DIR/scripts/proxy_manager.py" \
    --start --token "$TOKEN" --port "$PROXY_PORT" \
    && ok "Proxy running → http://localhost:$PROXY_PORT/v1" \
    || warn "Proxy failed to start — run: token-proxy --start"
else
  warn "Docker not available — proxy skipped."
  info "Install Docker and run: token-proxy --start"
fi

# ══════════════════════════════════════════════════════════════
#   DONE
# ══════════════════════════════════════════════════════════════
echo ""
echo ""
divider
echo -e "  ${GREEN}${BOLD}Setup complete!${RESET}"
divider
echo ""
echo -e "  ${BOLD}What was configured:${RESET}"
echo ""
echo -e "  ${GREEN}✓${RESET} Token stored centrally at:"
echo -e "    ${DIM}$CENTRAL_ENV${RESET}"
echo ""
echo -e "  ${GREEN}✓${RESET} Auto-loaded in every new terminal session"
echo ""
echo -e "  ${GREEN}✓${RESET} Daily auto-refresh via cron (log: $LOG_FILE)"
echo ""
if [ "$HAS_DOCKER" = true ]; then
echo -e "  ${GREEN}✓${RESET} CLI Proxy running:"
echo -e "    ${DIM}http://localhost:$PROXY_PORT/v1${RESET}"
echo -e "    ${DIM}Use model names: claude, claude-sonnet-4-6, gemini${RESET}"
fi
echo ""
divider
echo ""
echo -e "  ${BOLD}Reload your shell, then use these commands:${RESET}"
echo ""
echo -e "    ${CYAN}source $SHELL_RC${RESET}             reload now"
echo -e "    ${CYAN}token-status${RESET}                 check token health"
echo -e "    ${CYAN}token-link /path/to/project${RESET}  wire a project"
echo -e "    ${CYAN}token-proxy --status${RESET}         check proxy"
echo ""
echo -e "  ${BOLD}Connect any project to the proxy:${RESET}"
echo ""
echo -e "    ${DIM}OPENAI_BASE_URL=http://localhost:$PROXY_PORT/v1${RESET}"
echo -e "    ${DIM}OPENAI_API_KEY=local${RESET}"
echo ""
echo -e "  ${BOLD}From a Docker container:${RESET}"
echo ""
echo -e "    ${DIM}OPENAI_BASE_URL=http://host.docker.internal:$PROXY_PORT/v1${RESET}"
echo ""
divider
echo ""
echo -e "  ${DIM}Next time you need to redo token auth (~1 year from now):${RESET}"
echo -e "  ${DIM}just run: claude setup-token && token-refresh --force${RESET}"
echo ""
