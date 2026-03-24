"""本地 MCP 服务示例：挂载 NPC 状态查询工具。"""

import os
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

# 确保可以导入项目内 app 包
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.tools.npc_state_tools import get_npc_runtime_state_local

mcp = FastMCP("ai-npc-local-mcp")


@mcp.tool()
def get_npc_runtime_state(npc_id: str) -> dict[str, Any]:
    """
    获取 NPC 当前运行状态。
    """
    return get_npc_runtime_state_local(npc_id)


if __name__ == "__main__":
    # stdio 模式，便于 MCP 客户端接入
    mcp.run()

