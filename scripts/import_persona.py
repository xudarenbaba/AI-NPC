"""将 lore/persona/*.md 导入统一 memory（memory_type=persona）。"""
import sys
import hashlib
from pathlib import Path

# 项目根目录加入 path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from app.memory.long_term import LongTermMemory


def normalize_text(text: str) -> str:
    return text.strip().replace("\r\n", "\n").replace("\r", "\n")


def main() -> None:
    store = LongTermMemory()
    persona_dir = root / "lore" / "persona"
    if not persona_dir.exists():
        print("lore/persona 目录不存在，已跳过")
        return

    count = 0
    for f in sorted(persona_dir.glob("*.md")):
        npc_id = f.stem.strip()
        if not npc_id:
            continue
        text = normalize_text(f.read_text(encoding="utf-8"))
        if not text:
            continue
        dedupe_id = f"persona:{npc_id}:{hashlib.sha1(text.encode('utf-8')).hexdigest()}"
        store.add_persona(npc_id=npc_id, texts=[text], ids=[dedupe_id])
        count += 1
        print(f"  imported persona: {npc_id} <- {f.name}")
    print(f"已导入 {count} 个角色设定到 persona memory。")


if __name__ == "__main__":
    main()
