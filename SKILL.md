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
- [x] Single agent + routing evidence: `app/main.py` `POST /run` — `calc:` goes to exec, everything else to search, every run returns a `trace`
- [x] Typed tool-calling evidence: `app/tools.py` — `search_tool` (DDG + 5s pool timeout) and `exec_tool` (sandboxed builtins + 5s daemon-thread timeout, eval-first for expressions), both `{"ok":...}` errors-as-data, never raise
- [x] Two-agent handoff evidence: `app/agents.py` — `researcher` works, `hand_off` moves the envelope explicitly, `summarizer` formats the final `answer`; mismatch caught by test before demo
- [x] Planner evidence: `app/planner.py` — deterministic rules (`calc:` → exec, else search+summarize, splits on and/then), logged as first trace entry before any tool runs
- [ ] Resumable state evidence: checkpoint config (Step 5)
- [ ] Budgets/circuit breaker evidence: `app/guards.py` exists (`MAX_STEPS 25`, `$0.50`), not wired yet (Step 6)
- [ ] Human-in-loop evidence: approval gate endpoint (Step 7)
- [ ] Eval + tracing evidence: `eval/scenarios.jsonl` 2 samples, 20-scenario table pending (Step 8)

# 6. Numbers I measured
| Metric | Before | After | How I measured it |
|---|---|---|---|
| success rate 20 scenarios | TBD | 85% target | scenario suite |
| avg cost/run | TBD | TBD | token counter |
| avg steps/run | TBD | TBD | trace log |

# 7. Things that broke and how I fixed them
1. Symptom: `pytest` hung forever and never printed a summary — had to kill the terminal.
   Cause: The `while True` timeout test spun forever inside a non-daemon pool thread, and Python joins non-daemon threads at exit. The test proved the timeout but murdered the runner.
   Fix: Timeout now runs the snippet in a `threading.Thread(daemon=True)` (`_call_with_timeout` in `app/tools.py`). Daemon threads die with the process, so a hung snippet costs 5 seconds, not the whole run.
   Lesson: Any code that can loop forever must run on a thread the process is allowed to abandon. Timeouts guard results; daemon threads guard exits.
2. Symptom: `calc: 12*8+3` returned `(no output)` instead of 99.
   Cause: The snippet was a bare expression — nothing printed, nothing assigned to `result`. My exec path only understood statements.
   Fix: Try `eval` first for single expressions (returns `result = 99`), fall back to `exec` on `SyntaxError`. Bare math now just works.
   Lesson: Agents send expressions, not programs. Meet them where they are.
3. Symptom: The new summarizer answered `Could not complete '': unknown error` on a perfectly successful exec.
   Cause: `hand_off` nests work under a `payload` key, but the summarizer read `tool`/`result`/`goal` at the top level. Producer and consumer disagreed on the envelope.
   Fix: Summarizer unwraps `handoff["payload"]` first (falling back to the dict itself). The handoff test caught it before any demo ran.
   Lesson: Every agent boundary gets a test asserting the real shape. In multi-agent systems the envelope is the API.
4. Symptom: Two old tests broke the moment the planner landed — `KeyError: 'tool'` on `trace[0]`.
   Cause: The trace contract grew a head. Plan entries sit first now, so `trace[0]` is intent, not action. The tests assumed positions instead of roles.
   Fix: Old shape tests now assert `trace[0]` is the plan and `trace[1]` is the first tool. New tests pin the planner: calc plans one exec step, search plans search+summarize, `and then` splits.
   Lesson: When the trace gains a stage, update shape tests to name stages by kind, not index. Positions shift; roles don't.

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
