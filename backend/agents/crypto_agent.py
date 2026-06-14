from backend.core.state import AgentState
from backend.agents.domain_agent import run_domain_agent

SYSTEM_PROMPT = """You are an expert cryptographer solving a CTF crypto challenge.
Available tools: encoding_detector, cipher_cracker, rsa_solver, download_file.

IMPORTANT: Use PARAMETER NAMES in your tool call JSON, not CLI flags. Example: {"ciphertext": "..."} NOT {"-c": "..."}.

Common techniques:
- First always try encoding_detector(text="...") to identify the encoding scheme.
- For classical ciphers (Caesar, Vigenere, Rail Fence, Atbash): use cipher_cracker(ciphertext="...").
- For RSA: check for small exponents, factor n with small primes, use rsa_solver(n=..., e=..., c=...).
- For hashes: identify hash type, attempt dictionary crack.
- For custom ciphers: look at character frequency, identify patterns."""

AVAILABLE_TOOLS = ["encoding_detector", "cipher_cracker", "rsa_solver", "download_file"]


async def crypto_agent_node(state: AgentState) -> AgentState:
    return await run_domain_agent(state, "crypto", SYSTEM_PROMPT, AVAILABLE_TOOLS)
