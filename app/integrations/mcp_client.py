"""MCP 客户端封装：通过 stdio 连接本地 MCP 服务并调用工具。"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


def _default_server_args() -> tuple[str, list[str]]:
    """默认使用当前 Python 启动项目内的 MCP 服务脚本。"""
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    script = os.path.join(project_root, "npc_mcp", "local_server.py")
    return sys.executable, [script]


class MCPToolClient:
    """简单 MCP 客户端：每次调用建立一次短连接，便于与 Flask 同步代码集成。"""

    def __init__(self, command: str | None = None, args: list[str] | None = None):
        d_cmd, d_args = _default_server_args()
        self.command = command or d_cmd
        self.args = args or d_args

    def list_tools(self) -> list[dict[str, Any]]:
        return asyncio.run(self._list_tools_async())

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        return asyncio.run(self._call_tool_async(name, arguments or {}))

    async def _list_tools_async(self) -> list[dict[str, Any]]:
        params = StdioServerParameters(command=self.command, args=self.args)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                tools = []
                for t in result.tools:
                    tools.append(
                        {
                            "name": t.name,
                            "description": t.description or "",
                            "input_schema": getattr(t, "inputSchema", None) or {"type": "object"},
                        }
                    )
                return tools

    async def _call_tool_async(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        params = StdioServerParameters(command=self.command, args=self.args)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name=name, arguments=arguments)
                # MCP 返回 content[]，常见是 text/json 文本，统一转换为 dict
                if not result.content:
                    return {}
                first = result.content[0]
                text = getattr(first, "text", "")
                if not text:
                    return {"content": str(first)}
                try:
                    return json.loads(text)
                except Exception:
                    return {"text": text}

