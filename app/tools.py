import concurrent.futures
import io
import threading
from contextlib import redirect_stdout

from ddgs import DDGS

SEARCH_TIMEOUT_SECONDS = 5
SEARCH_MAX_RESULTS = 5

_search_pool = concurrent.futures.ThreadPoolExecutor(
    max_workers=2,thread_name_prefix="search-tool"
)

def _ddg_search(query:str) -> list[dict]:
    with DDGS(timeout=SEARCH_TIMEOUT_SECONDS) as ddgs:
        return list(ddgs.text(query,max_results=SEARCH_MAX_RESULTS))

"""Typed tools - errors as data, never hidden exceptions. Timeouts enforced."""
def search_tool(query: str) -> dict:
    try:
        future = _search_pool.submit(_ddg_search,query)
        results = future.result(timeout=SEARCH_TIMEOUT_SECONDS)
        return {"ok":True,"data":results}
    except concurrent.futures.TimeoutError:
        return {
             "ok": False,
            "error": f"search timed out after {SEARCH_TIMEOUT_SECONDS}s",
        }
    except Exception as exc:  # noqa: BLE001 - errors-as-data by design
        return {"ok": False, "error": str(exc) or exc.__class__.__name__}
def db_tool(sql: str) -> dict:
    return {"ok": False, "error": "TODO"}


EXEC_TIMEOUT_SECONDS = 5
EXEC_MAX_CHARS = 2000

_SAFE_BUILTINS = {
    "abs": abs, "min": min, "max": max, "sum": sum, "len": len,
    "range": range, "round": round, "sorted": sorted, "pow": pow,
    "int": int, "float": float, "str": str, "bool": bool, "list": list,
    "dict": dict, "tuple": tuple, "set": set, "enumerate": enumerate,
    "zip": zip, "print": print,
}


def _exec_code(code: str) -> str:
    if len(code) > EXEC_MAX_CHARS:
        raise ValueError(f"code too long ({len(code)} > {EXEC_MAX_CHARS} chars)")
    buf = io.StringIO()
    env = {"__builtins__": _SAFE_BUILTINS}
    try:
        value = eval(compile(code, "<agent>", "eval"), env)
        printed = buf.getvalue().strip()
        out = (printed + "\n" if printed else "") + f"result = {value!r}"
        return out
    except SyntaxError:
        pass
    with redirect_stdout(buf):
        exec(compile(code, "<agent>", "exec"), env)  # noqa: S102 - sandboxed builtins, timeout-guarded, agent tool by design
    out = buf.getvalue().strip()
    if "result" in env:
        out = (out + "\n" if out else "") + f"result = {env['result']!r}"
    return out or "(no output)"


def _call_with_timeout(fn, timeout: float):
    """Run fn in a daemon thread so infinite loops can't hang the process."""
    box: dict = {}
    done = threading.Event()

    def target():
        try:
            box["value"] = fn()
        except Exception as exc:  # noqa: BLE001 - errors-as-data by design
            box["error"] = exc
        finally:
            done.set()

    worker = threading.Thread(target=target, daemon=True)
    worker.start()
    if not done.wait(timeout):
        raise TimeoutError(f"timed out after {timeout}s")
    if "error" in box:
        raise box["error"]
    return box.get("value")


def exec_tool(code: str) -> dict:
    """Run a Python snippet, sandboxed stdlib-only. Never raises."""
    try:
        return {"ok": True, "data": _call_with_timeout(lambda: _exec_code(code), EXEC_TIMEOUT_SECONDS)}
    except TimeoutError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001 - errors-as-data by design
        return {"ok": False, "error": str(exc) or exc.__class__.__name__}
