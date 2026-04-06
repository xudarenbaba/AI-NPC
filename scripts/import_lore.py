"""将 lore 目录下的文本文件导入统一 memory（memory_type=world）。"""
import sys
from pathlib import Path

# 项目根目录加入 path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from app.memory.long_term import LongTermMemory


def chunk_text(text: str, max_len: int = 400) -> list[str]:
    """按段落或长度切分为片段"""
    parts = []
    for para in text.split("\n\n"):
        para = para.strip()
        if not para or para.startswith("#"):
            continue
        if len(para) <= max_len:
            parts.append(para)
        else:
            for i in range(0, len(para), max_len):
                parts.append(para[i : i + max_len])
    return parts


def main() -> None:
    lore_dir = root / "lore"
    if not lore_dir.exists():
        print("lore 目录不存在，已跳过")
        return
    store = LongTermMemory()
    all_chunks = []
    for f in sorted(lore_dir.glob("**/*.md")):
        text = f.read_text(encoding="utf-8")
        chunks = chunk_text(text)
        all_chunks.extend(chunks)
        print(f"  {f.name}: {len(chunks)} 段")
    if not all_chunks:
        print("未找到可导入的 .md 内容")
        return
    store.add_world(all_chunks)
    print(f"已导入 {len(all_chunks)} 段到 world memory。")


if __name__ == "__main__":
    main()
