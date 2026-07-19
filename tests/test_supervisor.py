import pytest

from backend.agents import supervisor


class _FakeDeepAgentSupervisor(supervisor.DeepAgentSupervisor):
    def _ensure_agent(self):
        return object()


def _state():
    return {
        "manifest": {"description": "test"},
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
        "session_id": "test-session",
        "trace_events": [],
        "difficulty": None,
        "mode": "solve",
    }


def test_merge_state_appends_reducer_fields():
    state = _state()
    merged = supervisor._merge_state(
        state,
        {
            "trace_events": [{"event_type": "classification"}],
            "observations": ["first"],
            "category": "web",
        },
    )
    merged = supervisor._merge_state(
        merged,
        {
            "trace_events": [{"event_type": "completed"}],
            "observations": ["second"],
        },
    )

    assert merged["category"] == "web"
    assert [e["event_type"] for e in merged["trace_events"]] == [
        "classification",
        "completed",
    ]
    assert merged["observations"] == ["first", "second"]


@pytest.mark.asyncio
async def test_supervisor_astream_yields_values(monkeypatch):
    async def fake_classify(state):
        return {
            "category": "web",
            "current_agent": "web_agent",
            "trace_events": [{"event_type": "classification"}],
        }

    async def fake_difficulty(state):
        return {"difficulty": "Easy"}

    async def fake_route(state):
        return {"current_agent": "web_agent"}

    async def fake_web_agent(state):
        return {
            "solved": True,
            "final_flag": "picoCTF{ok}",
            "current_agent": "flag_validation",
            "trace_events": [{"event_type": "flag_validated"}],
        }

    async def fake_validate(state):
        return {"trace_events": [{"event_type": "completed"}]}

    monkeypatch.setattr(supervisor, "classify_node", fake_classify)
    monkeypatch.setattr(supervisor, "difficulty_estimator_node", fake_difficulty)
    monkeypatch.setattr(supervisor, "route_node", fake_route)
    monkeypatch.setattr(supervisor, "web_agent_node", fake_web_agent)
    monkeypatch.setattr(supervisor, "flag_validation_node", fake_validate)

    graph = _FakeDeepAgentSupervisor()
    states = [state async for state in graph.astream(_state(), stream_mode="values")]

    assert len(states) == 5
    assert states[-1]["solved"] is True
    assert states[-1]["final_flag"] == "picoCTF{ok}"
    assert [e["event_type"] for e in states[-1]["trace_events"]] == [
        "classification",
        "flag_validated",
        "completed",
    ]


@pytest.mark.asyncio
async def test_supervisor_astream_rejects_unsupported_stream_mode():
    graph = _FakeDeepAgentSupervisor()

    with pytest.raises(ValueError):
        async for _ in graph.astream(_state(), stream_mode="updates"):
            pass
