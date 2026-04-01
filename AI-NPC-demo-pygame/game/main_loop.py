import os

import pygame

from config import SETTINGS
from game.ai_client import AiClient
from game.models import NPC
from game.window_focus import try_focus_game_window
from game.ui import UI
from game.world import World


def _is_physical_e_key(event: pygame.event.Event) -> bool:
    if event.type != pygame.KEYDOWN:
        return False
    if event.key == pygame.K_e:
        return True
    sc = getattr(event, "scancode", -1)
    code_e = getattr(pygame, "SCANCODE_E", 8)
    return sc == code_e


def _append_input(buffer: str, text: str) -> str:
    room = SETTINGS.input_max_chars - len(buffer)
    if room <= 0:
        return buffer
    return buffer + text[:room]


def _is_effectively_empty_message(s: str) -> bool:
    """去掉空白与常见零宽字符，避免「看不见的内容」误触发发送。"""
    if not s:
        return True
    for zw in ("\u200b", "\u200c", "\u200d", "\ufeff"):
        s = s.replace(zw, "")
    return len(s.strip()) == 0


def run_game() -> None:
    if SETTINGS.use_sdl_text_input:
        os.environ.setdefault("SDL_IME_SHOW_UI", "1")

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
    ime_pending = False
    chat_transcript: list[tuple[str, str]] = []
    transcript_scroll = [0]
    snap_transcript_bottom = [True]

    def enter_chat(npc: NPC) -> None:
        nonlocal chat_mode, chat_target, input_buffer, ime_pending
        chat_mode = True
        chat_target = npc
        input_buffer = ""
        chat_transcript.clear()
        transcript_scroll[0] = 0
        snap_transcript_bottom[0] = True
        if SETTINGS.use_sdl_text_input:
            ime_pending = True
        try_focus_game_window()
        try:
            pygame.mouse.set_visible(True)
        except Exception:
            pass

    def exit_chat() -> None:
        nonlocal chat_mode, chat_target, input_buffer, request_pending, ime_pending
        chat_mode = False
        chat_target = None
        input_buffer = ""
        request_pending = False
        ime_pending = False
        chat_transcript.clear()
        transcript_scroll[0] = 0
        if SETTINGS.use_sdl_text_input:
            try:
                pygame.key.stop_text_input()
            except Exception:
                pass

    def draw_frame(now: float) -> None:
        ui.draw(
            screen,
            world,
            now,
            stats,
            chat_mode=chat_mode,
            chat_target=chat_target,
            input_buffer=input_buffer,
            request_pending=request_pending,
            chat_transcript=chat_transcript,
            transcript_scroll=transcript_scroll,
            snap_transcript_bottom=snap_transcript_bottom,
        )
        pygame.display.flip()

    while running:
        dt = clock.tick(SETTINGS.fps) / 1000.0
        now = pygame.time.get_ticks() / 1000.0

        if ime_pending and chat_mode and SETTINGS.use_sdl_text_input:
            try:
                r = ui.layout_chat_panel(screen)
                pygame.key.start_text_input()
                pygame.key.set_text_input_rect(r)
            except Exception:
                pass
            ime_pending = False

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEWHEEL and chat_mode:
                transcript_scroll[0] += int(event.y) * 28
                snap_transcript_bottom[0] = False
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
                        if _is_effectively_empty_message(input_buffer):
                            exit_chat()
                            continue
                        msg = input_buffer.strip()
                        nearest_npc, nearest_dist = world.nearest_npc()
                        if nearest_npc is not chat_target or nearest_dist > SETTINGS.interact_distance:
                            stats["status"] = "已离开对话范围"
                            exit_chat()
                            continue
                        if now < chat_target.next_ai_time:
                            stats["status"] = "冷却中，请稍候"
                            continue

                        chat_transcript.append(("player", msg))
                        input_buffer = ""
                        snap_transcript_bottom[0] = True
                        draw_frame(now)

                        request_pending = True
                        snap_transcript_bottom[0] = True
                        draw_frame(now)

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

                        reply = (result.action.dialogue or "").strip()
                        if not reply:
                            if result.ok:
                                reply = "（本次未返回台词）"
                            else:
                                reply = f"（请求失败）{result.error_message}"
                        chat_transcript.append(("npc", reply))
                        snap_transcript_bottom[0] = True

                        action_result = world.apply_action(chat_target, result.action, now)
                        chat_target.last_action_result = action_result
                        if result.action.action_type == "idle" and result.action.dialogue.strip():
                            chat_target.dialogue_text = result.action.dialogue
                            chat_target.dialogue_until = now + SETTINGS.bubble_duration_seconds

                    elif event.key == pygame.K_BACKSPACE and not request_pending:
                        input_buffer = input_buffer[:-1]
                    elif (
                        not SETTINGS.use_sdl_text_input
                        and not request_pending
                        and event.unicode
                        and not (event.mod & pygame.KMOD_CTRL)
                    ):
                        ch = event.unicode
                        if ch.isprintable() and ch not in "\r\n\t":
                            input_buffer = _append_input(input_buffer, ch)
                elif _is_physical_e_key(event) and not chat_mode:
                    nearest_npc, nearest_dist = world.nearest_npc()
                    can_open = (
                        nearest_npc is not None
                        and nearest_dist <= SETTINGS.interact_distance
                        and now >= nearest_npc.next_ai_time
                    )
                    if can_open and nearest_npc is not None:
                        enter_chat(nearest_npc)
            elif event.type == pygame.TEXTINPUT and chat_mode and not request_pending:
                if SETTINGS.use_sdl_text_input and event.text:
                    input_buffer = _append_input(input_buffer, event.text)

        if chat_mode and SETTINGS.use_sdl_text_input:
            try:
                pygame.key.set_text_input_rect(ui.layout_chat_panel(screen))
            except Exception:
                pass

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

        draw_frame(now)

    if SETTINGS.use_sdl_text_input:
        try:
            pygame.key.stop_text_input()
        except Exception:
            pass
    pygame.quit()
