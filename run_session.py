#!/usr/bin/env python3
"""Run a specific session by ID through the solver and output the flag."""
import asyncio
import json
import sys
from pathlib import Path

SESSIONS_DB = Path(__file__).resolve().parent / "data" / "sessions.json"
SESSION_ID = "39267966-ae40-469a-be1d-a39c4944f081"


async def main():
    data = json.loads(SESSIONS_DB.read_text())
    session = data["sessions"].get(SESSION_ID)
    if not session:
        print(f"Session {SESSION_ID} not found")
        sys.exit(1)

    print(f"Running session {SESSION_ID}...")
    print(f"Challenge: {session['manifest']['description'][:80]}...")

    from backend.agents.supervisor import supervisor_graph
    from backend.memory.session_store import session_store
    from backend.tools.pwn.session_manager import close_all_sessions

    initial_state = {k: v for k, v in session.items() if not k.startswith("_")}
    initial_state.pop("created_at", None)
    initial_state.pop("updated_at", None)

    seen = 0
    solved = False
    final_flag = None
    final_state = None

    async for state in supervisor_graph.astream(initial_state, stream_mode="values"):
        final_state = state
        new_events = state.get("trace_events", [])[seen:]
        for event in new_events:
            et = event.get("event_type", "")
            data_ = event.get("data", {})
            agent = event.get("agent", "")
            if et == "llm_reasoning":
                raw = data_.get("raw_output", "")[:120]
                print(f"  [{agent}] LLM: {raw}...")
            elif et == "tool_call":
                print(f"  [{agent}] Calling: {data_.get('tool')}({data_.get('args')})")
            elif et == "tool_result":
                out = data_.get("output", "")[:60]
                ok = data_.get("success", False)
                print(f"  [{agent}] Result (ok={ok}): {out}")
            elif et == "flag_validated":
                print(f"  [FLAG] Candidate: {data_.get('flag')}")
                solved = True
                final_flag = data_.get("flag")
            elif et == "completed":
                solved = data_.get("solved", False)
                final_flag = data_.get("flag")
            seen += 1

        # Save progress after each iteration
        state_to_save = {k: v for k, v in state.items() if not k.startswith("_")}
        data["sessions"][SESSION_ID].update(state_to_save)
        SESSIONS_DB.write_text(json.dumps(data, indent=2))
        print(f"  [SAVE] iteration={final_state.get('iteration_count', '?')}")

    await close_all_sessions()

    if solved and final_flag:
        # Save one more time
        data["sessions"][SESSION_ID]["solved"] = True
        data["sessions"][SESSION_ID]["final_flag"] = final_flag
        SESSIONS_DB.write_text(json.dumps(data, indent=2))
        print(f"\n{'='*50}")
        print(f"FLAG: {final_flag}")
        print(f"{'='*50}")
    else:
        reason = final_state.get("failure_reason", "Unknown") if final_state else "Unknown"
        print(f"\nUnsolved: {reason}")


if __name__ == "__main__":
    asyncio.run(main())
