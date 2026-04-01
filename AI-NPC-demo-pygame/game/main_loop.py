import pygame

from config import SETTINGS
from game.ai_client import AiClient
from game.ui import UI
from game.world import World


def run_game() -> None:
    pygame.init()
    screen = pygame.display.set_mode((SETTINGS.window_width, SETTINGS.window_height))
    pygame.display.set_caption("AI NPC Pygame Demo")
    clock = pygame.time.Clock()

    world = World.create_default()
    ui = UI()
    ai_client = AiClient()

    stats: dict[str, int | str] = {"latency_ms": 0, "error_count": 0, "status": "READY"}
    running = True

    while running:
        dt = clock.tick(SETTINGS.fps) / 1000.0
        now = pygame.time.get_ticks() / 1000.0
        interact_pressed = False

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_e:
                    interact_pressed = True

        keys = pygame.key.get_pressed()
        move = pygame.Vector2(0, 0)
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            move.y -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            move.y += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            move.x -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            move.x += 1

        world.update_player(move, dt)
        world.update_npcs(dt)

        nearest_npc, nearest_dist = world.nearest_npc()
        can_interact = (
            nearest_npc is not None
            and nearest_dist <= SETTINGS.interact_distance
            and now >= nearest_npc.next_ai_time
        )

        if interact_pressed and can_interact and nearest_npc is not None:
            result = ai_client.request_decision(world.player, nearest_npc, "你好", nearest_dist)
            nearest_npc.next_ai_time = now + SETTINGS.ai_cooldown_seconds
            stats["latency_ms"] = result.latency_ms
            if result.ok:
                stats["status"] = "OK"
            else:
                stats["error_count"] = int(stats["error_count"]) + 1
                stats["status"] = f"ERR: {result.error_message}"

            action_result = world.apply_action(nearest_npc, result.action, now)
            nearest_npc.last_action_result = action_result
            if result.action.action_type == "idle" and result.action.dialogue.strip():
                nearest_npc.dialogue_text = result.action.dialogue
                nearest_npc.dialogue_until = now + SETTINGS.bubble_duration_seconds

        ui.draw(screen, world, now, stats)
        pygame.display.flip()

    pygame.quit()
