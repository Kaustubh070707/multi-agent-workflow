from fastapi import FastAPI
from pydantic import BaseModel

from app.tools import exec_tool, search_tool

app = FastAPI(title="Multi-Agent Workflow - D4")


class RunRequest(BaseModel):
    goal: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/run")
def run(req: RunRequest):
    # Step 2: route by prefix — calc: goes to exec, everything else to search.
    # Errors are data, never raised.
    goal = req.goal.strip()
    if goal.lower().startswith("calc:"):
        tool, result = "exec", exec_tool(goal[5:].strip())
    else:
        tool, result = "search", search_tool(goal)
    trace = [{"tool": tool, "input": goal, "output": result}]
    status = "done" if result.get("ok") else "error"
    return {"goal": req.goal, "status": status, "trace": trace}
