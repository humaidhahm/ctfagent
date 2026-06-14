import string
from collections import Counter
from backend.tools.base import BaseTool
from backend.tools.crypto.encoding_detector import score_text, ENGLISH_FREQ
from loguru import logger


def chi_squared(text: str) -> float:
    letters = [c.lower() for c in text if c.isalpha()]
    if not letters:
        return float("inf")
    n = len(letters)
    counter = Counter(letters)
    chi2 = 0.0
    for ch in string.ascii_lowercase:
        observed = counter.get(ch, 0)
        expected = ENGLISH_FREQ.get(ch, 0) * n
        if expected > 0:
            chi2 += (observed - expected) ** 2 / expected
    return chi2


def crack_caesar(ciphertext: str = "") -> list[dict]:
    results = []
    for shift in range(26):
        plain = ""
        for c in ciphertext:
            if c.isalpha():
                base = ord('A') if c.isupper() else ord('a')
                plain += chr((ord(c) - base - shift) % 26 + base)
            else:
                plain += c
        chi2 = chi_squared(plain)
        score = score_text(plain)
        results.append({"shift": shift, "plaintext": plain[:500], "chi2": round(chi2, 2), "score": round(score, 4)})
    results.sort(key=lambda x: x["chi2"])
    return results[:5]


def crack_vigenere(ciphertext: str = "") -> list[dict]:
    text = ciphertext.upper()
    letters_only = [c for c in text if c.isalpha()]
    if len(letters_only) < 20:
        return []

    best_results = []
    for key_len in range(2, min(15, len(letters_only) // 3) + 1):
        key = ""
        for i in range(key_len):
            col = letters_only[i::key_len]
            # Use chi-squared minimization against English frequency
            best_shift = 0
            best_chi2 = float("inf")
            for shift in range(26):
                shifted = [chr((ord(c) - ord('A') - shift) % 26 + ord('A')) for c in col]
                shifted_text = "".join(shifted)
                chi2 = chi_squared(shifted_text)
                if chi2 < best_chi2:
                    best_chi2 = chi2
                    best_shift = shift
            key += chr(ord('A') + best_shift)

        plain = ""
        key_idx = 0
        for c in ciphertext:
            if c.isalpha():
                base = ord('A') if c.isupper() else ord('a')
                key_char = key[key_idx % len(key)]
                key_shift = ord(key_char) - ord('A')
                plain += chr((ord(c) - base - key_shift) % 26 + base)
                key_idx += 1
            else:
                plain += c

        chi2 = chi_squared(plain)
        score_val = score_text(plain)
        best_results.append({
            "key": key,
            "key_length": key_len,
            "plaintext": plain[:500],
            "chi2": round(chi2, 2),
            "score": round(score_val, 4),
        })

    best_results.sort(key=lambda x: x["chi2"])
    return best_results[:5]


def crack_rail_fence(ciphertext: str = "") -> list[dict]:
    results = []
    for rails in range(2, 11):
        fence = [[] for _ in range(rails)]
        rail = 0
        direction = 1
        for c in ciphertext:
            fence[rail].append(c)
            rail += direction
            if rail == rails - 1 or rail == 0:
                direction *= -1
        plain = "".join("".join(r) for r in fence)
        # Actually for decryption we need to reconstruct properly
        # Rail fence decode
        n = len(ciphertext)
        positions = [0] * n
        rail2 = 0
        direction2 = 1
        for i in range(n):
            positions[i] = rail2
            rail2 += direction2
            if rail2 == rails - 1 or rail2 == 0:
                direction2 *= -1

        idx = 0
        decoded = [""] * n
        for r in range(rails):
            for i in range(n):
                if positions[i] == r:
                    decoded[i] = ciphertext[idx]
                    idx += 1

        plain = "".join(decoded)
        chi2 = chi_squared(plain)
        score_val = score_text(plain)
        results.append({
            "rails": rails,
            "plaintext": plain[:500],
            "chi2": round(chi2, 2),
            "score": round(score_val, 4),
        })

    results.sort(key=lambda x: x["chi2"])
    return results[:3]


class CipherCrackerTool(BaseTool):
    name = "cipher_cracker"
    description = "Crack classical ciphers (Caesar, Vigenere, Rail Fence, Atbash)"

    async def run(self, ciphertext: str = "", cipher_type: str = "auto") -> dict:
        if not ciphertext:
            return {"success": False, "output": "", "error": "No ciphertext provided", "command": "crypto/cipher_cracker.py"}
        if not ciphertext:
            return {"success": False, "output": "No ciphertext provided", "error": ""}

        results = {}

        from backend.tools.crypto.encoding_detector import decode_atbash
        atbash_plain = decode_atbash(ciphertext)
        atbash_score = score_text(atbash_plain)

        if cipher_type in ("auto", "caesar"):
            caesar_results = crack_caesar(ciphertext)
            results["caesar"] = caesar_results

        if cipher_type in ("auto", "vigenere") and len(ciphertext) > 20:
            vig_results = crack_vigenere(ciphertext)
            if vig_results:
                results["vigenere"] = vig_results

        if cipher_type in ("auto", "rail_fence"):
            rail_results = crack_rail_fence(ciphertext)
            if rail_results:
                results["rail_fence"] = rail_results

        if cipher_type in ("auto", "atbash"):
            results["atbash"] = {
                "plaintext": atbash_plain[:500],
                "score": round(atbash_score, 4),
            }

        output_lines = []
        if cipher_type == "auto":
            all_candidates = []
            for cat, candidates in results.items():
                if isinstance(candidates, list):
                    all_candidates.extend(candidates)
                elif isinstance(candidates, dict):
                    all_candidates.append(candidates)

            all_candidates.sort(key=lambda x: x.get("chi2", float("inf")))

            if all_candidates:
                best = all_candidates[0]
                output_lines.append(f"Best guess: {best.get('plaintext', '')[:500]}")
                output_lines.append(f"Score: {best.get('score', 0)}")
                output_lines.append(f"Chi2: {best.get('chi2', 'N/A')}")
            if atbash_score > 0.25:
                output_lines.append(f"\nAtbash: {atbash_plain[:500]}")
        else:
            for cat, data in results.items():
                output_lines.append(f"\n{cat.upper()}:")
                if isinstance(data, list):
                    for r in data[:3]:
                        output_lines.append(f"  {r}")
                else:
                    output_lines.append(f"  {data}")

        return {
            "success": True,
            "output": "\n".join(output_lines) if output_lines else "No decryption found",
            "error": "",
            "parsed_results": results,
        }
