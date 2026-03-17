#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# cliproxyapi_manager.sh — Manage the CLIProxyAPI Docker service
#
# CLIProxyAPI solves the Claude Code CLI OAuth token expiration
# problem by acting as a persistent proxy on localhost:8317.
# Claude Code CLI points to it via ANTHROPIC_BASE_URL.
#
# Usage:
#   bash cliproxyapi_manager.sh setup     # First-time setup + login
#   bash cliproxyapi_manager.sh start     # Start container
#   bash cliproxyapi_manager.sh stop      # Stop container
#   bash cliproxyapi_manager.sh restart   # Restart container
#   bash cliproxyapi_manager.sh status    # Show status
#   bash cliproxyapi_manager.sh login     # Re-authenticate (if needed)
#   bash cliproxyapi_manager.sh logs      # Tail logs
# ═══════════════════════════════════════════════════════════════

CONTAINER_NAME="cliproxyapi"
IMAGE="eceasy/cli-proxy-api:latest"
API_PORT="${CLIPROXYAPI_PORT:-8317}"
LOGIN_PORT="54545"
CONFIG_DIR="$HOME/.config/ai-auth/cliproxyapi"
TOKEN_DIR="$CONFIG_DIR/tokens"
CONFIG_FILE="$CONFIG_DIR/config.yaml"
SHELL_RC="$HOME/.bashrc"
[ "$(basename "$SHELL")" = "zsh" ] && [ -f "$HOME/.zshrc" ] && SHELL_RC="$HOME/.zshrc"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'
RED='\033[0;31m'; BOLD='\033[1m'; DIM='\033[2m'; RESET='\033[0m'
ok()   { echo -e "  ${GREEN}✓${RESET} $*"; }
info() { echo -e "  ${CYAN}·${RESET} $*"; }
warn() { echo -e "  ${YELLOW}⚠${RESET} $*"; }
fail() { echo -e "  ${RED}✗${RESET} $*"; exit 1; }

# ─── Helpers ──────────────────────────────────────────────────
is_running() {
  docker ps --filter "name=$CONTAINER_NAME" --format "{{.Names}}" 2>/dev/null \
    | grep -q "^${CONTAINER_NAME}$"
}

is_exists() {
  docker ps -a --filter "name=$CONTAINER_NAME" --format "{{.Names}}" 2>/dev/null \
    | grep -q "^${CONTAINER_NAME}$"
}

# Returns "name|image" of any container using our port (excluding our own named container)
get_port_occupant() {
  docker ps --format "{{.Names}}|{{.Image}}|{{.Ports}}" 2>/dev/null \
    | grep ":${API_PORT}->" \
    | grep -v "^${CONTAINER_NAME}|" \
    | head -1
}

# True if the port occupant is running our own image (just with a different name)
occupant_is_our_image() {
  local occupant="$1"
  local image
  image=$(echo "$occupant" | cut -d'|' -f2)
  echo "$image" | grep -q "cli-proxy-api"
}

ensure_docker() {
  command -v docker >/dev/null 2>&1 || fail "Docker is required but not found."
}

# ─── Write config.yaml ────────────────────────────────────────
write_config() {
  mkdir -p "$CONFIG_DIR" "$TOKEN_DIR"
  chmod 700 "$CONFIG_DIR"
  cat > "$CONFIG_FILE" << EOF
# CLIProxyAPI configuration
# Managed by auth-token-manager

port: $API_PORT
auth-dir: "~/.cli-proxy-api"
request-retry: 3
debug: false
logging-to-file: false

# No API key protection — localhost only
auth:
  providers: []
EOF
  chmod 600 "$CONFIG_FILE"
  ok "Config written to $CONFIG_FILE"
}

# ─── Wire Claude Code CLI ─────────────────────────────────────
wire_claude_cli() {
  local block="
# ── CLIProxyAPI — prevents OAuth 401 errors ─────────────────
# Claude Code CLI routes through localhost:$API_PORT
# which handles token refresh automatically
export ANTHROPIC_BASE_URL=http://localhost:$API_PORT
export ANTHROPIC_AUTH_TOKEN=sk-dummy
# ────────────────────────────────────────────────────────────"

  if ! grep -q "CLIProxyAPI" "$SHELL_RC" 2>/dev/null; then
    echo "$block" >> "$SHELL_RC"
    ok "ANTHROPIC_BASE_URL added to $SHELL_RC"
    info "Run: source $SHELL_RC"
  else
    ok "ANTHROPIC_BASE_URL already in $SHELL_RC"
  fi

  # Apply to current session too
  export ANTHROPIC_BASE_URL="http://localhost:$API_PORT"
  export ANTHROPIC_AUTH_TOKEN="sk-dummy"
}

# ─── Start container ──────────────────────────────────────────
cmd_start() {
  ensure_docker

  # Case 1: our named container is already running — nothing to do
  if is_running; then
    ok "CLIProxyAPI already running on localhost:$API_PORT"
    return
  fi

  # Case 2: our named container exists but is stopped — remove and recreate
  if is_exists; then
    info "Removing stopped container '$CONTAINER_NAME'..."
    docker rm "$CONTAINER_NAME" >/dev/null 2>&1
  fi

  # Case 3: port is occupied by something else
  local occupant
  occupant=$(get_port_occupant)
  if [ -n "$occupant" ]; then
    local occ_name occ_image
    occ_name=$(echo "$occupant" | cut -d'|' -f1)
    occ_image=$(echo "$occupant" | cut -d'|' -f2)

    echo ""
    warn "Port $API_PORT is already in use."
    echo -e "  Container : ${BOLD}$occ_name${RESET}"
    echo -e "  Image     : ${DIM}$occ_image${RESET}"
    echo ""

    if occupant_is_our_image "$occupant"; then
      # It's our image running under a different name — take it over
      info "This is our CLIProxyAPI image running under a different name."
      info "Stopping '$occ_name' and recreating as '$CONTAINER_NAME'..."
      docker stop "$occ_name" >/dev/null 2>&1 || true
      docker rm   "$occ_name" >/dev/null 2>&1 || true
      ok "Stopped '$occ_name' — will start fresh as '$CONTAINER_NAME'."
    else
      # It's a completely different container — user must decide
      echo -e "  This is a ${RED}different${RESET} container — not managed by auth-token-manager."
      echo ""
      echo "  What would you like to do?"
      echo "  1) Stop '$occ_name' and continue  (CLIProxyAPI will take port $API_PORT)"
      echo "  2) Exit — I will fix this manually"
      echo ""
      echo -ne "  Choice [1/2]: "
      read -r choice
      case "$choice" in
        1)
          info "Stopping '$occ_name'..."
          docker stop "$occ_name" >/dev/null 2>&1 || true
          docker rm   "$occ_name" >/dev/null 2>&1 || true
          ok "Stopped '$occ_name'."
          ;;
        *)
          echo ""
          echo "  Exiting. To fix manually:"
          echo "    docker stop $occ_name"
          echo "    docker rm   $occ_name"
          echo "    bash cliproxyapi_manager.sh start"
          echo ""
          exit 0
          ;;
      esac
    fi
  fi

  # Case 4: port is free — start normally
  [ ! -f "$CONFIG_FILE" ] && write_config

  info "Pulling latest image..."
  docker pull "$IMAGE" --quiet

  info "Starting CLIProxyAPI on port $API_PORT..."
  docker run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    -p "${API_PORT}:8317" \
    -p "${LOGIN_PORT}:54545" \
    -v "$CONFIG_FILE:/CLIProxyAPI/config.yaml:ro" \
    -v "$TOKEN_DIR:/root/.cli-proxy-api" \
    "$IMAGE" >/dev/null

  sleep 2
  if is_running; then
    ok "CLIProxyAPI started → http://localhost:$API_PORT"
  else
    fail "Container failed to start. Run: docker logs $CONTAINER_NAME"
  fi
}

cmd_stop() {
  ensure_docker
  if ! is_exists; then
    info "Container not running."
    return
  fi
  docker stop "$CONTAINER_NAME" >/dev/null
  docker rm   "$CONTAINER_NAME" >/dev/null
  ok "CLIProxyAPI stopped."
}

cmd_restart() {
  cmd_stop
  cmd_start
}

cmd_status() {
  ensure_docker
  echo ""
  echo -e "  ${BOLD}CLIProxyAPI Status${RESET}"
  echo "  ─────────────────────────────────────────"
  if is_running; then
    STATUS=$(docker ps --filter "name=$CONTAINER_NAME" --format "{{.Status}}")
    echo -e "  ${GREEN}✓${RESET} Running: $STATUS"
    echo -e "     API:   http://localhost:$API_PORT/v1/messages"
  elif is_exists; then
    echo -e "  ${YELLOW}⚠${RESET} Container exists but stopped"
    echo -e "     Run: bash cliproxyapi_manager.sh start"
  else
    echo -e "  ${RED}✗${RESET} Not installed"
    echo -e "     Run: bash cliproxyapi_manager.sh setup"
  fi

  echo ""
  local base_url="${ANTHROPIC_BASE_URL:-not set}"
  if [ "$base_url" = "http://localhost:$API_PORT" ]; then
    echo -e "  ${GREEN}✓${RESET} ANTHROPIC_BASE_URL=$base_url"
  else
    echo -e "  ${YELLOW}⚠${RESET} ANTHROPIC_BASE_URL=$base_url"
    echo -e "     Expected: http://localhost:$API_PORT"
    echo -e "     Run: source $SHELL_RC"
  fi

  # Check tokens
  local token_count
  token_count=$(find "$TOKEN_DIR" -name "*.json" 2>/dev/null | wc -l | tr -d ' ')
  if [ "$token_count" -gt 0 ]; then
    echo -e "  ${GREEN}✓${RESET} $token_count OAuth token(s) stored in $TOKEN_DIR"
  else
    echo -e "  ${YELLOW}⚠${RESET} No tokens found — run login"
  fi
  echo ""
}

cmd_logs() {
  ensure_docker
  is_exists || fail "Container not running."
  docker logs -f --tail 50 "$CONTAINER_NAME"
}

# ─── Login — one-time per machine ─────────────────────────────
cmd_login() {
  ensure_docker
  is_running || cmd_start

  echo ""
  echo -e "${BOLD}  CLIProxyAPI — Claude OAuth Login${RESET}"
  echo "  ─────────────────────────────────────────"
  echo ""
  echo "  This is a ONE-TIME step per machine."
  echo "  After this, tokens refresh automatically forever."
  echo ""

  # Detect if we're in a remote SSH session
  if [ -n "$SSH_CLIENT" ] || [ -n "$SSH_TTY" ]; then
    echo -e "  ${YELLOW}Remote session detected (SSH).${RESET}"
    echo ""
    echo "  You need to set up an SSH tunnel first."
    echo "  On your LOCAL machine (Termux / PC), run:"
    echo ""
    echo -e "    ${CYAN}ssh -L 54545:127.0.0.1:54545 $(whoami)@$(hostname -I | awk '{print $1}')${RESET}"
    echo ""
    echo "  Then come back here and press Enter."
    echo ""
    echo -ne "  ${DIM}Press Enter when SSH tunnel is ready...${RESET}"
    read -r
    echo ""
  fi

  echo "  Starting login flow..."
  echo -e "  ${YELLOW}→ A browser URL will appear. Open it in your browser.${RESET}"
  echo -e "  ${YELLOW}→ Sign in to claude.ai and click Authorize.${RESET}"
  echo ""

  docker exec -it "$CONTAINER_NAME" ./CLIProxyAPI --claude-login

  echo ""
  # Check tokens were saved
  local token_count
  token_count=$(find "$TOKEN_DIR" -name "*.json" 2>/dev/null | wc -l | tr -d ' ')
  if [ "$token_count" -gt 0 ]; then
    ok "Login successful — $token_count token(s) saved to $TOKEN_DIR"
    ok "Claude Code CLI will no longer get 401 errors."
  else
    warn "No tokens found after login — something may have gone wrong."
    info "Try again or check: docker logs $CONTAINER_NAME"
  fi
  echo ""
}

# ─── First-time setup ─────────────────────────────────────────
cmd_setup() {
  ensure_docker

  echo ""
  echo -e "${BOLD}  CLIProxyAPI — First-Time Setup${RESET}"
  echo "  ══════════════════════════════════════════"
  echo ""
  echo "  Fixes: OAuth token expiration (401 errors) in Claude Code CLI"
  echo "  How:   Persistent Docker proxy on localhost:$API_PORT"
  echo "         that handles token refresh automatically."
  echo ""

  # Step 1: config
  write_config

  # Step 2: start
  cmd_start

  # Step 3: wire CLI
  wire_claude_cli

  echo ""
  echo "  ──────────────────────────────────────────"
  echo -e "  ${BOLD}One last step — authenticate once:${RESET}"
  echo ""
  echo -e "    ${CYAN}bash cliproxyapi_manager.sh login${RESET}"
  echo ""
  echo "  After that, OAuth tokens refresh automatically."
  echo "  You will never see a 401 error again."
  echo ""
}

# ─── Entry point ──────────────────────────────────────────────
CMD="${1:-status}"
case "$CMD" in
  setup)   cmd_setup   ;;
  start)   cmd_start   ;;
  stop)    cmd_stop    ;;
  restart) cmd_restart ;;
  status)  cmd_status  ;;
  login)   cmd_login   ;;
  logs)    cmd_logs    ;;
  *)
    echo "Usage: bash cliproxyapi_manager.sh [setup|start|stop|restart|status|login|logs]"
    echo "  setup    — first-time installation + config + wiring"
    echo "  login    — one-time OAuth authentication"
    echo "  start    — start container"
    echo "  stop     — stop container"
    echo "  restart  — restart container"
    echo "  status   — show status"
    echo "  logs     — tail container logs"
    ;;
esac
