import shutil
import subprocess
import time
from typing import Optional
from loguru import logger

DOMAIN_TOOLS: dict[str, list[str]] = {
    "Web": [
        "sqlmap", "gobuster", "ffuf", "nikto", "whatweb",
        "wfuzz", "nmap", "nc", "curl", "wget", "git",
        "jq", "openssl", "masscan", "dnsenum", "dnsrecon",
        "dirsearch", "theHarvester", "wafw00f", "sslyze",
        "xsstrike", "arjun", "sqliv",
    ],
    "Forensics": [
        "binwalk", "exiftool", "steghide", "zsteg", "tshark",
        "foremost", "hashcat", "john", "xxd", "pngcheck",
        "audacity", "sleuthkit", "testdisk", "scalpel",
        "bulk_extractor", "strings", "pdftotext", "stegsolve",
        "stegoveritas", "oletools", "pdf-parser",
    ],
    "Pwn": [
        "gdb", "python3", "strings", "objdump", "strace",
        "ltrace", "patchelf", "ROPgadget", "checksec",
        "one_gadget", "pwntools", "angr", "z3", "keystone",
        "unicorn", "qemu-x86_64",
    ],
    "RE": [
        "r2", "strings", "objdump", "unzip", "file", "upx",
        "readelf", "nm", "pyelftools", "lief", "capstone",
        "frida",
    ],
    "Crypto": [
        "openssl", "yara", "hashid", "gmpy2", "pycryptodome",
        "sage",
    ],
    "OSINT": [
        "whois", "dig", "nslookup", "traceroute", "sherlock",
        "holehe", "theHarvester", "shodan", "recon-ng",
    ],
    "Misc": [
        "screen", "tmux", "htop", "tree", "vim", "nano",
        "7z", "rsync", "locate", "pip3", "docker",
    ],
}


def flatten_tool_list() -> list[str]:
    seen = set()
    result = []
    for tools in DOMAIN_TOOLS.values():
        for t in tools:
            if t not in seen:
                seen.add(t)
                result.append(t)
    return result


ALL_TOOLS: list[str] = flatten_tool_list()

# ─── TTL Cache ─────────────────────────────────────────────

_TOOL_CACHE: dict[str, tuple[str | None, float]] = {}
_CACHE_TTL = 30.0


def _cached_check(name: str, force_refresh: bool = False) -> str | None:
    now = time.monotonic()
    if not force_refresh:
        cached = _TOOL_CACHE.get(name)
        if cached and (now - cached[1]) < _CACHE_TTL:
            return cached[0]

    path = shutil.which(name)
    version: str | None = path if path else None
    _TOOL_CACHE[name] = (version, now)
    return version


def check_tool_installed(name: str) -> bool:
    return _cached_check(name) is not None


def get_tool_path(name: str) -> str | None:
    return _cached_check(name)


def invalidate_cache():
    _TOOL_CACHE.clear()


async def check_all_tools(force_refresh: bool = False) -> dict:
    results: dict[str, Optional[str]] = {}
    logger.info("Checking all domain tools...")
    for tool in ALL_TOOLS:
        results[tool] = _cached_check(tool, force_refresh=force_refresh)
    return results


async def check_domain_tools(domain: str, force_refresh: bool = False) -> dict:
    results: dict[str, Optional[str]] = {}
    tools = DOMAIN_TOOLS.get(domain, [])
    for tool in tools:
        results[tool] = _cached_check(tool, force_refresh=force_refresh)
    return results


def get_domain_summary() -> dict[str, dict]:
    summary = {}
    for domain, tools in DOMAIN_TOOLS.items():
        found = sum(1 for t in tools if check_tool_installed(t))
        summary[domain] = {"found": found, "total": len(tools)}
    return summary
