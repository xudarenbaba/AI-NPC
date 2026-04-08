import pygame

from config import SETTINGS
from game.constants import (
    BACKGROUND_COLOR,
    BOTTOM_BAR_BG,
    BUBBLE_BG_COLOR,
    BUBBLE_BORDER_COLOR,
    CHAT_NPC_BUBBLE_BG,
    CHAT_NPC_BUBBLE_BORDER,
    CHAT_PLAYER_BUBBLE_BG,
    CHAT_PLAYER_BUBBLE_BORDER,
    CHAT_VIEWPORT_BG,
    ERROR_COLOR,
    GRID_COLOR,
    GRID_SIZE,
    HINT_COLOR,
    NPC_ACTIVE_COLOR,
    NPC_COLOR,
    NPC_RADIUS,
    PLAYER_COLOR,
    PLAYER_RADIUS,
    SIDE_PANEL_BG,
    TEXT_COLOR,
    TOP_BAR_BG,
    ZONE_BORDER,
)
from game.layout import zone_rects
from game.models import NPC
from game.world import World


def _make_font(size: int) -> pygame.font.Font:
    """优先使用可显示中文的系统字体。"""
    return pygame.font.SysFont(
        ["Microsoft YaHei", "SimHei", "SimSun", "DengXian", "Noto Sans CJK SC"],
        size,
    )


def _wrap_text_to_width(font: pygame.font.Font, text: str, max_width: int) -> list[str]:
    """按像素宽度折行（支持中文，按字符累加）。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines_out: list[str] = []
    for para in text.split("\n"):
        if not para:
            lines_out.append("")
            continue
        current = ""
        for ch in para:
            test = current + ch
            if font.size(test)[0] <= max_width:
                current = test
            else:
                if current:
                    lines_out.append(current)
                current = ch
        if current:
            lines_out.append(current)
    return lines_out if lines_out else [""]


class UI:
    """中央对话窗：标题为 NPC 名称，中间为双方聊天记录，底部为输入行。"""

    MODAL_W = 760
    MODAL_H = 480
    TRANSCRIPT_PAD = 14
    LINE_GAP = 4
    BUBBLE_PAD_X = 12
    BUBBLE_PAD_Y = 8
    INPUT_H = 50

    def __init__(self) -> None:
        self.font = _make_font(20)
        self.small_font = _make_font(16)
        self.title_font = _make_font(24)
        self.input_rect = pygame.Rect(0, 0, 100, 40)

    def modal_outer_rect(self, screen: pygame.Surface) -> pygame.Rect:
        w, h = screen.get_size()
        return pygame.Rect(
            w // 2 - self.MODAL_W // 2,
            h // 2 - self.MODAL_H // 2,
            self.MODAL_W,
            self.MODAL_H,
        )

    def transcript_viewport_rect(self, screen: pygame.Surface) -> pygame.Rect:
        box = self.modal_outer_rect(screen)
        # 标题 + 副标题 + 焦点提示后留出记录区
        top = box.y + 108
        bottom = box.bottom - self.INPUT_H - 56
        return pygame.Rect(
            box.x + self.TRANSCRIPT_PAD,
            top,
            box.w - self.TRANSCRIPT_PAD * 2,
            max(40, bottom - top),
        )

    def layout_chat_panel(self, screen: pygame.Surface) -> pygame.Rect:
        """底部输入框，供 SDL 文本输入定位。"""
        box = self.modal_outer_rect(screen)
        self.input_rect = pygame.Rect(
            box.x + 20,
            box.bottom - self.INPUT_H - 18,
            box.w - 40,
            self.INPUT_H,
        )
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
        ime_composition: str,
        input_focused: bool,
        request_pending: bool,
        chat_transcript: list[tuple[str, str]],
        transcript_scroll: list[int],
        snap_transcript_bottom: list[bool],
    ) -> None:
        screen.fill(BACKGROUND_COLOR)
        self._draw_scene_zones(screen)
        self._draw_grid(screen)
        self._draw_top_bar(screen)
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
            self._draw_label(screen, npc.display_name, npc.pos.x - 34, npc.pos.y - 44)
            self._draw_label(screen, npc.job, npc.pos.x - 34, npc.pos.y - 24, small=True)
            if npc.has_dialogue(now_seconds):
                self._draw_bubble(screen, npc.dialogue_text, npc.pos.x + 18, npc.pos.y - 58)
        pygame.draw.circle(screen, PLAYER_COLOR, (int(world.player.pos.x), int(world.player.pos.y)), PLAYER_RADIUS)
        self._draw_label(screen, "玩家", world.player.pos.x - 20, world.player.pos.y - 36)
        self._draw_label(screen, "旅者", world.player.pos.x - 20, world.player.pos.y - 20, small=True)
        if not chat_mode:
            self._draw_hint(screen, nearest_npc, nearest_dist)
        self._draw_overlay(screen, nearest_dist, stats)
        self._draw_side_panel(screen, world, nearest_npc)
        self._draw_bottom_bar(screen)
        if chat_mode:
            self._draw_chat_dialog(
                screen,
                chat_target,
                input_buffer,
                ime_composition,
                input_focused,
                request_pending,
                chat_transcript,
                transcript_scroll,
                snap_transcript_bottom,
            )

    def _draw_grid(self, screen: pygame.Surface) -> None:
        width, height = screen.get_size()
        for x in range(0, width, GRID_SIZE):
            pygame.draw.line(screen, GRID_COLOR, (x, 0), (x, height), 1)
        for y in range(0, height, GRID_SIZE):
            pygame.draw.line(screen, GRID_COLOR, (0, y), (width, y), 1)

    def _draw_scene_zones(self, screen: pygame.Surface) -> None:
        width, height = screen.get_size()
        zones = zone_rects(width, height)
        for _key, (rect, color, label) in zones.items():
            pygame.draw.rect(screen, color, rect, border_radius=10)
            pygame.draw.rect(screen, ZONE_BORDER, rect, width=2, border_radius=10)
            label_surf = self.small_font.render(label, True, (210, 220, 230))
            screen.blit(label_surf, (rect.x + 8, rect.y + 8))

    def _draw_top_bar(self, screen: pygame.Surface) -> None:
        width, _ = screen.get_size()
        bar = pygame.Rect(0, 0, width, 46)
        pygame.draw.rect(screen, TOP_BAR_BG, bar)
        pygame.draw.line(screen, (68, 74, 88), (0, bar.bottom), (width, bar.bottom), 1)
        title = self.font.render("云渊界 · 青石村", True, (245, 235, 190))
        meta = self.small_font.render("白天 · 村口广场 · 灵潮不稳", True, (175, 185, 200))
        screen.blit(title, (14, 8))
        screen.blit(meta, (230, 15))

    def _draw_side_panel(self, screen: pygame.Surface, world: World, nearest_npc: NPC | None) -> None:
        width, height = screen.get_size()
        panel = pygame.Rect(width - 250, 54, 236, height - 112)
        pygame.draw.rect(screen, SIDE_PANEL_BG, panel, border_radius=12)
        pygame.draw.rect(screen, (70, 76, 88), panel, width=2, border_radius=12)

        header = self.font.render("角色信息", True, (230, 220, 180))
        screen.blit(header, (panel.x + 12, panel.y + 10))
        y = panel.y + 44
        gap = 8
        count = max(1, len(world.npcs))
        usable_h = panel.height - 56
        card_h = max(66, min(90, (usable_h - (count - 1) * gap) // count))
        for npc in world.npcs:
            card = pygame.Rect(panel.x + 10, y, panel.w - 20, card_h)
            active = npc is nearest_npc
            fill = (54, 62, 74) if active else (39, 44, 54)
            bd = (245, 200, 118) if active else (82, 90, 104)
            pygame.draw.rect(screen, fill, card, border_radius=8)
            pygame.draw.rect(screen, bd, card, width=2, border_radius=8)
            n1 = self.font.render(npc.display_name, True, TEXT_COLOR)
            n2 = self.small_font.render(npc.job, True, (200, 210, 220))
            task_text = npc.task if len(npc.task) <= 12 else npc.task[:12] + "…"
            n3 = self.small_font.render(task_text, True, (150, 165, 180))
            screen.blit(n1, (card.x + 10, card.y + 8))
            screen.blit(n2, (card.x + 10, card.y + 30))
            screen.blit(n3, (card.x + 10, card.y + 50))
            y += card_h + gap

    def _draw_bottom_bar(self, screen: pygame.Surface) -> None:
        width, height = screen.get_size()
        bar = pygame.Rect(0, height - 36, width, 36)
        pygame.draw.rect(screen, BOTTOM_BAR_BG, bar)
        pygame.draw.line(screen, (68, 74, 88), (0, bar.y), (width, bar.y), 1)
        hint = self.small_font.render(
            "移动: WASD/方向键  互动: E  发送: Enter  关闭对话: Esc  滚轮: 浏览记录",
            True,
            (185, 195, 210),
        )
        screen.blit(hint, (12, bar.y + 9))

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
            text = f"按 E 打开与「{nearest_npc.display_name}」的对话窗口"
            color = HINT_COLOR
        else:
            text = "靠近 NPC 后按 E 开始对话"
            color = TEXT_COLOR
        surf = self.font.render(text, True, color)
        screen.blit(surf, (20, SETTINGS.window_height - 72))

    def _draw_overlay(self, screen: pygame.Surface, nearest_dist: float, stats: dict[str, int | str]) -> None:
        status = str(stats.get("status", ""))
        err = status.startswith("异常") or status.startswith("ERR")
        lines = [
            f"最近距离: {nearest_dist:.1f} px",
            f"上次延迟: {stats['latency_ms']} ms",
            f"错误次数: {stats['error_count']}",
            f"状态: {stats['status']}",
        ]
        y = 58
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

    def _draw_chat_dialog(
        self,
        screen: pygame.Surface,
        chat_target: NPC | None,
        input_buffer: str,
        ime_composition: str,
        input_focused: bool,
        request_pending: bool,
        chat_transcript: list[tuple[str, str]],
        transcript_scroll: list[int],
        snap_transcript_bottom: list[bool],
    ) -> None:
        w, h = screen.get_size()
        dim = pygame.Surface((w, h))
        dim.fill((0, 0, 0))
        dim.set_alpha(165)
        screen.blit(dim, (0, 0))

        box = self.modal_outer_rect(screen)
        pygame.draw.rect(screen, (40, 46, 58), box, border_radius=16)
        pygame.draw.rect(screen, (255, 200, 70), box, width=4, border_radius=16)

        npc_name = chat_target.display_name if chat_target is not None else "NPC"
        npc_id = chat_target.npc_id if chat_target is not None else ""
        title = self.title_font.render(f"与「{npc_name}」对话", True, (255, 235, 160))
        screen.blit(title, (box.x + 20, box.y + 14))
        if npc_id:
            sub = self.small_font.render(
                f"{npc_id} · Enter 发送 · 空行+Enter 关闭 · Esc",
                True,
                HINT_COLOR,
            )
        else:
            sub = self.small_font.render(
                "Enter 发送 · 空行+Enter 关闭 · Esc",
                True,
                HINT_COLOR,
            )
        screen.blit(sub, (box.x + 20, box.y + 44))

        focus_tip = (
            "提示：当前输入框已获得焦点，可直接输入中文。"
            if input_focused
            else "提示：输入框未获得焦点，请先用鼠标点击游戏窗口再输入。"
        )
        focus_color = (130, 220, 160) if input_focused else (255, 175, 100)
        focus_lines = _wrap_text_to_width(
            self.small_font,
            focus_tip,
            max(200, box.w - 48),
        )
        fy = box.y + 66
        for fl in focus_lines:
            fs = self.small_font.render(fl, True, focus_color)
            screen.blit(fs, (box.x + 20, fy))
            fy += self.small_font.get_height() + 2

        vp = self.transcript_viewport_rect(screen)
        pygame.draw.rect(screen, CHAT_VIEWPORT_BG, vp, border_radius=10)
        pygame.draw.rect(screen, (70, 76, 88), vp, width=1, border_radius=10)

        bubble_max_w = max(120, vp.w - 56)
        # 预计算内容总高（与绘制循环一致）
        blocks: list[tuple[str, str, list[str], int]] = []
        total_h = 0
        for role, body in chat_transcript:
            lines = _wrap_text_to_width(self.font, body, bubble_max_w)
            label_h = self.small_font.get_height() + 4
            bubble_h = self.BUBBLE_PAD_Y * 2 + len(lines) * (self.font.get_height() + self.LINE_GAP)
            block_h = label_h + bubble_h + 10
            blocks.append((role, body, lines, block_h))
            total_h += block_h
        if request_pending:
            total_h += self.small_font.get_height() + 4 + self.font.get_height() + 20

        view_h = vp.height
        max_scroll = max(0, total_h - view_h)
        if snap_transcript_bottom and snap_transcript_bottom[0]:
            transcript_scroll[0] = max_scroll
            snap_transcript_bottom[0] = False
        transcript_scroll[0] = max(0, min(transcript_scroll[0], max_scroll))

        clip = screen.get_clip()
        screen.set_clip(vp)
        scroll = transcript_scroll[0]
        y_content = vp.y - scroll

        for role, _body, lines, block_h in blocks:
            is_player = role == "player"
            label = "你" if is_player else npc_name
            label_color = CHAT_PLAYER_BUBBLE_BORDER if is_player else CHAT_NPC_BUBBLE_BORDER
            bubble_bg = CHAT_PLAYER_BUBBLE_BG if is_player else CHAT_NPC_BUBBLE_BG
            bubble_bd = CHAT_PLAYER_BUBBLE_BORDER if is_player else CHAT_NPC_BUBBLE_BORDER

            label_s = self.small_font.render(label, True, label_color)
            if is_player:
                label_x = vp.right - label_s.get_width() - 8
            else:
                label_x = vp.x + 8
            screen.blit(label_s, (label_x, y_content))

            line_surfs = [self.font.render(t, True, TEXT_COLOR) for t in lines]
            bw = min(
                bubble_max_w,
                max((s.get_width() for s in line_surfs), default=0) + self.BUBBLE_PAD_X * 2,
            )
            bh = self.BUBBLE_PAD_Y * 2 + len(line_surfs) * (self.font.get_height() + self.LINE_GAP)
            if is_player:
                bx = vp.right - bw - 8
            else:
                bx = vp.x + 8
            by = y_content + label_s.get_height() + 4
            bubble_r = pygame.Rect(bx, by, bw, bh)
            pygame.draw.rect(screen, bubble_bg, bubble_r, border_radius=10)
            pygame.draw.rect(screen, bubble_bd, bubble_r, width=2, border_radius=10)

            ty = by + self.BUBBLE_PAD_Y
            for s in line_surfs:
                sx = bx + self.BUBBLE_PAD_X
                screen.blit(s, (sx, ty))
                ty += s.get_height() + self.LINE_GAP

            y_content += block_h

        if request_pending:
            hint = self.small_font.render(npc_name, True, CHAT_NPC_BUBBLE_BORDER)
            screen.blit(hint, (vp.x + 8, y_content))
            wait = self.font.render("正在回复…", True, (200, 200, 200))
            screen.blit(wait, (vp.x + 8, y_content + hint.get_height() + 4))

        screen.set_clip(clip)

        self.layout_chat_panel(screen)
        pygame.draw.rect(screen, (20, 24, 30), self.input_rect, border_radius=10)
        pygame.draw.rect(screen, (255, 200, 70), self.input_rect, width=2, border_radius=10)

        prefix = "等待回复中，输入已锁定 · " if request_pending else ""
        base = input_buffer if input_buffer else SETTINGS.input_placeholder
        display = prefix + base
        color = (140, 145, 155) if not input_buffer and not request_pending else TEXT_COLOR
        if request_pending:
            color = (160, 160, 165)
        surf = self.font.render(display[:300], True, color)
        screen.blit(surf, (self.input_rect.x + 12, self.input_rect.y + 14))
        if ime_composition and not request_pending:
            comp = self.font.render(f" [{ime_composition}]", True, (255, 210, 120))
            screen.blit(comp, (self.input_rect.x + 12 + surf.get_width(), self.input_rect.y + 14))

        if not request_pending and input_focused:
            ticks = pygame.time.get_ticks()
            if (ticks // 500) % 2 == 0:
                caret_x = self.input_rect.x + 12 + surf.get_width() + 2
                if ime_composition:
                    comp_w = self.font.size(f" [{ime_composition}]")[0]
                    caret_x += comp_w
                caret_y1 = self.input_rect.y + 12
                caret_y2 = self.input_rect.bottom - 12
                pygame.draw.line(screen, (245, 245, 245), (caret_x, caret_y1), (caret_x, caret_y2), 2)

        count = self.small_font.render(
            f"{len(input_buffer)}/{SETTINGS.input_max_chars}",
            True,
            (255, 150, 120) if len(input_buffer) >= SETTINGS.input_max_chars else (150, 160, 170),
        )
        screen.blit(count, (self.input_rect.right - count.get_width() - 10, self.input_rect.y - 18))

    def input_screen_rect(self) -> pygame.Rect:
        return self.input_rect
