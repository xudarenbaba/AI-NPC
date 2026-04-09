"""知识图谱 schema 与公共工具。"""
from __future__ import annotations

import hashlib
import re
import unicodedata

ALLOWED_LABELS: set[str] = {
    "Character",
    "Location",
    "Organization",
    "Item",
    "Quest",
    "Event",
    "Concept",
}

ALLOWED_RELATIONS: set[str] = {
    "LOCATED_IN",
    "AFFILIATED_WITH",
    "HAS_ROLE",
    "HAS_TASK",
    "CAN_DO",
    "KNOWS",
    "HOSTILE_TO",
    "TRADES_WITH",
    "REQUIRES",
    "PARTICIPATES_IN",
}


def normalize_name(name: str) -> str:
    text = unicodedata.normalize("NFKC", (name or "").strip())
    text = re.sub(r"\s+", " ", text)
    return text


def slug(name: str) -> str:
    text = normalize_name(name).lower()
    text = re.sub(r"[^\w\u4e00-\u9fff]+", "_", text, flags=re.UNICODE)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "node"


def stable_entity_id(label: str, name: str) -> str:
    """
    统一稳定 ID 规则（导入/检索共用）：
    <Label>:<slug>:<sha1_12>
    """
    l = (label or "").strip()
    if l not in ALLOWED_LABELS:
        raise ValueError(f"Unsupported label: {label}")
    canonical = normalize_name(name)
    digest_src = f"{l}|{canonical}".encode("utf-8")
    digest = hashlib.sha1(digest_src).hexdigest()[:12]
    return f"{l}:{slug(canonical)}:{digest}"

