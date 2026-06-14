from backend.tools.base import BaseTool
from loguru import logger


class StringsTool(BaseTool):
    name = "strings_tool"
    description = "Extract printable strings from binary files"

    async def run(self, filepath: str = "", min_length: int = 4) -> dict:
        if not filepath:
            return {"success": False, "output": "", "error": "No filepath provided", "command": "pwn/strings_tool.py"}
        cmd = ["strings", "-n", str(min_length), filepath]
        result = await self._exec(cmd)
        if result["success"]:
            lines = result["output"].splitlines()
            interesting = [
                line for line in lines
                if any(kw in line.lower() for kw in
                       ["flag", "ctf", "pico", "secret", "password", "key", "http",
                        "admin", "user", "login", "token", "{", "}", "debug"])
            ]
            if interesting:
                result["interesting_strings"] = interesting[:50]
                logger.info(f"strings found {len(interesting)} interesting strings in {filepath}")
        return result
