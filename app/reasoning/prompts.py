""" System / User Prompt 组装 """
from typing import Any


def build_messages(
    player_message: str,
    npc_id: str | None = None,
    scene_info: dict[str, Any] | None = None,
    short_term_history: list[dict[str, Any]] | None = None,
    long_term_chunks: list[str] | None = None,
    system_extra: str | None = None,
) -> list[dict[str, Any]]:
    """
    组装发给 LLM 的消息：角色设定 + 长期记忆 + 短期对话 + 当前输入。
    要求模型通过 Function Calling 输出结构化动作。
    """
    system_parts = [
        "你是一位游戏中的 NPC，根据玩家的对话做出自然、符合角色设定的回复。",
        "你必须通过调用 npc_action 工具来输出你的回复与动作，不要直接在对话内容里回复。",
        "npc_action 的 dialogue 字段填写你对玩家说的台词（第一人称、简短），可选的 emotion、action_type 等按需填写。",
    ]
    if npc_id:
        system_parts.append(f"当前你要扮演的 NPC_id 是：{npc_id}。你必须遵守该 NPC 的行为限制与职责，不能假装成其他 NPC。")
    if system_extra:
        system_parts.append(system_extra)
    if long_term_chunks:
        system_parts.append("\n【以下是与当前对话相关的背景或记忆，请酌情参考】\n")
        system_parts.append("\n".join(long_term_chunks))
    system_content = "\n".join(system_parts)

    user_parts = []
    if scene_info:
        user_parts.append(f"[场景] {scene_info}")
    if short_term_history:
        for turn in short_term_history:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            user_parts.append(f"{'玩家' if role == 'user' else 'NPC'}: {content}")
    user_parts.append(f"玩家: {player_message}")
    user_content = "\n".join(user_parts)

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]
