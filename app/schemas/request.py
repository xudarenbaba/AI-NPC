""" /chat 请求体定义 """
from typing import Any, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """游戏客户端发来的聊天请求"""

    player_id: str = Field(..., description="玩家唯一标识")
    message: str = Field(..., description="玩家当前输入的对话文本")
    scene_info: Optional[dict[str, Any]] = Field(
        default_factory=dict,
        description="当前场景信息，如地点、时间、周围 NPC 等",
    )
    npc_id: Optional[str] = Field(default=None, description="当前对话的 NPC 标识，可选")
