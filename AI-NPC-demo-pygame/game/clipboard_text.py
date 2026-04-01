"""从系统剪贴板取文本：Windows 优先用 CF_UNICODETEXT（中文可靠），再回退 pygame.scrap。"""

from __future__ import annotations

import sys
from typing import Any


def _paste_windows_cf_unicode() -> str | None:
    if sys.platform != "win32":
        return None
    try:
        import ctypes
    except ImportError:
        return None

    CF_UNICODETEXT = 13
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    if not user32.OpenClipboard(None):
        return None
    try:
        h = user32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return None
        p = kernel32.GlobalLock(h)
        if not p:
            return None
        try:
            return ctypes.wstring_at(p)
        finally:
            kernel32.GlobalUnlock(h)
    finally:
        user32.CloseClipboard()


def _paste_pygame_scrap() -> str | None:
    try:
        import pygame
    except ImportError:
        return None
    try:
        raw: Any = pygame.scrap.get(pygame.SCRAP_TEXT)
    except Exception:
        return None
    if raw is None:
        return None
    if isinstance(raw, bytes):
        for enc in ("utf-8", "utf-16-le", "gbk"):
            try:
                return raw.decode(enc)
            except Exception:
                continue
        return raw.decode("utf-8", errors="ignore")
    return str(raw)


def get_clipboard_text() -> str | None:
    """返回剪贴板纯文本；无法读取时返回 None。"""
    if sys.platform == "win32":
        t = _paste_windows_cf_unicode()
        if t is not None and t.strip() != "":
            return t
    t2 = _paste_pygame_scrap()
    if t2 is not None and str(t2).strip() != "":
        return str(t2)
    return None
