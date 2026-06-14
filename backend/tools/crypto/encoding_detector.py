import base64
import binascii
import re
import string
from backend.tools.base import BaseTool
from loguru import logger


ENGLISH_FREQ = {
    'a': 0.08167, 'b': 0.01492, 'c': 0.02782, 'd': 0.04253,
    'e': 0.12702, 'f': 0.02228, 'g': 0.02015, 'h': 0.06094,
    'i': 0.06966, 'j': 0.00153, 'k': 0.00772, 'l': 0.04025,
    'm': 0.02406, 'n': 0.06749, 'o': 0.07507, 'p': 0.01929,
    'q': 0.00095, 'r': 0.05987, 's': 0.06327, 't': 0.09056,
    'u': 0.02758, 'v': 0.00978, 'w': 0.02360, 'x': 0.00150,
    'y': 0.01974, 'z': 0.00074,
}


COMMON_WORDS = {"the", "and", "that", "have", "for", "with", "this", "flag",
                 "from", "they", "been", "what", "were", "when", "your", "which",
                 "their", "each", "would", "about", "there", "could", "should"}


def score_text(text: str = "") -> float:
    if not text:
        return 0.0
    letters = [c.lower() for c in text if c.isalpha()]
    if not letters:
        return 0.0

    chi2 = 0.0
    n = len(letters)
    from collections import Counter
    counter = Counter(letters)
    for ch, expected in ENGLISH_FREQ.items():
        observed = counter.get(ch, 0)
        expected_count = expected * n
        if expected_count > 0:
            chi2 += (observed - expected_count) ** 2 / expected_count

    lower_text = text.lower()
    word_score = sum(1 for w in COMMON_WORDS if w in lower_text)

    return max(0.0, 1.0 - chi2 / (n * 10)) + word_score * 0.05


def decode_base64(s: str) -> str | None:
    try:
        decoded = base64.b64decode(s)
        result = decoded.decode(errors="replace")
        return result if result.strip() else None
    except Exception:
        return None


def decode_base64_urlsafe(s: str) -> str | None:
    try:
        decoded = base64.urlsafe_b64decode(s + "==")
        return decoded.decode(errors="replace")
    except Exception:
        return None


def decode_base32(s: str) -> str | None:
    try:
        decoded = base64.b32decode(s.upper())
        return decoded.decode(errors="replace")
    except Exception:
        return None


def decode_hex(s: str) -> str | None:
    try:
        decoded = bytes.fromhex(s.strip())
        return decoded.decode(errors="replace")
    except Exception:
        return None


def decode_rot13(s: str) -> str:
    return s.translate(str.maketrans(
        string.ascii_letters,
        string.ascii_lowercase[13:] + string.ascii_lowercase[:13] +
        string.ascii_uppercase[13:] + string.ascii_uppercase[:13],
    ))


def decode_rot_n(s: str, n: int) -> str:
    return s.translate(str.maketrans(
        string.ascii_letters,
        string.ascii_lowercase[n:] + string.ascii_lowercase[:n] +
        string.ascii_uppercase[n:] + string.ascii_uppercase[:n],
    ))


def decode_binary(s: str) -> str | None:
    try:
        chars = s.strip().split()
        if all(all(c in "01" for c in ch) and len(ch) == 8 for ch in chars):
            decoded = bytes(int(ch, 2) for ch in chars)
            return decoded.decode(errors="replace")
        return None
    except Exception:
        return None


def decode_morse(s: str) -> str | None:
    morse_map = {
        '.-': 'A', '-...': 'B', '-.-.': 'C', '-..': 'D', '.': 'E',
        '..-.': 'F', '--.': 'G', '....': 'H', '..': 'I', '.---': 'J',
        '-.-': 'K', '.-..': 'L', '--': 'M', '-.': 'N', '---': 'O',
        '.--.': 'P', '--.-': 'Q', '.-.': 'R', '...': 'S', '-': 'T',
        '..-': 'U', '...-': 'V', '.--': 'W', '-..-': 'X', '-.--': 'Y',
        '--..': 'Z', '-----': '0', '.----': '1', '..---': '2',
        '...--': '3', '....-': '4', '.....': '5', '-....': '6',
        '--...': '7', '---..': '8', '----.': '9',
        '.-.-.-': '.', '--..--': ',', '..--..': '?', '.----.': "'",
        '-.-.--': '!', '-..-.': '/', '-.--.': '(', '-.--.-': ')',
        '.-...': '&', '---...': ':', '-.-.-.': ';', '-...-': '=',
        '.-.-.': '+', '-....-': '-', '..--.-': '_', '.-..-.': '"',
        '...-..-': '$', '.--.-.': '@',
    }
    try:
        words = s.strip().split(" / ")
        decoded_words = []
        for word in words:
            chars = word.split()
            decoded_chars = []
            for c in chars:
                if c in morse_map:
                    decoded_chars.append(morse_map[c])
                else:
                    return None
            decoded_words.append("".join(decoded_chars))
        return " ".join(decoded_words)
    except Exception:
        return None


def decode_atbash(s: str) -> str:
    result = []
    for c in s:
        if 'a' <= c <= 'z':
            result.append(chr(ord('z') - (ord(c) - ord('a'))))
        elif 'A' <= c <= 'Z':
            result.append(chr(ord('Z') - (ord(c) - ord('A'))))
        else:
            result.append(c)
    return "".join(result)


def decode_url_encoded(s: str) -> str | None:
    import urllib.parse
    try:
        return urllib.parse.unquote(s)
    except Exception:
        return None


def _looks_like_flag_or_text(decoded: str) -> bool:
    if "{" in decoded and "}" in decoded:
        return True
    letters = sum(1 for c in decoded if c.isalpha())
    whitespace = sum(1 for c in decoded if c.isspace())
    total = len(decoded)
    if total < 3:
        return False
    letter_ratio = letters / total
    return letter_ratio > 0.3 or (letter_ratio > 0.1 and whitespace > 0)


class EncodingDetectorTool(BaseTool):
    name = "encoding_detector"
    description = "Detect and decode common CTF encoding schemes"

    async def run(self, text: str = "") -> dict:
        if not text:
            return {"success": False, "output": "", "error": "No text provided", "command": "crypto/encoding_detector.py"}
        attempts = []
        result = {"encoding": "unknown", "decoded": "", "all_attempts": []}

        test_string = text.strip()

        if not test_string:
            return result

        is_pure_hex = bool(re.fullmatch(r'[0-9a-fA-F]+', test_string)) and len(test_string) % 2 == 0
        if is_pure_hex:
            decoded = decode_hex(test_string)
            if decoded and decoded != test_string and _looks_like_flag_or_text(decoded):
                score = score_text(decoded)
                result["encoding"] = "hex"
                result["decoded"] = decoded[:2000]
                result["all_attempts"] = [{"encoding": "hex", "decoded": decoded[:500], "score": round(score, 4)}]
                return result

        decoders = [
            ("base64", decode_base64),
            ("base64_urlsafe", decode_base64_urlsafe),
            ("base32", decode_base32),
            ("hex", decode_hex),
            ("url_encoded", decode_url_encoded),
            ("binary", decode_binary),
            ("morse", decode_morse),
        ]

        for name, decoder in decoders:
            try:
                decoded = decoder(test_string)
                if decoded and decoded != test_string and _looks_like_flag_or_text(decoded):
                    score = score_text(decoded)
                    attempts.append({"encoding": name, "decoded": decoded[:500], "score": round(score, 4)})
                    result["encoding"] = name
                    result["decoded"] = decoded[:2000]
                    result["all_attempts"] = attempts
                    result["score"] = round(score, 4)
                    logger.info(f"Detected encoding: {name} (score={score:.2f})")
                    return result
            except Exception:
                pass

        if test_string.isascii() and test_string.isalpha():
            atbash_decoded = decode_atbash(test_string)
            if _looks_like_flag_or_text(atbash_decoded) and atbash_decoded != test_string:
                score = score_text(atbash_decoded)
                attempts.append({"encoding": "atbash", "decoded": atbash_decoded[:500], "score": round(score, 4)})

            rot13_decoded = decode_rot13(test_string)
            if _looks_like_flag_or_text(rot13_decoded) and rot13_decoded != test_string:
                score = score_text(rot13_decoded)
                attempts.append({"encoding": "rot13", "decoded": rot13_decoded[:500], "score": round(score, 4)})

            best_rot_n = None
            best_rot_score = -1
            for n in range(1, 26):
                if n == 13:
                    continue
                d = decode_rot_n(test_string, n)
                if _looks_like_flag_or_text(d) and d != test_string:
                    s = score_text(d)
                    if s > best_rot_score:
                        best_rot_score = s
                        best_rot_n = n

            if best_rot_n:
                d = decode_rot_n(test_string, best_rot_n)
                attempts.append({"encoding": f"rot{best_rot_n}", "decoded": d[:500], "score": round(best_rot_score, 4)})

            if attempts:
                best = max(attempts, key=lambda x: x.get("score", -1))
                result["encoding"] = best["encoding"]
                result["decoded"] = best["decoded"]

        result["all_attempts"] = attempts
        return result
