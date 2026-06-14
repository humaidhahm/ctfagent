from backend.tools.base import BaseTool
from loguru import logger


class Radare2Tool(BaseTool):
    name = "radare2"
    description = "Reverse engineer binaries with radare2"

    async def run(self, filepath: str = "", commands: list[str] = None) -> dict:
        if not filepath:
            return {"success": False, "output": "", "error": "No filepath provided", "command": "re/radare2_tool.py"}
        commands = commands or ["aaa", "s main", "pdf"]
        cmd = ["r2", "-q", "-c", "; ".join(commands), filepath]
        result = await self._exec(cmd)
        if result["success"]:
            output_len = len(result["output"])
            logger.info(f"radare2 executed {len(commands)} commands on {filepath} ({output_len} chars)")
        return result
