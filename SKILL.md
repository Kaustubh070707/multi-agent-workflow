---
project: multi-agent-workflow
track: ai-ml
level: advanced
started: 2026-09-09
shipped:
repo:
live:
---
# 1. What this project is
Non-technical: Several specialised AI helpers that plan, use tools, and finish a multi-step job safely with approval.
Engineer: LangGraph planner-worker system with typed tools, persisted resumable state, budgets, guards, full trace log.

# 2. Problem it solves
Completes multi-step tasks (search + DB + API + code exec) reliably, failing safely instead of looping or overspending.

# 3. Architecture
```
[Goal] -> [Planner: ordered subtasks + logged plan] -> [Workers w/ scoped tools] -> [Tools: search, db, api, exec]
State: Postgres + Redis checkpoint, resume after restart. Guards: step limit, cost breaker, human approval.
```
Components:
- planner -> decompose -> explicit handoff protocol, logged before exec
- workers -> scoped tool access -> least privilege per agent
- tools -> typed schemas, timeouts, errors-as-data -> agent can see + recover
- guards -> loop detection, budget breaker -> stops runaway

# 4. Key decisions and trade-offs
| Decision | Options I considered | What I chose | Why | What I gave up |
|---|---|---|---|---|
| Orchestrator | LangGraph vs CrewAI | LangGraph TBD | State + cycles explicit | CrewAI speed |
| State | Postgres vs in-mem | Postgres + checkpoint | Resume mid-run | Simplicity |
| Errors | exceptions vs errors-as-data | errors-as-data | Agent can reason | Call-stack fidelity |

# 5. Skills demonstrated
- [ ] Agent orchestration evidence: `app/graph.py`
- [ ] Typed tool-calling evidence: `app/tools.py`
- [ ] Resumable state evidence: checkpoint config
- [ ] Budgets/circuit breaker evidence: `app/guards.py`
- [ ] Human-in-loop evidence: approval gate endpoint
- [ ] Eval + tracing evidence: `eval/scenarios.jsonl` + trace log

# 6. Numbers I measured
| Metric | Before | After | How I measured it |
|---|---|---|---|
| success rate 20 scenarios | TBD | 85% target | scenario suite |
| avg cost/run | TBD | TBD | token counter |
| avg steps/run | TBD | TBD | trace log |

# 7. Things that broke and how I fixed them
1. Symptom:
   Cause:
   Fix:
   Lesson:

# 8. What I would do differently at 100x scale
- TBD:
- TBD:
- TBD:

# 9. Interview answers I have rehearsed
Q: Agent stuck calling same tool repeatedly - how do you stop it?
A:
Q: Tool returns garbage - does agent notice? Show me how.
A:
Q: How do you cap what a runaway costs?
A:

# 10. Honest limitations
<What this does NOT do.>

# 11. How to run it
```bash
git clone <repo> && cd multi-agent-workflow
cp .env.example .env
docker compose up --build
# open http://localhost:8000/docs
```
Required environment variables: OPENAI_API_KEY, DATABASE_URL, REDIS_URL

# 12. Credits
- https://github.com/microsoft/generative-ai-for-beginners
- https://github.com/langchain-ai/langchain
- https://github.com/eugeneyan/applied-ml
