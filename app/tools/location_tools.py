"""本地工具：自然语言地点 -> 预置坐标。"""

from typing import Any

# 你可以后续替换为读取配置或地图文件
PLACE_COORDINATES: dict[str, dict[str, Any]] = {
    "村口": {"x": 10, "y": 5, "z": 10},
    "商店": {"x": 42, "y": 18, "z": 220},
    "铁匠铺": {"x": 55, "y": 12, "z": 30},
    "酒馆": {"x": 27, "y": 30, "z": 340},
    "广场": {"x": 20, "y": 20, "z": 450},
}


def resolve_location_coordinates(place_name: str) -> dict[str, Any] | None:
    """
    输入地点名，返回该地点坐标。
    - 入参: place_name(str)
    - 出参: {"place_name": str, "x": int, "y": int, "z": int} 或 None
    """
    key = (place_name or "").strip()
    if not key:
        return None
    hit = PLACE_COORDINATES.get(key)
    if hit is None:
        return None
    return {
        "place_name": key,
        "x": hit["x"],
        "y": hit["y"],
        "z": hit["z"],
    }

