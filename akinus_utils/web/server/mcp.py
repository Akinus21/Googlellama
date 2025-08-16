# mcp.py
from akinus_utils.utils.app_details import APP_NAME
from mcp.server.fastmcp import FastMCP

# Create the shared MCP server instance
mcp = FastMCP(APP_NAME)

# Wrap the original decorator to add CLI tagging
_original_tool_decorator = mcp.tool

def tool_with_cli_tag(*args, **kwargs):
    def wrapper(func):
        func._mcp_tool = True  # ✅ Tag for CLI discovery
        return _original_tool_decorator(*args, **kwargs)(func)
    return wrapper

# Replace the default .tool decorator with our wrapped version
mcp.tool = tool_with_cli_tag