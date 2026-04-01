import math
from dataclasses import dataclass

import pygame

from config import SETTINGS
from game.models import AiAction, NPC, Player


@dataclass
class World:
    width: int
    height: int
    player: Player
    npcs: list[NPC]

    @classmethod
    def create_default(cls) -> "World":
        player = Player(
            player_id=SETTINGS.player_id,
            pos=pygame.Vector2(SETTINGS.window_width * 0.5, SETTINGS.window_height * 0.5),
            speed=SETTINGS.player_speed,
        )
        npcs = [
            NPC("npc_guard_001", pygame.Vector2(220, 180), SETTINGS.npc_speed),
            NPC("npc_merchant_001", pygame.Vector2(520, 240), SETTINGS.npc_speed),
            NPC("npc_oldman_001", pygame.Vector2(760, 360), SETTINGS.npc_speed),
        ]
        return cls(SETTINGS.window_width, SETTINGS.window_height, player, npcs)

    def update_player(self, move: pygame.Vector2, dt: float) -> None:
        if move.length_squared() > 0:
            move = move.normalize()
        self.player.pos += move * self.player.speed * dt
        self.player.pos.x = max(0, min(self.width, self.player.pos.x))
        self.player.pos.y = max(0, min(self.height, self.player.pos.y))

    def update_npcs(self, dt: float) -> None:
        for npc in self.npcs:
            if npc.move_target is None:
                continue
            delta = npc.move_target - npc.pos
            dist = delta.length()
            if dist <= 1.0:
                npc.pos = npc.move_target
                npc.move_target = None
                npc.runtime_state = "idle"
                continue
            direction = delta.normalize()
            step = min(dist, npc.speed * dt)
            npc.pos += direction * step
            npc.runtime_state = "move"

    def nearest_npc(self) -> tuple[NPC | None, float]:
        closest_npc: NPC | None = None
        closest_dist = math.inf
        for npc in self.npcs:
            dist = npc.pos.distance_to(self.player.pos)
            if dist < closest_dist:
                closest_npc = npc
                closest_dist = dist
        return closest_npc, closest_dist

    def apply_action(self, npc: NPC, action: AiAction, now_seconds: float) -> str:
        if action.action_type == "dialogue":
            if action.dialogue.strip():
                npc.dialogue_text = action.dialogue.strip()
                npc.dialogue_until = now_seconds + SETTINGS.bubble_duration_seconds
            npc.runtime_state = "dialogue"
            return "success"

        if action.action_type == "move":
            target = action.extra.get("target_pos")
            if isinstance(target, list) and len(target) == 2:
                try:
                    x = float(target[0])
                    y = float(target[1])
                    npc.move_target = pygame.Vector2(
                        max(0, min(self.width, x)),
                        max(0, min(self.height, y)),
                    )
                    npc.runtime_state = "move"
                    return "success"
                except (TypeError, ValueError):
                    npc.runtime_state = "idle"
                    return "invalid_target"
            npc.runtime_state = "idle"
            return "missing_target"

        npc.runtime_state = "idle"
        return "success"
