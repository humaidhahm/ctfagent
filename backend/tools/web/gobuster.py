from backend.tools.base import BaseTool
from loguru import logger


class GobusterTool(BaseTool):
    name = "gobuster"
    description = "Directory/file enumeration tool"

    async def run(self, url: str = "", wordlist: str = "/usr/share/wordlists/dirb/common.txt",
                  extensions: str = "php,html,txt,bak") -> dict:
        if not url:
            return {"success": False, "output": "", "error": "No url provided", "command": "gobuster"}
        cmd = [
            "gobuster", "dir",
            "-u", url,
            "-w", wordlist,
            "-t", "20",
            "--no-error",
            "-q",
        ]
        if extensions and extensions not in ("false", "true", ""):
            cmd.extend(["-x", extensions])
        result = await self._exec(cmd)
        if result["success"]:
            discovered = []
            for line in result["output"].splitlines():
                if "Status:" in line or "/" in line and any(c.isdigit() for c in line[:10]):
                    discovered.append(line.strip())
            if discovered:
                logger.info(f"gobuster discovered {len(discovered)} paths on {url}")
        return result
