import hashlib
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Optional
import aiofiles
import magic
import httpx
from loguru import logger

from backend.core.manifest import ChallengeManifest, FileAttachment, ChallengeCategory


URL_REGEX = re.compile(r'https?://[^\s\'\"<>]+')
IP_PORT_REGEX = re.compile(r'(\d{1,3}(?:\.\d{1,3}){3}):(\d+)')
HOST_PORT_REGEX = re.compile(r'(?:host|server|connect to)\s*[:\s]+([a-zA-Z0-9.-]+)\s*(?:port|:)\s*(\d+)', re.IGNORECASE)
NC_REGEX = re.compile(r'(?:^|\s)nc\s+([a-zA-Z0-9.-]+)\s+(\d+)')
FLAG_FORMAT_REGEX = re.compile(r'((?:[A-Za-z0-9_]+)?(?:CTF|flag|FLAG)\{[^}]+\})')


async def compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    async with aiofiles.open(filepath, "rb") as f:
        while chunk := await f.read(8192):
            h.update(chunk)
    return h.hexdigest()


async def ingest_challenge(
    description: str,
    name: str,
    upload_dir: str,
    files: Optional[list[tuple[str, bytes, str]]] = None,
    target_url: Optional[str] = None,
    target_host: Optional[str] = None,
    target_port: Optional[int] = None,
    flag_format: Optional[str] = None,
    title: Optional[str] = None,
) -> ChallengeManifest:
    challenge_id = str(uuid.uuid4())
    challenge_dir = os.path.join(upload_dir, challenge_id)
    os.makedirs(challenge_dir, exist_ok=True)

    attachments: list[FileAttachment] = []
    input_types: set[str] = {"text"}

    if target_url:
        input_types.add("url")
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.head(target_url, follow_redirects=True)
                if resp.status_code >= 400:
                    logger.warning(f"URL {target_url} returned status {resp.status_code}")
        except Exception as e:
            logger.warning(f"URL {target_url} unreachable: {e}")

    if target_host:
        input_types.add("url")

    if files:
        for filename, content, content_type in files:
            filepath = os.path.join(challenge_dir, filename)
            async with aiofiles.open(filepath, "wb") as f:
                await f.write(content)

            mime_type = content_type or magic.from_file(filepath, mime=True)
            sha256 = await compute_sha256(filepath)
            size = os.path.getsize(filepath)

            attachments.append(FileAttachment(
                filename=filename,
                filepath=filepath,
                mime_type=mime_type,
                size_bytes=size,
                sha256=sha256,
            ))
            input_types.add("file")

    extracted_urls = URL_REGEX.findall(description)

    if not target_url and extracted_urls:
        target_url = extracted_urls[0]

    for url in extracted_urls:
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code < 400:
                    filename = os.path.basename(url.split("?")[0]) or f"download_{uuid.uuid4().hex}"
                    filepath = os.path.join(challenge_dir, filename)
                    with open(filepath, "wb") as f:
                        f.write(resp.content)
                    mime_type = magic.from_file(filepath, mime=True)
                    sha256 = await compute_sha256(filepath)
                    attachments.append(FileAttachment(
                        filename=filename,
                        filepath=filepath,
                        mime_type=mime_type,
                        size_bytes=len(resp.content),
                        sha256=sha256,
                    ))
                    input_types.add("file")
                    logger.info(f"Ingest downloaded {url} -> {filepath} ({len(resp.content)} bytes)")
        except Exception as e:
            logger.warning(f"Ingest failed to download {url}: {e}")

    extracted_ports = IP_PORT_REGEX.findall(description)
    extracted_hosts = HOST_PORT_REGEX.findall(description)
    extracted_nc = NC_REGEX.findall(description)

    if not target_port and extracted_ports:
        ip, port = extracted_ports[0]
        target_host = target_host or ip
        target_port = int(port)

    if not target_host and extracted_hosts:
        host, port = extracted_hosts[0]
        target_host = host
        target_port = target_port or int(port)

    if not target_host and extracted_nc:
        host, port = extracted_nc[0]
        target_host = host
        target_port = target_port or int(port)

    if not flag_format:
        fmt_matches = FLAG_FORMAT_REGEX.findall(description)
        if fmt_matches:
            flag_format = fmt_matches[0].split("{")[0] + "{...}" if "{" in fmt_matches[0] else f"{fmt_matches[0]}"

    raw_input_type = "mixed" if len(input_types) > 1 else input_types.pop() if input_types else "text"

    manifest = ChallengeManifest(
        challenge_id=challenge_id,
        title=title,
        name=name,
        description=description,
        category=ChallengeCategory.UNKNOWN,
        attachments=attachments,
        target_url=target_url,
        target_host=target_host,
        target_port=target_port,
        flag_format=flag_format,
        raw_input_type=raw_input_type,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    logger.info(f"Ingested challenge {challenge_id}: type={raw_input_type}, files={len(attachments)}, url={target_url}")
    return manifest
