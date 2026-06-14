import json
import os
import uuid
from backend.tools.base import BaseTool
from loguru import logger


class FfufTool(BaseTool):
    name = "ffuf"
    description = "Fast web fuzzer for parameter discovery"

    async def run(self, url: str = "", wordlist: str = "/usr/share/wordlists/dirb/common.txt",
                  fc: str = "404") -> dict:
        if not url:
            return {"success": False, "output": "", "error": "No url provided", "command": "ffuf"}
        outfile = f"/tmp/ffuf_out_{uuid.uuid4().hex}.json"
        cmd = [
            "ffuf", "-u", url, "-w", wordlist,
            "-fc", fc, "-t", "20",
            "-o", outfile, "-of", "json", "-s",
        ]
        result = await self._exec(cmd)
        if os.path.exists(outfile):
            try:
                with open(outfile) as f:
                    data = json.load(f)
                results = data.get("results", [])
                if results:
                    parsed = [
                        {"url": r.get("url"), "status": r.get("status"), "length": r.get("length")}
                        for r in results
                    ]
                    result["parsed_results"] = parsed
                    logger.info(f"ffuf found {len(parsed)} results for {url}")
                os.remove(outfile)
            except Exception as e:
                logger.warning(f"ffuf parse error: {e}")
        return result
