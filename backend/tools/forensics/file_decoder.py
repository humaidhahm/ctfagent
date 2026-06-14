import os
import base64
from pathlib import Path
from backend.tools.base import BaseTool
from loguru import logger


class FileDecoderTool(BaseTool):
    name = "file_decoder"
    description = "Read a file, detect and decode base64/hex encoded content, save decoded output to a new file."

    async def run(self, filepath: str = "", output_filename: str = "") -> dict:
        if not filepath:
            return {"success": False, "output": "", "error": "No filepath provided", "command": "file_decoder"}

        filepath = Path(filepath)
        if not filepath.exists():
            return {"success": False, "output": "", "error": f"File not found: {filepath}", "command": "file_decoder"}

        raw = filepath.read_bytes()
        text = raw.decode("latin-1").strip()

        decoded = None
        method = ""

        # Try base64
        try:
            decoded = base64.b64decode(text)
            method = "base64"
            logger.info(f"file_decoder: detected base64 encoding in {filepath}")
        except Exception:
            pass

        # Try hex if no base64
        if decoded is None:
            clean = "".join(c for c in text if c in "0123456789abcdefABCDEF")
            if len(clean) > 10 and len(clean) == len(text.replace(" ", "").replace("\n", "")):
                try:
                    decoded = bytes.fromhex(clean)
                    method = "hex"
                    logger.info(f"file_decoder: detected hex encoding in {filepath}")
                except Exception:
                    pass

        if decoded is None:
            return {
                "success": False,
                "output": f"No encoding detected in {filepath}. File is {len(raw)} bytes, first 100 chars: {text[:100]}",
                "error": "Could not detect base64 or hex encoding",
                "command": f"file_decoder {filepath}",
            }

        out_dir = filepath.parent
        out_name = output_filename or (filepath.stem + "_decoded" + filepath.suffix)
        out_path = out_dir / out_name

        out_path.write_bytes(decoded)

        import magic
        mime = magic.from_file(str(out_path), mime=True)

        result = {
            "success": True,
            "output": (
                f"Decoded {filepath} ({len(raw)} bytes) using {method}\n"
                f"Output: {out_path} ({len(decoded)} bytes, {mime})\n"
                f"Output filepath: {out_path}"
            ),
            "error": "",
            "command": f"file_decoder {filepath}",
            "decoded_filepath": str(out_path),
            "decoded_size": len(decoded),
            "decoded_mime": mime,
            "encoding": method,
        }
        logger.info(f"file_decoder: {filepath} -> {out_path} ({len(decoded)} bytes, {mime})")
        return result
