from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_run_search_shape():
    r = client.post("/run", json={"goal": "Find latest FastAPI release"})
    assert r.status_code == 200
    body = r.json()
    assert body["goal"] == "Find latest FastAPI release"
    assert body["status"] in ("done", "error")
    assert isinstance(body["trace"], list) and body["trace"]
    assert body["trace"][0].get("kind") == "plan"
    assert body["trace"][1]["tool"] == "search"


def test_run_calc_shape():
    r = client.post("/run", json={"goal": "calc: 12*8+3"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "done"
    assert body["trace"][1]["tool"] == "exec"
    assert "99" in str(body["trace"][1]["output"])


def test_handoff_protocol_shape():
    from app.main import RunRequest, run

    body = run(RunRequest(goal="calc: 12*8+3"))
    kinds = [t.get("kind", "tool") for t in body["trace"]]
    assert "handoff" in kinds
    handoff = next(t for t in body["trace"] if t.get("kind") == "handoff")
    assert handoff["from"] == "researcher" and handoff["to"] == "summarizer"
    assert "payload" in handoff


def test_summarizer_formats_answer():
    from app.main import RunRequest, run

    body = run(RunRequest(goal="calc: 6*7"))
    assert body["status"] == "done"
    assert "42" in body["answer"]
    assert body["trace"][-1]["kind"] == "summary"


def test_plan_logged_before_execution():
    from app.main import RunRequest, run

    body = run(RunRequest(goal="calc: 6*7"))
    assert body["trace"][0].get("kind") == "plan"
    assert isinstance(body["trace"][0]["steps"], list) and body["trace"][0]["steps"]


def test_planner_splits_steps():
    from app.planner import plan

    calc = plan("calc: 6*7")
    assert len(calc) == 1 and calc[0]["tool"] == "exec"
    search = plan("Find latest FastAPI release and summarize")
    assert [s["tool"] for s in search] == ["search", "summarize"]
    multi = plan("calc: 2+2 and then summarize")
    assert len(multi) == 2


def test_run_persisted_and_resumable(tmp_path, monkeypatch):
    from app import store

    monkeypatch.setattr(store, "RUNS_DIR", tmp_path)
    from app.main import RunRequest, run
    from app.store import load_run

    body = run(RunRequest(goal="calc: 6*7"))
    assert body.get("run_id")
    # fresh read, as after a restart — no in-memory state involved
    saved = load_run(body["run_id"])
    assert saved["goal"] == "calc: 6*7"
    assert saved["answer"] == body["answer"]
    assert saved["trace"][0].get("kind") == "plan"


def test_get_run_endpoint(tmp_path, monkeypatch):
    from app import store

    monkeypatch.setattr(store, "RUNS_DIR", tmp_path)
    from fastapi.testclient import TestClient

    from app.main import app

    c = TestClient(app)
    posted = c.post("/run", json={"goal": "calc: 2+2"}).json()
    fetched = c.get(f"/run/{posted['run_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["answer"] == posted["answer"]
    assert c.get("/run/does-not-exist").status_code == 404


def test_guard_stops_error_loop(monkeypatch):
    from app import guards, main

    monkeypatch.setattr(guards, "MAX_STEPS", 3)
    monkeypatch.setattr(main, "MAX_RETRIES", 10)
    monkeypatch.setattr(main, "search_tool", lambda q: {"ok": False, "error": "down"})

    body = main.run(main.RunRequest(goal="Find something"))
    assert body["status"] == "stopped"
    reasons = [t for t in body["trace"] if t.get("kind") == "guard"]
    assert reasons and "step" in reasons[0].get("reason", "")
    attempts = [t for t in body["trace"] if "tool" in t]
    assert len(attempts) <= 4


def test_budget_stops_run(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "search_tool", lambda q: {"ok": False, "error": "down"})
    monkeypatch.setattr(main, "COST_PER_SEARCH", 10.0)
    body = main.run(main.RunRequest(goal="Find something"))
    assert body["status"] == "stopped"
    guard_reasons = [t.get("reason", "") for t in body["trace"] if t.get("kind") == "guard"]
    assert any("cost" in r or "budget" in r for r in guard_reasons)


def test_approval_blocks_tool(tmp_path, monkeypatch):
    from app import store

    monkeypatch.setattr(store, "RUNS_DIR", tmp_path)
    from fastapi.testclient import TestClient

    from app import main
    from app.main import app

    calls = []
    monkeypatch.setattr(main, "search_tool", lambda q: calls.append(q) or {"ok": True, "data": []})
    c = TestClient(app)
    body = c.post("/run", json={"goal": "send email report to team"}).json()
    assert body["status"] == "awaiting_approval"
    assert calls == []
    assert "approval_token" in body


def test_approve_resumes_run(tmp_path, monkeypatch):
    from app import store

    monkeypatch.setattr(store, "RUNS_DIR", tmp_path)
    from fastapi.testclient import TestClient

    from app import main
    from app.main import app

    monkeypatch.setattr(main, "search_tool", lambda q: {"ok": True, "data": [{"title": "t"}]})
    c = TestClient(app)
    pending = c.post("/run", json={"goal": "send email report to team"}).json()
    done = c.post("/approve", json={"approval_token": pending["approval_token"]}).json()
    assert done["status"] == "done"
    assert done["trace"][0].get("kind") == "plan"
    bad = c.post("/approve", json={"approval_token": "nope"})
    assert bad.status_code in (403, 404)


def test_exec_errors_are_data():
    from app.tools import exec_tool

    ok = exec_tool("result = 6*7")
    assert ok["ok"] is True and "42" in str(ok.get("data"))

    bad = exec_tool("import os")
    assert bad["ok"] is False and bad["error"]

    slow = exec_tool("while True:\n    pass")
    assert slow["ok"] is False and "timed out" in slow["error"]
