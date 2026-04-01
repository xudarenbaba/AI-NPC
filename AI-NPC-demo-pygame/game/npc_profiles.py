"""与 app/tools/npc_state_tools.NPC_STATE 对齐的 Demo 角色与坐标。"""

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


# world_location 与 npc_state_tools.NPC_STATE 保持一致；screen_* 按 960×540 场景布局
NPC_PROFILES: tuple[NpcProfile, ...] = (
    NpcProfile(
        npc_id="npc_guard_001",
        display_name="城门守卫",
        job="守卫",
        task="看守城门",
        available_actions=("dialogue", "idle", "emote"),
        world_location={"x": 5, "y": 5, "z": 0},
        screen_x=128.0,
        screen_y=288.0,
    ),
    NpcProfile(
        npc_id="npc_merchant_001",
        display_name="行商",
        job="商人",
        task="售卖补给",
        available_actions=("dialogue", "move", "use_item", "idle"),
        world_location={"x": 42, "y": 18, "z": 0},
        screen_x=512.0,
        screen_y=224.0,
    ),
    NpcProfile(
        npc_id="npc_tavern_keeper_001",
        display_name="酒馆掌柜",
        job="酒馆掌柜",
        task="提供情报与接待来客",
        available_actions=("dialogue", "emote", "idle"),
        world_location={"x": 27, "y": 30, "z": 0},
        screen_x=416.0,
        screen_y=448.0,
    ),
    NpcProfile(
        npc_id="npc_alchemist_001",
        display_name="药师",
        job="药师",
        task="炼制止血散与祛瘴丹",
        available_actions=("dialogue", "use_item", "idle"),
        world_location={"x": 33, "y": 24, "z": 0},
        screen_x=704.0,
        screen_y=288.0,
    ),
    NpcProfile(
        npc_id="npc_scout_001",
        display_name="巡山斥候",
        job="巡山斥候",
        task="侦查北山谷口异动",
        available_actions=("dialogue", "move", "emote", "idle"),
        world_location={"x": 12, "y": 38, "z": 0},
        screen_x=160.0,
        screen_y=128.0,
    ),
)

PROFILE_BY_ID: dict[str, NpcProfile] = {p.npc_id: p for p in NPC_PROFILES}


def get_profile(npc_id: str) -> NpcProfile | None:
    return PROFILE_BY_ID.get(npc_id)
