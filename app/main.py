from fastapi import FastAPI
from pydantic import BaseModel

from app.agents import hand_off, researcher, summarizer
from app.tools import exec_tool, search_tool

app = FastAPI(title="Multi-Agent Workflow - D4")


class RunRequest(BaseModel):
    goal: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/run")
def run(req: RunRequest):
    # Step 3: researcher works, hands off explicitly, summarizer answers.
    # Errors are data, never raised.
    goal = req.goal.strip()
    tool, result = researcher(goal, exec_tool, search_tool)
    trace = [{"tool": tool, "input": goal, "output": result}]
    handoff = hand_off("researcher", "summarizer", {"tool": tool, "result": result, "goal": goal})
    trace.append(handoff)
    summary = summarizer(handoff)
    trace.append(summary)
    status = "done" if result.get("ok") else "error"
    return {"goal": req.goal, "status": status, "trace": trace, "answer": summary["answer"]}
