import asyncio
from backend.tools.base import BaseTool
from backend.tools.pwn.session_manager import (
    create_session,
    has_session,
    read_session,
    write_session,
    close_session,
    _sessions,
)
from loguru import logger


def _available_sessions() -> str:
    if not _sessions:
        return "No active sessions."
    return "Active sessions: " + ", ".join(sorted(_sessions.keys()))


class RemoteConnectTool(BaseTool):
    name = "remote_connect"
    description = "Connect to a remote host:port, send data, and receive response. Automatically reuses existing persistent sessions when called with the same host and port."
    parameters = {
        "host": {"type": "string", "description": "Target hostname or IP"},
        "port": {"type": "integer", "description": "Target port"},
        "data": {"type": "string", "description": "Data/command to send (omit to just read the prompt)"},
        "timeout": {"type": "integer", "description": "Read timeout in seconds (default: 5)"},
        "newline": {"type": "boolean", "description": "Append newline to data (default: false)"},
        "session_id": {"type": "string", "description": "(Optional) Exact session_id string from a previous remote_connect output"},
        "close_session": {"type": "boolean", "description": "Set to true to close the session after reading"},
    }

    async def run(self, host: str = "", port: int = 0, **kwargs) -> dict:
        host = kwargs.pop("target_host", host)
        port = kwargs.pop("target_port", port) or port
        payload = kwargs.pop("data", "")
        payload = kwargs.pop("send_data", payload)
        payload = kwargs.pop("input", payload)
        payload = kwargs.pop("command", payload)
        payload = kwargs.pop("payload", payload)
        payload = kwargs.pop("cmd", payload)
        timeout = kwargs.pop("timeout", 5)
        append_newline = kwargs.pop("newline", False)
        session_id = kwargs.pop("session_id", "")
        close_after = kwargs.pop("close_session", False)

        if session_id:
            if close_after:
                await close_session(session_id)
                return {"success": True, "output": f"Session {session_id} closed.", "session_id": session_id}
            if not has_session(session_id):
                return {
                    "success": False,
                    "output": f"ERROR: Session '{session_id}' not found. " + _available_sessions(),
                    "error": f"Session {session_id} not found",
                }
            if payload:
                try:
                    await write_session(session_id, payload, append_newline)
                except Exception as e:
                    return {
                        "success": False,
                        "output": f"ERROR: Write failed: {e}. Create a new session with remote_connect(host=..., port=...).",
                        "error": str(e),
                    }
            result_text = await read_session(session_id, read_timeout=timeout)
            if len(result_text) > 4000:
                result_text = result_text[:2000] + "\n...[TRUNCATED]...\n" + result_text[-1000:]
            return {
                "success": True,
                "output": result_text or "(no new output)",
                "session_id": session_id,
            }

        if not host or not port:
            return {"success": False, "output": "host and port are required. " + _available_sessions(), "error": ""}

        # Auto-reuse existing session for same host:port
        auto_id = f"{host}:{port}"
        if has_session(auto_id):
            if close_after:
                await close_session(auto_id)
                return {"success": True, "output": f"Session {auto_id} closed.", "session_id": auto_id}
            if payload:
                try:
                    await write_session(auto_id, payload, append_newline)
                except Exception:
                    # Session died (server timeout). Auto-reconnect.
                    logger.warning(f"Session {auto_id} dead, reconnecting...")
                    await close_session(auto_id)
                    try:
                        await create_session(host, port, connect_timeout=max(15, timeout))
                        await write_session(auto_id, payload, append_newline)
                    except Exception as e2:
                        return {
                            "success": False,
                            "output": f"ERROR: Reconnect failed: {e2}",
                            "error": str(e2),
                        }
            result_text = await read_session(auto_id, read_timeout=max(10, timeout))
            if len(result_text) > 4000:
                result_text = result_text[:2000] + "\n...[TRUNCATED]...\n" + result_text[-1000:]
            return {
                "success": True,
                "output": result_text or "(no new output - try again with same host:port to wait for prompt)",
                "session_id": auto_id,
                "command": f"reuse {host}:{port}",
            }

        try:
            await create_session(host, port, connect_timeout=max(15, timeout))
            if payload:
                await write_session(auto_id, payload, append_newline)
            result_text = await read_session(auto_id, read_timeout=max(10, timeout))
            if len(result_text) > 4000:
                result_text = result_text[:2000] + "\n...[TRUNCATED]...\n" + result_text[-1000:]
            logger.info(f"remote_connect {host}:{port} - sent '{payload}' - got {len(result_text)} chars")
            return {
                "success": True,
                "output": result_text or "(connected)",
                "session_id": auto_id,
                "command": f"connect {host}:{port}",
            }
        except asyncio.TimeoutError:
            return {"success": False, "output": f"CONNECTION TIMEOUT: {host}:{port} did not respond in time. Try increasing timeout or check if server is up.", "error": f"Connection to {host}:{port} timed out"}
        except ConnectionRefusedError:
            return {"success": False, "output": f"CONNECTION REFUSED: {host}:{port}. The server may be down.", "error": f"Connection to {host}:{port} refused"}
        except OSError as e:
            return {"success": False, "output": f"CONNECTION ERROR: {e}. Check host and port.", "error": str(e)}
        except Exception as e:
            return {"success": False, "output": f"CONNECTION ERROR: {e}", "error": str(e)}
