#!/usr/bin/env python3
"""
auth-token-manager — proxy_manager.py
Manages the CLI Proxy Docker container (LiteLLM-based).
Exposes OpenAI-compatible API at localhost:PORT using your OAuth token.

Commands:
  --start              Start proxy container (default)
  --stop               Stop proxy container
  --restart            Restart proxy container
  --status             Show proxy status
  --logs               Tail proxy logs
  --provider <name>    Switch active provider: claude (default), gemini
  --port <port>        Port to use (default: 8080)
"""

import os
import sys
import subprocess
import argparse
import json
import tempfile
from pathlib import Path

CONTAINER_NAME = "ai-proxy"
DEFAULT_PORT   = 8080

# ─── Config loading ───────────────────────────────────────────────────────────

def load_config() -> dict:
    config_file = Path.home() / ".claude" / "skills" / "auth-token-manager" / "config" / "config.env"
    cfg = {}
    if config_file.exists():
        for line in config_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                cfg[k.strip()] = v.strip().strip('"')
    return {
        "central_env": Path(cfg.get("AI_AUTH_CENTRAL_ENV",
                            Path.home() / ".claude" / "skills" / "auth-token-manager" / "config" / "tokens.env")),
        "port":        int(cfg.get("AI_PROXY_PORT", DEFAULT_PORT)),
    }

def read_central_env(central_env: Path) -> dict:
    result = {}
    if not central_env.exists():
        return result
    for line in central_env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            result[k.strip()] = v.strip().strip('"')
    return result

def get_token(central_env: Path) -> str:
    env = read_central_env(central_env)
    return (
        env.get("CLAUDE_CODE_OAUTH_TOKEN")
        or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "")
    )

def get_gemini_token(central_env: Path) -> str:
    env = read_central_env(central_env)
    return (
        env.get("GEMINI_OAUTH_TOKEN")
        or os.environ.get("GEMINI_OAUTH_TOKEN", "")
    )

# ─── LiteLLM config generation ───────────────────────────────────────────────

def make_litellm_config(claude_token: str, gemini_token: str) -> str:
    """Generate litellm config YAML with available providers."""
    models = []

    if claude_token:
        models += [
            {
                "model_name": "claude-sonnet-4-6",
                "litellm_params": {
                    "model": "anthropic/claude-sonnet-4-6",
                    "api_key": claude_token,
                },
            },
            {
                "model_name": "claude-opus-4-6",
                "litellm_params": {
                    "model": "anthropic/claude-opus-4-6",
                    "api_key": claude_token,
                },
            },
            {
                "model_name": "claude",   # convenient alias → sonnet
                "litellm_params": {
                    "model": "anthropic/claude-sonnet-4-6",
                    "api_key": claude_token,
                },
            },
        ]

    if gemini_token:
        models += [
            {
                "model_name": "gemini-2.0-flash",
                "litellm_params": {
                    "model": "gemini/gemini-2.0-flash",
                    "api_key": gemini_token,
                },
            },
            {
                "model_name": "gemini",   # convenient alias
                "litellm_params": {
                    "model": "gemini/gemini-2.0-flash",
                    "api_key": gemini_token,
                },
            },
        ]

    if not models:
        raise ValueError("No tokens available. Run 'claude setup-token' first.")

    lines = [
        "model_list:",
    ]
    for m in models:
        lines.append(f"  - model_name: {m['model_name']}")
        lines.append(f"    litellm_params:")
        lines.append(f"      model: {m['litellm_params']['model']}")
        lines.append(f"      api_key: \"{m['litellm_params']['api_key']}\"")

    lines += [
        "",
        "general_settings:",
        "  master_key: \"local\"",
        "  drop_params: true",
    ]
    return "\n".join(lines) + "\n"

# ─── Docker operations ────────────────────────────────────────────────────────

def docker_run(cmd: list, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker"] + cmd,
        capture_output=capture,
        text=True,
        timeout=30,
    )

def container_exists() -> bool:
    r = docker_run(["ps", "-a", "--filter", f"name={CONTAINER_NAME}", "--format", "{{.Names}}"],
                   capture=True)
    return CONTAINER_NAME in r.stdout

def container_running() -> bool:
    r = docker_run(["ps", "--filter", f"name={CONTAINER_NAME}", "--format", "{{.Names}}"],
                   capture=True)
    return CONTAINER_NAME in r.stdout

def write_config_to_host(config_yaml: str) -> str:
    """Write litellm config to a persistent location on the host."""
    config_dir = Path.home() / ".claude" / "skills" / "auth-token-manager" / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "litellm_config.yaml"
    config_path.write_text(config_yaml)
    config_path.chmod(0o600)
    return str(config_path)

# ─── Commands ────────────────────────────────────────────────────────────────

def cmd_start(cfg: dict, port: int, token: str = None):
    if container_running():
        print(f"[OK] Proxy already running on localhost:{port}")
        return

    if container_exists():
        print("[INFO] Removing stopped container...")
        docker_run(["rm", CONTAINER_NAME], capture=True)

    central_env  = cfg["central_env"]
    claude_token = token or get_token(central_env)
    gemini_token = get_gemini_token(central_env)

    if not claude_token:
        print("[ERROR] No Claude token found.")
        print("        Run 'claude setup-token' then 'token-refresh --force'")
        sys.exit(1)

    config_yaml = make_litellm_config(claude_token, gemini_token)
    config_path = write_config_to_host(config_yaml)

    IMAGE = "ghcr.io/berriai/litellm:main-latest"

    # Pull image first (separate step with no timeout — can take minutes)
    print(f"[INFO] Pulling proxy image (this may take a few minutes on first run)...")
    pull = subprocess.run(
        ["docker", "pull", IMAGE],
        text=True,
        timeout=600,   # 10 min for large image download
    )
    if pull.returncode != 0:
        print(f"[ERROR] Failed to pull image.")
        sys.exit(1)
    print(f"[INFO] Starting proxy on port {port}...")

    result = docker_run([
        "run", "-d",
        "--name", CONTAINER_NAME,
        "--restart", "unless-stopped",
        "-p", f"{port}:4000",
        "-v", f"{config_path}:/app/config.yaml:ro",
        IMAGE,
        "--config", "/app/config.yaml",
        "--port", "4000",
    ])

    if result.returncode != 0:
        print(f"[ERROR] Failed to start proxy container.")
        print(f"        stderr: {result.stderr}")
        sys.exit(1)

    print(f"[OK] Proxy started → http://localhost:{port}/v1")
    print(f"     Models: claude, claude-sonnet-4-6, claude-opus-4-6" +
          (", gemini, gemini-2.0-flash" if gemini_token else ""))
    print(f"\n     Connect from code:")
    print(f"       OPENAI_BASE_URL=http://localhost:{port}/v1")
    print(f"       OPENAI_API_KEY=local")
    print(f"\n     Connect from Docker app:")
    print(f"       OPENAI_BASE_URL=http://host.docker.internal:{port}/v1")

def cmd_stop():
    if not container_exists():
        print("[INFO] Proxy container not found.")
        return
    docker_run(["stop", CONTAINER_NAME], capture=True)
    docker_run(["rm",   CONTAINER_NAME], capture=True)
    print("[OK] Proxy stopped.")

def cmd_restart(cfg: dict, port: int):
    cmd_stop()
    cmd_start(cfg, port)

def cmd_status(port: int):
    if container_running():
        r = docker_run(["ps", "--filter", f"name={CONTAINER_NAME}",
                        "--format", "{{.Status}}\t{{.Ports}}"], capture=True)
        print(f"[OK] Proxy running: {r.stdout.strip()}")
        print(f"     Endpoint: http://localhost:{port}/v1")
    elif container_exists():
        print("[WARN] Proxy container exists but is stopped. Run: token-proxy --start")
    else:
        print("[INFO] Proxy not installed. Run: token-proxy --start")

def cmd_logs():
    if not container_exists():
        print("[INFO] Proxy container not found.")
        return
    subprocess.run(["docker", "logs", "-f", "--tail", "50", CONTAINER_NAME])

# ─── Entry point ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="CLI Proxy Manager")
    parser.add_argument("--start",    action="store_true")
    parser.add_argument("--stop",     action="store_true")
    parser.add_argument("--restart",  action="store_true")
    parser.add_argument("--status",   action="store_true")
    parser.add_argument("--logs",     action="store_true")
    parser.add_argument("--token",    metavar="TOKEN", help="Override token")
    parser.add_argument("--port",     type=int, default=None)
    args = parser.parse_args()

    cfg  = load_config()
    port = args.port or cfg["port"]

    if args.stop:
        cmd_stop()
    elif args.status:
        cmd_status(port)
    elif args.logs:
        cmd_logs()
    elif args.restart:
        cmd_restart(cfg, port)
    else:
        # Default: start
        cmd_start(cfg, port, token=args.token)

if __name__ == "__main__":
    main()
