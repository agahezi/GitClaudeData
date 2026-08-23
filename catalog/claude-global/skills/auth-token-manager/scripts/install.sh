#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# auth-token-manager — install.sh
#
# PURPOSE: Smart idempotent setup script. Safe to run anytime.
#          - Fresh machine → installs everything
#          - Expired OAuth → renews token only
#          - Everything OK → prints status and exits
#          - Partial install → completes only what is missing
#
# UPDATED: CLIProxyAPI centralized — uses ONE container in
#          ~/proxy-stack/ via docker-compose instead of
#          per-project containers.
#
# Usage:
#   bash install.sh          # smart check + fix
#   bash install.sh --status # just print status, no changes
# ═══════════════════════════════════════════════════════════════
set -e

# ─── Constants ─────────────────────────────────────────────────
CENTRAL_ENV="${AI_AUTH_CENTRAL_ENV:-$HOME/.config/ai-auth/tokens.env}"
CONFIG_DIR="$HOME/.config/ai-auth"
INSTALL_DIR="$HOME/.claude/skills/auth-token-manager"
LOG_FILE="/tmp/ai-token-refresh.log"
CREDS_FILE="$HOME/.claude/.credentials.json"
PROXY_STACK_DIR="$HOME/proxy-stack"
CLIPROXY_CONFIG_DIR="$PROXY_STACK_DIR/cli-proxy-api"
CLIPROXY_PORT="8317"

if [ "$(basename "$SHELL")" = "zsh" ] && [ -f "$HOME/.zshrc" ]; then
  SHELL_RC="$HOME/.zshrc"
else
  SHELL_RC="$HOME/.bashrc"
fi

# ─── UI ───────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'
RED='\033[0;31m'; BOLD='\033[1m'; DIM='\033[2m'; RESET='\033[0m'

ok()   { echo -e "  ${GREEN}[OK]${RESET} $*"; }
miss() { echo -e "  ${YELLOW}[MISSING]${RESET} $*"; }
err()  { echo -e "  ${RED}[ERROR]${RESET} $*"; }
info() { echo -e "  ${CYAN}·${RESET} $*"; }
warn() { echo -e "  ${YELLOW}⚠${RESET} $*"; }
fail() { echo -e "  ${RED}✗${RESET} $*"; exit 1; }

# ═══════════════════════════════════════════════════════════════
# CHECK FUNCTIONS — return 0 if OK, 1 if needs fixing
# ═══════════════════════════════════════════════════════════════

check_docker() {
  if command -v docker &>/dev/null && docker ps &>/dev/null; then
    ok "Docker"
    return 0
  fi
  miss "Docker — installing..."
  return 1
}

check_node() {
  if command -v node &>/dev/null; then
    local ver
    ver=$(node --version 2>/dev/null)
    ok "Node.js $ver"
    return 0
  fi
  miss "Node.js — installing..."
  return 1
}

check_claude_code() {
  if command -v claude &>/dev/null; then
    ok "Claude Code CLI"
    return 0
  fi
  miss "Claude Code CLI — installing..."
  return 1
}

check_proxy_stack() {
  if [ -f "$PROXY_STACK_DIR/docker-compose.yml" ] && \
     grep -q "cli-proxy-api" "$PROXY_STACK_DIR/docker-compose.yml" 2>/dev/null && \
     [ -f "$CLIPROXY_CONFIG_DIR/config.yaml" ]; then
    ok "proxy-stack directory"
    return 0
  fi
  miss "proxy-stack — creating..."
  return 1
}

check_proxy_running() {
  if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "cli-proxy-api"; then
    ok "CLIProxyAPI container running"
    return 0
  fi
  miss "CLIProxyAPI container — starting..."
  return 1
}

check_oauth_token() {
  local response clients
  response=$(curl -s --max-time 5 http://localhost:$CLIPROXY_PORT/v1/models 2>/dev/null)
  clients=$(echo "$response" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(len(d.get('data', [])))
except:
    print(0)
" 2>/dev/null || echo "0")

  if [ "$clients" -gt "0" ]; then
    ok "OAuth token loaded ($clients auth clients)"
    return 0
  fi
  miss "OAuth token — renewal required"
  return 1
}

check_env_vars() {
  local base_url api_key base_count key_count
  base_url=$(grep "^export ANTHROPIC_BASE_URL=" "$SHELL_RC" 2>/dev/null | tail -1 | sed 's/^export ANTHROPIC_BASE_URL=//')
  api_key=$(grep "^export ANTHROPIC_API_KEY=" "$SHELL_RC" 2>/dev/null | tail -1 | sed 's/^export ANTHROPIC_API_KEY=//')
  base_count=$(grep -c "ANTHROPIC_BASE_URL" "$SHELL_RC" 2>/dev/null || echo "0")
  key_count=$(grep -c "ANTHROPIC_API_KEY" "$SHELL_RC" 2>/dev/null || echo "0")

  if [ "$base_url" = "http://localhost:$CLIPROXY_PORT" ] && \
     [ "$api_key" = "dummy" ] && \
     [ "$base_count" -eq 1 ] && \
     [ "$key_count" -eq 1 ]; then
    # Also check ~/.profile sources ~/.bashrc
    if grep -q "source ~/.bashrc" ~/.profile 2>/dev/null; then
      ok "Environment variables + ~/.profile"
    else
      miss "~/.profile not configured — run fix_env_vars"
      return 1
    fi
    return 0
  fi
  miss "Environment variables — updating..."
  return 1
}

check_shell_aliases() {
  if grep -q "auth-token-manager" "$SHELL_RC" 2>/dev/null && \
     grep -q "alias token-status=" "$SHELL_RC" 2>/dev/null; then
    ok "Shell aliases"
    return 0
  fi
  miss "Shell aliases — adding..."
  return 1
}

check_cron_jobs() {
  if crontab -l 2>/dev/null | grep -q "refresh_token.py" && \
     crontab -l 2>/dev/null | grep -q "check_proxy_health.sh"; then
    ok "Cron jobs"
    return 0
  fi
  miss "Cron jobs — adding..."
  return 1
}

check_central_env() {
  if [ -f "$CENTRAL_ENV" ]; then
    ok "Central token store ($CENTRAL_ENV)"
    return 0
  fi
  miss "Central token store — creating..."
  return 1
}

check_health_script() {
  if [ -f "$PROXY_STACK_DIR/check_proxy_health.sh" ] && [ -x "$PROXY_STACK_DIR/check_proxy_health.sh" ]; then
    ok "Health check script"
    return 0
  fi
  miss "Health check script — creating..."
  return 1
}

check_login_script() {
  if [ -f "$PROXY_STACK_DIR/claude-login.sh" ] && [ -x "$PROXY_STACK_DIR/claude-login.sh" ]; then
    ok "Login script"
    return 0
  fi
  miss "Login script — creating..."
  return 1
}

# ═══════════════════════════════════════════════════════════════
# INSTALL / FIX FUNCTIONS — called when checks fail
# ═══════════════════════════════════════════════════════════════

install_docker() {
  echo ""
  info "Installing Docker..."
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER"
  info "Docker installed. You may need to log out and back in for group changes."
  info "Or run: newgrp docker"
  echo ""
}

install_node() {
  echo ""
  info "Installing Node.js >= 22..."
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt-get install -y nodejs
  ok "Node.js $(node --version) installed"
}

install_claude_code() {
  echo ""
  info "Installing Claude Code CLI..."
  npm install -g @anthropic-ai/claude-code
  ok "Claude Code CLI installed"
}

create_proxy_stack() {
  # Create directory structure
  mkdir -p "$CLIPROXY_CONFIG_DIR"

  # Write config.yaml
  cat > "$CLIPROXY_CONFIG_DIR/config.yaml" << 'CONFIGEOF'
port: 8317
auth-dir: "/root/.cli-proxy-api"
debug: false
logging-to-file: false
usage-statistics-enabled: false
request-retry: 3
quota-exceeded:
  switch-project: true
  switch-preview-model: true
auth:
  providers: []
oauth-model-alias:
  claude:
    - name: "claude-opus-4-6"
      alias: "claude-sonnet-4-5-20250929"
    - name: "claude-sonnet-4-6"
      alias: "claude-sonnet-4-5-20250929"
    - name: "claude-opus-4-5"
      alias: "claude-sonnet-4-5-20250929"
CONFIGEOF
  ok "Config → $CLIPROXY_CONFIG_DIR/config.yaml"

  # Write docker-compose.yml if missing
  if [ ! -f "$PROXY_STACK_DIR/docker-compose.yml" ]; then
    cat > "$PROXY_STACK_DIR/docker-compose.yml" << 'COMPOSEEOF'
version: '3'

services:
  cli-proxy-api:
    image: eceasy/cli-proxy-api:latest
    container_name: cli-proxy-api
    restart: unless-stopped
    ports:
      - "8317:8317"
    volumes:
      - ./cli-proxy-api/config.yaml:/CLIProxyAPI/config.yaml
      - cli_proxy_auth:/root/.cli-proxy-api

volumes:
  cli_proxy_auth:
    external: true
    name: proxy-stack_cli_proxy_auth
COMPOSEEOF
    ok "docker-compose.yml created"
  elif ! grep -q "cli-proxy-api" "$PROXY_STACK_DIR/docker-compose.yml"; then
    warn "docker-compose.yml exists but missing cli-proxy-api service — add manually"
  else
    ok "docker-compose.yml — cli-proxy-api already present"
  fi

  # Create Docker volume if not exists
  if ! docker volume inspect proxy-stack_cli_proxy_auth >/dev/null 2>&1; then
    docker volume create proxy-stack_cli_proxy_auth >/dev/null
    ok "Docker volume proxy-stack_cli_proxy_auth created"
  fi
}

start_proxy() {
  cd "$PROXY_STACK_DIR" && docker compose up -d cli-proxy-api
  sleep 3
  if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "cli-proxy-api"; then
    ok "CLIProxyAPI started → http://localhost:$CLIPROXY_PORT"
  else
    warn "CLIProxyAPI failed to start — check: docker logs cli-proxy-api"
  fi
}

fix_env_vars() {
  # Remove ALL conflicting Anthropic/Claude env vars
  sed -i '/ANTHROPIC_AUTH_TOKEN/d' "$SHELL_RC"
  sed -i '/ANTHROPIC_BASE_URL/d' "$SHELL_RC"
  sed -i '/ANTHROPIC_API_KEY/d' "$SHELL_RC"
  sed -i '/CLAUDE_CODE_OAUTH_TOKEN/d' "$SHELL_RC"

  # Remove old CLIProxyAPI block if present
  sed -i '/# ── CLIProxyAPI — prevents OAuth 401 errors/,/# ────────────────────────────────────────────────────────────/d' "$SHELL_RC"

  # Add correct values — once
  echo 'export ANTHROPIC_BASE_URL=http://localhost:'"$CLIPROXY_PORT" >> "$SHELL_RC"
  echo 'export ANTHROPIC_API_KEY=dummy' >> "$SHELL_RC"

  # Verify no duplicates
  local count_base count_key
  count_base=$(grep -c "ANTHROPIC_BASE_URL" "$SHELL_RC")
  count_key=$(grep -c "ANTHROPIC_API_KEY" "$SHELL_RC")

  if [ "$count_base" -eq 1 ] && [ "$count_key" -eq 1 ]; then
    ok "Environment variables set (no duplicates)"
  else
    err "Duplicate env vars detected (BASE_URL=$count_base, API_KEY=$count_key) — check $SHELL_RC manually"
  fi

  # Ensure all terminal sessions load ~/.bashrc automatically
  if ! grep -q "source ~/.bashrc" ~/.profile 2>/dev/null; then
    echo 'source ~/.bashrc' >> ~/.profile
    ok "~/.profile updated — all sessions will load env vars automatically"
  else
    ok "~/.profile already configured"
  fi
}

fix_shell_aliases() {
  # Remove old auth-token-manager block if present
  sed -i '/# ── auth-token-manager/,/# ────────────────────────────────────────────────────────────/d' "$SHELL_RC"

  # Write fresh block (aliases only, env vars handled by fix_env_vars)
  cat >> "$SHELL_RC" << ALIASEOF

# ── auth-token-manager ──────────────────────────────────────
alias token-status='python3 $INSTALL_DIR/scripts/refresh_token.py --status'
alias token-refresh='python3 $INSTALL_DIR/scripts/refresh_token.py'
alias token-link='python3 $INSTALL_DIR/scripts/refresh_token.py --link'
alias cliproxy='bash $INSTALL_DIR/scripts/cliproxyapi_manager.sh'
# ────────────────────────────────────────────────────────────
ALIASEOF
  ok "Shell aliases added to $SHELL_RC"
}

setup_central_env() {
  mkdir -p "$(dirname "$CENTRAL_ENV")"
  mkdir -p "$CONFIG_DIR" && chmod 700 "$CONFIG_DIR"

  # Read existing token if available
  local token=""
  if [ -f "$CREDS_FILE" ]; then
    token=$(python3 -c "
import json
try:
    d=json.load(open('$CREDS_FILE'))
    print(d.get('claudeAiOauth',{}).get('accessToken',''))
except: print('')
" 2>/dev/null)
  fi

  cat > "$CENTRAL_ENV" << EOF
# AI Provider Tokens — managed by auth-token-manager
# Last updated: $(date '+%Y-%m-%d %H:%M:%S')
# DO NOT commit this file to git.

CLAUDE_CREDENTIAL_TOKEN="$token"
EOF
  chmod 600 "$CENTRAL_ENV"

  cat > "$CONFIG_DIR/config.env" << EOF
AI_AUTH_CENTRAL_ENV="$CENTRAL_ENV"
AI_PROXY_PORT="$CLIPROXY_PORT"
CLAUDE_CREDENTIALS_PATH="$CREDS_FILE"
EOF
  ok "Central token store → $CENTRAL_ENV"
}

add_cron_jobs() {
  local current_cron new_cron changed
  current_cron=$(crontab -l 2>/dev/null || echo "")
  new_cron="$current_cron"
  changed=false

  if ! echo "$current_cron" | grep -q "refresh_token.py"; then
    new_cron=$(printf '%s\n%s\n%s' "$new_cron" "# auth-token-manager — daily token refresh" "0 6 * * * python3 $INSTALL_DIR/scripts/refresh_token.py >> $LOG_FILE 2>&1")
    changed=true
  fi

  if ! echo "$current_cron" | grep -q "check_proxy_health.sh"; then
    new_cron=$(printf '%s\n%s\n%s' "$new_cron" "# CLIProxyAPI health check — every hour" "0 * * * * $PROXY_STACK_DIR/check_proxy_health.sh >> /tmp/proxy-health.log 2>&1")
    changed=true
  fi

  if [ "$changed" = true ]; then
    echo "$new_cron" | crontab -
    ok "Cron jobs added"
  fi
}

create_health_script() {
  mkdir -p "$PROXY_STACK_DIR"
  cat > "$PROXY_STACK_DIR/check_proxy_health.sh" << 'HEALTHEOF'
#!/bin/bash
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
LOGFILE="/tmp/proxy-health.log"

response=$(curl -s http://localhost:8317/v1/models 2>/dev/null)
clients=$(echo $response | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(len(d.get('data', [])))
except:
    print(0)
" 2>/dev/null || echo "0")

if [ "$clients" -gt "0" ]; then
    echo "[$TIMESTAMP] OK — $clients auth clients" >> $LOGFILE
else
    echo "[$TIMESTAMP] ERROR — no auth clients, restarting" >> $LOGFILE
    cd /home/$(whoami)/proxy-stack && docker compose restart cli-proxy-api
    sleep 5
    echo "[$TIMESTAMP] Restarted" >> $LOGFILE
fi
HEALTHEOF
  chmod +x "$PROXY_STACK_DIR/check_proxy_health.sh"
  ok "Health check script created"
}

create_login_script() {
  mkdir -p "$PROXY_STACK_DIR"
  cat > "$PROXY_STACK_DIR/claude-login.sh" << 'LOGINEOF'
#!/bin/bash
echo "======================================"
echo "  Claude OAuth Login for CLIProxyAPI"
echo "======================================"
echo ""
echo "STEP 1: Run this command on your LOCAL machine:"
HOSTNAME_IP=$(hostname -I | awk '{print $1}')
echo "  ssh -L 54545:127.0.0.1:54545 $(whoami)@<TAILSCALE_IP>"
echo ""
echo "STEP 2: Press Enter when SSH tunnel is ready..."
read

docker run --rm -it \
  -p 54545:54545 \
  -v proxy-stack_cli_proxy_auth:/root/.cli-proxy-api \
  -v ~/proxy-stack/cli-proxy-api/config.yaml:/CLIProxyAPI/config.yaml \
  eceasy/cli-proxy-api:latest \
  /CLIProxyAPI/CLIProxyAPI --claude-login

echo ""
echo "STEP 3: Starting proxy..."
cd ~/proxy-stack && docker compose up -d cli-proxy-api

echo ""
echo "STEP 4: Verifying..."
sleep 3
curl -s http://localhost:8317/v1/models | python3 -c "
import sys, json
d = json.load(sys.stdin)
clients = len(d.get('data', []))
if clients > 0:
    print(f'OK — {clients} auth clients loaded')
else:
    print('WARNING — proxy running but no auth loaded')
    print('Try running this script again')
"
LOGINEOF
  chmod +x "$PROXY_STACK_DIR/claude-login.sh"
  ok "Login script created"
}

# ═══════════════════════════════════════════════════════════════
# OAUTH RENEWAL — handles the interactive login flow
# ═══════════════════════════════════════════════════════════════

renew_oauth_token() {
  echo ""
  echo -e "${BOLD}  ══════════════════════════════════════${RESET}"
  echo -e "${BOLD}    Claude OAuth Token Renewal${RESET}"
  echo -e "${BOLD}  ══════════════════════════════════════${RESET}"
  echo ""
  echo "  Your OAuth token is expired or missing."
  echo "  This requires a one-time browser authentication."
  echo ""

  # Detect SSH session
  if [ -n "$SSH_CLIENT" ] || [ -n "$SSH_TTY" ]; then
    local server_ip
    server_ip=$(hostname -I | awk '{print $1}')
    echo -e "  ${YELLOW}Remote session detected (SSH).${RESET}"
    echo ""
    echo "  STEP 1: Open a NEW terminal on your LOCAL machine and run:"
    echo -e "    ${CYAN}ssh -L 54545:127.0.0.1:54545 $(whoami)@$server_ip${RESET}"
    echo ""
    echo "  STEP 2: Keep that terminal open and press Enter here..."
    read -rp "  Press Enter when SSH tunnel is ready: "
    echo ""
  fi

  # Stop the running container so port 54545 is free for login
  if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "cli-proxy-api"; then
    info "Stopping CLIProxyAPI for login flow..."
    cd "$PROXY_STACK_DIR" && docker compose stop cli-proxy-api 2>/dev/null || true
  fi

  docker run --rm -it \
    -p 54545:54545 \
    -v proxy-stack_cli_proxy_auth:/root/.cli-proxy-api \
    -v "$CLIPROXY_CONFIG_DIR/config.yaml:/CLIProxyAPI/config.yaml" \
    eceasy/cli-proxy-api:latest \
    /CLIProxyAPI/CLIProxyAPI --claude-login

  echo ""
  info "Restarting CLIProxyAPI..."
  cd "$PROXY_STACK_DIR" && docker compose up -d cli-proxy-api
  sleep 3

  if check_oauth_token; then
    ok "OAuth token renewed successfully"
    return 0
  else
    err "Token renewal failed — try running this script again"
    return 1
  fi
}

# ═══════════════════════════════════════════════════════════════
# STATUS — print-only mode (--status flag)
# ═══════════════════════════════════════════════════════════════

print_status() {
  echo ""
  echo -e "${BOLD}  ══════════════════════════════════════${RESET}"
  echo -e "${BOLD}    AI Dev Environment Status${RESET}"
  echo -e "${BOLD}  ══════════════════════════════════════${RESET}"
  echo ""

  check_docker        || true
  check_node          || true
  check_claude_code   || true
  check_proxy_stack   || true
  check_proxy_running || true
  check_oauth_token   || true
  check_env_vars      || true
  check_shell_aliases || true
  check_cron_jobs     || true
  check_central_env   || true
  check_health_script || true
  check_login_script  || true

  echo ""
  echo -e "  ${DIM}Run without --status to fix any issues.${RESET}"
  echo ""
}

# ═══════════════════════════════════════════════════════════════
# MAIN — smart check-then-fix flow
# ═══════════════════════════════════════════════════════════════

main() {
  echo ""
  echo -e "${BOLD}  ══════════════════════════════════════════════════${RESET}"
  echo -e "${BOLD}    AI Dev Environment Setup / Check${RESET}"
  echo -e "${BOLD}  ══════════════════════════════════════════════════${RESET}"
  echo ""
  echo -e "  ${DIM}Smart mode: checks each component, fixes only what is missing.${RESET}"
  echo ""

  local NEEDS_OAUTH=0

  # ── 1. Prerequisites ──────────────────────────────────────
  echo -e "  ${BOLD}--- Prerequisites ---${RESET}"
  check_docker      || install_docker
  check_node        || install_node
  check_claude_code || install_claude_code
  echo ""

  # ── 2. proxy-stack infrastructure ─────────────────────────
  echo -e "  ${BOLD}--- Infrastructure ---${RESET}"
  check_proxy_stack   || create_proxy_stack
  check_health_script || create_health_script
  check_login_script  || create_login_script
  echo ""

  # ── 3. Shell configuration ───────────────────────────────
  echo -e "  ${BOLD}--- Shell Configuration ---${RESET}"
  check_central_env   || setup_central_env
  check_env_vars      || fix_env_vars
  check_shell_aliases || fix_shell_aliases
  check_cron_jobs     || add_cron_jobs
  echo ""

  # ── 4. Start proxy if not running ────────────────────────
  echo -e "  ${BOLD}--- Proxy ---${RESET}"
  check_proxy_running || start_proxy
  echo ""

  # ── 5. Check OAuth last — requires proxy to be running ───
  echo -e "  ${BOLD}--- Authentication ---${RESET}"
  check_oauth_token || NEEDS_OAUTH=1
  echo ""

  # ── 6. OAuth renewal if needed ───────────────────────────
  if [ "$NEEDS_OAUTH" -eq 1 ]; then
    renew_oauth_token
  fi

  # ══════════════════════════════════════════════════════════
  # Final Status
  # ══════════════════════════════════════════════════════════
  echo ""
  echo -e "${BOLD}  ══════════════════════════════════════════════════${RESET}"
  echo -e "${BOLD}    Final Status${RESET}"
  echo -e "${BOLD}  ══════════════════════════════════════════════════${RESET}"
  echo ""
  check_docker        || true
  check_node          || true
  check_claude_code   || true
  check_proxy_stack   || true
  check_proxy_running || true
  check_oauth_token   || true
  check_env_vars      || true
  check_shell_aliases || true
  check_cron_jobs     || true
  echo ""
  echo -e "  ${DIM}Run: claude 'hello' to verify end-to-end.${RESET}"
  echo -e "  ${DIM}Token renewal: bash ~/proxy-stack/claude-login.sh${RESET}"
  echo -e "${BOLD}  ══════════════════════════════════════════════════${RESET}"
  echo ""
}

# ═══════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════

case "${1:-}" in
  --status|-s)
    print_status
    ;;
  *)
    main
    ;;
esac
