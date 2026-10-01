"""File-backed run store. Every completed run persists as runs/{id}.json.

Survives restarts by construction — reads never touch process memory.
Postgres + Redis checkpoint is the documented next step (SKILL.md);
files prove the resume contract with zero infra.
"""
import json
import uuid
from pathlib import Path

RUNS_DIR = Path("runs")


def _path(run_id: str) -> Path:
    safe = "".join(c for c in run_id if c.isalnum() or c in "-_")[:64]
    return RUNS_DIR / f"{safe}.json"


def save_run(record: dict) -> str:
    run_id = record.get("run_id") or uuid.uuid4().hex[:12]
    record = {**record, "run_id": run_id}
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    _path(run_id).write_text(json.dumps(record, default=str), encoding="utf-8")
    return run_id


def load_run(run_id: str) -> dict | None:
    try:
        return json.loads(_path(run_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
