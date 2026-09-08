from fastapi import FastAPI

app = FastAPI(title="Multi-Agent Workflow - D4")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/run")
def run(goal: str):
    # TODO 1: single agent + 1 tool
    # TODO 3-4: planner + handoff, log plan
    # TODO 5-7: persistence, guards, approval gate
    return {"goal": goal, "status": "TODO", "trace": []}
