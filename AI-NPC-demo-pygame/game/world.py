import math
from dataclasses import dataclass

import pygame

from config import SETTINGS
from game.models import AiAction, NPC, Player
from game.npc_profiles import NPC_PROFILES


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
        npcs: list[NPC] = []
        for p in NPC_PROFILES:
            npcs.append(
                NPC(
                    npc_id=p.npc_id,
                    display_name=p.display_name,
                    job=p.job,
                    task=p.task,
                    available_actions=p.available_actions,
                    world_location=dict(p.world_location),
                    pos=pygame.Vector2(p.screen_x, p.screen_y),
                    speed=SETTINGS.npc_speed,
                )
            )
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

        if action.action_type == "emote":
            if action.dialogue.strip():
                npc.dialogue_text = action.dialogue.strip()
                npc.dialogue_until = now_seconds + SETTINGS.bubble_duration_seconds
            npc.runtime_state = "emote"
            return "success"

        if action.action_type == "use_item":
            if action.dialogue.strip():
                npc.dialogue_text = action.dialogue.strip()
                npc.dialogue_until = now_seconds + SETTINGS.bubble_duration_seconds
            npc.runtime_state = "use_item"
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
