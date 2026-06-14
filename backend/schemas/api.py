from pydantic import BaseModel
from typing import Optional, Literal


class SolveRequest(BaseModel):
    description: str
    target_url: Optional[str] = None
    target_host: Optional[str] = None
    target_port: Optional[int] = None
    flag_format: Optional[str] = "picoCTF{...}"
    mode: Literal["solve", "hint"] = "solve"


class SolveResponse(BaseModel):
    session_id: str
    status: Literal["queued", "running", "solved", "failed"]
    category: Optional[str] = None
    flag: Optional[str] = None
    trace_ws_url: str


class TraceEvent(BaseModel):
    event_type: Literal[
        "classification",
        "tool_call",
        "tool_result",
        "hypothesis",
        "flag_candidate",
        "flag_validated",
        "error",
        "completed",
        "difficulty",
    ]
    agent: str
    data: dict
    timestamp: str
    iteration: int


class SessionSummary(BaseModel):
    session_id: str
    status: str
    category: Optional[str] = None
    flag: Optional[str] = None
    created_at: str
    iteration_count: int


class BenchmarkRequest(BaseModel):
    challenges: list[dict]


class HealthResponse(BaseModel):
    status: str
    tools: dict
