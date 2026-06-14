import math
import httpx
from typing import Optional
from sympy import factorint, isprime
from Crypto.Util.number import long_to_bytes
from backend.tools.base import BaseTool
from loguru import logger


def integer_nth_root(n: int, e: int) -> Optional[int]:
    if e <= 0:
        return None
    low, high = 0, n
    while low <= high:
        mid = (low + high) // 2
        power = pow(mid, e)
        if power == n:
            return mid
        elif power < n:
            low = mid + 1
        else:
            high = mid - 1
    return None


def fermat_factor(n: int) -> Optional[tuple[int, int]]:
    a = math.isqrt(n)
    if a * a < n:
        a += 1
    b2 = a * a - n
    while b2 >= 0:
        b = math.isqrt(b2)
        if b * b == b2:
            return (a - b, a + b)
        a += 1
        b2 = a * a - n
        if a > n // 2:
            return None
    return None


def trial_factor(n: int, limit: int = 10_000_000) -> Optional[tuple[int, int]]:
    if n % 2 == 0:
        return (2, n // 2)
    i = 3
    while i < limit:
        if n % i == 0:
            return (i, n // i)
        i += 2
    return None


async def query_factordb(n: int) -> Optional[dict]:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"http://factordb.com/api?query={n}")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "FF":
                    factors = []
                    for factor, count in data.get("factors", []):
                        factors.extend([int(factor)] * count)
                    return {"factors": factors}
            return None
    except Exception as e:
        logger.warning(f"FactorDB query failed: {e}")
        return None


class RSASolverTool(BaseTool):
    name = "rsa_solver"
    description = "Solve RSA challenges: small e, known factors, Fermat, FactorDB"

    async def run(self, n: int = None, e: int = None, c: int = None,
                  p: int = None, q: int = None) -> dict:
        if not n or not e or not c:
            return {"success": False, "output": "n, e, and c are required", "error": ""}

        p_found, q_found = p, q
        method = ""

        if p and q and isprime(p) and isprime(q):
            method = "given_factors"
        elif e <= 3:
            m_candidate = integer_nth_root(c, e)
            if m_candidate and pow(m_candidate, e, n) == c:
                plaintext = long_to_bytes(m_candidate)
                return {
                    "success": True,
                    "output": f"Plaintext: {plaintext.decode(errors='replace')}",
                    "error": "",
                    "method": "small_e_attack",
                    "plaintext": plaintext.decode(errors="replace"),
                    "m": m_candidate,
                }
        else:
            factors = fermat_factor(n)
            if factors:
                p_found, q_found = factors
                method = "fermat"
            else:
                factors = trial_factor(n)
                if factors:
                    p_found, q_found = factors
                    method = "trial_division"
                else:
                    factordb_result = await query_factordb(n)
                    if factordb_result and len(factordb_result["factors"]) >= 2:
                        p_found = factordb_result["factors"][0]
                        q_found = factordb_result["factors"][1]
                        method = "factordb"

        if p_found and q_found:
            try:
                phi = (p_found - 1) * (q_found - 1)
                d = pow(e, -1, phi)
                m = pow(c, d, n)
                plaintext = long_to_bytes(m)
                decoded = plaintext.decode(errors="replace")
                return {
                    "success": True,
                    "output": f"Decrypted: {decoded}\nMethod: {method}\np={p_found}\nq={q_found}\nd={d}",
                    "error": "",
                    "method": method,
                    "plaintext": decoded,
                    "p": p_found,
                    "q": q_found,
                    "d": d,
                    "m": m,
                }
            except Exception as ex:
                return {"success": False, "output": f"Decryption failed: {ex}", "error": str(ex)}

        return {"success": False, "output": "Could not factor n with any method", "error": ""}
