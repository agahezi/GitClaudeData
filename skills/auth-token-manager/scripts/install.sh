#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# auth-token-manager — install.sh
#
# PURPOSE: First-time machine setup. Run ONCE per machine.
#          Creates token, central env, cron, Docker proxy.
#          After this — everything is automatic.
#
# DOES NOT: integrate projects (use /proxy-setup agent for that)
#
# Usage:
#   bash install.sh
#   AI_AUTH_CENTRAL_ENV=/custom/path/tokens.env bash install.sh
# ═══════════════════════════════════════════════════════════════
set -e

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CENTRAL_ENV="${AI_AUTH_CENTRAL_ENV:-$HOME/.config/ai-auth/tokens.env}"
CONFIG_DIR="$HOME/.config/ai-auth"
INSTALL_DIR="$HOME/.claude/skills/auth-token-manager"
PROXY_PORT="${AI_PROXY_PORT:-8080}"
LOG_FILE="/tmp/ai-token-refresh.log"
CREDS_FILE="$HOME/.claude/.credentials.json"

if [ "$(basename "$SHELL")" = "zsh" ] && [ -f "$HOME/.zshrc" ]; then
  SHELL_RC="$HOME/.zshrc"
else
  SHELL_RC="$HOME/.bashrc"
fi

# ─── UI ───────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'
BOLD='\033[1m'; DIM='\033[2m'; RESET='\033[0m'

ok()      { echo -e "  ${GREEN}✓${RESET} $*"; }
info()    { echo -e "  ${CYAN}·${RESET} $*"; }
warn()    { echo -e "  ${YELLOW}⚠${RESET} $*"; }
fail()    { echo -e "  ✗ $*"; exit 1; }
section() { echo -e "\n${BOLD}${CYAN}── Step $1 of 5 — $2${RESET}\n"; }
pause()   { echo -e "\n  ${DIM}Press Enter to continue...${RESET}"; read -r; }
confirm() { echo -e "  ${BOLD}$1${RESET} ${DIM}[Y/n]${RESET} "; read -r a; [[ "$a" =~ ^[Nn]$ ]] && return 1 || return 0; }

wait_for_token() {
  local elapsed=0
  echo -ne "  ${DIM}Waiting for token"
  while [ $elapsed -lt 120 ]; do
    TOKEN=$(python3 -c "
import json
try:
    d=json.load(open('$CREDS_FILE'))
    print(d.get('claudeAiOauth',{}).get('accessToken',''))
except: print('')
" 2>/dev/null)
    [ -n "$TOKEN" ] && echo -e "${RESET}" && return 0
    echo -ne "."; sleep 2; elapsed=$((elapsed+2))
  done
  echo -e "${RESET}"; return 1
}

# ══════════════════════════════════════════════════════════════
clear
echo ""
echo -e "${BOLD}  auth-token-manager — Machine Setup Wizard${RESET}"
echo "  ════════════════════════════════════════════════════"
echo ""
echo "  What will happen:"
echo -e "  ${CYAN}Step 1${RESET}  Check dependencies"
echo -e "  ${CYAN}Step 2${RESET}  Claude OAuth token  ${DIM}(browser, one-time)${RESET}"
echo -e "  ${CYAN}Step 3${RESET}  Gemini OAuth         ${DIM}(optional)${RESET}"
echo -e "  ${CYAN}Step 4${RESET}  Automated setup      ${DIM}(central env, cron, proxy)${RESET}"
echo -e "  ${CYAN}Step 5${RESET}  CLIProxyAPI login + verification"
echo ""
echo -e "  ${DIM}After this wizard — everything runs automatically.${RESET}"
echo -e "  ${DIM}Renewal needed only ~once a year (2 min).${RESET}"
echo ""
echo -e "  ${DIM}To integrate a project after this wizard: /proxy-setup${RESET}"
echo ""
pause

# ══════════════════════════════════════════════════════════════
section 1 "Checking dependencies"

# python3
command -v python3 >/dev/null 2>&1 \
  && ok "Python 3: $(python3 --version)" \
  || fail "Python 3 is required: sudo apt install python3"

# Node.js
if command -v node >/dev/null 2>&1; then
  ok "Node.js: $(node --version)"
else
  warn "Node.js not found — required for Claude CLI."
  if confirm "Install Node.js via nvm?"; then
    curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    nvm install --lts && nvm use --lts
    ok "Node.js: $(node --version)"
  else
    fail "Node.js is required. Install manually and re-run."
  fi
fi

# Claude CLI
if command -v claude >/dev/null 2>&1; then
  ok "Claude CLI: $(claude --version 2>/dev/null | head -1)"
else
  warn "Claude CLI not found."
  if confirm "Install Claude CLI? (npm install -g @anthropic-ai/claude-code)"; then
    npm install -g @anthropic-ai/claude-code
    ok "Claude CLI: $(claude --version 2>/dev/null | head -1)"
  else
    fail "Claude CLI is required."
  fi
fi

# Docker
if command -v docker >/dev/null 2>&1; then
  ok "Docker: $(docker --version)"
  HAS_DOCKER=true
else
  warn "Docker not found — proxy setup will be skipped."
  info "After installing Docker: token-proxy --start"
  HAS_DOCKER=false
fi

ok "All required dependencies found."
pause

# ══════════════════════════════════════════════════════════════
section 2 "Claude OAuth Token"

# Check existing token
EXISTING_TOKEN=""
if [ -f "$CREDS_FILE" ]; then
  EXISTING_TOKEN=$(python3 -c "
import json
try:
    d=json.load(open('$CREDS_FILE'))
    print(d.get('claudeAiOauth',{}).get('accessToken',''))
except: print('')
" 2>/dev/null)
fi

if [ -n "$EXISTING_TOKEN" ]; then
  EXPIRES=$(python3 -c "
import json
from datetime import datetime,timezone
try:
    d=json.load(open('$CREDS_FILE'))
    ms=d['claudeAiOauth']['expiresAt']
    dt=datetime.fromtimestamp(ms/1000,tz=timezone.utc)
    days=(dt-datetime.now(tz=timezone.utc)).days
    print(f'{dt.strftime(\"%Y-%m-%d\")} ({days} days left)')
except: print('unknown')
" 2>/dev/null)
  ok "Existing token found — expires: $EXPIRES"
  TOKEN="$EXISTING_TOKEN"
  confirm "Use existing token? (No = create new one)" || EXISTING_TOKEN=""
fi

if [ -z "$EXISTING_TOKEN" ]; then
  echo ""
  echo -e "  ${BOLD}What is a Claude OAuth token?${RESET}"
  echo ""
  echo "  A credential linking this machine to your Claude.ai account (Pro/Max)."
  echo "  Valid ~1 year. No automatic renewal."
  echo "  At end of year — manual renewal takes ~2 minutes."
  echo ""
  echo "  ───────────────────────────────────────────────────"
  echo ""
  echo -e "  ${BOLD}What will happen now:${RESET}"
  echo -e "  1. We run ${CYAN}claude setup-token${RESET}"
  echo "  2. A URL appears in this terminal"
  echo "  3. Open in browser, sign in to claude.ai, click Authorize"
  echo "  4. Terminal receives token automatically — no copy/paste needed"
  echo ""
  pause

  echo -e "  ${YELLOW}→ Open the URL that appears in your browser and authorize.${RESET}"
  echo -e "  ${YELLOW}→ If the token is printed here, the script captures it automatically.${RESET}"
  echo ""

  # Run setup-token — show output in real-time AND capture it
  # (using tee so the URL appears immediately while we also save the output)
  SETUP_TMPFILE=$(mktemp)
  claude setup-token 2>&1 | tee "$SETUP_TMPFILE"
  echo ""
  SETUP_OUTPUT=$(cat "$SETUP_TMPFILE")
  rm -f "$SETUP_TMPFILE"

  # Try to extract token from stdout first (headless flow prints it directly)
  STDOUT_TOKEN=$(echo "$SETUP_OUTPUT" | grep -o 'sk-ant-oat01-[A-Za-z0-9_-]*' | head -1)

  if [ -n "$STDOUT_TOKEN" ]; then
    # Token was printed to stdout — write it to credentials file
    TOKEN="$STDOUT_TOKEN"
    mkdir -p "$(dirname "$CREDS_FILE")"
    python3 -c "
import json, os, time
creds_file = '$CREDS_FILE'
try:
    existing = json.load(open(creds_file)) if os.path.exists(creds_file) else {}
except:
    existing = {}
oauth = existing.setdefault('claudeAiOauth', {})
oauth['accessToken'] = '$STDOUT_TOKEN'
# Set expiresAt to 1 year from now if not already set
if 'expiresAt' not in oauth or oauth['expiresAt'] == 0:
    oauth['expiresAt'] = int((time.time() + 365 * 24 * 3600) * 1000)
json.dump(existing, open(creds_file, 'w'), indent=2)
"
    ok "Token captured from output and saved."
  else
    # Token not in stdout — check credentials file (browser flow)
    if wait_for_token; then
      ok "Token received successfully!"
    else
      echo ""
      fail "Token not received. Run 'claude setup-token' manually, copy the token, then run: token-refresh --force"
    fi
  fi
fi

TOKEN=$(python3 -c "
import json, os
# Check env var first (set manually by user)
import os
env_token = os.environ.get('CLAUDE_CODE_OAUTH_TOKEN', '')
if env_token:
    print(env_token)
else:
    try:
        d=json.load(open('$CREDS_FILE'))
        print(d.get('claudeAiOauth',{}).get('accessToken',''))
    except: print('')
" 2>/dev/null)
[ -z "$TOKEN" ] && fail "Could not read token. Set it manually: export CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-... then re-run."

info "Token: ...${TOKEN: -16}"
pause

# ══════════════════════════════════════════════════════════════
section 3 "Gemini OAuth (optional)"

echo "  Enables using Gemini models through your Google account."
echo -e "  ${DIM}Token validity: ~1 hour (gcloud auto-refreshes on every cron run)${RESET}"
echo ""

GEMINI_TOKEN=""
if confirm "Set up Gemini OAuth?"; then
  if ! command -v gcloud >/dev/null 2>&1; then
    info "Installing gcloud CLI..."
    curl https://sdk.cloud.google.com | bash
    source "$HOME/.bashrc" 2>/dev/null || true
  fi
  echo ""
  echo -e "  ${YELLOW}→ A browser will open to sign in to Google.${RESET}"
  pause
  gcloud auth login --quiet           || warn "gcloud auth login failed — skipping."
  gcloud auth application-default login --quiet || true
  GEMINI_TOKEN=$(gcloud auth print-access-token 2>/dev/null || echo "")
  [ -n "$GEMINI_TOKEN" ] && ok "Gemini token received." || warn "Could not get Gemini token — skipping."
else
  info "Skipping. Can be added later: gcloud auth login"
fi
pause

# ══════════════════════════════════════════════════════════════
section 4 "Automated setup"
echo "  From here everything is automatic."
echo ""

# Scripts are already in place — INSTALL_DIR points to the skill directory
chmod +x "$INSTALL_DIR/scripts/"*.sh "$INSTALL_DIR/scripts/"*.py 2>/dev/null || true
ok "Scripts ready at $INSTALL_DIR/scripts/"

# Config
mkdir -p "$CONFIG_DIR" && chmod 700 "$CONFIG_DIR"
cat > "$CONFIG_DIR/config.env" << EOF
AI_AUTH_CENTRAL_ENV="$CENTRAL_ENV"
AI_PROXY_PORT="$PROXY_PORT"
CLAUDE_CREDENTIALS_PATH="$CREDS_FILE"
EOF
ok "Config → $CONFIG_DIR/config.env"

# Central tokens.env
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

# Shell
SOURCE_BLOCK="
# ── auth-token-manager ──────────────────────────────────────
[ -f \"$CENTRAL_ENV\" ] && set -a && source \"$CENTRAL_ENV\" && set +a
alias token-status='python3 $INSTALL_DIR/scripts/refresh_token.py --status'
alias token-refresh='python3 $INSTALL_DIR/scripts/refresh_token.py'
alias token-link='python3 $INSTALL_DIR/scripts/refresh_token.py --link'
alias token-proxy='python3 $INSTALL_DIR/scripts/proxy_manager.py'
alias cliproxy='bash $INSTALL_DIR/scripts/cliproxyapi_manager.sh'
# ────────────────────────────────────────────────────────────"
if ! grep -q "auth-token-manager" "$SHELL_RC" 2>/dev/null; then
  echo "$SOURCE_BLOCK" >> "$SHELL_RC"
  ok "Shell aliases → $SHELL_RC"
else
  ok "Shell aliases — already present"
fi

# Cron
CRON_LINE="0 6 * * * python3 $INSTALL_DIR/scripts/refresh_token.py >> $LOG_FILE 2>&1"
EXISTING_CRON=$(crontab -l 2>/dev/null || echo "")
if ! echo "$EXISTING_CRON" | grep -q "auth-token-manager"; then
  (echo "$EXISTING_CRON"; echo "# auth-token-manager"; echo "$CRON_LINE") | crontab -
  ok "Cron — runs daily at 06:00 → $LOG_FILE"
else
  ok "Cron — already installed"
fi

# Proxy
if [ "$HAS_DOCKER" = true ]; then
  python3 "$INSTALL_DIR/scripts/proxy_manager.py" \
    --start --token "$TOKEN" --port "$PROXY_PORT" \
    && ok "Proxy → http://localhost:$PROXY_PORT/v1" \
    || warn "Proxy failed — run later: token-proxy --start"
else
  warn "Docker not available — proxy not started"
fi

# CLIProxyAPI — fixes OAuth 401 errors for Claude Code CLI
if [ "$HAS_DOCKER" = true ]; then
  bash "$INSTALL_DIR/scripts/cliproxyapi_manager.sh" setup     && ok "CLIProxyAPI configured → run 'cliproxy login' to authenticate"     || warn "CLIProxyAPI setup failed — run: cliproxy setup"
fi

# ══════════════════════════════════════════════════════════════
section 5 "CLIProxyAPI Login + Final Verification"

if [ "$HAS_DOCKER" = true ]; then
  # Check if CLIProxyAPI already has tokens — skip login if so
  TOKEN_DIR="$HOME/.config/ai-auth/cliproxyapi/tokens"
  TOKEN_COUNT=$(find "$TOKEN_DIR" -name "*.json" 2>/dev/null | wc -l | tr -d ' ')

  if [ "$TOKEN_COUNT" -gt 0 ]; then
    ok "CLIProxyAPI already has $TOKEN_COUNT token(s) — skipping login."
    echo ""
  else
    echo "  This is the final one-time step."
    echo "  After this, Claude Code CLI will never get a 401 error again."
    echo ""

  # Detect SSH session
  if [ -n "$SSH_CLIENT" ] || [ -n "$SSH_TTY" ]; then
    SERVER_IP=$(hostname -I | awk '{print $1}')
    echo -e "  ${YELLOW}Remote session detected (SSH).${RESET}"
    echo ""
    echo "  The OAuth callback (port 54545) must be reachable from your browser."
    echo "  This requires your current SSH connection to include port forwarding."
    echo ""
    echo -e "  ${BOLD}Is your current SSH connection already using port forwarding?${RESET}"
    echo -e "  i.e. did you connect with:"
    echo -e "    ${CYAN}ssh -L 54545:127.0.0.1:54545 $(whoami)@$SERVER_IP${RESET}"
    echo ""
    echo "  1) Yes — my SSH already has -L 54545 (ready to proceed)"
    echo "  2) No  — I need to reconnect with port forwarding"
    echo ""
    echo -ne "  Choice [1/2]: "
    read -r ssh_choice
    echo ""

    if [ "$ssh_choice" != "1" ]; then
      echo "  Open a NEW terminal on your local machine and connect with:"
      echo ""
      echo -e "    ${CYAN}ssh -L 54545:127.0.0.1:54545 $(whoami)@$SERVER_IP${RESET}"
      echo ""
      echo "  Then re-run this script from that new connection."
      echo ""
      echo "  Skipping CLIProxyAPI login for now."
      echo "  Run later: cliproxy login"
      echo ""
      HAS_DOCKER=false   # skip login but continue to summary
    fi
  fi

  echo "  Starting CLIProxyAPI login..."
  echo -e "  ${YELLOW}→ A URL will appear. Open it in your browser and authorize.${RESET}"
  echo ""

  bash "$INSTALL_DIR/scripts/cliproxyapi_manager.sh" login
  fi  # end else (no existing tokens)

  # ── Final verification ────────────────────────────────────
  echo ""
  echo "  ─────────────────────────────────────────────────────"
  echo -e "  ${BOLD}Final verification — sending test message to Claude...${RESET}"
  echo ""

  # Reload env so ANTHROPIC_BASE_URL is set
  set -a && source "$CENTRAL_ENV" && set +a 2>/dev/null || true
  export ANTHROPIC_BASE_URL="http://localhost:8317"
  export ANTHROPIC_AUTH_TOKEN="sk-dummy"

  # Test via curl directly to CLIProxyAPI
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    --max-time 15 \
    -X POST "http://localhost:8317/v1/messages" \
    -H "Content-Type: application/json" \
    -H "x-api-key: dummy" \
    -H "anthropic-version: 2023-06-01" \
    -d '{"model":"claude-sonnet-4-5-20250929","max_tokens":10,"messages":[{"role":"user","content":"hi"}]}' \
    2>/dev/null)

  case "$HTTP_CODE" in
    200)
      ok "CLIProxyAPI responded (HTTP 200) — auth is working!"
      echo ""
      echo -e "  ${GREEN}${BOLD}Everything is working end-to-end.${RESET}"
      ;;
    529)
      warn "Anthropic servers temporarily overloaded (529) — auth is OK."
      ok "Try: claude \"hello\" in a few minutes."
      ;;
    401)
      warn "Authentication error (401) — run: cliproxy login"
      ;;
    000)
      warn "Could not reach proxy — run: cliproxy start"
      ;;
    *)
      warn "HTTP $HTTP_CODE — run: cliproxy status"
      ;;
  esac
else
  warn "Docker not available — skipping CLIProxyAPI login and verification."
fi

# ══════════════════════════════════════════════════════════════
echo ""
echo "  ══════════════════════════════════════════════════════"
echo -e "  ${GREEN}${BOLD}  ✓  Machine Setup Complete!${RESET}"
echo "  ══════════════════════════════════════════════════════"
echo ""
echo -e "  ${BOLD}What was configured:${RESET}"
echo "  ✓  Claude token stored centrally"
echo "  ✓  Auto-loaded in every new terminal session"
echo "  ✓  Daily cron — warns before token expiry"
[ "$HAS_DOCKER" = true ] && echo "  ✓  Proxy running → http://localhost:$PROXY_PORT/v1"
[ "$HAS_DOCKER" = true ] && echo "  ✓  CLIProxyAPI authenticated → 401 errors fixed"
echo ""
echo "  ─────────────────────────────────────────────────────"
echo -e "  ${BOLD}To integrate a project:${RESET}"
echo ""
echo -e "    ${CYAN}source $SHELL_RC${RESET}   # reload aliases"
echo -e "    ${CYAN}/proxy-setup${RESET}       # integrate a project (agent command)"
echo ""
echo "  ─────────────────────────────────────────────────────"
echo -e "  ${DIM}Annual token renewal (~once/year, ~2 min):${RESET}"
echo -e "  ${DIM}  claude setup-token && token-refresh --force${RESET}"
echo -e "  ${DIM}  cliproxy login${RESET}"
echo ""
