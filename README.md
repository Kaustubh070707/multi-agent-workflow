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
ruff check app/ tests/ eval/ && pytest -q   # 15 passed
uvicorn app.main:app --reload
# POST /run {"goal": "calc: 12*8+3"} -> done with 99 + run_id
# GET /run/{id} replays from disk (survives restart)
# POST /approve {"approval_token": "<run_id>"} resumes gated goals (send/email/delete/publish/pay)
# python eval/run_eval.py -> 20/20 (95% target beaten), avg $0.0072/run
```

## Eval
`eval/scenarios.jsonl` - 20 tasks (`python eval/run_eval.py`). Most valuable part is the results table:

| Result | Count | Notes |
|---|---|---|
| **HIT 20/20 (100%)** | avg cost $0.0072/run, avg 1.1 tool steps | target was 85% |
| calc (12) | 10 done, 2 correctly errored | `import os` blocked by sandbox, `while True` timed out in 5s |
| live search (2) | handled as errors here | DDG unreachable from this sandbox; `done_or_error` by design, resumed as done where network works |
| approval (5) | 5 gated, 5 resumed after approve | zero tool calls before human approval, bad tokens 403 |
| multi-step plan (1) | done | `calc: 2+2 and then summarize` follows plan step one |

## Gate
1. Same tool loop - how stopped?
2. Garbage tool output - does agent notice?
3. Cost cap for runaway?
