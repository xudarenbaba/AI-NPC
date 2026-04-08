from __future__ import annotations

from dataclasses import dataclass

import pygame

# 统一地图布局：UI 方框与 NPC 初始落点都基于这份锚点数据。
RIGHT_PANEL_W = 250
TOP_BAR_H = 46
BOTTOM_BAR_H = 36


@dataclass(frozen=True)
class ZoneLayout:
    key: str
    label: str
    color: tuple[int, int, int]
    # 相对 playfield 的比例坐标
    x_ratio: float
    y_ratio: float
    w_ratio: float
    h_ratio: float


ZONES: tuple[ZoneLayout, ...] = (
    ZoneLayout("gate", "村口", (44, 58, 68), 0.02, 0.02, 0.26, 0.25),
    ZoneLayout("shop", "商铺", (54, 64, 52), 0.70, 0.03, 0.27, 0.22),
    ZoneLayout("square", "广场", (52, 56, 72), 0.34, 0.33, 0.34, 0.33),
    ZoneLayout("tavern", "酒馆", (66, 52, 44), 0.63, 0.72, 0.33, 0.24),
    ZoneLayout("forge", "铁匠铺", (60, 52, 46), 0.05, 0.73, 0.26, 0.23),
)

# NPC 初始位置锚点：zone_key + 区域内相对位置。
NPC_ANCHORS: dict[str, tuple[str, float, float]] = {
    "npc_guard_001": ("gate", 0.35, 0.55),
    "npc_scout_001": ("gate", 0.78, 0.68),
    "npc_merchant_001": ("shop", 0.58, 0.55),
    "npc_tavern_keeper_001": ("tavern", 0.55, 0.58),
    "npc_alchemist_001": ("square", 0.30, 0.52),
}


def playfield_rect(width: int, height: int) -> pygame.Rect:
    return pygame.Rect(16, 58, width - 290, height - 110)


def zone_rects(width: int, height: int) -> dict[str, tuple[pygame.Rect, tuple[int, int, int], str]]:
    pf = playfield_rect(width, height)
    out: dict[str, tuple[pygame.Rect, tuple[int, int, int], str]] = {}
    for z in ZONES:
        rect = pygame.Rect(
            int(pf.x + z.x_ratio * pf.w),
            int(pf.y + z.y_ratio * pf.h),
            int(z.w_ratio * pf.w),
            int(z.h_ratio * pf.h),
        )
        out[z.key] = (rect, z.color, z.label)
    return out


def npc_spawn_pos(npc_id: str, width: int, height: int) -> pygame.Vector2 | None:
    anchor = NPC_ANCHORS.get(npc_id)
    if anchor is None:
        return None
    zone_key, xr, yr = anchor
    z = zone_rects(width, height).get(zone_key)
    if z is None:
        return None
    rect, _color, _label = z
    x = rect.x + xr * rect.w
    y = rect.y + yr * rect.h
    return pygame.Vector2(float(x), float(y))
