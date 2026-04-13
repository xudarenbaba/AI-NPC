from dataclasses import dataclass, field
from typing import Any

import pygame

# 情绪标签 → 颜文字映射（纯文本，任何字体都能渲染）
_EMOTION_KAOMOJI: dict[str, str] = {
    # ── 积极 ──
    "友好": "(^_^)", "friendly": "(^_^)",
    "开心": "(^▽^)", "happy": "(^▽^)", "高兴": "(^▽^)", "愉快": "(^▽^)",
    "兴奋": "(>▽<)", "excited": "(>▽<)",
    "好奇": "(?_?)", "curious": "(?_?)",
    "温柔": "(╹◡╹)", "gentle": "(╹◡╹)", "温暖": "(╹◡╹)", "warm": "(╹◡╹)",
    "热情": "(≧∇≦)", "enthusiastic": "(≧∇≦)",
    "满足": "(˘▽˘)", "satisfied": "(˘▽˘)", "欣慰": "(˘▽˘)",
    "感激": "(◕‿◕)", "grateful": "(◕‿◕)", "感谢": "(◕‿◕)",
    "自豪": "(￣▽￣)", "proud": "(￣▽￣)", "骄傲": "(￣▽￣)",
    "期待": "(°▽°)", "hopeful": "(°▽°)", "希望": "(°▽°)",
    "调皮": "(^_~)", "playful": "(^_~)", "俏皮": "(^_~)",
    "害羞": "(*/▽＼*)", "shy": "(*/▽＼*)", "羞涩": "(*/▽＼*)",
    "得意": "(￣ω￣)", "smug": "(￣ω￣)",
    "关心": "(°▽°)", "caring": "(°▽°)", "关切": "(°▽°)",
    # ── 中性 ──
    "平静": "(-_-)", "calm": "(-_-)",
    "严肃": "(—_—)", "serious": "(—_—)",
    "neutral": "(._.)", "中立": "(._.)",
    "思考": "(°-°)", "thoughtful": "(°-°)", "沉思": "(°-°)",
    "疑惑": "(°_°?)", "wondering": "(°_°?)",
    "无奈": "(￣_￣)", "helpless": "(￣_￣)",
    "冷淡": "(-.-)", "indifferent": "(-.-)", "冷漠": "(-.-)",
    # ── 消极 ──
    "警惕": "(¬_¬)", "alert": "(¬_¬)", "警觉": "(¬_¬)", "戒备": "(¬_¬)",
    "悲伤": "(T_T)", "sad": "(T_T)", "难过": "(T_T)", "伤心": "(T_T)",
    "愤怒": "(>_<)", "angry": "(>_<)", "生气": "(>_<)",
    "害怕": "(°△°)", "fearful": "(°△°)", "恐惧": "(°△°)", "惊恐": "(°△°)",
    "困惑": "(⊙_⊙)", "confused": "(⊙_⊙)", "迷惑": "(⊙_⊙)",
    "惊讶": "(°o°)", "surprised": "(°o°)", "震惊": "(°o°)!",
    "失望": "(._. )", "disappointed": "(._. )",
    "厌烦": "(-_-#)", "annoyed": "(-_-#)", "不耐烦": "(-_-#)",
    "嫉妒": "(>_>)", "jealous": "(>_>)",
    "紧张": "(°~°)", "nervous": "(°~°)",
    "鄙视": "(¬‿¬)", "contempt": "(¬‿¬)", "轻蔑": "(¬‿¬)",
    "疲惫": "(=_=)", "tired": "(=_=)", "累": "(=_=)",
    "尴尬": "(^_^;)", "embarrassed": "(^_^;)",
    "怀疑": "(￢_￢)", "suspicious": "(￢_￢)",
    "哀求": "(>_<;)", "pleading": "(>_<;)",
}


def emotion_to_emoji(emotion: str | None) -> str:
    """将情绪标签转换为对应颜文字，未知标签返回空字符串。"""
    if not emotion:
        return ""
    key = emotion.strip()
    return _EMOTION_KAOMOJI.get(key, _EMOTION_KAOMOJI.get(key.lower(), ""))


@dataclass
class AiAction:
    action_type: str = "idle"
    dialogue: str = ""
    emotion: str = "neutral"
    target_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Player:
    player_id: str
    pos: pygame.Vector2
    speed: float


@dataclass
class NPC:
    npc_id: str
    display_name: str
    job: str
    task: str
    available_actions: tuple[str, ...]
    world_location: dict[str, int]
    pos: pygame.Vector2
    speed: float
    runtime_state: str = "idle"
    last_action_result: str = "none"
    dialogue_text: str = ""
    dialogue_until: float = 0.0
    move_target: pygame.Vector2 | None = None
    next_ai_time: float = 0.0

    def has_dialogue(self, now_seconds: float) -> bool:
        return now_seconds < self.dialogue_until and bool(self.dialogue_text.strip())
