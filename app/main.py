from fastapi import FastAPI
from pydantic import BaseModel

from app.tools import search_tool

app = FastAPI(title="Multi-Agent Workflow - D4")


class RunRequest(BaseModel):
    goal: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/run")
def run(req: RunRequest):
    # Step 1: single agent + 1 tool (search). Errors are data, never raised.
    result = search_tool(req.goal)
    trace = [{"tool": "search", "input": req.goal, "output": result}]
    status = "done" if result.get("ok") else "error"
    return {"goal": req.goal, "status": status, "trace": trace}
