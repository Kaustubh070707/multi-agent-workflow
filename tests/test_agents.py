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


def test_exec_errors_are_data():
    from app.tools import exec_tool

    ok = exec_tool("result = 6*7")
    assert ok["ok"] is True and "42" in str(ok.get("data"))

    bad = exec_tool("import os")
    assert bad["ok"] is False and bad["error"]

    slow = exec_tool("while True:\n    pass")
    assert slow["ok"] is False and "timed out" in slow["error"]
