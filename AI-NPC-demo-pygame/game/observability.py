from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from config import SETTINGS
from game.models import AiAction, NPC


@dataclass
class ObservationSnapshot:
    npc_id: str = ""
    npc_name: str = ""
    message: str = ""
    action_type: str = ""
    emotion: str = ""
    target_id: str = ""
    extra_summary: str = ""
    latency_ms: int = 0
    ok: bool = True
    error_message: str = ""
    action_result: str = ""
    runtime_state: str = ""


@dataclass
class ObservationStore:
    latest: ObservationSnapshot = field(default_factory=ObservationSnapshot)
    events: list[str] = field(default_factory=list)
    samples: list[dict[str, Any]] = field(default_factory=list)

    def push_event(self, text: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.events.append(f"[{stamp}] {text}")
        if len(self.events) > SETTINGS.obs_event_limit:
            self.events = self.events[-SETTINGS.obs_event_limit :]

    def push_sample(self, item: dict[str, Any]) -> None:
        self.samples.append(item)
        if len(self.samples) > SETTINGS.obs_sample_limit:
            self.samples = self.samples[-SETTINGS.obs_sample_limit :]


def action_extra_summary(action: AiAction) -> str:
    if action.action_type == "move":
        target = action.extra.get("target_pos")
        if isinstance(target, list) and len(target) == 2:
            return f"target_pos={target}"
    if action.extra:
        keys = ", ".join(sorted(action.extra.keys())[:4])
        return f"keys={keys}"
    return "-"


def build_snapshot(
    npc: NPC,
    message: str,
    action: AiAction,
    latency_ms: int,
    ok: bool,
    error_message: str,
    action_result: str,
) -> ObservationSnapshot:
    return ObservationSnapshot(
        npc_id=npc.npc_id,
        npc_name=npc.display_name,
        message=message[: SETTINGS.obs_redact_message_len],
        action_type=action.action_type,
        emotion=action.emotion,
        target_id=action.target_id or "",
        extra_summary=action_extra_summary(action),
        latency_ms=latency_ms,
        ok=ok,
        error_message=error_message,
        action_result=action_result,
        runtime_state=npc.runtime_state,
    )


def export_samples(samples: list[dict[str, Any]]) -> str:
    out_dir = Path(SETTINGS.obs_export_dir)
    if not out_dir.is_absolute():
        out_dir = Path(__file__).resolve().parents[1] / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"obs-{datetime.now().strftime('%Y%m%d-%H%M%S')}.jsonl"
    out_path = out_dir / filename
    with out_path.open("w", encoding="utf-8") as f:
        for item in samples:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    return str(out_path)
