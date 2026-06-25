#!/usr/bin/env python3
"""
CTFAgent — Autonomous CTF Solving Framework
Interactive CLI (Metasploit-style)
"""

import asyncio
import json
import os
import select
import shutil
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import set_key
from langchain_core.messages import SystemMessage, HumanMessage
from pwnlib.flag.flag import env_file

from backend.core.llm_client import get_llm


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
try:
    import readline
    HISTFILE = os.path.expanduser("~/.ctfagent_history")
    try:
        readline.read_history_file(HISTFILE)
    except FileNotFoundError:
        pass
    import atexit
    atexit.register(lambda: readline.write_history_file(HISTFILE))
except ImportError:
    pass

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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.agents.supervisor import supervisor_graph
from backend.ingestion.ingestor import ingest_challenge
from backend.config.settings import settings
from backend.core.flag_detector import detect_flag, validate_flag
from backend.memory.session_store import session_store
from backend.memory.experience_db import experience_db

BANNER = r"""
[bold cyan]  _____ _______ ______                      _   
 / ____|__   __|  ____/\                   | |  
| |       | |  | |__ /  \   __ _  ___ _ __ | |_ 
| |       | |  |  __/ /\ \ / _` |/ _ \ '_ \| __|
| |____   | |  | | / ____ \ (_| |  __/ | | | |_ 
 \_____|  |_|  |_|/_/    \_\__, |\___|_| |_|\__|
                            __/ |               
                           |___/                 [/bold cyan]"""[1:]

TAGLINE = "[bold cyan]Autonomous CTF Solver  ·  NVIDIA NIM x GEMMA 31B x GEMINI 3.1 Flash Lite  ·  v1.0.0[/bold cyan]"

def print_help():
    """Print categorized help with Rich tables in a Panel."""
    table = Table(show_header=False, box=None, padding=(0, 2, 0, 0))
    table.add_column("Cmd", style="cyan", no_wrap=True)
    table.add_column("Args", style="dim", no_wrap=True)
    table.add_column("Description")

    help_items = [
        ("[green]CHALLENGES[/green]", "", ""),
        ("/solve", "<desc|file>", "Submit a CTF challenge to solve"),
        ("/sessions", "", "List all active sessions"),
        ("/view", "<id>", "View session details and trace"),
        ("/watch", "<id>", "Live-stream agent reasoning trace"),
        ("/writeup", "<id>", "Generate writeup for solved challenge"),
        ("/benchmark", "", "Run benchmark against known challenges"),
        ("", "", ""),
        ("[green]EXPERIENCE[/green]", "", ""),
        ("/experience", "", "View/manage experience database"),
        ("/experience_find", "<query>", "Search similar past challenges"),
        ("/experience_clear", "", "Clear all experiences"),
        ("", "", ""),
        ("[green]TOOLS[/green]", "", ""),
        ("/tools", "", "Check all available security tools"),
        ("/tools", "<domain>", "Check tools for a domain (web, pwn, etc.)"),
        ("/install", "", "Install missing system tools (sudo)"),
        ("/install_", "<domain>", "Install tools for a specific domain"),
        ("", "", ""),
        ("[green]SYSTEM[/green]", "", ""),
        ("/banner", "", "Display the banner"),
        ("/clear", "", "Clear the screen"),
        ("/help", "", "Show this help message"),
        ("exit / quit", "", "Exit CTFAgent"),
    ]
    for cmd, arg, desc in help_items:
        table.add_row(cmd, arg, desc)

    examples = Table(show_header=False, box=None, padding=(0, 2, 0, 0))
    examples.add_column("", style="dim")
    examples.add_row("[bold yellow]Examples:[/bold yellow]")
    examples.add_row('solve "The challenge has a login form at http://target.com"')
    examples.add_row("solve ./challenge.elf")
    examples.add_row("watch <session_id>")

    console.print(Panel(table, border_style="dim", title="[bold]Commands[/bold]", title_align="left"))
    console.print(Panel(examples, border_style="dim", title="[bold]Examples[/bold]", title_align="left"))


DOMAIN_COLORS = {
    "web": "cyan",
    "crypto": "yellow",
    "forensics": "blue",
    "pwn": "red",
    "re": "magenta",
    "osint": "orange1",
    "misc": "green",
    "unknown": "dim",
}

DOMAIN_COLORS_ANSI = {
    "Web": "cyan", "Forensics": "blue", "Pwn": "red",
    "RE": "magenta", "Crypto": "yellow", "OSINT": "orange1", "Misc": "green",
}

EVENT_COLORS = {
    "classification": "bold cyan",
    "llm_reasoning": "bold cyan",
    "tool_call": "bold green",
    "tool_result": "white",
    "hypothesis": "bold purple",
    "flag_candidate": "bold yellow",
    "flag_validated": "bold green on black",
    "error": "bold red",
    "completed": "bold green",
    "difficulty": "dim yellow",
}


def format_event(event: dict) -> Text:
    etype = event.get("event_type", "unknown")
    agent = event.get("agent", "?")
    data = event.get("data", {})
    ts = event.get("timestamp", "")[11:19]

    color = EVENT_COLORS.get(etype, "white")
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
            return Text(f"{prefix} ⚠ LLM error: {error}", style="bold red")
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
        return Text(f"{prefix} ⚑ Found candidate: {flags} (via {method})", style="bold yellow")

    elif etype == "flag_validated":
        flag = data.get("flag", "")
        return Text(f"{prefix} ★ FLAG VALIDATED: {flag}", style="bold green on black")

    elif etype == "error":
        error = data.get("error", "Unknown error")
        return Text(f"{prefix} ✗ {error}", style="bold red")

    elif etype == "completed":
        solved = data.get("solved", False)
        if solved:
            flag = data.get("flag", "")
            return Text(f"{prefix} ★ CHALLENGE SOLVED! Flag: {flag}", style="bold green")
        else:
            reason = data.get("reason", "")
            return Text(f"{prefix} ✗ Unsolved: {reason}", style="bold red")

    elif etype == "difficulty":
        diff = data.get("difficulty", "?")
        mins = data.get("estimated_minutes", "?")
        return Text(f"{prefix} Difficulty: {diff} (~{mins}min)", style="dim yellow")

    return Text(f"{prefix} {json.dumps(data)[:200]}", style="white")


def print_session_table(sessions: list[dict]):
    if not sessions:
        console.print("[dim]No sessions[/dim]")
        return

    table = Table(box=box.ROUNDED, border_style="dim")
    table.add_column("ID", style="dim", width=8)
    table.add_column("Status", width=10)
    table.add_column("Category", width=12)
    table.add_column("Iterations", width=10)
    table.add_column("Flag", width=40)

    for s in sessions[-10:]:
        sid = s.get("session_id", "?")[:8]
        status = s.get("status", "?")
        status_style = {"solved": "green", "running": "cyan", "queued": "yellow", "failed": "red"}.get(status, "dim")
        cat = s.get("category", "?")
        cat_color = DOMAIN_COLORS.get(cat, "dim")
        flag = s.get("flag", "") or "—"
        iterations = str(s.get("iteration_count", 0))

        table.add_row(
            sid,
            f"[{status_style}]{status}[/{status_style}]",
            f"[{cat_color}]{cat}[/{cat_color}]",
            iterations,
            f"[green]{flag}[/green]" if s.get("flag") else flag,
        )

    console.print(table)


async def cmd_solve(args: str):
    """Solve a CTF challenge"""
    description = args.strip()

    if not description:
        console.print("[yellow]Paste the challenge description (then press Enter twice):[/yellow]")
        desc_lines = []
        while True:
            line = sys.stdin.readline()
            if not line:
                break
            stripped = line.rstrip("\n\r")
            if stripped == "" and desc_lines:
                break
            desc_lines.append(stripped)
        description = "\n".join(desc_lines)

    if not description.strip():
        console.print("[red]No challenge provided.[/red]")
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

    for attempt in range(1, max_retries + 1):
        if attempt > 1:
            console.print(f"\n[bold yellow]Retry attempt {attempt}/{max_retries}...[/bold yellow]\n")

        session_id = str(uuid.uuid4())
        console.print("[dim]Ingesting challenge...[/dim]")

        manifest = await ingest_challenge(
            description=description,
            upload_dir=settings.upload_dir,
            files=files,
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

        console.print()
        m = manifest
        title = m.title or ""
        desc_first = m.description.strip().split("\n")[0][:100]
        pts = f"{m.points} pts" if m.points else ""
        auth = ""
        for line in m.description.split("\n"):
            low = line.strip().lower()
            if low.startswith("by "):
                auth = line.strip()[3:]
                break
        cat = initial_state.get("category", "?")
        diff = initial_state.get("difficulty") or "?"
        flag_fmt = m.flag_format or settings.flag_format or ""
        attachments_info = ""
        if m.attachments:
            names = ", ".join(a.filename for a in m.attachments)
            attachments_info = f"\n[dim]Attachments:[/dim] {names}"
        url_info = f"\n[dim]Target:[/dim] [cyan]{m.target_url}[/cyan]" if m.target_url else ""
        console.print(Panel(
            f"[bold white]{title or desc_first}[/bold white]\n"
            f"{'[dim]by ' + auth + '[/dim]' if auth else ''}"
            f"{'  ' + pts if pts else ''}"
            f"\n"
            f"[dim]Domain:[/dim] {cat}  [dim]Difficulty:[/dim] {diff}\n"
            f"[dim]Flag format:[/dim] [green]{flag_fmt}[/green]"
            f"{attachments_info}"
            f"{url_info}",
            border_style="cyan",
            title="[bold]Challenge Summary[/bold]",
        ))
        console.print(f"[cyan]Session ID:[/cyan] {session_id}")
        console.print(f"[dim]Launching agent... streaming live trace below[/dim]\n")

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
                    f"[bold green]★ FLAG:[/bold green] [bold white]{final_flag}[/bold white]\n"
                    f"[dim]Solved in {iters} iterations[/dim]",
                    border_style="green",
                    title="[bold green]SOLVED[/bold green]",
                ))

                valid_prefix = flag_format.split("{")[0] if "{" in flag_format else ""
                if valid_prefix and not final_flag.startswith(valid_prefix + "{"):
                    console.print(f"[yellow]⚠ Flag does not match expected format [bold]{flag_format}[/bold][/yellow]")
                elif valid_prefix and final_flag.startswith(valid_prefix + "{"):
                    console.print(f"[dim]✓ Flag matches expected format [bold]{flag_format}[/bold][/dim]")

                console.print()
                console.print("[bold cyan]Is this flag correct?[/bold cyan]")
                confirm = input("  [y/N] ").strip().lower()
                if confirm in ("y", "yes"):
                    console.print(f"\n[bold green]✓ Flag confirmed![/bold green]")
                    return
                else:
                    console.print("[yellow]Flag rejected — retrying with feedback...[/yellow]")
                    description += f"\n\n[Previous attempt found flag {final_flag} which was incorrect. Try a different approach.]"
                    continue
            else:
                reason = failure_reason or "No flag found"
                console.print(Panel(
                    f"[bold red]✗ UNSOLVED[/bold red]\n[dim]{reason}[/dim]",
                    border_style="red",
                    title="[bold red]FAILED[/bold red]",
                ))
                if attempt < max_retries:
                    console.print("[yellow]Retrying with a fresh attempt...[/yellow]")
                break

        except Exception as e:
            from rich.text import Text
            et = Text("Error solving challenge: ", style="bold red")
            et.append(str(e))
            error_console.print(et)
            import traceback
            error_console.print(traceback.format_exc(), style="dim")
            if attempt < max_retries:
                description += f"\n\n[Previous attempt failed with error: {e}. Try again.]"
                continue
            return

    console.print("[dim]All retries exhausted. Challenge remains unsolved.[/dim]")


async def cmd_sessions():
    """List all sessions"""
    sessions = await session_store.list_sessions()
    print_session_table(sessions)


async def cmd_view(session_id: str):
    """View session details"""
    session_id = session_id.strip()
    if not session_id:
        error_console.print("[red]Usage:[/red] view [cyan]<session_id>[/cyan]")
        return

    session = await session_store.get(session_id)
    if not session:
        error_console.print(f"[red]Session not found:[/red] {session_id[:8]}")
        return

    manifest = session.get("manifest", {})
    console.print(Panel(
        f"[bold]Description:[/bold] {manifest.get('description', 'N/A')[:200]}\n"
        f"[bold]Category:[/bold] [{DOMAIN_COLORS.get(session.get('category'), 'dim')}]{session.get('category', '?')}[/]\n"
        f"[bold]Status:[/bold] {'[green]SOLVED[/green]' if session.get('solved') else '[red]FAILED[/red]' if session.get('failure_reason') else '[cyan]RUNNING[/cyan]'}\n"
        f"[bold]Iterations:[/bold] {session.get('iteration_count', 0)}\n"
        f"[bold]Flag:[/bold] [green]{session.get('final_flag', 'None')}[/green]\n"
        f"[bold]Hypothesis:[/bold] [purple]{session.get('current_hypothesis', 'N/A')}[/purple]",
        title=f"Session {session_id[:8]}",
        border_style="cyan",
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
        console.print("[red]Usage: watch <session_id>[/red]")
        return

    seen = 0
    console.print(f"[dim]Watching session {session_id}... (Ctrl+C to stop)[/dim]\n")

    try:
        while True:
            session = await session_store.get(session_id)
            if not session:
                console.print("[red]Session not found[/red]")
                break

            events = session.get("trace_events", [])
            new_events = events[seen:]

            for event in new_events:
                console.print(format_event(event))
                seen += 1

                if event.get("event_type") == "completed":
                    console.print("\n[bold green]Session complete![/bold green]")
                    return

            if session.get("solved") or session.get("failure_reason"):
                await asyncio.sleep(0.5)
                continue

            await asyncio.sleep(0.3)

    except KeyboardInterrupt:
        console.print("\n[dim]Stopped watching[/dim]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


async def cmd_writeup(session_id: str):
    """Generate a writeup for a solved challenge"""
    session_id = session_id.strip()
    if not session_id:
        console.print("[red]Usage: writeup <session_id>[/red]")
        return

    session = await session_store.get(session_id)
    if not session:
        console.print(f"[red]Session not found: {session_id}[/red]")
        return

    if not session.get("solved"):
        console.print("[yellow]Challenge not solved yet. Run solve first.[/yellow]")
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

    console.print("[dim]Generating writeup...[/dim]")
    try:
        response = await llm.ainvoke(prompt)
        writeup = response.content
        console.print(Markdown(writeup))
    except Exception as e:
        console.print(f"[red]Writeup generation failed: {e}[/red]")


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

    console.print("[bold yellow]Running benchmark...[/bold yellow]\n")

    results = []
    for i, challenge in enumerate(known_challenges):
        console.print(f"[dim]Challenge {i+1}/{len(known_challenges)}: {challenge['description'][:80]}...[/dim]")

        manifest = await ingest_challenge(
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

    table = Table(box=box.ROUNDED, border_style="dim", title="Benchmark Results")
    table.add_column("#", width=3)
    table.add_column("Challenge", width=50)
    table.add_column("Category", width=12)
    table.add_column("Solved", width=8)
    table.add_column("Iterations", width=10)
    table.add_column("Flag", width=40)

    for i, r in enumerate(results):
        cat_color = DOMAIN_COLORS.get(r.get("category", ""), "dim")
        solved_str = "[green]✓[/green]" if r["solved"] else "[red]✗[/red]"
        table.add_row(
            str(i + 1),
            Text(r["challenge"], style="dim"),
            f"[{cat_color}]{r.get('category', '?')}[/{cat_color}]",
            solved_str,
            str(r["iterations"]),
            f"[green]{r['flag']}[/green]" if r.get("flag") else "[dim]—[/dim]",
        )

    console.print(table)

    solved_count = sum(1 for r in results if r["solved"])
    console.print(f"\n[bold]Solve rate: {solved_count}/{len(results)} ({solved_count/len(results)*100:.1f}%)[/bold]")


async def cmd_experience(args: str):
    """View/manage the experience database"""
    parts = args.strip().split(maxsplit=1)
    subcmd = parts[0].lower() if parts else "list"

    if subcmd == "clear":
        experience_db.clear()
        console.print("[green]Experience database cleared.[/green]")
        return

    if subcmd == "find":
        query = parts[1] if len(parts) > 1 else ""
        if not query:
            console.print("[red]Usage: experience find <query>[/red]")
            return
        results = experience_db.find_similar(query, top_k=10)
        if not results:
            console.print("[yellow]No similar past challenges found.[/yellow]")
            return
        table = Table(box=box.ROUNDED, border_style="dim", title=f"Similar Past Challenges: '{query}'")
        table.add_column("Category", width=12)
        table.add_column("Similarity", width=10)
        table.add_column("Tools Used", width=30)
        table.add_column("Flag (truncated)", width=40)
        for rec, score in results:
            tools_str = ", ".join(t.get("tool", "?") for t in (rec.tools_used or [])[:3])
            flag_short = rec.final_flag[:40] if rec.final_flag else "—"
            cat_color = DOMAIN_COLORS.get(rec.category, "dim")
            table.add_row(
                f"[{cat_color}]{rec.category}[/{cat_color}]",
                f"{score:.2f}",
                tools_str,
                f"[green]{flag_short}[/green]",
            )
        console.print(table)
        return

    stats = experience_db.get_stats()
    records = experience_db.records

    if not records:
        console.print("[yellow]Experience database is empty. Solved challenges will be saved here automatically.[/yellow]")
        return

    table = Table(box=box.ROUNDED, border_style="dim", title=f"Experience Database ({stats['total_records']} records)")
    table.add_column("ID", width=8)
    table.add_column("Category", width=12)
    table.add_column("Tools", width=30)
    table.add_column("Iterations", width=10)
    table.add_column("Flag (truncated)", width=40)
    table.add_column("Date", width=20)

    for rec in reversed(records[-20:]):
        tools_str = ", ".join(t.get("tool", "?") for t in (rec.tools_used or [])[:3])
        flag_short = rec.final_flag[:40] if rec.final_flag else "—"
        cat_color = DOMAIN_COLORS.get(rec.category, "dim")
        date_str = rec.created_at[:10] if rec.created_at else "?"
        table.add_row(
            rec.id[:8],
            f"[{cat_color}]{rec.category}[/{cat_color}]",
            tools_str,
            str(rec.iteration_count),
            f"[green]{flag_short}[/green]",
            date_str,
        )

    console.print(table)

    cat_breakdown = ", ".join(f"{k}={v}" for k, v in sorted(stats['categories'].items()))
    console.print(f"\n[dim]Categories: {cat_breakdown}[/dim]")


async def cmd_install(args: str = ""):
    """Install missing system tools (requires sudo). Captures output to avoid garbled display."""
    from backend.core.tool_checker import DOMAIN_TOOLS

    parts = args.strip().split(maxsplit=1)
    filter_domain = parts[0].capitalize() if parts and parts[0] else None

    if filter_domain and filter_domain not in DOMAIN_TOOLS:
        error_console.print(f"[red]Unknown domain:[/red] '{parts[0]}'. Available: {', '.join(DOMAIN_TOOLS.keys())}")
        return

    run_py = Path(__file__).resolve().parent.parent / 'run.py'

    console.print("[dim]Installing tools (captured output)...[/dim]")

    def _run_install():
        import subprocess as sp
        if os.geteuid() == 0:
            cmd = [sys.executable, str(run_py), '--install-only']
        elif shutil.which('sudo'):
            cmd = ['sudo', sys.executable, str(run_py), '--install-only']
        else:
            error_console.print("[red]Root privileges required.[/red] Run: [bold]sudo python3 run.py[/bold]")
            return None
        result = sp.run(cmd, capture_output=True, text=True, timeout=300)
        return result

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _run_install)

    if result is None:
        return

    if result.stdout:
        console.print(Panel(result.stdout[-1500:], border_style="dim", title="Installer Log"))
    if result.stderr:
        error_console.print(Panel(result.stderr[-500:], border_style="red", title="Errors"))

    if result.returncode == 0:
        console.print(Panel("[green]✔ Installation complete![/green]", border_style="green"))
    else:
        error_console.print(Panel(f"[red]✗ Installation exited with code {result.returncode}[/red]", border_style="red"))


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
    lines = []
    for d, m in sorted(missing_by_domain.items()):
        c = DOMAIN_COLORS.get(d.lower(), "white")
        tools_str = ", ".join(sorted(m))
        lines.append(f"  [{c}]▸ {d}:[/] [dim]{tools_str}[/dim]")
    body = "\n".join(lines)

    help_table = Table(show_header=False, box=None, padding=(0, 2, 0, 0))
    help_table.add_column("Cmd", style="green", no_wrap=True)
    help_table.add_column("Desc", style="dim")
    help_table.add_row("install", "Install all missing tools (sudo)")
    help_table.add_row("install <domain>", "Install tools for a specific domain")
    help_table.add_row("tools", "Check which tools are available")

    console.print(Panel(
        f"[bold yellow]{total_missing} tools not installed[/bold yellow]\n\n{body}\n\n[dim]Some functionality may be limited.[/dim]",
        border_style="yellow",
        title="[bold yellow]⚠ MISSING TOOLS[/bold yellow]",
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
            c = DOMAIN_COLORS_ANSI.get(domain_key, "cyan")
            console.print(f"\n[{c}]┌─── [{domain_key}] ({sum(1 for v in tools.values() if v)}/{len(tools)})[/{c}]\n")
            for tool, version in sorted(tools.items()):
                if version:
                    console.print(f"  [{c}]▸[/] [green]{tool:<18}[/green] [dim]{str(version)[:50]}[/dim]")
                else:
                    console.print(f"  [{c}]▸[/] [red]{tool:<18}[/red] [dim]not installed[/dim]")
            return
        else:
            console.print(f"[yellow]Unknown domain '{filter_domain}'. Available: {', '.join(DOMAIN_TOOLS.keys())}[/yellow]")
            return

    # Show all tools grouped by domain
    all_tools = await check_all_tools()
    summary = get_domain_summary()

    for domain, tools in DOMAIN_TOOLS.items():
        s = summary.get(domain, {"found": 0, "total": 0})
        c = DOMAIN_COLORS_ANSI.get(domain, "cyan")
        color = "green" if s["found"] == s["total"] else "yellow" if s["found"] > 0 else "red"
        console.print(f"\n[{c}]┌─── [{domain}] ({s['found']}/{s['total']})[/{c}]")

        for tool in tools:
            version = all_tools.get(tool)
            if version:
                console.print(f"  [{c}]▸[/] [green]{tool:<18}[/green] [dim]{str(version)[:50]}[/dim]")
            else:
                console.print(f"  [{c}]▸[/] [red]{tool:<18}[/red] [dim]not installed[/dim]")

    total_found = sum(v is not None for v in all_tools.values())
    total_all = len(all_tools)
    pct = total_found / total_all * 100 if total_all else 0
    bar_len = 20
    filled = int(pct * bar_len // 100)
    bar = "█" * filled + "░" * (bar_len - filled)
    console.print(f"\n  [dim]└─ [{bar}] {pct:.0f}% ({total_found}/{total_all})[/dim]")


def cmd_banner():
    """Display banner in a clean panel"""
    console.print(Panel(BANNER, border_style="green", subtitle=TAGLINE, subtitle_align="center"))


def read_input_line() -> str:
    """Read input — single line or multi-line paste with append support."""
    sys.stdout.write("\033[32m┃ ctfagent\033[0m\033[1m >\033[0m ")
    sys.stdout.flush()

    try:
        first = input()
    except (EOFError, KeyboardInterrupt):
        return ""

    if not first:
        return ""

    lines = [first.strip()]
    pasted = False

    # Bypass GNU readline's internal buffer by reading directly from a raw fd.
    # input()/readline reads ahead and may consume paste data into its own
    # buffer, making it invisible to select.select on sys.stdin.
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
        console.print(Panel(
            "\n".join(lines),
            border_style="dim",
            title="Pasted content",
        ))
        console.print("[dim]Add more lines or press [bold]Enter[/bold] twice to execute.[/dim]")
        while True:
            sys.stdout.write("\033[32m┃ append\033[0m\033[1m >\033[0m ")
            sys.stdout.flush()
            try:
                more = input()
            except (EOFError, KeyboardInterrupt):
                break
            if not more:
                break
            lines.append(more.strip())

    return "\n".join(lines)


async def cmd_flagformat():
    flag_format = input("Enter the new flag format. Enter to skip.")
    if flag_format != "":
        set_key(env_file,"FLAG_FORMAT",flag_format)


async def run_interactive():
    """Main interactive CLI loop"""
    cmd_banner()
    await check_missing_tools()
    console.print("[dim]Type [bold cyan]help[/bold cyan] for available commands. [bold cyan]exit[/bold cyan] to quit.[/dim]\n")

    while True:
        try:
            inp = read_input_line()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]✗ Interrupted[/yellow]")
            break

        if not inp:
            continue

        parts = inp.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd in ("/exit", "/quit"):
            console.print("[dim]Shutting down CTFAgent...[/dim]")
            break

        elif cmd == "/help":
            print_help()

        elif cmd == "/banner":
            cmd_banner()

        elif cmd == "/clear":
            os.system("clear" if os.name == "posix" else "cls")
            cmd_banner()

        elif cmd == "/solve":
            await cmd_solve(args)

        elif cmd == "/sessions":
            await cmd_sessions()

        elif cmd == "/view":
            await cmd_view(args)

        elif cmd == "/watch":
            await cmd_watch(args)

        elif cmd == "/writeup":
            await cmd_writeup(args)

        elif cmd == "/benchmark":
            await cmd_benchmark()

        elif cmd == "/tools":
            await cmd_tools(args)

        elif cmd == "/install":
            await cmd_install(args)

        elif cmd == "/experience":
            await cmd_experience(args)
            
        elif cmd == "/flagformat":
            await cmd_flagformat()

        else:
            from rich.text import Text
            llm = get_llm("default")
            response = await llm.ainvoke([
                HumanMessage(content=cmd)
            ])
            print(response.content)
            console.print("Use /help", style="bold cyan")
            console.print(" for available commands.", style="red")


def main():
    import asyncio
    asyncio.run(run_interactive())


if __name__ == "__main__":
    main()
