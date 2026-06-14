import os
import re
import hashlib
import subprocess
import tempfile
from backend.tools.base import BaseTool
from loguru import logger


class CuppTool(BaseTool):
    name = "cupp"
    description = "Generate password wordlist from personal details using CUPP, then test against hash"

    async def run(self, userinfo_path: str = "", hash_path: str = "",
                  check_script: str = "", output_dir: str = "") -> dict:
        if not userinfo_path:
            return {"success": False, "output": "", "error": "No userinfo file provided", "command": "cupp"}
        try:
            with open(userinfo_path, "r", errors="replace") as f:
                info_text = f.read()
        except Exception as e:
            return {"success": False, "output": "", "error": f"Cannot read userinfo: {e}", "command": "cupp"}

        details = self._parse_userinfo(info_text)
        tmpdir = output_dir or tempfile.mkdtemp(prefix="cupp_")
        output_lines = [f"Generated CUPP config from: {details}"]

        stdin_answers = self._build_stdin_answers(details)
        try:
            r = subprocess.run(
                ["python3", "/usr/share/cupp/cupp.py", "-i", "-q"],
                input=stdin_answers,
                capture_output=True, text=True, timeout=60, cwd=tmpdir
            )
            out = r.stdout + r.stderr
            output_lines.append(f"CUPP output: {out[:500]}")
            wordlist_path = None
            for fname in sorted(os.listdir(tmpdir), key=lambda x: os.path.getmtime(os.path.join(tmpdir, x)), reverse=True):
                if fname.endswith(".txt"):
                    wordlist_path = os.path.join(tmpdir, fname)
                    break
        except Exception as e:
            output_lines.append(f"CUPP error: {e}")
            return {"success": False, "output": "\n".join(output_lines), "error": str(e), "command": "cupp"}

        if not wordlist_path or not os.path.exists(wordlist_path):
            output_lines.append("CUPP did not generate a wordlist file")
            return {"success": False, "output": "\n".join(output_lines), "error": "No wordlist generated", "command": "cupp"}

        with open(wordlist_path, errors="replace") as f:
            wordlist_content = f.read()
        wordlist_lines = [w.strip() for w in wordlist_content.splitlines() if w.strip()]
        output_lines.append(f"Wordlist generated: {wordlist_path} ({len(wordlist_lines)} candidates)")

        # Try SHA-1 match
        target_hash = ""
        if hash_path:
            try:
                with open(hash_path) as f:
                    target_hash = f.read().strip()
                for pwd in wordlist_lines:
                    if pwd and hashlib.sha1(pwd.encode()).hexdigest() == target_hash:
                        output_lines.append(f"\n\u2705 PASSWORD FOUND: {pwd}")
                        output_lines.append(f"Flag: picoCTF{{{pwd}}}")
                        return {"success": True, "output": "\n".join(output_lines), "error": "", "command": "cupp"}
                output_lines.append(f"\nNo SHA-1 match in {len(wordlist_lines)} candidates")
            except Exception as e:
                output_lines.append(f"\nHash check error: {e}")

        # Try running check_script
        if check_script and os.path.exists(check_script):
            script_dir = os.path.dirname(os.path.abspath(check_script))
            target_wl = os.path.join(script_dir, "passwords.txt")
            try:
                with open(wordlist_path, errors="replace") as src_f:
                    with open(target_wl, "w") as dst_f:
                        dst_f.write(src_f.read())
                r = subprocess.run(["python3", check_script], capture_output=True, text=True, timeout=30, cwd=script_dir)
                script_out = (r.stdout + r.stderr).strip()
                output_lines.append(f"\ncheck_password.py output: {script_out[:500]}")
                m = re.search(r'picoCTF\{[^{}]+\}|CTF\{[^{}]+\}', script_out)
                if m:
                    output_lines.append(f"\n\u2705 FLAG FOUND: {m.group()}")
                    return {"success": True, "output": "\n".join(output_lines), "error": "", "command": "cupp"}
                if "password found" in script_out.lower() or "found" in script_out.lower():
                    output_lines.append(f"\n\u2705 Password found via script!")
            except Exception as e:
                output_lines.append(f"\nScript error: {e}")

        return {"success": True, "output": "\n".join(output_lines), "error": "", "command": "cupp"}

    def _build_stdin_answers(self, d: dict) -> str:
        fn = d.get("first_name", "").lower()
        sn = d.get("surname", "").lower()
        nn = d.get("nickname", "").lower()
        bd = d.get("birthdate", "").strip()
        bd_ddmmyyyy = ""
        if bd:
            parts = re.split(r'[\-/.\s]+', bd)
            if len(parts) == 3:
                day, month, year = parts[0], parts[1], parts[2]
                if len(year) == 4:
                    bd_ddmmyyyy = day.zfill(2) + month.zfill(2) + year
        pn = d.get("partner", "").lower()
        cn = d.get("child", "").lower()
        lines = [
            fn or "alice",
            sn,
            nn or "",
            bd_ddmmyyyy,
            "",
            pn,
            "",
            "",
            cn,
            "",
            "",
            "",
            "",
            "",
            "",
            "n",
            "n",
            "n",
        ]
        return "\n".join(lines)

    def _parse_userinfo(self, text: str) -> dict:
        d = {"first_name": "", "surname": "", "nickname": "",
             "birthdate": "", "partner": "", "child": ""}
        for line in text.splitlines():
            lower = line.lower()
            m = re.search(r'(?:first\s*name|fname)\s*[=:]\s*(.+)', lower)
            if m: d["first_name"] = m.group(1).strip()
            m = re.search(r'(?:surname|last\s*name|lname)\s*[=:]\s*(.+)', lower)
            if m: d["surname"] = m.group(1).strip()
            m = re.search(r'(?:nickname|nick)\s*[=:]\s*(.+)', lower)
            if m: d["nickname"] = m.group(1).strip()
            m = re.search(r'(?:birth\s*date|dob|date\s*of\s*birth)\s*[=:]\s*(.+)', lower)
            if m: d["birthdate"] = m.group(1).strip()
            m = re.search(r"partner(?:\'s)?\s*name\s*[=:]\s*(.+)", lower)
            if m: d["partner"] = m.group(1).strip()
            m = re.search(r"(?:child|son|daughter)(?:\'s)?\s*name\s*[=:]\s*(.+)", lower)
            if m: d["child"] = m.group(1).strip()
        return d
