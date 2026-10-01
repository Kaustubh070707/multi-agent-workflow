from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.agents import hand_off, researcher, summarizer
from app.planner import plan_entry
from app.store import load_run, save_run
from app.tools import exec_tool, search_tool

app = FastAPI(title="Multi-Agent Workflow - D4")


class RunRequest(BaseModel):
    goal: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/run")
def run(req: RunRequest):
    # Step 4: plan first (logged), then researcher works, hands off, summarizer answers.
    # Errors are data, never raised.
    goal = req.goal.strip()
    trace = [plan_entry(goal)]
    tool, result = researcher(goal, exec_tool, search_tool)
    trace.append({"tool": tool, "input": goal, "output": result})
    handoff = hand_off("researcher", "summarizer", {"tool": tool, "result": result, "goal": goal})
    trace.append(handoff)
    summary = summarizer(handoff)
    trace.append(summary)
    status = "done" if result.get("ok") else "error"
    body = {"goal": req.goal, "status": status, "trace": trace, "answer": summary["answer"]}
    body["run_id"] = save_run(body)
    return body


@app.get("/run/{run_id}")
def get_run(run_id: str):
    saved = load_run(run_id)
    if saved is None:
        raise HTTPException(status_code=404, detail="run not found")
    return saved
