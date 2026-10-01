"""Pluggable state: Postgres run records + Redis cost ledger, file fallback.

Rule: infra upgrades durability, never gates correctness. With no
DATABASE_URL/REDIS_URL reachable, everything runs on files + memory and
backend() reports "file". Tests force fallback; live compose gets postgres+redis.
"""
import json
import os
import socket
import uuid
from urllib.parse import urlparse

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://agents:agents@localhost:5433/agentsdb")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6380/0")

_mem_cost: dict[str, float] = {}
_probed: dict[str, bool] = {}


def _tcp_ok(url: str, timeout: float = 1.0) -> bool:
    try:
        parts = urlparse(url)
        host, port = parts.hostname or "localhost", parts.port or 5432
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _pg_ok() -> bool:
    if "pg" not in _probed:
        _probed["pg"] = _tcp_ok(DATABASE_URL)
    return _probed["pg"]


def _redis_ok() -> bool:
    if "redis" not in _probed:
        _probed["redis"] = _tcp_ok(REDIS_URL)
    return _probed["redis"]


def backend() -> str:
    if _pg_ok() and _redis_ok():
        return "postgres+redis"
    return "file"


def _pg_conn():
    import psycopg

    conn = psycopg.connect(DATABASE_URL, connect_timeout=3)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS runs "
        "(run_id TEXT PRIMARY KEY, body JSONB, created_at TIMESTAMPTZ DEFAULT now())"
    )
    return conn


def save(record: dict) -> str:
    run_id = record.get("run_id") or uuid.uuid4().hex[:12]
    record = {**record, "run_id": run_id}
    if _pg_ok():
        try:
            with _pg_conn() as conn:
                conn.execute(
                    "INSERT INTO runs (run_id, body) VALUES (%s, %s) "
                    "ON CONFLICT (run_id) DO UPDATE SET body = EXCLUDED.body",
                    (run_id, json.dumps(record, default=str)),
                )
            return run_id
        except Exception:  # noqa: BLE001 - fallback-by-design
            _probed["pg"] = False
    from app.store import save_run

    save_run(record)
    return run_id


def load(run_id: str) -> dict | None:
    if _pg_ok():
        try:
            with _pg_conn() as conn:
                row = conn.execute("SELECT body FROM runs WHERE run_id = %s", (run_id,)).fetchone()
                if row:
                    return row[0] if isinstance(row[0], dict) else json.loads(row[0])
        except Exception:  # noqa: BLE001 - fallback-by-design
            _probed["pg"] = False
    from app.store import load_run

    return load_run(run_id)


def _redis_client():
    import redis

    return redis.Redis.from_url(REDIS_URL, socket_timeout=2)


def record_cost(run_id: str, amount: float) -> None:
    if _redis_ok():
        try:
            _redis_client().incrbyfloat(f"cost:{run_id}", amount)
            return
        except Exception:  # noqa: BLE001 - fallback-by-design
            _probed["redis"] = False
    _mem_cost[run_id] = _mem_cost.get(run_id, 0.0) + amount


def total_cost(run_id: str) -> float:
    if _redis_ok():
        try:
            value = _redis_client().get(f"cost:{run_id}")
            return float(value) if value is not None else 0.0
        except Exception:  # noqa: BLE001 - fallback-by-design
            _probed["redis"] = False
    return _mem_cost.get(run_id, 0.0)
