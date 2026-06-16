# app/server.py
from fastmcp import FastMCP

mcp = FastMCP("PRC MCP")

@mcp.tool()
def ping() -> str:
    """Basic health test tool."""
    return "pong from prcmcp"