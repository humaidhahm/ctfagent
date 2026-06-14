import re
from typing import Optional
from loguru import logger

FLAG_PATTERNS = [
    r'picoCTF\{[^{}]+\}',
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


def validate_flag(flag: str, flag_format: Optional[str] = None) -> bool:
    if not flag:
        return False
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
    return {"found": False, "flags": [], "method": "none"}
