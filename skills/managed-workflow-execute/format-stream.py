#!/usr/bin/env python3
"""Formats Claude CLI stream-json output into human-readable terminal output."""

import json
import sys

# ANSI colors
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"
MAGENTA = "\033[35m"
RED = "\033[31m"
BG_RED = "\033[41m"
BG_GREEN = "\033[42m"
WHITE = "\033[37m"

MAX_CONTENT_LINES = 40


def truncate_lines(text, max_lines=MAX_CONTENT_LINES):
    """Truncate text to max_lines, showing count of hidden lines."""
    lines = text.split("\n")
    if len(lines) <= max_lines:
        return text
    shown = "\n".join(lines[:max_lines])
    return f"{shown}\n{DIM}    ... ({len(lines) - max_lines} more lines){RESET}"


def show_diff(old, new):
    """Show a colored diff between old and new strings."""
    if old:
        for line in old.split("\n"):
            print(f"{RED}  - {line}{RESET}", flush=True)
    if new:
        for line in new.split("\n"):
            print(f"{GREEN}  + {line}{RESET}", flush=True)


def format_tool_use(tool_name, tool_input):
    """Format a tool call with its content."""
    if tool_name == "Read":
        path = tool_input.get("file_path", "")
        print(f"\n{CYAN}{BOLD}  Reading:{RESET} {path}", flush=True)

    elif tool_name == "Write":
        path = tool_input.get("file_path", "")
        content = tool_input.get("content", "")
        print(f"\n{GREEN}{BOLD}  Writing:{RESET} {path}", flush=True)
        if content:
            truncated = truncate_lines(content)
            for line in truncated.split("\n"):
                print(f"{GREEN}  | {RESET}{DIM}{line}{RESET}", flush=True)

    elif tool_name == "Edit":
        path = tool_input.get("file_path", "")
        old = tool_input.get("old_string", "")
        new = tool_input.get("new_string", "")
        replace_all = tool_input.get("replace_all", False)
        label = " (replace all)" if replace_all else ""
        print(f"\n{YELLOW}{BOLD}  Editing:{RESET} {path}{label}", flush=True)
        show_diff(old, new)

    elif tool_name == "Bash":
        cmd = tool_input.get("command", "")
        desc = tool_input.get("description", "")
        if desc:
            print(f"\n{MAGENTA}{BOLD}  Running:{RESET} {desc}", flush=True)
        if cmd:
            for line in cmd.split("\n"):
                print(f"{MAGENTA}  $ {RESET}{DIM}{line}{RESET}", flush=True)

    elif tool_name == "Grep":
        pattern = tool_input.get("pattern", "")
        path = tool_input.get("path", "")
        print(f"\n{CYAN}{BOLD}  Searching:{RESET} '{pattern}' in {path}", flush=True)

    elif tool_name == "Glob":
        pattern = tool_input.get("pattern", "")
        print(f"\n{CYAN}{BOLD}  Finding:{RESET} {pattern}", flush=True)

    elif tool_name == "Skill":
        skill = tool_input.get("skill", "")
        print(f"\n{GREEN}{BOLD}  Skill:{RESET} {skill}", flush=True)

    elif tool_name == "Agent":
        prompt = tool_input.get("prompt", "")[:100]
        agent_type = tool_input.get("subagent_type", "")
        label = f" [{agent_type}]" if agent_type else ""
        print(f"\n{MAGENTA}{BOLD}  Agent{label}:{RESET} {prompt}...", flush=True)

    elif tool_name == "ToolSearch":
        query = tool_input.get("query", "")
        print(f"{DIM}  [ToolSearch: {query}]{RESET}", flush=True)

    elif tool_name in ("TodoWrite", "TodoRead"):
        print(f"{DIM}  [{tool_name}]{RESET}", flush=True)

    elif tool_name == "WebFetch":
        url = tool_input.get("url", "")
        print(f"\n{CYAN}{BOLD}  Fetching:{RESET} {url}", flush=True)

    elif tool_name == "WebSearch":
        query = tool_input.get("query", "")
        print(f"\n{CYAN}{BOLD}  Web Search:{RESET} {query}", flush=True)

    else:
        print(f"\n{CYAN}{BOLD}  {tool_name}{RESET}", flush=True)


def format_tool_result(content):
    """Show tool result output."""
    if not content:
        return
    text = ""
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text += block.get("text", "")
            elif isinstance(block, str):
                text += block
    elif isinstance(content, str):
        text = content

    if not text.strip():
        return

    truncated = truncate_lines(text.strip(), 15)
    for line in truncated.split("\n"):
        print(f"{DIM}    {line[:200]}{RESET}", flush=True)


def main():
    """Read JSON lines from stdin and format them."""
    print(f"\n{DIM}{'─' * 60}{RESET}", flush=True)
    print(f"{DIM}  Claude session starting...{RESET}", flush=True)
    print(f"{DIM}{'─' * 60}{RESET}\n", flush=True)

    # State tracking
    current_tool = None
    tool_input_json = ""
    in_thinking = False
    in_text = False

    while True:
        line = sys.stdin.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue

        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            if line.strip():
                print(line, flush=True)
            continue

        top_type = raw.get("type", "")

        # Skip system events (hooks, init)
        if top_type == "system":
            subtype = raw.get("subtype", "")
            if subtype == "init":
                model = raw.get("model", "unknown")
                print(f"{DIM}  Model: {model}{RESET}", flush=True)
            continue

        # Unwrap stream_event wrapper
        if top_type == "stream_event":
            event = raw.get("event", {})
        elif top_type == "assistant":
            # Full assistant message — already shown via stream events
            continue
        elif top_type == "result":
            cost = raw.get("cost_usd", raw.get("cost", None))
            if cost is not None:
                print(f"\n{DIM}  Session cost: ${cost}{RESET}", flush=True)
            duration = raw.get("duration_ms", raw.get("duration_api_ms", None))
            if duration is not None:
                secs = duration / 1000 if isinstance(duration, (int, float)) else duration
                print(f"{DIM}  Duration: {secs:.1f}s{RESET}", flush=True)
            continue
        elif top_type == "tool_result":
            # Tool result from the system
            content = raw.get("content", "")
            format_tool_result(content)
            continue
        else:
            event = raw

        etype = event.get("type", "")

        # ── content_block_start ──
        if etype == "content_block_start":
            block = event.get("content_block", {})
            btype = block.get("type", "")

            if btype == "thinking":
                in_thinking = True
                sys.stdout.write(f"\n{DIM}  Thinking...{RESET}")
                sys.stdout.flush()
            elif btype == "text":
                in_text = True
                in_thinking = False
                text = block.get("text", "")
                if text.strip():
                    sys.stdout.write(f"\n{BOLD}{text}{RESET}")
                    sys.stdout.flush()
            elif btype == "tool_use":
                in_thinking = False
                in_text = False
                current_tool = block.get("name", "")
                tool_input_json = ""
            elif btype == "tool_result":
                content = block.get("content", "")
                format_tool_result(content)

        # ── content_block_delta ──
        elif etype == "content_block_delta":
            delta = event.get("delta", {})
            dtype = delta.get("type", "")

            if dtype == "thinking_delta":
                sys.stdout.write(f"{DIM}.{RESET}")
                sys.stdout.flush()
            elif dtype == "text_delta":
                text = delta.get("text", "")
                if text:
                    sys.stdout.write(f"{BOLD}{text}{RESET}")
                    sys.stdout.flush()
            elif dtype == "input_json_delta" and current_tool:
                tool_input_json += delta.get("partial_json", "")
            elif dtype == "signature_delta":
                pass

        # ── content_block_stop ──
        elif etype == "content_block_stop":
            if current_tool:
                try:
                    tool_input = json.loads(tool_input_json) if tool_input_json else {}
                except json.JSONDecodeError:
                    tool_input = {}
                format_tool_use(current_tool, tool_input)
                current_tool = None
                tool_input_json = ""
            elif in_thinking:
                in_thinking = False
                print("", flush=True)
            elif in_text:
                in_text = False
                print("", flush=True)

        # ── message_delta (stop reason, usage) ──
        elif etype == "message_delta":
            pass

        # ── message_stop ──
        elif etype == "message_stop":
            pass

    print(f"\n{DIM}{'─' * 60}{RESET}", flush=True)
    print(f"{DIM}  Session ended.{RESET}", flush=True)
    print(f"{DIM}{'─' * 60}{RESET}\n", flush=True)


if __name__ == "__main__":
    main()
