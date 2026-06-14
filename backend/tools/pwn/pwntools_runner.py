import os
import uuid
import tempfile
import re
from backend.tools.base import BaseTool
from loguru import logger


class PwntoolsRunnerTool(BaseTool):
    name = "pwntools_runner"
    description = "Run a pwntools exploit script against a binary or remote target. Use this for multi-step remote interactions (leak-compute-send)."

    async def run(self, binary_path: str = None, exploit_script: str = None,
                  target_host: str = None, target_port: int = None,
                  host: str = None, port: int = None) -> dict:
        if not exploit_script:
            return {"success": False, "output": "No exploit script provided", "error": ""}

        target_host = target_host or host
        target_port = target_port or port

        # Fix common LLM escaping issues in exploit_script
        # The LLM often outputs \n (literal backslash-n) instead of actual newlines
        script = exploit_script.replace("\\n", "\n").replace("\\t", "\t")
        # Fix double-escaped quotes: \\\" -> \"
        script = script.replace('\\"', '"')
        # Fix double-escaped backslash-n that sometimes happens
        script = script.replace("\\\\n", "\n")
        # Strip any trailing/leading whitespace
        script = script.strip()

        script_path = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                if binary_path:
                    script = script.replace("/challenge/binary", binary_path)
                if target_host and target_port:
                    script = script.replace(
                        "# For remote: p = remote('HOST', PORT)",
                        f"p = remote('{target_host}', {target_port})"
                    )
                    script = script.replace(
                        'p = process("./challenge/binary")',
                        f"p = remote('{target_host}', {target_port})"
                    )
                f.write(script)
                script_path = f.name

            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            cmd = ["python3", script_path]
            result = await self._exec(cmd)

            if result["success"]:
                logger.info("pwntools exploit executed successfully")
            else:
                logger.warning(f"pwntools exploit failed: {result['error'][:200]}")

            return result
        except Exception as e:
            logger.error(f"pwntools runner error: {e}")
            return {"success": False, "output": "", "error": str(e), "command": "python3 exploit.py"}
        finally:
            if script_path and os.path.exists(script_path):
                os.unlink(script_path)
