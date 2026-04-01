from dataclasses import dataclass, field
from typing import Any

import pygame


@dataclass
class AiAction:
    action_type: str = "idle"
    dialogue: str = ""
    emotion: str = "neutral"
    target_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Player:
    player_id: str
    pos: pygame.Vector2
    speed: float


@dataclass
class NPC:
    npc_id: str
    display_name: str
    job: str
    task: str
    available_actions: tuple[str, ...]
    world_location: dict[str, int]
    pos: pygame.Vector2
    speed: float
    runtime_state: str = "idle"
    last_action_result: str = "none"
    dialogue_text: str = ""
    dialogue_until: float = 0.0
    move_target: pygame.Vector2 | None = None
    next_ai_time: float = 0.0

    def has_dialogue(self, now_seconds: float) -> bool:
        return now_seconds < self.dialogue_until and bool(self.dialogue_text.strip())
