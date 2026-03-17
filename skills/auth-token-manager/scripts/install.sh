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
INSTALL_DIR="$HOME/.local/lib/auth-token-manager"
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
section() { echo -e "\n${BOLD}${CYAN}── Step $1 of 4 — $2${RESET}\n"; }
pause()   { echo -e "\n  ${DIM}Enter להמשך...${RESET}"; read -r; }
confirm() { echo -e "  ${BOLD}$1${RESET} ${DIM}[Y/n]${RESET} "; read -r a; [[ "$a" =~ ^[Nn]$ ]] && return 1 || return 0; }

wait_for_token() {
  local elapsed=0
  echo -ne "  ${DIM}ממתין לטוקן"
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
echo "  מה יקרה:"
echo -e "  ${CYAN}Step 1${RESET}  בדיקת תלויות"
echo -e "  ${CYAN}Step 2${RESET}  Claude OAuth token  ${DIM}(browser, פעם אחת)${RESET}"
echo -e "  ${CYAN}Step 3${RESET}  Gemini OAuth         ${DIM}(אופציונלי)${RESET}"
echo -e "  ${CYAN}Step 4${RESET}  הגדרה אוטומטית מלאה  ${DIM}(central env, cron, proxy)${RESET}"
echo ""
echo -e "  ${DIM}לאחר wizard זה — הכל רץ אוטומטית.${RESET}"
echo -e "  ${DIM}חידוש נדרש רק ~פעם בשנה (2 דקות).${RESET}"
echo ""
echo -e "  ${DIM}לשילוב בפרויקט ספציפי לאחר wizard זה: /proxy-setup${RESET}"
echo ""
pause

# ══════════════════════════════════════════════════════════════
section 1 "בדיקת תלויות"

# python3
command -v python3 >/dev/null 2>&1 \
  && ok "Python 3: $(python3 --version)" \
  || fail "Python 3 נדרש: sudo apt install python3"

# Node.js
if command -v node >/dev/null 2>&1; then
  ok "Node.js: $(node --version)"
else
  warn "Node.js לא נמצא — נדרש לClaude CLI."
  if confirm "התקן Node.js דרך nvm?"; then
    curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    nvm install --lts && nvm use --lts
    ok "Node.js: $(node --version)"
  else
    fail "Node.js נדרש. התקן ידנית ורוץ שוב."
  fi
fi

# Claude CLI
if command -v claude >/dev/null 2>&1; then
  ok "Claude CLI: $(claude --version 2>/dev/null | head -1)"
else
  warn "Claude CLI לא נמצא."
  if confirm "התקן Claude CLI? (npm install -g @anthropic-ai/claude-code)"; then
    npm install -g @anthropic-ai/claude-code
    ok "Claude CLI: $(claude --version 2>/dev/null | head -1)"
  else
    fail "Claude CLI נדרש."
  fi
fi

# Docker
if command -v docker >/dev/null 2>&1; then
  ok "Docker: $(docker --version)"
  HAS_DOCKER=true
else
  warn "Docker לא נמצא — proxy יידחה לאחר ההתקנה."
  info "לאחר התקנת Docker: token-proxy --start"
  HAS_DOCKER=false
fi

ok "כל התלויות הנדרשות מוכנות."
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
    print(f'{dt.strftime(\"%Y-%m-%d\")} ({days} ימים נותרו)')
except: print('לא ידוע')
" 2>/dev/null)
  ok "טוקן קיים — פוקע: $EXPIRES"
  TOKEN="$EXISTING_TOKEN"
  confirm "השתמש בטוקן הקיים? (No = צור חדש)" || EXISTING_TOKEN=""
fi

if [ -z "$EXISTING_TOKEN" ]; then
  echo ""
  echo -e "  ${BOLD}מה זה Claude OAuth token?${RESET}"
  echo ""
  echo "  קישור בין מחשב זה לחשבון Claude.ai שלך (Pro/Max)."
  echo "  תקף ~שנה. אין חידוש אוטומטי."
  echo "  בסוף השנה — חידוש ידני של ~2 דקות."
  echo ""
  echo "  ───────────────────────────────────────────────────"
  echo ""
  echo -e "  ${BOLD}מה יקרה עכשיו:${RESET}"
  echo -e "  1. נריץ ${CYAN}claude setup-token${RESET}"
  echo "  2. יופיע URL בטרמינל"
  echo "  3. פתח ב-browser, התחבר לclaude.ai, לחץ Authorize"
  echo "  4. הטרמינל מקבל את הטוקן אוטומטית — אין copy/paste"
  echo ""
  pause

  [ -f "$CREDS_FILE" ] && mv "$CREDS_FILE" "${CREDS_FILE}.bak.$(date +%s)" 2>/dev/null || true

  echo -e "  ${YELLOW}→ פתח את ה-URL שיופיע בדפדפן ואשר.${RESET}"
  echo ""

  claude setup-token &
  CLAUDE_PID=$!

  if wait_for_token; then
    wait $CLAUDE_PID 2>/dev/null || true
    ok "טוקן התקבל בהצלחה!"
  else
    kill $CLAUDE_PID 2>/dev/null || true
    echo ""
    fail "טוקן לא התקבל תוך 2 דקות. הרץ 'claude setup-token' ידנית, ואז bash install.sh מחדש."
  fi
fi

TOKEN=$(python3 -c "
import json
try:
    d=json.load(open('$CREDS_FILE'))
    print(d.get('claudeAiOauth',{}).get('accessToken',''))
except: print('')
" 2>/dev/null)
[ -z "$TOKEN" ] && fail "לא ניתן לקרוא טוקן מהקובץ."

info "Token: ...${TOKEN: -16}"
pause

# ══════════════════════════════════════════════════════════════
section 3 "Gemini OAuth (אופציונלי)"

echo "  מאפשר שימוש במודלי Gemini דרך חשבון Google."
echo -e "  ${DIM}תוקף: ~שעה (gcloud מחדש אוטומטית בכל ריצת cron)${RESET}"
echo ""

GEMINI_TOKEN=""
if confirm "הגדר Gemini OAuth?"; then
  if ! command -v gcloud >/dev/null 2>&1; then
    info "מתקין gcloud CLI..."
    curl https://sdk.cloud.google.com | bash
    source "$HOME/.bashrc" 2>/dev/null || true
  fi
  echo ""
  echo -e "  ${YELLOW}→ יפתח דפדפן להתחברות לGoogle.${RESET}"
  pause
  gcloud auth login --quiet           || warn "gcloud auth login נכשל — דולג."
  gcloud auth application-default login --quiet || true
  GEMINI_TOKEN=$(gcloud auth print-access-token 2>/dev/null || echo "")
  [ -n "$GEMINI_TOKEN" ] && ok "Gemini token התקבל." || warn "לא ניתן לקבל Gemini token — דולג."
else
  info "דולג. ניתן להוסיף מאוחר יותר: gcloud auth login"
fi
pause

# ══════════════════════════════════════════════════════════════
section 4 "הגדרה אוטומטית"
echo "  מכאן הכל אוטומטי."
echo ""

# Scripts
mkdir -p "$INSTALL_DIR/scripts"
cp "$SKILL_DIR/scripts/refresh_token.py" "$INSTALL_DIR/scripts/"
cp "$SKILL_DIR/scripts/proxy_manager.py"  "$INSTALL_DIR/scripts/"
chmod +x "$INSTALL_DIR/scripts/"*.py
ok "Scripts → $INSTALL_DIR/scripts/"

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
# ────────────────────────────────────────────────────────────"
if ! grep -q "auth-token-manager" "$SHELL_RC" 2>/dev/null; then
  echo "$SOURCE_BLOCK" >> "$SHELL_RC"
  ok "Shell aliases → $SHELL_RC"
else
  ok "Shell aliases — כבר קיים"
fi

# Cron
CRON_LINE="0 6 * * * python3 $INSTALL_DIR/scripts/refresh_token.py >> $LOG_FILE 2>&1"
EXISTING_CRON=$(crontab -l 2>/dev/null || echo "")
if ! echo "$EXISTING_CRON" | grep -q "auth-token-manager"; then
  (echo "$EXISTING_CRON"; echo "# auth-token-manager"; echo "$CRON_LINE") | crontab -
  ok "Cron — יומי ב-06:00 → $LOG_FILE"
else
  ok "Cron — כבר קיים"
fi

# Proxy
if [ "$HAS_DOCKER" = true ]; then
  python3 "$INSTALL_DIR/scripts/proxy_manager.py" \
    --start --token "$TOKEN" --port "$PROXY_PORT" \
    && ok "Proxy → http://localhost:$PROXY_PORT/v1" \
    || warn "Proxy נכשל — הרץ מאוחר יותר: token-proxy --start"
else
  warn "Docker לא זמין — proxy לא הופעל"
fi

# ══════════════════════════════════════════════════════════════
echo ""
echo "  ══════════════════════════════════════════════════════"
echo -e "  ${GREEN}${BOLD}  ✓  Machine Setup Complete!${RESET}"
echo "  ══════════════════════════════════════════════════════"
echo ""
echo -e "  ${BOLD}מה הוגדר:${RESET}"
echo "  ✓  Claude token שמור מרכזית"
echo "  ✓  נטען אוטומטית בכל פתיחת טרמינל"
echo "  ✓  Cron יומי — מתריע לפני פקיעה"
[ "$HAS_DOCKER" = true ] && echo "  ✓  Proxy רץ → http://localhost:$PROXY_PORT/v1"
echo ""
echo "  ─────────────────────────────────────────────────────"
echo -e "  ${BOLD}לשילוב בפרויקט:${RESET}"
echo ""
echo -e "    ${CYAN}source $SHELL_RC${RESET}   # טען aliases"
echo -e "    ${CYAN}/proxy-setup${RESET}       # שלב פרויקט (agent command)"
echo ""
echo "  ─────────────────────────────────────────────────────"
echo -e "  ${DIM}חידוש שנתי (~שנה מהיום, ~2 דקות):${RESET}"
echo -e "  ${DIM}  claude setup-token && token-refresh --force${RESET}"
echo ""
