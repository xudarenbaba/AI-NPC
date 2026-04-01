"""尽量让 Pygame 窗口获得键盘焦点（Windows）。无法替代「用户点击游戏窗口」。"""

from __future__ import annotations

import sys


def try_focus_game_window() -> None:
    """
    SDL 键盘事件只发给「前台」窗口。从终端启动游戏后焦点常在终端，
    需用户点击游戏窗口；此处尝试把游戏窗口提到前台（可能被系统拒绝）。
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        import pygame

        info = pygame.display.get_wm_info()
        hwnd = info.get("window")
        if not hwnd:
            return
        u = ctypes.windll.user32
        SW_RESTORE = 9
        u.ShowWindow(hwnd, SW_RESTORE)
        u.SetForegroundWindow(hwnd)
        u.BringWindowToTop(hwnd)
    except Exception:
        pass
