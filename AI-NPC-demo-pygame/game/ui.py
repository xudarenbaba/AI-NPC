import pygame

from config import SETTINGS
from game.constants import (
    BACKGROUND_COLOR,
    BUBBLE_BG_COLOR,
    BUBBLE_BORDER_COLOR,
    ERROR_COLOR,
    GRID_COLOR,
    GRID_SIZE,
    HINT_COLOR,
    NPC_ACTIVE_COLOR,
    NPC_COLOR,
    NPC_RADIUS,
    PLAYER_COLOR,
    PLAYER_RADIUS,
    TEXT_COLOR,
)
from game.world import World


class UI:
    def __init__(self) -> None:
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 20)

    def draw(self, screen: pygame.Surface, world: World, now_seconds: float, stats: dict[str, int | str]) -> None:
        screen.fill(BACKGROUND_COLOR)
        self._draw_grid(screen)
        nearest_npc, nearest_dist = world.nearest_npc()
        for npc in world.npcs:
            color = NPC_ACTIVE_COLOR if npc is nearest_npc and nearest_dist <= SETTINGS.interact_distance else NPC_COLOR
            pygame.draw.circle(screen, color, (int(npc.pos.x), int(npc.pos.y)), NPC_RADIUS)
            self._draw_label(screen, npc.npc_id, npc.pos.x - 45, npc.pos.y - 30)
            if npc.has_dialogue(now_seconds):
                self._draw_bubble(screen, npc.dialogue_text, npc.pos.x + 18, npc.pos.y - 50)
        pygame.draw.circle(screen, PLAYER_COLOR, (int(world.player.pos.x), int(world.player.pos.y)), PLAYER_RADIUS)
        self._draw_label(screen, "PLAYER", world.player.pos.x - 25, world.player.pos.y - 30)
        self._draw_hint(screen, nearest_npc, nearest_dist)
        self._draw_overlay(screen, nearest_dist, stats)

    def _draw_grid(self, screen: pygame.Surface) -> None:
        width, height = screen.get_size()
        for x in range(0, width, GRID_SIZE):
            pygame.draw.line(screen, GRID_COLOR, (x, 0), (x, height), 1)
        for y in range(0, height, GRID_SIZE):
            pygame.draw.line(screen, GRID_COLOR, (0, y), (width, y), 1)

    def _draw_label(self, screen: pygame.Surface, text: str, x: float, y: float) -> None:
        surf = self.small_font.render(text, True, TEXT_COLOR)
        screen.blit(surf, (x, y))

    def _draw_hint(self, screen: pygame.Surface, nearest_npc, nearest_dist: float) -> None:
        text = "靠近 NPC 按 E 交互"
        color = TEXT_COLOR
        if nearest_npc and nearest_dist <= SETTINGS.interact_distance:
            text = f"按 E 与 {nearest_npc.npc_id} 对话"
            color = HINT_COLOR
        surf = self.font.render(text, True, color)
        screen.blit(surf, (20, SETTINGS.window_height - 32))

    def _draw_overlay(self, screen: pygame.Surface, nearest_dist: float, stats: dict[str, int | str]) -> None:
        lines = [
            f"Nearest Dist: {nearest_dist:.1f}px",
            f"Last latency: {stats['latency_ms']}ms",
            f"Errors: {stats['error_count']}",
            f"Status: {stats['status']}",
        ]
        y = 14
        for line in lines:
            color = ERROR_COLOR if line.startswith("Status: ERR") else TEXT_COLOR
            surf = self.small_font.render(line, True, color)
            screen.blit(surf, (14, y))
            y += 18

    def _draw_bubble(self, screen: pygame.Surface, text: str, x: float, y: float) -> None:
        surf = self.small_font.render(text, True, TEXT_COLOR)
        rect = surf.get_rect()
        rect.topleft = (x, y)
        bg_rect = rect.inflate(14, 10)
        pygame.draw.rect(screen, BUBBLE_BG_COLOR, bg_rect, border_radius=6)
        pygame.draw.rect(screen, BUBBLE_BORDER_COLOR, bg_rect, width=1, border_radius=6)
        screen.blit(surf, rect)
