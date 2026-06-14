import os
import json
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, WebSocket
from loguru import logger

from backend.schemas.api import SolveRequest, SolveResponse, HealthResponse, BenchmarkRequest
from backend.ingestion.ingestor import ingest_challenge
from backend.memory.session_store import session_store
from backend.core.tool_checker import check_all_tools
from backend.config.settings import settings
from backend.agents.supervisor import supervisor_graph
from backend.api.websocket import websocket_handler
from backend.core.nim_client import get_nim_llm

router = APIRouter()

_task_registry: list = []


def _cleanup_tasks():
    global _task_registry
    _task_registry = [t for t in _task_registry if not t.done()]


async def _run_agent_async(initial_state: dict, session_id: str) -> None:
    try:
        final_state = await supervisor_graph.ainvoke(initial_state)
        await session_store.update(session_id, {
            "solved": final_state.get("solved", False),
            "final_flag": final_state.get("final_flag"),
            "failure_reason": final_state.get("failure_reason"),
        })
        await session_store.append_trace_events(session_id, final_state.get("trace_events", []))
        logger.info(f"Agent session {session_id} completed")
    except Exception as e:
        logger.error(f"Agent session {session_id} failed: {e}")
        await session_store.append_trace_events(session_id, [{
            "event_type": "error",
            "agent": "supervisor",
            "data": {"error": str(e)},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "iteration": 0,
        }])


@router.get("/health")
async def health_check() -> HealthResponse:
    tools = await check_all_tools()
    missing = [k for k, v in tools.items() if v is None]
    status = "degraded" if missing else "healthy"
    return HealthResponse(status=status, tools=tools)


@router.post("/api/solve", response_model=SolveResponse)
async def solve_challenge(
    description: str = Form(...),
    target_url: Optional[str] = Form(None),
    target_host: Optional[str] = Form(None),
    target_port: Optional[int] = Form(None),
    flag_format: Optional[str] = Form("picoCTF{...}"),
    mode: Optional[str] = Form("solve"),
    files: list[UploadFile] = File(default=[]),
) -> SolveResponse:
    session_id = str(uuid.uuid4())

    uploaded = []
    for f in files:
        if f.filename:
            content = await f.read()
            uploaded.append((f.filename, content, f.content_type or ""))

    manifest = await ingest_challenge(
        description=description,
        upload_dir=settings.upload_dir,
        files=uploaded if uploaded else None,
        target_url=target_url,
        target_host=target_host,
        target_port=target_port,
        flag_format=flag_format,
    )

    initial_state = {
        "manifest": manifest.model_dump(),
        "category": "unknown",
        "recommended_toolchain": [],
        "classification_reasoning": "",
        "current_agent": "classify",
        "tool_history": [],
        "observations": [],
        "current_hypothesis": "",
        "iteration_count": 0,
        "candidate_flags": [],
        "final_flag": None,
        "solved": False,
        "failure_reason": None,
        "session_id": session_id,
        "trace_events": [],
        "difficulty": None,
        "mode": mode,
    }

    await session_store.create(session_id, initial_state)

    _cleanup_tasks()
    task = asyncio.create_task(_run_agent_async(initial_state, session_id))
    _task_registry.append(task)

    trace_ws_url = f"ws://{settings.api_host}:{settings.api_port}/ws/{session_id}"

    return SolveResponse(
        session_id=session_id,
        status="queued",
        trace_ws_url=trace_ws_url,
    )


@router.get("/api/session/{session_id}")
async def get_session(session_id: str) -> dict:
    session = await session_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session_id,
        "status": "solved" if session.get("solved") else (
            "running" if session.get("iteration_count", 0) > 0 else "queued"),
        "category": session.get("category"),
        "flag": session.get("final_flag"),
        "candidate_flags": session.get("candidate_flags", []),
        "iteration_count": session.get("iteration_count", 0),
        "current_hypothesis": session.get("current_hypothesis", ""),
        "failure_reason": session.get("failure_reason"),
        "trace_events": session.get("trace_events", []),
        "difficulty": session.get("difficulty"),
        "created_at": session.get("created_at", ""),
    }


@router.get("/api/sessions")
async def list_sessions() -> list[dict]:
    return await session_store.list_sessions()


@router.delete("/api/session/{session_id}")
async def delete_session(session_id: str) -> dict:
    await session_store.delete(session_id)
    return {"status": "deleted"}


@router.get("/api/session/{session_id}/writeup")
async def get_writeup(session_id: str) -> dict:
    session = await session_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    manifest = session.get("manifest", {})
    writeup_path = os.path.join(settings.upload_dir, session_id, "writeup.md")
    if os.path.exists(writeup_path):
        with open(writeup_path) as f:
            return {"writeup": f.read()}

    if not session.get("solved"):
        raise HTTPException(status_code=400, detail="Challenge not solved, no writeup available")

    llm = get_nim_llm("supervisor", temperature=0.3)
    trace_str = json.dumps(session.get("trace_events", []), indent=2)[:4000]

    prompt = (
        "You solved this CTF challenge. Given this agent trace, write a clean step-by-step "
        "write-up in markdown format. Include: challenge description, approach, tools used, "
        "key observations, and the flag. Format it for publication on a CTF blog.\n\n"
        f"Description: {manifest.get('description', '')[:2000]}\n"
        f"Category: {session.get('category', '')}\n"
        f"Flag: {session.get('final_flag', '')}\n"
        f"Agent Trace: {trace_str}\n\n"
        "Write the complete writeup in markdown:\n"
    )

    try:
        response = await llm.ainvoke(prompt)
        writeup = response.content

        os.makedirs(os.path.dirname(writeup_path), exist_ok=True)
        with open(writeup_path, "w") as f:
            f.write(writeup)

        return {"writeup": writeup}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Writeup generation failed: {e}")


@router.post("/api/benchmark")
async def run_benchmark(req: BenchmarkRequest) -> dict:
    results = []
    for challenge in req.challenges:
        session_id = str(uuid.uuid4())
        manifest = await ingest_challenge(
            description=challenge.get("description", ""),
            upload_dir=settings.upload_dir,
            target_url=challenge.get("target_url"),
            target_host=challenge.get("target_host"),
            target_port=challenge.get("target_port"),
        )

        initial_state = {
            "manifest": manifest.model_dump(),
            "category": "unknown",
            "recommended_toolchain": [],
            "classification_reasoning": "",
            "current_agent": "classify",
            "tool_history": [],
            "observations": [],
            "current_hypothesis": "",
            "iteration_count": 0,
            "candidate_flags": [],
            "final_flag": None,
            "solved": False,
            "failure_reason": None,
            "session_id": session_id,
            "trace_events": [],
            "difficulty": None,
            "mode": "solve",
        }

        await session_store.create(session_id, initial_state)
        final_state = await supervisor_graph.ainvoke(initial_state)

        known_flag = challenge.get("known_flag", "")
        solved = final_state.get("solved", False)
        flag_match = solved and final_state.get("final_flag") == known_flag

        results.append({
            "session_id": session_id,
            "description": challenge.get("description", "")[:100],
            "solved": solved,
            "flag_match": flag_match,
            "expected_flag": known_flag,
            "actual_flag": final_state.get("final_flag"),
            "iterations": final_state.get("iteration_count", 0),
            "category": final_state.get("category"),
        })

    solved_count = sum(1 for r in results if r["solved"])
    match_count = sum(1 for r in results if r["flag_match"])

    return {
        "total": len(results),
        "solved": solved_count,
        "flag_matches": match_count,
        "solve_rate": round(match_count / len(results) * 100, 1) if results else 0,
        "results": results,
    }


@router.websocket("/ws/{session_id}")
async def agent_ws(websocket: WebSocket, session_id: str) -> None:
    await websocket_handler(websocket, session_id)
