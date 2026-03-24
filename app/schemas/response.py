""" 动作指令 JSON 结构，与游戏引擎约定 """
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class ActionResponse(BaseModel):
    """NPC 动作指令，由后端返回给游戏客户端执行"""

    action_type: Literal["dialogue", "move", "emote", "use_item", "idle"] = Field(
        default="dialogue",
        description="动作类型",
    )
    dialogue: str = Field(default="", description="NPC 对玩家说的台词")
    emotion: Optional[str] = Field(default=None, description="情绪/表情标签")
    target_id: Optional[str] = Field(default=None, description="动作目标，如移动目标、使用对象")
    extra: Optional[dict[str, Any]] = Field(default=None, description="扩展字段")
