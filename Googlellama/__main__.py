# Googlellama/__main__.py
import sys
import inspect
import argparse
import asyncio
from akinus.web.server.mcp import mcp
from akinus.web.google.auth import get_credentials

import Googlellama.tools as google_tools

def discover_mcp_tools(module):
    tools = {}
    for name, func in inspect.getmembers(module, inspect.iscoroutinefunction):
        if getattr(func, "_mcp_tool", False):
            tools[name] = func
    return tools

async def run_cli_tool(tool_func, args):
    sig = inspect.signature(tool_func)
    kwargs = {k: getattr(args, k) for k in sig.parameters}
    result = await tool_func(**kwargs)
    print(result)

def build_cli_parser(tools):
    parser = argparse.ArgumentParser(
        description="Run as MCP server (default) or invoke tools from google_tools.py."
    )
    subparsers = parser.add_subparsers(dest="command", help="Available tools")

    for tool_name, func in tools.items():
        doc = inspect.getdoc(func) or "No description."
        sig = inspect.signature(func)

        sub = subparsers.add_parser(tool_name, help=doc.splitlines()[0])
        sub.description = doc
        for param_name, param in sig.parameters.items():
            sub.add_argument(
                f"--{param_name}",
                required=(param.default == inspect._empty),
                help=f"{param_name} (type: {param.annotation.__name__ if param.annotation != inspect._empty else 'str'})"
            )
    return parser

def main():
    tools = discover_mcp_tools(google_tools)

    # Ensure credentials are available and valid
    try:
        creds = get_credentials()  # This will refresh or re-authorize if needed
    except FileNotFoundError:
        # Token file missing, force authorization
        from akinus.web.google.auth import authorize
        authorize()
        creds = get_credentials()

    if len(sys.argv) == 1:
        mcp.run()
    else:
        parser = build_cli_parser(tools)
        args = parser.parse_args()

        if not args.command:
            parser.print_help()
            sys.exit(1)

        asyncio.run(run_cli_tool(tools[args.command], args))


if __name__ == "__main__":
    main()