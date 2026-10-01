"""Deterministic planner. No LLM — rules decompose the goal into ordered steps.

Logged BEFORE any tool runs, so every trace opens with intent, not action.
"""
import re


def _split_parts(goal: str) -> list[str]:
    clean = goal.strip()
    if not clean:
        return []
    body = clean[5:].strip() if clean.lower().startswith("calc:") else clean
    parts = re.split(r"\s+(?:and then|then|and|;)\s+|\n+", body, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]


def plan(goal: str) -> list[dict]:
    """Decompose goal into ordered subtasks. Pure function, no side effects."""
    clean = goal.strip()
    if not clean:
        return [{"agent": "researcher", "tool": "search", "input": ""}]
    if clean.lower().startswith("calc:"):
        rest = clean[5:].strip()
        steps = _split_parts(rest)
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
