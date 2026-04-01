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
from game.models import NPC
from game.world import World


def _make_font(size: int) -> pygame.font.Font:
    """优先使用可显示中文的系统字体。"""
    return pygame.font.SysFont(
        ["Microsoft YaHei", "SimHei", "SimSun", "DengXian", "Noto Sans CJK SC"],
        size,
    )


class UI:
    """底部对话区布局与 `layout_chat_panel` 一致，供 IME 矩形与绘制共用。"""

    PANEL_HEIGHT = 140

    def __init__(self) -> None:
        self.font = _make_font(22)
        self.small_font = _make_font(18)
        w, h = SETTINGS.window_width, SETTINGS.window_height
        self.input_rect = self._input_rect_for_height(h)

    @staticmethod
    def _input_rect_for_height(window_h: int) -> pygame.Rect:
        # 面板内：标题 → 副标题 → 输入框（与 _draw_chat_panel 对齐）
        top = window_h - UI.PANEL_HEIGHT + 66
        return pygame.Rect(20, top, SETTINGS.window_width - 40, 40)

    def layout_chat_panel(self, screen: pygame.Surface) -> pygame.Rect:
        """当前窗口尺寸下的输入框矩形（与绘制一致）。"""
        _, h = screen.get_size()
        self.input_rect = self._input_rect_for_height(h)
        return self.input_rect

    def draw(
        self,
        screen: pygame.Surface,
        world: World,
        now_seconds: float,
        stats: dict[str, int | str],
        *,
        chat_mode: bool,
        chat_target: NPC | None,
        input_buffer: str,
        request_pending: bool,
    ) -> None:
        screen.fill(BACKGROUND_COLOR)
        self._draw_grid(screen)
        nearest_npc, nearest_dist = world.nearest_npc()
        for npc in world.npcs:
            is_target = chat_mode and chat_target is npc
            in_range = npc is nearest_npc and nearest_dist <= SETTINGS.interact_distance
            if is_target:
                color = NPC_ACTIVE_COLOR
            elif in_range:
                color = NPC_ACTIVE_COLOR
            else:
                color = NPC_COLOR
            pygame.draw.circle(screen, color, (int(npc.pos.x), int(npc.pos.y)), NPC_RADIUS)
            self._draw_label(screen, npc.display_name, npc.pos.x - 40, npc.pos.y - 42)
            self._draw_label(screen, npc.job, npc.pos.x - 40, npc.pos.y - 24, small=True)
            if npc.has_dialogue(now_seconds):
                self._draw_bubble(screen, npc.dialogue_text, npc.pos.x + 18, npc.pos.y - 58)
        pygame.draw.circle(screen, PLAYER_COLOR, (int(world.player.pos.x), int(world.player.pos.y)), PLAYER_RADIUS)
        self._draw_label(screen, "玩家", world.player.pos.x - 20, world.player.pos.y - 30)
        self._draw_hint(screen, nearest_npc, nearest_dist, chat_mode, chat_target)
        self._draw_overlay(screen, nearest_dist, stats)
        if chat_mode:
            self._draw_chat_panel(screen, chat_target, input_buffer, request_pending)

    def _draw_grid(self, screen: pygame.Surface) -> None:
        width, height = screen.get_size()
        for x in range(0, width, GRID_SIZE):
            pygame.draw.line(screen, GRID_COLOR, (x, 0), (x, height), 1)
        for y in range(0, height, GRID_SIZE):
            pygame.draw.line(screen, GRID_COLOR, (0, y), (width, y), 1)

    def _draw_label(
        self,
        screen: pygame.Surface,
        text: str,
        x: float,
        y: float,
        *,
        small: bool = False,
    ) -> None:
        font = self.small_font if small else self.font
        surf = font.render(text, True, TEXT_COLOR)
        screen.blit(surf, (x, y))

    def _draw_hint(
        self,
        screen: pygame.Surface,
        nearest_npc: NPC | None,
        nearest_dist: float,
        chat_mode: bool,
        chat_target: NPC | None,
    ) -> None:
        if chat_mode and chat_target is not None:
            text = f"与「{chat_target.display_name}」对话中 — Enter 发送 · Esc 取消"
            color = HINT_COLOR
        elif chat_mode:
            text = "对话中 — Enter 发送 · Esc 取消"
            color = HINT_COLOR
        elif nearest_npc and nearest_dist <= SETTINGS.interact_distance:
            text = f"按 E 与「{nearest_npc.display_name}」交谈"
            color = HINT_COLOR
        else:
            text = "靠近 NPC 后按 E 开始对话"
            color = TEXT_COLOR
        surf = self.font.render(text, True, color)
        # 对话模式下底部有大面板，提示上移避免被挡住
        y = SETTINGS.window_height - 155 if chat_mode else SETTINGS.window_height - 100
        screen.blit(surf, (20, y))

    def _draw_overlay(self, screen: pygame.Surface, nearest_dist: float, stats: dict[str, int | str]) -> None:
        status = str(stats.get("status", ""))
        err = status.startswith("异常") or status.startswith("ERR")
        lines = [
            f"最近距离: {nearest_dist:.1f} px",
            f"上次延迟: {stats['latency_ms']} ms",
            f"错误次数: {stats['error_count']}",
            f"状态: {stats['status']}",
        ]
        y = 14
        for line in lines:
            color = ERROR_COLOR if err and line.startswith("状态:") else TEXT_COLOR
            surf = self.small_font.render(line, True, color)
            screen.blit(surf, (14, y))
            y += 20

    def _draw_bubble(self, screen: pygame.Surface, text: str, x: float, y: float) -> None:
        max_w = 280
        words: list[str] = []
        for part in text.replace("\n", " ").split(" "):
            if part:
                words.append(part)
        lines_out: list[str] = []
        line = ""
        for w in words:
            test = (line + " " + w).strip() if line else w
            if self.small_font.size(test)[0] <= max_w:
                line = test
            else:
                if line:
                    lines_out.append(line)
                line = w
        if line:
            lines_out.append(line)
        if not lines_out:
            lines_out = [text[:40] + ("…" if len(text) > 40 else "")]

        line_surfs = [self.small_font.render(t, True, TEXT_COLOR) for t in lines_out]
        total_h = sum(s.get_height() for s in line_surfs) + (len(line_surfs) - 1) * 2
        max_line_w = max(s.get_width() for s in line_surfs)
        pad_x, pad_y = 12, 10
        bg_rect = pygame.Rect(int(x), int(y), max_line_w + pad_x * 2, total_h + pad_y * 2)
        pygame.draw.rect(screen, BUBBLE_BG_COLOR, bg_rect, border_radius=6)
        pygame.draw.rect(screen, BUBBLE_BORDER_COLOR, bg_rect, width=1, border_radius=6)
        cy = bg_rect.top + pad_y
        for s in line_surfs:
            screen.blit(s, (bg_rect.left + pad_x, cy))
            cy += s.get_height() + 2

    def _draw_chat_panel(
        self,
        screen: pygame.Surface,
        chat_target: NPC | None,
        input_buffer: str,
        request_pending: bool,
    ) -> None:
        w, h = screen.get_size()
        panel_top = h - self.PANEL_HEIGHT
        panel = pygame.Rect(0, panel_top, w, self.PANEL_HEIGHT)

        overlay = pygame.Surface((w, self.PANEL_HEIGHT), pygame.SRCALPHA)
        overlay.fill((42, 48, 62, 245))
        screen.blit(overlay, (0, panel_top))
        pygame.draw.rect(screen, (255, 210, 70), panel, width=4)

        title = self.font.render(
            "【对话模式】输入后按 Enter 发送，Esc 退出 · Ctrl+V 可粘贴中文",
            True,
            (255, 230, 140),
        )
        screen.blit(title, (16, panel_top + 10))

        self.input_rect = self._input_rect_for_height(h)
        pygame.draw.rect(screen, (24, 28, 36), self.input_rect, border_radius=8)
        pygame.draw.rect(screen, (255, 210, 70), self.input_rect, width=2, border_radius=8)

        prefix = "正在发送… " if request_pending else ""
        display = prefix + (input_buffer if input_buffer else SETTINGS.input_placeholder)
        color = (160, 165, 175) if not input_buffer and not request_pending else TEXT_COLOR
        surf = self.font.render(display[:240], True, color)
        screen.blit(surf, (self.input_rect.x + 12, self.input_rect.y + 11))

        if chat_target is not None:
            sub = self.small_font.render(
                f"对「{chat_target.display_name}」说",
                True,
                HINT_COLOR,
            )
            screen.blit(sub, (16, panel_top + 38))

    def input_screen_rect(self) -> pygame.Rect:
        return self.input_rect
