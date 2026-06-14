import asyncio
import json
from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger

from backend.memory.session_store import session_store


async def websocket_handler(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    logger.info(f"WebSocket connected for session {session_id}")

    cursor = 0
    try:
        while True:
            session = await session_store.get(session_id)
            if session is None:
                await websocket.send_json({
                    "event_type": "error",
                    "data": {"message": "Session not found"},
                })
                break

            new_events = await session_store.get_new_trace_events(session_id, cursor)
            for event in new_events:
                await websocket.send_json(event)
                cursor += 1

            completed_events = [e for e in new_events if e.get("event_type") == "completed"]
            if completed_events:
                await websocket.close()
                return

            await asyncio.sleep(0.2)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
        try:
            await websocket.close()
        except Exception:
            pass
