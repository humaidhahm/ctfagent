from backend.tools.base import BaseTool
from loguru import logger


class ROPgadgetTool(BaseTool):
    name = "ropgadget"
    description = "Find ROP gadgets in a binary"

    async def run(self, filepath: str = "") -> dict:
        if not filepath:
            return {"success": False, "output": "", "error": "No filepath provided", "command": "pwn/ropgadget_tool.py"}
        cmd = ["ROPgadget", "--binary", filepath, "--rop", "--badbytes", "0a"]
        result = await self._exec(cmd)
        if result["success"]:
            lines = result["output"].splitlines()
            useful = [l for l in lines if any(x in l.lower() for x in
                      ["pop rdi", "pop rsi", "pop rdx", "pop rax", "syscall",
                       "int 0x80", "ret", "/bin/sh", "system", "execve"])]
            if useful:
                result["useful_gadgets"] = useful[:30]
                logger.info(f"ROPgadget found {len(useful)} useful gadgets in {filepath}")
        return result
