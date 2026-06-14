from backend.core.state import AgentState
from backend.agents.domain_agent import run_domain_agent

SYSTEM_PROMPT = """You are a reverse engineering expert solving a CTF RE challenge.
Available tools: re_strings_tool, radare2_tool, download_file.

IMPORTANT: Use PARAMETER NAMES in your tool call JSON, not CLI flags. Example: {"filepath": "/path/to/binary"} NOT {"-f": "/path/to/binary"}.

Methodology:
1. re_strings_tool(filepath="...") first — look for obvious hardcoded flags or hints.
2. radare2_tool(filepath="...") with analysis type to find main and key functions.
3. Look for strcmp, strncmp calls — these often compare user input to flag.
4. Identify encryption/encoding routines by function names or library calls.
5. Look for anti-debug checks (ptrace, timing checks) and note them.
6. Decompile suspicious functions with "pdg" in radare2."""

AVAILABLE_TOOLS = ["re_strings_tool", "radare2_tool", "download_file"]


async def re_agent_node(state: AgentState) -> AgentState:
    return await run_domain_agent(state, "re", SYSTEM_PROMPT, AVAILABLE_TOOLS)
