#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# cliproxyapi_manager.sh — Thin wrapper for CLIProxyAPI
#
# Delegates to docker compose in ~/proxy-stack/.
# For first-time setup: bash ~/.claude/skills/auth-token-manager/scripts/install.sh
# For OAuth login:      bash ~/proxy-stack/claude-login.sh
#
# Usage:
#   bash cliproxyapi_manager.sh start     # Start container
#   bash cliproxyapi_manager.sh stop      # Stop container
#   bash cliproxyapi_manager.sh restart   # Restart container
#   bash cliproxyapi_manager.sh status    # Show status + health
#   bash cliproxyapi_manager.sh logs      # Tail logs
# ═══════════════════════════════════════════════════════════════

PROXY_STACK_DIR="$HOME/proxy-stack"
CONTAINER_NAME="cli-proxy-api"
API_PORT="8317"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'
RED='\033[0;31m'; BOLD='\033[1m'; DIM='\033[2m'; RESET='\033[0m'
ok()   { echo -e "  ${GREEN}✓${RESET} $*"; }
info() { echo -e "  ${CYAN}·${RESET} $*"; }
warn() { echo -e "  ${YELLOW}⚠${RESET} $*"; }
fail() { echo -e "  ${RED}✗${RESET} $*"; exit 1; }

check_prerequisites() {
  command -v docker >/dev/null 2>&1 || fail "Docker is required but not found."
  [ -f "$PROXY_STACK_DIR/docker-compose.yml" ] || fail "proxy-stack not found. Run: bash ~/.claude/skills/auth-token-manager/scripts/install.sh"
}

cmd_start() {
  check_prerequisites
  if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${CONTAINER_NAME}$"; then
    ok "CLIProxyAPI already running on localhost:$API_PORT"
    return
  fi
  cd "$PROXY_STACK_DIR" && docker compose up -d cli-proxy-api
  sleep 2
  if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${CONTAINER_NAME}$"; then
    ok "CLIProxyAPI started → http://localhost:$API_PORT"
  else
    fail "Failed to start. Run: docker logs $CONTAINER_NAME"
  fi
}

cmd_stop() {
  check_prerequisites
  cd "$PROXY_STACK_DIR" && docker compose stop cli-proxy-api
  ok "CLIProxyAPI stopped."
}

cmd_restart() {
  check_prerequisites
  cd "$PROXY_STACK_DIR" && docker compose restart cli-proxy-api
  sleep 2
  ok "CLIProxyAPI restarted."
}

cmd_status() {
  check_prerequisites
  echo ""
  echo -e "  ${BOLD}CLIProxyAPI Status${RESET}"
  echo "  ─────────────────────────────────────────"

  if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${CONTAINER_NAME}$"; then
    local status
    status=$(docker ps --filter "name=$CONTAINER_NAME" --format "{{.Status}}")
    ok "Running: $status"

    local response clients
    response=$(curl -s --max-time 5 http://localhost:$API_PORT/v1/models 2>/dev/null)
    clients=$(echo "$response" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(len(d.get('data', [])))
except:
    print(0)
" 2>/dev/null || echo "0")

    if [ "$clients" -gt "0" ]; then
      ok "Health: $clients auth client(s) loaded"
    else
      warn "Health: proxy running but no auth loaded"
      info "Run: bash ~/proxy-stack/claude-login.sh"
    fi
  else
    fail "Not running. Run: cliproxy start"
  fi

  echo ""
  local base_url="${ANTHROPIC_BASE_URL:-not set}"
  if [ "$base_url" = "http://localhost:$API_PORT" ]; then
    ok "ANTHROPIC_BASE_URL=$base_url"
  else
    warn "ANTHROPIC_BASE_URL=$base_url (expected http://localhost:$API_PORT)"
    info "Run: source ~/.bashrc"
  fi
  echo ""
}

cmd_logs() {
  check_prerequisites
  docker logs -f --tail 50 "$CONTAINER_NAME"
}

# ─── Entry point ──────────────────────────────────────────────
CMD="${1:-status}"
case "$CMD" in
  start)   cmd_start   ;;
  stop)    cmd_stop    ;;
  restart) cmd_restart ;;
  status)  cmd_status  ;;
  logs)    cmd_logs    ;;
  *)
    echo "Usage: cliproxy [start|stop|restart|status|logs]"
    echo ""
    echo "  start    — start CLIProxyAPI container"
    echo "  stop     — stop container"
    echo "  restart  — restart container"
    echo "  status   — show status + health check"
    echo "  logs     — tail container logs"
    echo ""
    echo "First-time setup: bash ~/.claude/skills/auth-token-manager/scripts/install.sh"
    echo "OAuth login:      bash ~/proxy-stack/claude-login.sh"
    ;;
esac
