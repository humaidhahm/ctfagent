import asyncio
import json
import os
import time
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone
from loguru import logger

from backend.core.state import AgentState
from backend.config.settings import settings


SESSIONS_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "sessions.json"


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, dict] = {}
        self._lock = asyncio.Lock()
        self._load()

    def _load(self):
        if SESSIONS_DB_PATH.exists():
            try:
                data = json.loads(SESSIONS_DB_PATH.read_text())
                self._sessions = data.get("sessions", {})
                # Evict expired sessions
                ttl = settings.session_ttl_seconds
                cutoff = time.time() - ttl
                expired = []
                for sid, sess in self._sessions.items():
                    created = sess.get("_created_ts", 0)
                    if created and created < cutoff:
                        expired.append(sid)
                for sid in expired:
                    del self._sessions[sid]
                if expired:
                    logger.info(f"Evicted {len(expired)} expired sessions")
                logger.info(f"Loaded {len(self._sessions)} sessions from disk")
            except Exception as e:
                logger.warning(f"Failed to load sessions: {e}")
                self._sessions = {}

    def _save(self):
        SESSIONS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "sessions": self._sessions,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        SESSIONS_DB_PATH.write_text(json.dumps(data, indent=2, default=str))

    async def create(self, session_id: str, initial_state: dict) -> None:
        async with self._lock:
            self._sessions[session_id] = {
                **initial_state,
                "trace_events": [],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "_created_ts": time.time(),
            }
            self._save()
            await self._enforce_limits()
            self._save()
            logger.info(f"Session {session_id} created")

    async def get(self, session_id: str) -> Optional[dict]:
        async with self._lock:
            return self._sessions.get(session_id)

    async def update(self, session_id: str, patch: dict) -> None:
        async with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id].update(patch)
                self._save()

    async def append_trace_events(self, session_id: str, events: list[dict]) -> None:
        async with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id].setdefault("trace_events", []).extend(events)
                self._save()

    async def get_new_trace_events(self, session_id: str, since_index: int) -> list[dict]:
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return []
            events = session.get("trace_events", [])
            return events[since_index:]

    async def delete(self, session_id: str) -> None:
        async with self._lock:
            self._sessions.pop(session_id, None)
            self._save()
            logger.info(f"Session {session_id} deleted")

    MAX_SESSION_COUNT = 200

    async def _enforce_limits(self):
        """Evict oldest sessions when over capacity."""
        if len(self._sessions) > self.MAX_SESSION_COUNT:
            excess = len(self._sessions) - self.MAX_SESSION_COUNT
            sorted_sids = sorted(
                self._sessions.keys(),
                key=lambda s: self._sessions[s].get("_created_ts", 0),
            )
            for sid in sorted_sids[:excess + 10]:
                del self._sessions[sid]
            logger.info(f"Evicted {excess + 10} old sessions (capacity: {self.MAX_SESSION_COUNT})")

    async def list_sessions(self) -> list[dict]:
        async with self._lock:
            results = []
            for sid, sess in self._sessions.items():
                iteration_count = sess.get("iteration_count", 0)
                solved = sess.get("solved", False)
                if solved:
                    status = "solved"
                elif iteration_count > 0:
                    status = "running"
                elif sess.get("current_agent") and sess["current_agent"] != "classify":
                    status = "running"
                else:
                    status = "queued"
                results.append({
                    "session_id": sid,
                    "status": status,
                    "category": sess.get("category"),
                    "flag": sess.get("final_flag"),
                    "created_at": sess.get("created_at", ""),
                    "iteration_count": iteration_count,
                })
            return results

    async def get_trace_event_count(self, session_id: str) -> int:
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return 0
            return len(session.get("trace_events", []))


session_store = SessionStore()
