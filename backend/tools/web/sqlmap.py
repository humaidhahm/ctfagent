import os
from backend.tools.base import BaseTool
from loguru import logger


class SQLMapTool(BaseTool):
    name = "sqlmap"
    description = "Automated SQL injection detection and exploitation tool"

    async def run(self, url: str = "", data: str = None, level: int = 1, risk: int = 1) -> dict:
        if not url:
            return {"success": False, "output": "", "error": "No url provided", "command": "web/sqlmap.py"}
        output_dir = "/tmp/sqlmap_out"
        os.makedirs(output_dir, exist_ok=True)
        cmd = [
            "sqlmap", "-u", url,
            "--batch",
            "--level", str(level),
            "--risk", str(risk),
            "--dump",
            "--output-dir", output_dir,
            "--forms",
            "--random-agent",
        ]
        if data:
            cmd += ["--data", data]

        result = await self._exec(cmd)
        if result["success"]:
            logger.info(f"sqlmap completed on {url}")
        return result
