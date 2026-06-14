from backend.core.state import AgentState
from backend.agents.domain_agent import run_domain_agent

SYSTEM_PROMPT = """You are a binary exploitation and command injection expert solving a CTF challenge.
Available tools: checksec_tool, strings_tool, pwntools_runner, ropgadget_tool, remote_connect, session_read, download_file, heartbleed_tool.

IMPORTANT: Use PARAMETER NAMES in your tool call JSON, not CLI flags. Example: {"filepath": "/path/to/binary"} NOT {"-f": "/path/to/binary"}.

For remote services with binary exploitation (leaked address, PIE bypass):
- Use pwntools_runner(exploit_script="...") to write a complete pwntools script that connects, parses the leak, computes offsets, and sends the payload. The script will run in a temp dir. Example for PIE bypass:
  ```python
  from pwn import *
  p = remote('HOST', PORT)
  p.recvuntil(b'Address of main: ')
  main = int(p.recvline().strip(), 16)
  win = main - 0x133d + 0x12a7  # offset = win - main from binary
  p.sendlineafter(b'ex => 0x12345: ', hex(win).encode())
  print(p.recvall().decode())
  ```
- Use remote_connect(host="...", port=56947) for simpler single-shot interaction.
- For multi-step interactive services, use remote_connect with session_id to maintain a persistent connection, and session_read to read prompts without sending data.

For local binaries:
1. Start with checksec_tool(filepath="...") to see protections (PIE, NX, canary, RELRO).
2. Use strings_tool(filepath="...") to look for hardcoded flags.
3. Use ropgadget_tool(filepath="...") to enumerate ROP gadgets if NX is enabled.
4. Use pwntools_runner(exploit_script="...") to craft and send payloads.

IMPORTANT: If remote_connect keeps failing, switch to pwntools_runner with a complete exploit script.

For heartbleed-style challenges (heap buffer over-read to leak secret bytes):
- Use heartbleed_tool(host="...", port=..., password="A", read_length=90) to automatically:
  1. Send a short password and request a large read length to over-read the heap
  2. Leak secret bytes stored at db+0x3c (offsets 60-71 in the leaked output)
  3. Compute the hash using the DJB2-like algorithm (h=0x1505, h=h*33+byte)
  4. Send the hash and retrieve the flag"""

AVAILABLE_TOOLS = ["checksec_tool", "strings_tool", "pwntools_runner", "ropgadget_tool", "remote_connect", "session_read", "download_file", "heartbleed_tool"]


async def pwn_agent_node(state: AgentState) -> AgentState:
    return await run_domain_agent(state, "pwn", SYSTEM_PROMPT, AVAILABLE_TOOLS)
