""" 配置加载，优先使用环境变量覆盖敏感项 """
import os
from pathlib import Path
from typing import Any

import yaml


def load_config(config_path: str | Path = "config.yaml") -> dict[str, Any]:
    path = Path(config_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent.parent / path
    if not path.exists():
        return _default_config()
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    # 环境变量覆盖
    if key := os.environ.get("AI_NPC_LLM_API_KEY"):
        cfg.setdefault("llm", {})["api_key"] = key
    return cfg


def _default_config() -> dict[str, Any]:
    return {
        "use_rag": True,
        "llm": {
            "provider": "openai_compatible",
            "model": "deepseek-chat",
            "api_key": "",
            "base_url": "https://api.deepseek.com",
            "temperature": 0.2,
            "timeout_s": 60,
        },
        "embeddings": {
            "provider": "huggingface",
            "model": "BAAI/bge-small-zh-v1.5",
            "cache_dir": "models",
            # True 时不访问 Hugging Face，仅用 cache_dir 下已有文件（需模型已完整缓存）
            "local_files_only": False,
        },
        "vectorstore": {
            "persist_dir": "data/chroma",
            "collection_name": "memory",
        },
        "memory": {
            "short_term_turns": 10,
            "k_world": 3,
            "k_persona": 3,
            "k_dialogue": 5,
            "dialogue_store_min_chars": 6,
        },
        "mcp": {
            "enabled": True,
            "command": None,
            "args": None,
        },
    }
