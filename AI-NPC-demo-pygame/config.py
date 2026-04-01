from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    window_width: int = 960
    window_height: int = 540
    fps: int = 60
    player_speed: float = 180.0
    npc_speed: float = 90.0
    interact_distance: float = 80.0
    ai_base_url: str = "http://localhost:5000"
    ai_chat_path: str = "/chat"
    ai_timeout_seconds: float = 1.2
    ai_cooldown_seconds: float = 2.0
    bubble_duration_seconds: float = 4.0
    scene_location: str = "village_square"
    scene_time: str = "day"
    player_id: str = "player_001"


SETTINGS = Settings()
