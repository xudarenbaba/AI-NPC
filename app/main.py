""" Flask 应用：Gateway 与路由 """
import logging
from typing import Any

from flask import Flask, request, jsonify, render_template

from app.config import load_config
from app.schemas.request import ChatRequest
from app.schemas.response import ActionResponse
from app.reasoning.prompts import build_messages
from app.reasoning.llm import call_llm_with_tools, reply_to_action
from app.memory.short_term import ShortTermMemory
from app.memory.long_term import LongTermMemory
from app.memory.consolidation import consolidate_turn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

short_term = ShortTermMemory()
long_term = LongTermMemory()


def create_app(config_path: str | None = None) -> Flask:
    app = Flask(__name__)
    if config_path:
        load_config(config_path)

    @app.route("/", methods=["GET"])
    def index() -> str:
        """提供一个最简的网页调试界面（调用 POST /chat）"""
        return render_template("index.html")

    @app.route("/health", methods=["GET"])
    def health() -> tuple[Any, int]:
        """健康检查，用于负载均衡或运维探测"""
        return jsonify({"status": "ok"}), 200

    @app.route("/chat", methods=["POST"])
    def chat() -> tuple[Any, int]:
        """接收游戏状态与玩家对话，返回 NPC 动作指令 JSON"""
        try:
            body = request.get_json(force=True, silent=True)
            if not body:
                return jsonify({"error": "Invalid JSON body"}), 400
            req = ChatRequest(
                player_id=body.get("player_id", ""),
                message=body.get("message", ""),
                scene_info=body.get("scene_info") or {},
                npc_id=body.get("npc_id"),
            )
            if not req.player_id or not req.message:
                return jsonify({"error": "player_id and message are required"}), 400
        except Exception as e:
            logger.exception("Chat request validation failed")
            return jsonify({"error": str(e)}), 400

        try:
            use_rag = load_config().get("use_rag", True)
            short_history = short_term.get_recent(req.player_id, npc_id=req.npc_id)
            long_chunks = []
            if use_rag:
                # 把 npc_id 一起纳入检索查询，尽量召回更贴合当前目标 NPC 的 lore/记忆片段
                query = f"npc_id:{req.npc_id}\nscene:{req.scene_info}\nplayer:{req.player_id}\nmessage:{req.message}"
                if req.scene_info:
                    query = f"{query}"
                long_chunks = long_term.search(
                    query,
                    filter_by_player=req.player_id,
                    filter_by_npc=req.npc_id,
                    include_lore=True,
                )

            messages = build_messages(
                player_message=req.message,
                npc_id=req.npc_id,
                scene_info=req.scene_info,
                short_term_history=short_history,
                long_term_chunks=long_chunks if long_chunks else None,
            )
            action = call_llm_with_tools(messages)
            if action is None:
                action = reply_to_action("（思考中……）")

            short_term.add_turn(req.player_id, "user", req.message, req.npc_id)
            short_term.add_turn(
                req.player_id,
                "assistant",
                action.dialogue,
                req.npc_id,
            )

            if load_config().get("use_consolidation", True):
                consolidate_turn(
                    player_id=req.player_id,
                    npc_id=req.npc_id,
                    user_message=req.message,
                    assistant_message=action.dialogue,
                    scene_info=req.scene_info,
                )

            return jsonify(action.model_dump(exclude_none=True)), 200
        except Exception as e:
            logger.exception("LLM or response build failed")
            return jsonify({"error": "Internal error", "detail": str(e)}), 500

    return app


app = create_app()
