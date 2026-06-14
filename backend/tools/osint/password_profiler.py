import hashlib
import re
import os
from backend.tools.base import BaseTool
from loguru import logger


class PasswordProfilerTool(BaseTool):
    name = "password_profiler"
    description = "Generate password candidates from personal info and test against SHA-1 hash or check_password script"

    async def run(self, userinfo_path: str = "", hash_path: str = "",
                  check_script: str = "", target_hash: str = "") -> dict:
        if not userinfo_path:
            return {"success": False, "output": "", "error": "No userinfo file provided", "command": "password_profiler"}
        try:
            with open(userinfo_path, "r", errors="replace") as f:
                info_text = f.read()
        except Exception as e:
            return {"success": False, "output": "", "error": f"Cannot read userinfo: {e}", "command": "password_profiler"}

        target = ""
        if hash_path:
            try:
                with open(hash_path, "r") as f:
                    target = f.read().strip()
            except Exception as e:
                logger.warning(f"Cannot read hash file: {e}")
        if not target and target_hash:
            target = target_hash.strip()

        details = self._extract_details(info_text)
        candidates = self._generate_candidates(details)

        output_lines = [f"Extracted details: {details}", f"Generated {len(candidates)} candidates"]
        if target:
            for pwd in candidates:
                computed = hashlib.sha1(pwd.encode()).hexdigest()
                if computed == target:
                    output_lines.append(f"\n✅ PASSWORD FOUND: {pwd}")
                    output_lines.append(f"SHA-1({pwd}) = {computed}")
                    logger.info(f"Password found via SHA-1: {pwd}")
                    return {"success": True, "output": "\n".join(output_lines), "error": "", "command": "password_profiler"}
            output_lines.append(f"\n❌ No match found among {len(candidates)} candidates")
            output_lines.append(f"Target hash: {target}")

        if check_script and os.path.exists(check_script):
            script_dir = os.path.dirname(os.path.abspath(check_script))
            wordlist_path = os.path.join(script_dir, "passwords.txt")
            try:
                with open(wordlist_path, "w") as f:
                    for pwd in candidates:
                        f.write(pwd + "\n")
                output_lines.append(f"\nWrote {len(candidates)} candidates to {wordlist_path}")
                import subprocess
                r = subprocess.run(["python3", check_script], capture_output=True, text=True, timeout=30, cwd=script_dir)
                out = (r.stdout + r.stderr).strip()
                output_lines.append(f"Script output: {out[:500]}")
                m = re.search(r'picoCTF\{[^{}]+\}|CTF\{[^{}]+\}|flag\{[^{}]+\}', out)
                if m:
                    output_lines.append(f"\n✅ PASSWORD FOUND via script: {m.group()}")
                    return {"success": True, "output": "\n".join(output_lines), "error": "", "command": "password_profiler"}
                if "password found" in out.lower():
                    output_lines.append(f"\n✅ PASSWORD FOUND via script!")
            except Exception as e:
                output_lines.append(f"\nScript error: {e}")

        return {"success": True, "output": "\n".join(output_lines), "error": "", "command": "password_profiler"}

    def _extract_details(self, text: str) -> dict:
        d = {
            "name": "", "first_name": "", "last_name": "",
            "birth_year": "", "birth_date": "", "pet": "",
            "city": "", "school": "", "company": "",
            "partner": "", "child": "", "nickname": "",
            "interests": [], "keywords": [],
        }
        for line in text.splitlines():
            line = line.strip()
            if ":" not in line and "=" not in line:
                continue
            lower = line.lower()
            # Match "First Name: Alice", "Surname: Johnson", "Nickname: AJ", etc.
            m = re.search(r'(?:first\s*name|fname)\s*[=:]\s*(.+)', lower)
            if m: d["first_name"] = m.group(1).strip()
            m = re.search(r'(?:surname|last\s*name|lname|family)\s*[=:]\s*(.+)', lower)
            if m: d["last_name"] = m.group(1).strip()
            m = re.search(r'(?:nickname|nick)\s*[=:]\s*(.+)', lower)
            if m: d["nickname"] = m.group(1).strip()
            # name= but NOT "Partner's Name:" or "Child's Name:" or "First Name:"
            m = re.search(r'(?<!\'s\s)(?<!first\s)(?<!partner\'s\s)(?<!child\'s\s)\bname\s*[=:]\s*(.+)', lower)
            if m and "partner" not in lower and "child" not in lower and "first" not in lower and "surname" not in lower:
                d["name"] = m.group(1).strip()
            m = re.search(r'(?:birth\s*(?:year|date)|yob|dob|date\s*of\s*birth)\s*[=:]\s*(\S+)', lower)
            if m:
                d["birth_date"] = m.group(1).strip()
                y = re.search(r'(\d{4})', d["birth_date"])
                if y:
                    d["birth_year"] = y.group(1)
            m = re.search(r'(?:partner|spouse|husband|wife)\s*(?:\'s)?\s*name\s*[=:]\s*(.+)', lower)
            if m: d["partner"] = m.group(1).strip()
            m = re.search(r'(?:child|son|daughter)\s*(?:\'s)?\s*name\s*[=:]\s*(.+)', lower)
            if m: d["child"] = m.group(1).strip()
            m = re.search(r'\b(pet|dog|cat|animal)\s*[=:]\s*(.+)', lower)
            if m: d["pet"] = m.group(1).strip()
            m = re.search(r'\b(city|town|location)\s*[=:]\s*(.+)', lower)
            if m: d["city"] = m.group(1).strip()
            m = re.search(r'\b(school|university|college)\s*[=:]\s*(.+)', lower)
            if m: d["school"] = m.group(1).strip()
            for word in line.split():
                w = word.strip(",:;.!?")
                if len(w) > 3 and w.isalpha():
                    d["keywords"].append(w)
        return d

    def _generate_candidates(self, d: dict) -> list:
        values = [v.strip().lower() for v in [
            d.get("first_name", ""), d.get("last_name", ""), d.get("nickname", ""),
            d.get("name", ""), d.get("partner", ""), d.get("child", ""),
            d.get("pet", ""), d.get("city", ""), d.get("school", ""),
        ] if v.strip()]
        nums = d.get("birth_year", ""), d.get("birth_date", "")
        base = values[0] if values else "user"
        candidates = set()

        # Each individual value (all cases)
        for v in values:
            candidates.add(v)
            candidates.add(v.capitalize())
            candidates.add(v.upper())

        # Each value + each other value and number
        all_parts = values + [n for n in nums if n]
        for a in all_parts:
            for b in all_parts:
                if a != b:
                    for sep in ["", ".", "_", "-", "!", "@", "#"]:
                        candidates.add(f"{a}{sep}{b}")
                        candidates.add(f"{a}{sep}{b}".capitalize())
                        candidates.add(f"{a}{sep}{b}".upper())

        # Value + number suffixes
        suffixes = ["123", "1234", "12345", "1", "!",
                     "2023", "2024", "2025", "2026",
                     "1990", "1991", "1992"]
        for v in values:
            for s in suffixes:
                candidates.add(f"{v}{s}")
                candidates.add(f"{v.capitalize()}{s}")
                candidates.add(f"{s}{v}")
                candidates.add(f"{v}_{s}")

        # Date patterns
        dates = [n for n in nums if n]
        for dt in dates:
            clean = dt.replace("-", "").replace("/", "").replace(".", "")
            candidates.add(clean)
            candidates.add(clean[:2])  # DD
            candidates.add(clean[2:4])  # MM
            candidates.add(clean[4:])  # YYYY
            # DDMM, MMDD, DDMMYYYY, MMDDYYYY
            if len(clean) == 8:
                candidates.add(clean[:4])  # DDMM
                candidates.add(clean[2:6])  # MMDD

        # Initial-based (first letter of first name + surname)
        if d.get("first_name") and d.get("last_name"):
            fi = d["first_name"][0].lower()
            ln = d["last_name"].lower()
            candidates.add(f"{fi}{ln}")
            candidates.add(f"{fi}{ln}123")
            candidates.add(f"{fi}.{ln}")
            candidates.add(f"{fi}_{ln}")

        # Common weak passwords
        for common in ["password", "password123", "admin", "letmein", "welcome",
                       "qwerty", "123456", "12345678", "football", "monkey",
                       "iloveyou", "sunshine", "princess", "abc123",
                       "qwerty123", "1q2w3e4r", "111111", "000000"]:
            candidates.add(common)

        return list(candidates)
