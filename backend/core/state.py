from typing import TypedDict, Annotated, Optional, List, Any
import operator


class ToolCall(TypedDict):
    tool_name: str
    tool_input: dict
    tool_output: str
    timestamp: str
    success: bool


class AgentState(TypedDict):
    manifest: dict
    name: str
    category: str
    recommended_toolchain: list[str]
    classification_reasoning: str
    current_agent: str
    tool_history: Annotated[list[ToolCall], operator.add]
    observations: Annotated[list[str], operator.add]
    current_hypothesis: str
    iteration_count: int
    candidate_flags: Annotated[list[str], operator.add]
    final_flag: Optional[str]
    solved: bool
    failure_reason: Optional[str]
    session_id: str
    trace_events: Annotated[list[dict], operator.add]
    difficulty: Optional[str] = None
    mode: str = "solve"
