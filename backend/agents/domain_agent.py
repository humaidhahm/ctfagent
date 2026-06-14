import json
import inspect
from datetime import datetime, timezone
from typing import Optional
from loguru import logger

from backend.core.nim_client import get_nim_llm
from backend.core.state import AgentState
from backend.core.flag_detector import detect_flag, validate_flag
from backend.agents.tool_registry import get_tool
from backend.memory.experience_db import experience_db


# Maps common LLM-invented argument names to actual tool parameter names.
# The LLM often uses short flags (-i, -f, -v) or generic names (input, data)
# instead of the actual Python parameter names in tool definitions.
_ARG_ALIASES: dict[str, str] = {
    # File path aliases
    "input": "filepath", "filename": "filepath", "path": "filepath",
    "file": "filepath", "source": "filepath", "target": "filepath",
    "i": "filepath", "f": "filepath", "p": "filepath",
    "binary": "binary_path",
    "send_data": "input_data",
    "args": "arguments", "cmd": "command", "command": "payload",
    "script": "exploit_script", "exploit": "exploit_script",
    "host": "target_host", "server": "target_host",
    "port": "target_port", "dst_port": "target_port",
    "output": "output_file",
    # Download aliases
    "download_url": "url", "source_url": "url",
    "out_dir": "output_dir", "dest": "output_dir",
    "save_to": "output_dir", "target_dir": "output_dir",
    # URL aliases
    "link": "url", "uri": "url", "endpoint": "url",
    "target_url": "url", "site": "url", "address": "url",
    # Cipher aliases
    "encrypted": "ciphertext", "enc": "ciphertext",
    "ct": "ciphertext", "encoded": "text",
    "type": "cipher_type", "algo": "cipher_type",
    "algorithm": "cipher_type",
    # Wordlist aliases
    "dict": "wordlist", "dictionary": "wordlist",
    "wl": "wordlist", "word_list": "wordlist",
    # RSA aliases
    "modulus": "n", "mod": "n", "N": "n",
    "pub_exp": "e", "exponent": "e", "E": "e",
    "cipher": "c", "C": "c",
    "prime1": "p", "prime2": "q", "P": "p", "Q": "q",
}


def _normalize_tool_args(tool_name: str, raw_args: dict) -> dict:
    """Normalize LLM-generated arg names and strip unknowns."""
    # Parse string args (LLM sometimes emits "args": "{}" or "args": '{"key": "val"}')
    if isinstance(raw_args, str):
        s = raw_args.strip()
        if s.startswith("{"):
            try:
                raw_args = json.loads(s)
            except json.JSONDecodeError:
                raw_args = {}
        else:
            raw_args = {}

    # Strip CLI-flag-like keys (exiftool -a -g -s, etc.) — none of our tools use dash-prefixed names
    raw_args = {k: v for k, v in raw_args.items() if not k.startswith("-")}

    # Strip keys whose values are also the key name (indicates LLM got confused)
    raw_args = {k: v for k, v in raw_args.items() if str(v) != k}

    # Limit to a reasonable number of args
    if len(raw_args) > 10:
        raw_args = dict(list(raw_args.items())[:10])

    # Apply alias mapping
    for alias, target in _ARG_ALIASES.items():
        if alias in raw_args and target not in raw_args:
            raw_args[target] = raw_args.pop(alias)

    # Convert dict-valued `data` to URL-encoded string (LLM often passes
    # {"content": "{{7*7}}"} instead of "content={{7*7}}")
    if isinstance(raw_args.get("data"), dict):
        import urllib.parse
        raw_args["data"] = urllib.parse.urlencode(raw_args["data"])

    return raw_args


import re

_JSON_IN_BACKTICKS = re.compile(
    r"```(?:json|JSON)?\s*\n?(\{.*?\}|\[.*?\])\s*\n?```",
    re.DOTALL,
)


def _extract_first_json(text: str) -> str:
    """Extract the first complete JSON object from text (handles markdown and trailing NL)."""
    # First try to find JSON inside markdown code fences
    m = _JSON_IN_BACKTICKS.search(text)
    if m:
        return m.group(1).strip()
    # Fallback: find the first naked { and bracket-match it
    text = text.strip()
    start = text.find("{")
    if start < 0:
        return text
    depth = 0
    in_str = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == '"' and not escaped:
            in_str = not in_str
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return text


def _filter_tool_args(tool_instance, args: dict) -> dict:
    """Keep only kwargs the tool's run() method actually accepts."""
    try:
        sig = inspect.signature(tool_instance.run)
        valid = set(sig.parameters.keys()) - {"self"}
        has_kwargs = any(
            p.kind == inspect.Parameter.VAR_KEYWORD
            for p in sig.parameters.values()
        )
        if has_kwargs:
            return args  # **kwargs means anything goes
        return {k: v for k, v in args.items() if k in valid}
    except (ValueError, TypeError):
        return args


NODE_NAME_MAP = {
    "web": "web_agent",
    "crypto": "crypto_agent",
    "forensics": "forensics_agent",
    "pwn": "pwn_agent",
    "re": "re_agent",
    "misc": "misc_agent",
    "osint": "misc_agent",
}


async def run_domain_agent(
    state: AgentState,
    agent_name: str,
    system_prompt: str,
    available_tools: list[str],
) -> dict:
    node_name = NODE_NAME_MAP.get(agent_name, agent_name)
    llm = get_nim_llm(agent_name)

    manifest = state.get("manifest", {})
    description = manifest.get("description", "")
    category = state.get("category", "unknown")
    target_url = manifest.get("target_url")
    target_host = manifest.get("target_host")
    target_port = manifest.get("target_port")
    tool_history = state.get("tool_history", [])
    observations = state.get("observations", [])
    current_hypothesis = state.get("current_hypothesis", "No hypothesis yet")
    iteration = state.get("iteration_count", 0)
    mode = state.get("mode", "solve")
    solved = state.get("solved", False)

    if solved:
        return {"current_agent": "flag_validation"}

    if iteration >= 20:
        reason = f"Max iterations ({20}) reached without solving"
        # Trim tool_history to avoid unbounded memory
        state["tool_history"] = state.get("tool_history", [])[-20:]
        logger.warning(f"Session {state.get('session_id')}: {reason}")
        return {
            "current_agent": "flag_validation",
            "failure_reason": reason,
            "trace_events": [{
                "event_type": "error",
                "agent": agent_name,
                "data": {"error": reason},
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "iteration": iteration,
            }],
        }

    attachments = manifest.get("attachments", [])
    challenge_context = f"Description: {description}\nCategory: {category}\n"
    if target_url:
        challenge_context += f"Target URL: {target_url}\n"
    if target_host:
        challenge_context += f"Target Host: {target_host}:{target_port}\n"
    if attachments:
        challenge_context += "Available files:\n"
        for att in attachments:
            filename = att.get("filename", "?")
            filepath = att.get("filepath", "?")
            mime = att.get("mime_type", "?")
            size = att.get("size_bytes", 0)
            challenge_context += f"  - {filename} ({mime}, {size} bytes) @ {filepath}\n"

    tool_history_str = ""
    loop_warning = ""
    if tool_history:
        recent = tool_history[-15:]
        for i, tc in enumerate(recent):
            tool_history_str += (
                f"\nTool Call {i+1}: {tc.get('tool_name')}({tc.get('tool_input', {})})\n"
                f"Output: {tc.get('tool_output', '')[:500]}\n"
            )
        # Detect repeated same-tool calls with no progress
        last_tools = [t.get("tool_name") for t in tool_history[-6:]]
        if len(last_tools) >= 3 and len(set(last_tools)) == 1:
            loop_warning = (
                f"\n⚠️ WARNING: You have called {last_tools[0]} {len(last_tools)} times in a row "
                "and it keeps failing. Try a DIFFERENT tool or approach immediately.\n"
            )
        elif len(last_tools) >= 4 and len(set(last_tools[-4:])) <= 1:
            loop_warning = (
                "\n⚠️ WARNING: You keep repeating the same tool. Switch strategy now.\n"
            )

    observations_str = "\n".join(observations[-3:]) if observations else "No observations yet."

    similar = experience_db.find_similar(description, category=category, top_k=3)
    experience_hints = ""
    if similar:
        experience_hints = "Past similar solved challenges:\n"
        for rec, score in similar:
            tools_str = ", ".join(
                f"{t.get('tool', '?')}({json.dumps(t.get('args', {}))})"
                for t in (rec.tools_used or [])
            )
            experience_hints += f"  [{rec.category}] (score={score:.2f}) Tools: {tools_str}\n"
            if rec.workflow:
                experience_hints += f"  Workflow: {rec.workflow}\n"
            if rec.final_flag and rec.final_flag != "picoCTF{...}":
                experience_hints += f"  → Flag: {rec.final_flag}\n"
        experience_hints += "\n"

    hint_instructions = ""
    if mode == "hint":
        hint_instructions = (
            "You are in HINT mode. Do NOT reveal the flag or complete solution. "
            "Generate a single progressive hint."
        )

    prompt = (
        f"{system_prompt}\n\n"
        f"{hint_instructions}\n\n"
        f"--- CHALLENGE CONTEXT ---\n{challenge_context}\n"
        f"{loop_warning}"
        f"Current hypothesis: {current_hypothesis}\n"
        f"--- RECENT OBSERVATIONS ---\n{observations_str}\n"
        f"--- TOOL HISTORY (last 5) ---\n{tool_history_str}\n"
        f"--- PAST EXPERIENCES ---\n{experience_hints if experience_hints else 'No past similar challenges in database yet.'}\n"
        f"Available tools: {', '.join(available_tools)}\n"
        f"Iteration: {iteration + 1}\n"
    )

    if mode == "hint":
        prompt += "\nRespond with a single progressive hint. No JSON.\n"
    else:
        prompt += (
            '\nGiven this context, what single tool should I call next and with what arguments?'
            '\nRespond ONLY with valid JSON. Use the tool PARAMETER NAMES (like "filepath", "url", "ciphertext", "text", "n", "e", "c"), NOT CLI flags (like -f, -u, -c).'
            '\nExample: {"tool": "exiftool_tool", "args": {"filepath": "/path/to/file"}, "reasoning": "Read metadata to find hidden info."}'
            '\n\nYour valid JSON:\n'
        )

    import asyncio
    max_llm_retries = 5
    for attempt in range(max_llm_retries):
        try:
            full_llm_text = ""
            async for chunk in llm.astream(prompt):
                token = getattr(chunk, "content", "") or ""
                full_llm_text += token
                print(token, end="", flush=True)
            print(flush=True)
            content = full_llm_text.strip()
            if not content:
                logger.warning(f"LLM returned empty response for {agent_name}")
                return {
                    "current_agent": "flag_validation",
                    "failure_reason": "LLM returned empty response",
                    "trace_events": [{
                        "event_type": "error",
                        "agent": agent_name,
                        "data": {"error": "LLM returned empty response"},
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "iteration": iteration,
                    }],
                }
            break
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "Too Many Requests" in err_str:
                wait = 2 ** (attempt + 1)
                logger.warning(f"LLM rate limited (429) for {agent_name}, retry {attempt+1}/{max_llm_retries} after {wait}s: {e}")
                await asyncio.sleep(wait)
                continue
            logger.error(f"LLM call failed for {agent_name}: {e}")
            return {
                "current_agent": "flag_validation",
                "failure_reason": f"LLM error: {e}",
                "trace_events": [{
                    "event_type": "error",
                    "agent": agent_name,
                    "data": {"error": str(e)},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "iteration": iteration,
                }],
            }
    else:
        logger.error(f"LLM call failed for {agent_name} after {max_llm_retries} retries (rate limited)")
        return {
            "current_agent": "flag_validation",
            "failure_reason": "LLM rate limited after retries",
            "trace_events": [{
                "event_type": "error",
                "agent": agent_name,
                "data": {"error": "LLM rate limited after retries (429)"},
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "iteration": iteration,
            }],
        }

    new_events = []
    new_observations = []
    new_tool_calls = []
    new_candidate_flags = []

    if mode == "hint":
        new_observations.append("[HINT] " + content)
        new_events.append({
            "event_type": "hypothesis",
            "agent": agent_name,
            "data": {"hint": content},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "iteration": iteration,
        })
        return {
            "observations": new_observations,
            "trace_events": new_events,
            "iteration_count": iteration + 1,
            "current_agent": node_name,
        }

    try:
        # Extract first JSON object (handles trailing natural language)
        clean = _extract_first_json(content)
        parsed = json.loads(clean)
        tool_name = parsed.get("tool", "")
        tool_args = parsed.get("args", {})
        reasoning = parsed.get("reasoning", "")
        # Normalize & filter args immediately (before trace event uses them)
        tool_args = _normalize_tool_args(tool_name, tool_args)
    except json.JSONDecodeError:
        logger.warning(f"LLM response not valid JSON for {agent_name}: {content[:200]}")
        # Try to fix common LLM escaping issues: \\\" -> \", \n -> newline, etc.
        try:
            fixed = content.replace("\\\"", "\"")
            parsed = json.loads(fixed)
            tool_name = parsed.get("tool", "")
            tool_args = parsed.get("args", {})
            reasoning = parsed.get("reasoning", "")
            tool_args = _normalize_tool_args(tool_name, tool_args)
            logger.info(f"Fixed JSON parsing with escape cleanup for {agent_name}")
        except json.JSONDecodeError:
            new_observations.append(f"LLM returned invalid JSON. Try again. Raw: {content[:200]}")
            return {
                "observations": new_observations,
                "iteration_count": iteration + 1,
                "current_agent": node_name,
                "trace_events": [{
                    "event_type": "llm_reasoning",
                    "agent": agent_name,
                    "data": {"raw_output": content[:2000], "error": "Invalid JSON"},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "iteration": iteration,
                }],
            }

    new_events.append({
        "event_type": "llm_reasoning",
        "agent": agent_name,
        "data": {"raw_output": content[:2000], "reasoning": reasoning},
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "iteration": iteration,
    })

    if tool_name not in available_tools:
        logger.warning(f"Agent {agent_name} requested unavailable tool: {tool_name}")
        return {
            "observations": [f"Tool {tool_name} not in available tools"],
            "iteration_count": iteration + 1,
            "current_agent": node_name,
            "current_hypothesis": reasoning,
        }

    tool_instance = get_tool(tool_name)
    if not tool_instance:
        return {
            "observations": [f"Tool {tool_name} not found in registry"],
            "iteration_count": iteration + 1,
            "current_agent": node_name,
        }

    new_events.append({
        "event_type": "tool_call",
        "agent": agent_name,
        "data": {"tool": tool_name, "args": tool_args, "reasoning": reasoning},
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "iteration": iteration,
    })

    # Hard loop breaker: if same tool called 4+ times in a row, force a strategy change
    last_tool_names = [t.get("tool_name") for t in tool_history[-5:]] + [tool_name]
    if len(last_tool_names) >= 4 and len(set(last_tool_names[-4:])) == 1:
        logger.warning(f"Loop detected: {tool_name} called {len(last_tool_names[-4:])} times in a row")
        return {
            "observations": [f"❌ {tool_name} has been called {len(last_tool_names[-4:])} times without success. The current approach is NOT working. You MUST try a different tool or a completely different approach NOW."],
            "iteration_count": iteration + 1,
            "current_agent": node_name,
            "current_hypothesis": f"Strategy rejected: {tool_name} loop. Need different approach.",
            "trace_events": new_events + [{
                "event_type": "tool_result",
                "agent": agent_name,
                "data": {"tool": tool_name, "success": False, "error": "Loop detected. Strategy rejected."},
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "iteration": iteration,
            }],
        }

    # Strip unknown kwargs that the tool doesn't accept
    tool_args = _filter_tool_args(tool_instance, tool_args)

    try:
        tool_result = await tool_instance.run(**tool_args)
    except TypeError as e:
        logger.warning(f"Tool {tool_name} called with invalid args: {e}")
        return {
            "observations": [f"Tool {tool_name} error: {e}. Try different arguments."],
            "iteration_count": iteration + 1,
            "current_agent": node_name,
            "trace_events": new_events + [{
                "event_type": "tool_result",
                "agent": agent_name,
                "data": {"tool": tool_name, "success": False, "error": str(e)},
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "iteration": iteration,
            }],
        }
    except Exception as e:
        logger.error(f"Tool {tool_name} unexpected error: {e}")
        return {
            "observations": [f"Tool {tool_name} crashed: {e}"],
            "iteration_count": iteration + 1,
            "current_agent": node_name,
            "trace_events": new_events + [{
                "event_type": "error",
                "agent": agent_name,
                "data": {"tool": tool_name, "error": str(e)},
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "iteration": iteration,
            }],
        }

    new_events.append({
        "event_type": "tool_result",
        "agent": agent_name,
        "data": {
            "tool": tool_name,
            "success": tool_result.get("success", False),
            "output": tool_result.get("output", "")[:1000],
            "error": tool_result.get("error", "")[:200],
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "iteration": iteration,
    })

    flag_result = await detect_flag(
        tool_result.get("output", ""),
        manifest.get("flag_format"),
    )
    if flag_result["found"]:
        for flag in flag_result["flags"]:
            if validate_flag(flag, manifest.get("flag_format")):
                new_candidate_flags.append(flag)
                new_events.append({
                    "event_type": "flag_validated",
                    "agent": agent_name,
                    "data": {"flag": flag, "method": flag_result["method"]},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "iteration": iteration,
                })
                logger.info(f"Flag found and validated: {flag}")
                return {
                    "candidate_flags": new_candidate_flags,
                    "final_flag": flag,
                    "solved": True,
                    "current_agent": "flag_validation",
                    "trace_events": new_events,
                    "current_hypothesis": reasoning,
                }

        new_events.append({
            "event_type": "flag_candidate",
            "agent": agent_name,
            "data": {"flags": flag_result["flags"], "method": flag_result["method"]},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "iteration": iteration,
        })

    new_tool_calls.append({
        "tool_name": tool_name,
        "tool_input": tool_args,
        "tool_output": tool_result.get("output", "")[:2000],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "success": tool_result.get("success", False),
    })
    # Keep tool_history bounded: only return the new record; reducer appends it
    # The state reducer uses operator.add, so each return adds one element.
    # Total history is bounded by max_iterations * 1 = 20 entries.
    obs_output = tool_result.get('output', '')[:200]
    obs_error = tool_result.get('error', '')
    if obs_error:
        obs_output += f" [ERROR: {obs_error[:100]}]"
    new_observations.append(f"{tool_name}: {obs_output}")

    new_events.append({
        "event_type": "hypothesis",
        "agent": agent_name,
        "data": {"hypothesis": reasoning},
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "iteration": iteration,
    })

    return {
        "tool_history": new_tool_calls,
        "observations": new_observations,
        "current_hypothesis": reasoning,
        "iteration_count": iteration + 1,
        "current_agent": node_name,
        "trace_events": new_events,
        "candidate_flags": new_candidate_flags,
        "final_flag": None,
    }
