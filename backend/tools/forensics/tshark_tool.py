import os
import uuid
from backend.tools.base import BaseTool
from loguru import logger


class TsharkTool(BaseTool):
    name = "tshark"
    description = "Analyze pcap files with tshark"

    async def run(self, filepath: str = "", filter_expr: str = None, follow_stream: bool = False) -> dict:
        if not filepath:
            return {"success": False, "output": "", "error": "No filepath provided", "command": "forensics/tshark_tool.py"}
        outputs = []

        # Mode 1: Protocol hierarchy
        cmd1 = ["tshark", "-r", filepath, "-q", "-z", "io,phs"]
        result1 = await self._exec(cmd1)
        if result1["success"]:
            outputs.append("=== PROTOCOL HIERARCHY ===")
            outputs.append(result1["output"])

        # Mode 2: HTTP objects export
        export_dir = f"/tmp/tshark_http_{uuid.uuid4().hex}"
        os.makedirs(export_dir, exist_ok=True)
        cmd2 = ["tshark", "-r", filepath, "--export-objects", f"http,{export_dir}"]
        result2 = await self._exec(cmd2)
        if result2["success"]:
            exported_files = os.listdir(export_dir)
            if exported_files:
                outputs.append(f"\n=== HTTP OBJECTS ({len(exported_files)} files) ===")
                outputs.append(str(exported_files))
                for fn in exported_files[:5]:
                    fp = os.path.join(export_dir, fn)
                    if os.path.isfile(fp) and os.path.getsize(fp) < 10000:
                        with open(fp, errors="replace") as f:
                            outputs.append(f"\n--- {fn} ---\n{f.read()[:1000]}")

        # Mode 3: DNS queries
        cmd3 = ["tshark", "-r", filepath, "-Y", "dns.flags.response == 0", "-T", "fields",
                "-e", "dns.qry.name", "-e", "dns.qry.type"]
        result3 = await self._exec(cmd3)
        if result3["success"] and result3["output"].strip():
            outputs.append(f"\n=== DNS QUERIES ===")
            outputs.append(result3["output"][:2000])

        # Mode 4: Follow TCP streams (first 3)
        if follow_stream:
            for stream_id in range(3):
                cmd4 = ["tshark", "-r", filepath, "-q", "-z", f"follow,tcp,ascii,{stream_id}"]
                result4 = await self._exec(cmd4)
                if result4["success"] and result4["output"].strip():
                    outputs.append(f"\n=== TCP STREAM {stream_id} ===")
                    outputs.append(result4["output"][:2000])

        # Mode 5: Custom filter
        if filter_expr:
            cmd5 = ["tshark", "-r", filepath, "-Y", filter_expr, "-T", "json"]
            result5 = await self._exec(cmd5)
            if result5["success"]:
                outputs.append(f"\n=== CUSTOM FILTER: {filter_expr} ===")
                outputs.append(result5["output"][:2000])

        combined = "\n".join(outputs) if outputs else "No analyzable data found"
        return {
            "success": True,
            "output": combined,
            "error": "",
        }
