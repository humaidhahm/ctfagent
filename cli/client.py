#!/usr/bin/env python3
"""
CTFAgent — Autonomous CTF Solving Framework
Interactive CLI (Metasploit-style)
"""

import asyncio
import json
from prompt_toolkit import prompt
import os
import select
import shutil
import signal
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from cli.terminal import setup_terminal
from dotenv import set_key
from langchain_core.messages import SystemMessage, HumanMessage
from backend.core.llm_client import get_llm, refresh_llm_runtime, RotatingLLM
from run import (
    configure_llm_keys,
    configured_key_counts,
    ENV_FILE,
    export_runtime_env,
    get_version,
)


_exiting = False

def _signal_handler(signum, frame):
    global _exiting
    if _exiting:
        os._exit(128 + signum)
    _exiting = True
    sys.stderr.write("\033[?25h\033[0m\n\033[1;33mShutting down CTFAgent...\033[0m\n")
    sys.exit(0)

def _extract_json(text: str) -> tuple[dict | None, str]:
    """Extract the first JSON object from text that may contain natural language prefix."""
    text = text.replace("```json", "").replace("```", "").strip()
    start = text.find("{")
    if start == -1:
        return None, text
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i+1]), text[:start].strip()
                except json.JSONDecodeError:
                    return None, text
    return None, text


# Enable command history (up/down arrow recall)
HISTFILE = os.path.expanduser("~/.ctfagent_history")
try:
    import readline
    try:
        readline.read_history_file(HISTFILE)
    except FileNotFoundError:
        pass
    import atexit
    atexit.register(lambda: readline.write_history_file(HISTFILE))
except ImportError:
    pass

_prompt_session = None


def _get_prompt_session():
    global _prompt_session
    if _prompt_session is None:
        try:
            from prompt_toolkit import PromptSession
            from prompt_toolkit.history import FileHistory

            _prompt_session = PromptSession(history=FileHistory(HISTFILE))
        except Exception:
            _prompt_session = False
    return _prompt_session if _prompt_session else None


def decode_ansi_sequence(seq_str: str, history: list = None) -> str:
    """Decodes ANSI escape sequences and MSVCRT key codes into line input text.

    Decodes sequences such as ^[[A, ^[[B, ^[[C, ^[[D, ^[[5~, ^[[6~ without returning
    or displaying raw sequence characters.
    """
    if not history:
        history = []
        if os.path.exists(HISTFILE):
            try:
                with open(HISTFILE, "r", encoding="utf-8", errors="ignore") as f:
                    history = [line.rstrip("\r\n") for line in f if line.rstrip("\r\n")]
            except Exception:
                pass

    buf = []
    cursor = 0
    hist_idx = len(history)
    saved_draft = ""

    i = 0
    n = len(seq_str)
    while i < n:
        ch = seq_str[i]
        # MSVCRT Windows key prefix
        if ch in ('\xe0', '\x00') and i + 1 < n:
            code = seq_str[i + 1]
            i += 2
            if code == 'H':  # Up Arrow
                if history:
                    if hist_idx == len(history):
                        saved_draft = "".join(buf)
                    if hist_idx > 0:
                        hist_idx -= 1
                        buf = list(history[hist_idx])
                        cursor = len(buf)
            elif code == 'P':  # Down Arrow
                if history:
                    if hist_idx < len(history) - 1:
                        hist_idx += 1
                        buf = list(history[hist_idx])
                        cursor = len(buf)
                    elif hist_idx == len(history) - 1:
                        hist_idx = len(history)
                        buf = list(saved_draft)
                        cursor = len(buf)
            elif code == 'K':  # Left Arrow
                if cursor > 0:
                    cursor -= 1
            elif code == 'M':  # Right Arrow
                if cursor < len(buf):
                    cursor += 1
            elif code == 'I':  # Page Up
                if history:
                    if hist_idx == len(history):
                        saved_draft = "".join(buf)
                    hist_idx = max(0, hist_idx - 5)
                    buf = list(history[hist_idx])
                    cursor = len(buf)
            elif code == 'Q':  # Page Down
                if history:
                    if hist_idx < len(history) - 1:
                        hist_idx = min(len(history) - 1, hist_idx + 5)
                        buf = list(history[hist_idx])
                        cursor = len(buf)
                    elif hist_idx == len(history) - 1:
                        hist_idx = len(history)
                        buf = list(saved_draft)
                        cursor = len(buf)
            continue

        # ANSI Escape sequences
        if ch == '\x1b':
            if i + 2 < n and seq_str[i + 1:i + 3] in ('[A', 'OA'):  # Up Arrow
                i += 3
                if history:
                    if hist_idx == len(history):
                        saved_draft = "".join(buf)
                    if hist_idx > 0:
                        hist_idx -= 1
                        buf = list(history[hist_idx])
                        cursor = len(buf)
                continue
            elif i + 2 < n and seq_str[i + 1:i + 3] in ('[B', 'OB'):  # Down Arrow
                i += 3
                if history:
                    if hist_idx < len(history) - 1:
                        hist_idx += 1
                        buf = list(history[hist_idx])
                        cursor = len(buf)
                    elif hist_idx == len(history) - 1:
                        hist_idx = len(history)
                        buf = list(saved_draft)
                        cursor = len(buf)
                continue
            elif i + 2 < n and seq_str[i + 1:i + 3] in ('[C', 'OC'):  # Right Arrow
                i += 3
                if cursor < len(buf):
                    cursor += 1
                continue
            elif i + 2 < n and seq_str[i + 1:i + 3] in ('[D', 'OD'):  # Left Arrow
                i += 3
                if cursor > 0:
                    cursor -= 1
                continue
            elif i + 3 < n and seq_str[i + 1:i + 4] == '[5~':  # Page Up
                i += 4
                if history:
                    if hist_idx == len(history):
                        saved_draft = "".join(buf)
                    hist_idx = max(0, hist_idx - 5)
                    buf = list(history[hist_idx])
                    cursor = len(buf)
                continue
            elif i + 3 < n and seq_str[i + 1:i + 4] == '[6~':  # Page Down
                i += 4
                if history:
                    if hist_idx < len(history) - 1:
                        hist_idx = min(len(history) - 1, hist_idx + 5)
                        buf = list(history[hist_idx])
                        cursor = len(buf)
                    elif hist_idx == len(history) - 1:
                        hist_idx = len(history)
                        buf = list(saved_draft)
                        cursor = len(buf)
                continue
            else:
                j = i + 1
                while j < n and not seq_str[j].isalpha() and seq_str[j] != '~':
                    j += 1
                i = j + 1 if j < n else n
                continue

        if ch in ('\r', '\n'):
            break
        elif ch in ('\x08', '\x7f'):
            if cursor > 0:
                buf.pop(cursor - 1)
                cursor -= 1
            i += 1
        elif ch == '\x03':
            raise KeyboardInterrupt()
        elif ch == '\x04':
            raise EOFError()
        elif ord(ch) >= 32:
            buf.insert(cursor, ch)
            cursor += 1
            i += 1
        else:
            i += 1

    return "".join(buf)


def safe_input(prompt_text: str = "") -> str:
    """Read a line of user input, decoding ANSI escape sequences (arrow keys, Page Up/Down).

    Prevents raw sequence output such as ^[[A, ^[[B, ^[[C, ^[[D, ^[[5~, ^[[6~.
    Supports Up/Down Arrow history navigation, Left/Right Arrow cursor movement, Page Up/Down.
    """
    if sys.stdin.isatty():
        session = _get_prompt_session()
        if session is not None:
            try:
                from prompt_toolkit.formatted_text import ANSI

                return session.prompt(ANSI(prompt_text))
            except (EOFError, KeyboardInterrupt):
                raise
            except Exception:
                pass

    try:
        raw_line = input(prompt_text)
    except (EOFError, KeyboardInterrupt):
        raise

    if "\x1b" in raw_line or "\xe0" in raw_line or "^[" in raw_line:
        raw_line = raw_line.replace("^[", "\x1b")
        return decode_ansi_sequence(raw_line)

    return raw_line


# Redirect loguru to file BEFORE any backend imports
import loguru
loguru.logger.remove()  # remove default stderr handler
loguru.logger.add("/tmp/ctfagent.log", rotation="10 MB", level="INFO", format="{time} | {level} | {message}")

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.text import Text
from rich.layout import Layout
from rich.markdown import Markdown
from rich.style import Style
from rich import box
from rich.align import Align

console = Console()
error_console = Console(stderr=True)

ANSI_CYAN = "\033[38;2;0;229;255m"
ANSI_PURPLE = "\033[38;2;168;85;247m"
ANSI_GREEN = "\033[38;2;63;185;80m"
ANSI_WHITE = "\033[1;38;2;230;237;243m"
ANSI_RESET = "\033[0m"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.agents.supervisor import supervisor_graph
from backend.ingestion.ingestor import ingest_challenge
from backend.config.settings import settings
from backend.core.flag_detector import detect_flag, validate_flag
from backend.memory.session_store import session_store
from backend.services.memory_client import MemoryServiceError, memory_client
from backend.memory.experience_db import experience_db


def set_default_flag_format(flag_format: str) -> None:
    set_key(str(ENV_FILE), "FLAG_FORMAT", flag_format)
    settings.flag_format = flag_format


BANNER = r"""
[bold #00E5FF]  _____ _______ ______                      _   
 / ____|__   __|  ____/\                   | |  
| |       | |  | |__ /  \   __ _  ___ _ __ | |_ 
| |       | |  |  __/ /\ \ / _` |/ _ \ '_ \| __|
| |____   | |  | | / ____ \ (_| |  __/ | | | |_ 
 \_____|  |_|  |_|/_/    \_\__, |\___|_| |_|\__|
                            __/ |               
                           |___/                 [/bold #00E5FF]"""[1:]

TAGLINE = "[bold #00E5FF]Autonomous CTF Solver  ·  NVIDIA NIM x GEMMA 31B x GEMINI 3.1 Flash Lite  ·  v1.0.0[/bold #00E5FF]"

def print_help():
    """Print categorized help with Rich tables in a Panel."""
    table = Table(show_header=False, box=None, padding=(0, 2, 0, 0))
    table.add_column("Cmd", style="#00E5FF", no_wrap=True)
    table.add_column("Args", style="#9CA3AF", no_wrap=True)
    table.add_column("Description")

    help_items = [
        ("[#3FB950]CHALLENGES[/#3FB950]", "", ""),
        ("/solve", "<desc|file>", "Submit a CTF challenge to solve"),
        ("/flag","FORMAT","Set the flag format"),
        ("/llm","","Configure LLMs"),
        ("/sessions", "", "List all active sessions"),
        ("/view", "<id>", "View session details and trace"),
        ("/watch", "<id>", "Live-stream agent reasoning trace"),
        ("/writeup", "<id>", "Generate writeup for solved challenge"),
        ("/benchmark", "", "Run benchmark against known challenges"),
        ("", "", ""),
        ("[#3FB950]EXPERIENCE[/#3FB950]", "", ""),
        ("/experience", "", "View/manage experience database"),
        ("/experience_find", "<query>", "Search similar past challenges"),
        ("/experience_clear", "", "Clear all experiences"),
        ("", "", ""),
        ("[#3FB950]TOOLS[/#3FB950]", "", ""),
        ("[#3FB950]MCP MEMORY[/#3FB950]", "", ""),
        ("/memory search", "<query>", "Search MCP writeups"),
        ("/memory get", "<id>", "Retrieve a complete MCP writeup"),
        ("/memory domains", "", "List MCP writeup domains"),
        ("/memory sources", "<query>", "Search MCP source documents"),
        ("/memory source", "<id>", "Retrieve an MCP source document"),
        ("/memory fetch", "<url>", "Fetch a bounded MCP web reference"),
        ("", "", ""),
        ("[#3FB950]TOOLS[/#3FB950]", "", ""),
        ("/tools", "", "Check all available security tools"),
        ("/tools", "<domain>", "Check tools for a domain (web, pwn, etc.)"),
        ("/install", "", "Install missing system tools (sudo)"),
        ("/install_", "<domain>", "Install tools for a specific domain"),
        ("", "", ""),
        ("[#3FB950]SYSTEM[/#3FB950]", "", ""),
        ("/banner", "", "Display the banner"),
        ("/clear", "", "Clear the screen"),
        ("/help", "", "Show this help message"),
        ("exit / quit", "", "Exit CTFAgent"),
    ]
    for cmd, arg, desc in help_items:
        table.add_row(cmd, arg, desc)

    examples = Table(show_header=False, box=None, padding=(0, 2, 0, 0))
    examples.add_column("", style="#9CA3AF")
    examples.add_row("[bold #D29922]Examples:[/bold #D29922]")
    examples.add_row('solve "The challenge has a login form at http://target.com"')
    examples.add_row("solve ./challenge.elf")
    examples.add_row("watch <session_id>")

    console.print(Panel(table, border_style="#9CA3AF", title="[bold]Commands[/bold]", title_align="left"))
    console.print(Panel(examples, border_style="#9CA3AF", title="[bold]Examples[/bold]", title_align="left"))


BANNER = r"""
[bold #00E5FF]   ______ _______ ______    _____  ____  _    __ ______ _____
  / ____//_  __// ____/   / ___/ / __ \| |  / // ____// ___/
 / /      / /  / /_       \__ \ / / / /| | / // __/   \__ \
/ /___   / /  / __/      ___/ // /_/ / | |/ // /___  ___/ /
\____/  /_/  /_/        /____/ \____/  |___//_____/ /____/ [/bold #00E5FF]"""[1:]

TAGLINE = "[bold #00E5FF]AI Ethical Hacking Terminal  //  CTF Solver  //  v1.0.0[/bold #00E5FF]"

THEME = {
    "cyan": "#00E5FF",
    "muted": "#9CA3AF",
    "green": "#3FB950",
    "purple": "#A855F7",
    "red": "#F85149",
}


def terminal_panel(renderable, title: str, border_style: str = "#00E5FF", **kwargs) -> Panel:
    """Create a compact neon terminal panel."""
    return Panel(
        renderable,
        title=f"[bold {THEME['cyan']}][ {title.upper()} ][/bold {THEME['cyan']}]",
        title_align="left",
        border_style=border_style,
        box=box.ROUNDED,
        padding=(1, 2),
        **kwargs,
    )


def print_help():
    """Print a themed command dashboard."""
    def command_group(rows: list[tuple[str, str, str]]) -> Table:
        table = Table(show_header=False, box=None, padding=(0, 1, 0, 0), expand=True)
        table.add_column("Prompt", style="#00E5FF", no_wrap=True, width=1)
        table.add_column("Command", style="#E6EDF3", no_wrap=True)
        table.add_column("Args", style="#A855F7", no_wrap=True)
        table.add_column("Description", style="#9CA3AF")
        for cmd, args, desc in rows:
            table.add_row(">", cmd, args, desc)
        return table

    solve_rows = [
        ("/solve", "<desc|file>", "submit a challenge"),
        ("/scan", "<desc|file>", "alias for solve"),
        ("/flag", "", "set flag format"),
        ("/writeup", "<id>", "generate writeup"),
    ]
    session_rows = [
        ("/sessions", "", "list sessions"),
        ("/history", "", "alias for sessions"),
        ("/view", "<id>", "show session trace"),
        ("/watch", "<id>", "stream live trace"),
    ]
    tool_rows = [
        ("/tools", "[domain]", "check installed tools"),
        ("/install", "[domain]", "install missing tools"),
        ("/experience", "", "show solved history"),
        ("/experience find", "<query>", "search similar solves"),
    ]
    system_rows = [
        ("/chat", "[question]", "ask the LLM"),
        ("/llm", "", "configure providers"),
        ("/clear", "", "redraw terminal"),
        ("/exit", "", "quit"),
    ]

    grid = Table.grid(expand=True)
    grid.add_column(ratio=1)
    grid.add_column(ratio=1)
    grid.add_row(
        terminal_panel(command_group(solve_rows), "Challenges"),
        terminal_panel(command_group(session_rows), "Sessions"),
    )
    grid.add_row(
        terminal_panel(command_group(tool_rows), "Tools & Memory"),
        terminal_panel(command_group(system_rows), "System"),
    )

    examples = Table.grid(padding=(0, 1))
    examples.add_column(style="#9CA3AF")
    examples.add_row("[#00E5FF]>[/#00E5FF] [#E6EDF3]/solve[/#E6EDF3] [#A855F7]\"login form at http://target\"[/#A855F7]")
    examples.add_row("[#00E5FF]>[/#00E5FF] [#E6EDF3]/tools[/#E6EDF3] [#A855F7]web[/#A855F7]")
    examples.add_row("[#00E5FF]>[/#00E5FF] [#E6EDF3]/watch[/#E6EDF3] [#A855F7]<session_id>[/#A855F7]")

    console.print(Panel(
        grid,
        title="[bold #00E5FF]CTF SOLVER // HELP MENU[/bold #00E5FF]",
        title_align="center",
        border_style="#9CA3AF",
        box=box.ROUNDED,
        padding=(1, 1),
    ))
    console.print(terminal_panel(examples, "Quick Runs", border_style="#9CA3AF"))


DOMAIN_COLORS = {
    "web": "#00E5FF",
    "crypto": "#D29922",
    "forensics": "#101725",
    "pwn": "#F85149",
    "re": "#A855F7",
    "osint": "#D29922",
    "misc": "#3FB950",
    "unknown": "#9CA3AF",
}

DOMAIN_COLORS_ANSI = {
    "Web": "#00E5FF", "Forensics": "#101725", "Pwn": "#F85149",
    "RE": "#A855F7", "Crypto": "#D29922", "OSINT": "#D29922", "Misc": "#3FB950",
}

EVENT_COLORS = {
    "classification": "bold #00E5FF",
    "llm_reasoning": "bold #00E5FF",
    "tool_call": "bold #3FB950",
    "tool_result": "#E6EDF3",
    "hypothesis": "bold #A855F7",
    "flag_candidate": "bold #D29922",
    "flag_validated": "bold #3FB950 on #101725",
    "error": "bold #F85149",
    "completed": "bold #3FB950",
    "difficulty": "#D29922",
}


def format_event(event: dict) -> Text:
    etype = event.get("event_type", "unknown")
    agent = event.get("agent", "?")
    data = event.get("data", {})
    ts = event.get("timestamp", "")[11:19]

    color = EVENT_COLORS.get(etype, "#E6EDF3")
    prefix = f"[{ts}] [{etype.upper():<14}] [{agent:<10}]"

    if etype == "classification":
        cat = data.get("category", "?")
        conf = data.get("confidence", 0)
        return Text(f"{prefix} → {cat} (confidence: {conf:.2f})", style=color)

    elif etype == "llm_reasoning":
        raw = data.get("raw_output", "")[:1200]
        reasoning = data.get("reasoning", "")
        error = data.get("error", "")
        if error:
            return Text(f"{prefix} ⚠ LLM error: {error}", style="bold #F85149")
        parsed, prefix_text = _extract_json(raw)
        if parsed:
            tool = parsed.get("tool", "")
            args = parsed.get("args", {})
            rsn = parsed.get("reasoning", reasoning) or reasoning
            args_str = " ".join(f"{k}={v}" for k, v in args.items() if v)
            lines = []
            if prefix_text:
                lines.append(prefix_text[:200])
            lines.append(f"🧠 {rsn}")
            if tool:
                lines.append(f"🔧 {tool} {args_str}")
            display = "\n  │ ".join(lines)
            return Text(f"{prefix} ▼ {display}", style=color)
        lines = raw.split("\n")
        display = "\n  │ ".join(lines[:6])
        return Text(f"{prefix} ▼ {display}", style=color)

    elif etype == "tool_call":
        tool = data.get("tool", "?")
        args = data.get("args", {})
        if isinstance(args, str):
            args = {}
        args_str = " ".join(f"{k}={v}" for k, v in args.items() if v)
        return Text(f"{prefix} 🔧 {tool} {args_str}", style=color)

    elif etype == "tool_result":
        success = data.get("success", False)
        output = data.get("output", "")[:400]
        error = data.get("error", "")
        status = "✓" if success else "✗"
        if output:
            lines = output.split("\n")[:5]
            out_preview = "\n  │ ".join(lines)
            return Text(f"{prefix} [{status}] {out_preview}", style=color)
        elif error:
            return Text(f"{prefix} [{status}] ✗ {error[:200]}", style=color)
        else:
            return Text(f"{prefix} [{status}] (no output)", style=color)

    elif etype == "hypothesis":
        hypothesis = data.get("hypothesis", "")
        return Text(f"{prefix} 🧠 {hypothesis}", style=color)

    elif etype == "flag_candidate":
        flags = data.get("flags", [])
        method = data.get("method", "?")
        return Text(f"{prefix} ⚑ Found candidate: {flags} (via {method})", style="bold #D29922")

    elif etype == "flag_validated":
        flag = data.get("flag", "")
        return Text(f"{prefix} ★ FLAG VALIDATED: {flag}", style="bold #3FB950 on #101725")

    elif etype == "error":
        error = data.get("error", "Unknown error")
        return Text(f"{prefix} ✗ {error}", style="bold #F85149")

    elif etype == "completed":
        solved = data.get("solved", False)
        if solved:
            flag = data.get("flag", "")
            return Text(f"{prefix} ★ CHALLENGE SOLVED! Flag: {flag}", style="bold #3FB950")
        else:
            reason = data.get("reason", "")
            return Text(f"{prefix} ✗ Unsolved: {reason}", style="bold #F85149")

    elif etype == "difficulty":
        diff = data.get("difficulty", "?")
        mins = data.get("estimated_minutes", "?")
        return Text(f"{prefix} Difficulty: {diff} (~{mins}min)", style="#D29922")

    return Text(f"{prefix} {json.dumps(data)[:200]}", style="#E6EDF3")


def format_event(event: dict) -> Text:
    """Format trace events without padded columns or decorative glyphs."""
    etype = event.get("event_type", "unknown")
    agent = event.get("agent", "?")
    data = event.get("data", {})
    ts = event.get("timestamp", "")[11:19] or "--:--:--"

    color = EVENT_COLORS.get(etype, "#E6EDF3")
    prefix = f"[{ts}] [{etype.upper()}] [{agent}]"

    if etype == "classification":
        cat = data.get("category", "?")
        conf = data.get("confidence", 0)
        return Text(f"{prefix} -> {cat} (confidence: {conf:.2f})", style=color)

    if etype == "llm_reasoning":
        raw = data.get("raw_output", "")[:1200]
        reasoning = data.get("reasoning", "")
        error = data.get("error", "")
        if error:
            return Text(f"{prefix} LLM error: {error}", style="bold #F85149")

        parsed, prefix_text = _extract_json(raw)
        if parsed:
            tool = parsed.get("tool", "")
            args = parsed.get("args", {})
            rsn = parsed.get("reasoning", reasoning) or reasoning
            args_str = " ".join(f"{k}={v}" for k, v in args.items() if v)
            lines = []
            if prefix_text:
                lines.append(prefix_text[:200])
            if rsn:
                lines.append(str(rsn))
            if tool:
                lines.append(f"tool {tool} {args_str}".rstrip())
            return Text(f"{prefix} " + "\n  | ".join(lines), style=color)

        return Text(f"{prefix} " + "\n  | ".join(raw.split("\n")[:6]), style=color)

    if etype == "tool_call":
        tool = data.get("tool", "?")
        args = data.get("args", {})
        if isinstance(args, str):
            args = {}
        args_str = " ".join(f"{k}={v}" for k, v in args.items() if v)
        return Text(f"{prefix} tool {tool} {args_str}".rstrip(), style=color)

    if etype == "tool_result":
        success = data.get("success", False)
        output = data.get("output", "")[:400]
        error = data.get("error", "")
        status = "ok" if success else "error"
        if output:
            out_preview = "\n  | ".join(output.split("\n")[:5])
            return Text(f"{prefix} [{status}] {out_preview}", style=color)
        if error:
            return Text(f"{prefix} [{status}] {error[:200]}", style=color)
        return Text(f"{prefix} [{status}] (no output)", style=color)

    if etype == "hypothesis":
        return Text(f"{prefix} {data.get('hypothesis', '')}", style=color)

    if etype == "flag_candidate":
        flags = data.get("flags", [])
        method = data.get("method", "?")
        return Text(f"{prefix} Found candidate: {flags} (via {method})", style="bold #D29922")

    if etype == "flag_validated":
        return Text(f"{prefix} FLAG VALIDATED: {data.get('flag', '')}", style="bold #3FB950 on #101725")

    if etype == "error":
        return Text(f"{prefix} {data.get('error', 'Unknown error')}", style="bold #F85149")

    if etype == "completed":
        if data.get("solved", False):
            return Text(f"{prefix} CHALLENGE SOLVED! Flag: {data.get('flag', '')}", style="bold #3FB950")
        return Text(f"{prefix} Unsolved: {data.get('reason', '')}", style="bold #F85149")

    if etype == "difficulty":
        diff = data.get("difficulty", "?")
        mins = data.get("estimated_minutes", "?")
        return Text(f"{prefix} Difficulty: {diff} (~{mins}min)", style="#D29922")

    return Text(f"{prefix} {json.dumps(data)[:200]}", style="#E6EDF3")


def print_session_table(sessions: list[dict]):
    if not sessions:
        console.print("[#9CA3AF]No sessions[/#9CA3AF]")
        return

    table = Table(box=box.ROUNDED, border_style="#9CA3AF")
    table.add_column("ID", style="#9CA3AF", width=8)
    table.add_column("Status", width=10)
    table.add_column("Category", width=12)
    table.add_column("Iterations", width=10)
    table.add_column("Flag", width=40)

    for s in sessions[-10:]:
        sid = s.get("session_id", "?")[:8]
        status = s.get("status", "?")
        status_style = {"solved": "#3FB950", "running": "#00E5FF", "queued": "#D29922", "failed": "#F85149"}.get(status, "#9CA3AF")
        cat = s.get("category", "?")
        cat_color = DOMAIN_COLORS.get(cat, "#9CA3AF")
        flag = s.get("flag", "") or "—"
        iterations = str(s.get("iteration_count", 0))

        table.add_row(
            sid,
            f"[{status_style}]{status}[/{status_style}]",
            f"[{cat_color}]{cat}[/{cat_color}]",
            iterations,
            f"[#3FB950]{flag}[/#3FB950]" if s.get("flag") else flag,
        )

    console.print(table)


async def generate_challenge_name(description: str) -> str:
    """Generate a short title for a CTF challenge."""
    _name_llm = get_llm("supervisor", temperature=0)
    prompt = f"""
You are naming CTF challenges.

Generate a concise title for the following challenge.

Rules:
- 2-5 words
- Title Case
- No quotes
- No punctuation except hyphens if necessary
- Return ONLY the title

Challenge:
{description[:3000]}
"""

    try:
        response = await _name_llm.ainvoke(prompt)
        return response.content.strip().splitlines()[0]
    except Exception:
        return "Unnamed Challenge"

def print_summary(summary: dict):
    attachments = summary.get("attachments", [])

    attachment_text = (
        ", ".join(a.get("filename", str(a)) for a in attachments)
        if attachments else "None"
    )

    cat = summary.get("category", "Unknown")
    if hasattr(cat, "value"):
        cat = cat.value

    target = summary.get("target_url") or ""
    target_host = summary.get("target_host")
    target_port = summary.get("target_port")
    if not target and target_host and target_port:
        target = f"{target_host}:{target_port}"

    body = (
        f"[bold #E6EDF3]{summary.get('title') or summary.get('name') or 'Untitled'}[/bold #E6EDF3]\n\n"
        f"[#9CA3AF]Category:[/#9CA3AF]      {summary.get('category', 'Unknown')}\n"
        f"[#9CA3AF]Difficulty:[/#9CA3AF]    {summary.get('difficulty', 'Unknown')}\n"
        f"[#9CA3AF]Points:[/#9CA3AF]        {summary.get('points', '-')}\n"
        f"[#9CA3AF]Target:[/#9CA3AF]        {summary.get('target_url', '-')}\n"
        f"[#9CA3AF]Flag Format:[/#9CA3AF]   [#3FB950]{summary.get('flag_format', '-')}[/#3FB950]\n"
        f"[#9CA3AF]Attachments:[/#9CA3AF]   {attachment_text}\n\n"
        f"[bold]Description[/bold]\n"
        f"{summary.get('description', '').strip()}"
    )

    console.print(
        Panel(
            body,
            title="[bold #00E5FF]Challenge Summary[/bold #00E5FF]",
            border_style="#00E5FF",
        )
    )
SUMMARY_FIELDS = [
    ("title", "Title", False),
    ("category", "Category", False),
    ("difficulty", "Difficulty", False),
    ("points", "Points", False),
    ("target_url", "Target URL", False),
    ("flag_format", "Flag Format", False),
    ("description", "Description", True),
]

def edit_summary(summary: dict):
    while True:
        console.print("\n[bold]Editable Fields[/bold]\n")

        for i, (_, label, _) in enumerate(SUMMARY_FIELDS, 1):
            console.print(f"{i}. {label}")

        console.print("0. Done")

        choice = safe_input("> ").strip()

        if choice == "0":
            return

        if not choice.isdigit():
            continue

        idx = int(choice) - 1

        if idx < 0 or idx >= len(SUMMARY_FIELDS):
            continue

        key, label, multiline = SUMMARY_FIELDS[idx]

        console.print(f"\nCurrent {label}:\n")

        print(summary.get(key, ""))

        console.print()

        if multiline:
            value = read_multiline(f"New {label}:")
        else:
            value = safe_input(f"New {label}: ")

        summary[key] = value

def _stdin_has_pending_input() -> bool:
    try:
        return bool(select.select([sys.stdin], [], [], 0)[0])
    except (OSError, ValueError):
        return False


def _read_lines_until_double_blank(read_line, has_pending_input=None) -> str:
    has_pending_input = has_pending_input or (lambda: False)
    lines = []
    blank_count = 0

    while True:
        line = read_line()
        if line is None:
            break

        stripped = line.rstrip("\n\r")
        if stripped == "":
            if has_pending_input():
                if lines:
                    lines.append("")
                blank_count = 0
                continue
            if lines:
                blank_count += 1
                if blank_count >= 2:
                    break
                lines.append("")
            continue

        blank_count = 0
        lines.append(stripped)

    while lines and lines[-1] == "":
        lines.pop()

    return "\n".join(lines)


def read_multiline(prompt=""):
    if prompt:
        print(prompt)
    print("(Finish by pressing Enter twice)\n")

    return _read_lines_until_double_blank(safe_input, _stdin_has_pending_input)

async def cmd_solve(args: str):
    """Solve a CTF challenge"""
    description = args.strip()
    name = ""
    if not description:
        console.print("[#D29922]Paste the challenge description (then press Enter twice):[/#D29922]")
        def read_stdin_line():
            line = sys.stdin.readline()
            if not line:
                return None
            return line

        description = _read_lines_until_double_blank(read_stdin_line, _stdin_has_pending_input)

    if not description.strip():
        console.print("[#F85149]No challenge provided.[/#F85149]")
        return

    if os.path.isfile(description):
        filepath = description
        with open(filepath, "rb") as f:
            content = f.read()
        description = f"Challenge file: {os.path.basename(filepath)}"
        files = [(os.path.basename(filepath), content, "")]
    else:
        files = None
        filepath = None

    flag_format = settings.flag_format or ""
    max_retries = 3
    if flag_format == "" or flag_format.strip().lower() == "none":
        flag_format = safe_input("Error: Flag format not provided. Enter the flag format:")
        set_default_flag_format(flag_format)

    for attempt in range(1, max_retries + 1):
        if attempt > 1:
            console.print(f"\n[bold #D29922]Retry attempt {attempt}/{max_retries}...[/bold #D29922]\n")

        session_id = str(uuid.uuid4())
        console.print("[#9CA3AF]Ingesting challenge...[/#9CA3AF]")
        name = await generate_challenge_name(description)
        manifest = await ingest_challenge(
            name=name,
            description=description,
            upload_dir=settings.upload_dir,
            files=files,
            flag_format=flag_format,
        )

        initial_state = {
            "manifest": manifest.model_dump(),
            "category": "unknown",
            "recommended_toolchain": [],
            "classification_reasoning": "",
            "current_agent": "classify",
            "tool_history": [],
            "observations": [],
            "current_hypothesis": "",
            "iteration_count": 0,
            "candidate_flags": [],
            "final_flag": None,
            "solved": False,
            "failure_reason": None,
            "session_id": session_id,
            "trace_events": [],
            "difficulty": None,
            "mode": "solve",
        }

        await session_store.create(session_id, initial_state)

        m = manifest
        title = m.title or ""
        name = m.name or ""
        desc_first = m.description.strip().split("\n")[0][:1000]
        pts = f"{m.points} pts" if m.points else ""
        auth = ""
        for line in m.description.split("\n"):
            low = line.strip().lower()
            if low.startswith("by "):
                auth = line.strip()[3:]
                break
        cat = initial_state.get("category", "?")
        diff = initial_state.get("difficulty") or "?"
        flag_fmt = m.flag_format or flag_format
        attachments_info = ""
        if m.attachments:
            names = ", ".join(a.filename for a in m.attachments)
            attachments_info = f"\n[#9CA3AF]Attachments:[/#9CA3AF] {names}"
        url_info = f"\n[#9CA3AF]Target:[/#9CA3AF] [#00E5FF]{m.target_url}[/#00E5FF]" if m.target_url else ""
        summary = {
            "title": manifest.title,
            "category": manifest.category,
            "target": manifest.target_url,
            "flag_format": manifest.flag_format or flag_format,
            "description": manifest.description,
        }
        summary = manifest.model_dump()

        while True:
            print_summary(summary)

            console.print(
                "\n[E] Edit Summary    [C] Continue    [Q] Cancel"
            )
            while select.select([sys.stdin], [], [], 0)[0]:
                sys.stdin.readline()
            choice = sys.stdin.readline().strip().lower()

            if choice in ("c", "continue", ""):
                break

            if choice in ("q", "quit"):
                return

            if choice in ("e", "edit"):
                edit_summary(summary)

        manifest = manifest.model_validate(summary)
        initial_state["manifest"] = manifest.model_dump()

        console.print(f"[#00E5FF]Session ID:[/#00E5FF] {session_id}")
        console.print(f"[#9CA3AF]Launching agent... streaming live trace below[/#9CA3AF]\n")

        seen = 0
        solved = False
        final_flag = None
        failure_reason = None

        final_state = None

        try:
            async for state in supervisor_graph.astream(initial_state, stream_mode="values"):
                final_state = state
                new_events = state.get("trace_events", [])[seen:]
                for event in new_events:
                    console.print(format_event(event))
                    seen += 1
                    if event.get("event_type") == "completed":
                        solved = event.get("data", {}).get("solved", False)
                        final_flag = event.get("data", {}).get("flag")
                        failure_reason = event.get("data", {}).get("reason")
                    elif event.get("event_type") == "flag_validated":
                        solved = True
                        final_flag = event.get("data", {}).get("flag")

            if final_state:
                await session_store.update(session_id, {
                    "solved": final_state.get("solved", False),
                    "final_flag": final_state.get("final_flag"),
                    "failure_reason": final_state.get("failure_reason"),
                    "trace_events": final_state.get("trace_events", []),
                    "iteration_count": final_state.get("iteration_count", 0),
                    "category": final_state.get("category"),
                    "current_hypothesis": final_state.get("current_hypothesis"),
                })

            console.print()
            if solved and final_flag:
                iters = final_state.get("iteration_count", 0) if final_state else 0
                console.print(Panel(
                    f"[bold #3FB950]★ FLAG:[/bold #3FB950] [bold #E6EDF3]{final_flag}[/bold #E6EDF3]\n"
                    f"[#9CA3AF]Solved in {iters} iterations[/#9CA3AF]",
                    border_style="#3FB950",
                    title="[bold #3FB950]SOLVED[/bold #3FB950]",
                ))

                valid_prefix = flag_format.split("{")[0] if "{" in flag_format else ""
                if valid_prefix and not final_flag.startswith(valid_prefix + "{"):
                    console.print(f"[#D29922]⚠ Flag does not match expected format [bold]{flag_format}[/bold][/#D29922]")
                elif valid_prefix and final_flag.startswith(valid_prefix + "{"):
                    console.print(f"[#9CA3AF]✓ Flag matches expected format [bold]{flag_format}[/bold][/#9CA3AF]")

                console.print()
                console.print("[bold #00E5FF]Is this flag correct?[/bold #00E5FF]")
                confirm = safe_input("  [y/N] ").strip().lower()
                if confirm in ("y", "yes"):
                    console.print(f"\n[bold #3FB950]✓ Flag confirmed![/bold #3FB950]")
                    return
                else:
                    console.print("[#D29922]Flag rejected — retrying with feedback...[/#D29922]")
                    description += f"\n\n[Previous attempt found flag {final_flag} which was incorrect. Try a different approach.]"
                    continue
            else:
                reason = failure_reason or "No flag found"
                console.print(Panel(
                    f"[bold #F85149]✗ UNSOLVED[/bold #F85149]\n[#9CA3AF]{reason}[/#9CA3AF]",
                    border_style="#F85149",
                    title="[bold #F85149]FAILED[/bold #F85149]",
                ))
                if attempt < max_retries:
                    console.print("[#D29922]Retrying with a fresh attempt...[/#D29922]")
                    description += f"\n\n[Previous attempt failed: {reason}. Try a different approach.]"
                    continue
                break

        except Exception as e:
            from rich.text import Text
            et = Text("Error solving challenge: ", style="bold #F85149")
            et.append(str(e))
            error_console.print(et)
            import traceback
            error_console.print(traceback.format_exc(), style="#9CA3AF")
            if attempt < max_retries:
                description += f"\n\n[Previous attempt failed with error: {e}. Try again.]"
                continue
            return

    console.print("[#9CA3AF]All retries exhausted. Challenge remains unsolved.[/#9CA3AF]")


async def cmd_sessions():
    """List all sessions"""
    sessions = await session_store.list_sessions()
    print_session_table(sessions)


async def cmd_view(session_id: str):
    """View session details"""
    session_id = session_id.strip()
    if not session_id:
        error_console.print("[#F85149]Usage:[/#F85149] view [#00E5FF]<session_id>[/#00E5FF]")
        return

    session = await session_store.get(session_id)
    if not session:
        error_console.print(f"[#F85149]Session not found:[/#F85149] {session_id[:8]}")
        return

    manifest = session.get("manifest", {})
    console.print(Panel(
        f"[bold]Description:[/bold] {manifest.get('description', 'N/A')[:200]}\n"
        f"[bold]Category:[/bold] [{DOMAIN_COLORS.get(session.get('category'), '#9CA3AF')}]{session.get('category', '?')}[/]\n"
        f"[bold]Status:[/bold] {'[#3FB950]SOLVED[/#3FB950]' if session.get('solved') else '[#F85149]FAILED[/#F85149]' if session.get('failure_reason') else '[#00E5FF]RUNNING[/#00E5FF]'}\n"
        f"[bold]Iterations:[/bold] {session.get('iteration_count', 0)}\n"
        f"[bold]Flag:[/bold] [#3FB950]{session.get('final_flag', 'None')}[/#3FB950]\n"
        f"[bold]Hypothesis:[/bold] [#A855F7]{session.get('current_hypothesis', 'N/A')}[/#A855F7]",
        title=f"Session {session_id[:8]}",
        border_style="#00E5FF",
    ))

    events = session.get("trace_events", [])
    if events:
        console.print(f"\n[bold]Trace ({len(events)} events):[/bold]")
        for event in events:
            console.print(format_event(event))


async def cmd_watch(session_id: str):
    """Live-stream agent trace"""
    session_id = session_id.strip()
    if not session_id:
        console.print("[#F85149]Usage: /watch <session_id>[/#F85149]")
        return

    seen = 0
    console.print(f"[#9CA3AF]Watching session {session_id}... (Ctrl+C to stop)[/#9CA3AF]\n")

    try:
        while True:
            session = await session_store.get(session_id)
            if not session:
                console.print("[#F85149]Session not found[/#F85149]")
                break

            events = session.get("trace_events", [])
            new_events = events[seen:]

            for event in new_events:
                console.print(format_event(event))
                seen += 1

                if event.get("event_type") == "completed":
                    console.print("\n[bold #3FB950]Session complete![/bold #3FB950]")
                    return

            if session.get("solved") or session.get("failure_reason"):
                await asyncio.sleep(0.5)
                continue

            await asyncio.sleep(0.3)

    except KeyboardInterrupt:
        console.print("\n[#9CA3AF]Stopped watching[/#9CA3AF]")
    except Exception as e:
        console.print(f"[#F85149]Error: {e}[/#F85149]")


async def cmd_writeup(session_id: str):
    """Generate a writeup for a solved challenge"""
    session_id = session_id.strip()
    if not session_id:
        console.print("[#F85149]Usage: /writeup <session_id>[/#F85149]")
        return

    session = await session_store.get(session_id)
    if not session:
        console.print(f"[#F85149]Session not found: {session_id}[/#F85149]")
        return

    if not session.get("solved"):
        console.print("[#D29922]Challenge not solved yet. Run /solve first.[/#D29922]")
        return

    from backend.core.nim_client import get_nim_llm

    llm = get_nim_llm("supervisor", temperature=0.3)
    manifest = session.get("manifest", {})
    trace_str = json.dumps(session.get("trace_events", []), indent=2)[:4000]

    prompt = (
        "You solved this CTF challenge. Given this agent trace, write a clean step-by-step "
        "write-up in markdown format. Include: challenge description, approach, tools used, "
        "key observations, and the flag. Format it for publication on a CTF blog.\n\n"
        f"Description: {manifest.get('description', '')[:2000]}\n"
        f"Category: {session.get('category', '')}\n"
        f"Flag: {session.get('final_flag', '')}\n"
        f"Agent Trace: {trace_str}\n\n"
        "Write the complete writeup in markdown:\n"
    )

    console.print("[#9CA3AF]Generating writeup...[/#9CA3AF]")
    try:
        response = await llm.ainvoke(prompt)
        writeup = response.content
        console.print(Markdown(writeup))
    except Exception as e:
        console.print(f"[#F85149]Writeup generation failed: {e}[/#F85149]")


async def cmd_benchmark():
    """Run benchmark against known challenges"""
    known_challenges = [
        {
            "description": "Decrypt this: picoCTF{g00d_k1dney_19324}",
        },
        {
            "description": "Can you find the flag? The website at http://mercury.picoctf.net:1773/ has a hidden directory. Use directory enumeration.",
            "known_flag": "",
        },
    ]

    console.print("[bold #D29922]Running benchmark...[/bold #D29922]\n")

    results = []
    for i, challenge in enumerate(known_challenges):
        console.print(f"[#9CA3AF]Challenge {i+1}/{len(known_challenges)}: {challenge['description'][:80]}...[/#9CA3AF]")

        manifest = await ingest_challenge(
            name=challenge["name"],
            description=challenge["description"],
            upload_dir=settings.upload_dir,
        )

        session_id = str(uuid.uuid4())
        initial_state = {
            "manifest": manifest.model_dump(),
            "category": "unknown",
            "recommended_toolchain": [],
            "classification_reasoning": "",
            "current_agent": "classify",
            "tool_history": [],
            "observations": [],
            "current_hypothesis": "",
            "iteration_count": 0,
            "candidate_flags": [],
            "final_flag": None,
            "solved": False,
            "failure_reason": None,
            "session_id": session_id,
            "trace_events": [],
            "difficulty": None,
            "mode": "solve",
        }

        await session_store.create(session_id, initial_state)
        final_state = await supervisor_graph.ainvoke(initial_state)

        solved = final_state.get("solved", False)
        results.append({
            "challenge": challenge["description"][:100],
            "solved": solved,
            "flag": final_state.get("final_flag"),
            "iterations": final_state.get("iteration_count", 0),
            "category": final_state.get("category"),
        })

    table = Table(box=box.ROUNDED, border_style="#9CA3AF", title="Benchmark Results")
    table.add_column("#", width=3)
    table.add_column("Challenge", width=50)
    table.add_column("Category", width=12)
    table.add_column("Solved", width=8)
    table.add_column("Iterations", width=10)
    table.add_column("Flag", width=40)

    for i, r in enumerate(results):
        cat_color = DOMAIN_COLORS.get(r.get("category", ""), "#9CA3AF")
        solved_str = "[#3FB950]✓[/#3FB950]" if r["solved"] else "[#F85149]✗[/#F85149]"
        table.add_row(
            str(i + 1),
            Text(r["challenge"], style="#9CA3AF"),
            f"[{cat_color}]{r.get('category', '?')}[/{cat_color}]",
            solved_str,
            str(r["iterations"]),
            f"[#3FB950]{r['flag']}[/#3FB950]" if r.get("flag") else "[#9CA3AF]—[/#9CA3AF]",
        )

    console.print(table)

    solved_count = sum(1 for r in results if r["solved"])
    console.print(f"\n[bold]Solve rate: {solved_count}/{len(results)} ({solved_count/len(results)*100:.1f}%)[/bold]")

async def cmd_memory(args: str):
    """Use the memory service through its MCP tools."""
    parts = args.strip().split(maxsplit=1)
    subcmd = parts[0].lower() if parts else "help"
    value = parts[1].strip() if len(parts) > 1 else ""

    calls: dict[str, tuple[str, dict]] = {
        "domains": ("list_domains", {}),
    }
    if subcmd == "search":
        if not value:
            console.print("[red]Usage: /memory search <query>[/red]")
            return
        calls[subcmd] = ("search_writeups", {"query": value, "limit": 10})
    elif subcmd == "get":
        try:
            calls[subcmd] = ("get_writeup", {"id": int(value)})
        except ValueError:
            console.print("[red]Usage: /memory get <numeric-id>[/red]")
            return
    elif subcmd == "sources":
        if not value:
            console.print("[red]Usage: /memory sources <query>[/red]")
            return
        calls[subcmd] = ("search_source_documents", {"query": value, "limit": 10})
    elif subcmd == "source":
        try:
            calls[subcmd] = ("get_source_document", {"id": int(value)})
        except ValueError:
            console.print("[red]Usage: /memory source <numeric-id>[/red]")
            return
    elif subcmd == "fetch":
        if not value:
            console.print("[red]Usage: /memory fetch <url>[/red]")
            return
        calls[subcmd] = ("fetch_web_reference", {"url": value})
    elif subcmd not in calls:
        console.print("[yellow]Usage: /memory search|get|domains|sources|source|fetch ...[/yellow]")
        return

    tool_name, arguments = calls[subcmd]
    try:
        result = await memory_client.call_tool(tool_name, arguments)
    except MemoryServiceError as error:
        console.print(f"[red]Memory MCP error: {error}[/red]")
        return
    console.print_json(json.dumps(result, default=str))

async def cmd_experience(args: str):
    """View/manage the experience database"""
    parts = args.strip().split(maxsplit=1)
    subcmd = parts[0].lower() if parts else "list"

    if subcmd == "clear":
        experience_db.clear()
        console.print("[#3FB950]Experience database cleared.[/#3FB950]")
        return

    if subcmd == "find":
        query = parts[1] if len(parts) > 1 else ""
        if not query:
            console.print("[#F85149]Usage: /experience find <query>[/#F85149]")
            return
        results = experience_db.find_similar(query, top_k=10)
        if not results:
            console.print("[#D29922]No similar past challenges found.[/#D29922]")
            return
        table = Table(box=box.ROUNDED, border_style="#9CA3AF", title=f"Similar Past Challenges: '{query}'")
        table.add_column("Category", width=12)
        table.add_column("Similarity", width=10)
        table.add_column("Tools Used", width=30)
        table.add_column("Flag (truncated)", width=40)
        for rec, score in results:
            tools_str = ", ".join(t.get("tool", "?") for t in (rec.tools_used or [])[:3])
            flag_short = rec.final_flag[:40] if rec.final_flag else "—"
            cat_color = DOMAIN_COLORS.get(rec.category, "#9CA3AF")
            table.add_row(
                f"[{cat_color}]{rec.category}[/{cat_color}]",
                f"{score:.2f}",
                tools_str,
                f"[#3FB950]{flag_short}[/#3FB950]",
            )
        console.print(table)
        return

    stats = experience_db.get_stats()
    records = experience_db.records

    if not records:
        console.print("[#D29922]Experience database is empty. Solved challenges will be saved here automatically.[/#D29922]")
        return

    table = Table(box=box.ROUNDED, border_style="#9CA3AF", title=f"Experience Database ({stats['total_records']} records)")
    table.add_column("ID", width=8)
    table.add_column("Category", width=12)
    table.add_column("Tools", width=30)
    table.add_column("Iterations", width=10)
    table.add_column("Flag (truncated)", width=40)
    table.add_column("Date", width=20)

    for rec in reversed(records[-20:]):
        tools_str = ", ".join(t.get("tool", "?") for t in (rec.tools_used or [])[:3])
        flag_short = rec.final_flag[:40] if rec.final_flag else "—"
        cat_color = DOMAIN_COLORS.get(rec.category, "#9CA3AF")
        date_str = rec.created_at[:10] if rec.created_at else "?"
        table.add_row(
            rec.id[:8],
            f"[{cat_color}]{rec.category}[/{cat_color}]",
            tools_str,
            str(rec.iteration_count),
            f"[#3FB950]{flag_short}[/#3FB950]",
            date_str,
        )

    console.print(table)

    cat_breakdown = ", ".join(f"{k}={v}" for k, v in sorted(stats['categories'].items()))
    console.print(f"\n[#9CA3AF]Categories: {cat_breakdown}[/#9CA3AF]")


async def cmd_install(args: str = ""):
    """Install missing system tools (requires sudo). Captures output to avoid garbled display."""
    from backend.core.tool_checker import DOMAIN_TOOLS

    parts = args.strip().split(maxsplit=1)
    filter_domain = parts[0].capitalize() if parts and parts[0] else None

    if filter_domain and filter_domain not in DOMAIN_TOOLS:
        error_console.print(f"[#F85149]Unknown domain:[/#F85149] '{parts[0]}'. Available: {', '.join(DOMAIN_TOOLS.keys())}")
        return

    run_py = Path(__file__).resolve().parent.parent / 'run.py'

    console.print("[#9CA3AF]Installing tools...[/#9CA3AF]")

    from run import run_install_only

    try:
        run_install_only()

        console.print(
            Panel(
                "[#3FB950]✔ Installation complete![/#3FB950]",
                border_style="#3FB950",
            )
        )
    except Exception as e:
        error_console.print(
            Panel(
                f"[#F85149]✗ Installation failed:[/#F85149]\n{e}",
                border_style="#F85149",
            )
        )

    print()  # Separate installer output from the final status.


async def cmd_install(args: str = ""):
    """Install missing system tools with themed terminal status panels."""
    from backend.core.tool_checker import DOMAIN_TOOLS

    parts = args.strip().split(maxsplit=1)
    filter_domain = parts[0].capitalize() if parts and parts[0] else None

    if filter_domain and filter_domain not in DOMAIN_TOOLS:
        error_console.print(terminal_panel(
            f"[#F85149]Unknown domain:[/#F85149] [#E6EDF3]{parts[0]}[/#E6EDF3]\n"
            f"[#9CA3AF]Available:[/#9CA3AF] [#00E5FF]{', '.join(DOMAIN_TOOLS.keys())}[/#00E5FF]\n\n"
            "[#9CA3AF]Usage:[/#9CA3AF] [#E6EDF3]/install[/#E6EDF3] [#A855F7][domain][/#A855F7]",
            "Install Error",
            border_style="#F85149",
        ))
        return

    target = filter_domain or "all domains"
    console.print(terminal_panel(
        f"[#9CA3AF]Target[/#9CA3AF]    : [#E6EDF3]{target}[/#E6EDF3]\n"
        "[#9CA3AF]Installer[/#9CA3AF] : [#00E5FF]system tool bootstrap[/#00E5FF]\n"
        "[#9CA3AF]Status[/#9CA3AF]    : [#A855F7]running[/#A855F7]\n\n"
        "[#9CA3AF]Installer output may appear below while packages are checked or installed.[/#9CA3AF]",
        "Install In Progress",
        border_style="#9CA3AF",
    ))

    from run import run_install_only

    try:
        run_install_only()
        console.print(terminal_panel(
            f"[#9CA3AF]Target[/#9CA3AF] : [#E6EDF3]{target}[/#E6EDF3]\n"
            "[#9CA3AF]Status[/#9CA3AF] : [#3FB950]complete[/#3FB950]\n\n"
            "[#9CA3AF]Run [#E6EDF3]/tools[/#E6EDF3] to refresh availability.[/#9CA3AF]",
            "Install Complete",
            border_style="#3FB950",
        ))
    except Exception as e:
        error_console.print(terminal_panel(
            f"[#9CA3AF]Target[/#9CA3AF] : [#E6EDF3]{target}[/#E6EDF3]\n"
            "[#9CA3AF]Status[/#9CA3AF] : [#F85149]failed[/#F85149]\n\n"
            f"[#F85149]{e}[/#F85149]",
            "Install Failed",
            border_style="#F85149",
        ))

    print()


REPRESENTATIVE_TOOLS = {
    "Web": "curl",
    "Forensics": "strings",
    "Pwn": "python3",
    "RE": "file",
    "Crypto": "openssl",
    "OSINT": "whois",
    "Misc": "screen",
}

async def check_missing_tools():
    """Check for missing tools — spot-check 1 tool per domain for fast startup."""
    import shutil
    from backend.core.tool_checker import DOMAIN_TOOLS

    missing_by_domain = {}
    total_missing = 0
    # First: fast spot-check (1 tool per domain)
    for domain, tool in REPRESENTATIVE_TOOLS.items():
        if not shutil.which(tool):
            missing_by_domain[domain] = [tool]
            total_missing += 1
    # If all rep tools found, skip exhaustive check
    if total_missing == 0:
        return
    # Only if something missing, do full scan
    missing_by_domain = {}
    total_missing = 0
    for domain, tools in DOMAIN_TOOLS.items():
        missing = [t for t in tools if not shutil.which(t)]
        if missing:
            missing_by_domain[domain] = missing
            total_missing += len(missing)

    if total_missing == 0:
        return

    console.print()

    missing_table = Table(show_header=False, box=None, padding=(0, 1, 0, 0), expand=True)
    missing_table.add_column("Prompt", style="#00E5FF", no_wrap=True, width=1)
    missing_table.add_column("Domain", style="#E6EDF3", no_wrap=True)
    missing_table.add_column("Missing Tools", style="#9CA3AF")
    for domain, missing in sorted(missing_by_domain.items()):
        color = DOMAIN_COLORS.get(domain.lower(), "#E6EDF3")
        tools_str = ", ".join(sorted(missing))
        missing_table.add_row(">", f"[{color}]{domain}[/{color}]", tools_str)

    commands = Table(show_header=False, box=None, padding=(0, 1, 0, 0), expand=True)
    commands.add_column("Prompt", style="#00E5FF", no_wrap=True, width=1)
    commands.add_column("Command", style="#E6EDF3", no_wrap=True)
    commands.add_column("Description", style="#9CA3AF")
    commands.add_row(">", "/install", "install all missing tools")
    commands.add_row(">", "/install <domain>", "install one domain")
    commands.add_row(">", "/tools", "refresh tool status")

    grid = Table.grid(expand=True)
    grid.add_column(ratio=2)
    grid.add_column(ratio=1)
    grid.add_row(
        terminal_panel(missing_table, "Affected Domains", border_style="#F85149"),
        terminal_panel(commands, "Recovery Commands", border_style="#9CA3AF"),
    )

    console.print(Panel(
        grid,
        title=f"[bold #F85149]CTF SOLVER // {total_missing} MISSING TOOLS[/bold #F85149]",
        title_align="center",
        border_style="#9CA3AF",
        box=box.ROUNDED,
        padding=(1, 1),
        subtitle="[#9CA3AF]Some solver capabilities may be limited until these tools are installed.[/#9CA3AF]",
        subtitle_align="center",
    ))
    console.print()
    return

    console.print()
    lines = []
    for d, m in sorted(missing_by_domain.items()):
        c = DOMAIN_COLORS.get(d.lower(), "#E6EDF3")
        tools_str = ", ".join(sorted(m))
        lines.append(f"  [{c}]▸ {d}:[/] [#9CA3AF]{tools_str}[/#9CA3AF]")
    body = "\n".join(lines)

    help_table = Table(show_header=False, box=None, padding=(0, 2, 0, 0))
    help_table.add_column("Cmd", style="#3FB950", no_wrap=True)
    help_table.add_column("Desc", style="#9CA3AF")
    help_table.add_row("install", "Install all missing tools (sudo)")
    help_table.add_row("install <domain>", "Install tools for a specific domain")
    help_table.add_row("tools", "Check which tools are available")

    console.print(Panel(
        f"[bold #D29922]{total_missing} tools not installed[/bold #D29922]\n\n{body}\n\n[#9CA3AF]Some functionality may be limited.[/#9CA3AF]",
        border_style="#D29922",
        title="[bold #D29922]⚠ MISSING TOOLS[/bold #D29922]",
    ))
    console.print()


async def cmd_tools(args: str = ""):
    """Check tool availability by domain"""
    from backend.core.tool_checker import (
        check_all_tools, check_domain_tools, get_domain_summary,
        DOMAIN_TOOLS,
    )

    parts = args.strip().split(maxsplit=1)
    filter_domain = parts[0].lower() if parts and parts[0] else None

    if filter_domain:
        # Capitalize first letter for domain match
        domain_key = filter_domain.capitalize()
        if domain_key in DOMAIN_TOOLS:
            tools = await check_domain_tools(domain_key)
            c = DOMAIN_COLORS_ANSI.get(domain_key, "#00E5FF")
            console.print(f"\n[{c}]┌─── [{domain_key}] ({sum(1 for v in tools.values() if v)}/{len(tools)})[/{c}]\n")
            for tool, version in sorted(tools.items()):
                if version:
                    console.print(f"  [{c}]▸[/] [#3FB950]{tool:<18}[/#3FB950] [#9CA3AF]{str(version)[:50]}[/#9CA3AF]")
                else:
                    console.print(f"  [{c}]▸[/] [#F85149]{tool:<18}[/#F85149] [#9CA3AF]not installed[/#9CA3AF]")
            return
        else:
            console.print(f"[#D29922]Unknown domain '{filter_domain}'. Available: {', '.join(DOMAIN_TOOLS.keys())}[/#D29922]")
            return

    # Show all tools grouped by domain
    all_tools = await check_all_tools()
    summary = get_domain_summary()

    for domain, tools in DOMAIN_TOOLS.items():
        s = summary.get(domain, {"found": 0, "total": 0})
        c = DOMAIN_COLORS_ANSI.get(domain, "#00E5FF")
        color = "#3FB950" if s["found"] == s["total"] else "#D29922" if s["found"] > 0 else "#F85149"
        console.print(f"\n[{c}]┌─── [{domain}] ({s['found']}/{s['total']})[/{c}]")

        for tool in tools:
            version = all_tools.get(tool)
            if version:
                console.print(f"  [{c}]▸[/] [#3FB950]{tool:<18}[/#3FB950] [#9CA3AF]{str(version)[:50]}[/#9CA3AF]")
            else:
                console.print(f"  [{c}]▸[/] [#F85149]{tool:<18}[/#F85149] [#9CA3AF]not installed[/#9CA3AF]")

    total_found = sum(v is not None for v in all_tools.values())
    total_all = len(all_tools)
    pct = total_found / total_all * 100 if total_all else 0
    bar_len = 20
    filled = int(pct * bar_len // 100)
    bar = "█" * filled + "░" * (bar_len - filled)
    console.print(f"\n  [#9CA3AF]└─ [{bar}] {pct:.0f}% ({total_found}/{total_all})[/#9CA3AF]")


def cmd_banner():
    """Display the CTF Solver terminal dashboard."""
    intro = Table.grid(padding=(0, 1))
    intro.add_column(justify="left")
    intro.add_row(BANNER)
    intro.add_row("[bold #00E5FF]CTF SOLVER[/bold #00E5FF]  [#9CA3AF]AI ETHICAL HACKING ASSISTANT[/#9CA3AF]")
    intro.add_row("")
    intro.add_row("[#9CA3AF]Version[/#9CA3AF]     : [#E6EDF3]1.0.0[/#E6EDF3]")
    intro.add_row("[#9CA3AF]Workspace[/#9CA3AF]   : [#A855F7]/home/ctf-solver[/#A855F7]")
    intro.add_row("[#9CA3AF]Mode[/#9CA3AF]        : [#3FB950]Interactive[/#3FB950]")
    intro.add_row("[#9CA3AF]Hint[/#9CA3AF]        : type [#00E5FF]/help[/#00E5FF] to view commands")

    status = Table.grid(padding=(0, 1))
    status.add_column()
    status.add_row("[#9CA3AF]* AI Core[/#9CA3AF]        : [#3FB950]configured[/#3FB950]")
    status.add_row("[#9CA3AF]* Knowledge Base[/#9CA3AF] : [#3FB950]loaded[/#3FB950]")
    status.add_row(f"[#9CA3AF]* Flag Format[/#9CA3AF]    : [#A855F7]{settings.flag_format or 'unset'}[/#A855F7]")
    status.add_row(f"[#9CA3AF]* Uploads[/#9CA3AF]        : [#00E5FF]{settings.upload_dir}[/#00E5FF]")
    status.add_row("[#9CA3AF]* Commands[/#9CA3AF]       : [#E6EDF3]/solve, /tools, /sessions, /watch[/#E6EDF3]")

    tips = Table.grid(padding=(0, 1))
    tips.add_column()
    tips.add_row("[#00E5FF]>[/#00E5FF] [#E6EDF3]/solve <desc|file>[/#E6EDF3] [#9CA3AF]start a challenge[/#9CA3AF]")
    tips.add_row("[#00E5FF]>[/#00E5FF] [#E6EDF3]/tools [domain][/#E6EDF3]    [#9CA3AF]check tool availability[/#9CA3AF]")
    tips.add_row("[#00E5FF]>[/#00E5FF] [#E6EDF3]/sessions[/#E6EDF3]          [#9CA3AF]show active sessions[/#9CA3AF]")
    tips.add_row("[#00E5FF]>[/#00E5FF] [#E6EDF3]/watch <id>[/#E6EDF3]        [#9CA3AF]stream a trace[/#9CA3AF]")
    tips.add_row("[#00E5FF]>[/#00E5FF] [#E6EDF3]/clear[/#E6EDF3]             [#9CA3AF]redraw terminal[/#9CA3AF]")

    grid = Table.grid(expand=True)
    grid.add_column(ratio=1)
    grid.add_column(ratio=1)
    grid.add_column(ratio=1)
    grid.add_row(
        terminal_panel(intro, "CTF Solver"),
        terminal_panel(status, "System Status"),
        terminal_panel(tips, "Quick Commands"),
    )

    console.print(Panel(
        grid,
        title="[bold #00E5FF]CTF SOLVER // AI ETHICAL HACKING TERMINAL[/bold #00E5FF]",
        title_align="center",
        border_style="#9CA3AF",
        box=box.ROUNDED,
        padding=(1, 1),
    ))


def read_input_line() -> str | None:
    """Read input with the CTF Solver neon prompt."""
    try:
        first = safe_input(f"{ANSI_CYAN}ctfsolver{ANSI_RESET} {ANSI_PURPLE}~{ANSI_RESET}{ANSI_WHITE} >{ANSI_RESET} ")
    except (EOFError, KeyboardInterrupt):
        return None

    if not first:
        return ""

    lines = [first.strip()]
    pasted = False

    try:
        fd = os.open("/dev/stdin", os.O_RDONLY | os.O_NONBLOCK)
        try:
            raw = os.read(fd, 65536)
            if raw:
                pasted = True
                for raw_line in raw.split(b"\n"):
                    stripped = raw_line.decode("utf-8", errors="replace").strip()
                    if not stripped:
                        break
                    lines.append(stripped)
        finally:
            os.close(fd)
    except (OSError, IOError):
        pass

    if pasted:
        console.print(terminal_panel("\n".join(lines), "Pasted Content", border_style="#9CA3AF"))
        console.print("[#9CA3AF]Add more lines or press [bold]Enter[/bold] twice to execute.[/#9CA3AF]")
        while True:
            sys.stdout.write(f"{ANSI_CYAN}append{ANSI_RESET} {ANSI_PURPLE}~{ANSI_RESET}{ANSI_WHITE} >{ANSI_RESET} ")
            sys.stdout.flush()
            try:
                more = safe_input()
            except (EOFError, KeyboardInterrupt):
                break
            if not more:
                break
            lines.append(more.strip())

    return "\n".join(lines)


async def cmd_flagformat():
    flag_format = safe_input("Enter the new flag format. Enter to skip.")
    if flag_format != "":
        set_default_flag_format(flag_format)


LLM_PROVIDERS = [
    ("nim", "NVIDIA NIM", "NVIDIA_NIM_API_KEYS"),
    ("gemma", "Google AI / Gemma", "GOOGLE_API_KEYS"),
    ("gemini", "Google AI / Gemini", "GOOGLE_API_KEYS"),
]


def _key_count(value: str) -> int:
    return len([key for key in value.split(",") if key.strip() and key.strip() != "your_key_here"])


def _llm_prompt(label: str) -> str:
    return safe_input(f"{ANSI_CYAN}ctfsolver{ANSI_RESET} {ANSI_PURPLE}llm{ANSI_RESET} {label} > ").strip()


async def cmd_llm():
    """Configure LLM provider and API key pools with themed UI."""
    content = ENV_FILE.read_text() if ENV_FILE.exists() else ""
    current = get_env_value(content, "LLM_PROVIDER") or settings.llm_provider or "nim"

    provider_table = Table(show_header=False, box=None, padding=(0, 1, 0, 0), expand=True)
    provider_table.add_column("Index", style="#00E5FF", no_wrap=True, width=3)
    provider_table.add_column("Provider", style="#E6EDF3", no_wrap=True)
    provider_table.add_column("Keys", style="#9CA3AF")
    provider_table.add_column("Status", style="#A855F7", no_wrap=True)

    for index, (provider, label, key_name) in enumerate(LLM_PROVIDERS, start=1):
        key_total = _key_count(get_env_value(content, key_name))
        status = "active" if provider == current else "available"
        provider_table.add_row(
            str(index),
            f"{label} [#9CA3AF]({provider})[/#9CA3AF]",
            f"{key_total} configured",
            status,
        )

    console.print(Panel(
        provider_table,
        title="[bold #00E5FF]CTF SOLVER // LLM CONFIG[/bold #00E5FF]",
        title_align="center",
        border_style="#9CA3AF",
        box=box.ROUNDED,
        padding=(1, 1),
        subtitle="[#9CA3AF]Select a provider number, or press Enter to keep the current provider.[/#9CA3AF]",
        subtitle_align="center",
    ))

    selected = _llm_prompt("provider")
    if selected:
        try:
            provider, label, key_name = LLM_PROVIDERS[int(selected) - 1]
        except (ValueError, IndexError):
            error_console.print(terminal_panel(
                "[#F85149]Invalid provider selection.[/#F85149]\n\n[#9CA3AF]Run [#E6EDF3]/llm[/#E6EDF3] again and choose one of the displayed numbers.[/#9CA3AF]",
                "LLM Config Error",
                border_style="#F85149",
            ))
            return
    else:
        provider, label, key_name = next(
            (item for item in LLM_PROVIDERS if item[0] == current),
            LLM_PROVIDERS[0],
        )

    existing_keys = get_env_value(content, key_name)
    should_update_keys = _key_count(existing_keys) == 0
    if not should_update_keys:
        choice = _llm_prompt(f"update {key_name}? [y/N]").lower()
        should_update_keys = choice in ("y", "yes")

    if should_update_keys:
        keys = _llm_prompt(f"{label} API keys (comma-separated)")
        if not keys:
            error_console.print(terminal_panel(
                f"[#F85149]{key_name} cannot be empty for {label}.[/#F85149]",
                "LLM Config Error",
                border_style="#F85149",
            ))
            return
        content = set_env_value(content, key_name, keys)

    content = set_env_value(content, "LLM_PROVIDER", provider)
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    ENV_FILE.write_text(content)

    os.environ["LLM_PROVIDER"] = provider
    settings.llm_provider = provider
    if key_name == "NVIDIA_NIM_API_KEYS":
        os.environ[key_name] = get_env_value(content, key_name)
        settings.nvidia_nim_api_keys = get_env_value(content, key_name)
    else:
        os.environ[key_name] = get_env_value(content, key_name)
        settings.google_api_keys = get_env_value(content, key_name)

    console.print(terminal_panel(
        f"[#9CA3AF]Provider[/#9CA3AF] : [#E6EDF3]{label}[/#E6EDF3]\n"
        f"[#9CA3AF]Mode[/#9CA3AF]     : [#A855F7]{provider}[/#A855F7]\n"
        f"[#9CA3AF]Key Pool[/#9CA3AF] : [#00E5FF]{key_name}[/#00E5FF] "
        f"[#9CA3AF]({_key_count(get_env_value(content, key_name))} configured)[/#9CA3AF]\n"
        f"[#9CA3AF]Saved[/#9CA3AF]    : [#3FB950]{ENV_FILE}[/#3FB950]",
        "LLM Config Saved",
        border_style="#3FB950",
    ))


def normalize_command(cmd: str, args: str) -> tuple[str, str]:
    """Normalize slash command aliases."""
    cmd = cmd.lstrip("/").lower()

    if cmd == "scan":
        cmd = "solve"
    elif cmd == "history":
        cmd = "sessions"
    elif cmd == "experience_find":
        cmd = "experience"
        args = f"find {args}".strip()
    elif cmd == "experience_clear":
        cmd = "experience"
        args = "clear"
    elif cmd == "install_":
        cmd = "install"

    return cmd, args


async def cmd_chat(args: str):
    """Ask the configured LLM a question without starting a solve session."""
    question = args.strip()
    if not question:
        question = safe_input("Ask CTF Solver: ").strip()
    if not question:
        return

    llm = get_llm("default")
    response = await llm.ainvoke([HumanMessage(content=question)])
    console.print(terminal_panel(response.content, "AI Chat", border_style="#9CA3AF"))


async def run_interactive():
    """Main interactive CLI loop"""
    cmd_banner()
    await check_missing_tools()
    console.print("[#9CA3AF]Type [bold #00E5FF]/help[/bold #00E5FF] for commands.[/#9CA3AF]\n")

    while True:
        try:
            inp = read_input_line()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[#D29922]✗ Interrupted[/#D29922]")
            break

        if inp is None:
            console.print("\n[#9CA3AF]Input closed. Shutting down CTFAgent...[/#9CA3AF]")
            console.print("[#9CA3AF]For Docker CLI usage, run: docker run --rm -it ctfagent[/#9CA3AF]")
            break

        if not inp:
            continue

        parts = inp.split(maxsplit=1)
        raw_cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        if not raw_cmd.startswith("/") and raw_cmd not in ("exit", "quit"):
            await cmd_chat(inp)
            continue

        cmd, args = normalize_command(raw_cmd, args)

        if cmd in ("exit", "quit"):
            console.print("[#9CA3AF]Shutting down CTF Solver...[/#9CA3AF]")
            break

        elif cmd == "help":
            print_help()

        elif cmd == "banner":
            cmd_banner()

        elif cmd == "clear":
            os.system("clear" if os.name == "posix" else "cls")
            cmd_banner()

        elif cmd == "solve":
            await cmd_solve(args)

        elif cmd == "sessions":
            await cmd_sessions()

        elif cmd == "view":
            await cmd_view(args)

        elif cmd == "watch":
            await cmd_watch(args)

        elif cmd == "writeup":
            await cmd_writeup(args)

        elif cmd == "benchmark":
            await cmd_benchmark()

        elif cmd == "tools":
            await cmd_tools(args)

        elif cmd == "install":
            await cmd_install(args)

        elif cmd == "memory":
            await cmd_memory(args)

        elif cmd == "experience":
            await cmd_experience(args)
            
        elif cmd == "flag":
            await cmd_flagformat()

        elif cmd == "/llm":
            content = ENV_FILE.read_text()
            content = configure_llm_keys(content,config=True)
            ENV_FILE.write_text(content)
            export_runtime_env(content)
            refresh_llm_runtime()
            counts = configured_key_counts(content)
            console.print(
                "[green]LLM configuration updated.[/green] "
                f"[dim]Google keys: {counts['google']}, NIM keys: {counts['nim']}[/dim]"
            )

        else:
            console.print(f"[yellow]Command not found: {cmd}[/yellow]")
            console.print("[dim]Type [bold cyan]/help[/bold cyan] for available commands.[/dim]")


def main():
    import asyncio
    setup_terminal()
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    asyncio.run(run_interactive())


if __name__ == "__main__":
    main()
