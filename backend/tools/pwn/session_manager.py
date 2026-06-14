import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PersistentSession:
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    host: str
    port: int
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)


_sessions: dict[str, PersistentSession] = {}
_lock: asyncio.Lock = None
SESSION_TIMEOUT = 300


def _get_lock() -> asyncio.Lock:
    global _lock
    if _lock is None:
        _lock = asyncio.Lock()
    return _lock


async def create_session(host: str, port: int, connect_timeout: float = 10.0) -> str:
    session_id = f"{host}:{port}"
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(host, port),
        timeout=connect_timeout,
    )
    async with _get_lock():
        old = _sessions.get(session_id)
        if old:
            try:
                old.writer.close()
                await old.writer.wait_closed()
            except Exception:
                pass
        _sessions[session_id] = PersistentSession(reader, writer, host, port)
    return session_id


def _get_session(session_id: str) -> Optional[PersistentSession]:
    s = _sessions.get(session_id)
    if s:
        s.last_used = time.time()
    return s


def has_session(session_id: str) -> bool:
    return session_id in _sessions


async def read_session(session_id: str, read_timeout: float = 3.0, max_bytes: int = 10000) -> str:
    session = _get_session(session_id)
    if not session:
        return ""
    response = b""
    try:
        while True:
            chunk = await asyncio.wait_for(session.reader.read(4096), timeout=read_timeout)
            if not chunk:
                break
            response += chunk
            if len(response) >= max_bytes:
                break
    except (asyncio.TimeoutError, ConnectionResetError):
        pass
    return response.decode(errors="replace")


async def write_session(session_id: str, data: str, append_newline: bool = False) -> None:
    session = _get_session(session_id)
    if not session:
        return
    payload = (data + "\n" if append_newline else data).encode()
    try:
        session.writer.write(payload)
        await session.writer.drain()
    except Exception:
        raise


async def close_session(session_id: str) -> bool:
    async with _get_lock():
        session = _sessions.pop(session_id, None)
        if not session:
            return False
        try:
            session.writer.close()
            await session.writer.wait_closed()
        except Exception:
            pass
        return True


async def close_all_sessions() -> int:
    async with _get_lock():
        ids = list(_sessions.keys())
        for sid in ids:
            s = _sessions.pop(sid, None)
            if s:
                try:
                    s.writer.close()
                except Exception:
                    pass
        return len(ids)


async def cleanup_stale_sessions(max_age: float = SESSION_TIMEOUT) -> int:
    now = time.time()
    stale = [sid for sid, s in list(_sessions.items()) if now - s.last_used > max_age]
    for sid in stale:
        await close_session(sid)
    return len(stale)
