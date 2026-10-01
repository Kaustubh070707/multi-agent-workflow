"""MCP tool server (stdio): exposes the sandboxed `calc` tool over MCP.

Run: python -m app.mcp_server   (speaks MCP on stdin/stdout)
The client side lives in app/mcp_client.py. Same sandbox + timeouts as
app/tools.py exec_tool — one implementation of the safety rules.
"""
from mcp.server.fastmcp import FastMCP

from app.tools import _exec_code

mcp = FastMCP("agent-tools")


@mcp.tool()
def calc(code: str) -> str:
    """Evaluate a Python snippet in a restricted sandbox. Returns text or raises."""
    return _exec_code(code)


if __name__ == "__main__":
    mcp.run()
