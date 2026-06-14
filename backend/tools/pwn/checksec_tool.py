import json
from backend.tools.base import BaseTool
from loguru import logger


class ChecksecTool(BaseTool):
    name = "checksec"
    description = "Check binary security protections (PIE, NX, Canary, RELRO)"

    async def run(self, filepath: str = "") -> dict:
        if not filepath:
            return {"success": False, "output": "", "error": "No filepath provided", "command": "pwn/checksec_tool.py"}
        if filepath == "json":
            return {"success": False, "output": "", "error": "Invalid filepath 'json' — pass the actual binary path", "command": "pwn/checksec_tool.py"}
        cmd = ["checksec", "--file", filepath]
        result = await self._exec(cmd)
        if result["success"]:
            lines = result["output"].strip().split("\n")
            fmt = ["Binary protections:"]
            for line in lines:
                line = line.strip()
                if ":" in line and not line.startswith("[*]"):
                    fmt.append(f"  {line.strip()}")
            if len(fmt) > 1:
                result["output"] = "\n".join(fmt)
            logger.info(f"checksec analyzed {filepath}")
        return result
