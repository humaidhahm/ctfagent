"""Smart decode engine — multi-layer transform detection with heuristic ranking.
Auto-detects encoding type, decodes, scores plaintext quality, and chains transforms.
Shares core decode functions with backend.tools.crypto.encoding_detector."""

import re
import string
from collections import Counter

from backend.tools.crypto.encoding_detector import (
    decode_base64, decode_base32, decode_hex, decode_binary,
    decode_rot13, decode_atbash, decode_url_encoded as decode_url,
    score_text,
)

# ─── Decode Transforms ──────────────────────────────────────

DECODE_TRANSFORMS = []


def register(func):
    DECODE_TRANSFORMS.append(func)
    return func


@register
def decode_base64_wrapper(text: str):
    return decode_base64(text)


@register
def decode_base32_wrapper(text: str):
    return decode_base32(text)


@register
def decode_hex_wrapper(text: str):
    return decode_hex(text)


@register
def decode_reverse(text: str):
    return text[::-1]


@register
def decode_binary_wrapper(text: str):
    return decode_binary(text)


@register
def decode_ascii_codes(text: str):
    try:
        nums = re.findall(r'\d+', text)
        return ''.join(chr(int(n)) for n in nums)
    except Exception:
        return None


@register
def decode_url_wrapper(text: str):
    return decode_url(text)


@register
def decode_rot13_wrapper(text: str):
    return decode_rot13(text)


@register
def decode_atbash_wrapper(text: str):
    return decode_atbash(text)


def decode_rot_n(text: str, n: int):
    """Rotate by n positions."""
    result = []
    for c in text:
        if 'a' <= c <= 'z':
            result.append(chr((ord(c) - ord('a') + n) % 26 + ord('a')))
        elif 'A' <= c <= 'Z':
            result.append(chr((ord(c) - ord('A') + n) % 26 + ord('A')))
        else:
            result.append(c)
    return ''.join(result)


# ─── Main Engine ────────────────────────────────────────────

def smart_decode(text: str, max_depth: int = 5) -> list[dict]:
    """Apply multi-layer decoding with heuristic ranking.
    Returns ranked list of {text, method, score, depth} dicts."""
    results = []
    seen = set()

    def _recurse(current: str, method_chain: list[str], depth: int):
        if depth > max_depth or current in seen:
            return
        seen.add(current)

        score = score_text(current)
        results.append({
            "text": current[:500],
            "method": " → ".join(method_chain) if method_chain else "raw",
            "score": score,
            "depth": depth,
        })

        for decoder in DECODE_TRANSFORMS:
            try:
                decoded = decoder(current)
                if decoded and decoded != current:
                    _recurse(decoded, method_chain + [decoder.__name__.replace("decode_", "").replace("_wrapper", "")], depth + 1)
            except Exception:
                pass

        if depth == 0:
            pass
        elif depth < 2:
            for n in range(1, 26):
                decoded = decode_rot_n(current, n)
                if decoded and decoded != current:
                    score = score_text(decoded)
                    if score > 0.3:
                        results.append({
                            "text": decoded[:500],
                            "method": " → ".join(method_chain + [f"rot{n}"]) if method_chain else f"rot{n}",
                            "score": score,
                            "depth": depth + 1,
                        })

    _recurse(text.strip(), [], 0)
    results.sort(key=lambda r: r["score"], reverse=True)
    return results


def best_decode(text: str) -> dict | None:
    """Return the single best decode result."""
    results = smart_decode(text)
    if results:
        return results[0]
    return None
