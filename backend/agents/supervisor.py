from datetime import datetime, timezone
from langgraph.graph import StateGraph, END
from typing import Literal
from loguru import logger

from backend.core.state import AgentState
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
    "misc": "misc_agent",
}


async def route_node(state: AgentState) -> dict:
    category = state.get("category", "unknown")
    logger.info(f"Routing challenge: category={category}")

    if category not in CATEGORY_ROUTE:
        return {"current_agent": target, "observations": [f"Category '{category}' defaulted to web agent"]}
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
    return state.get("current_agent", "web_agent")


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
    return {
        "trace_events": [{
            "event_type": "completed",
            "agent": "supervisor",
            "data": {"solved": False, "reason": reason},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "iteration": state.get("iteration_count", 0),
        }],
    }


def build_supervisor_graph() -> StateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("classify", classify_node)
    workflow.add_node("difficulty_estimator", difficulty_estimator_node)
    workflow.add_node("route", route_node)
    for agent in DOMAIN_AGENTS:
        workflow.add_node(agent, _get_agent_node(agent))
    workflow.add_node("flag_validation", flag_validation_node)

    workflow.set_entry_point("classify")

    workflow.add_edge("classify", "difficulty_estimator")
    workflow.add_edge("difficulty_estimator", "route")

    workflow.add_conditional_edges("route", router, {
        a: a for a in DOMAIN_AGENTS
    } | {"classify": "classify"})

    for agent in DOMAIN_AGENTS:
        workflow.add_conditional_edges(agent, agent_looper, {
            "flag_validation": "flag_validation",
            agent: agent,
        })

    workflow.add_edge("flag_validation", END)
    return workflow.compile()


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


supervisor_graph = build_supervisor_graph()
