"""本地/ MCP 共享的 NPC 状态工具。"""

from typing import Any

NPC_STATE = {
    "default": {
        "location": {"x": 10, "y": 5, "z": 0},
        "job": "村民",
        "task": "巡逻",
        "available_actions": ["dialogue", "move", "idle"],
    },
    "npc_guard_001": {
        "location": {"x": 5, "y": 5, "z": 0},
        "job": "守卫",
        "task": "看守城门",
        "available_actions": ["dialogue", "idle", "emote"],
    },
    "npc_merchant_001": {
        "location": {"x": 42, "y": 18, "z": 0},
        "job": "商人",
        "task": "售卖补给",
        "available_actions": ["dialogue", "move", "use_item", "idle"],
    },
}


def get_npc_runtime_state_local(npc_id: str) -> dict[str, Any]:
    """获取 NPC 当前状态。可以返回npc的坐标，能做的任务等"""
    item = NPC_STATE.get(npc_id) or NPC_STATE["default"]
    return {
        "npc_id": npc_id,
        "location": item["location"],
        "job": item["job"],
        "task": item["task"],
        "available_actions": item["available_actions"],
    }

