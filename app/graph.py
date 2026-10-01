"""LangGraph orchestration: plan -> act (retry cycle) -> summarize.

Same functions, same trace shapes as the direct path — the graph adds
cycles (bounded retries route back to act) and checkpointed state
(Postgres when reachable, memory otherwise). Pure LangGraph 0.6 API.
"""
import operator
from typing import Annotated, Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app import guards
from app.agents import hand_off, researcher, summarizer
from app.guards import MAX_COST_USD_PER_RUN, should_stop
from app.planner import plan_entry
from app.tools import exec_tool, search_tool


class RunState(dict):
    goal: str
    trace: Annotated[list, operator.add]
    steps: int
    cost: float
    failures: int
    tool: str
    result: dict
    answer: str
    status: str


def _checkpointer():
    try:
        from langgraph.checkpoint.postgres import PostgresSaver

        from app.state import DATABASE_URL, _tcp_ok

        if _tcp_ok(DATABASE_URL):
            saver = PostgresSaver.from_conn_string(DATABASE_URL)
            saver.setup()
            return saver
    except Exception:  # noqa: BLE001,S110 - postgres optional, memory fallback
        pass
    return MemorySaver()


def plan_node(state: RunState) -> dict:
    return {"trace": [plan_entry(state["goal"])]}


# Tool implementations, swappable in tests (monkeypatch graph.TOOLS entries).
# Production wiring in main._execute points these at main's names so existing
# patch points keep working; direct graph users override here.
TOOLS = {"exec": exec_tool, "search": search_tool}


def act_node(state: RunState) -> dict:
    goal = state["goal"]
    steps = state.get("steps", 0)
    cost = state.get("cost", 0.0)
    tool, result = researcher(goal, TOOLS["exec"], TOOLS["search"])
    steps += 1
    price = guards.COST_PER_EXEC if tool == "exec" else guards.COST_PER_SEARCH
    cost += price
    entry: dict[str, Any] = {"tool": tool, "input": goal, "output": result,
                             "step": steps, "cost_usd": round(cost, 4)}
    return {"trace": [entry], "steps": steps, "cost": cost,
            "failures": state.get("failures", 0) + (0 if result.get("ok") else 1),
            "tool": tool, "result": result}


def _guard_reason(steps: int, cost: float) -> str | None:
    if not should_stop(steps, cost, MAX_COST_USD_PER_RUN):
        return None
    if steps >= guards.MAX_STEPS:  # read live so tests can force it
        return f"step limit reached ({steps} >= {guards.MAX_STEPS})"
    return f"cost budget reached (${cost:.2f} >= ${MAX_COST_USD_PER_RUN:.2f})"


def route(state: RunState) -> str:
    reason = _guard_reason(state.get("steps", 0), state.get("cost", 0.0))
    if reason is not None:
        return "stopped"
    if state.get("result", {}).get("ok"):
        return "summarize"
    if state.get("failures", 0) >= guards.MAX_RETRIES:  # read live so tests can force it
        return "summarize"
    return "act"


def stopped_node(state: RunState) -> dict:
    reason = _guard_reason(state.get("steps", 0), state.get("cost", 0.0)) or "stopped"
    return {"trace": [{"kind": "guard", "reason": reason}],
            "status": "stopped", "answer": f"Stopped: {reason}."}


def summarize_node(state: RunState) -> dict:
    handoff = hand_off("researcher", "summarizer",
                       {"tool": state.get("tool", ""), "result": state.get("result", {}),
                        "goal": state.get("goal", "")})
    summary = summarizer(handoff)
    result = state.get("result", {})
    status = "done" if result.get("ok") else "error"
    return {"trace": [handoff, summary], "status": status, "answer": summary["answer"]}


def build_graph(checkpointer=None):
    builder = StateGraph(RunState)
    builder.add_node("plan", plan_node)
    builder.add_node("act", act_node)
    builder.add_node("summarize", summarize_node)
    builder.add_node("stopped", stopped_node)
    builder.add_edge(START, "plan")
    builder.add_edge("plan", "act")
    builder.add_conditional_edges("act", route, {"act": "act", "summarize": "summarize", "stopped": "stopped"})
    builder.add_edge("summarize", END)
    builder.add_edge("stopped", END)
    return builder.compile(checkpointer=checkpointer or MemorySaver())


def run_graph(goal: str, thread_id: str = "default", checkpointer=None, alpha: float = 0.5) -> dict:
    """Execute one goal through the graph. Returns body with trace/answer/status."""
    _ = alpha
    cp = checkpointer if checkpointer is not None else _checkpointer()
    owns_context = hasattr(cp, "__enter__")
    if owns_context:
        cp = cp.__enter__()
    try:
        graph = build_graph(checkpointer=cp)
        final = graph.invoke({"goal": goal.strip()},
                             config={"configurable": {"thread_id": thread_id}})
    finally:
        if owns_context:
            cp.__exit__(None, None, None)
    trace = list(final.get("trace", []))
    return {"goal": goal, "status": final.get("status", "error"),
            "trace": trace, "answer": final.get("answer", "")}
