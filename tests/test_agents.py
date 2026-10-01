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
    assert body["trace"][0]["tool"] == "search"


def test_run_calc_shape():
    r = client.post("/run", json={"goal": "calc: 12*8+3"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "done"
    assert body["trace"][0]["tool"] == "exec"
    assert "99" in str(body["trace"][0]["output"])


def test_exec_errors_are_data():
    from app.tools import exec_tool

    ok = exec_tool("result = 6*7")
    assert ok["ok"] is True and "42" in str(ok.get("data"))

    bad = exec_tool("import os")
    assert bad["ok"] is False and bad["error"]

    slow = exec_tool("while True:\n    pass")
    assert slow["ok"] is False and "timed out" in slow["error"]
