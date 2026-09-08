"""Typed tools - errors as data, never hidden exceptions. Timeouts enforced."""
def search_tool(query: str) -> dict:
    # TODO: implement with timeout, return {"ok": True, "data": ...} or {"ok": False, "error": ...}
    return {"ok": False, "error": "TODO"}

def db_tool(sql: str) -> dict:
    return {"ok": False, "error": "TODO"}
