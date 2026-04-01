# AI-NPC Pygame 演示

位于 `AI-NPC` 仓库内的独立子项目，通过 HTTP 调用本仓库后端的 `POST /chat`，在 2D 场景中演示「靠近 → 输入 → 回车 → 展示 NPC 回复」的最小闭环。

## 角色与坐标

- 角色定义与 `app/tools/npc_state_tools.py` 中 `NPC_STATE` 对齐（`npc_id`、职业、任务、`available_actions`、**世界坐标** `world_location`）。
- **屏幕坐标**在 `game/npc_profiles.py` 中单独配置（960×540 场景下的像素位置）。
- 当前 NPC：**城门守卫、行商、酒馆掌柜、药师、巡山斥候**。

## 技术栈

- Python 3.10+
- pygame
- requests

## 运行方式

1. 在项目根目录启动 AI 后端：`python run.py`（默认 `http://localhost:5000`）。
2. 安装演示依赖并运行：

```bash
cd AI-NPC-demo-pygame
pip install -r requirements.txt
python run.py
```

（可选）启用 MCP 时另起终端：`python npc_mcp/local_server.py`，并在 `config.yaml` 中 `mcp.enabled: true`。

## 操作说明

- `WASD` / 方向键：移动（**对话输入模式下禁用移动**）
- `E`：靠近 NPC 后进入对话，底部出现输入框
- 输入文字后 `Enter`：发送到 `/chat` 并显示返回台词 / 动作
- `Esc`：关闭输入框；在主界面则退出游戏

中文输入依赖系统输入法；若无法直接键入，可复制粘贴到输入框。

## 请求体补充字段（`scene_info`）

除原有字段外，会附带（后端可忽略）：

- `npc_display_name`、`npc_job`、`npc_task`、`npc_available_actions`
- `npc_world_location`（与 `NPC_STATE` 一致）
- `npc_screen_pos`、`player_screen_pos`（像素）

## 支持的动作类型

与后端 `ActionResponse` 一致：`dialogue`、`move`、`emote`、`use_item`、`idle`。  
`move` 的 `extra.target_pos` 约定为 **屏幕像素** `[x, y]`。

## 默认配置

见 `config.py`：`ai_base_url`、`交互距离`、`冷却`、`超时`、`输入最大长度` 等。
