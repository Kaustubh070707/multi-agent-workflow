"""Deterministic planner. No LLM — rules decompose the goal into ordered steps.

Logged BEFORE any tool runs, so every trace opens with intent, not action.
"""
import re


def _split_parts(goal: str, code: bool = False) -> list[str]:
    clean = goal.strip()
    if not clean:
        return []
    if code:
        # Code keeps its newlines — only "and then"/";" split steps, never line breaks.
        # Called with the calc: prefix already stripped by plan().
        parts = re.split(r"\s+(?:and then|then|and|;)\s+", clean, flags=re.IGNORECASE)
        return [p.strip() for p in parts if p.strip()]
    if clean.lower().startswith("calc:"):
        return _split_parts(clean[5:].strip(), code=True)
    parts = re.split(r"\s+(?:and then|then|and|;)\s+|\n+", clean, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]


def plan(goal: str) -> list[dict]:
    """Decompose goal into ordered subtasks. Pure function, no side effects."""
    clean = goal.strip()
    if not clean:
        return [{"agent": "researcher", "tool": "search", "input": ""}]
    lowered = clean.lower()
    if lowered.startswith("mcp:"):
        return [{"agent": "researcher", "tool": "mcp_calc", "input": clean[4:].strip()}]
    if lowered.startswith("calc:"):
        rest = clean[5:].strip()
        steps = _split_parts(rest, code=True)
        if len(steps) <= 1:
            return [{"agent": "researcher", "tool": "exec", "input": rest}]
        return [
            {"agent": "researcher", "tool": "exec", "input": steps[0]},
            {"agent": "summarizer", "tool": "summarize", "input": " ".join(steps[1:])},
        ]
    return [
        {"agent": "researcher", "tool": "search", "input": clean},
        {"agent": "summarizer", "tool": "summarize", "input": clean},
    ]


def plan_entry(goal: str) -> dict:
    """Trace entry logged before execution."""
    return {"kind": "plan", "goal": goal.strip(), "steps": plan(goal)}
