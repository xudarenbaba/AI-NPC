from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    window_width: int = 1280
    window_height: int = 720
    fps: int = 60
    player_speed: float = 180.0
    npc_speed: float = 90.0
    interact_distance: float = 80.0
    ai_base_url: str = "http://localhost:5000"
    ai_chat_path: str = "/chat"
    # LangGraph + 多轮 LLM + MCP 常需数十秒；过短会客户端先超时，误显示「走神」台词
    ai_timeout_seconds: float = 120.0
    ai_cooldown_seconds: float = 2.0
    bubble_duration_seconds: float = 4.0
    scene_location: str = "村口广场"
    scene_time: str = "白天"
    player_id: str = "player_001"
    input_max_chars: int = 500
    input_placeholder: str = "在此输入要说的话…"
    # 聊天模式下启用 SDL 文本输入（TEXTINPUT/TEXTEDITING），用于稳定支持中文 IME。
    use_sdl_text_input: bool = True
    obs_enabled: bool = True
    obs_event_limit: int = 12
    obs_sample_limit: int = 120
    obs_export_dir: str = "logs"
    obs_redact_message_len: int = 80


SETTINGS = Settings()
