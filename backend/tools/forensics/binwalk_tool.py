import uuid
from backend.tools.base import BaseTool
from loguru import logger


class BinwalkTool(BaseTool):
    name = "binwalk"
    description = "Analyze and extract embedded files from firmware/images"

    async def run(self, filepath: str = "", extract: bool = False) -> dict:
        if not filepath:
            return {"success": False, "output": "", "error": "No filepath provided", "command": "forensics/binwalk_tool.py"}
        cmd = ["binwalk", "--signature"]
        extract_dir = f"/tmp/binwalk_{uuid.uuid4().hex}"
        if extract:
            cmd += ["--extract", "--directory", extract_dir, "--run-as=root"]
        cmd.append(filepath)

        result = await self._exec(cmd)
        if result["success"]:
            embedded = []
            for line in result["output"].splitlines():
                if any(x in line for x in ["JPEG", "PNG", "ZIP", "gzip", "bzip2", "ELF", "DLL",
                                            "LZMA", "FAT", "ext2", "ext3", "ext4", "Squashfs"]):
                    embedded.append(line.strip())
            if embedded:
                logger.info(f"binwalk found {len(embedded)} embedded signatures in {filepath}")
                result["embedded_signatures"] = embedded
        return result
