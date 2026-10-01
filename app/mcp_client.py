"""MCP client: calls the `calc` tool on the bundled stdio server.

Errors are data, never raised — same contract as app/tools.py.
Spawns one short-lived server subprocess per call (documented cost);
local exec_tool stays the fast path.
"""
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

_PARAMS = StdioServerParameters(
    command=sys.executable,
    args=["-m", "app.mcp_server"],
)


async def _call_calc(code: str, timeout: float) -> str:
    import anyio

    async with stdio_client(_PARAMS) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        with anyio.fail_after(timeout):
            result = await session.call_tool("calc", {"code": code})
    parts = []
    for block in result.content:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts) or "(no output)", bool(getattr(result, "isError", False))


def mcp_calc_tool(code: str, timeout: float = 30.0) -> dict:
    """Call calc over MCP stdio. Never raises."""
    import anyio

    try:
        data, is_error = anyio.run(_call_calc, code, timeout)
        if is_error:
            return {"ok": False, "error": data or "tool error"}
        return {"ok": True, "data": data}
    except Exception as exc:  # noqa: BLE001 - errors-as-data by design
        return {"ok": False, "error": str(exc) or exc.__class__.__name__}
