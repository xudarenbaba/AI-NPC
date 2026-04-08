"""与 app/tools/npc_state_tools.NPC_STATE 对齐的 Demo 角色信息。

screen_x/screen_y 仅作为兜底坐标；当前默认由 game.layout.NPC_ANCHORS 决定初始落点。
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NpcProfile:
    npc_id: str
    display_name: str
    job: str
    task: str
    available_actions: tuple[str, ...]
    """与后端 MCP 一致的世界坐标（逻辑地图）。"""
    world_location: dict[str, int]
    """Pygame 屏幕像素位置（本 Demo 的真实站位）。"""
    screen_x: float
    screen_y: float


# world_location 与 npc_state_tools.NPC_STATE 保持一致；
# screen_* 按 1280×720 场景下的地点语义布局：
# - 罗恩/凯：村口与外沿
# - 马修：商铺
# - 艾琳娜：酒馆
# - 赛琳：工坊（铁匠铺附近）
NPC_PROFILES: tuple[NpcProfile, ...] = (
    NpcProfile(
        npc_id="npc_guard_001",
        display_name="罗恩",
        job="城门守卫",
        task="看守城门",
        available_actions=("dialogue", "idle", "emote"),
        world_location={"x": 5, "y": 5, "z": 0},
        screen_x=112.0,
        screen_y=138.0,
    ),
    NpcProfile(
        npc_id="npc_merchant_001",
        display_name="马修",
        job="行商",
        task="售卖补给",
        available_actions=("dialogue", "move", "use_item", "idle"),
        world_location={"x": 42, "y": 18, "z": 0},
        screen_x=866.0,
        screen_y=150.0,
    ),
    NpcProfile(
        npc_id="npc_tavern_keeper_001",
        display_name="艾琳娜",
        job="酒馆掌柜",
        task="提供情报与接待来客",
        available_actions=("dialogue", "emote", "idle"),
        world_location={"x": 27, "y": 30, "z": 0},
        screen_x=792.0,
        screen_y=556.0,
    ),
    NpcProfile(
        npc_id="npc_alchemist_001",
        display_name="赛琳",
        job="药师",
        task="炼制止血散与祛瘴丹",
        available_actions=("dialogue", "use_item", "idle"),
        world_location={"x": 33, "y": 24, "z": 0},
        screen_x=188.0,
        screen_y=548.0,
    ),
    NpcProfile(
        npc_id="npc_scout_001",
        display_name="凯",
        job="巡山斥候",
        task="侦查北山谷口异动",
        available_actions=("dialogue", "move", "emote", "idle"),
        world_location={"x": 12, "y": 38, "z": 0},
        screen_x=228.0,
        screen_y=168.0,
    ),
)

PROFILE_BY_ID: dict[str, NpcProfile] = {p.npc_id: p for p in NPC_PROFILES}


def get_profile(npc_id: str) -> NpcProfile | None:
    return PROFILE_BY_ID.get(npc_id)
