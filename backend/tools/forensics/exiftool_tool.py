import json
from backend.tools.base import BaseTool
from loguru import logger


class ExifToolTool(BaseTool):
    name = "exiftool"
    description = "Read metadata from files using exiftool"

    async def run(self, filepath: str = "", input: str = "", filename: str = "", path: str = "") -> dict:
        filepath = filepath or input or filename or path
        cmd = ["exiftool", "-j", filepath]
        result = await self._exec(cmd)
        if result["success"]:
            try:
                parsed = json.loads(result["output"])
                if isinstance(parsed, list) and len(parsed) > 0:
                    result["metadata"] = parsed[0]
                    flat = []
                    for k, v in parsed[0].items():
                        if isinstance(v, str) and v.strip():
                            flat.append(f"{k}: {v}")
                    result["output"] = "\n".join(flat)
                    logger.info(f"exiftool read {len(flat)} fields from {filepath}")
            except json.JSONDecodeError:
                logger.warning(f"exiftool JSON parse failed for {filepath}")
        return result
