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
Engineer: LangGraph planner-worker graph (plan -> act retry-cycle -> summarize, Postgres or memory checkpoint) with typed tools, file+Postgres resumable state, Redis cost ledger, budgets, guards, full trace log. Deterministic rule planner (no LLM) keeps the 20/20 reproducible.

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
| Orchestrator | LangGraph vs CrewAI vs deterministic rules | LangGraph graph (`app/graph.py`) over deterministic rule planner | Retries are a real graph cycle (act routes back to act), checkpoints persist per thread; the planner stays rules so the 20/20 reproduces. Gave up pure-simplicity: graph adds nodes/edges/checkpointer concepts. |
| Tool transport | In-process calls vs MCP stdio | Both: local `exec`/`search` fast path plus `mcp:` prefix routed to `mcp_calc_tool` via bundled `app/mcp_server.py` | MCP proves tool-calling over a protocol boundary (server/client, timeouts, `isError`); local path stays for speed. Gave up per-call subprocess cost on the MCP path (~1-2s spawn). |
| State | Files only vs Postgres+Redis | Postgres `runs` table + Redis cost ledger with file/memory fallback (`app/state.py`, `docker-compose.yml`) | Infra upgrades durability without gating correctness: `backend()` reports `postgres+redis` live, `file` otherwise; tests force fallback. Gave up single-backend simplicity. |
| Planner | LLM planner vs rule planner | Rules (`calc:` prefix, and/then splitting) | Every plan is reproducible and asserted in tests; an LLM planner would make the 20/20 non-deterministic | Handling open-ended goals |
| State | Postgres vs in-mem | Postgres + checkpoint | Resume mid-run | Simplicity |
| Errors | exceptions vs errors-as-data | errors-as-data | Agent can reason | Call-stack fidelity |

# 5. Skills demonstrated
- [x] Single agent + routing evidence: `app/main.py` `POST /run` — `calc:` goes to exec, everything else to search, every run returns a `trace`
- [x] Typed tool-calling evidence: `app/tools.py` — `search_tool` (DDG + 5s pool timeout) and `exec_tool` (sandboxed builtins + 5s daemon-thread timeout, eval-first for expressions), both `{"ok":...}` errors-as-data, never raise
- [x] MCP transport evidence: `app/mcp_server.py` (FastMCP stdio `calc`, same sandbox) + `app/mcp_client.py` (timeout, `isError` honored) — `mcp:` goals route through it; priced as search
- [x] Two-agent handoff evidence: `app/agents.py` — `researcher` works, `hand_off` moves the envelope explicitly, `summarizer` formats the final `answer`; mismatch caught by test before demo
- [x] Planner evidence: `app/planner.py` — deterministic rules (`calc:` → exec, else search+summarize, splits on and/then), logged as first trace entry before any tool runs
- [x] Resumable state evidence: `app/store.py` (file) + `app/state.py` (Postgres `runs` table + Redis cost ledger, file/memory fallback) — live `docker-compose.yml:1` verified `postgres+redis` round-trip; `runs/` ignored
- [x] Budgets/circuit breaker evidence: `POST /run` costs every attempt (search $0.01, exec $0.001 placeholder pricing), retries failing steps up to 3×, then `should_stop` trips with a `guard` trace entry stating step vs cost reason
- [x] Human-in-loop evidence: `needs_approval` keyword gate (send/email/delete/publish/pay) — `POST /run` returns `awaiting_approval` with zero tool calls, `POST /approve` resumes; bad tokens 403
- [ ] Eval + tracing evidence: `eval/scenarios.jsonl` 2 samples, 20-scenario table pending (Step 8)

# 6. Numbers I measured
| Metric | Before | After | How I measured it |
|---|---|---|---|
| success rate 20 scenarios | — | 20/20 (100%) on first full run | `python eval/run_eval.py`: 12 calc, 2 live-search (error-handled offline), 5 approval-gated, 1 multi-step |
| avg cost/run | — | $0.0072 | cost ledger in trace (`COST_PER_SEARCH 0.01`, `COST_PER_EXEC 0.001` placeholder pricing) |
| avg steps/run | — | 1.1 tool calls | counted from trace entries |
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
5. Symptom: The guard test reported `cost budget reached ($0.03 >= $0.50)` — a budget trip that never happened.
   Cause: `from app.guards import MAX_STEPS` binds the value at import time. The test patched `guards.MAX_STEPS` to 3, `should_stop` saw 3 and tripped correctly, but my reason-string check still read the stale 25 and blamed cost.
   Fix: Read `guards.MAX_STEPS` live at check time. Same rule as the daemon threads: shared mutable config must be read, not copied.
7. Symptom: The 20-scenario eval printed nothing and exited 0 — three runs in a row, no error, no output.
   Cause: `redirect_stdout` swaps `sys.stdout` for the whole process. The `while True` scenario's daemon thread never leaves its `with` block, so every later `print` in the process flowed into its dead buffer. The eval was actually running fine underneath.
   Fix: Print is now collected per call (a local list injected as the sandbox `print`), never a global redirect. Verified: same eval immediately printed 20/20.
   Lesson: Never mutate process-global state from inside code that can outlive its caller. Thread-local collection instead of global redirection, always.
8. Symptom: The planner split `while True:\n pass` into two steps (`while True:` + `pass`), decapitating the code.
   Cause: I fixed newline-splitting in `_split_parts` but `plan()` strips the `calc:` prefix before calling it, so multi-line code fell into the generic branch that still splits newlines. Fixed the wrong door.
   Fix: `_split_parts` takes a `code=True` flag; `plan()` passes it for calc goals. Verified with a real-newline reproduction (shell quoting had hidden the bug twice).
   Lesson: Test with real newlines from a file, not shell `-c` strings — PowerShell mangles `\n` into literals and the repro lies to you.
   Lesson: `from x import NAME` freezes values. Anything tests need to move — limits, flags, prices — must be read off the module each time.
6. Decision, not a bug: the approval token *is* the pending run_id.
   Cause: A separate token store would be a second source of truth to keep in sync. The run_id is already unguessable hex, already persisted, already unique.
   Fix: `/approve` looks up the run_id and requires status `awaiting_approval`; anything else gets 403. Both paths share one `_execute`, so approved and direct runs behave identically — proven by the same assertions running against both.
   Lesson: Reuse identity instead of inventing it. Every new ID scheme is a new thing to expire, revoke, and leak.
4. Symptom: Two old tests broke the moment the planner landed — `KeyError: 'tool'` on `trace[0]`.
   Cause: The trace contract grew a head. Plan entries sit first now, so `trace[0]` is intent, not action. The tests assumed positions instead of roles.
   Fix: Old shape tests now assert `trace[0]` is the plan and `trace[1]` is the first tool. New tests pin the planner: calc plans one exec step, search plans search+summarize, `and then` splits.
   Lesson: When the trace gains a stage, update shape tests to name stages by kind, not index. Positions shift; roles don't.
9. Symptom: `mcp: import os` came back `ok: True` with a traceback as the "data".
   Cause: MCP delivers tool failures as result content flagged `isError`, not as exceptions. My client collected text and ignored the flag — a traceback counted as success.
   Fix: Honor `isError`: error-flagged content returns `{"ok": False, ...}`. Same errors-as-data contract, one layer deeper.
   Lesson: Every transport boundary re-hides errors in a new shape. Assert the failure path per transport, not just per tool.
10. Symptom: Tests patched `graph.TOOLS` and went green — while the flow ignored the dict and used import-bound names.
    Cause: `act_node` called `researcher(goal, exec_tool, search_tool)` with module imports; TOOLS existed only as decoration. Patches proved nothing.
    Fix: `act_node` now reads `TOOLS[...]` entries, so `setitem` patches genuinely steer the flow. Verified by watching the tests fail before the fix and pass after.
    Lesson: A patch surface the code doesn't read is a lie the suite tells itself. After writing a seam, prove it steers.

# 8. What I would do differently at 100x scale
- Replace the rule planner with an LLM planner behind the same `plan()` shape, keeping deterministic eval as the regression gate so the 20/20 stays meaningful.
- Move exec off threads into real sandboxes (gVisor/Firecracker per call) and Postgres LISTEN/NOTIFY instead of file polling, because daemon threads and file stores don't survive real multi-tenancy.
- Sign tool results and pin MCP server versions — today any local process can pose as `app.mcp_server`, which is fine for a demo and unacceptable at scale.

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
