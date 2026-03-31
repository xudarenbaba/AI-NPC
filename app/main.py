""" Flask 应用：Gateway 与路由 """
import logging
from typing import Any

from flask import Flask, request, jsonify, render_template

from app.config import load_config
from app.schemas.request import ChatRequest
from app.reasoning.llm import reply_to_action
from app.langgraph_agent import build_agent_graph

logger = logging.getLogger(__name__)


def create_app(config_path: str | None = None) -> Flask:
    app = Flask(__name__)
    if config_path:
        load_config(config_path)

    # LangGraph 编排的最简链路（单链路：RAG -> Prompt -> LLM tools -> 写回Chroma）
    agent_graph = build_agent_graph()
    logger.info("Flask app created. LangGraph pipeline is ready.")

    @app.route("/", methods=["GET"])
    def index() -> str:
        """提供一个最简的网页调试界面（调用 POST /chat）"""
        return render_template("index.html")

    @app.route("/health", methods=["GET"])
    def health() -> tuple[Any, int]:
        """健康检查，用于负载均衡或运维探测"""
        logger.info("Health check called.")
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
            logger.info(
                "Chat request accepted. player_id=%s npc_id=%s message_len=%s",
                req.player_id,
                req.npc_id,
                len(req.message),
            )
        except Exception as e:
            logger.exception("Chat request validation failed")
            return jsonify({"error": str(e)}), 400

        try:
            state = agent_graph.invoke(
                {
                    "player_id": req.player_id,
                    "npc_id": req.npc_id,
                    "message": req.message,
                    "scene_info": req.scene_info or {},
                },
                {"recursion_limit": 20},
            )
            action = state.get("action")
            if action is None:
                action = reply_to_action("（思考中……）")
            logger.info(
                "Chat request completed. player_id=%s npc_id=%s action_type=%s",
                req.player_id,
                req.npc_id,
                action.action_type,
            )
            return jsonify(action.model_dump(exclude_none=True)), 200
        except Exception as e:
            logger.exception("LLM or response build failed")
            return jsonify({"error": "Internal error", "detail": str(e)}), 500

    return app


app = create_app()
