from backend.tools.base import BaseTool
from backend.tools.pwn.session_manager import read_session, has_session, _sessions
from loguru import logger


def _available_sessions() -> str:
    if not _sessions:
        return "No active sessions."
    return "Active sessions: " + ", ".join(sorted(_sessions.keys()))


class SessionReadTool(BaseTool):
    name = "session_read"
    description = "Read data from an existing persistent session without sending anything. Use host+port instead of session_id."
    parameters = {
        "host": {"type": "string", "description": "Host of the session to read from (same as remote_connect call)"},
        "port": {"type": "integer", "description": "Port of the session to read from"},
        "session_id": {"type": "string", "description": "Exact session_id string (alternative to host+port)"},
        "timeout": {"type": "integer", "description": "Read timeout in seconds (default: 3)"},
    }

    async def run(self, session_id: str = "", **kwargs) -> dict:
        host = kwargs.pop("host", "") or kwargs.pop("target_host", "")
        port = kwargs.pop("port", 0) or kwargs.pop("target_port", 0)
        timeout = kwargs.pop("timeout", 3)

        if not session_id and host and port:
            session_id = f"{host}:{port}"
        if not session_id and host and not port:
            session_id = host

        if not session_id:
            return {"success": False, "output": "ERROR: provide host+port or session_id. " + _available_sessions(), "error": "session_id required"}
        if not has_session(session_id):
            return {
                "success": False,
                "output": f"ERROR: Session '{session_id}' not found. " + _available_sessions(),
                "error": f"Session {session_id} not found",
            }

        result_text = await read_session(session_id, read_timeout=timeout)
        if not result_text:
            return {
                "success": True,
                "output": "(no new data available - try remote_connect again with same host:port)",
                "session_id": session_id,
            }

        if len(result_text) > 4000:
            result_text = result_text[:2000] + "\n...[TRUNCATED]...\n" + result_text[-1000:]

        logger.info(f"session_read {session_id} - got {len(result_text)} chars")
        return {
            "success": True,
            "output": result_text,
            "session_id": session_id,
        }
