from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app import graph, state
from app.planner import plan_entry
from app.store import load_run, save_run

app = FastAPI(title="Multi-Agent Workflow - D4")

# Pricing, retry and cost limits live in app.guards (single source of truth).
# Patch points for tests: graph.TOOLS entries, guards.MAX_STEPS.


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


def _execute(goal: str) -> dict:
    # All execution flows through the LangGraph graph: plan -> act (retry
    # cycle) -> summarize, checkpointed. Tests override graph.TOOLS entries.
    return graph.run_graph(goal.strip())


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
    hit = state.cache_get(goal)
    if hit is not None:
        # Fresh identity per request: the cached answer is reused, but this
        # run gets its own id and its own persisted record.
        replay = {k: v for k, v in hit.items() if k != "run_id"}
        replay["run_id"] = save_run(replay)
        return replay
    body = _execute(goal)
    body["goal"] = req.goal
    body["run_id"] = save_run(body)
    if body.get("status") == "done":
        # Errors and gated/stopped runs are never cached: failures are
        # transient (retry next time), approvals must stay human-gated.
        state.cache_put(goal, body)
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
