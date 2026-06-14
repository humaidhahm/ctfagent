import asyncio
import signal
from typing import Optional
from backend.config.settings import settings
from loguru import logger


class BaseTool:
    name: str = ""
    description: str = ""

    async def run(self, **kwargs) -> dict:
        raise NotImplementedError

    async def _exec(
        self,
        cmd: list[str],
        input_data: Optional[str] = None,
        cwd: Optional[str] = None,
    ) -> dict:
        proc = None
        try:
            logger.info(f"Executing: {' '.join(cmd)}")
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE if input_data else None,
                cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=input_data.encode() if input_data else None),
                timeout=settings.max_tool_timeout_seconds,
            )
            out_text = stdout.decode(errors="replace") if stdout else ""
            err_text = stderr.decode(errors="replace") if stderr else ""
            output = out_text + err_text
            if len(output) > 4000:
                output = output[:2000] + "\n...[TRUNCATED]...\n" + output[-1000:]
            return {
                "success": proc.returncode == 0,
                "output": output,
                "error": err_text if proc.returncode != 0 else "",
                "command": " ".join(cmd),
            }
        except asyncio.TimeoutError:
            msg = f"Tool timed out after {settings.max_tool_timeout_seconds}s"
            logger.warning(f"{' '.join(cmd)}: {msg}")
            partial_out = ""
            partial_err = ""
            if proc:
                try:
                    proc.kill()
                    await asyncio.wait_for(proc.wait(), timeout=5)
                    if proc.stdout:
                        partial_out = (await proc.stdout.read()).decode(errors="replace")
                    if proc.stderr:
                        partial_err = (await proc.stderr.read()).decode(errors="replace")
                except Exception:
                    try:
                        proc.send_signal(signal.SIGKILL)
                    except Exception:
                        pass
            output = partial_out + partial_err
            if len(output) > 4000:
                output = output[:2000] + "\n...[TRUNCATED]...\n" + output[-1000:]
            return {
                "success": False,
                "output": output if output else "",
                "error": msg,
                "command": " ".join(cmd),
            }
        except FileNotFoundError:
            msg = f"Command not found: {cmd[0]}"
            logger.error(msg)
            return {"success": False, "output": "", "error": msg, "command": " ".join(cmd)}
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {"success": False, "output": "", "error": str(e), "command": " ".join(cmd)}
