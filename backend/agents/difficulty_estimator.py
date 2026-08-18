import json
from datetime import datetime, timezone
from loguru import logger
from backend.core.llm_client import get_llm
from backend.core.state import AgentState


async def difficulty_estimator_node(state: AgentState) -> dict:
    llm = get_llm("flag_detector", temperature=0.0)

    manifest = state.get("manifest", {})
    description = manifest.get("description", "")
    category = state.get("category", "unknown")

    prompt = (
        "Rate this CTF challenge difficulty.\n\n"
        f"Description: {description[:1000]}\n"
        f"Category: {category}\n\n"
        "Respond ONLY with valid JSON:\n"
        '{"difficulty": "Easy"|"Medium"|"Hard", '
        '"estimated_minutes": <number>, '
        '"reasoning": "<short reason>"}\n'
    )

    try:
        response = await llm.ainvoke(prompt)
        content = response.content.strip().replace("```json", "").replace("```", "").strip()
        parsed = json.loads(content)
        difficulty = parsed.get("difficulty", "Medium")
        difficulty = difficulty.capitalize()
        if difficulty not in ("Easy", "Medium", "Hard"):
            difficulty = "Medium"
        est_minutes = parsed.get("estimated_minutes", 30)
        logger.info(f"Estimated difficulty: {difficulty} ({est_minutes} min)")
        return {
            "difficulty": difficulty,
            "trace_events": [{
                "event_type": "difficulty",
                "agent": "classifier",
                "data": {"difficulty": difficulty, "estimated_minutes": est_minutes},
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "iteration": 0,
            }],
        }
    except Exception as e:
        logger.warning(f"Difficulty estimation failed: {e}")
        return {}
