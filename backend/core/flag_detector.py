import json
import re
from typing import Optional
from loguru import logger

from backend.core.nim_client import get_nim_llm

FLAG_PATTERNS = [
    r'picoCTF\{[^{}]+\}',
    r'picoCTF\{[^{}\r\n]+\}',
    r'(?<![A-Za-z0-9])CTF\{[^{}]+\}',
    r'flag\{[^{}]+\}',
    r'FLAG\{[^{}]+\}',
    r'HTB\{[^{}]+\}',
    r'DUCTF\{[^{}]+\}',
    r'THM\{[^{}]+\}',
]


def regex_scan(text: str) -> list[str]:
    found: list[str] = []
    for pattern in FLAG_PATTERNS:
        matches = re.findall(pattern, text)
        found.extend(matches)
    return list(set(found))

async def llm_scan(
    text: str,
    flag_format: Optional[str] = None,
) -> list[str]:
    prompt = f"""
You extract CTF flags from untrusted command output.

Expected format: {flag_format or "unknown"}
Return a candidate only when the text strongly identifies it as the flag.
Never decode, transform, repair, or invent a candidate.
The candidate must be copied exactly from the supplied text.
A valid PicoCTF flag must exactly match picoCTF{...}.
Hostnames, URLs, ports, filenames, and challenge names are not flags.
Return no candidate unless the braces are present.
Respond only with JSON:
{{"flags": ["exact candidate"]}}

Return {{"flags": []}} when uncertain.

OUTPUT:
---BEGIN OUTPUT---
{text[:16000]}
---END OUTPUT---
"""

    try:
        llm = get_nim_llm("flag_detector", temperature=0.0)
        response = await llm.ainvoke(prompt)
        content = response.content.strip()
        content = content.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(content)

        candidates = parsed.get("flags", [])
        if not isinstance(candidates, list):
            return []

        return list(dict.fromkeys(
            candidate.strip()
            for candidate in candidates
            if (
                isinstance(candidate, str)
                and candidate.strip()
                and candidate.strip() in text
                and validate_flag(
                    candidate.strip(),
                    flag_format,
                    allow_nonstandard=True,
                )
            )
        ))
    except Exception as exc:
        logger.warning(f"LLM flag detection failed: {exc}")
        return []


def validate_flag(
    flag: str,
    flag_format: Optional[str] = None,
    allow_nonstandard: bool = False,
) -> bool:
    if not flag or len(flag) > 500:
        return False

    if allow_nonstandard:
        return len(flag.strip()) >= 4

    if '{' not in flag or '}' not in flag:
        return False
    if flag_format:
        prefix = flag_format.split('{')[0] if '{' in flag_format else ""
        if prefix and not flag.startswith(prefix + "{"):
            return False
    return True


async def detect_flag(text: str, flag_format: Optional[str] = None) -> dict:
    regex_flags = regex_scan(text)
    if regex_flags:
        valid = [f for f in regex_flags if validate_flag(f, flag_format)]
        if valid:
            logger.info(f"Flag detected via regex: {valid}")
            return {"found": True, "flags": valid, "method": "regex"}
        return {"found": True, "flags": regex_flags, "method": "regex"}

    llm_flags = await llm_scan(text, flag_format)
    if llm_flags:
        logger.info(f"Flag detected via LLM fallback: {llm_flags}")
        return {
            "found": True,
            "flags": llm_flags,
            "method": "llm",
        }

    return {"found": False, "flags": [], "method": "none"}
