import os
import uuid
import httpx
from pathlib import Path
from backend.config.settings import settings
from backend.tools.base import BaseTool
from loguru import logger
from rich.progress import (
    Progress, BarColumn, TextColumn, DownloadColumn,
    TransferSpeedColumn, TimeRemainingColumn,
)


class DownloadFileTool(BaseTool):
    name = "download_file"
    description = "Download a file from a URL and save it locally. Returns the local filepath and metadata."

    async def run(self, url: str = "", output_dir: str = "") -> dict:
        if not url:
            return {"success": False, "output": "", "error": "No url provided", "command": "download_file"}

        out_dir = output_dir or settings.upload_dir
        os.makedirs(out_dir, exist_ok=True)

        try:
            async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
                async with client.stream("GET", url) as resp:
                    if resp.status_code >= 400:
                        return {
                            "success": False,
                            "output": "",
                            "error": f"HTTP {resp.status_code} fetching {url}",
                            "command": f"download_file {url}",
                        }

                    total = int(resp.headers.get("content-length", 0))
                    filename = os.path.basename(url.split("?")[0]) or f"download_{uuid.uuid4().hex}"
                    filepath = os.path.join(out_dir, filename)

                    progress = Progress(
                        TextColumn("[cyan]{task.description}"),
                        BarColumn(),
                        DownloadColumn(),
                        TransferSpeedColumn(),
                        TimeRemainingColumn(),
                    )
                    with progress:
                        task = progress.add_task(f"[cyan]Downloading {filename}", total=total)
                        with open(filepath, "wb") as f:
                            async for chunk in resp.aiter_bytes():
                                f.write(chunk)
                                progress.update(task, advance=len(chunk))

                import magic
                mime = magic.from_file(filepath, mime=True)
                size = os.path.getsize(filepath)

                result = {
                    "success": True,
                    "output": f"Downloaded {size} bytes to {filepath}\nMIME type: {mime}",
                    "error": "",
                    "command": f"download_file {url}",
                    "filepath": filepath,
                    "size_bytes": size,
                    "mime_type": mime,
                    "filename": filename,
                }
                logger.info(f"download_file: {url} -> {filepath} ({size} bytes, {mime})")
                return result
        except Exception as e:
            logger.error(f"download_file error: {e}")
            return {"success": False, "output": "", "error": str(e), "command": f"download_file {url}"}
