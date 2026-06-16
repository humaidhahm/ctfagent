import json
from datetime import datetime, timezone
from loguru import logger

from backend.core.nim_client import get_nim_llm
from backend.core.state import AgentState
from backend.memory.session_store import session_store
from backend.memory.experience_db import experience_db


async def classify_node(state: AgentState) -> dict:
    llm = get_nim_llm("classifier", temperature=0.0)

    manifest = state.get("manifest", {})
    description = manifest.get("description", "")
    attachments = manifest.get("attachments", [])
    target_url = manifest.get("target_url")

    attachment_info = ""
    for att in attachments:
        attachment_info += f"- {att.get('filename')} ({att.get('mime_type')}, {att.get('size_bytes')} bytes)\n"

    similar = experience_db.find_similar(description, top_k=3)
    experience_hints = ""
    if similar:
        experience_hints = "\nSimilar past challenges solved:\n"
        for rec, score in similar:
            tools_str = ", ".join(t.get("tool", "?") for t in (rec.tools_used or []))
            experience_hints += (
                f"- [{rec.category}] (similarity {score:.2f}) "
                f"Tools: {tools_str or 'none'} → Flag: {rec.final_flag[:40]}...\n"
            )
        experience_hints += "\n"

    prompt = (
        "You are a CTF challenge classifier. Given a challenge description and list of attached files, "
        "determine the challenge category.\n\n"
        "Categories:\n"
        "- web: HTTP services, login pages, SQL, XSS, SSRF, cookies, JWTs, APIs, command injection, shell injection, ping injection, remote code execution via web\n"
        "- crypto: ciphers, RSA, AES, hashes, encoding schemes, number theory\n"
        "- forensics: files to analyse, steganography, pcap dumps, memory images, metadata\n"
        "- pwn: binary files, buffer overflows, format strings, shellcode, ROP, local binary exploitation\n"
        "- re: binaries to reverse-engineer, obfuscated code, keygen challenges\n"
        "- osint: password profiling from personal details, social media investigation, real-world lookups, hash cracking with personal info\n"
        "- misc: anything else, general skills challenges, interactive terminal games, educational simulations\n\n"
        f"{experience_hints}"
        f"Description:\n{description}\n\n"
        f"Attachments:\n{attachment_info if attachment_info else 'None'}\n"
        f"Target URL: {target_url or 'None'}\n\n"
        "Respond ONLY with valid JSON in this exact format:\n"
        '{\n  "category": "<one of the above>",\n  "confidence": <0.0-1.0>,\n'
        '  "reasoning": "<one sentence>",\n'
        '  "recommended_tools": ["<tool1>", "<tool2>", ...]\n}\n'
    )

    try:
        response = await llm.ainvoke(prompt)
        content = response.content.strip()
        content = content.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(content)
        valid_tools = set(list_tools())
        recommended = [
            tool for tool in parsed.get("recommended_tools", [])
            if tool in valid_tools
        ]
    except Exception as e:
        logger.error(f"Classification failed: {e}")
        return {
            "category": "misc",
            "recommended_toolchain": ["gobuster", "curl_probe"],
            "classification_reasoning": "Classification LLM error, defaulted to misc",
            "trace_events": [{
                "event_type": "error",
                "agent": "classifier",
                "data": {"error": f"Classification failed: {e}"},
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "iteration": 0,
            }],
        }

    category = parsed.get("category", "misc").lower()
    if category not in ("web", "crypto", "forensics", "pwn", "re", "osint", "misc"):
        category = "misc"
    # OSINT and misc both route to misc handler

    logger.info(f"Classified challenge as: {category} ({parsed.get('confidence', 0.0)})")

    return {
        "category": category,
        "recommended_toolchain": parsed.get("recommended_tools", []),
        "classification_reasoning": parsed.get("reasoning", ""),
        "trace_events": [{
            "event_type": "classification",
            "agent": "classifier",
            "data": {
                "category": category,
                "confidence": parsed.get("confidence", 0.0),
                "reasoning": parsed.get("reasoning", ""),
                "recommended_tools": parsed.get("recommended_tools", []),
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "iteration": 0,
        }],
    }
