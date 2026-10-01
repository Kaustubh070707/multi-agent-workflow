# Multi-Agent AI Workflow

Planner-worker agents with real tools, safe failure modes, and measured eval — every run traced, every failure a shaped response instead of a crash.

## Try it

```bash
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
# POST /run {"goal": "calc: 12*8+3"} -> done with 99 + run_id
# GET /run/{id} replays the run from disk (survives restart)
# POST /approve {"approval_token": "<run_id>"} resumes gated goals
```

Goals starting `calc:` run sandboxed Python; everything else searches the web. Goals with irreversible words (`send`, `email`, `delete`, `publish`, `pay`) wait for human approval with zero tool calls first.

## Architecture

```
[goal] -> [planner: ordered steps, logged first] -> [researcher: tools] -> [handoff] -> [summarizer: answer]
                guards (step limit 25, $0.50 budget, 3 retries) watch every attempt
                runs persist to runs/{id}.json — GET /run/{id} replays after restart
```

- Typed tools, errors-as-data: `search_tool` (web, 5s timeout) and `exec_tool` (sandboxed builtins, 5s daemon-thread timeout) return `{"ok":...}`, never raise.
- Explicit handoff envelope between agents; planner is deterministic rules (no LLM, fully reproducible).
- Cost ledger per attempt; loop and budget trips recorded in-trace with reasons.

## Results (20 scenarios, `python eval/run_eval.py`)

| Result | Detail |
|---|---|
| **20/20 (100%)** | avg $0.0072/run, 1.1 tool steps (target was 85%) |
| calc (12) | 10 done, 2 correctly errored (`import` blocked, infinite loop timed out) |
| live search (2) | error-handled offline by design; succeed where network works |
| approval (5) | gated pre-execution, resumed after approve, bad tokens rejected |
| multi-step plan (1) | plan steps drive the worker, not the raw goal string |

## Repo layout

```
app/agents.py       researcher, handoff, summarizer
app/planner.py      deterministic plan-first decomposition
app/tools.py        search + exec tools (timeouts, sandbox)
app/guards.py       step/budget limits
app/store.py        file run store + resume endpoint
eval/scenarios.jsonl  20 tasks
tests/              15 tests (contract shapes, guards, gates, persistence)
SKILL.md            engineering log — decisions, numbers, failures
```

## Limitations (honest)

- Planner is rules, not an LLM — open-ended goals get keyword routing, not reasoning. LangGraph is installed for the day workflows need real cycles.
- State is files, not Postgres/Redis — resume contract proven, zero infra.
- Pricing is placeholder ($0.01/search) until real LLM billing plugs in.
- Web search needs network; the sandbox here times out, so live-search scenarios assert safe handling, not live answers.
