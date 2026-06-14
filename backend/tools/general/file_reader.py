from backend.tools.base import BaseTool
from loguru import logger


class FileReaderTool(BaseTool):
    name = "file_reader"
    description = "Read the contents of a text file"

    async def run(self, filepath: str = "") -> dict:
        if not filepath:
            return {"success": False, "output": "", "error": "No filepath provided", "command": "file_reader"}
        try:
            with open(filepath, "r", errors="replace") as f:
                content = f.read()
            if len(content) > 5000:
                content = content[:2500] + "\n...[TRUNCATED]...\n" + content[-1000:]
            logger.info(f"file_reader read {filepath} ({len(content)} bytes)")
            return {"success": True, "output": content, "error": "", "command": f"cat {filepath}"}
        except Exception as e:
            logger.error(f"file_reader error: {e}")
            return {"success": False, "output": "", "error": str(e), "command": f"cat {filepath}"}
