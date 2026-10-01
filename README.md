# D4 Multi-Agent AI Workflow with Tool Calling

> Track D / Advanced / 4 weeks. Planner-worker agents with real tools, safe failure, eval.

## Build order (do in order)
1. Single agent + 1 tool. Reliable first.
2. Typed schemas, errors-as-data (never hidden exceptions).
3. 2nd agent + explicit handoff protocol.
4. Planner, log plan before exec.
5. Persistence (survives restart mid-run).
6. Break on purpose: fail tool, force loop, exceed budget. Add guards.
7. Human approval gate for destructive/costly ops.
8. Run 20 scenarios, publish success/cost/steps table.

## Run
```bash
pip install -r requirements-dev.txt
cp .env.example .env
ruff check app/ && pytest -q
uvicorn app.main:app --reload
# POST /run {"goal": "calc: 12*8+3"} -> done with 99; search goals call the web tool
```

## Eval
`eval/scenarios.jsonl` - 20 tasks. Most valuable part is the results table in README.

| Scenario | Success | Cost | Steps |
|---|---|---|---|
| TBD | | | |

## Gate
1. Same tool loop - how stopped?
2. Garbage tool output - does agent notice?
3. Cost cap for runaway?
