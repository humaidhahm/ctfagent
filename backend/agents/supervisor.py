from datetime import datetime, timezone
from typing import Any
from deepagents import create_deep_agent
from loguru import logger

from backend.core.state import AgentState
from backend.core.llm_client import get_chat_model
from backend.agents.classifier import classify_node
from backend.agents.difficulty_estimator import difficulty_estimator_node
from backend.agents.web_agent import web_agent_node
from backend.agents.crypto_agent import crypto_agent_node
from backend.agents.forensics_agent import forensics_agent_node
from backend.agents.pwn_agent import pwn_agent_node
from backend.agents.re_agent import re_agent_node
from backend.agents.misc_agent import misc_agent_node
from backend.memory.experience_db import experience_db
from backend.tools.pwn.session_manager import close_all_sessions

DOMAIN_AGENTS = ["web_agent", "crypto_agent", "forensics_agent", "pwn_agent", "re_agent", "misc_agent"]
CATEGORY_ROUTE = {
    "web": "web_agent",
    "crypto": "crypto_agent",
    "forensics": "forensics_agent",
    "pwn": "pwn_agent",
    "re": "re_agent",
    "osint": "misc_agent",
    "ai": "misc_agent",
    "misc": "misc_agent",
}

ADDITIVE_STATE_KEYS = {
    "tool_history",
    "observations",
    "candidate_flags",
    "trace_events",
}

SUPERVISOR_PROMPT = """You are the CTFAgent supervisor.
Coordinate CTF solving work by classifying the challenge, estimating difficulty,
routing to the right specialist, and validating the final flag. Keep state
updates concise and let specialist agents use their domain tools."""


async def route_node(state: AgentState) -> dict:
    category = state.get("category", "unknown")
    logger.info(f"Routing challenge: category={category}")

    if category not in CATEGORY_ROUTE:
        logger.warning(f"Unknown category '{category}', retrying classifier before routing")
        retry = await classify_node(state)
        category = retry.get("category", "misc")
        target = CATEGORY_ROUTE.get(category, "misc_agent")
        return {
            **retry,
            "current_agent": target,
            "observations": [f"Category '{state.get('category', 'unknown')}' reclassified as '{category}'"],
        }

    target = CATEGORY_ROUTE.get(category, "web_agent")
    return {"current_agent": target}


def router(state: AgentState) -> str:
    current = state.get("current_agent", "classify")
    if current in DOMAIN_AGENTS:
        return current
    return "classify"


def agent_looper(state: AgentState) -> str:
    if state.get("solved") or state.get("failure_reason") is not None:
        return "flag_validation"
    from backend.config.settings import settings
    if state.get("iteration_count", 0) >= settings.max_agent_iterations:
        return "flag_validation"
    if state.get("iteration_count", 0) >= settings.max_agent_iterations:
        return "flag_validation"
    return state.get("current_agent", "misc_agent")


async def flag_validation_node(state: AgentState) -> dict:
    logger.info(f"Flag validation: solved={state.get('solved')}, flags={state.get('candidate_flags')}")

    closed = await close_all_sessions()
    if closed:
        logger.info(f"Cleaned up {closed} persistent session(s)")

    if state.get("solved") and state.get("final_flag"):
        logger.success(f"Challenge solved! Flag: {state['final_flag']}")
        try:
            experience_db.add_solved(state)
        except Exception as e:
            logger.warning(f"Failed to save to experience DB: {e}")
        return {
            "trace_events": [{
                "event_type": "completed",
                "agent": "supervisor",
                "data": {"solved": True, "flag": state["final_flag"]},
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "iteration": state.get("iteration_count", 0),
            }],
        }

    reason = state.get("failure_reason", "Unsolved - no flag found after all iterations")
    logger.info(f"Challenge unsolved: {reason}")
    try:
        experience_db.add_unsolved(state)
    except Exception as e:
        logger.warning(f"Failed to save to experience DB: {e}")
    return {
        "trace_events": [{
            "event_type": "completed",
            "agent": "supervisor",
            "data": {"solved": False, "reason": reason},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "iteration": state.get("iteration_count", 0),
        }],
    }


def _get_agent_node(name: str):
    nodes = {
        "web_agent": web_agent_node,
        "crypto_agent": crypto_agent_node,
        "forensics_agent": forensics_agent_node,
        "pwn_agent": pwn_agent_node,
        "re_agent": re_agent_node,
        "misc_agent": misc_agent_node,
    }
    return nodes[name]


def _merge_state(state: AgentState, updates: dict[str, Any]) -> AgentState:
    next_state = dict(state)

    for key, value in updates.items():
        if key in ADDITIVE_STATE_KEYS:
            current = next_state.get(key, [])
            if value is None:
                value = []
            next_state[key] = list(current) + list(value)
        else:
            next_state[key] = value

    return next_state


class DeepAgentSupervisor:
    """Deep Agents-backed supervisor with the old async invoke contract."""

    def __init__(self):
        self.agent = None

    def _ensure_agent(self):
        if self.agent is not None:
            return self.agent

        self.agent = create_deep_agent(
            model=get_chat_model("supervisor", temperature=0.0),
            tools=[],
            system_prompt=SUPERVISOR_PROMPT,
        )
        return self.agent

    async def _run(self, initial_state: AgentState):
        state = dict(initial_state)
        self._ensure_agent()

        for node in (classify_node, difficulty_estimator_node, route_node):
            state = _merge_state(state, await node(state))
            yield state

        while True:
            next_node = router(state)
            if next_node == "classify":
                state = _merge_state(state, await classify_node(state))
                yield state
                state = _merge_state(state, await route_node(state))
                yield state
                continue

            state = _merge_state(state, await _get_agent_node(next_node)(state))
            yield state
            next_route = agent_looper(state)
            if next_route == "flag_validation":
                break

        yield _merge_state(state, await flag_validation_node(state))

    async def ainvoke(self, initial_state: AgentState) -> AgentState:
        final_state = None
        async for state in self._run(initial_state):
            final_state = state
        return final_state or dict(initial_state)

    async def astream(self, initial_state: AgentState, stream_mode: str = "values"):
        if stream_mode != "values":
            raise ValueError("DeepAgentSupervisor only supports stream_mode='values'")

        async for state in self._run(initial_state):
            yield state


def build_supervisor_graph() -> DeepAgentSupervisor:
    return DeepAgentSupervisor()


supervisor_graph = build_supervisor_graph()
