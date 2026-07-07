"""MCP (Model Context Protocol) client for VRTwin.

Connects to the servers listed in `mcp_servers.json`, discovers their tools
and registers each one with the avatar's LLM so AIAvatarKit's built-in
tool-calling loop can use them. A server that fails to start is logged and
skipped, so the avatar always comes up even with a broken tool config.

The config file uses the same `mcpServers` format as Claude Desktop, plus an
optional per-server `"enabled"` flag:

    {"mcpServers": {"time": {"command": "python", "args": ["-m", "mcp_server_time"]}}}

`"command": "python"` always means this venv's interpreter.
"""

import asyncio
import json
import logging
import re
import shutil
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Dict, List

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)

APP_DIR = Path(__file__).parent
DEFAULT_CONFIG_PATH = APP_DIR / "mcp_servers.json"
WORKSPACE_DIR = APP_DIR / "mcp_workspace"

CONNECT_TIMEOUT = 30.0


def default_servers() -> Dict[str, dict]:
    """The out-of-the-box servers. fetch/time/search are pure Python and run in
    this venv; memory/filesystem need Node.js (npx) and are skipped without it."""
    return {
        "fetch": {"command": "python", "args": ["-m", "mcp_server_fetch"], "enabled": True},
        "time": {"command": "python", "args": ["-m", "mcp_server_time"], "enabled": True},
        "search": {"command": "python", "args": ["-m", "duckduckgo_mcp_server.server"], "enabled": True},
        "memory": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-memory"],
            "env": {"MEMORY_FILE_PATH": str(WORKSPACE_DIR / "memory.json")},
            "enabled": True,
        },
        "filesystem": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", str(WORKSPACE_DIR)],
            "enabled": True,
        },
    }


def ensure_default_config(config_path: Path = DEFAULT_CONFIG_PATH) -> None:
    WORKSPACE_DIR.mkdir(exist_ok=True)
    if not config_path.exists():
        save_servers(default_servers(), config_path)
        logger.info(f"Created default MCP config at {config_path}")


def load_servers(config_path: Path = DEFAULT_CONFIG_PATH) -> Dict[str, dict]:
    ensure_default_config(config_path)
    with open(config_path, encoding="utf-8") as f:
        return json.load(f).get("mcpServers", {})


def save_servers(servers: Dict[str, dict], config_path: Path = DEFAULT_CONFIG_PATH) -> None:
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump({"mcpServers": servers}, f, indent=2)
        f.write("\n")


def _resolve_command(command: str) -> str | None:
    """'python' means this venv's interpreter; otherwise look on PATH and in
    the venv's bin/Scripts dir (where pip puts console scripts)."""
    if command == "python":
        return sys.executable
    if Path(command).is_absolute():
        return command if Path(command).exists() else None
    return shutil.which(command) or shutil.which(command, path=str(Path(sys.executable).parent))


def _sanitize_tool_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name)[:64]


class MCPManager:
    def __init__(self, config_path: Path = DEFAULT_CONFIG_PATH, tool_timeout: float = 30.0):
        self.config_path = Path(config_path)
        self.tool_timeout = tool_timeout
        self.exit_stack = AsyncExitStack()
        self.sessions: Dict[str, ClientSession] = {}
        self.tools: List[tuple] = []  # (server_name, mcp.types.Tool)

    async def start(self) -> None:
        for name, entry in load_servers(self.config_path).items():
            if not entry.get("enabled", True):
                continue
            try:
                await self._connect(name, entry)
            except Exception as ex:
                logger.warning(f"MCP server '{name}' failed to start, skipping: {ex}")

    async def stop(self) -> None:
        try:
            await self.exit_stack.aclose()
        except Exception as ex:
            logger.warning(f"Error while shutting down MCP servers: {ex}")

    async def _connect(self, name: str, entry: dict) -> None:
        command = _resolve_command(entry.get("command", ""))
        if not command:
            logger.warning(f"MCP server '{name}': command '{entry.get('command')}' not found, skipping. "
                           "(npx servers need Node.js installed.)")
            return
        params = StdioServerParameters(
            command=command,
            args=entry.get("args", []),
            env=entry.get("env") or None,
        )
        read, write = await self.exit_stack.enter_async_context(stdio_client(params))
        session = await self.exit_stack.enter_async_context(ClientSession(read, write))
        await asyncio.wait_for(session.initialize(), timeout=CONNECT_TIMEOUT)
        tools = (await session.list_tools()).tools
        self.sessions[name] = session
        self.tools.extend((name, t) for t in tools)
        logger.info(f"MCP server '{name}': {', '.join(t.name for t in tools) or 'no tools'}")

    def register_tools(self, llm) -> List[str]:
        """Registers every discovered tool with the LLM as `servername_toolname`.
        Returns the registered names."""
        registered = []
        for server_name, tool in self.tools:
            spec_name = _sanitize_tool_name(f"{server_name}_{tool.name}")
            if spec_name in llm.tools:
                logger.warning(f"Duplicate MCP tool name '{spec_name}', skipping.")
                continue
            spec = {
                "type": "function",
                "function": {
                    "name": spec_name,
                    "description": tool.description or tool.name,
                    "parameters": tool.inputSchema or {"type": "object", "properties": {}},
                },
            }
            llm.tool(spec)(self._make_handler(server_name, tool.name))
            registered.append(spec_name)
        return registered

    def _make_handler(self, server_name: str, tool_name: str):
        async def handler(**kwargs):
            try:
                result = await asyncio.wait_for(
                    self.sessions[server_name].call_tool(tool_name, kwargs),
                    timeout=self.tool_timeout,
                )
            except Exception as ex:
                logger.warning(f"MCP tool {server_name}.{tool_name} failed: {ex}")
                return {"error": f"Tool call failed: {ex}"}
            texts = [c.text for c in result.content if getattr(c, "text", None)]
            text = "\n".join(texts)
            if getattr(result, "isError", False):
                return {"error": text or "Tool returned an error."}
            # Never return an empty dict: aiavatar drops falsy tool results.
            return {"result": text or "(no output)"}

        return handler
