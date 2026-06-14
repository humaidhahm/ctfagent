import os
import uuid
from backend.tools.base import BaseTool
from loguru import logger


class SteghideTool(BaseTool):
    name = "steghide"
    description = "Extract hidden data from JPEG/PNG/WAV using steghide"

    async def run(self, filepath: str = "", passphrase: str = "") -> dict:
        if not filepath:
            return {"success": False, "output": "", "error": "No filepath provided", "command": "forensics/steghide_tool.py"}
        common_passphrases = ["", "password", "secret", "flag", "steganography",
                              "pass", "123456", "admin", "key", "hidden",
                              os.path.splitext(os.path.basename(filepath))[0]]

        # Try provided passphrase first
        if passphrase:
            common_passphrases = [passphrase] + common_passphrases

        for pwd in common_passphrases:
            outfile = f"/tmp/steghide_{uuid.uuid4().hex}.out"
            cmd = [
                "steghide", "extract",
                "-sf", filepath,
                "-p", pwd,
                "-f",
                "-xf", outfile,
            ]
            result = await self._exec(cmd)
            if result["success"] and os.path.exists(outfile):
                with open(outfile) as f:
                    content = f.read()
                os.remove(outfile)
                logger.info(f"steghide extracted data from {filepath} with passphrase '{pwd}'")
                return {
                    "success": True,
                    "output": f"Extracted with passphrase '{pwd}':\n{content}",
                    "error": "",
                    "passphrase": pwd,
                    "extracted_content": content,
                }

        return {"success": False, "output": "No data extracted with common passphrases", "error": ""}
