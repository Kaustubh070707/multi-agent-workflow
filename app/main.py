from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app import guards
from app.agents import hand_off, researcher, summarizer
from app.guards import should_stop
from app.planner import plan_entry
from app.store import load_run, save_run
from app.tools import exec_tool, search_tool

app = FastAPI(title="Multi-Agent Workflow - D4")

# Placeholder pricing per tool call until real LLM billing plugs in (SKILL.md).
# The plumbing (ledger, floors, trip reasons) is what this step proves.
COST_PER_SEARCH = 0.01
COST_PER_EXEC = 0.001
MAX_COST_USD_PER_RUN = 0.50
# Consecutive failures before giving up with status error (guard is the backstop).
MAX_RETRIES = 3


class RunRequest(BaseModel):
    goal: str


class ApproveRequest(BaseModel):
    approval_token: str


# Goals matching these words can change the world outside the logs.
# They wait for a human before any tool runs.
IRREVERSIBLE_KEYWORDS = ("send", "email", "delete", "publish", "pay")


def needs_approval(goal: str) -> bool:
    lowered = goal.lower()
    return any(word in lowered for word in IRREVERSIBLE_KEYWORDS)


@app.get("/health")
def health():
    return {"status": "ok"}


def _guard_reason(steps: int, cost: float) -> str | None:
    if not should_stop(steps, cost, MAX_COST_USD_PER_RUN):
        return None
    if steps >= guards.MAX_STEPS:  # read live so tests can force it
        return f"step limit reached ({steps} >= {guards.MAX_STEPS})"
    return f"cost budget reached (${cost:.2f} >= ${MAX_COST_USD_PER_RUN:.2f})"


def _execute(goal: str) -> dict:
    # Step 6+7 core: plan, guarded retries, handoff, summary. No persistence here.
    trace = [plan_entry(goal)]
    steps = 0
    cost = 0.0
    failures = 0
    tool, result = "search", {"ok": False, "error": "not attempted"}
    while True:
        reason = _guard_reason(steps, cost)
        if reason is not None:
            trace.append({"kind": "guard", "reason": reason, "steps": steps, "cost_usd": round(cost, 4)})
            return {"goal": goal, "status": "stopped", "trace": trace,
                    "answer": f"Stopped: {reason}."}
        tool, result = researcher(goal, exec_tool, search_tool)
        steps += 1
        cost += COST_PER_EXEC if tool == "exec" else COST_PER_SEARCH
        trace.append({"tool": tool, "input": goal, "output": result,
                      "step": steps, "cost_usd": round(cost, 4)})
        if result.get("ok"):
            break
        failures += 1
        if failures >= MAX_RETRIES:
            break
    handoff = hand_off("researcher", "summarizer", {"tool": tool, "result": result, "goal": goal})
    trace.append(handoff)
    summary = summarizer(handoff)
    trace.append(summary)
    status = "done" if result.get("ok") else "error"
    return {"goal": goal, "status": status, "trace": trace, "answer": summary["answer"]}


@app.post("/run")
def run(req: RunRequest):
    # Step 7: irreversible goals wait for a human before any tool runs.
    goal = req.goal.strip()
    if needs_approval(goal):
        pending = {"goal": req.goal, "status": "awaiting_approval",
                   "trace": [plan_entry(goal),
                             {"kind": "approval",
                              "reason": "goal looks irreversible — waiting for human approval"}]}
        pending["run_id"] = save_run(pending)
        pending["approval_token"] = pending["run_id"]
        save_run(pending)
        return pending
    body = _execute(goal)
    body["goal"] = req.goal
    body["run_id"] = save_run(body)
    return body


@app.post("/approve")
def approve(req: ApproveRequest):
    saved = load_run(req.approval_token)
    if saved is None or saved.get("status") != "awaiting_approval":
        raise HTTPException(status_code=403, detail="unknown or stale approval token")
    body = _execute(saved["goal"])
    body["run_id"] = saved["run_id"]
    body["approved"] = True
    save_run(body)
    return body


@app.get("/run/{run_id}")
def get_run(run_id: str):
    saved = load_run(run_id)
    if saved is None:
        raise HTTPException(status_code=404, detail="run not found")
    return saved
