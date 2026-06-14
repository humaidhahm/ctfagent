from backend.tools.base import BaseTool
from loguru import logger


class ZstegTool(BaseTool):
    name = "zsteg"
    description = "Detect LSB steganography in PNG/BMP files"

    async def run(self, filepath: str = "") -> dict:
        if not filepath:
            return {"success": False, "output": "", "error": "No filepath provided", "command": "forensics/zsteg_tool.py"}
        cmd = ["zsteg", "--all", filepath]
        result = await self._exec(cmd)
        if result["success"] and result["output"].strip():
            channels = []
            for line in result["output"].splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("meta") and not stripped.startswith("bmp"):
                    channels.append(stripped)
            if channels:
                logger.info(f"zsteg found {len(channels)} channels in {filepath}")
                result["channels"] = channels
        return result
