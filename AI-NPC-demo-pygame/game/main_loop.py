import pygame

from config import SETTINGS
from game.ai_client import AiClient
from game.models import NPC
from game.ui import UI
from game.world import World


def run_game() -> None:
    pygame.init()
    screen = pygame.display.set_mode((SETTINGS.window_width, SETTINGS.window_height))
    pygame.display.set_caption("AI NPC · Pygame 演示（对接 /chat）")
    clock = pygame.time.Clock()

    world = World.create_default()
    ui = UI()
    ai_client = AiClient()

    stats: dict[str, int | str] = {"latency_ms": 0, "error_count": 0, "status": "就绪"}
    running = True

    chat_mode = False
    chat_target: NPC | None = None
    input_buffer = ""
    request_pending = False

    def enter_chat(npc: NPC) -> None:
        nonlocal chat_mode, chat_target, input_buffer
        chat_mode = True
        chat_target = npc
        input_buffer = ""
        try:
            pygame.key.start_text_input()
            pygame.key.set_text_input_rect(ui.input_screen_rect())
        except Exception:
            pass

    def exit_chat() -> None:
        nonlocal chat_mode, chat_target, input_buffer, request_pending
        chat_mode = False
        chat_target = None
        input_buffer = ""
        request_pending = False
        try:
            pygame.key.stop_text_input()
        except Exception:
            pass

    while running:
        dt = clock.tick(SETTINGS.fps) / 1000.0
        now = pygame.time.get_ticks() / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if chat_mode:
                        exit_chat()
                    else:
                        running = False
                elif chat_mode and chat_target is not None:
                    if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                        if request_pending:
                            continue
                        msg = input_buffer.strip()
                        if not msg:
                            continue
                        nearest_npc, nearest_dist = world.nearest_npc()
                        if nearest_npc is not chat_target or nearest_dist > SETTINGS.interact_distance:
                            stats["status"] = "已离开对话范围"
                            exit_chat()
                            continue
                        if now < chat_target.next_ai_time:
                            stats["status"] = "冷却中，请稍候"
                            continue
                        request_pending = True
                        result = ai_client.request_decision(
                            world.player, chat_target, msg, nearest_dist
                        )
                        request_pending = False
                        chat_target.next_ai_time = now + SETTINGS.ai_cooldown_seconds
                        stats["latency_ms"] = result.latency_ms
                        if result.ok:
                            stats["status"] = "正常"
                        else:
                            stats["error_count"] = int(stats["error_count"]) + 1
                            stats["status"] = f"异常: {result.error_message}"

                        action_result = world.apply_action(chat_target, result.action, now)
                        chat_target.last_action_result = action_result
                        if result.action.action_type == "idle" and result.action.dialogue.strip():
                            chat_target.dialogue_text = result.action.dialogue
                            chat_target.dialogue_until = now + SETTINGS.bubble_duration_seconds
                        input_buffer = ""
                    elif event.key == pygame.K_BACKSPACE:
                        input_buffer = input_buffer[:-1]
                elif event.key == pygame.K_e and not chat_mode:
                    nearest_npc, nearest_dist = world.nearest_npc()
                    can_open = (
                        nearest_npc is not None
                        and nearest_dist <= SETTINGS.interact_distance
                        and now >= nearest_npc.next_ai_time
                    )
                    if can_open and nearest_npc is not None:
                        enter_chat(nearest_npc)
            elif event.type == pygame.TEXTINPUT and chat_mode and not request_pending:
                if event.text:
                    room = SETTINGS.input_max_chars - len(input_buffer)
                    if room > 0:
                        input_buffer += event.text[:room]

        keys = pygame.key.get_pressed()
        move = pygame.Vector2(0, 0)
        if not chat_mode:
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

        ui.draw(
            screen,
            world,
            now,
            stats,
            chat_mode=chat_mode,
            chat_target=chat_target,
            input_buffer=input_buffer,
            request_pending=request_pending,
        )
        pygame.display.flip()

    try:
        pygame.key.stop_text_input()
    except Exception:
        pass
    pygame.quit()
