#!/usr/bin/env python3
"""
auth-token-manager — proxy_manager.py
Manages the LiteLLM Docker proxy container.
Exposes OpenAI-compatible API at localhost:PORT.

Commands:
  (default) / --start   Start proxy
  --stop                Stop proxy
  --restart             Restart proxy
  --status              Show status
  --logs                Tail logs
  --token TOKEN         Override Claude token (for install.sh)
  --port PORT           Override port
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

CONTAINER_NAME = "ai-proxy"
DEFAULT_PORT   = 8080

def load_config() -> dict:
    config_file = Path.home() / ".config" / "ai-auth" / "config.env"
    cfg = {}
    if config_file.exists():
        for line in config_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                cfg[k.strip()] = v.strip().strip('"')
    return {
        "central_env": Path(cfg.get("AI_AUTH_CENTRAL_ENV",
                            Path.home() / ".config" / "ai-auth" / "tokens.env")),
        "port": int(cfg.get("AI_PROXY_PORT", DEFAULT_PORT)),
    }

def read_tokens(central_env: Path) -> dict:
    result = {}
    if not central_env.exists():
        return result
    for line in central_env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            result[k.strip()] = v.strip().strip('"')
    return result

def make_litellm_config(claude_token: str, gemini_token: str) -> str:
    models = []
    if claude_token:
        for alias, model in [
            ("claude",            "anthropic/claude-sonnet-4-6"),
            ("claude-sonnet-4-6", "anthropic/claude-sonnet-4-6"),
            ("claude-opus-4-6",   "anthropic/claude-opus-4-6"),
            ("claude-haiku-4-5",  "anthropic/claude-haiku-4-5-20251001"),
        ]:
            models.append((alias, model, claude_token))
    if gemini_token:
        for alias, model in [
            ("gemini",           "gemini/gemini-2.0-flash"),
            ("gemini-2.0-flash", "gemini/gemini-2.0-flash"),
            ("gemini-2.5-pro",   "gemini/gemini-2.5-pro"),
            ("gemini-2.5-flash", "gemini/gemini-2.5-flash"),
        ]:
            models.append((alias, model, gemini_token))

    if not models:
        raise ValueError("No tokens available. Run install.sh first.")

    lines = ["model_list:"]
    for alias, model, key in models:
        lines += [
            f"  - model_name: {alias}",
            f"    litellm_params:",
            f"      model: {model}",
            f'      api_key: "{key}"',
        ]
    lines += ["", "general_settings:", '  master_key: "local"', "  drop_params: true"]
    return "\n".join(lines) + "\n"

def write_litellm_config(yaml: str) -> str:
    path = Path.home() / ".config" / "ai-auth" / "litellm_config.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml)
    path.chmod(0o600)
    return str(path)

def docker(args: list, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["docker"] + args,
                          capture_output=capture, text=True, timeout=60)

def is_running() -> bool:
    r = docker(["ps", "--filter", f"name={CONTAINER_NAME}", "--format", "{{.Names}}"])
    return CONTAINER_NAME in r.stdout

def exists() -> bool:
    r = docker(["ps", "-a", "--filter", f"name={CONTAINER_NAME}", "--format", "{{.Names}}"])
    return CONTAINER_NAME in r.stdout

def cmd_start(cfg: dict, port: int, override_token: str = None):
    if is_running():
        print(f"[OK] Proxy already running → http://localhost:{port}/v1")
        return
    if exists():
        docker(["rm", CONTAINER_NAME])

    tokens       = read_tokens(cfg["central_env"])
    claude_token = override_token or tokens.get("CLAUDE_CODE_OAUTH_TOKEN", "")
    gemini_token = tokens.get("GEMINI_OAUTH_TOKEN", "")

    if not claude_token and not gemini_token:
        print("[ERROR] No tokens found. Run install.sh first.")
        sys.exit(1)

    config_path = write_litellm_config(
        make_litellm_config(claude_token, gemini_token)
    )

    r = docker([
        "run", "-d",
        "--name", CONTAINER_NAME,
        "--restart", "unless-stopped",
        "-p", f"{port}:4000",
        "-v", f"{config_path}:/app/config.yaml:ro",
        "ghcr.io/berriai/litellm:main-latest",
        "--config", "/app/config.yaml", "--port", "4000",
    ], capture=True)

    if r.returncode != 0:
        print(f"[ERROR] {r.stderr.strip()}")
        sys.exit(1)

    models = []
    if claude_token: models += ["claude", "claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5"]
    if gemini_token: models += ["gemini", "gemini-2.0-flash", "gemini-2.5-pro", "gemini-2.5-flash"]

    print(f"[OK] Proxy started → http://localhost:{port}/v1")
    print(f"     Models: {', '.join(models)}")
    print(f"\n     Python:  AsyncOpenAI(base_url='http://localhost:{port}/v1', api_key='local')")
    print(f"     Docker:  http://host.docker.internal:{port}/v1")

def cmd_stop():
    if not exists():
        print("[INFO] Proxy not running.")
        return
    docker(["stop", CONTAINER_NAME])
    docker(["rm",   CONTAINER_NAME])
    print("[OK] Proxy stopped.")

def cmd_status(port: int):
    if is_running():
        r = docker(["ps", "--filter", f"name={CONTAINER_NAME}", "--format", "{{.Status}}"])
        print(f"[OK] Running: {r.stdout.strip()} → http://localhost:{port}/v1")
    elif exists():
        print("[WARN] Container stopped. Run: token-proxy --start")
    else:
        print("[INFO] Not installed. Run: token-proxy --start")

def cmd_logs():
    if not exists():
        print("[INFO] No container found.")
        return
    subprocess.run(["docker", "logs", "-f", "--tail", "50", CONTAINER_NAME])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start",   action="store_true")
    parser.add_argument("--stop",    action="store_true")
    parser.add_argument("--restart", action="store_true")
    parser.add_argument("--status",  action="store_true")
    parser.add_argument("--logs",    action="store_true")
    parser.add_argument("--token",   default=None)
    parser.add_argument("--port",    type=int, default=None)
    args = parser.parse_args()

    cfg  = load_config()
    port = args.port or cfg["port"]

    if args.stop:           cmd_stop()
    elif args.status:       cmd_status(port)
    elif args.logs:         cmd_logs()
    elif args.restart:      cmd_stop(); cmd_start(cfg, port)
    else:                   cmd_start(cfg, port, override_token=args.token)

if __name__ == "__main__":
    main()
