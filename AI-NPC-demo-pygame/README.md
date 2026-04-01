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

- `WASD` / 方向键：移动（**对话模式下禁用移动**）
- **焦点**：Pygame 没有独立「输入框控件」，键盘（含 **Ctrl+V**）只会发给**当前获得焦点的窗口**。从终端启动时焦点常在终端，**请先鼠标单击游戏窗口**再输入；按 E 后会尝试把游戏窗置顶（Windows），若仍无效请手动点一下游戏画面。
- `E`：靠近 NPC 后在**屏幕中央**打开对话窗：标题为 **当前 NPC 名称**，中间为**双方聊天记录**（左侧 NPC、右侧「你」），底部为输入行
- 输入后 `Enter`：先显示你的那句话，再请求后端；收到后在同窗口追加 **NPC 回复**（等待时显示「正在回复…」）
- **空内容 + Enter**：关闭对话窗
- **鼠标滚轮**：在记录区上下滚动（新消息会自动滚到底）
- `Esc`：关闭对话窗；在主界面则退出游戏

默认 **不** 开启 SDL 文本输入（`config.py` 中 `use_sdl_text_input: false`），避免 Windows 上键盘被 IME 独占。  
中文 **Ctrl+V**：在 Windows 上会优先读系统剪贴板 **Unicode**，不依赖 `pygame.scrap` 编码。  
`ai_timeout_seconds` 默认 **120**：后端 LangGraph + 多轮 LLM + MCP 常需十余秒；若超时过短，客户端会先断开并误显示「走神」类回复。

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
