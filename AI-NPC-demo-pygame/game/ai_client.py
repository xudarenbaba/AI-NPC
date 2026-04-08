import time
from dataclasses import dataclass
from typing import Any

import requests

from config import SETTINGS
from game.models import AiAction, NPC, Player


VALID_ACTION_TYPES = frozenset({"dialogue", "move", "emote", "use_item", "idle"})


@dataclass
class AiClientResult:
    action: AiAction
    ok: bool
    latency_ms: int
    error_message: str = ""
    request_payload: dict[str, Any] | None = None
    response_payload: dict[str, Any] | None = None


class AiClient:
    def __init__(self) -> None:
        self.chat_url = f"{SETTINGS.ai_base_url.rstrip('/')}{SETTINGS.ai_chat_path}"

    def request_decision(
        self,
        player: Player,
        npc: NPC,
        message: str,
        distance_to_player: float,
    ) -> AiClientResult:
        payload: dict[str, Any] = {
            "player_id": player.player_id,
            "npc_id": npc.npc_id,
            "message": message,
            "scene_info": {
                "location": SETTINGS.scene_location,
                "time": SETTINGS.scene_time,
                "distance_to_player": round(distance_to_player, 2),
                "npc_runtime_state": npc.runtime_state,
                "last_action_result": npc.last_action_result,
                "npc_display_name": npc.display_name,
                "npc_job": npc.job,
                "npc_task": npc.task,
                "npc_available_actions": list(npc.available_actions),
                "npc_world_location": dict(npc.world_location),
                "npc_screen_pos": {"x": round(float(npc.pos.x), 1), "y": round(float(npc.pos.y), 1)},
                "player_screen_pos": {
                    "x": round(float(player.pos.x), 1),
                    "y": round(float(player.pos.y), 1),
                },
            },
        }
        start = time.perf_counter()
        tout = SETTINGS.ai_timeout_seconds
        # (连接超时, 读取超时)：本机后端连接应很快，推理可能很慢
        timeout_arg: float | tuple[float, float] = (min(15.0, tout), tout)
        try:
            response = requests.post(self.chat_url, json=payload, timeout=timeout_arg)
            latency_ms = int((time.perf_counter() - start) * 1000)
            response.raise_for_status()
            data = response.json()
            action_type = str(data.get("action_type", "")).strip().lower()
            if action_type not in VALID_ACTION_TYPES:
                return AiClientResult(
                    action=AiAction(action_type="idle", dialogue=""),
                    ok=False,
                    latency_ms=latency_ms,
                    error_message="invalid action_type",
                    request_payload=payload,
                    response_payload=data if isinstance(data, dict) else None,
                )

            action = AiAction(
                action_type=action_type,
                dialogue=str(data.get("dialogue", "")),
                emotion=str(data.get("emotion", "neutral")),
                target_id=data.get("target_id"),
                extra=data.get("extra") if isinstance(data.get("extra"), dict) else {},
            )
            return AiClientResult(
                action=action,
                ok=True,
                latency_ms=latency_ms,
                request_payload=payload,
                response_payload=data if isinstance(data, dict) else None,
            )
        except requests.Timeout:
            latency_ms = int((time.perf_counter() - start) * 1000)
            return AiClientResult(
                action=AiAction(action_type="dialogue", dialogue="我刚刚走神了，稍后再聊。"),
                ok=False,
                latency_ms=latency_ms,
                error_message="timeout",
                request_payload=payload,
            )
        except requests.RequestException as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            return AiClientResult(
                action=AiAction(action_type="idle", dialogue="现在信号不太好。"),
                ok=False,
                latency_ms=latency_ms,
                error_message=str(exc),
                request_payload=payload,
            )
        except ValueError:
            latency_ms = int((time.perf_counter() - start) * 1000)
            return AiClientResult(
                action=AiAction(action_type="idle", dialogue="我没听清你的话。"),
                ok=False,
                latency_ms=latency_ms,
                error_message="invalid json",
                request_payload=payload,
            )
