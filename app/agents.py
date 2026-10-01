"""Two agents, one explicit handoff. No LLM — deterministic and offline-safe."""


def researcher(goal: str, exec_tool, search_tool) -> tuple[str, dict]:
    """Owns the tools. Follows the first planned step, not the raw goal. Never raises."""
    from app.planner import plan

    clean = goal.strip()
    steps = plan(goal)
    first = steps[0] if steps else {"tool": "search", "input": clean}
    if first["tool"] == "exec":
        return "exec", exec_tool(first["input"])
    return "search", search_tool(first["input"] if first["tool"] == "search" else clean)


def hand_off(from_agent: str, to_agent: str, payload: dict) -> dict:
    """The only legal way for work to move between agents. Always logged."""
    return {"kind": "handoff", "from": from_agent, "to": to_agent, "payload": payload}


def summarizer(handoff: dict) -> dict:
    """Owns formatting. Turns a handoff payload into a final answer. Never raises."""
    try:
        payload = handoff.get("payload", handoff)
        tool = payload.get("tool", "unknown")
        result = payload.get("result", {})
        goal = payload.get("goal", "")
        if not isinstance(result, dict) or not result.get("ok"):
            err = result.get("error", "unknown error") if isinstance(result, dict) else "bad payload"
            return {"kind": "summary", "answer": f"Could not complete '{goal}': {err}."}
        if tool == "exec":
            return {"kind": "summary", "answer": f"Result: {result.get('data')}"}
        items = result.get("data") or []
        if not items:
            return {"kind": "summary", "answer": f"No results found for '{goal}'."}
        titles = [str(i.get("title") or i.get("href") or "?")[:120] for i in items[:3]]
        lines = "\n".join(f"{n}. {t}" for n, t in enumerate(titles, 1))
        return {"kind": "summary", "answer": f"Top {len(titles)} results for '{goal}':\n{lines}"}
    except Exception as exc:  # noqa: BLE001 - summarizer never raises by contract
        return {"kind": "summary", "answer": f"Summarizer failed safely: {exc}"}
