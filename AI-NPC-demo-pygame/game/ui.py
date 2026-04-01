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
    """对话使用屏幕中央模态框，避免底部被任务栏/缩放裁切或 SRCALPHA 绘制异常看不到。"""

    MODAL_W = 680
    MODAL_H = 260

    def __init__(self) -> None:
        self.font = _make_font(22)
        self.small_font = _make_font(18)
        self.input_rect = pygame.Rect(0, 0, 100, 40)

    def modal_box_rect(self, screen: pygame.Surface) -> pygame.Rect:
        w, h = screen.get_size()
        return pygame.Rect(
            w // 2 - self.MODAL_W // 2,
            h // 2 - self.MODAL_H // 2,
            self.MODAL_W,
            self.MODAL_H,
        )

    def layout_chat_panel(self, screen: pygame.Surface) -> pygame.Rect:
        """与 `_draw_chat_modal` 中输入框一致，供 SDL 文本输入定位。"""
        box = self.modal_box_rect(screen)
        self.input_rect = pygame.Rect(box.x + 20, box.bottom - 68, box.w - 40, 46)
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
        if not chat_mode:
            self._draw_hint(screen, nearest_npc, nearest_dist)
        self._draw_overlay(screen, nearest_dist, stats)
        if chat_mode:
            self._draw_chat_modal(screen, chat_target, input_buffer, request_pending)

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
    ) -> None:
        if nearest_npc and nearest_dist <= SETTINGS.interact_distance:
            text = f"按 E 与「{nearest_npc.display_name}」交谈（对话框在屏幕中央）"
            color = HINT_COLOR
        else:
            text = "靠近 NPC 后按 E 开始对话"
            color = TEXT_COLOR
        surf = self.font.render(text, True, color)
        screen.blit(surf, (20, SETTINGS.window_height - 36))

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

    def _draw_chat_modal(
        self,
        screen: pygame.Surface,
        chat_target: NPC | None,
        input_buffer: str,
        request_pending: bool,
    ) -> None:
        w, h = screen.get_size()
        dim = pygame.Surface((w, h))
        dim.fill((0, 0, 0))
        dim.set_alpha(165)
        screen.blit(dim, (0, 0))

        box = self.modal_box_rect(screen)
        pygame.draw.rect(screen, (44, 50, 64), box, border_radius=14)
        pygame.draw.rect(screen, (255, 200, 60), box, width=5, border_radius=14)

        title = self.font.render("【对话】", True, (255, 230, 140))
        screen.blit(title, (box.x + 20, box.y + 18))

        line1 = self.small_font.render(
            "输入台词后按 Enter 发送 · 空行 + Enter 退出 · Esc 取消 · Ctrl+V 粘贴中文",
            True,
            HINT_COLOR,
        )
        screen.blit(line1, (box.x + 20, box.y + 52))

        name = chat_target.display_name if chat_target is not None else "NPC"
        line2 = self.font.render(f"对「{name}」说：", True, TEXT_COLOR)
        screen.blit(line2, (box.x + 20, box.y + 86))

        self.input_rect = pygame.Rect(box.x + 20, box.bottom - 68, box.w - 40, 46)
        pygame.draw.rect(screen, (22, 26, 34), self.input_rect, border_radius=10)
        pygame.draw.rect(screen, (255, 200, 60), self.input_rect, width=3, border_radius=10)

        prefix = "正在发送… " if request_pending else ""
        display = prefix + (input_buffer if input_buffer else SETTINGS.input_placeholder)
        color = (150, 155, 165) if not input_buffer and not request_pending else TEXT_COLOR
        surf = self.font.render(display[:220], True, color)
        screen.blit(surf, (self.input_rect.x + 12, self.input_rect.y + 12))

    def input_screen_rect(self) -> pygame.Rect:
        return self.input_rect
